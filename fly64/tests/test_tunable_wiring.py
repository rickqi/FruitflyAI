"""CONTRACT GUARD: a registry pid is only "wired" when the panel write path
actually reaches the reader that consumes it.

History
-------
The 2026-09 audit found that ``skills/brain_tunable_params.json`` advertised 21
parameters, 14 of which had ZERO occurrences anywhere in fly64/ or plugin/
source — aspirational names authored ahead of the implementation.  That audit's
follow-up (commit ea509a9) wired them up and flipped every one of them to
``wired: true``, but

  * it moved the ``breakout_forward_bias`` reader to ``_esc`` while the registry
    pid stayed ``exploration.breakout_forward_bias`` — so the panel POST landed
    in the exploration section and the consumer read the escape one, i.e. the
    "fix" itself created a dead parameter (A3 §4.2a, §4.5);
  * ``reflex.cooldown_min`` was declared wired with no consumer anywhere
    (A3 §4.2b);
  * the hardcoded expectations in this file (7 wired / 14 unwired) were never
    updated, which is why 8 of its assertions failed.

The registry now holds 39 pids and all of them declare ``wired: true``, so this
file no longer hardcodes counts or lists.  It re-derives every fact from
``brain_tunable_params.json``, ``fly64/main.py`` and the mutator:

P1-5 aligned the two ranges that were lying.  ``exploration.bold_explore_stuck_s``
was registered [15, 180] while the brain clamps it to [1, 10] — an EMPTY
intersection, so *every* legal sample (including the old default 60) was
silently rewritten; and ``exploration.turn_bias`` was registered [0, 0.4] while
the R31-fix12 clamp keeps [0, 0.25], so anything above a quarter was eaten.  The
runtime clamps are the behaviour-protecting side and the coach prompt already
advertises them, so the REGISTRY was aligned to the clamps (with the real usable
range spelled out in each description) and ``KNOWN_RANGE_MISMATCH`` is now empty.

  1. every pid declares a wiring flag;
  2. every wired pid has an AST read site in the brain;
  3. every pid's write path (panel POST -> ``apply_strategy_update`` -> the
     EVO-072 normalisation) lands the value in the pid's OWN registered
     section, and the reader for that leaf reads THAT section — the check that
     catches the ea509a9 regression;
  4. every registry ``[min, max]`` intersects the runtime clamp applied by
     ``fly64/main.py`` — with NO whitelist — and the clamp is read from BOTH
     shapes main.py uses (the dedicated ``CLAMP_BOUNDS`` table applied by
     ``apply_strategy_clamps`` and the inline ``max``/``min`` wrappers).
     P1-1 moved the two clamps this contract exists for into that table, so an
     inline-only walk stopped seeing them and the intersection check passed
     vacuously for exactly those pids;
  5. no registry range is WIDER than its runtime clamp: a legal registry sample
     the brain silently rewrites is the P1-5 defect (registry
     ``exploration.bold_explore_stuck_s`` [15, 180] vs clamp [1, 10] was an
     EMPTY intersection, and ``exploration.turn_bias`` max 0.4 vs clamp 0.25
     silently ate every sample above a quarter);
  6. the coach prompt's accepted windows (``plugin/llm_consult``
     ``COACH_NUMERIC_WINDOWS``) equal the registry range for every shared
     dotted id — P1-2 requirement "同步到教练 prompt" is pinned, not assumed;
  7. the mutator's search space is exactly the registry's wired set.
"""
import ast
import json
import re
import sys
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent      # fly64/
SCHEMA = REPO_ROOT / "skills" / "brain_tunable_params.json"
MAIN = REPO_ROOT / "fly64" / "main.py"
PANEL = REPO_ROOT / "web" / "evo-params.html"
CONSUMERS = ["fly64/main.py", "fly64/memory.py", "fly64/model.py",
             "fly64/central_complex.py"]

sys.path.insert(0, str(REPO_ROOT))

#: A3 §4.4 / execution-plan P0-2+P1-2: registry range vs runtime clamp pairs
#: that do NOT intersect.  P1-5 aligned the registry to the runtime clamps, so
#: this set is EMPTY and must stay empty — the range contract is now checked
#: mechanically for every wired pid (`test_the_range_whitelist_is_empty` fails
#: if an entry is added back, and the intersection tests below fail on the
#: mismatch anyway).
KNOWN_RANGE_MISMATCH = set()


