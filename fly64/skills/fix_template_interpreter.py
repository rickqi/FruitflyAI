#!/usr/bin/env python3
"""
Fly64 FixTemplateInterpreter — LLM-assisted structured directive interpreter.

Extends the heuristic ``parse_fix_template`` parser (in ``fix_executor.py``) with
an LLM subagent fallback for templates that cannot be fully resolved into
structured directives (action="manual").

Directive contract
------------------
Producer: :func:`parse_extended_directives` (this module) and
``fix_executor.parse_fix_template``.  Consumer: ``FixExecutor.execute``.
Both producers must emit the *same* names and payload keys, otherwise the
executor answers ``unknown action`` or silently drops the edit:

==================  =========================================  ==================
action              template form                              payload keys
==================  =========================================  ==================
``replace``         ``# Find:`` / ``# Search:`` + ``# Replace:``  find, replace
``change``          ``# Change:`` + ``# To:`` (or ``# Add:``)  change, to
``insert_after``    ``# Add after <anchor>``, ``# Add below   find, add
                    <anchor>``, ``# After:``, or ``# Find:``
                    with an ``# Add:`` payload
``insert_before``   ``# Add before <anchor>``, ``# Insert      find, add
                    before <anchor>``, ``# Before:``
``append``          ``# Add:`` with no anchor                  add
``manual``          no structured payload at all               manual_instructions
``advisory``        classified natural-language verify /       advisory_type,
                    investigate template (produced only by      manual_instructions
                    ``fix_executor._interpret_natural_language``)
==================  =========================================  ==================

``# Files: a, b`` makes the following block apply to every listed file (one
directive per file).  A ``# Code:`` block — or, for an anchor written without
that marker, the raw lines that follow it — becomes the directive's ``add``
payload.  ``# Check:`` / ``# Adjust:`` / ``# Symbol:`` / ``# Note:`` lines are
advisory: they never become payload, and a template made only of them resolves
to ``manual`` so it cannot be reported as applied.

Key responsibilities:

1.  **LLM-assisted structured parsing**
    For templates that have some directives but contain manual/unstructured
    sections, the interpreter delegates to the subagent to infer the missing
    pieces and produce a unified, structured template.

2.  **Pure-manual interpretation**
    For templates that are entirely free-form (no ``# File:`` / ``# Find:`` /
    ``# Replace:`` / ``# Change:`` / ``# To:`` / ``# Add:`` / ``# After:`` /
    ``# Before:`` directives), the interpreter requests an LLM subagent to
    derive the best-effort structured directives and still includes the
    original instructions as ``manual_instructions``.

3.  **Template rewriting**
    For each pattern registered in the catalog, a ``rewrite()`` method
    translates its natural-language ``fix_template`` into a fully-structured
    multi-directive form (``# File:`` + ``# Change:`` + ``# To:`` blocks).

Usage::

    interpreter = FixTemplateInterpreter()
    directives = interpreter.interpret(template)
    if not directives:
        print("Could not interpret template — manual action required")

    structured_template = interpreter.rewrite(pattern)
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════
# Data classes
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class InterpretationResult:
    """Result of interpreting (and possibly rewriting) a template.

    Attributes
    ----------
    directives : list[dict]
        Fully-resolved structured directives (same shape as ``parse_fix_template``
        output).  Each dict has at least ``file``, ``action`` (one of
        ``replace``, ``change``, ``insert_after``, ``insert_before``, ``append``,
        ``manual``).
    manual_instructions : str
        The original free-form instructions, retained so human reviewers or the
        coach can audit what the LLM derived.
    confidence : float
        Confidence score in [0.0, 1.0] — 1.0 means the template was fully
        parsed heuristically without LLM fallback.
    used_llm : bool
        True when the LLM subagent was actually invoked.
    """
    directives: list[dict] = field(default_factory=list)
    manual_instructions: str = ""
    confidence: float = 1.0
    used_llm: bool = False


# ═══════════════════════════════════════════════════════════════════════
# New structured-directive parser extensions
# ═══════════════════════════════════════════════════════════════════════

# Extended regex patterns beyond the original parse_fix_template
RE_FILE = re.compile(r"^#\s*File:\s*(.+)$", re.IGNORECASE)
RE_FILES = re.compile(r"^#\s*Files:\s*(.+)$", re.IGNORECASE)
RE_FIND = re.compile(r"^#\s*(?:Find|Search):\s*(.+)$", re.IGNORECASE)
RE_CHANGE = re.compile(r"^#\s*Change:\s*(.+)$", re.IGNORECASE)
RE_TO = re.compile(r"^#\s*To:\s*(.+)$", re.IGNORECASE)
RE_REPLACE = re.compile(r"^#\s*Replace:\s*(.*)$", re.IGNORECASE)
RE_ADD = re.compile(r"^#\s*Add:\s*(.*)$", re.IGNORECASE)
RE_ADD_AFTER = re.compile(
    r"^#\s*Add\s+(?:after|below)\s+(.+)$", re.IGNORECASE
)
RE_INSERT_BEFORE = re.compile(
    r"^#\s*(?:Insert|Add)\s+before\s+(.+)$", re.IGNORECASE
)
RE_AFTER = re.compile(r"^#\s*After:\s*(.+)$", re.IGNORECASE)
RE_BEFORE = re.compile(r"^#\s*Before:\s*(.+)$", re.IGNORECASE)
RE_ADJUST = re.compile(
    r"^#\s*Adjust:\s*(.+)$", re.IGNORECASE
)
RE_SYMBOL = re.compile(
    r"^#\s*Symbol:\s*(.+)$", re.IGNORECASE
)
# ``# Code:`` marks the start of the payload of the pending anchor.
RE_CODE_MARKER = re.compile(r"^#\s*Code:?\s*$", re.IGNORECASE)
# Comment lines that are advisory by definition: they never become payload.
RE_ADVISORY = re.compile(
    r"^#\s*(?:Check|Adjust|Symbol|Note|Verify|Investigate|Fix):",
    re.IGNORECASE,
)


def parse_extended_directives(lines: list[str]) -> list[dict]:
    """Parse the extended directive set into ``FixExecutor``-ready directives.

    Recognised forms (see the module docstring for the full action table):

    * ``# File: <path>`` — target file for the following block.
    * ``# Files: <a>, <b>`` — the following block applies to *every* listed
      file; one directive per file is emitted.  A registration marker is never
      left in the output, because ``FixExecutor.execute`` would report it as
      ``unknown action``.
    * ``# Find:`` / ``# Search:`` + ``# Replace:`` — ``replace``.
    * ``# Change:`` + ``# To:`` (or ``# Change:`` + ``# Add:``) — ``change``
      with the ``change``/``to`` payload keys the executor consumes.
    * ``# Add after <anchor>`` / ``# Add below <anchor>`` — ``insert_after``.
    * ``# Add before <anchor>`` / ``# Insert before <anchor>`` — ``insert_before``.
    * ``# After:`` / ``# Before:`` — the same two anchor forms.
    * ``# Add:`` with no anchor — ``append``.
    * ``# Code:`` — every following line up to the next directive becomes the
      pending anchor's ``add`` payload.  For an anchor written without the
      marker, the first raw (non-comment) line starts that payload.

    ``# Check:`` / ``# Adjust:`` / ``# Symbol:`` / ``# Note:`` and any other
    non-directive line are advisory.  A template with no executable payload
    resolves to a single ``[{"action": "manual", ...}]`` carrying the original
    text, so an advisory-only template can never be reported as applied.
    """
    directives: list[dict] = []
    current_files: list[str] = []
    current_find: str = ""
    current_replace: str = ""
    current_add: str = ""
    current_after: str = ""
    current_before: str = ""
    change_buffer: str = ""         # holds text from # Change:
    code_lines: list[str] = []      # payload of the pending anchor
    in_code: bool = False
    manual_lines: list[str] = []
    has_any_directive = False

    def _flush():
        nonlocal current_files, current_find, current_replace
        nonlocal current_add, current_after, current_before
        nonlocal change_buffer, code_lines, in_code, has_any_directive
        if not current_files:
            return
        has_any_directive = True

        add_text = current_add
        if code_lines:
            block = "\n".join(code_lines).strip("\n")
            add_text = "%s\n%s" % (add_text, block) if add_text else block

        payload: dict | None = None

        # Priority: Change+To pair → change
        if change_buffer and current_replace:
            payload = {"action": "change",
                       "change": change_buffer.strip(),
                       "to": current_replace.strip()}
        elif change_buffer and add_text:
            payload = {"action": "change",
                       "change": change_buffer.strip(),
                       "to": add_text.strip()}
        elif current_find and current_replace:
            payload = {"action": "replace",
                       "find": current_find.strip(),
                       "replace": current_replace.strip()}
        elif current_after and add_text:
            payload = {"action": "insert_after",
                       "find": current_after.strip(),
                       "add": add_text}
        elif current_before and add_text:
            payload = {"action": "insert_before",
                       "find": current_before.strip(),
                       "add": add_text}
        elif current_find and add_text:
            payload = {"action": "insert_after",
                       "find": current_find.strip(),
                       "add": add_text}
        elif add_text:
            payload = {"action": "append", "add": add_text}
        elif current_find and not current_replace:
            payload = {"action": "replace",
                       "find": current_find.strip(),
                       "replace": ""}

        # ``# Files:`` registers a file LIST: emit one directive per file so
        # every named file really receives the edit.
        if payload is not None:
            for target in current_files:
                directives.append({"file": target, **payload})

        # Reset
        current_files = []
        current_find = ""
        current_replace = ""
        current_add = ""
        current_after = ""
        current_before = ""
        change_buffer = ""
        code_lines = []
        in_code = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # --- Recognised directives (a directive always ends a code block) ---

        m = RE_FILE.match(stripped)
        if m:
            _flush()
            current_files = [m.group(1).strip()]
            continue

        m = RE_FILES.match(stripped)
        if m:
            _flush()
            current_files = [f.strip() for f in re.split(r"[,;]\s*", m.group(1))
                             if f.strip()]
            continue

        m = RE_FIND.match(stripped)
        if m and current_files:
            current_find = m.group(1).strip()
            continue

        m = RE_CHANGE.match(stripped)
        if m and current_files:
            change_buffer = m.group(1).strip()
            continue

        m = RE_TO.match(stripped)
        if m and current_files:
            current_replace = m.group(1).strip()
            continue

        m = RE_REPLACE.match(stripped)
        if m and current_files:
            current_replace = m.group(1).strip()
            continue

        m = RE_ADD.match(stripped)
        if m and current_files:
            current_add = m.group(1).strip()
            continue

        # "Add after <anchor>" / "Add below <anchor>"
        m = RE_ADD_AFTER.match(stripped)
        if m and current_files:
            current_after = m.group(1).strip()
            continue

        # "Add/Insert before <anchor>"
        m = RE_INSERT_BEFORE.match(stripped)
        if m and current_files:
            current_before = m.group(1).strip()
            continue

        m = RE_AFTER.match(stripped)
        if m and current_files:
            current_after = m.group(1).strip()
            continue

        m = RE_BEFORE.match(stripped)
        if m and current_files:
            current_before = m.group(1).strip()
            continue

        # --- Payload capture ---------------------------------------------

        # Explicit "# Code:" marker: the following lines are the payload.
        if RE_CODE_MARKER.match(stripped):
            if current_after or current_before or current_add:
                in_code = True
            continue

        # Advisory comment lines stay advisory even inside a code block.
        if RE_ADVISORY.match(stripped):
            manual_lines.append(line)
            continue

        if in_code:
            code_lines.append(line.rstrip("\n"))
            continue

        # An anchor written without "# Code:": the first raw line starts the
        # inserted block (the module's own rewrites use this form).
        if (current_after or current_before) and not stripped.startswith("#"):
            in_code = True
            code_lines.append(line.rstrip("\n"))
            continue

        # Accumulate non-directive lines (advisory / manual instructions)
        manual_lines.append(line)

    _flush()

    if not has_any_directive:
        stripped_lines = [l.strip() for l in lines if l.strip()]
        return [{"action": "manual",
                 "manual_instructions": "\n".join(stripped_lines)}]

    if not directives and manual_lines:
        return [{"action": "manual",
                 "manual_instructions": "\n".join(manual_lines).strip()}]

    return directives


# ═══════════════════════════════════════════════════════════════════════
# FixTemplateInterpreter
# ═══════════════════════════════════════════════════════════════════════

def _call_llm_subagent(template: str, context: dict | None = None) -> str | None:
    """Invoke the LLM subagent to interpret *template* into structured JSON.

    This is a placeholder for the actual LLM invocation.  The production
    integration should call the team's LLM subagent (or a dedicated model)
    through the DSH harness, parse the response as JSON, and return the
    raw response text.

    For testing/development, this function logs the attempt and returns None
    so callers can degrade gracefully.
    """
    # Placeholder: log the interpretation request.
    logger.info(
        "LLM subagent requested for template (len=%d chars, context=%s)",
        len(template),
        json.dumps(context) if context else "none",
    )
    # In production, replace with:
    #   response = some_llm_client.complete(prompt_build(template, context))
    #   return response.text
    return None


def _build_interpret_prompt(template: str) -> str:
    """Build the prompt for LLM-assisted template interpretation."""
    return (
        "You are FixTemplateInterpreter, an AI that converts natural-language\n"
        "fix templates into structured JSON directives.\n\n"
        "Supported actions:\n"
        '  - {"action": "replace", "file": "...", "find": "...", "replace": "..."}\n'
        '  - {"action": "insert_after", "file": "...", "find": "...", "add": "..."}\n'
        '  - {"action": "insert_before", "file": "...", "find": "...", "add": "..."}\n'
        '  - {"action": "append", "file": "...", "add": "..."}\n'
        '  - {"action": "change", "file": "...", "change": "...", "to": "..."}\n\n'
        "Rules:\n"
        "1. Output ONLY a JSON array of directive objects.\n"
        "2. When the template is purely advisory with no concrete edit, emit\n"
        '   [{"action": "manual", "manual_instructions": "<full original>"}].\n'
        "3. Be concise: avoid adding commentary outside the JSON.\n\n"
        "Template to interpret:\n```\n" + template + "\n```\n\n"
        "JSON output:"
    )


class FixTemplateInterpreter:
    """Interprets natural-language fix templates into structured directives.

    Two-tier strategy:
    1. **Heuristic pass** — ``parse_extended_directives()`` resolves all
       directives that match the known ``# File:``, ``# Change:`` / ``# To:``,
       ``# Add after``, ``# Files:`` patterns.
    2. **LLM fallback** — if the heuristic result contains ``action="manual"``
       items, the whole template is sent to the LLM subagent for a more
       sophisticated interpretation. The LLM result (if received) replaces
       the heuristic output.
    """

    def __init__(self, workspace_root: Path | None = None):
        self.workspace_root = Path(workspace_root).resolve() if workspace_root else (
            Path(__file__).resolve().parent.parent.parent
        )

    # ── Public API ──────────────────────────────────────────────────

    def interpret(
        self,
        template: str,
        *,
        allow_llm: bool = True,
        context: dict | None = None,
    ) -> InterpretationResult:
        """Interpret *template* into structured directives.

        Parameters
        ----------
        template : str
            The raw ``fix_template`` string.
        allow_llm : bool
            When True (default), the LLM subagent is invoked if the heuristic
            pass yields only a ``manual``-action directive.
        context : dict, optional
            Optional extra context (e.g. ``{"pattern_id": "circle_loop"}``)
            passed to the LLM subagent.

        Returns
        -------
        InterpretationResult
        """
        lines = template.strip().splitlines()
        heuristic = parse_extended_directives(lines)

        is_manual = (
            len(heuristic) == 1 and heuristic[0].get("action") == "manual"
        )

        if not is_manual:
            # Heuristic succeeded – no LLM needed
            return InterpretationResult(
                directives=heuristic,
                manual_instructions="",
                confidence=1.0,
                used_llm=False,
            )

        if not allow_llm:
            # Return the heuristic manual result as-is
            manual_text = heuristic[0].get("manual_instructions", template.strip())
            return InterpretationResult(
                directives=heuristic,
                manual_instructions=manual_text,
                confidence=0.0,
                used_llm=False,
            )

        # ── LLM fallback ──
        llm_response = _call_llm_subagent(template, context)
        if llm_response is None:
            logger.warning("LLM subagent did not return a result; falling back to manual.")
            return InterpretationResult(
                directives=heuristic,
                manual_instructions=heuristic[0].get("manual_instructions", template.strip()),
                confidence=0.0,
                used_llm=False,
            )

        # Attempt to parse the LLM response as JSON
        try:
            llm_directives = json.loads(llm_response)
            if isinstance(llm_directives, list):
                return InterpretationResult(
                    directives=llm_directives,
                    manual_instructions=template.strip(),
                    confidence=0.7,
                    used_llm=True,
                )
            logger.warning("LLM response not a JSON array, got: %s", type(llm_directives))
        except json.JSONDecodeError as e:
            logger.warning("LLM response is not valid JSON: %s", e)

        # Fallback: heuristic manual
        return InterpretationResult(
            directives=heuristic,
            manual_instructions=heuristic[0].get("manual_instructions", template.strip()),
            confidence=0.0,
            used_llm=False,
        )

    # ── Pattern rewriting ────────────────────────────────────────────

    def rewrite(self, pattern: dict) -> str:
        """Rewrite a pattern's ``fix_template`` into fully-structured form.

        *pattern* should be a dict with keys ``id``, ``name``, ``fix_template``,
        ``fix_files``, ``diagnosis``.

        Returns a newline-separated template string where every directive is
        explicit (``# File:`` / ``# Change:`` / ``# To:`` / etc.).
        """
        pid = pattern.get("id", "unknown")
        original = pattern.get("fix_template", "")
        fix_files = pattern.get("fix_files", [])

        structured = self._build_structured_for(pid, original, fix_files)
        return structured

    # ── Rewriting templates ──────────────────────────────────────────

    @staticmethod
    def _build_structured_for(
        pattern_id: str,
        original: str,
        fix_files: list[str],
    ) -> str:
        """Return a fully-structured template for the given pattern."""
        registry = _STRUCTURED_REWRITES
        if pattern_id in registry:
            return registry[pattern_id]

        # Fallback: if no rewrite is registered, try to interpret heuristically
        # and produce directives that we can format back into structured lines.
        return original  # unchanged

    def interpret_and_execute(
        self,
        template: str,
        executor: Any,  # FixExecutor instance
        fix_id: str,
        pattern_id: str,
    ) -> Any:  # FixExecutionReport
        """Convenience: interpret then execute via an existing FixExecutor."""
        from skills.fix_executor import FixExecutor, FixExecutionReport  # noqa

        result = self.interpret(template)

        if (
            len(result.directives) == 1
            and result.directives[0].get("action") == "manual"
        ):
            # Even after LLM fallback it is still manual
            report = FixExecutionReport(
                fix_id=fix_id,
                pattern_id=pattern_id,
                started_at=__import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                ).isoformat(),
            )
            report.manual_action_needed = True
            report.manual_instructions = result.manual_instructions or template.strip()
            report.completed_at = report.started_at
            return report

        # Build a synthetic template from directives, using exactly the
        # directive names/keys that FixExecutor.execute consumes.
        lines: list[str] = []
        for d in result.directives:
            f = d.get("file", "")
            if f:
                lines.append(f"# File: {f}")
            act = d.get("action")
            if act == "replace":
                lines.append(f"# Find: {d.get('find', '')}")
                lines.append(f"# Replace: {d.get('replace', '')}")
            elif act == "change":
                lines.append(f"# Change: {d.get('change', '')}")
                lines.append(f"# To: {d.get('to', '')}")
            elif act in ("insert_after",):
                lines.append(f"# After: {d.get('find', '')}")
                lines.append(f"# Add: {d.get('add', '')}")
            elif act in ("insert_before",):
                lines.append(f"# Before: {d.get('find', '')}")
                lines.append(f"# Add: {d.get('add', '')}")
            elif act == "append":
                lines.append(f"# Add: {d.get('add', '')}")
        synthetic = "\n".join(lines)

        # Every directive carries its own ``file`` (``# Files:`` is expanded
        # per file at parse time), so there is no fallback file list to pass.
        return executor.execute(
            fix_id=fix_id,
            pattern_id=pattern_id,
            fix_template=synthetic,
            fix_files=None,
        )


# ═══════════════════════════════════════════════════════════════════════
# Pre-built structured rewrites for the 8 degradation patterns
# ═══════════════════════════════════════════════════════════════════════

_STRUCTURED_REWRITES: dict[str, str] = {
    # ── 1. circle_loop ────────────────────────────────────────────────
    "circle_loop": (
        "# Fix: Add ground_angle gate before cliff avoidance\n"
        "# File: fly64/fly64/main.py\n"
        "# Change: if wall_score < 0.1 and asymmetry_magnitude < 0.06:  # cliff avoidance triggers\n"
        "# To: if wall_score < 0.1 and asymmetry_magnitude < 0.06 and ground_angle < 0.3:  # gate: only if ground is angled\n"
    ),
    # ── 2. ramp_trap ──────────────────────────────────────────────────
    "ramp_trap": (
        "# Fix: Add ramp escape override when stuck >180s on slope\n"
        "# File: fly64/fly64/main.py\n"
        "# Add after slope detection:\n"
        "# Code:\n"
        "if ramp_score > 0.5 and stuck_duration > 180:\n"
        "    control.x = rng.integers(60, 80) * (-1 if rng.random() < 0.5 else 1)\n"
        "    control.y = 40\n"
    ),
    # ── 3. reflex_cooldown_gap ────────────────────────────────────────
    "reflex_cooldown_gap": (
        "# Fix: Make reflex cooldown adaptive based on stuck_duration\n"
        "# File: fly64/fly64/memory.py\n"
        "# Change: cooldown_duration = 10.0\n"
        "# To: cooldown = max(2.0, self.base_cooldown_duration - stuck_duration * 0.05)\n"
        "# Note: stuck_duration is passed in from anomaly_state context\n"
    ),
    # ── 4. low_coverage_stagnation ──────────────────────────────────
    "low_coverage_stagnation": (
        "# Fix: Trigger forced_bold_explore immediately when coverage stagnant\n"
        "# File: fly64/fly64/main.py\n"
        "# Add before normal escape logic:\n"
        "# Code:\n"
        "if coverage_stagnant_120s and visited_cells < 50:\n"
        "    forced_bold_explore = True\n"
    ),
    # ── 5. below_ground_stuck ────────────────────────────────────────
    "below_ground_stuck": (
        "# Fix: Lower fallen detection threshold from -100 to 50\n"
        "# File: fly64/fly64/memory.py\n"
        "# Change: fallen = pos_y < -100\n"
        "# To: fallen = pos_y < 50\n"
        "# Note: SM64 ground level is Y=120; any Y<50 means Mario is below ground surface.\n"
    ),
    # ── 6. fallen_recovery_stuck ──────────────────────────────────────
    "fallen_recovery_stuck": (
        "# Fix: Fallen recovery — audit jump drive + alternation paths\n"
        "# Files: fly64/fly64/main.py, fly64/fly64/memory.py, fly64/fly64/model.py\n"
        "# File: fly64/fly64/main.py\n"
        "# Check: model.escape_jump_drive is set True while memory_ctrl.fallen\n"
        "# Check: model.step injects jump-pool current when flag is on\n"
        "# File: fly64/fly64/memory.py\n"
        "# Check: ReflexController.bold_direction(): _last_direction flips each cycle\n"
        "# File: fly64/fly64/model.py\n"
        "# Check: TurnAdaptation.counter_drive / breakout currents reach turn pools\n"
        "#          during fallen escape (no zero-current gate)\n"
        "# Adjust: If any check fails, repair the corresponding path\n"
    ),
    # ── 7. suspended_animation ────────────────────────────────────────
    "suspended_animation": (
        "# Investigate: All control signals zero while game state=1 neural control active\n"
        "# File: fly64/fly64/main.py\n"
        "# Check: bridge connectivity, model.visual_connected flag, encode_retina() output\n"
        "# Check: timeout recovery in main.py for visual disconnection\n"
        "# Adjust: If bridge disconnected, add reconnection logic\n"
        "# Adjust: If visual_connected is False, add reset path\n"
    ),
    # ── 8. wall_corner_command_decoupled ───────────────────────────────
    "wall_corner_command_decoupled": (
        "# Fix: corollary discharge comparator (action-effect mismatch)\n"
        "# File: fly64/fly64/main.py\n"
        "# Add after control computation:\n"
        "# Code:\n"
        "# expected = control.y * 0.6; actual = pose displacement\n"
        "# mismatch if expected > 25 and moved < 3 for > 15 frames\n"
        "# Reflex: reverse y=-50 + alternating turn to un-wedge\n"
        "expected = control.y * 0.6\n"
        "actual = abs(pose[0] - prev_pose[0]) + abs(pose[2] - prev_pose[2])\n"
        "if expected > 25 and actual < 3:\n"
        "    mismatch_frames += 1\n"
        "else:\n"
        "    mismatch_frames = 0\n"
        "if mismatch_frames > 15:\n"
        "    control.y = -50\n"
        "    control.x = -control.x  # alternate turn direction\n"
        "prev_pose = pose[:]\n"
    ),
}


# ═══════════════════════════════════════════════════════════════════════
# Convenience
# ═══════════════════════════════════════════════════════════════════════

def interpret_fix_template(
    template: str,
    workspace_root: Path | None = None,
    allow_llm: bool = True,
) -> InterpretationResult:
    """Standalone convenience: create a FixTemplateInterpreter and interpret."""
    interpreter = FixTemplateInterpreter(workspace_root=workspace_root)
    return interpreter.interpret(template, allow_llm=allow_llm)