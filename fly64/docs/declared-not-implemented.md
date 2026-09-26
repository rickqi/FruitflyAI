# Declared but not implemented — decision register

> **Generated** by `scripts/build_unimplemented_register.py` from the audit
> tools.  Do not hand-edit: re-run the script after changing a baseline, the
> tunable schema, or the motor-injection audit.  Record a decision in the
> `Decision` column by editing the *source* audit (a baseline entry's `note`,
> a schema `wired` flag), then regenerate.

Each row is something the project **declares** (a test asserts it, a schema
advertises it, an invariant demands it) that **no code implements**.  They
were each found by a separate investigation; the point of this file is that
each is decided ONCE — *implement* or *formally retire* — instead of being
rediscovered, re-argued and worked around.

Sources: `known_failures.win32.json` (aspirational tests), `skills/brain_tunable_params.json`
(`wired: false`), `scripts/audit_motor_injections.py` (architecture).

---

## 1. Tests asserting unimplemented features — 16 entries

| test file | # | what is declared | evidence | Decision |
|---|---|---|---|---|
| `tests/test_what_i_see_protocol.py` | 10 | test_build_request_with_scene_context | ENHANCED_PROMPT_TEMPLATE / build_consult_request(SceneContext) / StrategyWriter(scene_tags) / parse_response(semantic_level) do not exist in plugin/ll | _implement / retire_ |
| `tests/test_mbon_saturation.py` | 5 | test_absolute_override_at_095 | _saturation_recovery_counter / _saturation_recovered appear NOWHERE in fly64|plugin|skills; MushroomBody has a different mechanism (_saturation_frames | _implement / retire_ |
| `tests/test_invariants.py` | 1 | test_no_visual_motor_shortcut | architectural invariant violated by design: fly64/model.py injects current into motor pools from 66 sites (79%% guarded, 7 visually gated). Measured b | _implement / retire_ |

## 2. Unwired tunable parameters — 0 entries

Advertised by `skills/brain_tunable_params.json`; since EVO-066 the panel
renders them disabled and Phase 6 excludes them from its search.  Each needs a
real consumer before `wired` may be set to `true` (a guard test enforces it).

| parameter | declared range | default | documented intent | Decision |
|---|---|---|---|---|

## 2b. Closed decisions — hand-maintained (survives only if re-added)

> The generator above emits only items still **awaiting** a decision, so a row
> that is implemented simply disappears from it.  Those disappearances are
> recorded here by hand with the evidence that closed them.  Re-running
> `scripts/build_unimplemented_register.py` overwrites this section — copy it
> back, or teach the generator to emit closed items (out of scope of the
> RULE-19 repair that wrote this).

| parameter | status | unit contract | reader | PIN |
|---|---|---|---|---|
| `exploration.gate_forward_threshold` | **implemented** (`wired: true`, live reader — regeneration dropped it from the §2 unwired list) | **Hz**, `0.4 .. 8.0`, default `2.0` | `fly64/fly64/main.py` — `rate_per_tick_to_hz()` + `gate_open_hz()` (flow.json: `forward_rate_hz`, `gate_forward_threshold_hz`, `gate_forward`) | `tests/test_gate_units.py` |
| `exploration.gate_jump_threshold` | **implemented** (`wired: true`, live reader — regeneration dropped it from the §2 unwired list) | P0-a8: **ratio (dimensionless)**, `0.25 .. 4.0`, default `0.75` (migrated from Hz; see contract_registry.json `ratio_threshold_unit`) | same reader (flow.json: `jump_rate_hz`, `gate_jump_threshold_hz`, `gate_jump`) | `tests/test_gate_units.py` |

**RULE-19 unit contract (8th case of the "declared unit ≠ consumed unit"
family).** `Control.forward_rate / turn_rate / jump_rate` are **per-tick**
firing fractions of a 13-tick (≈ 250 ms) motor-pool window
(`fly64/fly64/model.py:1912-1916`), so `0.0 ≤ rate ≤ 1.0`.  The dashboard
telemetry reports the *same* pool quantity in **Hz**
(`telemetry.py:77-78`: window count ÷ `ticks · dt`), and the schema above
declares `gate_forward_threshold` in **Hz** — the pre-repair readers compared the
raw per-tick fraction against the Hz threshold
(`control.jump_rate > 2.0`, `control.forward_rate > 0.4`), which made
`gate_jump` mathematically unreachable: the observed maximum is `1.0`
(0.276/tick = 13.8 Hz measured), so the gate was permanently `False` whatever
EVO sampled from the declared range; `gate_forward` looked healthy only
because the forward pool happened to be saturated (0.923/tick = 46.15 Hz).
The repair converts the observed rate to Hz exactly once
(`rate_per_tick_to_hz(rate, model.dt)`, the same 1/dt the dashboard uses) and
compares Hz against Hz in `gate_open_hz()`, whose boundary is **closed**
(observed == threshold → `False`).  Defaults are calibrated against the
model's own decode references, not against the test: `2.0 Hz` ≈ the forward
decode's full-drive point (`raw_y` clip at `0.043/tick`).

**P0-a8 migration:** `gate_jump_threshold` changed unit from Hz to **ratio
(dimensionless)** — the behavioral comparison becomes `jump_rate / max(forward_rate, FWD_RATIO_FLOOR) > r`
where `FWD_RATIO_FLOOR = 0.008`, `r ∈ [0.25, 4.0]`, default `0.75` (P1-b3).
The key is reused; the Hz-era register entry and unit-contract tests are
updated to ratio semantics.
the jump decoder's own trigger (`jump_rate > 0.04/tick` = `2.0 Hz`,
`model.py:2138`), with the registry maxima (`8.0` / `20.0 Hz`) kept below the
Nyquist rate `1/dt = 50 Hz` so a declared threshold stays reachable.

