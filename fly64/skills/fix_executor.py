#!/usr/bin/env python3
"""
Fly64 FixExecutor — auto-fix闭环的模板执行引擎。

Parses fix_template directives produced by PatternCatalog patterns and applies
them to source files.  Supports classic directives:

  # File: <relative path>
  # Files: <path1>, <path2>, <path3>         (multi-file registration)
  # Find: / # Search: <exact text or pattern>
  # Replace: <replacement text>
  # Change: <target text>                    (paired with # To:)
  # To: <replacement text>                   (paired with # Change:)
  # Add: <text to insert>
  # After: / # Add after: <anchor line>
  # Before: / # Add before: / # Insert before: <anchor line>

When no structured directives are detected the fix is recorded as a
manual-action advisory.

Extended capabilities:
  - ``# Change:`` / ``# To:`` pairs for inline text-replacement directives.
  - ``# Files:`` comma/semicolon-separated list for multi-file edits.
  - ``# Add after <anchor>`` / ``# Add below <anchor>`` as aliases for
    ``# After:``.
  - ``# Insert before <anchor>`` / ``# Add before <anchor>`` as aliases for
    ``# Before:``.

Integration with the EVO pipeline:
  FixExecutor(fix_catalog).execute_all(findings, dry_run=False)
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Result dataclass ──────────────────────────────────────────────────


@dataclass
class FixActionResult:
    """Outcome of a single file-edit attempt.

    * ``applied`` — True when the edit actually changed the file on disk
      (or would have, under dry_run).
    * ``dry_run`` — set when ``FixExecutor`` was created with ``dry_run=True``.
    * ``file`` — the absolute or resolved path touched.
    * ``anchor`` — the Find/After/Before text that was sought.
    * ``error`` — description when ``applied=False`` due to an error.
    * ``backup_path`` — path of the backup created before the edit (empty
      string when none, e.g. dry_run or no-match).
    """

    fix_id: str = ""
    applied: bool = False
    dry_run: bool = False
    file: str = ""
    anchor: str = ""
    error: str = ""
    backup_path: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FixExecutionReport:
    """Aggregate result of executing one fix (possibly across several files)."""

    fix_id: str
    pattern_id: str
    started_at: str
    completed_at: str = ""
    actions: list[FixActionResult] = field(default_factory=list)
    all_applied: bool = False
    manual_action_needed: bool = False
    manual_instructions: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ── Template parser ───────────────────────────────────────────────────


def parse_fix_template(template: str) -> list[dict]:
    """Parse a fix_template string into structured edit directives.

    Each returned dict has:
      ``file`` (str) — target file path (relative to workspace root).
      ``action`` (str) — one of ``replace``, ``change``, ``insert_after``,
         ``insert_before``, ``append``, ``manual``.
      ``find`` (str)  — text/anchor to locate when applicable.
      ``replace`` or ``add`` (str) — replacement or inserted text.

    Supports both the classic directive set (``# File:``, ``# Find:``,
    ``# Replace:``, ``# After:``, ``# Before:``, ``# Add:``) and the extended
    set (``# Change:`` / ``# To:`` pairs, ``# Files:`` multi-file,
    ``# Add after <anchor>`` variants).

    When the template contains no recognised directive the single return item
    has ``action="manual"`` and the raw template in ``manual_instructions``.
    """
    lines = template.strip().splitlines()
    directives: list[dict] = []

    # State accumulated while scanning lines
    current_file: str = ""
    current_find: str = ""
    current_replace: str = ""
    current_add: str = ""
    current_after: str = ""
    current_before: str = ""
    change_buffer: str = ""          # holds text from # Change:
    multi_file_registry: list[str] = []  # holds multiple filenames from # Files:
    manual_lines: list[str] = []
    has_any_directive = False

    def _flush():
        nonlocal current_file, current_find, current_replace
        nonlocal current_add, current_after, current_before
        nonlocal change_buffer, multi_file_registry, has_any_directive
        if not current_file:
            return  # no active file to flush — not a directive
        has_any_directive = True

        # Collect all filenames to apply this block to
        target_files = [current_file]
        if multi_file_registry:
            target_files = multi_file_registry
            multi_file_registry = []

        # Determine action
        if change_buffer and current_replace:
            for f in target_files:
                directives.append({
                    "file": f,
                    "action": "change",
                    "change": change_buffer.strip(),
                    "to": current_replace.strip(),
                })
        elif change_buffer and current_add:
            for f in target_files:
                directives.append({
                    "file": f,
                    "action": "change",
                    "change": change_buffer.strip(),
                    "to": current_add.strip(),
                })
        elif current_find and current_replace:
            for f in target_files:
                directives.append({
                    "file": f,
                    "action": "replace",
                    "find": current_find.strip(),
                    "replace": current_replace.strip(),
                })
        elif current_after and current_add:
            for f in target_files:
                directives.append({
                    "file": f,
                    "action": "insert_after",
                    "find": current_after.strip(),
                    "add": current_add.strip(),
                })
        elif current_before and current_add:
            for f in target_files:
                directives.append({
                    "file": f,
                    "action": "insert_before",
                    "find": current_before.strip(),
                    "add": current_add.strip(),
                })
        elif current_find and current_add:
            for f in target_files:
                directives.append({
                    "file": f,
                    "action": "insert_after",
                    "find": current_find.strip(),
                    "add": current_add.strip(),
                })
        elif current_add:
            for f in target_files:
                directives.append({
                    "file": f,
                    "action": "append",
                    "add": current_add.strip(),
                })
        elif current_find and current_replace == "":
            for f in target_files:
                directives.append({
                    "file": f,
                    "action": "replace",
                    "find": current_find.strip(),
                    "replace": "",
                })

        # Reset per-file / per-block state
        current_file = ""
        current_find = ""
        current_replace = ""
        current_add = ""
        current_after = ""
        current_before = ""
        change_buffer = ""

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # ── Recognised directives (classic + extended) ──

        # # File: <path>
        m = re.match(r"^#\s*File:\s*(.+)$", stripped, re.IGNORECASE)
        if m:
            _flush()
            current_file = m.group(1).strip()
            continue

        # # Files: <path1>, <path2>, <path3>
        m = re.match(r"^#\s*Files:\s*(.+)$", stripped, re.IGNORECASE)
        if m:
            _flush()
            parts = [p.strip() for p in re.split(r"[,;]\s*", m.group(1)) if p.strip()]
            if parts:
                current_file = parts[0]
                if len(parts) > 1:
                    multi_file_registry = parts[:]
            continue

        # # Find: / # Search:
        m = re.match(r"^#\s*(?:Find|Search):\s*(.+)$", stripped, re.IGNORECASE)
        if m and current_file:
            current_find = m.group(1).strip()
            continue

        # # Change: <target text>
        m = re.match(r"^#\s*Change:\s*(.+)$", stripped, re.IGNORECASE)
        if m and current_file:
            change_buffer = m.group(1).strip()
            continue

        # # To: <replacement text>
        m = re.match(r"^#\s*To:\s*(.+)$", stripped, re.IGNORECASE)
        if m and current_file:
            current_replace = m.group(1).strip()
            continue

        # # Replace:
        m = re.match(r"^#\s*Replace:\s*(.*)$", stripped, re.IGNORECASE)
        if m and current_file:
            current_replace = m.group(1).strip()
            continue

        # # Add:
        m = re.match(r"^#\s*Add:\s*(.*)$", stripped, re.IGNORECASE)
        if m and current_file:
            current_add = m.group(1).strip()
            continue

        # # Add after <anchor> / # Add below <anchor>
        m = re.match(r"^#\s*Add\s+(?:after|below)\s+(.+)$", stripped, re.IGNORECASE)
        if m and current_file:
            current_after = m.group(1).strip()
            continue

        # # Add/Insert before <anchor>
        m = re.match(r"^#\s*(?:Insert|Add)\s+before\s+(.+)$", stripped, re.IGNORECASE)
        if m and current_file:
            current_before = m.group(1).strip()
            continue

        # # After:
        m = re.match(r"^#\s*After:\s*(.+)$", stripped, re.IGNORECASE)
        if m and current_file:
            current_after = m.group(1).strip()
            continue

        # # Before:
        m = re.match(r"^#\s*Before:\s*(.+)$", stripped, re.IGNORECASE)
        if m and current_file:
            current_before = m.group(1).strip()
            continue

        # Accumulate non-directive lines as manual instructions
        manual_lines.append(line)

    # Flush the last accumulated block
    _flush()

    if not has_any_directive:
        # Try natural-language interpretation fallback
        nl_result = _interpret_natural_language(template, lines)
        if nl_result is not None:
            return nl_result
        return [{
            "action": "manual",
            "manual_instructions": template.strip(),
        }]

    if not directives and manual_lines:
        # Lines may hold natural-language directives mixed with partial structure
        nl_result = _interpret_natural_language(
            "\n".join(manual_lines).strip(), manual_lines
        )
        if nl_result is not None:
            return nl_result
        return [{
            "action": "manual",
            "manual_instructions": "\n".join(manual_lines).strip(),
        }]

    return directives


def _interpret_natural_language(
    template: str, lines: list[str]
) -> list[dict] | None:
    """Attempt to interpret natural-language-only fix templates as structured directives.

    Handles the common patterns found in ``default_patterns.json`` that lack
    ``# Find:`` / ``# Replace:`` directives but still contain actionable info:

    * ``# Strengthen <something> in <file>`` — adjust parameter.
    * ``# Verify <something> in <file>`` — verification advisory (remains manual).
    * ``# File: <path>`` without structured Find/Replace — advisory.
    * ``# Fix: <action>\n# File: <path>`` — partial structure.
    * ``# Files: <path1>, <path2>`` — multi-file advisory.

    Returns ``None`` to let the caller fall back to the ``manual`` action.
    """
    # If ANY line has a recognised directive prefix, treat this as structured
    # but incomplete — still return None so the caller can flag it as manual.
    directive_keywords = [
        "# find:", "# search:", "# replace:", "# change:", "# to:",
        "# add:", "# after:", "# before:", "# add after", "# add below",
        "# insert before", "# add before",
    ]
    any_directive = any(
        any(line.strip().lower().startswith(kw) for kw in directive_keywords)
        for line in lines
    )
    if any_directive:
        return None  # partial structure, keep as manual

    # Heuristic 1: "Verify <topic> in <file>" — advisory only
    has_verify = any(
        re.match(r"^#\s*Verify\s+", line.strip(), re.IGNORECASE)
        for line in lines
    )
    has_investigate = any(
        re.match(r"^#\s*(?:Fix|Investigate|Check|Audit):?\s+", line.strip(), re.IGNORECASE)
        for line in lines
    )

    # Try to extract a file path
    extracted_file = None
    for line in lines:
        m = re.match(
            r"^#\s*(?:File|Files|In)\s*:?\s*(.+)$", line.strip(), re.IGNORECASE
        )
        if m:
            parts = [p.strip() for p in re.split(r"[,;]\s*", m.group(1)) if p.strip()]
            if parts:
                extracted_file = parts[0]

    advisory = template.strip()
    if has_verify or has_investigate:
        return [{
            "action": "advisory",
            "advisory_type": "verify" if has_verify else "investigate",
            "file": extracted_file or "",
            "manual_instructions": advisory,
        }]

    return None  # pure natural language, let the caller use manual


# ── FixExecutor ───────────────────────────────────────────────────────


class FixExecutor:
    """Apply fix_template directives to source files.

    Supports both classic and extended directive forms.  The extended set adds:

    * ``# Change: <target>`` + ``# To: <replacement>``  — inline replace.
    * ``# Files: <csv list>``  — apply to multiple files in one block.
    * ``# Add after <anchor>`` / ``# Add below <anchor>``  — same as
      ``# After: <anchor>``.
    * ``# Insert before <anchor>`` / ``# Add before <anchor>``  — same as
      ``# Before: <anchor>``.

    Parameters
    ----------
    workspace_root : Path or str, optional
        Root directory for resolving relative file paths.  Defaults to the
        flygym project root (parent of the ``fly64/`` directory).
    dry_run : bool
        When True, log intended changes without modifying files.  The report
        still indicates what *would* be done.  Default False.
    backup : bool
        When True (default), create a ``.bak`` backup before each edit so
        individual actions can be rolled back.
    """

    def __init__(
        self,
        workspace_root: Optional[Path] = None,
        dry_run: bool = False,
        backup: bool = True,
    ):
        self.dry_run = dry_run
        self.backup = backup
        # Resolve workspace root: the workspace root is 3 levels up from this file
        # (skills/fix_executor.py -> fly64/skills/ -> fly64/ -> workspace)
        self.workspace_root = Path(workspace_root).resolve() if workspace_root else (
            Path(__file__).resolve().parent.parent.parent
        )
        # Track backups for rollback: backup_path -> original content
        self._backups: dict[str, str] = {}

    # ── Public API ──────────────────────────────────────────────────

    def execute(
        self,
        fix_id: str,
        pattern_id: str,
        fix_template: str,
        fix_files: Optional[list[str]] = None,
    ) -> FixExecutionReport:
        """Parse and execute a single fix template.

        Parameters
        ----------
        fix_id : str
            The FixEntry.id (e.g. ``"fix_0001"``).
        pattern_id : str
            The pattern id that produced this fix.
        fix_template : str
            Raw fix template string, e.g. from ``Finding.fix_template``.
        fix_files : list of str, optional
            Override file list (from Finding.fix_files).  Directives inside
            the template take precedence.

        Returns
        -------
        FixExecutionReport
        """
        report = FixExecutionReport(
            fix_id=fix_id,
            pattern_id=pattern_id,
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        directives = parse_fix_template(fix_template)

        # Special case: manual-action advisory
        # Special case: advisory (natural-language verify/investigate)
        if len(directives) == 1 and directives[0].get("action") == "advisory":
            report.manual_action_needed = True
            report.manual_instructions = directives[0].get("manual_instructions", fix_template)
            report.completed_at = datetime.now(timezone.utc).isoformat()
            return report

        # Special case: manual-action advisory
        if len(directives) == 1 and directives[0].get("action") == "manual":
            report.manual_action_needed = True
            report.manual_instructions = directives[0].get("manual_instructions", fix_template)
            report.completed_at = datetime.now(timezone.utc).isoformat()
            return report

        for directive in directives:
            action = directive.get("action", "")
            file_rel = directive.get("file", "")
            file_path = self._resolve_file(file_rel, fix_files)

            if not file_path:
                report.actions.append(FixActionResult(
                    fix_id=fix_id,
                    applied=False,
                    error=f"file not resolved (rel={file_rel}, fix_files={fix_files})",
                ))
                continue

            if action == "replace":
                result = self._do_replace(
                    fix_id, file_path,
                    directive.get("find", ""),
                    directive.get("replace", ""),
                )
            elif action == "change":
                result = self._do_change(
                    fix_id, file_path,
                    directive.get("change", ""),
                    directive.get("to", ""),
                )
            elif action == "insert_after":
                result = self._do_insert_after(
                    fix_id, file_path,
                    directive.get("find", ""),
                    directive.get("add", ""),
                )
            elif action == "insert_before":
                result = self._do_insert_before(
                    fix_id, file_path,
                    directive.get("find", ""),
                    directive.get("add", ""),
                )
            elif action == "append":
                result = self._do_append(
                    fix_id, file_path,
                    directive.get("add", ""),
                )
            else:
                result = FixActionResult(
                    fix_id=fix_id,
                    applied=False,
                    error=f"unknown action: {action}",
                )

            result.file = str(file_path)
            report.actions.append(result)

        report.all_applied = all(a.applied for a in report.actions)
        report.completed_at = datetime.now(timezone.utc).isoformat()
        return report

    def execute_all(
        self,
        findings: list,
        fix_catalog,
        *,
        dry_run: Optional[bool] = None,
    ) -> list[FixExecutionReport]:
        """Convenience: execute fix templates for every finding in a list.

        Each *finding* must have ``pattern_id``, ``fix_template``, ``fix_files``
        attributes (duck-typing compatible with ``Finding``).  The fix is first
        recorded in *fix_catalog* (a ``FixCatalog`` instance), then executed.
        """
        if dry_run is not None:
            self.dry_run = dry_run

        reports: list[FixExecutionReport] = []
        for finding in findings:
            entry = fix_catalog.record_fix(finding)
            report = self.execute(
                fix_id=entry.id,
                pattern_id=finding.pattern_id,
                fix_template=finding.fix_template,
                fix_files=finding.fix_files,
            )
            reports.append(report)
        return reports

    # ── Rollback ─────────────────────────────────────────────────────

    def rollback(self, report: FixExecutionReport) -> list[dict]:
        """Undo all previously-applied actions in a report.

        Returns a list of rollback outcomes (each with ``file``, ``success``,
        ``error``).  Only actions that created a backup can be rolled back.
        """
        outcomes: list[dict] = []
        for action in report.actions:
            file_path = action.file
            backup_path = action.backup_path
            if not file_path or not backup_path:
                outcomes.append({
                    "file": file_path,
                    "success": False,
                    "error": "no backup available",
                })
                continue
            try:
                with open(backup_path, "r", encoding="utf-8") as f:
                    original = f.read()
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(original)
                os.remove(backup_path)
                self._backups.pop(file_path, None)
                outcomes.append({"file": file_path, "success": True})
            except Exception as e:
                outcomes.append({"file": file_path, "success": False, "error": str(e)})
        return outcomes

    # ── Internal helpers ─────────────────────────────────────────────

    def _resolve_file(self, file_rel: str, fix_files: Optional[list[str]] = None) -> Optional[Path]:
        """Resolve a relative file path against the workspace root.

        Uses the directive's ``file_rel`` first; falls back to the first
        entry in ``fix_files``.
        """
        rel = file_rel or (fix_files[0] if fix_files else "")
        if not rel:
            return None
        candidate = self.workspace_root / rel
        if candidate.exists():
            return candidate
        # Try relative to workspace without the fly64/ prefix
        alt = self.workspace_root / rel.replace("fly64/", "", 1)
        if alt.exists():
            return alt
        # Just return the constructed path (the edit will fail with a clear error)
        return candidate

    def _read_file(self, path: Path) -> Optional[str]:
        try:
            return path.read_text(encoding="utf-8")
        except Exception as e:
            return None

    def _create_backup(self, path: Path, content: str) -> str:
        """Create a .bak backup file. Returns the backup path string."""
        if not self.backup or self.dry_run:
            return ""
        backup_path = path.with_suffix(path.suffix + ".bak")
        # Append a timestamp if a backup already exists
        if backup_path.exists():
            backup_path = path.with_suffix(
                f".bak.{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            )
        backup_path.write_text(content, encoding="utf-8")
        self._backups[str(path)] = str(backup_path)
        return str(backup_path)

    def _do_replace(
        self, fix_id: str, path: Path,
        find_text: str, replace_text: str,
    ) -> FixActionResult:
        """Replace *find_text* with *replace_text* in *path*."""
        if not path.exists():
            return FixActionResult(fix_id=fix_id, error=f"file not found: {path}",
                                   anchor=find_text)
        content = self._read_file(path)
        if content is None:
            return FixActionResult(fix_id=fix_id,
                                   error=f"could not read: {path}", anchor=find_text)

        if find_text not in content:
            return FixActionResult(fix_id=fix_id,
                                   error=f"find text not found in {path.name}",
                                   anchor=find_text)

        new_content = content.replace(find_text, replace_text, 1)
        if new_content == content:
            return FixActionResult(fix_id=fix_id,
                                   error="no change (replace produced identical content)",
                                   anchor=find_text)

        if self.dry_run:
            return FixActionResult(fix_id=fix_id, applied=True, dry_run=True,
                                   file=str(path), anchor=find_text)

        backup_path = self._create_backup(path, content)
        try:
            path.write_text(new_content, encoding="utf-8")
            return FixActionResult(fix_id=fix_id, applied=True,
                                   file=str(path), anchor=find_text,
                                   backup_path=backup_path)
        except Exception as e:
            return FixActionResult(fix_id=fix_id,
                                   error=f"write failed: {e}", anchor=find_text)

    def _do_change(
        self, fix_id: str, path: Path,
        change_text: str, to_text: str,
    ) -> FixActionResult:
        """Replace *change_text* with *to_text* in *path*.

        ``change`` is a synonym for ``replace`` and uses the same logic.
        """
        if not path.exists():
            return FixActionResult(fix_id=fix_id, error=f"file not found: {path}",
                                   anchor=change_text)
        content = self._read_file(path)
        if content is None:
            return FixActionResult(fix_id=fix_id,
                                   error=f"could not read: {path}", anchor=change_text)

        if change_text not in content:
            return FixActionResult(fix_id=fix_id,
                                   error=f"change text not found in {path.name}",
                                   anchor=change_text)

        new_content = content.replace(change_text, to_text, 1)
        if new_content == content:
            return FixActionResult(fix_id=fix_id,
                                   error="no change (change produced identical content)",
                                   anchor=change_text)

        if self.dry_run:
            return FixActionResult(fix_id=fix_id, applied=True, dry_run=True,
                                   file=str(path), anchor=change_text)

        backup_path = self._create_backup(path, content)
        try:
            path.write_text(new_content, encoding="utf-8")
            return FixActionResult(fix_id=fix_id, applied=True,
                                   file=str(path), anchor=change_text,
                                   backup_path=backup_path)
        except Exception as e:
            return FixActionResult(fix_id=fix_id,
                                   error=f"write failed: {e}", anchor=change_text)

    def _do_insert_after(
        self, fix_id: str, path: Path,
        anchor: str, add_text: str,
    ) -> FixActionResult:
        """Insert *add_text* on the line after the line containing *anchor*."""
        if not path.exists():
            return FixActionResult(fix_id=fix_id, error=f"file not found: {path}",
                                   anchor=anchor)
        content = self._read_file(path)
        if content is None:
            return FixActionResult(fix_id=fix_id,
                                   error=f"could not read: {path}", anchor=anchor)

        lines = content.splitlines(keepends=True)
        new_lines = list(lines)
        inserted = False
        for i, line in enumerate(lines):
            if anchor in line:
                indent = ""
                trail = "\n"
                m = re.match(r"^(\s*)", line)
                if m:
                    indent = m.group(1)
                if add_text.endswith("\n"):
                    trail = ""
                added_line = indent + add_text + trail
                # Insert after current line
                if i + 1 < len(new_lines):
                    new_lines.insert(i + 1, added_line)
                else:
                    new_lines.append(added_line)
                inserted = True
                break

        if not inserted:
            return FixActionResult(fix_id=fix_id,
                                   error=f"anchor not found in {path.name}",
                                   anchor=anchor)

        new_content = "".join(new_lines)
        if self.dry_run:
            return FixActionResult(fix_id=fix_id, applied=True, dry_run=True,
                                   file=str(path), anchor=anchor)

        backup_path = self._create_backup(path, content)
        try:
            path.write_text(new_content, encoding="utf-8")
            return FixActionResult(fix_id=fix_id, applied=True,
                                   file=str(path), anchor=anchor,
                                   backup_path=backup_path)
        except Exception as e:
            return FixActionResult(fix_id=fix_id,
                                   error=f"write failed: {e}", anchor=anchor)

    def _do_insert_before(
        self, fix_id: str, path: Path,
        anchor: str, add_text: str,
    ) -> FixActionResult:
        """Insert *add_text* on the line before the line containing *anchor*."""
        if not path.exists():
            return FixActionResult(fix_id=fix_id, error=f"file not found: {path}",
                                   anchor=anchor)
        content = self._read_file(path)
        if content is None:
            return FixActionResult(fix_id=fix_id,
                                   error=f"could not read: {path}", anchor=anchor)

        lines = content.splitlines(keepends=True)
        inserted = False
        for i, line in enumerate(lines):
            if anchor in line:
                indent = ""
                trail = "\n"
                m = re.match(r"^(\s*)", line)
                if m:
                    indent = m.group(1)
                if add_text.endswith("\n"):
                    trail = ""
                added_line = indent + add_text + trail
                new_lines = list(lines)
                new_lines.insert(i, added_line)
                new_content = "".join(new_lines)
                inserted = True
                break

        if not inserted:
            return FixActionResult(fix_id=fix_id,
                                   error=f"anchor not found in {path.name}",
                                   anchor=anchor)

        if self.dry_run:
            return FixActionResult(fix_id=fix_id, applied=True, dry_run=True,
                                   file=str(path), anchor=anchor)

        backup_path = self._create_backup(path, content)
        try:
            path.write_text(new_content, encoding="utf-8")
            return FixActionResult(fix_id=fix_id, applied=True,
                                   file=str(path), anchor=anchor,
                                   backup_path=backup_path)
        except Exception as e:
            return FixActionResult(fix_id=fix_id,
                                   error=f"write failed: {e}", anchor=anchor)

    def _do_append(
        self, fix_id: str, path: Path,
        add_text: str,
    ) -> FixActionResult:
        """Append *add_text* to the end of *path*."""
        if not path.exists():
            return FixActionResult(fix_id=fix_id, error=f"file not found: {path}",
                                   anchor="")
        content = self._read_file(path)
        if content is None:
            return FixActionResult(fix_id=fix_id,
                                   error=f"could not read: {path}", anchor="")

        trailing_nl = "" if content.endswith("\n") else "\n"
        new_content = content + trailing_nl + add_text + "\n"

        if self.dry_run:
            return FixActionResult(fix_id=fix_id, applied=True, dry_run=True,
                                   file=str(path), anchor="")

        backup_path = self._create_backup(path, content)
        try:
            path.write_text(new_content, encoding="utf-8")
            return FixActionResult(fix_id=fix_id, applied=True,
                                   file=str(path), anchor="",
                                   backup_path=backup_path)
        except Exception as e:
            return FixActionResult(fix_id=fix_id,
                                   error=f"write failed: {e}", anchor="")


# ── Convenience ───────────────────────────────────────────────────────


def auto_fix_findings(
    findings: list,
    fix_catalog,
    workspace_root: Optional[Path] = None,
    dry_run: bool = False,
) -> list[FixExecutionReport]:
    """Standalone convenience: create a FixExecutor and execute all findings."""
    executor = FixExecutor(workspace_root=workspace_root, dry_run=dry_run)
    return executor.execute_all(findings, fix_catalog)