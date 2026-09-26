# Current State Analysis v3

> **Revision date**: 2026-09-23
> **Overview**: Systematic analysis of three critical gaps in the Fly64 project: EVO auto-fix pipeline effectiveness (Problem 1), visual coverage stagnation (Problem 3), and test suite growth management (Problem 4).
>
> ⚠️ **Revised against actual on-disk codebase**. Some earlier findings have been superseded by commits merged since the initial investigation.

---

## Delta Summary: What Changed Since Initial Analysis

| Claim in Initial Analysis | Current State (2026-09-23) | Verdict |
|---|---|---|
| `fix_executor.py` missing `apply_fix`/`verify` | `apply_fix` now has 5 `_do_*` methods; `verify` is advisory-only heuristic | **Partial fix — apply works, verify still missing** |
| Fix catalog: 19 fixes, 0 effective, 11 ineffective, 8 reverted | 19 fixes, **2 effective** (fix_0010: 0.0068, fix_0012: 0.0218), **0 reverted** | **Improved** |
| 8 retina methods with zero coverage | **Only `encode_on_off` has zero coverage**. `encode_color` tested via `test_brain_alternation.py`; `compute_small_targets` via `test_p2_kpi.py` (15+ calls); EMD/HRC/flow/terrain via `test_emd.py` (18), `test_optic_flow.py` (41), `test_retina_calibration.py` (26) | **Significantly improved** |
| 92 test files, 1,278 tests | **94 test files, 1,327 tests** | **Evolved** |
| `known_failures.json` deleted | **`known_failures.win32.json` exists** | **Restored** |

---

## 1. EVO Auto-Fix Pipeline Gap (Problem 1)

### 1.1 Metrics

| Metric | Previous | Current |
|--------|----------|---------|
| Total fixes | 19 | 19 |
| **Effective (score > 0)** | **0** | **2** (fix_0010: 0.0068, fix_0012: 0.0218) |
| Ineffective (score = 0/null) | 11 | 17 |
| Reverted | 8 | **0** |

### 1.2 Fix Executor Engine — Current State

`fix_executor.py` (867 lines) now has a **complete execution engine**:

| Method | Line | Status |
|--------|------|--------|
| `execute()` | 438 | ✅ Parses directives, dispatches to action methods |
| `execute_all()` | 542 | ✅ Batch execution with catalog recording |
| `rollback()` | 572 | ✅ Per-file backup restoration |
| `_do_replace()` | 642 | ✅ Replace text in file |
| `_do_change()` | 680 | ✅ Synonym for replace |
| `_do_insert_after()` | 721 | ✅ Insert after anchor line |
| `_do_insert_before()` | 775 | ✅ Insert before anchor line |
| `_do_append()` | 825 | ✅ Append to end of file |
| `auto_fix_findings()` | 859 | ✅ Standalone convenience function |

### 1.3 The Critical Gap: No Automated `verify()`

The only `verify` logic in `fix_executor.py` is a **parsing heuristic** (lines 354-384) that classifies `# Verify <topic> in <file>` directives as **advisory** (manual action needed). There is **no method** that:

- ✅ Confirms the fix was correctly applied
- ❌ Re-checks the pattern condition to verify it no longer triggers
- ❌ Measures effectiveness programmatically after auto-apply

**Impact**: The pipeline can auto-apply fixes (Phase ③ works) but cannot confirm they succeeded or measure their effect (Phase ④ is manual-only).

### 1.4 FixTemplateInterpreter — New, Not Wired

`fix_template_interpreter.py` (710 lines) — **NEW**:

| Method | Status |
|--------|--------|
| `FixTemplateInterpreter.interpret()` | ✅ Works standalone |
| `interpret_and_execute()` | ✅ Combines interpretation + execution |
| `interpret_fix_template()` | ✅ Standalone convenience |

**Key finding**: `fix_template_interpreter.py` is **NOT imported or called** by `evolution_skill.py`. The EVO pipeline uses `FixExecutor.execute()` directly at line 2482, completely bypassing the interpreter.

**Duplication issue**: Both `fix_executor.py` (line 290) and `fix_template_interpreter.py` (line ~70) have their own fix template parsing logic — risk of divergence.

### 1.5 Pipeline State (Updated)

| Phase | Component | Status |
|-------|-----------|--------|
| ① Monitor | DataCollector | ✅ |
| ② Diagnose | DiagnosisEngine + PatternCatalog | ✅ 15 patterns |
| ③ Fix | FixExecutor.execute() + FixCatalog | ✅ **Auto-apply works** |
| ④ Verify | Advisory-only heuristic | ❌ **Not automated** |
| ⑤ Document | SelfDocumenter | ✅ |

