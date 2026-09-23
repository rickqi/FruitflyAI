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

  1. every pid declares a wiring flag;
  2. every wired pid has an AST read site in the brain;
  3. every pid's write path (panel POST -> ``apply_strategy_update`` -> the
     EVO-072 normalisation) lands the value in the pid's OWN registered
     section, and the reader for that leaf reads THAT section — the check that
     catches the ea509a9 regression;
  4. every registry ``[min, max]`` intersects the runtime clamp applied by
     ``fly64/main.py`` and the default lies inside the intersection;
  5. the mutator's search space is exactly the registry's wired set.
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

# A3 §4.4 / execution-plan P0-2+P1-2: registry range vs runtime clamp pairs
# that do NOT intersect.  Asserted as a SUBSET so aligning the ranges (P1-2)
# keeps this file green, while a NEW mismatch fails immediately.
KNOWN_RANGE_MISMATCH = {
    # registry [15, 180] vs main.py clamp [1, 10] — no legal EVO sample can
    # survive, which is why the panel description recommends "5~10".
    "exploration.bold_explore_stuck_s",
}


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
    def _pairs(self):
        pairs = {}
        for pid, meta in _params().items():
            registry = (float(meta["min"]), float(meta["max"]))
            clamp = _clamp_bounds(pid.split(".", 1)[1])
            lo = registry[0] if clamp[0] is None else clamp[0]
            hi = registry[1] if clamp[1] is None else clamp[1]
            pairs[pid] = (registry, clamp, (lo, hi))
        return pairs

    def test_every_registry_range_intersects_its_runtime_clamp(self):
        bad = []
        for pid, (registry, clamp, span) in self._pairs().items():
            if span[0] > span[1] and pid not in KNOWN_RANGE_MISMATCH:
                bad.append((pid, registry, clamp))
        assert not bad, (
            "registry range and runtime clamp do not intersect, so every "
            "legal EVO sample is silently rewritten: %s" % bad)

    def test_default_lies_in_the_intersection(self):
        bad = []
        for pid, (registry, clamp, span) in self._pairs().items():
            if pid in KNOWN_RANGE_MISMATCH:
                continue
            default = float(_params()[pid]["default"])
            if not span[0] <= default <= span[1]:
                bad.append((pid, default, span))
        assert not bad, (
            "registry default is outside registry∩runtime-clamp: %s" % bad)


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