def _schema():
    return json.loads(SCHEMA.read_text(encoding="utf-8"))


def _params():
    return _schema()["params"]


@lru_cache(maxsize=None)
def _main_source():
    return MAIN.read_text(encoding="utf-8")


@lru_cache(maxsize=None)
def _main_tree():
    """One parse for the whole module: the AST helpers below mix node
    identities (read sites vs. a parents map), so they must share a tree."""
    return ast.parse(_main_source())


@lru_cache(maxsize=None)
def _parents():
    tree = _main_tree()
    out = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            out[child] = node
    return out


def _numeric(node):
    """Literal float for ``0.25`` / ``1`` / ``-0.2``, else None."""
    if (isinstance(node, ast.Constant) and isinstance(node.value, (int, float))
            and not isinstance(node.value, bool)):
        return float(node.value)
    if (isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub)
            and isinstance(node.operand, ast.Constant)
            and isinstance(node.operand.value, (int, float))):
        return -float(node.operand.value)
    return None


def _read_string_keys(rel):
    """String literals that are read through a mapping in one consumer file."""
    p = REPO_ROOT / rel
    if not p.exists():
        return set()
    tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    found = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        par = parents.get(node)
        if isinstance(par, ast.Call) and isinstance(par.func, ast.Attribute):
            if par.func.attr in ("get", "pop") and node in par.args:
                found.add(node.value)
        elif isinstance(par, ast.Subscript) and par.slice is node:
            if isinstance(par.ctx, ast.Load):
                found.add(node.value)
    return found


@lru_cache(maxsize=None)
def _read_nodes():
    """Every literal-keyed read in fly64/main.py.

    Returns ``(leaf, lineno, receiver_name, default, node)`` for
    ``<recv>.get("leaf", default)`` / ``<recv>.pop("leaf")`` calls and for
    ``<recv>["leaf"]`` loads (main.py clamps some knobs by re-assigning the
    section entry in place).
    """
    out = []
    for node in ast.walk(_main_tree()):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr in ("get", "pop") and node.args):
            key = node.args[0]
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                recv = node.func.value
                out.append((key.value, node.lineno,
                            recv.id if isinstance(recv, ast.Name) else None,
                            _numeric(node.args[1]) if len(node.args) > 1 else None,
                            node))
        elif isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Load):
            key = node.slice
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                recv = node.value
                out.append((key.value, node.lineno,
                            recv.id if isinstance(recv, ast.Name) else None,
                            None, node))
    return tuple(out)


@lru_cache(maxsize=None)
def _var_sections():
    """``_expl`` -> ``"exploration"`` etc., read out of main.py's own assignments."""
    sections = {}
    for node in ast.walk(_main_tree()):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            for sub in ast.walk(node.value):
                if (isinstance(sub, ast.Call)
                        and isinstance(sub.func, ast.Attribute)
                        and sub.func.attr in ("get", "pop") and sub.args):
                    key = sub.args[0]
                    if isinstance(key, ast.Constant) and isinstance(key.value, str):
                        sections.setdefault(target.id, key.value)
    return sections


@lru_cache(maxsize=None)
def _clamp_bounds(leaf):
    """Tightest ``max(...)``/``min(...)`` literals wrapped around any read of
    *leaf* in main.py, as ``(lo, hi)`` (None = unbounded)."""
    parents = _parents()
    lo = hi = None
    for key, _lineno, _recv, _default, node in _read_nodes():
        if key != leaf:
            continue
        cur = node
        while True:
            par = parents.get(cur)
            if (isinstance(par, ast.Call) and isinstance(par.func, ast.Name)
                    and par.func.id in ("float", "int", "abs")):
                cur = par
                continue
            if (isinstance(par, ast.Call) and isinstance(par.func, ast.Name)
                    and par.func.id in ("max", "min")):
                for arg in par.args:
                    value = _numeric(arg)
                    if value is None:
                        continue
                    if par.func.id == "max":
                        lo = value if lo is None else max(lo, value)
                    else:
                        hi = value if hi is None else min(hi, value)
                cur = par
                continue
            break
    return lo, hi


