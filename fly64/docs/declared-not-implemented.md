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

## 2. Unwired tunable parameters — 14 entries

Advertised by `skills/brain_tunable_params.json`; since EVO-066 the panel
renders them disabled and Phase 6 excludes them from its search.  Each needs a
real consumer before `wired` may be set to `true` (a guard test enforces it).

| parameter | declared range | default | documented intent | Decision |
|---|---|---|---|---|
| `escape.commit_reinforce` | 0.05 .. 0.3 | 0.15 | Current injected into the committed turn direction during escape. Higher = stronger directional commitment. | _implement / retire_ |
| `escape.commit_suppress` | 0.02 .. 0.25 | 0.1 | Current injected to suppress the opposite turn direction during escape commitment. | _implement / retire_ |
| `escape.forward_accum_step` | 0.001 .. 0.02 | 0.005 | Per-frame increment of adaptive forward gain when displacement is near-zero. | _implement / retire_ |
| `exploration.breakout_forward_bias` | 0.2 .. 1.0 | 0.7 | Fraction of forward drive during escape behavior (vs. turning). Higher = straighter breakout runs. | _implement / retire_ |
| `exploration.cliff_tangent_gain` | 0.0 .. 3.0 | 1.0 | How strongly the cliff tangent bias influences turn pools. 0 = disable detour, 3 = strong swerve. | _implement / retire_ |
| `exploration.dopamine_revisit_cost` | 0.0 .. 1.0 | 0.5 | Dopamine punishment threshold for revisit_penalty. Higher = MB learns faster to avoid loops. | _implement / retire_ |
| `exploration.gate_forward_threshold` | 0.1 .. 0.8 | 0.4 | Forward pool firing rate gate (Hz). Lower = easier to trigger forward motion. | _implement / retire_ |
| `exploration.gate_jump_threshold` | 0.5 .. 4.0 | 2.0 | Jump pool firing rate gate (Hz). Lower = jump triggers more easily. | _implement / retire_ |
| `exploration.loop_breakout_threshold` | 0.3 .. 0.95 | 0.6 | loop_score above this activates forced escape behavior when stuck. Lower = escape from milder loops. | _implement / retire_ |
| `exploration.revisit_penalty_scale` | 0.0 .. 0.8 | 0.4 | Weight of revisit_penalty in health_score. Higher = more aggressive avoidance of familiar ground. | _implement / retire_ |
| `exploration.stuck_ramp_cooldown` | 1.0 .. 15.0 | 5.0 | Seconds stuck_ramp reflex stays suppressed after firing. Longer = less reflex thrashing. | _implement / retire_ |
| `exploration.visual_gain_novelty_boost` | -0.2 .. 0.5 | 0.1 | Sensor gain boost per unit novelty (applied at model.step). Positive = stronger response to novel visual input | _implement / retire_ |
| `reflex.adaptive_cooldown_scale` | 0.01 .. 0.15 | 0.05 | Cooldown reduction per second stuck (adaptive cooldown formula). Higher = reflexes fire faster as stuck persis | _implement / retire_ |
| `reflex.cooldown_min` | 0.5 .. 5.0 | 2.0 | Minimum reflex cooldown duration in seconds. Lower = faster re-trigger but more thrashing. | _implement / retire_ |

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

- `model.py:1699` → `self.jump_nodes` via `tau`
- `model.py:1721` → `self.jump_nodes` via `sky_score`
- `model.py:1823` → `self.forward` via `cliff_confirmed, cliff_tangent_bias`
- `model.py:1732` → `self.turn_left` via `opening_asymmetry, opening_score`
- `model.py:1820` → `self.turn_right` via `cliff_confirmed, cliff_tangent_bias`
- `model.py:1822` → `self.turn_left` via `cliff_confirmed, cliff_tangent_bias`
- `model.py:1734` → `self.turn_right` via `opening_asymmetry, opening_score`

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
| unwired tunable parameters | 14 |
| architectural aspirations | 1 |
| **total awaiting a decision** | **31** |

Note: this register deliberately lists only things with **zero**
implementation.  Partially implemented items (e.g. the 3 `test-drift` and the
remaining `real-bug` entries in the verification baseline) are tracked
separately by `scripts/check_regressions.py`.
