"""PIN: the forward/jump gate unit contract (RULE-19, 8th case of the family).

DEFECT (measured)
-----------------
`Control.forward_rate / turn_rate / jump_rate` are **per-tick** firing
fractions of a 13-tick (≈ 250 ms) motor-pool window (``fly64/model.py:1912``
..``1916``): ``recent = history.mean()``, so ``0.0 ≤ rate ≤ 1.0``
(``1.0`` = every pool neuron fires every tick = ``1/dt`` Hz).

The dashboard telemetry reports the *same* physical quantity in **Hz**
(``telemetry.py:77-78``: window count ÷ ``ticks · dt``), and the tunable
schema declares the two gate thresholds in **Hz**.  The pre-repair readers in
``fly64/fly64/main.py`` compared the raw per-tick fraction against the Hz
threshold::

    "gate_jump": getattr(control, "jump_rate", 0.0) > float(
        _expl.get("gate_jump_threshold", 2.0))          # max 1.0 < 2.0

so ``gate_jump`` was **mathematically unreachable** — the observed ceiling is
``1.0``, and the measured live pool (``0.276/tick`` = 13.8 Hz) could not open
a gate declared at 2.0 Hz whatever EVO sampled from its declared range.
``gate_forward`` had the same defect and merely *looked* healthy because the
forward pool happened to be saturated (``0.923/tick`` = 46.15 Hz > 0.4).

WHAT THIS FILE PINS (not by relaxing any threshold)
---------------------------------------------------
1. Thresholds and observations share one unit (**Hz**) and the conversion is
   done exactly once, in ``main.py``, with the same ``1/dt`` the dashboard
   uses (``rate_per_tick_to_hz``) — no consumer infers a unit.
2. ``gate_jump`` is reachable in Hz: the measured live jump pool opens it, and
   the boundary is explicit (observed == threshold → closed; the per-tick
   value that used to be compared is still below the threshold).
3. ``gate_forward`` opens on a healthy forward pool (5 Hz) and closes on a
   silent one, without needing saturation, while still *not* being permanent.
4. The registry ranges are Hz-consistent and calibrated against the decoder's
   own references (``model.py``), with the maxima below the Nyquist rate
   ``1/dt`` so a declared threshold stays physically reachable.
5. The register (``docs/declared-not-implemented.md``) records these two pids
   as implemented with the unit convention, and no longer as zero-consumer.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent          # fly64/
sys.path.insert(0, str(REPO_ROOT))

from fly64.main import (GATE_RATE_DT_DEFAULT, gate_open_hz,  # noqa: E402
                        rate_per_tick_to_hz)
from fly64.model import FlyModel                             # noqa: E402
from fly64.telemetry import Observatory                      # noqa: E402

MAIN_PY = REPO_ROOT / "fly64" / "main.py"
MODEL_PY = REPO_ROOT / "fly64" / "model.py"
SCHEMA = REPO_ROOT / "skills" / "brain_tunable_params.json"
DOCS = REPO_ROOT / "docs" / "declared-not-implemented.md"

DT = GATE_RATE_DT_DEFAULT            # 0.02 s/tick → 50 Hz control loop
NYQUIST_HZ = 1.0 / DT                # 50 Hz — the pool-rate ceiling

# Captain-measured live pool rates (per ticket) from the saturated-forward run:
# forward 0.923/tick = 46.15 Hz (pinned at the ceiling — the bug this team
# repairs), jump 0.276/tick = 13.8 Hz.
MEASURED_FORWARD_PER_TICK = 0.923
MEASURED_JUMP_PER_TICK = 0.276

FORWARD_PID = "exploration.gate_forward_threshold"
JUMP_PID = "exploration.gate_jump_threshold"
GATE_PIDS = (FORWARD_PID, JUMP_PID)

RATE_ATTRS = ("forward_rate", "turn_rate", "jump_rate")


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _params() -> dict:
    return json.loads(SCHEMA.read_text(encoding="utf-8"))["params"]


def _main_tree() -> ast.Module:
    return ast.parse(MAIN_PY.read_text(encoding="utf-8"))


def _main_source() -> str:
    return MAIN_PY.read_text(encoding="utf-8")


def _read_defaults(leaf: str):
    """Literal defaults of every ``<recv>.get("<leaf>", <literal>)`` in main.py."""
    out = []
    for node in ast.walk(_main_tree()):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get" and len(node.args) > 1):
            key, value = node.args[0], node.args[1]
            if (isinstance(key, ast.Constant) and key.value == leaf
                    and isinstance(value, ast.Constant)
                    and isinstance(value.value, (int, float))
                    and not isinstance(value.value, bool)):
                out.append(float(value.value))
    return out


def _assignments() -> dict:
    out: dict = {}
    for node in ast.walk(_main_tree()):
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)):
            out.setdefault(node.targets[0].id, node.value)
    return out


def _flow_json_literals() -> dict:
    """``{key: value_node}`` of the ``DashboardHTTP.flow_json`` dict literal."""
    for node in ast.walk(_main_tree()):
        if not isinstance(node, ast.Assign):
            continue
        target = node.targets[0]
        if not (isinstance(target, ast.Attribute) and target.attr == "flow_json"):
            continue
        value = node.value
        # `json.dumps({...}, separators=...).encode()`
        while (isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute)
               and value.func.attr == "encode"):
            value = value.func.value
        if (isinstance(value, ast.Call) and value.args
                and isinstance(value.args[0], ast.Dict)):
            body = value.args[0]
            return {k.value: v for k, v in zip(body.keys, body.values)
                    if isinstance(k, ast.Constant) and isinstance(k.value, str)}
    raise AssertionError("main.py has no DashboardHTTP.flow_json dict literal")


def _unwrap(node: ast.AST) -> ast.AST:
    """Strip ``round(x, n)`` / ``float(x)`` wrappers."""
    while (isinstance(node, ast.Call) and len(node.args) == 1
           and isinstance(node.func, ast.Name)
           and node.func.id in ("round", "float")):
        node = node.args[0]
    return node


def _decoder_references_hz() -> dict:
    """The decoder's own rate references (Hz), read out of ``model.py``.

    Deriving them from the source (instead of hardcoding a table) means a
    decoder change fails this PIN loudly rather than silently invalidating the
    calibration the schema documents.
    """
    src = MODEL_PY.read_text(encoding="utf-8")
    fwd = re.search(
        r"raw_y\s*=\s*np\.clip\(\(forward_rate\s*-\s*([\d.]+)\)\s*\*\s*([\d.]+),\s*0,\s*([\d.]+)\)",
        src)
    assert fwd, ("model.py no longer decodes the forward pool as "
                 "(forward_rate - onset) * gain clipped to a ceiling")
    onset, gain, ceiling = (float(g) for g in fwd.groups())
    jump = re.search(r"jump\s*=\s*jump_rate\s*>\s*([\d.]+)", src)
    assert jump, "model.py no longer triggers a jump at `jump_rate > <rate>`"
    return {
        "forward_onset_hz": onset / DT,
        "forward_full_drive_hz": (onset + ceiling / gain) / DT,
        "jump_event_hz": float(jump.group(1)) / DT,
    }


# --------------------------------------------------------------------------
# 1. the schema speaks Hz and its ranges are physically reachable
# --------------------------------------------------------------------------

@pytest.mark.parametrize("pid", GATE_PIDS)
def test_schema_declares_hz_with_a_reachable_range(pid):
    meta = _params()[pid]
    lo, hi, dflt = float(meta["min"]), float(meta["max"]), float(meta["default"])
    assert "Hz" in meta["description"], "the unit must be declared in the schema"
    assert "RULE-19" in meta["description"], "the unit contract must be referenced"
    assert 0.0 < lo <= dflt <= hi
    # A threshold above the pool-rate ceiling (1/dt) can never be exceeded:
    # that is precisely how the old 2.0-"Hz" jump gate became unreachable.
    assert hi <= NYQUIST_HZ, "%s max=%s Hz is above Nyquist %s Hz" % (pid, hi, NYQUIST_HZ)
    assert dflt < NYQUIST_HZ


@pytest.mark.parametrize("pid", GATE_PIDS)
def test_schema_description_names_both_sides_of_the_comparison(pid):
    """Explicit units: the per-tick observation AND the Hz threshold."""
    desc = _params()[pid]["description"]
    assert "每-tick" in desc, "the per-tick observation side must be named"
    assert "1/dt" in desc, "the Hz conversion factor must be documented"
    assert "telemetry.py" in desc, "the dashboard unit agreement must be documented"


def test_thresholds_are_calibrated_against_the_decoder_not_the_test():
    """The registry must stay measurable — calibrated on `model.py`, in Hz.

    Guards against "passing" this PIN by loosening the constants:
      * the jump gate must be STRICTLY stricter than the decoder's own jump
        trigger, otherwise the gate is open whenever a jump could fire at all;
      * the forward gate must open no later than the decoder's full-drive
        point (`raw_y` saturates there), so it never requires saturation;
      * neither gate may open on zero activity.
    """
    refs = _decoder_references_hz()
    fwd = _params()[FORWARD_PID]
    jmp = _params()[JUMP_PID]

    assert refs["jump_event_hz"] == pytest.approx(2.0)
    assert refs["forward_onset_hz"] == pytest.approx(0.4)
    assert refs["forward_full_drive_hz"] == pytest.approx(2.15)

    assert float(fwd["default"]) > refs["forward_onset_hz"], (
        "gate_forward must not open on the decoder's first trace of drive")
    assert float(fwd["default"]) <= refs["forward_full_drive_hz"], (
        "gate_forward must already be open at full decode drive (no saturation)")
    assert float(fwd["min"]) >= refs["forward_onset_hz"]
    assert float(jmp["default"]) > refs["jump_event_hz"], (
        "gate_jump must be stricter than the decoder's own jump trigger")
    assert float(jmp["min"]) >= refs["jump_event_hz"]
    assert float(jmp["max"]) <= NYQUIST_HZ


# --------------------------------------------------------------------------
# 2. main.py converts once, explicitly, and compares Hz against Hz
# --------------------------------------------------------------------------

def test_every_pool_rate_is_converted_to_hz_before_the_gate():
    """The flow.json publication site converts with `rate_per_tick_to_hz`."""
    asg = _assignments()
    for var, attr in (("_forward_rate_hz", "forward_rate"),
                      ("_turn_rate_hz", "turn_rate"),
                      ("_jump_rate_hz", "jump_rate")):
        assert var in asg, "%s is missing from main.py" % var
        call = asg[var]
        assert isinstance(call, ast.Call) and getattr(call.func, "id", None) == \
            "rate_per_tick_to_hz", "%s is not the shared Hz conversion" % var
        observed = call.args[0]
        assert isinstance(observed, ast.Call) and getattr(observed.func, "id", None) == \
            "getattr" and observed.args[1].value == attr, (
            "%s must convert Control.%s (the per-tick fraction)" % (var, attr))
        assert ast.unparse(call.args[1]) == "_rate_dt", (
            "%s must use the model's own dt, not a second hardcoded rate" % var)

    # `_rate_dt` comes from model.dt with a documented fallback.
    assert "_rate_dt" in asg
    dt_src = ast.unparse(asg["_rate_dt"])
    assert "dt" in dt_src and "GATE_RATE_DT_DEFAULT" in dt_src, dt_src


def test_gates_compare_hz_against_hz_and_republish_the_threshold_unit():
    lit = _flow_json_literals()
    for key in ("forward_rate_hz", "turn_rate_hz", "jump_rate_hz"):
        assert key in lit, "flow.json must expose %s" % key
    for key in ("gate_forward_threshold_hz", "gate_jump_threshold_hz"):
        assert key in lit, "flow.json must expose the threshold unit as %s" % key
    for key, var in (("gate_forward", "_forward_rate_hz"),
                     ("gate_jump", "_jump_rate_hz")):
        inner = _unwrap(lit[key])
        assert isinstance(inner, ast.Call) and getattr(inner.func, "id", None) == \
            "gate_open_hz", "%s must go through gate_open_hz" % key
        assert ast.unparse(inner.args[0]) == var, (
            "%s must compare the Hz value, not the per-tick fraction" % key)

    # The thresholds are still read from the `exploration` section (the panel
    # write path) and are still literals inside the registry range.
    for leaf in ("gate_forward_threshold", "gate_jump_threshold"):
        defaults = _read_defaults(leaf)
        assert len(defaults) == 1, "%s read sites: %s" % (leaf, defaults)


def test_no_per_tick_rate_is_compared_against_a_hz_threshold():
    """Regression pin for the exact defect: no Compare may mix the two units."""
    mixed = []
    for node in ast.walk(_main_tree()):
        if not isinstance(node, ast.Compare):
            continue
        left = ast.unparse(node.left)
        if not any(left.endswith(attr) for attr in RATE_ATTRS):
            continue
        right = " ".join(ast.unparse(c) for c in node.comparators)
        if "gate_" in right or "threshold" in right:
            mixed.append("%s (line %d)" % (ast.unparse(node), node.lineno))
    assert not mixed, (
        "per-tick pool rate compared against an Hz threshold: %s" % mixed)

    src = _main_source()
    # The defective readers used the old (per-tick-context) literals.
    assert '"gate_forward_threshold", 0.4' not in src
    assert '"gate_jump_threshold", 2.0' not in src


def test_main_defaults_equal_the_schema_defaults():
    """The in-code fallback can never drift from the registry default."""
    for pid in GATE_PIDS:
        leaf = pid.split(".", 1)[1]
        defaults = _read_defaults(leaf)
        assert defaults == [pytest.approx(float(_params()[pid]["default"]))], (
            "main.py fallback %s != registry default %s for %s"
            % (defaults, _params()[pid]["default"], pid))


# --------------------------------------------------------------------------
# 3. the gates are reachable, and the boundary is explicit
# --------------------------------------------------------------------------

def test_gate_jump_is_reachable_at_the_measured_pool_rate():
    """gate_jump must not be a constant-False signal any more."""
    threshold = float(_params()[JUMP_PID]["default"])
    observed_hz = rate_per_tick_to_hz(MEASURED_JUMP_PER_TICK, DT)
    assert observed_hz == pytest.approx(13.8, abs=0.05)
    assert gate_open_hz(observed_hz, threshold) is True

    # The defect, reproduced: the same measurement compared as a per-tick
    # fraction against the Hz threshold was unreachable by construction.
    assert MEASURED_JUMP_PER_TICK <= 1.0
    assert gate_open_hz(MEASURED_JUMP_PER_TICK, threshold) is False


def test_gate_jump_boundary_is_closed_and_ceiling_is_open():
    threshold = float(_params()[JUMP_PID]["default"])
    assert gate_open_hz(threshold, threshold) is False, "boundary must be closed"
    assert gate_open_hz(threshold + 1e-9, threshold) is True
    assert gate_open_hz(threshold - 1e-9, threshold) is False
    assert gate_open_hz(0.0, threshold) is False, "a silent pool is closed"
    assert gate_open_hz(NYQUIST_HZ, threshold) is True, (
        "the ceiling rate (1/dt) must be able to open the gate")


def test_gate_forward_opens_on_a_healthy_pool_without_saturation():
    threshold = float(_params()[FORWARD_PID]["default"])
    refs = _decoder_references_hz()

    assert threshold < 5.0
    assert gate_open_hz(5.0, threshold) is True, "healthy forward pool must open"
    assert gate_open_hz(refs["forward_full_drive_hz"], threshold) is True, (
        "the gate must already be open at full decode drive — not saturation")
    # ... while remaining informative rather than always-on.
    assert gate_open_hz(0.0, threshold) is False
    assert gate_open_hz(refs["forward_onset_hz"], threshold) is False, (
        "the decoder's first trace of drive must not open the gate")
    assert gate_open_hz(threshold - 1e-9, threshold) is False


# --------------------------------------------------------------------------
# 4. brain and dashboard report the same quantity in the same unit
# --------------------------------------------------------------------------

def test_brain_and_dashboard_agree_on_the_hz_conversion():
    """Same 1/dt as telemetry.py, so the two telemetry surfaces cannot diverge."""
    m = FlyModel(demo=True)
    assert m.dt == pytest.approx(DT)
    obs = Observatory(m)
    rng = np.random.default_rng(64)
    game = dict(x=0, y=0, jump=False, state=4, age_ms=300.)
    for tick in range(30):
        frame = rng.integers(0, 256, (256, 384, 3), np.uint8)
        control, spikes = m.step(frame)
        row = obs.observe(frame, tick, control, spikes, game)
        assert row["forward"] == pytest.approx(
            rate_per_tick_to_hz(control.forward_rate, m.dt), rel=1e-6)
        assert row["jump"] == pytest.approx(
            rate_per_tick_to_hz(control.jump_rate, m.dt), rel=1e-6)
        assert row["right"] - row["left"] == pytest.approx(
            rate_per_tick_to_hz(control.turn_rate, m.dt), abs=1e-5)


def test_rate_per_tick_to_hz_rejects_a_nonsense_dt():
    with pytest.raises(ValueError):
        rate_per_tick_to_hz(0.5, 0.0)
    with pytest.raises(ValueError):
        rate_per_tick_to_hz(0.5, -0.02)


# --------------------------------------------------------------------------
# 5. the register records the decision (and its unit convention)
# --------------------------------------------------------------------------

def test_register_marks_both_gate_pids_implemented_in_hz():
    text = DOCS.read_text(encoding="utf-8")
    assert "RULE-19" in text, "the unit contract decision must be recorded"
    for pid in GATE_PIDS:
        rows = [ln for ln in text.splitlines() if pid in ln]
        assert rows, "%s must be recorded in the register" % pid
        assert any("implemented" in ln and "Hz" in ln for ln in rows), rows
        for ln in rows:
            low = ln.lower()
            assert not any(marker in low for marker in
                           ("zero consumer", "zero-consumer")), rows
            assert "零消费者" not in ln, rows

    # The stale "unwired tunable parameters" table must not list them again.
    section2 = text.split("## 2.")[1].split("## 2b.")[0]
    for pid in GATE_PIDS:
        assert pid not in section2, (
            "%s is implemented; it must not sit in the unwired table" % pid)

    # Ranges recorded in the register stay in sync with the schema.
    assert "0.4 .. 8.0" in text and "2.0 .. 20.0" in text