@lru_cache(maxsize=None)
def _dedicated_clamp_table():
    """``{dotted_key: (lo, hi)}`` from main.py's ``CLAMP_BOUNDS`` literal.

    P1-1 (t1) moved the inline ``max(0.0, min(0.25, x))`` assignments into a
    module-level table applied by ``apply_strategy_clamps``; the AST walk in
    :func:`_clamp_bounds` therefore cannot see them any more.  Without this
    source the range check below would fall back to the registry range for
    exactly the two pids the contract exists for — i.e. pass vacuously while
    ``bold_explore_stuck_s`` had an EMPTY intersection with its clamp.
    """
    table = {}
    for node in ast.walk(_main_tree()):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Dict):
            continue
        if not any(isinstance(t, ast.Name) and t.id == "CLAMP_BOUNDS"
                   for t in node.targets):
            continue
        for key_node, bounds in zip(node.value.keys, node.value.values):
            if not (isinstance(key_node, ast.Constant)
                    and isinstance(key_node.value, str)):
                continue
            if not isinstance(bounds, ast.Tuple) or len(bounds.elts) != 2:
                continue
            lo, hi = _numeric(bounds.elts[0]), _numeric(bounds.elts[1])
            if lo is None or hi is None:
                continue
            table[key_node.value] = (lo, hi)
    return table


def _runtime_clamp(pid):
    """Tightest runtime ``(lo, hi)`` main.py applies to a registry pid.

    Two sources, because main.py clamps in two shapes: the dedicated
    ``CLAMP_BOUNDS`` table and inline ``max``/``min`` wrappers around a reader.
    ``None`` on either side means "unbounded from this source".
    """
    leaf = pid.split(".", 1)[1]
    lo, hi = _clamp_bounds(leaf)
    dedicated = _dedicated_clamp_table().get(pid)
    if dedicated is not None:
        lo = dedicated[0] if lo is None else max(lo, dedicated[0])
        hi = dedicated[1] if hi is None else min(hi, dedicated[1])
    return lo, hi


def _reader_sections(leaf, aliases=()):
    """Registered sections the readers of *leaf* (or its aliases) read from."""
    known = _var_sections()
    wanted = {leaf, *aliases}
    return {known.get(recv)
            for key, _lineno, recv, _default, _node in _read_nodes()
            if key in wanted}


@lru_cache(maxsize=None)
def _statements_mentioning(*needles):
    """Assignments in main.py whose reconstructed source mentions any of
    *needles*, in file order.  Used to execute the production reader statements
    verbatim, so a write-then-readback assertion cannot stay green while the
    real reader is dead (the ea509a9 failure mode a hand-written mirror would
    miss)."""
    hits = []
    for node in ast.walk(_main_tree()):
        if not isinstance(node, (ast.Assign, ast.AugAssign)):
            continue
        text = ast.unparse(node)
        if any(needle in text for needle in needles):
            hits.append((node.lineno, text))
    return tuple(text for _lineno, text in sorted(hits))


def _run_wiring(statements, namespace):
    for statement in statements:
        exec(statement, namespace)
    return namespace


@pytest.fixture(scope="module")
def consumed():
    keys = set()
    for rel in CONSUMERS:
        keys |= _read_string_keys(rel)
    return keys


class TestSchemaMarksWiring:
    def test_every_param_declares_wiring(self):
        missing = [pid for pid, m in _params().items()
                   if not isinstance(m, dict) or "wired" not in m]
        assert not missing, (
            "param(s) without an explicit wired flag: %s — the BrainMutator "
            "and the panel both read it" % missing)

    def test_schema_documents_the_meaning(self):
        note = _schema().get("wired_note", "")
        assert "wired" in note and "active_strategy" in note

    def test_wired_set_is_the_whole_registry(self):
        """All 39 pids are wired as of ea509a9; an unwired one must be
        re-added to this file's history before it can be searched again."""
        unwired = [pid for pid, m in _params().items() if not m.get("wired")]
        assert not unwired, (
            "these registry pids are no longer wired — update the contract "
            "and the known-unwired documentation: %s" % unwired)