---

## 2. Visual Coverage (Problem 3)

### 2.1 Retina Method Coverage — Corrected

| Method | Line | Tests | Coverage Vehicle | Status |
|--------|------|-------|-------------------|--------|
| `encode_on_off(atlas)` | 460 | **0** | — | ❌ **Critical gap** |
| `compute_emd(on, off)` | 516 | 18 | `test_emd.py` | ✅ |
| `compute_hrc(lum)` | 554 | 5+ | `test_retina.py` | ✅ |
| `compute_small_targets(on, off)` | 671 | ~15+ calls | `test_p2_kpi.py` | ✅ |
| `encode_color(atlas)` | 837 | 2 | `test_brain_alternation.py` | ✅ |
| `edge_orientation(atlas)` | 953 | Indirect only | via `compute_flow` | ⚠️ |
| `compute_flow(atlas)` | 994 | 41 | `test_optic_flow.py` | ✅ |
| `classify_terrain(...)` | 1457 | Integrated | `test_optic_flow.py` | ✅ |

### 2.2 Critical Gap: `encode_on_off`

`encode_on_off` (line 460) is the **entry point** for the retinal ON/OFF pathway. It generates transient signals that feed:
- `compute_emd()` — EMD motion detection
- `compute_small_targets()` — small target detection

**If `encode_on_off` has a bug, all downstream functions silently degrade.**

### 2.3 Test File Coverage Map

| Test File | Tests | Domain | Status |
|-----------|-------|--------|--------|
| `test_retina.py` | 16 | HRC, flow, terrain | ⚠️ Legacy |
| `test_retina_calibration.py` | 26 | Geometry, FOV, sectors | ✅ New |
| `test_emd.py` | 18 | EMD 4-direction, opponent | ✅ New |
| `test_optic_flow.py` | 41 | Flow, terrain, self-motion | ✅ New |
| **Total retina-adjacent** | **101+** | | **↑ from ~16** |

### 2.4 Comparison: Mushroom Body vs Retina

| Module | Tests | Test Density | Trend |
|--------|-------|-------------|-------|
| `mushroom_body.py` (406 lines) | 33 tests | 3.3 tests/100 lines | Stable |
| `retina.py` (~1,269 lines) | **101+** (6 files) | 8.0 tests/100 lines | **Rapidly improving** |

---

## 3. Test Suite Growth (Problem 4)

### 3.1 Metrics

| Metric | Previous | Current |
|--------|----------|---------|
| Test files | 92 | **94** |
| Test functions | 1,278 | **1,327** |
| Collection time | 5.80s | **5.76s** |

**Growth rate**: +49 tests across ~30 commits = 1.6 tests/commit. Collection time stable.

### 3.2 Regression Baseline Restored

`known_failures.win32.json` exists with structured entries (`platform`, `recorded_at`, `count`, `entries`). `check_regressions.py` can now distinguish new failures from baseline.

### 3.3 New Test Files Since Initial Analysis

| File | Tests | Purpose |
|------|-------|---------|
| `test_fix_template_interpreter.py` | 33 | FixTemplateInterpreter lifecycle |
| `test_emd.py` | 18 | EMD four-direction motion |
| `test_optic_flow.py` | 41 | Flow, terrain, self-motion, memory |
| `test_retina_calibration.py` | 26 | Retina geometry, FOV, sectors |
| `test_plugin_mhr.py` | 46 | Plugin MHR module |

---

## 4. Corrected Execution Priorities

| Priority | Task | Rationale |
|----------|------|-----------|
| **P0** | `fix_executor.py`: Implement automated `verify()` method | Last remaining gap in EVO pipeline; apply already works |
| **P0** | Wire `fix_template_interpreter.py` into `evolution_skill.py` | Currently dead code — never called by the EVO pipeline |
| **P0** | Add tests for `encode_on_off(atlas)` | Zero coverage; feeds all downstream motion detection |
| **P1** | Consolidate duplicate `parse_fix_template` (fix_executor vs fix_template_interpreter) | Two implementations risk divergence |
| **P1** | Add direct tests for `edge_orientation(atlas)` | Currently only indirect coverage via compute_flow |
| **P1** | Profile 5.76s collection time | Manageable now, worth monitoring |
| **P2** | `compute_small_targets` edge case tests | Already well-covered, formal documentation only |