## 3. Architectural aspirations

### 3.1 `test_no_visual_motor_shortcut` — 66 motor-pool injection sites

The test asserts that with the connectome zeroed, a black frame and a white
frame produce **identical** motor commands.  Measured (EVO-071): they differ
from tick 2, and disabling the two documented sensory gates does not change
that — because with the connectome zeroed those direct injections are the
only path.

| measure | value |
|---|---|
| motor-pool injection sites in `fly64/model.py` | 66 |
| conditionally guarded (decided by a Python branch) | 52 (79%) |
| gated on a visual feature | 7 (11%) |

Visually gated sites:

- `model.py:1716` → `self.jump_nodes` via `tau`
- `model.py:1738` → `self.jump_nodes` via `sky_score`
- `model.py:1840` → `self.forward` via `cliff_confirmed, cliff_tangent_bias`
- `model.py:1749` → `self.turn_left` via `opening_asymmetry, opening_score`
- `model.py:1837` → `self.turn_right` via `cliff_confirmed, cliff_tangent_bias`
- `model.py:1839` → `self.turn_left` via `cliff_confirmed, cliff_tangent_bias`
- `model.py:1751` → `self.turn_right` via `opening_asymmetry, opening_score`

**The honest framing**: P1 "neural takeover" retired some symbolic
branches, but 66 direct injections remain and 52 of them are decided by a
condition.  Either the invariant is retired as too strong (the documented
sensory-gate design is intentional), or the injections are progressively
replaced by network-resolved competition.
Decision: _retire invariant / continue takeover_.

---

## Summary

| source | entries |
|---|---|
| aspirational tests | 16 |
| unwired tunable parameters | 0 |
| architectural aspirations | 1 |
| **total awaiting a decision** | **17** |

Note: this register deliberately lists only things with **zero**
implementation.  Partially implemented items (e.g. the 3 `test-drift` and the
remaining `real-bug` entries in the verification baseline) are tracked
separately by `scripts/check_regressions.py`.