class TestWiredFlagMatchesReality:
    def test_every_wired_param_has_a_consumer(self, consumed):
        bad = []
        for pid, meta in _params().items():
            if not meta.get("wired"):
                continue
            leaf = pid.split(".")[-1]
            aliases = meta.get("aliases") or []
            if leaf in consumed or any(a in consumed for a in aliases):
                continue
            bad.append(pid)
        assert not bad, (
            "param(s) marked wired=true have no reader in the brain: %s — "
            "either the flag is wrong or the consumer was lost" % bad)

    def test_every_wired_param_has_a_read_site_in_main(self):
        """The four consumer files above are grepped by literal; this pins the
        same fact to main.py's read sites specifically, so a knob whose only
        occurrence is a keyword argument cannot pass."""
        bad = [pid for pid in _params()
               if not _reader_sections(pid.split(".", 1)[1],
                                       _params()[pid].get("aliases") or [])]
        assert not bad, "no main.py read site reaches: %s" % bad


class TestPanelWritePathReachesTheReader:
    """The durable form of the A3 route probe (.tmp/_a3_param_route_probe.py)."""

    def test_every_pid_lands_in_its_registered_section(self):
        from fly64.main import apply_strategy_update

        pids = list(_params())
        probe = {pid: 0.123456789 for pid in pids}
        cur: dict = {}
        applied, rejected = apply_strategy_update(cur, probe)
        assert rejected == [], "the panel write path rejected: %s" % rejected
        assert set(applied) == set(pids)

        # EVO-072 normalisation, mirroring fly64/main.py:1280-1290.  The panel
        # path is already dot-expanded, so this is a no-op for it; the dotted
        # producers are EVO's writers (plan P1-1).
        for section in ("exploration", "escape", "reflex"):
            body = cur.get(section)
            if not isinstance(body, dict):
                continue
            prefix = section + "."
            for key in list(body.keys()):
                if key.startswith(prefix):
                    clean = key[len(prefix):]
                    if clean not in body:
                        body[clean] = body[key]
                    del body[key]

        lost = [pid for pid in pids
                if (cur.get(pid.split(".", 1)[0]) or {})
                .get(pid.split(".", 1)[1]) != probe[pid]]
        assert not lost, (
            "the panel value never reached the pid's own registered section "
            "(reader falls back to its default): %s" % lost)

    def test_every_pid_reader_reads_its_own_section(self):
        """The ea509a9 failure mode: write ``exploration.*``, read ``_esc``."""
        bad = []
        for pid, meta in _params().items():
            section, leaf = pid.split(".", 1)
            sections = _reader_sections(leaf, meta.get("aliases") or [])
            if section not in sections:
                bad.append((pid, sorted(str(s) for s in sections)))
        assert not bad, (
            "pid(s) whose reader reads a DIFFERENT section than the pid is "
            "registered in (a dead parameter): %s" % bad)

    def test_breakout_forward_bias_is_read_from_exploration(self):
        """Regression pin for ea509a9 (A3 §4.2a): this reader must never be
        switched back to the escape section."""
        assert _reader_sections("breakout_forward_bias") == {"exploration"}, (
            "exploration.breakout_forward_bias is registered under "
            "exploration.*, so the panel/EVO value lands in _expl; reading "
            "_esc makes the knob dead")

    def test_cooldown_min_reaches_the_reflex_cooldown(self):
        """Regression pin for reflex.cooldown_min (A3 §4.2b): it had zero
        consumers while being advertised as wired."""
        assert _reader_sections("cooldown_min") == {"reflex"}
        assignments = [ast.unparse(node) for node in ast.walk(_main_tree())
                       if isinstance(node, ast.Assign)
                       and "cooldown_duration" in ast.unparse(node.targets[0])]
        assert assignments, "main.py never writes reflex.cooldown_duration"
        assert any("cooldown_min" in text for text in assignments), (
            "reflex.cooldown_min does not feed reflex.cooldown_duration — the "
            "pid would be inert again")
        assert _clamp_bounds("cooldown_min") == (0.5, 5.0), (
            "the reflex.cooldown_min clamp must match its registry range")


