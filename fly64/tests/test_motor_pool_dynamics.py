#!/usr/bin/env python3
"""T2+T8 regression — motor-pool dynamic range, steering revival, reflex share.

Root cause + measurements: ``docs/analysis/motor-pool-saturation-findings.md``
(t1).  This module locks down three defect families and their round-2 repairs:

1. **forward pool pinned at the ceiling** (t1 §A1/§A4/§A5).  Live: 0.92–1.00
   occupancy (46.15–50.00 Hz) while ``mb_mbon_forward`` swung −0.89…+0.97, i.e.
   the MBON pathway was not the driver; the pool had no feedback of its own
   occupancy and a post-leak floor (breakout 0.50 + tonic 0.18 + sticky
   reflex_forward 0.20) held it there.  T2 added the occupancy homeostat on the
   MBON pathway + forward-pool tonic; **T8** extends it to the two escape legs
   and the R16 breakout forward leg, adds an *aggregate ceiling* on the
   auxiliary forward legs (t8 measured the live-like escape arm at exactly
   0.5000 occupancy without it), and neutralises the ``_last_disp_x/_z`` dead
   read that used to ramp the escape accumulator to its cap permanently.
2. **steering pools silent** (t1 §A5/§B4).  ``breakout_drive``'s stuck boost
   clamps each turn pool by −0.25 V/tick even with zero fatigue; measured
   left/right were 0.000/0.000 Hz.  The clamp now scales with the real weave
   signature while the forward breakthrough keeps a bounded floor.
3. **reflex-flag stickiness** (t1 §A5 + t8).  main.py writes
   ``reflex_turn/forward/jump`` while the reflex is active and never resets
   them, so a one-off write used to inject current forever.  Flags now expire:
   1.0 inside ``reflex_flag_ttl``, exponential decay with ``reflex_flag_tau``
   afterwards, and the auxiliary leg is occupancy-scaled on top.

Fixture note: the prepared MaleCNS cache is absent on this host
(``fly64/.cache/malecns``), so the tests use ``FlyModel(demo=True)``.  The
fixture's random graph pins *every* motor pool at the ceiling on its own
(measured occupancy 1.0000), which would mask the pathway under test; the graph
is therefore scaled into the responsive regime (``CONNECTOME_SCALE``) so the
assertions measure the mechanism, not the fixture.
"""
from __future__ import annotations

import ast
import pathlib
import re

import numpy as np
import pytest
import scipy.sparse as sp

from fly64.model import FlyModel

# ---- controlled fixture -----------------------------------------------------

CONNECTOME_SCALE = 0.02          # responsive regime (fixture alone pins at 1.0)
DARK = np.zeros((256, 384, 3), np.uint8)
BRIGHT = np.full((256, 384, 3), 255, np.uint8)
NOISE = np.random.default_rng(7).integers(0, 256, (256, 384, 3), np.uint8)

TICKS = 400
WARM = 150                       # discard the transient (occupancy low-pass 0.15 s)

# t7 owns the main.py wiring of the reflex/LIF blend (contract: out of scope for
# t2/t8).  This is the documented one-liner the model-side API expects, at the
# site where main.py currently overwrites control.x/y with the reflex command:
#     x, y, jump = model.blend_reflex_control(action["control_x"],
#                                             action["control_y"], action["jump"])
#     control.x, control.y, control.jump = x, y, jump
T7_WIRING_SITE = "main.py:1550-1552"


class _StubMushroom:
    """Constant-MBON mushroom body: isolates mbon[k] → motor-pool injection."""

    def __init__(self, mb: float):
        self.mbon_outputs = np.asarray([mb] + [0.0] * 8, dtype=np.float32)
        self.familiarity = 0.0
        self.assoc_count = 0

    def encode(self, sig):
        return self.mbon_outputs

    def set_dopamine(self, d):
        return 0.0

    def update_weights(self):
        return 0

    def recall(self):
        return None

    def consolidate_anomaly_resolution(self, *a, **k):
        return None


def _model(mb: float = 0.0, *, scale: float = CONNECTOME_SCALE,
           stuck: float = 0.0, escape: bool = False,
           escape_bias: float = 0.20, fatigue: float = 0.0,
           breakout: bool = True) -> FlyModel:
    m = FlyModel(demo=True, seed=64)
    m.w = (sp.csr_matrix((m.n, m.n), dtype=np.float32) if scale == 0.0
           else m.w * scale)
    m.stuck_duration = stuck
    m.anomaly_state_name = "oscillating"      # live value (disables the pit/R22
    m.mb_mbon_forward = mb                    # stuck-gated open-loop injectors)
    m.escape_mode = escape
    # main.py's live wiring: escape.breakout_forward_bias → _max_escape_forward
    # and escape.forward_accum_max → the accumulator seed (main.py:1413, 1507).
    m._max_escape_forward = escape_bias
    m._escape_forward_accum = escape_bias
    m._turn_adapt.left = m._turn_adapt.right = float(fatigue) * m._turn_adapt.saturation
    if not breakout:
        m.breakout_split = lambda stuck_duration=None: (0.0, 0.0, 0.0)
    m.mushroom = _StubMushroom(mb)
    return m


