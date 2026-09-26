# Execution Plan v3 (Corrected)

> **Revision date**: 2026-09-23
> **Prioritized tasks** based on the corrected current state analysis. All claims verified against actual on-disk codebase.
>
> ⚠️ **Key corrections vs initial analysis**: `fix_executor.py` now HAS apply methods (5 `_do_*` methods). `encode_color` and `compute_small_targets` ARE tested. Only `encode_on_off` has truly zero coverage.

---

## P0 — Critical

### P0-1: Implement automated `verify()` in `fix_executor.py`

**What**: Add a `verify(fix_entry, fix_catalog)` method to `FixExecutor` that confirms a fix was correctly applied and the triggering pattern no longer fires.

**Current state**: `fix_executor.py` has 5 `_do_*` apply methods and `rollback()`, but `verify` is only an advisory heuristic (classifies `# Verify <topic> in <file>` as manual action).

**Implementation outline**:
1. `verify(fix_id, pattern_id, fix_catalog)`: Look up the fix entry, re-read affected file(s), confirm text changes are present, optionally re-run the pattern's diagnosis check
2. Return `FixVerificationReport`: `fix_id`, `applied` (bool), `file_check` (each file state), `pattern_cleared` (optional)
3. Wire into `evolution_skill.py` Fix phase (line 2482): after `self.fix_executor.execute()`, call `self.fix_executor.verify()` and log

**Effort**: 1d
**Expected outcome**: EVO pipeline Phase ④ becomes automated.

### P0-2: Wire `fix_template_interpreter.py` into EVO pipeline

**What**: Connect `interpret_and_execute()` into `evolution_skill.py`.

**Current state**: `fix_template_interpreter.py` (710 lines) is fully functional with `interpret()`, `interpret_and_execute()`, `rewrite()`. `evolution_skill.py` calls `FixExecutor.execute()` directly at line 2482 and **never imports** `fix_template_interpreter`.

**Implementation outline**:
1. Import `interpret_and_execute` or `FixTemplateInterpreter` in `evolution_skill.py`
2. At the Fix phase (~line 2479), offer configurable path: `FixExecutor.execute()` for well-formed directives, `interpret_and_execute()` for NL templates
3. Consolidate `parse_fix_template` (duplicated in both modules) — see P1-1

**Effort**: 0.5-1d
**Expected outcome**: FixTemplateInterpreter becomes a live EVO pipeline component.

### P0-3: Add tests for `encode_on_off(atlas)`

**What**: Write tests for `retina.encode_on_off()` — **zero direct test coverage**, feeds all downstream motion detection.

**Test cases** (add to `test_retina.py`):

| Test | Verifies |
|------|----------|
| ON transient from bright input | Positive signal on positive contrast |
| OFF transient from dark input | Positive signal on negative contrast |
| Zero response from uniform input | No change = no transient |
| ON and OFF are complementary | ON increases where OFF decreases |
| Output shape matches input | Dimensional correctness |

**Effort**: 0.5d
**Expected outcome**: The single remaining retina coverage hole is closed.

---

## P1 — High

### P1-1: Consolidate duplicate `parse_fix_template`

**What**: Eliminate duplicate parsing between `fix_executor.py` (line 290, `parse_fix_template()`) and `fix_template_interpreter.py` (its own `parse_extended_directives`).

**Implementation**: Single `FixTemplateParser` → import in both modules. Deprecate standalone `parse_fix_template()` with backward compat wrapper.

**Effort**: 0.5d
**Depends**: P0-2

### P1-2: Direct tests for `edge_orientation(atlas)`

**What**: Add 3-4 tests for `retina.edge_orientation()` — currently only indirectly tested via `compute_flow`.

**Test cases**: Vertical edge, horizontal edge, diagonal classification, confidence scoring.

**Effort**: 0.5d

### P1-3: Profile test collection time (5.76s)

**What**: Investigate 5.76s pytest collection at 94 files / 1,327 tests. Not urgent, worth monitoring baseline.

**Effort**: 0.5d

---

## P2 — Medium

| ID | Task | Effort |
|----|------|--------|
| P2-1 | Document `compute_small_targets` coverage (extensively tested in `test_p2_kpi.py`, missing from `test_retina.py`) | 0.25d |
| P2-2 | Review test file sprawl (94 files) for consolidation | 0.5d |

---

## Summary

| ID | Task | Prio | Effort | Depends | Outcome |
|----|------|------|--------|---------|---------|
| P0-1 | `verify()` in `fix_executor.py` | 🔴 | 1d | — | Phase ④ automated |
| P0-2 | Wire interpreter into EVO | 🔴 | 0.5-1d | — | Dead code activated |
| P0-3 | Tests for `encode_on_off()` | 🔴 | 0.5d | — | Last retina gap |
| P1-1 | Consolidate `parse_fix_template` | 🟡 | 0.5d | P0-2 | Single parser |
| P1-2 | Tests for `edge_orientation()` | 🟡 | 0.5d | — | Direct coverage |
| P1-3 | Profile collection time | 🟡 | 0.5d | — | Monitor growth |

**Total**: ~4d. **Parallelize**: P0-1 + P0-2 + P0-3 simultaneously → P1-1 + P1-2 → P1-3.