class TestWriteThenReadBackThroughTheRealStatement:
    """P0-2 acceptance for the two formerly-dead pids: writing a non-default
    value must produce a non-default value at the consumer.

    The reader statements are exec'd exactly as they are written in
    fly64/main.py, so this is not a re-implementation.
    """

    def test_breakout_forward_bias_write_reaches_the_model(self):
        statements = _statements_mentioning("breakout_forward_bias")
        assert statements, "the breakout_forward_bias reader disappeared"
        namespace = _run_wiring(statements, {
            "_expl": {"breakout_forward_bias": 0.20},
            "model": SimpleNamespace(),
        })
        assert namespace["model"]._max_escape_forward == pytest.approx(0.20), (
            "a value written to exploration.breakout_forward_bias did not "
            "reach model._max_escape_forward (reader default 0.50)")

    def test_cooldown_min_write_reaches_the_reflex_controller(self):
        statements = _statements_mentioning("stuck_ramp_cooldown", "cooldown_min")
        assert statements, "the reflex cooldown wiring disappeared"

        def wired(stuck_ramp_cooldown, cooldown_min):
            namespace = _run_wiring(statements, {
                "_expl": {"stuck_ramp_cooldown": stuck_ramp_cooldown},
                "_reflex_sec": {"cooldown_min": cooldown_min},
                "memory_ctrl": SimpleNamespace(reflex=SimpleNamespace()),
            })
            return namespace["memory_ctrl"].reflex.cooldown_duration

        assert wired(1.0, 2.0) == pytest.approx(2.0)   # registry default
        assert wired(1.0, 5.0) == pytest.approx(5.0)   # non-default write
        assert wired(9.0, 2.0) == pytest.approx(9.0)   # stuck_ramp stays live

    def test_the_affected_signals_reach_the_telemetry_payload(self):
        """The value chain a tuning change can be observed through."""
        src = _main_source()
        # reflex.cooldown_min -> reflex_cooldowns in the flow.json payload.
        assert "reflex_cooldowns" in src, "reflex cooldowns missing from flow.json"
        # model._max_escape_forward caps model._escape_forward_accum, which is
        # injected into the forward LIF pool (model.py:1679-1685) and surfaces
        # as forward_rate / primitive_disp in the same telemetry payload.
        assert "forward_rate" in src and "primitive_disp" in src


class TestReflexCooldownMinIsLive:
    """reflex.cooldown_min must change the reflex's post-fire cooldown.

    The floor is composed in fly64/main.py; the consumer that turns that
    duration into a real cooldown is ReflexController._start_reflex, which the
    behavioural half of this class exercises for real.
    """

    @staticmethod
    def _wired_duration(stuck_ramp_cooldown, cooldown_min):
        namespace = _run_wiring(
            _statements_mentioning("stuck_ramp_cooldown", "cooldown_min"),
            {"_expl": {"stuck_ramp_cooldown": stuck_ramp_cooldown},
             "_reflex_sec": {"cooldown_min": cooldown_min},
             "memory_ctrl": SimpleNamespace(reflex=SimpleNamespace())})
        return namespace["memory_ctrl"].reflex.cooldown_duration

    @staticmethod
    def _fire(duration):
        from fly64.memory import ReflexController
        rc = ReflexController(cooldown_duration=duration)
        rc._cooldowns[rc.STUCK_RAMP] = 0.0
        rc._start_reflex(rc.STUCK_RAMP, lambda a, b: 0)
        return rc.cooldowns[rc.STUCK_RAMP]

    def test_setting_cooldown_min_changes_the_reflex_cooldown(self):
        before = self._fire(self._wired_duration(1.0, 2.0))
        after = self._fire(self._wired_duration(1.0, 5.0))
        assert before == pytest.approx(2.0)
        assert after == pytest.approx(5.0)
        assert after != before, "the knob does not reach the reflex cooldown"

    def test_stuck_ramp_cooldown_stays_a_live_dimension(self):
        assert self._fire(self._wired_duration(9.0, 2.0)) == pytest.approx(9.0)

    def test_default_composition_leaves_todays_behaviour_unchanged(self):
        """Registry defaults: stuck_ramp_cooldown 5.0, cooldown_min 2.0."""
        assert self._wired_duration(5.0, 2.0) == pytest.approx(5.0)