_CACHE: dict = {}


def _measured(mb: float = 0.0, frame_kind: str = "dark", *, scale: float = CONNECTOME_SCALE,
              stuck: float = 0.0, escape: bool = False, escape_bias: float = 0.20,
              fatigue: float = 0.0, breakout: bool = True,
              reflex_forward: int = 0, reflex_mode: str = "off",
              reflex_turn: bool = False, ticks: int = TICKS,
              warm: int = WARM) -> dict:
    """Run one controlled scenario and return pool/feedback statistics.

    ``reflex_mode``: ``"off"`` never writes the flag, ``"once"`` writes it once
    before the loop (the t1 sticky pattern), ``"refresh"`` writes it every tick
    (what main.py does while the reflex is active).
    """
    key = (mb, frame_kind, scale, stuck, escape, escape_bias, fatigue, breakout,
           reflex_forward, reflex_mode, reflex_turn, ticks, warm)
    if key in _CACHE:
        return _CACHE[key]
    frame = {"dark": DARK, "bright": BRIGHT, "noise": NOISE}[frame_kind]
    m = _model(mb, scale=scale, stuck=stuck, escape=escape, escape_bias=escape_bias,
               fatigue=fatigue, breakout=breakout)
    if reflex_forward and reflex_mode == "once":
        m.reflex_forward = reflex_forward
    pools = {"forward": m.forward, "left": m.turn_left,
             "right": m.turn_right, "jump": m.jump_nodes}
    acc = {k: [] for k in pools}
    gates, tonics, aux_used, brk_applied, eff_fwd = [], [], [], [], []
    left_active = right_active = 0
    for i in range(ticks):
        if reflex_forward and reflex_mode == "refresh":
            m.reflex_forward = reflex_forward
        if reflex_turn:
            m.reflex_turn = 70 if (i // 100) % 2 == 0 else -70
        m.step(frame)
        if i >= warm:
            for k, ids in pools.items():
                acc[k].append(float(m.spikes[ids].mean()))
            gates.append(float(m._fwd_homeo_gain))
            tonics.append(float(m._fwd_tonic_current))
            aux_used.append(float(m._fwd_aux_used))
            brk_applied.append(float(m._fwd_brk_applied))
            eff_fwd.append(float(m._reflex_effective["forward"]))
            left_active += int(bool(m.spikes[m.turn_left].any()))
            right_active += int(bool(m.spikes[m.turn_right].any()))
    fwd_series = acc["forward"]
    out = {
        "occ": {k: float(np.mean(v)) for k, v in acc.items()},
        "fwd_max": float(np.max(fwd_series)) if fwd_series else 0.0,
        "gate": float(np.mean(gates)),
        "tonic": float(np.mean(tonics)),
        "aux": float(np.mean(aux_used)),
        "aux_max": float(np.max(aux_used)),
        "brk": float(np.mean(brk_applied)),
        "eff_fwd": float(np.mean(eff_fwd)),
        "left_active": left_active,
        "right_active": right_active,
        "samples": ticks - warm,
    }
    _CACHE[key] = out
    return out


# ---- (a) + monotonicity: forward pool dynamic range -------------------------

def test_full_mbon_drive_does_not_pin_forward_pool():
    """(a) MBON forward driven at 1.0 → steady-state occupancy < 0.6.

    Pre-fix the same input produced 0.92–1.00 (46.15–50.00 Hz, t1 §A1).  The
    pool must also stay alive — the homeostat is bounded, never a mute.
    """
    r = _measured(mb=1.0)
    assert r["occ"]["forward"] < 0.6, \
        f"forward pool pinned at {r['occ']['forward']:.4f} occupancy (>= 0.6)"
    assert r["occ"]["forward"] > 0.05, \
        f"forward pool went silent ({r['occ']['forward']:.4f}) under full MBON drive"


def test_forward_occupancy_is_monotonic_in_mbon_input():
    """Occupancy rises monotonically with MBON input and never reaches the ceiling."""
    occs = {mb: _measured(mb=mb)["occ"]["forward"] for mb in (0.0, 0.25, 0.5, 0.75, 1.0)}
    vals = list(occs.values())
    assert all(b >= a for a, b in zip(vals, vals[1:])), \
        f"occupancy not monotonic in MBON input: {occs}"
    assert occs[1.0] > occs[0.0] + 0.05, \
        f"no measurable response to MBON strength: {occs}"
    assert occs[1.0] < 0.6 and occs[0.0] < 0.6, \
        f"ceiling not restored: {occs}"


# ---- (b) negative feedback of the pool's own occupancy ----------------------

def test_forward_homeo_gain_is_negative_feedback_of_occupancy():
    """(b) The injected drive falls as the pool's occupancy rises (and is floored)."""
    m = FlyModel(demo=True, seed=64)
    gates = [m.forward_homeo_gain(o) for o in (0.0, 0.15, 0.30, 0.45, 0.60, 0.80, 1.0)]
    assert gates[0] == pytest.approx(1.0), "no suppression at zero occupancy"
    assert all(b <= a for a, b in zip(gates, gates[1:])), \
        f"gain is not a decreasing function of occupancy: {gates}"
    assert gates[-1] == pytest.approx(m.fwd_homeo_floor)
    assert 0.0 < m.fwd_homeo_floor < 1.0, "floor must keep the pathway non-silent"
    assert gates[4] < gates[2], "suppression must be measurable inside the band"


def test_high_occupancy_measurably_suppresses_the_injection():
    """In-run evidence: the applied gain (and its tonic limb) is lower when the

    pool actually runs hot — an MBON-driven run vs a low-input run of the same
    model.  Both limbs are asserted: MBON-path gain and forward-pool tonic.
    """
    low = _measured(mb=0.0)
    high = _measured(mb=1.0)
    assert high["occ"]["forward"] > low["occ"]["forward"]
    assert high["gate"] < low["gate"] - 0.05, \
        f"mean gain not suppressed at higher occupancy ({low['gate']:.3f} → {high['gate']:.3f})"
    assert high["tonic"] < low["tonic"], \
        "forward-pool intrinsic (tonic) excitability did not fall with occupancy"
    assert low["tonic"] <= 0.180 + 1e-6, "tonic limb must never exceed tonic_current"


# ---- (c) forward occupancy tracks the visual/scene drive --------------------

def test_forward_occupancy_responds_to_visual_drive():
    """(c) Different visual drive → measurably different forward occupancy."""
    dark = _measured(mb=0.0, frame_kind="dark")["occ"]["forward"]
    bright = _measured(mb=0.0, frame_kind="bright")["occ"]["forward"]
    noise = _measured(mb=0.0, frame_kind="noise")["occ"]["forward"]
    spread = max(dark, bright, noise) - min(dark, bright, noise)
    assert spread > 0.05, \
        f"forward occupancy does not track the visual drive (dark={dark:.3f}, " \
        f"bright={bright:.3f}, noise={noise:.3f})"
    assert dark < bright, "a bright frame must drive the pool harder than a dark one"


# ---- (d) steering pools both fire under directional drive -------------------

def test_both_steering_pools_fire_under_directional_drive():
    """(d) left/right both produce spikes when a turn command is applied.

    Pre-fix the R16 stuck boost clamped each pool by −0.25 V/tick, so the
    undriven side stayed at 0.000 Hz (t1 §B4/E8b).
    """
    r = _measured(mb=0.0, reflex_turn=True)
    assert r["left_active"] > 0, "left steering pool never fired"
    assert r["right_active"] > 0, "right steering pool never fired"
    assert r["left_active"] >= 0.1 * r["samples"], \
        f"left pool barely active: {r['left_active']}/{r['samples']}"
    assert r["right_active"] >= 0.1 * r["samples"], \
        f"right pool barely active: {r['right_active']}/{r['samples']}"


def test_breakout_split_removes_the_silent_fly_turn_clamp():
    """Steering-revival mechanism (t1 §A5): the clamp needs real oscillation.

    * silent fly (zero fatigue) + long stuck: forward breakthrough keeps a
      bounded floor (escape preserved) but the per-side turn clamp is 0;
    * genuinely weaving fly (both circuits saturated): the full drive returns.
    * fatigue without stuck: the unboosted base drive keeps its old contract.
    * no stuck / no fatigue: no drive at all.
    """
    m = FlyModel(demo=True, seed=64)
    m._turn_adapt.left = m._turn_adapt.right = 0.0
    fwd, turn, raw = m.breakout_split(806.8)
    assert raw == pytest.approx(0.5)                 # stuck boost still computed
    assert turn == 0.0, "silent fly must not have its steering pools clamped"
    assert fwd == pytest.approx(0.5 * m.breakout_forward_osc_floor)
    assert fwd > 0.0, "escape breakthrough floor removed"

    m._turn_adapt.left = m._turn_adapt.right = m._turn_adapt.saturation
    fwd2, turn2, raw2 = m.breakout_split(806.8)
    assert raw2 == pytest.approx(0.85)               # base 0.35 + boost 0.50
    assert fwd2 == pytest.approx(0.85), "weave breakthrough no longer paid in full"
    assert turn2 == pytest.approx(0.425), "weave turn clamp no longer paid in full"

    fwd3, turn3, raw3 = m.breakout_split(0.0)
    assert raw3 == pytest.approx(m._turn_adapt.breakout_gain)
    assert fwd3 == pytest.approx(m._turn_adapt.breakout_gain)
    assert turn3 == pytest.approx(m._turn_adapt.breakout_gain * 0.5)

    m._turn_adapt.left = m._turn_adapt.right = 0.0
    assert m.breakout_split(0.0) == (0.0, 0.0, 0.0)


# ---- T8 A5: osc=1 arm and the breakout forward leg --------------------------

def test_oscillating_arm_stays_below_half_occupancy():
    """A5 acceptance: the weaving (osc=1) + long-stuck arm must measure < 50%.

    Both turn circuits saturated at ``stuck_duration`` 806.8 s — the state that
    used to pay the full +0.50 V/tick breakthrough.  The breakout forward leg is
    homeostat-scaled (asserted directly) and the measured occupancy stays under
    half the ceiling.
    """
    r = _measured(mb=1.0, stuck=806.8, fatigue=1.0)
    assert r["occ"]["forward"] < 0.5, \
        f"osc=1 arm occupancy {r['occ']['forward']:.4f} >= 0.50"
    assert r["occ"]["forward"] > 0.05, "osc=1 arm went silent"
    m = FlyModel(demo=True, seed=64)
    m._turn_adapt.left = m._turn_adapt.right = m._turn_adapt.saturation
    raw_fwd = m.breakout_split(806.8)[0]
    assert raw_fwd == pytest.approx(0.85)
    assert r["brk"] <= raw_fwd + 1e-6, \
        f"applied breakout push {r['brk']:.4f} exceeds the raw request {raw_fwd:.4f}"
    assert r["brk"] < raw_fwd, "breakout forward leg is not scaled by the homeostat"


def test_breakout_leg_changes_silent_stuck_occupancy():
    """A6: with/without the breakout leg, a silent stuck individual differs.

    Upgraded from the t2 "> 0" check: the leg must *change* the measured
    occupancy by a real margin in the silent (fatigue = 0) + long-stuck state.
    """
    on = _measured(mb=0.0, scale=0.0, stuck=806.8, fatigue=0.0)
    off = _measured(mb=0.0, scale=0.0, stuck=806.8, fatigue=0.0, breakout=False)
    delta = on["occ"]["forward"] - off["occ"]["forward"]
    assert on["brk"] > 0.0 and off["brk"] == 0.0
    assert delta > 0.05, \
        f"breakout leg changes occupancy by only {delta:+.4f} " \
        f"(on={on['occ']['forward']:.4f}, off={off['occ']['forward']:.4f})"
    assert on["occ"]["forward"] > 0.2, "escape forward drive lost"


# ---- T8 A1: live-like arm with escape ---------------------------------------

def test_live_like_escape_arm_stays_below_half_occupancy():
    """A1/A3 acceptance: escape_mode + live wiring must measure < 50%.

    Live-like = ``escape_mode`` on, ``breakout_forward_bias`` 0.2 (main.py:1413),
    the escape accumulator seeded as main.py:1507 does, long stuck, reflex
    forward refreshed every tick (an *active* reflex), MBON at the live plateau.
    Measured 0.5000 without the aggregate auxiliary ceiling (t8 pre-fix) and
    0.3963 / 0.4336 with it (scale 0.0 / 0.02).
    """
    for scale, limit in ((0.0, 0.5), (CONNECTOME_SCALE, 0.5)):
        r = _measured(mb=0.96, scale=scale, stuck=806.8, escape=True,
                      escape_bias=0.20, reflex_forward=70, reflex_mode="refresh")
        assert r["occ"]["forward"] < limit, \
            f"live-like escape arm (scale={scale}) occupancy " \
            f"{r['occ']['forward']:.4f} >= {limit}"
        assert r["occ"]["forward"] > 0.2, "escape forward drive lost in the live-like arm"
        assert r["aux_max"] <= 0.20 + 1e-6, \
            f"auxiliary forward legs exceeded the aggregate ceiling: {r['aux_max']:.4f}"


def test_escape_legs_are_homeostat_bounded():
    """A1: the two escape legs honour the occupancy gain + aggregate ceiling.

    The escape-current forward slice and the escape accumulator are auxiliary
    legs: at a high occupancy their applied drive must be below their raw
    request, and the aggregate applied in any tick must never exceed
    ``fwd_aux_ceiling``.
    """
    m = FlyModel(demo=True, seed=64)
    m.mushroom = _StubMushroom(0.0)
    m.escape_mode = True
    m.escape_current = 0.24
    m._fwd_aux_used = 0.0
    m._fwd_homeo_gain = 0.25                     # pool running hot
    assert m._aux_forward_current(0.24) < 0.24, \
        "escape leg not scaled by the occupancy gain"
    m._fwd_aux_used = 0.0
    m._fwd_homeo_gain = 1.0
    assert m._aux_forward_current(0.24) == pytest.approx(m.fwd_aux_ceiling)
    assert m._aux_forward_current(0.24) == pytest.approx(0.0), \
        "auxiliary budget not exhausted by the first leg"
    r = _measured(mb=0.96, scale=0.0, stuck=806.8, escape=True, escape_bias=0.20,
                  reflex_forward=70, reflex_mode="refresh")
    assert r["aux_max"] <= m.fwd_aux_ceiling + 1e-6


def test_live_like_stuck_regime_keeps_steering_alive():
    """End-to-end: the t1 symptom state (long stuck + active reflex + escape)

    must no longer silence the steering pools, and the forward pool must stay
    both off the ceiling and still driving.
    """
    r = _measured(mb=1.0, scale=0.0, stuck=806.8, escape=True, escape_bias=0.20,
                  reflex_forward=70, reflex_mode="refresh", reflex_turn=True)
    assert r["left_active"] > 0 and r["right_active"] > 0, \
        f"steering pools still silent in the live-like regime: {r}"
    assert r["occ"]["forward"] < 0.6, \
        f"forward pool pinned in the live-like regime: {r['occ']['forward']:.4f}"
    assert r["occ"]["forward"] > 0.2, \
        f"escape forward drive lost in the live-like regime: {r['occ']['forward']:.4f}"


def test_escape_accumulator_dead_read_is_neutralised():
    """A1: ``_last_disp_x/_z`` have no writer → no phantom ramp.

    The old ``getattr(..., 0.0)`` made the "adaptive" escape accumulator ramp to
    its cap and stay there: an unconditional post-leak constant.  Without a
    displacement signal the accumulator must settle back to its base; with one it
    must still ramp (the ramp stays a *response*, not a constant).
    """
    m = _model(scale=0.0, escape=True, escape_bias=0.20)
    for _ in range(100):
        m.step(DARK)
    assert m._disp_signal_available is False, "dead read still reported as available"
    assert m._escape_forward_accum == pytest.approx(m.escape_accum_base), \
        f"accumulator ramped without a displacement signal: {m._escape_forward_accum}"

    m2 = _model(scale=0.0, escape=True, escape_bias=0.20)
    m2._escape_forward_accum = m2.escape_accum_base
    m2._last_disp_x, m2._last_disp_z = 0.0, 0.0      # producer: no progress
    for _ in range(100):
        m2.step(DARK)
    assert m2._disp_signal_available is True
    assert m2._escape_forward_accum == pytest.approx(m2._max_escape_forward), \
        f"accumulator did not ramp with a real signal: {m2._escape_forward_accum}"

    m3 = _model(scale=0.0, escape=True, escape_bias=0.20)
    m3._escape_forward_accum = m3.escape_accum_base
    m3._last_disp_x, m3._last_disp_z = 5.0, 0.0      # producer: real progress
    for _ in range(50):
        m3.step(DARK)
    assert m3._escape_forward_accum == pytest.approx(m3.escape_accum_base), \
        "accumulator must not ramp while the fly is making progress"


# ---- T8 A2/A3: reflex-flag expiry -------------------------------------------

def test_stale_reflex_flag_injection_expires():
    """A2/A3: a one-off reflex write decays to zero; a refreshed one does not.

    Also records the t1 sticky evidence: the *raw* attribute is never reset by
    the model (it still reads 70 after 200 ticks) — only the effective injection
    expires.
    """
    m = _model(scale=0.0)
    m.reflex_forward = 70                      # one-off write (t1 sticky pattern)
    early, late = [], []
    for i in range(200):
        m.step(DARK)
        (early if i < 15 else late).append(float(m._reflex_effective["forward"]))
    assert np.mean(early) == pytest.approx(70.0), "fresh flag must be fully effective"
    assert np.mean(late) < 0.06 * 70, \
        f"stale flag injection did not decay: mean eff {np.mean(late):.3f}"
    assert m.reflex_forward == 70, "model must not reset the producer's flag"

    m2 = _model(scale=0.0)
    for _ in range(200):
        m2.reflex_forward = 70                 # refreshed every tick (main.py)
        m2.step(DARK)
    assert float(m2._reflex_effective["forward"]) == pytest.approx(70.0)
    assert m2.reflex_flag_scale("reflex_forward") == pytest.approx(1.0)


def test_reflex_flag_expiry_contract():
    """A2: the expiry map is explicit — inert / fresh / exponential decay."""
    m = FlyModel(demo=True, seed=64)
    for name in ("reflex_turn", "reflex_forward", "reflex_jump"):
        assert m.reflex_flag_scale(name) == 0.0, f"{name} inert before any write"
    m.reflex_forward = 70
    ttl = m.reflex_flag_ttl
    tau = m.reflex_flag_tau
    assert m.reflex_flag_scale("reflex_forward", 0) == pytest.approx(1.0)
    assert m.reflex_flag_scale("reflex_forward", int(ttl / m.dt)) == pytest.approx(1.0)
    later = m.reflex_flag_scale("reflex_forward", int((ttl + tau) / m.dt))
    assert later == pytest.approx(float(np.exp(-1.0)), abs=1e-6)
    decayed = [m.reflex_flag_scale("reflex_forward", t)
               for t in range(0, int((ttl + 8 * tau) / m.dt), 5)]
    assert all(b <= a for a, b in zip(decayed, decayed[1:])), "decay is not monotone"
    assert decayed[-1] == 0.0, "flag never reaches zero"


def test_stale_reflex_flag_adds_a_measurable_occupancy_floor():
    """A3: quantify the sticky-leg damage (occupancy increment).

    Minimal config (no MBON, no escape, no stuck): the tonic current alone leaves
    the pool nearly silent (measured 0.0572 — the residual is the OU pedestal,
    t1 §B3).  A one-off reflex write adds up to 0.20 V/tick and lifts occupancy
    to 0.2033 (+0.146); once the flag expires the increment disappears and the
    occupancy returns to the quiet level (measured 0.0573).  A *refreshed* flag
    (main.py's behaviour while the reflex is active) sustains +0.1932.
    """
    quiet = _measured(scale=0.0, reflex_forward=0, ticks=200, warm=100)
    refreshed = _measured(scale=0.0, reflex_forward=70, reflex_mode="refresh",
                          ticks=200, warm=100)
    assert quiet["occ"]["forward"] < 0.15, \
        f"quiet pool should stay near-silent: {quiet['occ']['forward']:.4f}"
    assert refreshed["occ"]["forward"] > quiet["occ"]["forward"] + 0.10, \
        f"an active reflex no longer drives the pool " \
        f"({refreshed['occ']['forward']:.4f} vs {quiet['occ']['forward']:.4f})"

    m = _model(scale=0.0)
    m.reflex_forward = 70
    fires = []
    for _ in range(200):
        m.step(DARK)
        fires.append(float(m.spikes[m.forward].mean()))
    early = float(np.mean(fires[5:15]))
    late = float(np.mean(fires[100:]))
    assert early > 0.1, f"one-off write never drove the pool (early={early:.3f})"
    assert late < early, \
        f"one-off write did not decay (early={early:.3f}, late={late:.3f})"
    assert abs(late - quiet["occ"]["forward"]) < 0.05, \
        f"after expiry the occupancy must return to the quiet level " \
        f"(late={late:.4f}, quiet={quiet['occ']['forward']:.4f})"


# ---- T8 A4(e): exhaustive write-site contract -------------------------------

_MODEL_PATH = pathlib.Path(__file__).resolve().parents[1] / "fly64" / "model.py"

# Notes are keyed by the exact (AST-normalised) right-hand side of each
# injection; every discovered site must match exactly one key and every key must
# be used, so adding, renaming or editing a forward-pool injection forces this
# contract to be updated.
_SITE_NOTES = {
    "mbon[0] * self.mbon_gain_forward * self._fwd_homeo_gain":
        "homeostat: MBON→forward pathway (T2)",
    "_recalled[0] * self.mbon_gain_forward * 0.5 * self._fwd_homeo_gain":
        "homeostat: consolidated-memory recall on the same pathway",
    "self.tonic_current * (1.0 - self._fwd_homeo_gain)":
        "homeostat: intrinsic tonic limb (negative write)",
    "self.escape_current":
        "gated: escape_mode whole-pool drive; forward slice is homeostat-bounded",
    "_esc_fwd - self.escape_current":
        "aux: escape-current forward slice (gain + aggregate ceiling)",
    "self._fallen_forward":
        "gated: fallen duty-cycle phase (default 0.20 < 1.0)",
    "_accum":
        "aux: escape accumulator (gain + aggregate ceiling)",
    "self._aux_forward_current(min(0.2, _rf_eff * 0.003))":
        "aux: reflex bridge (flag expiry + gain + aggregate ceiling)",
    "min(0.5, self.coach_forward_bias * 0.005)":
        "gated: coach command window",
    "0.1":
        "gated: interactive_near approach bias (0.10 < 1.0)",
    "_fwd_brk":
        "aux: R16 breakout forward leg (gain + aggregate ceiling)",
    "0.08":
        "gated: cliff tangential easing (−0.08, sub-threshold)",
    "_rest * 0.12":
        "gated: restlessness (0.12 < 1.0)",
    "0.4 * _hop":
        "gated: pit-escape oscillator (0.40 < 1.0)",
    "self.scene_danger * 0.06":
        "gated: danger caution (0.06·danger, sub-threshold)",
    "_rec * 0.08":
        "gated: helplessness recovery (0.08 < 1.0)",
}


def _forward_write_sites():
    """AST-enumerate every ``self.v[self.forward]`` / motor-pool injection site."""
    source = _MODEL_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    sites = []

    def pool_of(target):
        if (isinstance(target, ast.Subscript)
                and isinstance(target.value, ast.Attribute)
                and target.value.attr == "v"
                and isinstance(target.value.value, ast.Name)
                and target.value.value.id == "self"
                and isinstance(target.slice, ast.Attribute)
                and target.slice.attr in ("forward", "motor_nodes")):
            return target.slice.attr
        return None

    class _Visitor(ast.NodeVisitor):
        def __init__(self):
            self.if_depth = 0

        def visit_If(self, node):
            self.if_depth += 1
            self.generic_visit(node)
            self.if_depth -= 1

        def _record(self, target, value, lineno):
            pool = pool_of(target)
            if pool:
                sites.append(dict(lineno=lineno, pool=pool,
                                  rhs=ast.unparse(value), depth=self.if_depth))

        def visit_AugAssign(self, node):
            self._record(node.target, node.value, node.lineno)
            self.generic_visit(node)

        def visit_Assign(self, node):
            for target in node.targets:
                self._record(target, node.value, node.lineno)
            self.generic_visit(node)

    _Visitor().visit(tree)
    return source, sites


def test_forward_pool_write_sites_are_covered_or_gated():
    """A4(e): every constant injection into the forward pool is accounted for.

    Invariants (checked mechanically on the AST + source, not asserted by
    convention):

    * every discovered site matches exactly one registry note and every note is
      used (a new injection fails until it is classified);
    * an **ungated** site must be occupancy-covered — its RHS mentions
      ``_fwd_homeo_gain`` / ``_aux_forward_current``, or the statement that
      produces its value does;
    * a **gated** site must be inside at least one ``if`` *and* its own numeric
      literals (or the attribute's ``__init__`` default) must be below the LIF
      threshold, i.e. sub-threshold on its own.
    """
    source, sites = _forward_write_sites()
    assert len(sites) >= 12, f"write-site enumeration looks wrong: {sites}"

    matched = []
    for site in sites:
        hits = [k for k in _SITE_NOTES if k == site["rhs"]]
        assert len(hits) == 1, (
            f"model.py:{site['lineno']} injection {site['rhs']!r} matches "
            f"{len(hits)} registry notes — classify it explicitly")
        site["note"] = _SITE_NOTES[hits[0]]
        matched.append(hits[0])
    assert set(matched) == set(_SITE_NOTES), \
        f"registry entries without a site: {set(_SITE_NOTES) - set(matched)}"

    homeo_tokens = ("_fwd_homeo_gain", "_aux_forward_current")

    def _producer_covers(rhs, tokens):
        """Covered if the RHS (or any local it references) carries a token.

        ``self.v[self.forward] += _fwd_brk`` is covered when the statement that
        produced ``_fwd_brk`` routes it through ``_aux_forward_current``; the
        check reads that producer line out of the same source file.
        """
        if any(tok in rhs for tok in tokens):
            return True
        for name in set(re.findall(r"\b([A-Za-z_][A-Za-z_0-9]*)\b", rhs)):
            if re.search(rf"^\s*{re.escape(name)}\s*=.*({'|'.join(tokens)})",
                         source, re.M):
                return True
        return False

    for site in sites:
        rhs, note = site["rhs"], site["note"]
        covered = _producer_covers(rhs, homeo_tokens)
        if site["depth"] == 0:
            assert covered, (
                f"model.py:{site['lineno']} injects {rhs!r} unconditionally "
                f"without occupancy feedback ({note})")
        if note.startswith("aux"):
            assert covered, (
                f"model.py:{site['lineno']} is registered as an auxiliary leg but "
                f"does not go through _aux_forward_current ({rhs!r})")
        if "gated" in note:
            assert site["depth"] > 0, \
                f"model.py:{site['lineno']} is registered as gated but is not"
            lits = [float(x) for x in re.findall(r"(?<![\w.])(\d+\.?\d*)(?![\w.])", rhs)
                    if float(x) != 1.0]
            if lits:
                assert max(lits) < 1.0, \
                    f"model.py:{site['lineno']} gated constant {max(lits)} is >= threshold"
            else:
                attr = re.fullmatch(r"self\.([A-Za-z_][A-Za-z_0-9]*)", rhs)
                assert attr, f"model.py:{site['lineno']} cannot be bounded: {rhs!r}"
                default = re.search(rf"^\s*self\.{re.escape(attr.group(1))}\s*=\s*([0-9.]+)",
                                    source, re.M)
                assert default, f"no __init__ default found for {rhs!r}"
                assert float(default.group(1)) < 1.0, \
                    f"model.py:{site['lineno']} {rhs!r} default >= threshold"

    assert [s for s in sites if s["pool"] == "motor_nodes"], \
        "escape whole-pool injection disappeared from the enumeration"


def test_forward_aux_ceiling_bounds_the_aggregate():
    """A1/§A5: the auxiliary forward legs cannot sum past ``fwd_aux_ceiling``."""
    m = FlyModel(demo=True, seed=64)
    m._fwd_aux_used = 0.0
    m._fwd_homeo_gain = 1.0
    total = sum(m._aux_forward_current(leg)
                for leg in (0.125, 0.24, 0.24, 0.24))   # breakout, escape, accum, reflex
    assert total == pytest.approx(m.fwd_aux_ceiling)
    assert m._fwd_aux_used == pytest.approx(m.fwd_aux_ceiling)
    assert m.fwd_aux_ceiling < 0.402, (
        "the auxiliary ceiling must stay below the T=3 limit-cycle boundary "
        "(0.402 V/tick), otherwise the legs alone can pin the pool")


# ---- (e) reflex override keeps a proportional LIF share ---------------------

def test_reflex_blend_retains_network_share():
    """(e) The reflex command no longer overwrites control.x/y wholesale."""
    m = FlyModel(demo=True, seed=64)
    m.filtered_x, m.filtered_y, m.last_lif_jump = 24.0, 12.0, True

    assert m.reflex_network_share >= 0.25, "default network share must be >= 25%"
    x, y, jump = m.blend_reflex_control(70, 70)
    share = m.reflex_network_share
    assert abs(x - ((1 - share) * 70 + share * 24)) <= 0.5
    assert abs(y - ((1 - share) * 70 + share * 12)) <= 0.5
    assert x != 70 and y != 70, "reflex command still written through unchanged"
    assert abs(x - 70) >= share * abs(24 - 70) - 0.5
    assert m.last_reflex_mix["network_share"] == pytest.approx(share)
    assert m.last_reflex_mix["x"] == x and m.last_reflex_mix["y"] == y

    # configurable: 1.0 → pure network decode, 0.0 → pure reflex command
    assert m.blend_reflex_control(70, 70, network_share=1.0)[:2] == (24, 12)
    assert m.blend_reflex_control(70, 70, network_share=1.0)[2] is True
    assert m.blend_reflex_control(70, 70, network_share=0.0)[:2] == (70, 70)

    m.reflex_network_share = 0.5
    assert abs(m.blend_reflex_control(70, 70)[0] - 47) <= 0.5


def test_t7_integration_surface_and_share_floor():
    """A8 hand-off: the integration surface t7 needs exists and keeps ≥25%.

    The main.py edit itself is t7's (contract: out of scope here); this asserts
    the wiring target exists — ``reflex_network_share`` (configurable floor),
    ``blend_reflex_control`` (the mixer) and ``last_reflex_mix`` (the telemetry
    mirror) — and that the documented wiring keeps at least a quarter of the
    LIF decode in the command.  t7 must wire it at ``main.py:1550-1552`` and
    cover the ≥25% share in integration/live verification.
    """
    m = FlyModel(demo=True, seed=64)
    assert T7_WIRING_SITE.startswith("main.py")
    for surface in ("reflex_network_share", "blend_reflex_control", "last_reflex_mix"):
        assert hasattr(m, surface), f"missing integration surface: {surface}"
    m.filtered_x, m.filtered_y = 40.0, -40.0
    x, y, _ = m.blend_reflex_control(70, -70)
    reflex_share = (abs(70 - x) + abs(-70 - y)) / (abs(70 - 40.0) + abs(-70 + 40.0))
    assert reflex_share <= 1.0 - m.reflex_network_share + 1e-6, \
        "reflex share in the blended command exceeds (1 - network share)"
    assert abs(x - 70) >= m.reflex_network_share * abs(40.0 - 70.0) - 0.5


def test_reflex_blend_is_deterministic_and_bounded():
    """No unseeded RNG: identical inputs → identical outputs, stick range kept."""
    m = FlyModel(demo=True, seed=64)
    m.filtered_x, m.filtered_y = 500.0, -500.0        # out-of-range LIF decode
    first = [m.blend_reflex_control(70, -70) for _ in range(5)]
    assert all(v == first[0] for v in first), "blend is not deterministic"
    x, y, _ = first[0]
    assert -80 <= x <= 80 and -80 <= y <= 80, "blend left the SM64 stick range"


def test_no_unseeded_rng_in_the_motor_path():
    """Hard constraint: the new feedback/expiry paths add no RNG.

    Two models with the same seed must produce identical pool spikes, and the
    new state (occupancy EWMA, reflex stamps, auxiliary budget) must be
    reproducible.
    """
    a = _model(mb=0.5, escape=True, stuck=806.8)
    b = _model(mb=0.5, escape=True, stuck=806.8)
    for _ in range(60):
        a.reflex_forward = 70
        b.reflex_forward = 70
        a.step(DARK)
        b.step(DARK)
    np.testing.assert_array_equal(a.spikes, b.spikes)
    assert a._fwd_occupancy == pytest.approx(b._fwd_occupancy)
    assert a._fwd_aux_used == pytest.approx(b._fwd_aux_used)
    assert a._reflex_stamp == b._reflex_stamp