class TestRegistryRangeIntersectsRuntimeClamp:
    """P1-5: a registered range must describe what the runtime will accept.

    The registry is what the operator panel, the coach prompt and Phase 6's
    Gaussian search all sample from; the clamps in main.py decide what actually
    reaches behaviour.  When the two disagree, every legal sample is silently
    rewritten — the live form of the defect (coach 0.8 / 20.0 -> 0.25 / 10).
    """

    def _pairs(self):
        """``{pid: (registry, clamp, intersection)}``.

        ``intersection`` is the TRUE intersection of the two spans.  The
        original form substituted the clamp bound for the registry bound
        whenever a clamp existed, i.e. it compared the clamp with itself and
        could never see the pair it was written for: [15, 180] vs [1, 10]
        intersects as [max(15,1), min(180,10)] = [15, 10] — empty.  That is why
        the mismatch had to be written into the whitelist by hand.
        """
        pairs = {}
        for pid, meta in _params().items():
            registry = (float(meta["min"]), float(meta["max"]))
            clamp = _runtime_clamp(pid)
            lo = registry[0] if clamp[0] is None else max(registry[0], clamp[0])
            hi = registry[1] if clamp[1] is None else min(registry[1], clamp[1])
            pairs[pid] = (registry, clamp, (lo, hi))
        return pairs

    def test_the_range_whitelist_is_empty(self):
        """P1-5 requirement 2: no known range mismatch may remain."""
        assert KNOWN_RANGE_MISMATCH == set(), (
            "an exception was added back to KNOWN_RANGE_MISMATCH: the range "
            "contract must hold for every wired pid (align the registry or the "
            "clamp instead): %s" % sorted(KNOWN_RANGE_MISMATCH))

    def test_the_dedicated_clamp_table_is_visible_to_this_file(self):
        """Guard the guard: the two clamps of the P1-5 defect must be read.

        If ``CLAMP_BOUNDS`` ever moves again, this fails instead of the range
        check quietly falling back to the registry range for those pids.
        """
        table = _dedicated_clamp_table()
        assert table, "main.py's CLAMP_BOUNDS table is no longer readable"
        for pid in ("exploration.turn_bias", "exploration.bold_explore_stuck_s"):
            assert pid in table, (
                "%s is clamped somewhere this file cannot see — the range "
                "check would pass vacuously for it" % pid)

    def test_every_registry_range_intersects_its_runtime_clamp(self):
        bad = []
        for pid, (registry, clamp, span) in self._pairs().items():
            if span[0] > span[1]:
                bad.append((pid, registry, clamp))
        assert not bad, (
            "registry range and runtime clamp do not intersect, so every "
            "legal EVO sample is silently rewritten: %s" % bad)

    def test_no_registry_range_is_wider_than_its_runtime_clamp(self):
        """The stronger P1-5 form: no legal registry sample may be rewritten.

        Intersecting is not enough — ``turn_bias`` [0, 0.4] vs clamp [0, 0.25]
        intersected and still ate every request above a quarter.  A range that
        reaches outside its clamp is the silently-rewritten-sample defect.
        """
        bad = []
        for pid, (registry, clamp, _span) in self._pairs().items():
            lo, hi = clamp
            outside = ((lo is not None and registry[0] < lo)
                       or (hi is not None and registry[1] > hi))
            if outside:
                bad.append((pid, registry, "runtime clamp %s" % (clamp,)))
        assert not bad, (
            "registry ranges reach past the runtime clamp, so values the panel "
            "and the coach are told are legal get silently rewritten (align "
            "the registry [min, max] with main.py's clamp, or state the "
            "narrowed range in the registry description): %s" % bad)

    def test_default_lies_in_the_intersection(self):
        bad = []
        for pid, (registry, clamp, span) in self._pairs().items():
            default = float(_params()[pid]["default"])
            if not span[0] <= default <= span[1]:
                bad.append((pid, default, span))
        assert not bad, (
            "registry default is outside registry∩runtime-clamp: %s" % bad)

    def test_registry_ranges_match_the_coach_prompt_windows(self):
        """P1-5 requirement 4: the prompt is synced with the registry.

        ``plugin/llm_consult.COACH_NUMERIC_WINDOWS`` is what the coach is told
        it may ask for; the registry is what the panel/EVO may sample.  They
        must be the same numbers, or one of the two audiences is being lied to.
        """
        from plugin.llm_consult import COACH_NUMERIC_WINDOWS

        shared = {pid: window for pid, window in COACH_NUMERIC_WINDOWS.items()
                  if pid in _params()}
        assert set(shared) >= {"exploration.turn_bias",
                               "exploration.bold_explore_stuck_s"}, (
            "the coach prompt no longer advertises the two exploration "
            "windows this alignment is about: %s" % sorted(shared))
        bad = []
        for pid, window in shared.items():
            meta = _params()[pid]
            registry = (float(meta["min"]), float(meta["max"]))
            if (float(window[0]), float(window[1])) != registry:
                bad.append((pid, registry, "coach window %s" % (tuple(window),)))
        assert not bad, (
            "the coach prompt's accepted windows drift from the registry: %s"
            % bad)

    def test_the_two_aligned_pids_are_pinned(self):
        """The exact P1-5 rows, spelled out so a loosening cannot hide in the
        generic checks (they are the ones the live probe caught)."""
        pinned = {
            "exploration.turn_bias": ((0.0, 0.25), (0.0, 0.25), 0.25),
            "exploration.bold_explore_stuck_s": ((1.0, 10.0), (1.0, 10.0), 10.0),
        }
        for pid, (registry, clamp, default) in pinned.items():
            meta = _params()[pid]
            assert (float(meta["min"]), float(meta["max"])) == registry, (
                "%s registry range is %s, expected %s"
                % (pid, (meta["min"], meta["max"]), registry))
            assert _runtime_clamp(pid) == clamp, (
                "%s runtime clamp is %s, expected %s"
                % (pid, _runtime_clamp(pid), clamp))
            assert float(meta["default"]) == default, (
                "%s default is %s, expected %s"
                % (pid, meta["default"], default))
            # requirement 4: the registry description must state the real band
            assert "可用范围" in meta.get("description", ""), (
                "%s description must state its real usable range (P1-5 "
                "requirement 4): %r" % (pid, meta.get("description")))


class TestMutatorSearchSpaceIsWiredOnly:
    def test_live_params_is_the_registry_wired_set(self):
        from skills.evolution_skill import BrainMutator
        live = set(BrainMutator().live_params)
        assert live == set(_params()), (
            "Phase 6 search space diverged from the registry: %s"
            % sorted(live ^ set(_params())))

    def test_generate_candidate_only_emits_registry_params(self):
        """A trial mutates a bounded SUBSET of the search space on purpose
        (a full-dim mutation makes the fitness delta unattributable), so the
        contract is subset-and-non-empty, not equality."""
        from skills.evolution_skill import BrainMutator
        cand = BrainMutator().generate_candidate()
        assert cand, "a trial must move at least one dimension"
        assert set(cand) <= set(_params()), (
            "candidate includes params that are not in the registry: %s"
            % sorted(set(cand) - set(_params())))
        assert len(cand) < len(_params()), (
            "a full-dimensional candidate cannot be attributed to the "
            "parameters that actually moved")

    def test_param_paths_only_covers_registry_params(self):
        from skills.evolution_skill import BrainMutator
        assert set(BrainMutator().param_paths) == set(_params())

    def test_inject_writes_every_param_into_its_registered_section(
            self, tmp_path, monkeypatch):
        from skills import evolution_skill as es
        m = es.BrainMutator()
        strategy = {}
        monkeypatch.setattr(m, "_load_active_strategy", lambda: strategy)
        monkeypatch.setattr(m, "_write_active_strategy", lambda cfg: None)
        m._inject({pid: 1.0 for pid in _params()})
        written = {f"{s}.{k}" for s, sec in strategy.items()
                   if isinstance(sec, dict) and s != "__generation"
                   for k in sec}
        assert written == set(_params()), (
            "the writer lost or invented pids: %s"
            % sorted(written ^ set(_params())))


class TestPanelMarksInertSliders:
    def _src(self):
        return PANEL.read_text(encoding="utf-8")

    def test_panel_reads_the_wired_flag(self):
        assert "meta.wired" in self._src(), (
            "the panel ignores the wired flag, so it would again offer inert "
            "sliders that report success")

    def test_panel_disables_inert_sliders(self):
        compact = re.sub(r"\s+", "", self._src())
        assert re.search(r"wired===false\)\{[A-Za-z_$][\w$]*\.disabled=true",
                         compact), (
            "inert params must be disabled, not silently draggable")

    def test_panel_surfaces_the_inert_count(self):
        assert "未接线" in self._src(), (
            "the panel must label inert params for the operator")
