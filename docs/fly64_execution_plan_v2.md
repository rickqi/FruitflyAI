# Fly64 下一步执行计划 v2

> **取代关系（取代声明）**
> 本文件 `docs/fly64_execution_plan_v2.md` **取代** 既存 `docs/fly64_execution_plan.md`（676 行，实测，2026-09-20 之前撰写）。
> 既存文件**保留为历史版本，不删除、不修改**，仅供追溯；其全部结论以本文件为准。
> 本文件同时**取代** `docs/fly64_export_logs_analysis_report.md` 第 5 节的 12 项行动表（该表为 2026-09-17/09-18 快照，多个数字已过期）。

> **事实基准**：本文件的每一个数字均来自
> `docs/analysis/plan-v2/00-facts.md`（T0，788 行，全部带命令+原始输出）
> 与 `docs/analysis/plan-v2/01-reconciliation.md`（T1，435 行，32 条论断核对 + 8 项基础设施）。
> 未在实测中确认的数字一律标注「未验证」，不做外推。
>
> **范围声明**：本文件 = 文档与审计产物，**不含代码实现**。所有「实施步骤」是给执行者的施工说明，本轮不落地。
>
> **采集时点**：2026-09-20，Windows / `sys.platform = win32`。
> **解释器（全文统一）**：`D:\codes\flygym\.venv\Scripts\python.exe`（Python 3.11.9）。
> **路径约定（关键，两套并存，务必分清）**：
> 1. **正文叙述 / 表格 / 附录**中的路径写成「**相对仓库根**」（如 `fly64/tests/…`、`fly64/scripts/…`）。
> 2. **代码块内的命令**中出现的 `scripts\…`、`tests\…`、`skills\…`、`web\…` 按「**相对 `fly64/`**」解析，
>    因为下一行的「命令约定」已把命令块 `cwd` 固定为 `D:\codes\flygym\fly64`。
> ⚠️ 两条规则**不可互换**：把 §1 的写法直接复制进 `cwd=fly64/` 的终端的 `scripts\…` 位置，或把终端的 `scripts\…`
> 拿到仓库根执行，都会 `FileNotFoundError`。复制命令时**必须连同 `# cwd = …` 注释行一起复制**。
> **命令约定**：除显式标注 `# cwd = <repo root>` 者外，所有命令的 `cwd` 为 `D:\codes\flygym\fly64`，
> 即所有命令块都先用 `cd D:\codes\flygym\fly64` 建立上下文。

---

## 0. 当前状态（实测基线）与对报告数字的取代

### 0.1 实测基线表

| 指标 | **实测真值** | 命令（可复制） | 报告 / 旧执行计划的写法 | 取代结论 |
|---|---|---|---|---|
| `BRAIN_VERSION` | **`"2.23.11"`** @ `fly64/fly64/main.py:39`（注释 `R31-fix12`） | `Select-String -Path fly64\fly64\main.py -Pattern '^BRAIN_VERSION'` | 报告 L4/L149 = **2.23.6**；旧执行计划 L4 = 2.23.11（对） | **取代为 2.23.11** |
| 版本同步状态 | `fly64/skills/skills.md:3` = **2.23.7**、`:70` = **2.23.10**；`evolution_history.json` `canonical_versions.brain` = **2.23.6** → **同一仓库 4 种声明** | `Select-String -Path fly64\skills\skills.md -Pattern 'BRAIN_VERSION \*\*'` | 报告未提及 | **新增为已知缺陷（见行动 2 / 风险 R-02）** |
| 未记录版本数 | `2.23.7 / 2.23.8 / 2.23.9 / 2.23.10 / 2.23.11` 在 `evolution_history.json` 中 **零记录**（≥5 个） | `fly64/skills/evolution_history.json` 中 `brain_version` **语义最大值 = `2.23.6`**（⚠️ 排除 3 条字面量 `"None"`；字典序 `max()` 会返回 `"None"`/`2.9.1`，须按 `(major,minor,patch)` 排序，见 §0.2 命令） | 报告暗示 79 条记录已覆盖到最新 | **取代：agent.md 规则 15 当前不成立** |
| git HEAD | `1badb4072d27116a967bfaa3dd1d614c133881b9`（`master` → `origin/master`，`git describe` = `causal-baseline-241-g1badb40`，305 commits，HEAD 时间 2026-09-20 18:21:21 +0800） | `git rev-parse HEAD; git rev-parse --abbrev-ref HEAD; git describe --tags --always; git rev-list --count HEAD` | 报告未声明 | **新增为首手基线（全文验收以此为锚）** |
| 未提交改动数（**测试执行前**） | **3**（全部为未跟踪：`?? .omo/`、`?? docs/fly64_execution_plan.md`、`?? docs/fly64_export_logs_analysis_report.md`） | `git status --porcelain \| Measure-Object -Line` | 报告未声明 | **新增；引用时必须注明「测试执行前」** |
| 未提交改动数（**跑一次 pytest 后**） | **115**（M=45 / D=66 / ??=4），因 `fly64/.pytest-run/` 有 **132 个文件被 git 跟踪** | 见 0.3 | 报告未声明 | **新增：影响所有「以 git 干净度作证据」的验收** |
| pytest 全量结果 | **38 failed, 929 passed, 36 skipped**（216.43 s） | `cd fly64; & $py scripts\check_regressions.py` | 报告 L226 = **~482 passed / 11 failed** | **取代为 929 / 38 / 36** |
| 回归门禁退出码 | **1**（原因 = 10 条 NEW failures，**不是** baseline 缺失、**不是**路径不符） | 同上，输出首行 `(baseline win32, 38 entries)` 证明 baseline 命中 | 报告 L249 标「✅」 | **取代为「工具就绪但当前为红」** |
| win32 基线 | `fly64/tests/known_failures.win32.json`，`count = len(entries) = 38`；`aspirational 16 / environment 14 / test-drift 3 / real-bug 2 / unknown 3` | 见 0.2 | 报告 L170/L228/L252 = **36 条（13 env）** | **取代为 38 条 / env 14** |
| linux 基线 | `fly64/tests/known_failures.linux.json`，`count = len(entries) = 24`；`aspirational 16 / environment 1 / live-state 2 / test-drift 3 / unknown 2` | 见 0.2 | 报告未给 linux 值 | **新增** |
| 两平台交集 | 交集 22；win32-only 16；linux-only 2 | 见 0.2 | 报告未给 | **新增** |
| 基线文件名 | **`fly64/tests/known_failures.{win32,linux}.json`**（平台作用域双文件）；未限定名 `fly64/tests/known_failures.json` **不存在** | `Test-Path fly64\tests\known_failures.json` → `False` | 报告 L228/L249 写 `tests/known_failures.json`；旧执行计划 P2-9 **文件名正确** | **取代为平台作用域双文件** |
| `main.py` 直接写 `control` | **36 行 / 36 处赋值**（KPI 预算 `26`）→ **超标 10**；测试实测 **FAIL** | 见行动 8 | 报告 L167/L236/L286 = **35→12 处 / ~12 处** | **取代为 36（起点） / 目标 ≤26** |
| `agent.md` 行数 | **1360**（117938 bytes，全 LF，无 BOM） | `& $py -c "from pathlib import Path;print(len(Path('agent.md').read_bytes().decode('utf-8').splitlines()))"` | 报告 L4 = 1360（**正确**） | **保持一致**；⚠️ PowerShell `Get-Content` 给 921 属工具假象 |
| evolution 记录 | **79 条** records，**51** 个唯一 `brain_version` 字面量（含 3 条字面量 `"None"` → 语义唯一 **50**） | 见 0.2 | 报告 L4/L149 = 79 / 51 | **保持一致**（语义值用 50） |
| 报告/旧计划自身行数 | 报告 **314** 行；旧执行计划 **676** 行 | Python `splitlines()` | 任务描述写 670 | **取代为 676** |
| 契约审计输出 | `audit_contract_pairs.py` exit **0**，`TOTAL dead-writes + silent-defaults: 8` | `cd fly64; & $py scripts\audit_contract_pairs.py` | 报告未给数 | **新增为首手基线** |
| 双环度量 | `measure_evolution_health.py --json` exit 0：phase6 `trials_unique 68 / commits 1 / rollbacks 67 / commit_rate 0.0147 / inert_fraction 0.6667`；p44 `usable_for_signature 0 / signature_reuse_rate 0.0` | `cd fly64; & $py scripts\measure_evolution_health.py --json` | 报告未给数 | **新增为首手基线** |
| `evolution_health_trend.jsonl` | **仅 1 行**（2026-09-18T07:11:59Z） | `(Get-Content fly64\skills\evolution_health_trend.jsonl \| Measure-Object -Line).Lines` | 报告未提及 | **新增：行动 10「排行榜」无数据基础** |
| Playwright | **未安装**（`.venv` 无 `playwright`） | `& $py -c "import importlib.util as u; print(bool(u.find_spec('playwright')))"` → `False` | 报告未提及 | **新增：行动 12 有额外前置** |

### 0.2 基线统计一键复核（复制即用）

> **⚠️ Windows 注意**：PowerShell 5.1 的 `@'…'@` here-string 向原生程序传参时会剥离双引号，导致 Python `SyntaxError`。
> 以下使用 `Set-Content -Encoding utf8` 写入临时文件绕开——**无需管理员权限**，不会污染仓库（`%TEMP%` 在仓库外）。

```powershell
# cwd = D:\codes\flygym
$py = "D:\codes\flygym\.venv\Scripts\python.exe"
$env:PYTHONIOENCODING = "utf-8"

# 写临时脚本 → 执行 → 清理（基线条数与 cause 分布 + 跨平台交集）
$script = @'
import json, collections
sets = {}
for f in ("fly64/tests/known_failures.win32.json", "fly64/tests/known_failures.linux.json"):
    d = json.load(open(f, encoding="utf-8"))
    ids = {e["id"] for e in d["entries"]}
    sets[d["platform"]] = ids
    print(f, "count=", d["count"], "len=", len(d["entries"]), "unique=", len(ids))
    print("   causes:", dict(collections.Counter(e["cause"] for e in d["entries"])))
w, l = sets["win32"], sets["linux"]
print("intersection:", len(w & l), "win32-only:", len(w - l), "linux-only:", len(l - w))
'@
Set-Content -Path "$env:TEMP\_bl_check.py" -Value $script -Encoding utf8
& $py "$env:TEMP\_bl_check.py"; Remove-Item "$env:TEMP\_bl_check.py"

# 写临时脚本 → 执行 → 清理（evolution 记录数与唯一脑版本）
$script = @'
import json, re
d = json.load(open("fly64/skills/evolution_history.json", encoding="utf-8"))
r = d["records"]
vals = [str(x.get("brain_version")) for x in r]
sem = [v for v in vals if re.fullmatch(r"\d+\.\d+\.\d+", v)]          # 排除字面量 "None" 与 "x" 形式
key = lambda v: tuple(int(p) for p in v.split("."))
print("records:", len(r))
print("unique brain_version (literal):", len(set(vals)))
print("literal 'None' records:", vals.count("None"))
print("semantic max brain_version:", max(sem, key=key) if sem else None)
print("records >= 2.23.7 present:", sorted({v for v in sem if key(v) >= (2, 23, 7)}))
'@
Set-Content -Path "$env:TEMP\_bl_evo.py" -Value $script -Encoding utf8
& $py "$env:TEMP\_bl_evo.py"; Remove-Item "$env:TEMP\_bl_evo.py"
```

### 0.3 工作树污染实测（**所有「跑测试」类验收的前置**）

```powershell
# cwd = D:\codes\flygym
git ls-files fly64/.pytest-run | Measure-Object -Line      # → 132（被跟踪！）
git check-ignore -v fly64/.pytest-run                      # → rc=1（未被忽略）
git status --porcelain | Measure-Object -Line              # 执行 pytest 前 3 → 执行后 115
```

* `fly64/.gitignore` 忽略 `.venv/ .cache/ runtime/ artifacts/ private/ rom/ *.z64 *.n64 *.v64 __pycache__/ .pytest_cache/ .DS_Store`，**不含 `.pytest-run/`**。
* 结论：**任何以 `git status` 干净度或 `git diff` 内容为证据的验收，在当前仓库状态下不可复现**。
  本文件每个涉及 pytest 的行动，其验收命令都附「污染处理」四行（见 §4.1 模板）。

### 0.4 对报告已过期数字的取代清单（逐条）

| # | 报告位置 | 报告写法 | **本计划采用值** |
|---|---|---|---|
| S1 | L4 / L149 | Brain v2.23.6（最新） | **2.23.11** |
| S2 | L226 | ~482 通过 / 11 基线失败 | **929 passed / 38 failed / 36 skipped** |
| S3 | L170 / L228 / L252 | 基线 36 条（13 env） | **win32 38（env 14） / linux 24（env 1）** |
| S4 | L238 | 11 基线失败「均为 Windows 环境问题」 | **38 failed；其中 `environment` 仅 14，另有 `real-bug` 2 条真缺陷** |
| S5 | L294 | 基线 11 失败可根治 | **38 failed；其中 10 条为 NEW** |
| S6 | L167 / L236 / L286 | 写 control 35→12 处 / ~12 处 | **36 处（预算 26，超标 10）** |
| S7 | L228 / L249 | 基线文件 `tests/known_failures.json` | **`fly64/tests/known_failures.{win32,linux}.json`** |
| S8 | L4 / L21 | 7 个已导出会话 / 时间跨度至 09-20 | **10 个 zip / 9 个 session id**（未解包，未验证）；**`evolution_history.json` 无记录晚于 2026-09-18** |
| S9 | L107 | `gent.md` | **`agent.md`**（仓库根，1360 行） |
| S10 | L109–L147 版本表 | 34 个版本 | **断层**：漏 `2.14.0–2.21.1` 共 14 个真实版本（Motor-P1~P5+M1、v2.20.0 发布、t6 根因修复、R31-fix3~5）；引用演化轨迹一律以 `fly64/skills/evolution_history.json` 为准 |

### 0.5 旧执行计划（`docs/fly64_execution_plan.md`）的处置结论

旧计划的问题**不在数字**（其脑版本 2.23.11、基线 38/24 与文件名均正确），而在**围绕幻象 API 展开的修改步骤**：

| 旧计划条目 | 引用的不存在物 | 实测反证 | 本计划处置 |
|---|---|---|---|
| P0-1 | `SeqlockWatchdog.shutdown()`、`._state`、`SEQLOCK_HEALTHY/DEAD/ERROR`、`ShutdownBridge` | `bridge.py:56-83` 只有 `__init__/update/reset` 3 个方法；4 个符号全仓 **0 命中** | **删除**（该文档 L6-10 已自我否证，本次独立复核确认） |
| P0-2 | `bridge.control_written`；`audit_contract_pairs.py --mode trace --target control` | `control_written` **0 命中**；该命令实测 **exit 2**（`unrecognized arguments`） | **删除** |
| P0-3 | `MushroomBody.learn_from_outcome()`、`contract.emit()`、`@contract.on()`、`CoachContract` | 4 个符号全仓 **0 命中**（本次独立复核：含 `fly64/tests/` 在内的全 `fly64/` 树） | **重写** → 行动 4（改用真实入口 `model.scene_danger` → `DopamineGainController.compute`/`dopamine.bias` → `self.mushroom.set_dopamine`） |
| P1-4 | `SceneMemory.record_danger()`、`scene_recognition.py` 中的 `self.scene_memory.record_danger(...)` | `record_danger` **0 命中** | **重写** → 行动 4 |
| P1-6 | `fly64/plugin/evolution_logs.py`、`class EvolutionLogger` | 文件**不存在**；类名 **0 命中**（`fly64/plugin/` 实有 7 个 .py） | **删除**（最危险：易被当成「待修的真实模块」） |
| P2-7 | `CentralComplex.navigate_to_goal()`、`MemoryController.store_navigation_hint()/recall_navigation_hint()`、`bridge.inject_navigation()` | 4 个符号全仓 **0 命中** | **重写** → 行动 7（CX 回路**已实测在跑**，见行动 7） |
| P2-8 | `CoachContract`、`coach.contract.is_active()`、`coach.serialize()/deserialize()`、`scene_memory.set_danger()` | 全仓 **0 命中** | **重写** → 行动 9（改用真实资产 `fly64/tests/test_coach_contract.py`） |
| P3-11 | `pyproject.toml`、`.pre-commit-config.yaml` | 两者**均不存在**（`fly64/` 下有 `pytest.ini`，无 `pyproject.toml`；仓库根无 `.pre-commit-config.yaml`） | **重写** → 行动 3（挂到**实际存在**的 `.github/workflows/ci.yml`） |

**失效命令**（照抄必报错，本计划全部替换）：

| 旧命令 | 实测结果 | 本计划替代 |
|---|---|---|
| `python -m pytest fly64/tests/known_failures/ --collect-only` | `ERROR: file or directory not found`，**exit 4**（`known_failures` 不是目录） | 见行动 2 的 baseline 自检命令 |
| `python scripts/audit_contract_pairs.py --mode trace --target control` | **exit 2**，`unrecognized arguments`（真实 CLI 仅 `--json/--all`） | `& $py scripts\audit_contract_pairs.py --all` |
| `grep -rn 'print(' fly64/fly64/ fly64/plugin/ --include='*.py'` | Windows 默认 shell 无 `grep`；且 cwd 语义与文档其余命令不一致 | 用 DSH `grep` 工具，或 `Select-String -Path` |

**结构性问题（必须保留的历史教训）**：旧计划**丢失了报告 12 项行动中的 7 项**（#1 SM64 自动重启、#5 课程晋级、#6 DAN 权重、#8 写 control 清零、#10 度量看板、#11 WSL/CI、#12 CSS 契约），
而自造了 2 个幻象 P0 并自我否证 → 结果是**当时没有任何文档在推进「SM64 冻结自动重启」这个唯一经实测确认成立的 P0 缺口**。本计划 §1 的 12 项与报告 §5 **逐项一一对应，无丢失、无自造**。

---

## 1. 12 项行动总览

编号规则：`行动 N` 沿用**报告 §5 的原始编号 1–12**（便于与 `docs/fly64_export_logs_analysis_report.md` 对账）。
优先级沿用报告的 P0×3 / P1×3 / P2×3 / P3×3 分组。
「前置资产」列的 `✗` = T0/T1 已确认**不存在**，行动内含**降级/替代方案**。

| # | 优先 | 行动 | 前置资产（实测） | 关键落点 | 工作量 |
|---|---|---|---|---|---|
| 1 | **P0-1** | SM64 冻结自动重启 | ✅ `plugin/watchdog.sh`、✅ `scripts/start_fly64_full.sh`、✅ `scripts/consolidate.sh`、✅ `fly64/fly64/bridge.py:56-114`、✅ `fly64/fly64/main.py:2278` | 新增 `fly64/plugin/sm64_watchdog.sh` + `fly64/tests/test_sm64_watchdog.py` | 2.5–4 人日 |
| 2 | **P0-2** | 回归基线获取（分类工具 + 平台全量分类） | ✅ 双基线文件、✅ `scripts/check_regressions.py`、✅ `tests/test_regression_detector.py`；✗ 无独立分类工具 | 新增 `fly64/scripts/baseline_tool.py` + 修 3 条 `unknown` | 1.5–2.5 人日 |
| 3 | **P0-3** | 契约审计制度化 | ✅ `scripts/audit_contract_pairs.py`（exit 0）、✅ `.github/workflows/ci.yml`；✗ `pyproject.toml` / ✗ `.pre-commit-config.yaml` | 改 `.github/workflows/ci.yml`（**不是**新建 pre-commit） | 0.5–1 人日 |
| 4 | P1-4 | 场景识别 → MB 学习闭环 | ✅ `fly64/fly64/scene_recognition.py:783 danger_level()`、✅ `model.py:1465-1482`、✅ `DopamineGainController`；✗ `record_danger` / ✗ `learn_from_outcome` | `fly64/fly64/model.py` 多巴胺合成点 + 新增 `fly64/tests/test_scene_danger_learning.py` | 2–3.5 人日 |
| 5 | P1-5 | 课程晋级端到端验证 | ✅ `plugin/coach_outcomes.py:296 update_curriculum()`、✅ `skills/curriculum.json`、✅ `skills/coach_outcomes.jsonl`（30 行）、✅ `tests/test_coach_outcomes.py`、✅ `tests/test_curriculum_unknown_metric.py` | 真实数据复算 + 合成回放；**不重写状态机** | 1–2 人日 |
| 6 | P1-6 | DAN 权重自动化 | ✅ `fly64/fly64/model.py:1337-1345`（9 个 `DAN_*`）、✅ `fly64/scripts/measure_evolution_health.py`、✅ `tests/test_dan_shaping.py`；✗ `brain_tunable_params.json` 中无 DAN 键 | `fly64/skills/brain_tunable_params.json` + `model.py` `_compute_dopamine()` 读取点 | 2.5–4 人日 |
| 7 | P2-7 | CX 空间导航回路部署 | ✅ **已实测在跑**（`model.py:663,1741-1760`、`main.py:2033-2072`、`memory.py:2304 navigation_vectors`） | 收敛验收 + 补契约测试 `fly64/tests/test_cx_navigation_loop.py` | 1.5–3 人日 |
| 8 | P2-8 | `main.py` 写 control 清零 | ✅ `fly64/fly64/main.py`（36 处）、✅ `tests/test_p1_neural_takeover.py:230-242` | 分批 36 → ≤26 → 后续归零；改 `fly64/fly64/main.py` | 3–6 人日 |
| 9 | P2-9 | 教练通路契约测试 | ✅ `plugin/strategy_writer.py`、✅ `fly64/tests/test_coach_contract.py`、✅ `scripts/audit_contract_pairs.py`；✗ `CoachContract` | 扩展 `fly64/tests/test_coach_contract.py` + 新增 `fly64/tests/test_coach_roundtrip.py` | 1.5–2.5 人日 |
| 10 | P3-10 | 度量看板 | ✅ `scripts/measure_evolution_health.py --json`、✅ `main.py:202` `/evolution.json`、✅ `web/dashboard.js:1156-1185`、✅ `fly64/skills/evolution_health_trend.jsonl`（**仅 1 行**）；✗ 无「排行榜」任何实现 | `fly64/fly64/main.py`（新端点）+ `fly64/web/dashboard.js` + `fly64/web/index.html` | 2.5–4 人日 |
| 11 | P3-11 | WSL 测试 CI | ✅ `.github/workflows/ci.yml`（66 行，**已存在且已在 ubuntu-latest 跑**） | **补齐覆盖面**，不是新建 | 1–2 人日 |
| 12 | P3-12 | CSS 契约测试 | ✅ `fly64/scripts/layout_audit.py`（Playwright，4 门禁）；✗ `playwright` 未安装；✗ 无截图 diff | 扩 `layout_audit.py` + 新增 `fly64/tests/test_layout_contract.py` | 2–3.5 人日 |

---

## 2. 行动详述

> 每个行动统一 8 个字段：**目标与动机 / 涉及文件 / 实施步骤 / 验证命令 / 验收标准 / 前置依赖 / 工作量 / 风险与回滚**。
> `[不存在]` 标记的路径 = T0 已实测确认不存在，**不得照抄**，行动内已给出替代/降级方案。

---

### 行动 1 — SM64 冻结自动重启 【P0-1】

#### 目标与动机
把「SM64 帧生产冻结」从**只检测**变成**检测 + 自动恢复**。

* 检测层**已全链路打通且已被测试覆盖**：`fly64/fly64/bridge.py:56-83`（`SeqlockWatchdog`，`stale_after` 默认 5.0 s）→ `:103`（实例化）→ `:111-114`（`SharedBridge.stale`）→ `:145/:148`（每 tick 喂 seq）→ `fly64/fly64/main.py:2278`（发布 `"bridge_stale": bool(bridge.stale)`）→ `fly64/web/index.html:4`（`id="bridgeStalePill"`）→ `fly64/web/dashboard.js:1109-1111`（显隐）→ `fly64/web/dashboard.css:108-109`（`.stale-pill`）；测试 `fly64/tests/test_seqlock_watchdog.py`（103 行 / 11 test，本次实测 **11 passed**）。
* **动作层为零**（逐层实测）：`fly64/plugin/service.py` 全文仅 4 处匹配 `sm64|restart|kill|Popen|pkill`，其中唯一的 `kill` 在第 28 行是**文档串里的用法示例**；`fly64/plugin/runner.py` 7 处匹配无一为重启逻辑；`fly64/scripts/consolidate.sh` 的重启对象是**大脑**（`pkill -f "[f]ly64\.main"`），其触发前提是「**SM64 进程存活时**选 FULL 模式」——**它假定 SM64 还活着**；全仓无任何 `auto.?restart / respawn / restart_sm64` 实现。
* 报告 L215 的「未实现」成立，报告行动 1 的需求成立 → **这是当前唯一经实测确认成立的 P0 缺口**，且**旧执行计划把它整条丢了**。

#### 涉及文件

| 路径 | 状态 | 角色 |
|---|---|---|
| `fly64/plugin/watchdog.sh` | 存在（2549 bytes，75 行，`MAX_FAILS=3`，pid 文件 + `kill -0` 活性探测） | **模板与宿主**：新脚本沿用同一套 `log()/FAIL_COUNTER/is_alive()` 结构 |
| `fly64/scripts/start_fly64_full.sh` | 存在（107 行） | **SM64 启动命令的唯一可复用出处**：L58-61 `cd /root/fly64/.cache/sm64ex` + `setsid nohup env FLY64_BRIDGE="$BRIDGE_PATH" ./build/us_pc/sm64.us.f3dex2e --skip-intro > "$SM64_LOG" 2>&1 < /dev/null &` |
| `fly64/scripts/consolidate.sh` | 存在 | 启动契约（`:4-27` 注释块「勿删」/ `:71-75` / `:109-113` `setsid nohup … disown`），新脚本必须遵守 |
| `fly64/scripts/launch_full.sh` | 存在 | 备用启动路径（`:20-27`） |
| `fly64/plugin/sm64_watchdog.sh` | **[待新增]** | 新脚本本体 |
| `fly64/tests/test_sm64_watchdog.py` | **[待新增]** | 离线可运行的门禁测试 |
| `fly64/fly64/bridge.py` | 存在（只看，**不改**） | `:56-83` 看门狗的真实 API（`__init__ / update(seq, now) -> bool / reset()`） |
| `fly64/fly64/main.py` | 存在（只看） | `:2278` `bridge_stale` 发布点 |
| `fly64/plugin/fly64-service.pid` | **[不存在]**（运行期产物） | ⚠️ 参照 `watchdog.sh:38` 的 `is_alive()` 逻辑：**pid 文件不存在即视为 dead**。新脚本**不得**据此判 SM64 存活；SM64 的存活判据必须是 `pgrep -f "us_pc.*skip-intro"` 或 `/proc/<pid>` 扫描 |

#### 实施步骤

1. **确认桥接路径语义**：`watchdog.sh:20-28` 的 `resolve_bridge()` 从**游戏进程** `/proc/<pid>/environ` 读 `FLY64_BRIDGE`，默认回退 `/tmp/f64b`。新脚本复用同一函数，**不得硬编码**路径，否则重启后的 SM64 会写到与大脑不同的桥，产生永久误报（该 bug 在 `watchdog.sh:17-19` 的注释中被记录过）。
2. 新建 `fly64/plugin/sm64_watchdog.sh`，逻辑：
   * 读大脑的最新遥测中的 `bridge_stale`（首选：`curl -s http://127.0.0.1:8765/flow.json` 或 `/monitor` 端点，取 `bridge_stale` 字段——**与 `web/dashboard.js:1156-1165` 用的 `getFlow()` 同源**；降级：直接读 `/proc` 无法得到该字段时，用「桥文件 mtime 距今 > `STALE_S`」作为独立判据）。
   * `pgrep -f "us_pc.*skip-intro"` 判定游戏进程是否存在。
   * 触发条件（**必须同时满足**）：`bridge_stale == true` **且** 已连续 `N=3` 次采样为 stale（默认 `INTERVAL=10s`，与 `watchdog.sh`/`service.py` 的周期一致）→ 避免单次抖动误杀。
   * 动作：`pkill -f "sm64.us.f3dex2e"` → `sleep 3` → 以 `start_fly64_full.sh:58-61` 的**完全相同**的命令行重建（`setsid nohup env FLY64_BRIDGE="$(resolve_bridge)" … --skip-intro > /tmp/sm64.log 2>&1 < /dev/null &` + `disown`）→ 写 `sm64-restart.pid`。
   * **限流**：连续重启 `MAX_FAILS=3` 次仍失败 → 写 `ALERT` 一行到 `fly64/plugin/watchdog.log` 并**停止重启**（防止 SM64 闪退导致无限重启风暴）。沿用 `watchdog.sh` 的 `FAIL_COUNTER` 模式。
   * **clear stale flag**：大脑侧不需要改代码——`bridge.py:145/148` 会在下一帧到来时自动喂新 seq，`stale` 自动转 `False`。**不要**新增手动清零逻辑（那会掩盖检测层）。
3. 驱动方式（**两个候选，任选其一并写入部署文档**）：
   * (A) cron `* * * * * /root/fly64/plugin/sm64_watchdog.sh`（与 `watchdog.sh:6` 的设计一致）；
   * (B) 由 `fly64/plugin/service.py` 的周期循环内联调用（`service.py:89-95 check_bridge()`——其健康检查键名为 `bridge_fresh`，见 `:9` 模块 docstring——可复用同一个 tick）。
   ⚠️ **本机为 Windows，无法验证 WSL 运行态**（T0 §8 N5 / T1 U-01）。运行态验收必须由 WSL 侧执行者完成。
4. 新建 `fly64/tests/test_sm64_watchdog.py`：**纯离线**（不开 WSL、不真起游戏），断言：
   * 脚本存在且 `bash -n` 语法检查通过（`subprocess.run(["bash","-n",path])`；Windows 无 `bash` 时 `pytest.skip`）；
   * 脚本内**不含**硬编码桥路径（`assert "/tmp/f64b" not in body or "resolve_bridge" in body`）；
   * 脚本包含 `setsid nohup` 与 `disown`（启动契约）；
   * 脚本包含 `MAX_FAILS` 限流与 `ALERT` 分支；
   * 脚本以 `start_fly64_full.sh` 中同一二进制名 `sm64.us.f3dex2e --skip-intro` 作为重启目标。

#### 验证命令

```powershell
# cwd = D:\codes\flygym\fly64
$py = "D:\codes\flygym\.venv\Scripts\python.exe"
$env:PYTHONIOENCODING = "utf-8"

# (1) 新资产存在 + 语法
Test-Path plugin\sm64_watchdog.sh
bash -n plugin/sm64_watchdog.sh            # WSL 侧执行；Windows 无 bash 则跳过

# (2) 新测试通过
& $py -m pytest tests\test_sm64_watchdog.py -q -p no:cacheprovider --basetemp .pytest-a1

# (3) 无回归：对照 win32 基线（38 条），NEW failures 必须为 0
& $py scripts\check_regressions.py --report .tmp\a1_failures.txt      # WSL/长跑；见 §4.1

# (4) 检测层仍绿（不得因为新增脚本而破坏既有链路）
& $py -m pytest tests\test_seqlock_watchdog.py -q -p no:cacheprovider --basetemp .pytest-a1b
```

#### 验收标准（可客观判定）

1. `Test-Path fly64\plugin\sm64_watchdog.sh` → `True`。
2. `fly64/tests/test_sm64_watchdog.py` 收集数 ≥ 5，**全绿**。
3. `fly64/tests/test_seqlock_watchdog.py` 仍为 **11 passed**（与本次实测基线一致，检测层未被破坏）。
4. `scripts/check_regressions.py` 的 `NEW failures` 计数 **≤ 1**，且若为 1 则必须**只能是** `tests/test_p1_neural_takeover.py::TestKpiBaseline::test_control_write_count_shrunk`（该条是行动 8 的处理对象，属基线登记的 `test-drift`）。
   > 注：对照基线是 **38 条**（不是 36）；`pytest` 总量必须仍为 **929 passed / 38 failed / 36 skipped** 量级。
5. **WSL 运行态（仅 WSL 侧可判）**：手动 `pkill -f "sm64.us.f3dex2e"` 后，≤ 60 s 内 `pgrep -f "us_pc.*skip-intro"` 返回新 PID，且 `/flow.json` 的 `bridge_stale` 在 ≤ 30 s 内变为 `false`。
   ⚠️ **本条在本机（Windows）无法验收**，必须在交付物中显式标注为「待 WSL 验证」。

#### 前置依赖
无（P0 起点）。但**与行动 2 共享同一份基线**：行动 1 的验收 (4) 需要行动 2 提供**可信的基线**（当前基线含 10 条 NEW，见行动 2），否则「NEW ≤ 1」不可判。

#### 预估工作量
**2.5–4 人日**（脚本 1 d、离线测试 0.5 d、WSL 部署与联调 1–2 d、文档 0.5 d）。

#### 风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| 误判 stale → 杀掉正常运行的游戏 | 连续 3 次采样才触发；`MAX_FAILS=3` 上限；`INTERVAL=10s` | 删除 cron 行 / 移除 `service.py` 中的内联调用 → 行为回到「只检测」（即当前状态） |
| `resolve_bridge()` 取不到桥 → 重启后的游戏写错桥 | 复用 `watchdog.sh:20-28`；取不到时**中止本次重启**并写 `ALERT`，而非回退默认值 | 同上 |
| SM64 启动即崩 → 重启风暴 | `MAX_FAILS=3` + `ALERT` 后停手 | 同上 |
| 脚本新增文件污染工作树 | 新文件用 `git add` 入库（`fly64/plugin/*.sh` 未被 `.gitignore` 忽略，`fly64/.gitignore` 只忽略 `.venv/.cache/runtime/artifacts/private/rom/*.z64/*.n64/*.v64/__pycache__/.pytest_cache/.DS_Store`） | `git rm --cached` + 删文件 |

---

### 行动 2 — 回归基线获取：分类工具 + 平台全量分类 【P0-2】

> **标题修正**：报告原文「**扩展**回归基线」；实测基线**已经存在且自洽**（win32 `count == len(entries) == 38`，linux `== 24`，无重复 id），并且**已比报告的数字新**。
> 真正缺的不是「扩展」，而是 **(a) 一个独立的分类/自检工具**、**(b) 3 条 `unknown` 的分类、 (c) CI 环境的平台基线覆盖**。本计划按此修正。

#### 目标与动机
把「基线可维护」这件一次性的手工活变成可重复执行的门禁：
1. **工具缺失**：仓库**没有**独立的基线分类/审计工具。分类知识散落在 `fly64/scripts/check_regressions.py:56-64`（6 类 `CAUSES` 词表）+ `fly64/tests/test_regression_detector.py::TestBaselineIsWellFormed`（格式校验）+ 零散的 `fly64/.tmp/classify_failures.sh`（一次性诊断脚本，非门禁）。
2. **分类缺口（本次新发现的真实红灯）**：`fly64/tests/known_failures.win32.json` 有 **3 条 `cause = "unknown"` 且 `note` 为空**，直接导致
   `tests/test_regression_detector.py::TestBaselineIsWellFormed::test_every_entry_has_a_cause_and_note` **实测 FAIL**（本次独立复现）。
   该测试**自身就在 win32 基线的 `unknown` 条目里**（自锁：基线未分类 → 测试失败 → 失败被记为新 `unknown` → 永远失败）。
   三条待分类 id：
   * `tests/test_autonomy_regression.py::TestVersionContract::test_brain_version_in_skills_md_round_table`（**版本契约**，与 S1 的 4 种版本声明直接相关）
   * `tests/test_coach_pipeline.py::TestStrategyExecution::test_fallen_recovery_has_params`
   * `tests/test_regression_detector.py::TestDetectorDetects::test_reports_clean_against_its_own_baseline`
3. **平台覆盖缺口**：`.github/workflows/ci.yml` 是 ubuntu 上跑的，但**从不消费 `known_failures.linux.json`**，也**不跑 `check_regressions.py`** → linux 基线（24 条）处于「有文件、无门禁」的荒野状态。

#### 涉及文件

| 路径 | 状态 | 角色 |
|---|---|---|
| `fly64/tests/known_failures.win32.json` | 存在（11228 bytes，38 条，`count == len(entries)`） | 被修对象（3 条 unknown） |
| `fly64/tests/known_failures.linux.json` | 存在（7749 bytes，24 条，`count == len(entries)`） | 被校验对象 |
| `fly64/tests/known_failures.json` | **[不存在]** | ⚠️ 引用**必须**用平台作用域名；`check_regressions.py:41-54` 的 legacy 回退分支在当前 win32 下**不会被走到** |
| `fly64/scripts/check_regressions.py` | 存在（177 行，CLI `--report/--strict/--update/--platform`） | **权威读取方**：`:114` 读 `e["id"]`，`:56-64` 定义 `CAUSES`，`:120-125` 的 `--update` 会保留旧条目的 `cause/note` |
| `fly64/tests/test_regression_detector.py` | 存在（122 行，2 个 class / 6 个 test） | **权威格式门禁**：`TestBaselineIsWellFormed` 三个断言（cause 非空、note 非空、cause ∈ `CAUSES`） |
| `fly64/scripts/baseline_tool.py` | **[待新增]** | 新工具（分类 + 自检 + 跨平台差集） |
| `.github/workflows/ci.yml` | 存在（66 行，`working-directory: fly64`，Python 3.12） | linux 基线门禁的挂载点（与行动 3/11 共用） |
| `fly64/conftest.py` | 存在（**单文件，注意：`fly64/tests/conftest.py` 不存在**） | 测试夹具宿主（`_live_writeout_probe.py` 等运行期探针相关） |

#### 实施步骤

1. 新建 `fly64/scripts/baseline_tool.py`，**只读**子命令：
   * `--check`：读 `known_failures.<platform>.json`（复用 `from scripts.check_regressions import CAUSES, baseline_path`，**不要重复实现路径解析**），断言：
     `count == len(entries)`；`id` 无重复；每条 `cause ∈ CAUSES`；`cause ∈ {environment, aspirational, test-drift, live-state, real-bug}` 时 `note` 非空。退出码 0/1。
   * `--diff`：打印 win32 ∩ / win32-only / linux-only 三个集合（期望 22 / 16 / 2），并**对 win32-only 逐条打印 `note`**——这是「同一失败是否真是平台差异」的唯一可判据来源。
   * `--list-unknown`：列出 `cause == "unknown"` 的 id。
   * **禁止**写入任何基线文件（写操作只允许 `check_regressions.py --update` 这一个入口，避免两个写者）。
2. 修 3 条 `unknown`：
   * 先跑 `& $py -m pytest tests\test_autonomy_regression.py tests\test_coach_pipeline.py -q -p no:cacheprovider --basetemp .pytest-a2` 取真实报错原文；
   * 按 `CAUSES` 词表判定（`environment` / `aspirational` / `test-drift` / `live-state` / `real-bug`）并**写一句可核验的 note**（照抄现有条目的 note 风格，例如 `test_bridge.py::*` 的「Windows Python 3.11 has no time.clock_gettime_ns」）；
   * ⚠️ `test_brain_version_in_skills_md_round_table` 有**强前置**：它断言的正是 S1 的「版本三处同步」契约，而 `main.py=2.23.11 / skills.md=2.23.7,2.23.10 / canonical=2.23.6` **四值不一致** → 该条**不能**标 `environment`，正确分类应为 `real-bug`（契约真实破损）**或** 先完成版本收敛再让测试变绿。**先收敛版本号（见行动 2 步骤 3）还是先分类，是执行者必须做的决策，本计划不代做。**
3. （决策项，建议一并做）**版本收敛**：`fly64/skills/skills.md:3`（2.23.7）与 `:70`（2.23.10）应改为 `2.23.11`，`fly64/skills/evolution_history.json` 的 `canonical_versions.brain` 应更新为 `2.23.11`（`as_of` 同步）。这一步属**文档/元数据修改**，会同时影响行动 2 的分类与 §0 的 S1 —— 若本轮不做，必须在 `baseline_tool.py --diff` 输出中标注「版本契约暂挂」。
4. 把 `baseline_tool.py --check` 接进 `.github/workflows/ci.yml`（与行动 3 同一次改动）：在 ubuntu 上跑 `--platform linux`。
5. 用 `check_regressions.py --update` 刷新 win32 基线（**这会把当前 10 条 NEW failures 吸收进基线**）—— ⚠️ **必须在行动 8（写 control）之前执行**，否则行动 8 的「减少写点」会让那 10 条里的 `test-drift` 条目反向变成 NEW。
   `--update` 后立刻回跑一次 `--strict` 以确认基线不再腐烂。

#### 验证命令

```powershell
# cwd = D:\codes\flygym\fly64
$py = "D:\codes\flygym\.venv\Scripts\python.exe"
$env:PYTHONIOENCODING = "utf-8"

# (1) 基线自检（新工具）
& $py scripts\baseline_tool.py --check --platform win32
& $py scripts\baseline_tool.py --check --platform linux
& $py scripts\baseline_tool.py --diff
"EXIT=$LASTEXITCODE"

# (2) 无 unknown 残留
& $py scripts\baseline_tool.py --list-unknown

# (3) 格式门禁（当前红 → 目标绿）
& $py -m pytest tests\test_regression_detector.py -q -p no:cacheprovider --basetemp .pytest-a2

# (4) count 字段与实际条数一致（Python，勿用 Get-Content）
& $py -c "import json;[print(f,json.load(open(f,encoding='utf-8'))['count']==len(json.load(open(f,encoding='utf-8'))['entries'])) for f in ('tests/known_failures.win32.json','tests/known_failures.linux.json')]"
```

#### 验收标准（可客观判定）

1. `fly64/scripts/baseline_tool.py` 存在，`--check` 对 win32 与 linux **均 exit 0**。
2. `--list-unknown` 输出为空（0 条 `unknown`）。
3. `fly64/tests/test_regression_detector.py` **6 passed**（当前 1 failed / 5 passed → 改善），其中 `TestBaselineIsWellFormed::test_every_entry_has_a_cause_and_note` 转 **PASS**。
4. 两基线 `count == len(entries)`，`id` 无重复；win32 条数 ∈ {38, 更新后的 N}，linux = 24（或更新后的 N），且**更新后的数字必须记入本文档 §0.1 的修订版**。
5. `.github/workflows/ci.yml` 中出现 `baseline_tool.py --check --platform linux` 调用（`Select-String -Path ..\.github\workflows\ci.yml -Pattern 'baseline_tool'` 命中 ≥1）。
6. **回滚可观**：`git diff --stat` 显示被改的只有 1 个脚本 + 2 个基线 JSON + 1 个 ci.yml（+ 可选 skills.md / evolution_history.json）。

#### 前置依赖
* **被行动 1、4–12 全部依赖**（它们都拿 `check_regressions.py` 当无回归门禁）。
* 与行动 3（CI 挂载点）共享 `.github/workflows/ci.yml` ——二者**必须同批次提交**（否则产生合并冲突），但无严格拓扑顺序，可并行实施后在提交时合并。

#### 预估工作量
**1.5–2.5 人日**（工具 0.5 d、3 条分类 + 逐条实测 0.5–1 d、`--update` + `--strict` 校验 0.5 d、CI 挂载 0.5 d）。

#### 风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| `--update` 把**真回归**吸收成基线（掩盖缺陷） | ①`--update` 前必须先跑行动 2 步骤 2 的真实报错取证；②`real-bug` 2 条（`test_launcher_lock_blocks_duplicate`、`test_flow_computation_performance`）**必须在 note 里保留「真缺陷」字样**，不得降级为 environment | `git restore fly64/tests/known_failures.*.json`（两文件均可从 git 恢复，本次实测确认被跟踪） |
| 分类工具与 `check_regressions.py` 路径解析不一致（出现第二个「真值源」） | **强制 import 复用** `baseline_path()` 与 `CAUSES`，禁止重新实现 | 删 `baseline_tool.py`，退回手工 |
| 版本契约（`test_brain_version_in_skills_md_round_table`）被草率标为 `environment` | 步骤 2 的显式警告：该条与 S1 强相关，须 `real-bug` 或先收敛版本 | 同上 |
| 跑 pytest 污染工作树（115 条改动） | 见 §4.1 四行模板 | `git restore -- fly64/.pytest-run` + `git clean -fd fly64/.pytest-run` |

---

### 行动 3 — 契约审计制度化 【P0-3】

#### 目标与动机
报告原文：「`audit_contract_pairs.py` 加入 **WSL 部署后**执行步骤」。旧执行计划把它改成「注册到 `pyproject.toml` 或 `.pre-commit-config.yaml`」——**这两个文件在仓库中都不存在**（实测 `Test-Path` 均 `False`；`fly64/` 下也没有 `pyproject.toml`），照抄会直接失败。

**实测可用的落点只有一个**：`.github/workflows/ci.yml`（66 行，`runs-on: ubuntu-latest`，`working-directory: fly64`，Python 3.12）。它**已经**在跑 pytest，但**从不调用** `audit_contract_pairs.py`。

工具本身**可运行且当前为绿**（本次实测）：`cd fly64; & $py scripts\audit_contract_pairs.py` → **exit 0**，
末行 `TOTAL dead-writes + silent-defaults: 8`；`--all` 亦 exit 0。
它读**实时文件**（硬编码 9 个 `ARTIFACTS`，`ROOT = fly64/`），文件不存在即记 `absent` —— 本次实测中 `skills/coach_advice.json` 与 `plugin/service_status.json` 为 `absent`（运行期产物）。

#### 涉及文件

| 路径 | 状态 | 角色 |
|---|---|---|
| `fly64/scripts/audit_contract_pairs.py` | 存在（322 行，CLI **仅** `--json` / `--all`） | 被制度化的工具 |
| `.github/workflows/ci.yml` | 存在（66 行） | **唯一可用落点** |
| `fly64/pyproject.toml` | **[不存在]** | ✗ 报告/旧计划设想的落点之一，**禁用** |
| `.pre-commit-config.yaml` | **[不存在]** | ✗ 另一个设想落点，**禁用** |
| `fly64/plugin/.consult_request.json` | 存在（本次审计中被扫到，含 `[DEAD-WRITE] context.kind` @ `plugin/llm_consult.py:304`） | 审计输入 |
| `fly64/plugin/.consult_response.json` | 存在（含 2 处 `[DEAD-WRITE] strategy.exploration*` @ `llm_consult.py:128,130`） | 审计输入 |
| `fly64/plugin/.pending_outcome.json` | 存在 | 审计输入 |
| `fly64/skills/active_strategy.json` | 存在 | 审计输入 |
| `fly64/skills/curriculum.json` | 存在 | 审计输入 |
| `fly64/skills/coach_outcomes.jsonl` | 存在 | 审计输入 |
| `fly64/skills/scene_strategy_bindings.json` | 存在 | 审计输入 |
| `fly64/skills/coach_advice.json` | **[不存在]**（`absent`，运行期产物） | 审计输入（absent 是合法状态） |
| `fly64/plugin/service_status.json` | **[不存在]**（`absent`，运行期产物） | 审计输入（absent 是合法状态） |

#### 实施步骤

1. 在 `.github/workflows/ci.yml` 的 `Run tests` 步骤**之后**新增一步：
   ```yaml
   - name: Contract-pair audit (dead writes / silent defaults)
     run: |
       python scripts/audit_contract_pairs.py --json > /tmp/contract_audit.json
       python scripts/audit_contract_pairs.py
   ```
   ⚠️ **不要**写成会失败的 `|| exit 1` 门禁：当前 `TOTAL = 8`（8 处真实 dead-write/silent-default），
   立刻当门禁会把 CI 变红。**第一步只做「记录 + 上传 artifact」**，把「门禁化」留给后续轮次（那时 `TOTAL` 需先降到 0）。
2. 上传审计产物（复用既有 `actions/upload-artifact@v4` 模式，见 ci.yml:60-66）。
3. （WSL 侧，报告原意）在 `fly64/scripts/consolidate.sh` 的部署流程**末尾**追加一次审计调用并写日志 ——
   这是报告「加入 WSL 部署后执行步骤」的**直接落地方式**，且不需要任何新文件。
4. 在 `fly64/tests/test_coach_contract.py::TestAuditToolIsPresent::test_audit_script_exists`（已存在并**通过**）之外，
   不新增重复断言——该测试已覆盖「审计脚本存在」。

#### 验证命令

```powershell
# cwd = D:\codes\flygym\fly64
$py = "D:\codes\flygym\.venv\Scripts\python.exe"
$env:PYTHONIOENCODING = "utf-8"

# (1) 工具本身仍可运行且为绿
& $py scripts\audit_contract_pairs.py; "EXIT=$LASTEXITCODE"
& $py scripts\audit_contract_pairs.py --all; "EXIT=$LASTEXITCODE"
& $py scripts\audit_contract_pairs.py --json | Select-Object -First 5

# (2) CLI 未被误改（应报错，证明没有 --mode/--target）
& $py scripts\audit_contract_pairs.py --mode trace --target control; "EXIT=$LASTEXITCODE"   # 期望 exit 2

# (3) CI 已挂载
Select-String -Path ..\.github\workflows\ci.yml -Pattern 'audit_contract_pairs'

# (4) 既有契约测试仍绿
& $py -m pytest tests\test_coach_contract.py -q -p no:cacheprovider --basetemp .pytest-a3
```

#### 验收标准（可客观判定）

1. `.github/workflows/ci.yml` 中 `audit_contract_pairs` 命中 **≥1**（`Select-String` 可判）。
2. 本地 `& $py scripts\audit_contract_pairs.py` **exit 0**，末行仍为 `TOTAL dead-writes + silent-defaults: 8`（数字可升可降，但必须**被记录**；本轮**不**设为门禁）。
3. 误用 CLI 仍 `exit 2`（证明未擅自扩展参数面）。
4. `fly64/tests/test_coach_contract.py` **全绿**（本次实测该文件不含基线条目，故必须全绿）。
5. CI 步骤不阻塞 PR：新增步骤在 `TOTAL > 0` 时**不返回非零**。

#### 前置依赖
与**行动 2** 共用 `.github/workflows/ci.yml` → 必须同批提交。二者同属 P0，可并行开发、串行提交。

#### 预估工作量
**0.5–1 人日**。

#### 风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| 把 `TOTAL = 8` 直接设成门禁 → CI 常红 | 本轮只记录不上门禁；「门禁化」列为后续轮次 | 删掉新增 YAML 步骤（`git diff` 只有几行） |
| 照抄旧计划的 `pyproject.toml` / `.pre-commit-config.yaml` | **本文件显式标注两者不存在**；CI 是唯一落点 | 无（本就不会创建） |
| WSL 侧 `consolidate.sh` 追加调用改变部署行为 | 调用置于末尾且失败不 `exit`（`|| true`），只写日志 | `git restore fly64/scripts/consolidate.sh` |

---

### 行动 4 — 场景识别 → MB 学习闭环 【P1-4】

> **必须重写**：旧执行计划要求在 `SceneMemory.record_danger()` 中实现、在 `scene_recognition.py:783` 附近调用
> `self.scene_memory.record_danger(...)`，并在 `MushroomBody.learn_from_outcome()` 末尾写合约。
> **`record_danger` / `learn_from_outcome` 在全 `fly64/` 树（含 `fly64/tests/`）中 0 命中**（本次独立复核确认）。
> 照此施工会直接找不到函数。

#### 目标与动机
把「识别到危险场景」从**只做行为制动**升级为**同时进入 MB 学习管道**。

**实测现状（这是本行动的全部事实基础）**：

| 环节 | 实测位置 | 现状 |
|---|---|---|
| 危险度计算 | `fly64/fly64/scene_recognition.py:783 def danger_level()`（`tags & {"danger","lava","hell"} → 1.0`） | ✅ 存在，函数名正确（旧计划引用的行号也对，但方法名是 `danger_level` 不是 `record_danger`） |
| 写入模型 | `fly64/fly64/main.py:2042 model.scene_danger = scene_recognizer.danger_level()` | ✅ 每 tick 计算 |
| 初始化 | `fly64/fly64/model.py:538` / `:1173`（`self.scene_danger = 0.0`）与 `model.py:1849-1850` | ✅ 存在 |
| **唯一消费点** | `fly64/fly64/model.py:1849-1850`：`if self.scene_danger > 0.0: self.v[self.forward] -= self.scene_danger * 0.06` | ⚠️ **只注入 LIF 前向电流（行为制动），不进任何学习管道** |
| MB 学习管道 | `fly64/fly64/model.py:1461` `_behavioral_dop = self._compute_dopamine()` → `:1462` `_reward_contrib = max(-0.3, min(0.5, self.reward_signal)) * 0.4` → `:1465-1467` `_pending_dopamine` → `:1477-1479` `_coach_dopamine_bias` → `:1481-1482` `self.mushroom.set_dopamine(dop)` + `update_weights()` | ✅ **真实入口在这里**；`scene_danger` **未参与 dop 的任何一项** |
| 场景签名编码 | `fly64/fly64/model.py:1062-1074`（`scene_sig` → `self.mushroom.encode(self.scene_sig)`） | ✅ 场景已进 KC 层，但**危险度没有** |
| 增益调制 | `fly64/fly64/gain_modulation.py:84,90,143`（`dopamine_threshold`，默认 `DOPAMINE_GAIN_THRESHOLD`） | ✅ 可复用为第二条注入通道 |
| 相关测试 | `fly64/tests/test_restlessness.py:5,38,43,48-52`（**只断言行为制动那 0.06 项**，不涉及学习） | ⚠️ 覆盖的是旧通路 |

#### 涉及文件

| 路径 | 状态 | 角色 |
|---|---|---|
| `fly64/fly64/model.py` | 存在（2132 行） | **主改造点**：`_compute_dopamine()`（`:1362-1413` 附近的 DAN 合成）与 `:1461-1482` 的 dop 汇总 |
| `fly64/fly64/scene_recognition.py` | 存在（`SceneRecognizer` @ `:591`，`danger_level()` @ `:783`） | 信号源（**不改**，或用最小改动增强可观测性） |
| `fly64/fly64/main.py` | 存在（`:2042`） | 信号注入点（**不改**，`scene_danger` 已在 model 上） |
| `fly64/fly64/gain_modulation.py` | 存在（`DopamineGainController` @ `:56`） | 可选第二通道 |
| `fly64/tests/test_restlessness.py` | 存在 | **必须保持全绿**（回归保护） |
| `fly64/tests/test_mushroom_body.py` | 存在（`scene_sig` 相关 ≥10 个 test） | **必须保持全绿** |
| `fly64/tests/test_scene_danger_learning.py` | **[待新增]** | 新门禁 |
| `fly64/fly64/model.py:49 class SceneMemory` | 存在 | ⚠️ **同名异物警告**：这是**视觉短期记忆/亮度环形缓冲**；场景上下文 dataclass 在 `fly64/plugin/scene_context.py:93 class SceneMemory`。本行动**不需要**任何一个 `SceneMemory`，切勿被旧计划的措辞误导去改它们 |

#### 实施步骤

1. **先定夺口径**（不可跳过）：`scene_danger` 应进入 dop 的哪一项？两条候选，**必须二选一并写入代码注释**：
   * (A) 新增独立惩罚项 → 与 `_pending_dopamine` 同层：
     `dop = clip(_behavioral_dop + _reward_contrib + _pending + _coach_bias + (-K * scene_danger))`，`K` 初始 `0.30`（与 `DAN_PUNISH_LOOMING = 0.30` 对齐，见 `model.py:1342`）。
   * (B) 做成 `_compute_dopamine()` 内的一个 `DAN_*` 分支（**推荐**，因为它自动获得行动 6 的「可调参」能力，且与 `DAN_PUNISH_*` 家族风格一致）。
2. 在选定的注入点实现，并**保留行为制动项不动**（`model.py:1849-1850` 的 `0.06`），使「制动」与「学习」是两条独立通路 —— 这样 `test_restlessness.py` 不需改动。
3. 加**限幅与去抖**：`scene_danger` 是 0/1 阶跃信号，直接进 dop 会让每个危险帧都触发 `PLASTICITY_WINDOW`。建议：只在 `scene_danger` **上升沿**注入一次（类似 `add_setback` 的「单次消耗」语义，见 `model.py:1324-1329`），强度上限 `≤ 0.5`（与 `DAN_PUNISH_*` 最大项 `DAN_PUNISH_FALLEN = 0.80` 保持同级但更低）。
4. 新增 `fly64/tests/test_scene_danger_learning.py`（**不引用任何幻象 API**）：
   * 构造 `FlyModel`，设 `model.scene_danger = 1.0`，跑 1 tick，断言 `model.mushroom.dopamine` 相对基线**变负**（用 `mushroom.dopamine_stats()`，`mushroom_body.py:579`）；
   * 断言 `mushroom.update_weights()` 的返回突触数 > 0（`mushroom_body.py:362`）；
   * 断言**不触发**：`scene_danger = 0.0` 时 `mushroom.dopamine` 与基线一致；
   * 断言上升沿语义：连续 10 个 tick 保持 `scene_danger = 1.0` 时，总惩罚注入次数 == 1（不是 10）；
   * 断言行为制动项**未变**：`model.v[model.forward]` 的 `-scene_danger*0.06` 项仍在（与 `test_restlessness.py:48-52` 同口径但不重复）。
5. 用 `fly64/skills/scene_strategy_bindings.json` 作为**端到端取证入口**：跑一次真实/回放会话后确认绑定表出现危险场景条目（该文件被 `audit_contract_pairs.py` 的 `ARTIFACTS` 覆盖，可交叉验证）。

#### 验证命令

```powershell
# cwd = D:\codes\flygym\fly64
$py = "D:\codes\flygym\.venv\Scripts\python.exe"
$env:PYTHONIOENCODING = "utf-8"

# (1) 新门禁
& $py -m pytest tests\test_scene_danger_learning.py -q -p no:cacheprovider --basetemp .pytest-a4

# (2) 行为回归保护（必须仍全绿，11 → 与本次实测一致）
& $py -m pytest tests\test_restlessness.py tests\test_mushroom_body.py tests\test_gain_modulation.py -q -p no:cacheprovider --basetemp .pytest-a4b

# (3) 学习管道真实入口仍在（不许改名）
& $py -c "import re;s=open('fly64/model.py',encoding='utf-8').read();print('set_dopamine:', bool(re.search(r'self\.mushroom\.set_dopamine',s)));print('update_weights:', bool(re.search(r'self\.mushroom\.update_weights',s)))"

# (4) 幻象 API 仍为 0 命中（防止有人照旧计划写进来）
#     用 DSH grep 工具: path=fly64, include=*.py, pattern=learn_from_outcome|record_danger

# (5) 无回归（对照 win32 基线 38 条，NEW 必须为 0；见 §4.1）
& $py scripts\check_regressions.py --report .tmp\a4_failures.txt
```

#### 验收标准（可客观判定）

1. `fly64/tests/test_scene_danger_learning.py` 收集数 ≥ 5，**全绿**。
2. `tests/test_restlessness.py tests/test_mushroom_body.py tests/test_gain_modulation.py` **全绿**（回归保护；三者本次实测均不在 38 条基线中）。
3. `grep learn_from_outcome|record_danger` 在 `fly64/` 下命中数 **仍为 0**（证明没有照抄幻象 API）。
4. `scripts/check_regressions.py` 的 `NEW failures` **≤ 1** 且只能是 KPI 那条（同行动 1 的口径）；`pytest` 汇总仍为 `929 passed / 38 failed / 36 skipped` 量级。
5. **闭环可证**：`fly64/skills/scene_strategy_bindings.json` 在一次含危险场景的回放后出现 ≥1 条危险场景绑定（该文件存在且为审计输入，可判定）。

#### 前置依赖
* **依赖行动 2**（无回归门禁需要可信基线）。
* 若选 **(B) 方案**，则**与行动 6 强耦合**（`DAN_*` 可调参化）——建议行动 4 先按 (A) 落地并留好 (B) 的接口，行动 6 再迁移。**不要**让行动 4 等行动 6。

#### 预估工作量
**2–3.5 人日**（口径定夺 0.5 d、实现 0.5–1 d、测试 0.5–1 d、回放取证 0.5–1 d）。

#### 风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| 危险帧连续注入 → 过惩罚、MBON 饱和 | 上升沿单次注入 + 强度上限 0.5 | 把注入系数设为 0（保留代码路径，行为回到当前状态） |
| 破坏 `test_restlessness.py` 的行为制动断言 | 制动项 `model.py:1849-1850` **完全不动** | `git restore fly64/fly64/model.py` |
| 误改 `SceneMemory`（同名异物） | 本行动**不导入、不改动**任何 `SceneMemory`；两个同名类列在「涉及文件」表里作警示 | 无（不会触碰） |
| 学习信号与 `_coach_dopamine_bias` 打架 | 明确限幅层级（`dop` 已在 `:1466/:1479` 两次 `clip(-1,1)`），新项必须在 clip 之前加入 | 同上 |

---

### 行动 5 — 课程晋级端到端验证 【P1-5】

#### 目标与动机
报告称「t16 里程碑已完成正向验证」（`EVO-070` 记录含 `improved=2 / qualifying=1 / stage 1→5` 实测）。
**实测：状态机、持久化、单测全在，但「端到端晋级」的当前证据链断了** —— `fly64/skills/curriculum.json` 显示
`stage = 1`、`attempts = 8`、`consecutive_ok = 0`、`unobserved = 0`，且带 `reset_at = 2026-09-17T20:43:41+08:00`
与 `reset_reason`（「连击被脑冷启动/不可达窗口的虚假失败污染」）。
即：**晋级证据被一次 reset 清空**，当前无法证明 ladder 在真实数据上还能往上走。

而 `fly64/skills/coach_outcomes.jsonl` 现有 **30 行**（与 `measure_evolution_health.py --json` 的 `outcomes_total_lines: 30` 一致；
`outcome_verdicts = {unchanged: 21, worse: 1, improved: 8}`），`usable_for_signature = 0`（`skipped_no_scene_label = 30`）。

**因此本行动的定位是「端到端验证」，不是「重新实现」** —— 旧执行计划把这一整条**丢了**。

#### 涉及文件

| 路径 | 状态 | 角色 |
|---|---|---|
| `fly64/plugin/coach_outcomes.py` | 存在（351 行）：`:221` 区间头注释；`:222 _goal_met()`（**三态** True/False/**None=不可观测**）；`:253 load_curriculum()`；`:262 save_curriculum()`；`:269 DEFAULT_CURRICULUM`；`:280 STAGE_GOALS`（6 级，`disp_60s` 30/60/120/250/500/900）；`:290 goal_for_stage()`；`:296 update_curriculum(curriculum, outcome, memory, ok_streak=2, fail_streak=3)` | **被验证对象（不改）** |
| `fly64/skills/curriculum.json` | 存在（137 行，`stage 1`，`history` 20 条） | 真实状态输入 |
| `fly64/skills/coach_outcomes.jsonl` | 存在（30 行） | 真实 outcome 输入 |
| `fly64/plugin/runner.py` | 存在（`:349-351` 读 curriculum 进 context、`:403-406` `update_curriculum` + `save_curriculum`） | 真实调用链 |
| `fly64/plugin/service.py` | 存在（`:211-213` 读 curriculum 进 context） | 真实调用链 |
| `fly64/tests/test_coach_outcomes.py` | 存在（`**PIN tests**`：`:102-108` ok×2 → advance；`:129-136` 不观测不计连击；`:146-149` 持久化 roundtrip） | 现有覆盖（**不改**） |
| `fly64/tests/test_curriculum_unknown_metric.py` | 存在（`:76-123` 不可观测metric 不推进不退阶） | 现有覆盖（**不改**） |
| `fly64/scripts/replay_curriculum.py` | **[待新增]** | 端到端回放取证工具 |
| `fly64/tests/test_curriculum_end_to_end.py` | **[待新增]** | 端到端门禁 |
| `fly64/scripts/audit_contract_pairs.py` | 存在（`ARTIFACTS` 含 `skills/curriculum.json` @ `:172`） | 交叉验证入口 |

#### 实施步骤

1. **真实数据复算（只读）**：写一次性复算脚本（不外提），用 `fly64/skills/coach_outcomes.jsonl` 的 30 条 verdict 重放
   `update_curriculum()`，断言复算出的 `stage/attempts/consecutive_ok/consecutive_fail/unobserved`
   **等于** `fly64/skills/curriculum.json` 的现值。**若不等** → 记录差异，这就是「状态机与真实数据脱节」的硬证据，
   应作为**新发现**上报，而不是改数据。
2. 新增 `fly64/scripts/replay_curriculum.py`（**只读，不写 `skills/curriculum.json`**，写 `fly64/.tmp/`）：
   * `--from-jsonl`：按 1 复算并打印逐条 `(verdict, met, stage)` 轨迹；
   * `--synthetic`：用合成序列 `[improved×2 → 期望 stage 2]`、`[unchanged×3 → 期望 stage 1 回退]`、
     `[disp_60s=null ×5 → 期望 stage 不变且 unobserved=5]` 三组，**证明 ladder 双向可动**。
3. 新增 `fly64/tests/test_curriculum_end_to_end.py`，断言：
   * 「本能固化证据链 → 课程晋级」：用 `coach_outcomes.record_outcome`（**先确认该函数名，见步骤 0**）产出 improved →
     `update_curriculum` 推进 → `curriculum["stage"] == 2` → `goal_for_stage(2)["target"] == 60`；
   * 回退：连续 3 次未达成 → `stage` 回 1；
   * 不可观测：`disp_60s = None` 连续 5 次 → `stage` 不变、`unobserved == 5`、`consecutive_ok/fail` 不动；
   * 持久化：`save_curriculum` → `load_curriculum` roundtrip 后 `history` 长度 ≤ 20（`coach_outcomes.py:332` 的 `[-20:]` 截断）。
4. ⚠️ **步骤 0（必须先做）**：确认 `plugin/coach_outcomes.py` 中**产出 outcome 的真实函数名**
   （`fly64/plugin/runner.py:403` 调用 `co.update_curriculum(co.load_curriculum(), outcome, …)`，`outcome` 由上游产生）。
   **不得凭猜测写函数名** —— 本计划不给出未实测的函数名，此为一处显式**待确认项**。

#### 验证命令

```powershell
# cwd = D:\codes\flygym\fly64
$py = "D:\codes\flygym\.venv\Scripts\python.exe"
$env:PYTHONIOENCODING = "utf-8"

# (1) 真实数据复算（只读，必须与 curriculum.json 现值一致）
& $py scripts\replay_curriculum.py --from-jsonl

# (2) 合成序列证明 ladder 双向可动
& $py scripts\replay_curriculum.py --synthetic

# (3) 端到端门禁
& $py -m pytest tests\test_curriculum_end_to_end.py -q -p no:cacheprovider --basetemp .pytest-a5

# (4) 既有覆盖仍绿（PIN 测试 + 三态测试）
& $py -m pytest tests\test_coach_outcomes.py tests\test_curriculum_unknown_metric.py -q -p no:cacheprovider --basetemp .pytest-a5b

# (5) 只读性自证：跑完 (1)(2)(3)(4) 后 curriculum.json 未被改动
git diff --stat -- fly64/skills/curriculum.json      # 期望空
```

#### 验收标准（可客观判定）

1. `fly64/scripts/replay_curriculum.py --from-jsonl` exit 0，且打印的 `attempts == 8`、`stage == 1`
   （与 `fly64/skills/curriculum.json` 现值逐位一致）——**或**给出可复现的差异报告（差异本身也是合格产出，但必须显式标注）。
2. `--synthetic` 三组断言全部 PASS（正向晋级 / 反向回退 / 不可观测不动）。
3. `fly64/tests/test_curriculum_end_to_end.py` 收集数 ≥ 4，**全绿**。
4. `tests/test_coach_outcomes.py` + `tests/test_curriculum_unknown_metric.py` **全绿**（本次实测两者均不在 38 条基线中）。
5. `git diff --stat -- fly64/skills/curriculum.json` 为**空**（验证过程未污染真实状态）。
6. 无回归：`scripts/check_regressions.py` 的 `NEW failures` ≤ 1 且只能是 KPI 那条。

#### 前置依赖
**依赖行动 2**（无回归门禁）。**不依赖**行动 1/3/4。

#### 预估工作量
**1–2 人日**（函数名确认 0.2 d、复算 0.3 d、合成回放 0.3 d、门禁测试 0.5 d）。

#### 风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| 回放脚本误写 `skills/curriculum.json`（它是真实运行状态 + 审计输入） | 脚本**只写 `fly64/.tmp/`**；验收 (5) 用 `git diff --stat -- fly64/skills/curriculum.json` 强制自证 | `git restore fly64/skills/curriculum.json`（该文件被 git 跟踪） |
| 复算结果与现值不一致 → 被误判为「需要修数据」 | **差异是发现，不是缺陷**；上报 captain，**不得**改写 curriculum.json 去凑 | 无（只读） |
| 猜测不存在的函数名（重蹈旧计划覆辙） | 步骤 0 显式要求先实测函数名；本计划对未实测符号**不给名字** | 无 |

---

### 行动 6 — DAN 权重自动化 【P1-6】

> **必须重写**：旧执行计划把它替换成了 `fly64/plugin/evolution_logs.py` / `class EvolutionLogger` ——
> **该文件不存在、该类名 0 命中**（最危险的一条：容易被当成「待修的真实模块」而白白投入）。
> 报告原文的目标（「EVO 循环自主调优 `DAN_*` 常量，替代手动调参」，参考「EVO R18 已常量化」）**成立且资产齐全**。

#### 目标与动机
`fly64/fly64/model.py:1337-1345` 有 **9 个 `DAN_*` 类级常量**，并在 `:1362` 自述：
> 「Weights are the class-level ``DAN_*`` shaping constants — **tune the** …」

但它们**不在可演化参数字典里**：`fly64/skills/brain_tunable_params.json`（160 行，`21` 个参数，`wired: true` **仅 7 个**）中
**无任何 `DAN_*` 键**（实测）；与 dopamine 相关的键**仅 1 个**：`exploration.dopamine_revisit_cost`
（`wired: false`，且其 `default 0.5` **越界** `[min 0.0, max 0.4]` —— 见行动 6 步骤 3 与文末自检命令）。
`fly64/scripts/measure_evolution_health.py --json` 实测
`params_total 21 / params_wired 7 / params_inert 14 / inert_fraction 0.6667`，
且 `--phase6` 自述 `moved_dimensions_total {wired: 264, inert: 798, inert_share: 0.7514}`
→ **75% 的搜索维度是纯噪声**。把 DAN 常量接进 `wired` 参数，是同时改善「可调性」与「搜索效率」的高杠杆点。

#### 涉及文件

| 路径 | 状态 | 角色 |
|---|---|---|
| `fly64/fly64/model.py` | 存在：`:1337-1345` 9 个 `DAN_*`；`:1362-1413` `_compute_dopamine()` 的读点；`:1477-1479` `_coach_dopamine_bias` 通道 | **主改造点** |
| `fly64/skills/brain_tunable_params.json` | 存在（`version 1.1.0`，21 参数，`wired_note` 明确「`wired=true` means a component in `fly64/` or `plugin/` actually reads this dotted path from `active_strategy.json`」） | 声明面（新增 `dopamine.*` 键） |
| `fly64/fly64/main.py` | 存在：`:1294-1304` `_dop = dict(_active_strategy.get("dopamine", {}) or {})`；`load_active_strategy()` @ `:807` | **`dopamine` 段的热加载通路已存在**（R13b/`ver_append_fix9.py:25` 记录「`load_active_strategy` 透传 `dopamine` 键」）→ 新增键**天然可热加载** |
| `fly64/skills/active_strategy.json` | 存在 | 参数落地文件 |
| `fly64/tests/test_dan_shaping.py` | 存在（`:20-25` **PIN 了 `DAN_REWARD_EXPLORATION == 0.20` / `DAN_PUNISH_FALLEN == 0.80` / `DAN_PUNISH_LOOP_STATES == 0.35`**） | ⚠️ **硬约束**：改为可配置后这些 PIN 会失败 → 必须同步改（**或**保留类级默认值不变、只新增覆盖通道，见步骤 2 方案 α） |
| `fly64/tests/test_tunable_wiring.py` | 存在（`:10,141` 断言若干参数为 inert；`:173-180` 断言 inert 参数**不被写进** `active_strategy`） | ⚠️ 新增 `wired: true` 参数会改变该测试的期望集合 → 必须同步更新 |
| `fly64/scripts/measure_evolution_health.py` | 存在（`--phase6` 统计 wired/inert） | 度量入口（**不改**） |
| `fly64/scripts/audit_contract_pairs.py` | 存在（`ARTIFACTS` 含 `skills/active_strategy.json` @ `:165`） | 交叉验证：新键**必须有读点**，否则会被审计记为 `[DEAD-WRITE]` |

#### 实施步骤

1. **选定 3–5 个 DAN 常量**做首批可调参化（不要一次全上，避免 9 维同时开放导致归因不可分）。建议按 `DAN_PUNISH_*` 中权重最高者优先：
   `DAN_PUNISH_FALLEN (0.80)`、`DAN_PUNISH_STANDOFF (0.45)`、`DAN_PUNISH_CLIFF (0.40)`、`DAN_REWARD_PROGRESS (0.30)`、`DAN_PUNISH_STUCK (0.30)`。
2. **选一个实现方案（必须二选一并写注释）**：
   * **方案 α（推荐，对既有测试破坏最小）**：**保留类级 `DAN_*` 常量作为默认值**（`test_dan_shaping.py` 的 3 个 PIN **保持不变**），
     在 `_compute_dopamine()` 内改为 `getattr(self, "_dan_override", {}).get("DAN_PUNISH_FALLEN", self.DAN_PUNISH_FALLEN)`；
     由 `main.py` 的 `_dop` 段把 `active_strategy.dopamine.dan_*` 映射成 `model._dan_override`。
   * **方案 β**：把常量改为实例属性 → **会破坏 `test_dan_shaping.py:23-25` 的三个 PIN**，必须同步改测试。**不推荐**（PIN 是防漂移保护，不该为可调参而拆掉）。
3. 在 `fly64/skills/brain_tunable_params.json` 的 `params` 内新增条目，**严格沿用既有 schema**
   （`aliases / default / min / max / description / wired`），例如：
   ```json
   "dopamine.punish_fallen": {
     "default": 0.80, "min": 0.0, "max": 1.0,
     "description": "DAN_PUNISH_FALLEN — dopamine punishment magnitude while fallen.",
     "wired": true
   }
   ```
   `min/max` 必须包含 `default`（**注意既有文件里有多处 `default` 落在 `[min,max]` 之外的坏数据**，例如
   `exploration.dopamine_revisit_cost` 的 `default 0.5` 而 `max 0.4`、`exploration.breakout_forward_bias` 的 `default 0.7` 而 `max 0.4`、
   `escape.fallen_jump_boost` 的 `default 0.6` 而 `max 0.4` —— 新增条目**不得**复制这个错误；把这些既有问题记为**新发现**）。
4. 同步更新 `fly64/tests/test_tunable_wiring.py` 的期望集合（`:10` 的 inert 列表 / `:141` 的断言）。
5. 交叉验证可写性：跑 `audit_contract_pairs.py` 确认新键**不出现** `[DEAD-WRITE]`（即确有读点）。
6. 用 `measure_evolution_health.py --phase6` 复测 `params_wired / params_total / inert_fraction`，把改善量记入文档。

#### 验证命令

```powershell
# cwd = D:\codes\flygym\fly64
$py = "D:\codes\flygym\.venv\Scripts\python.exe"
$env:PYTHONIOENCODING = "utf-8"

# (1) DAN PIN 未被破坏（方案 α 下必须仍绿）
& $py -m pytest tests\test_dan_shaping.py -q -p no:cacheprovider --basetemp .pytest-a6

# (2) 可调参接线门禁
& $py -m pytest tests\test_tunable_wiring.py -q -p no:cacheprovider --basetemp .pytest-a6b

# (3) 新键的 wired 统计改善（对照基线 21 / 7 / 0.6667）
& $py scripts\measure_evolution_health.py --phase6 --json

# (4) 新键必须有读点（无 DEAD-WRITE）
& $py scripts\audit_contract_pairs.py | Select-String -Pattern 'dopamine|DEAD-WRITE'

# (5) 无回归
& $py scripts\check_regressions.py --report .tmp\a6_failures.txt
```

#### 验收标准（可客观判定）

1. `fly64/skills/brain_tunable_params.json` 中新增键数 ≥ 3，且每个的 `wired == true`；
   `& $py -c "import json;d=json.load(open('skills/brain_tunable_params.json',encoding='utf-8'));print(len(d['params']), sum(1 for v in d['params'].values() if v.get('wired')))"`
   的 `wired` 计数从 **7** 提升到 **≥10**。
2. `measure_evolution_health.py --phase6 --json` 的 `inert_fraction` 从 **0.6667** 下降到 **≤0.62**（对应 ≥3 维从 inert 转 wired）。
3. `tests/test_dan_shaping.py` **全绿**（方案 α）。
4. `tests/test_tunable_wiring.py` **全绿**。
5. `audit_contract_pairs.py` 输出中**不出现**新键的 `[DEAD-WRITE]`。
6. 无回归：`NEW failures` ≤ 1 且只能是 KPI 那条。

#### 前置依赖
* **依赖行动 2**。
* **与行动 4 有接口耦合**：若行动 4 选方案 (B)（把 `scene_danger` 做成 `DAN_*` 分支），行动 6 应把该分支一起纳入可调参集合。**建议顺序：行动 4 (A) 落地 → 行动 6 迁移**。行动 6 **不阻塞**行动 4。

#### 预估工作量
**2.5–4 人日**（首批选参 + 方案设计 0.5 d、`model.py` 读点改造 0.5–1 d、参数字典 + 测试同步 0.5–1 d、`active_strategy` 热加载联调 0.5–1 d、度量复核 0.5 d）。

#### 风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| 拆坏 `test_dan_shaping.py` 的 PIN 保护 | **强制方案 α**（保留类级默认值，只加覆盖层） | `git restore fly64/fly64/model.py fly64/tests/test_dan_shaping.py` |
| 新增 `wired: true` 但实际无读点 → `[DEAD-WRITE]` | 验收 (5) 强制审计；`brain_tunable_params.json` 的 `wired_note` 已写「Re-check with `scripts/audit_contract_pairs.py` before flipping a flag」 | 把 `wired` 改回 `false` |
| 一次开放 9 维 → EVO 归因不可分 | 首批只上 3–5 个 | 逐个回退 `wired: false` |
| 复制既有 `default ∉ [min,max]` 坏数据 | 验收 (1) 增加区间自检（见下） | 修正 `min/max` |
| 热加载链路 `_dop`（`main.py:1294-1304`）改坏 | 该段有 `dopamine.setback` 单次消耗语义，新增键**只读不消耗** | `git restore fly64/fly64/main.py` |

> 追加自检命令（建议加入行动 2 的 `baseline_tool.py` 或独立跑一次）：
> `& $py -c "import json;d=json.load(open('skills/brain_tunable_params.json',encoding='utf-8'));[print(k,v['default'],v['min'],v['max']) for k,v in d['params'].items() if not (v['min']<=v['default']<=v['max'])]"`

---

### 行动 7 — CX 空间导航回路部署 【P2-7】

> **必须重写，但结论是「已经基本部署完成」**。
> 旧执行计划要求实现 `CentralComplex.navigate_to_goal()`、`MemoryController.store_navigation_hint()/recall_navigation_hint()`、
> `bridge.inject_navigation()` —— **4 个符号全仓 0 命中**。
> 但实测显示：**CX 导航回路早已在真实主循环里跑**，只是**没有以这些名义的方法**。本行动因此从「部署」改为
> **「收敛验收 + 补齐契约测试」**，工作量与风险都大幅下降。

#### 目标与动机
确认并固化「罗盘自主化 + 路径积分 + 多源目标向量竞争」的**现存实现**，把它从事后自述变成**可回归的契约**。

**实测现状（逐环节）**：

| 环节 | 实测位置 | 状态 |
|---|---|---|
| CX 本体 | `fly64/fly64/central_complex.py:47 class CentralComplex`（491 行）；`:23 N_COLUMNS = 16`（环吸引子 16 列）；`:25 LOCAL_EXCITATION=1.2`；`:26 GLOBAL_INHIBITION=0.25`；`:30 STEERING_GAIN=0.12`；`:31 OPTIC_FLOW_GAIN=0.08`；`:32 GOAL_UPDATE_RATE=0.2`；`:33 MAX_STEERING=0.15`；`:34 GOAL_MEMORY_DECAY=0.999` | ✅ 存在 |
| 罗盘自主化（路径积分） | `:157 _self_motion_update(heading_rate, dt)`；`:142 _roll_fractional()`；`:249-292 update(...)` 内 **`_self_motion_update` 先跑**（自述「the bump moves by angular velocity FIRST, autonomously — this is the path-integration term」） | ✅ **已实现** |
| 视觉罗盘修正 | `:189 visual_relocalize(scene_id, ...)`；`:212 _weak_correction(azimuth_rad, weight)`；`main.py:2053-2065` 从 8 个 hue 频带算 `model.visual_azimuth` | ✅ **已实现** |
| 锚点/路径积分 | `:170 set_anchor(x,z)`；`:177 anchor_distance`；`:182 anchor_return_bearing`；`main.py:2051-2052`（`scene_change` 时 `model.cx.set_anchor(pose[0], pose[2])`） | ✅ **已实现** |
| 多源目标向量竞争 | `:249 update(..., goal_vectors: list[tuple[float,float,float]] \| None)`；`fly64/fly64/memory.py:2304 navigation_vectors(x,z,heading,...)`；`main.py:2066-2072 model.cx_goal_vectors = memory_ctrl.navigation_vectors(pose[0],pose[2],pose[3], model.cx_novelty_direction)` | ✅ **已实现** |
| 新奇方向源 | `fly64/fly64/memory.py:576 novelty_direction(x, z, heading, dead_end_keys=..., scene_change_rate=..., forced_bold_explore=...)`；`main.py:2032-2039` 赋值给 `model.cx_novelty_direction`（含 `dead_end_keys` 与 `coverage_rate` 门控） | ✅ **已实现** |
| 转向输出 | `fly64/fly64/model.py:1741-1756 cx_bias = self.cx.update(...)`；`:1757 self.cx_bias = cx_bias`；`:1759-1760 self.v[turn_left] += cx_bias * cx_gain_turn / self.v[turn_right] -= …` | ✅ **已实现**（旧计划的 `bridge.inject_navigation()` 是错的抽象层：CX 直接注入 **LIF 电流**，不走桥） |
| 环路破解 | `:40 CX_LOOP_BREAK_STUCK_S = 45.0`；`:44 CX_LOOP_BREAK_COOLDOWN_TICKS = 1500`；`model.py:1751-1755` 传 `stuck_duration`（注释记录了 `getattr(cx,"stuck_duration")` 恒为 0 的历史 bug，`EVO-057 · P1-1` 已修） | ✅ **已实现且已修过** |
| 测试覆盖 | **未找到**名为 `test_central_complex.py` 的专用测试文件 | ❌ **契约测试缺失 → 本行动的真实缺口** |

#### 涉及文件

| 路径 | 状态 | 角色 |
|---|---|---|
| `fly64/fly64/central_complex.py` | 存在（491 行） | **被验收对象（本行动不改动其逻辑，仅补测试）** |
| `fly64/fly64/memory.py` | 存在（`:576 novelty_direction`、`:2304 navigation_vectors`、`:1733 class MemoryController`） | 目标向量源 |
| `fly64/fly64/model.py` | 存在（`:663 self.cx = CentralComplex()`、`:1741-1760`） | 接线点 |
| `fly64/fly64/main.py` | 存在（`:2033-2072`） | 传感器/目标注入点 |
| `fly64/fly64/instinct_bindings.py` | 存在 | 相关绑定层 |
| `fly64/tests/test_cx_navigation_loop.py` | **[待新增]** | 契约测试（本行动主要交付物） |
| `fly64/tests/test_restlessness.py` | 存在（`:30-45` 断言 loop 压力；`test_standoff_30s_is_full` / `test_loop_pressure_rises_above_08` / `test_zero_when_calm`） | 相关既有覆盖 |

#### 实施步骤

1. **先做「存在性契约测试」**（本轮最高价值、零风险）：`fly64/tests/test_cx_navigation_loop.py`
   * `CentralComplex()` 可构造，`heading_column`（`:229`）返回 `0 ≤ c < 16`；
   * `set_anchor` / `anchor_distance` 一致：`set_anchor(10, 20)` → `anchor_distance` 随 `heading` 变化（`:170-187`）；
   * `update(heading=..., heading_rate=1.0, dt=0.02)` 的返回值为 `float` 且 `|ret| ≤ MAX_STEERING (0.15)`（`:33`）；
   * 自运动积分：`heading_rate != 0` 时 `heading_column` 逐 tick 漂移（**这是「路径积分」的可判定证据**）；
   * 多源竞争：传入 `goal_vectors=[(a,1.0,1.0),(b,0.1,1.0)]`，高权重方向对转向符号的影响更强（`:249-260` 的 `goal_vectors` 语义）；
   * `reset()`（`:448`）后状态回到初值；`compass_stats()`（`:477`）返回字典且含列分布。
2. **接线契约测试**（防回归，不依赖运行态）：
   * 源码级断言 `fly64/fly64/main.py` 含 `memory_ctrl.navigation_vectors(` 与 `model.cx.set_anchor(`；
   * 源码级断言 `fly64/fly64/model.py` 含 `self.cx.update(` 且 `goal_vectors=` 与 `visual_azimuth=` 两个关键字参数被传入；
   * 源码级断言 `cx_bias` 只注入 `turn_left/turn_right`（不注入 forward/jump）——即「只做转向，不做位移」，与 `central_complex.py:30 STEERING_GAIN` 的设计一致。
3. **做一次真实/回放的端到端取证**（可选，1 d）：跑一段带 `scene_change` 的会话，从 `/flow.json` 或 `main.py:2263` 的遥测里确认 `cx_*` 字段有非零变化。若环境不具备，明确标注「待 WSL 验证」。
4. **不改 `central_complex.py` 的逻辑**（除文档串外）。若发现必须改的点，单独立项，不塞进本行动。

#### 验证命令

```powershell
# cwd = D:\codes\flygym\fly64
$py = "D:\codes\flygym\.venv\Scripts\python.exe"
$env:PYTHONIOENCODING = "utf-8"

# (1) 新契约测试
& $py -m pytest tests\test_cx_navigation_loop.py -q -p no:cacheprovider --basetemp .pytest-a7

# (2) CX 可直接构造并跑 1000 tick（无异常）
& $py -c "import sys;sys.path.insert(0,'.');from fly64.central_complex import CentralComplex;cx=CentralComplex();[cx.update(heading=0.1*i,heading_rate=0.5,dt=0.02) for i in range(1000)];print('cx ok', cx.heading_column, cx.anchor_distance)"

# (3) 接线仍在（源码级）
& $py -c "s=open('fly64/main.py',encoding='utf-8').read();print('navigation_vectors:', 'navigation_vectors(' in s);print('set_anchor:', 'set_anchor(' in s)"
& $py -c "s=open('fly64/model.py',encoding='utf-8').read();print('cx.update:', 'self.cx.update(' in s);print('goal_vectors kw:', 'goal_vectors=' in s);print('visual_azimuth kw:', 'visual_azimuth=' in s)"

# (4) 幻象 API 仍 0 命中（防止照旧计划写进来）
#     DSH grep: path=fly64, include=*.py, pattern=navigate_to_goal|store_navigation_hint|inject_navigation

# (5) 无回归
& $py scripts\check_regressions.py --report .tmp\a7_failures.txt
```

#### 验收标准（可客观判定）

1. `fly64/tests/test_cx_navigation_loop.py` 收集数 ≥ 6，**全绿**。
2. 验证 (2) 的命令 exit 0 并打印合法 `heading_column ∈ [0,16)`。
3. 验证 (3) 的 5 个布尔断言**全为 `True`**。
4. `grep navigate_to_goal|store_navigation_hint|recall_navigation_hint|inject_navigation` 在 `fly64/` 下命中 **0**。
5. 无回归：`NEW failures` ≤ 1 且只能是 KPI 那条。
6. `playwright`-free、`WSL`-free：本行动的验收**全部可在 Windows 上离线完成**（这是它相对其他行动的重要优点）。

#### 前置依赖
**仅依赖行动 2**。可与行动 5、9 并行。

#### 预估工作量
**1.5–3 人日**（契约测试 0.5–1 d、接线断言 0.5 d、回放取证 0.5–1 d）。

#### 风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| 「部署」被误解为需要新建方法 → 重蹈旧计划的幻象 | 本文件显式写明 CX 回路**已实现**，并以「存在性契约测试」为交付物 | 删除新增测试文件即可（不触碰生产代码） |
| 契约测试过拟合到当前实现细节（重构即红） | 只断言**公开行为**（返回类型/范围/漂移/符号影响），不断言内部私有属性 | 同上 |
| 误改 `central_complex.py` 引入行为漂移 | 本行动**禁止**改其逻辑；任何逻辑改动必须另立项 | `git restore fly64/fly64/central_complex.py` |

---

### 行动 8 — `main.py` 写 control 清零 【P2-8】

> **起点数字必须改**：报告 L167/L236/L286 称「35→12 处 / ~12 处」。
> 实测口径（= 仓库官方 KPI，定义在 `fly64/tests/test_p1_neural_takeover.py:230-242`）：
> 正则 `\bcontrol\.\w+\s*=[^=]` → **36 行 / 36 处赋值**，预算 `KPI_LINES = KPI_ASSIGNMENTS = 26` → **超标 10**，
> 且该测试**实测 FAIL**（`AssertionError: write lines 36 / assert 36 <= 26`，本次独立复现）。
> 仓库中「35 处」**无任何可核验出处**（唯一可实测的 KPI 轨迹是 `fly64/scripts/ver_append_r24.py:37` 的「18→26 附豁免表」，
> 以及 `test_p1_neural_takeover.py:229` 的 `pre-P1: 45 / 53`（与 `:242` 的打印串同源；`:228` 是 `P1 baseline (2026-09-14): 18 lines / 18 assignments`）。

#### 目标与动机
把 `main.py` 对 `control` 的直接写入**降回预算内（≤26），再逐步归零**。
这是**唯一有现成红灯测试**的行动 → **最先可闭环验收**。
且必须区分「清零」与「达标」：**第一步的目标是回到 26 预算内，不是清零**（报告 L286 的「降至 0」是长期目标）。

#### 涉及文件

| 路径 | 状态 | 角色 |
|---|---|---|
| `fly64/fly64/main.py` | 存在（2471 行，Python 实测） | **唯一被改文件**；36 处写入点分布：`726-727, 1319-1320, 1336, 1338, 1400-1402, 1608-1610, 1616-1619, 1631, 1633, 1639, 1646, 1655-1656, 1668-1670, 1672, 1682-1683, 1691, 1694-1695, 1697, 1705-1706, 1882-1883`（⚠️ `1337` 是 `if control.y < 8:` **不是**写入行，故写成 `1336, 1338`） |
| `fly64/tests/test_p1_neural_takeover.py` | 存在（267 行）：`:230-231` `KPI_LINES = KPI_ASSIGNMENTS = 26`；`:233-242 test_control_write_count_shrunk`；`:244-249 test_remaining_writes_are_guardrails_or_llm` | **权威判据（勿改预算以求绿）** |
| `fly64/fly64/bridge.py` | 存在（`SharedBridge.write_control` 是唯一合法出口） | 目标抽象层 |
| `fly64/tests/known_failures.win32.json` | 存在（第 117-120 行的 `test-drift` 条目即本测试） | 基线登记（**先由行动 2 `--update` 处理**） |
| `fly64/scripts/audit_motor_injections.py` | 存在（基线 note 引用） | 辅助审计入口 |

#### 实施步骤

1. **先做分类（不可跳过）**：用 `:244-249` 的 `test_remaining_writes_are_guardrails_or_llm` 口径把 36 处分成三类：
   * **(a) 护栏类**（cliff reflex / 掉血 / 落地安全）——`1608-1619, 1631-1646, 1682-1697, 1705-1706, 1882-1883`。**保留**，但应按 `test_p1_neural_takeover.py` 的豁免表**登记豁免**。
   * **(b) 命令/对话类**（`1655-1656, 1668-1672` 的 `_cmd_*` 与 `_active_strategy["command"]`）——**保留**（操作员指令通道）。
   * **(c) 决策类**（`1319-1320, 1336, 1338, 1400-1402`：`turn_dir` / `cliff_turn_bias` / `action["control_x"]`）——**这些才是「去 Python 化」的真正目标**，应改为注入 LIF 电流（`model.v[turn_left/turn_right/forward]`），由网络产生 `control.*`。
   ⚠️ 类别 (a)/(b) 的存在意味着**「降到 0」在语义上不可能**（护栏与操作员通道不能删）。**必须先把预算口径与豁免表说清，再谈清零**；本计划主张：**先回到 ≤26，并把豁免表写进测试注释**，而不是追求字面 0。
2. 逐批改造类别 (c)，**每批 ≤ 6 处**，每批后跑 `test_control_write_count_shrunk` + 全量无回归。
3. **同步更新** `fly64/tests/test_p1_neural_takeover.py:222-242` 的注释块（现有注释自述「P1 baseline (2026-09-14): 18 lines / 18 assignments」与实测 36 **矛盾**）——把真实轨迹 `45/53 → 18/18 → 26 预算 → 现状 36` 记录清楚。**但不得提高 `KPI_LINES/KPI_ASSIGNMENTS`**（提高预算 = 作弊；`test_regression_detector.py` 的规范化精神是让基线「不能悄悄腐烂」）。
4. 若某批改动的行为风险高，**不要改**——把它加入豁免表并在注释中记录理由，然后相应下调可达目标（本计划允许「≤26 达标但非 0」作为**合格交付**）。

#### 验证命令

```powershell
# cwd = D:\codes\flygym\fly64
$py = "D:\codes\flygym\.venv\Scripts\python.exe"
$env:PYTHONIOENCODING = "utf-8"

# (1) 官方 KPI 计数（与测试正则同口径）
& $py -c "import re;src=open('fly64/main.py',encoding='utf-8').read();w=[i+1 for i,l in enumerate(src.splitlines()) if re.search(r'\bcontrol\.\w+\s*=[^=]',l)];a=re.findall(r'\bcontrol\.\w+\s*=[^=]',src);print('write lines:',len(w),'assignments:',len(a));print(w)"

# (2) 红灯测试（当前 FAIL → 目标 PASS）
& $py -m pytest "tests/test_p1_neural_takeover.py::TestKpiBaseline" -q -p no:cacheprovider --basetemp .pytest-a8

# (3) 护栏/豁免断言仍绿
& $py -m pytest tests\test_p1_neural_takeover.py -q -p no:cacheprovider --basetemp .pytest-a8b

# (4) 行为回归（bridge 写入链）
& $py -m pytest tests\test_bridge.py tests\test_coach_dopamine.py -q -p no:cacheprovider --basetemp .pytest-a8c

# (5) 无回归（对照 win32 基线；本测试是基线登记条目，故"减少"应让它在 --strict 下变成"现在通过"）
& $py scripts\check_regressions.py --report .tmp\a8_failures.txt
& $py scripts\check_regressions.py --strict --report .tmp\a8_failures.txt
```

#### 验收标准（可客观判定）

1. 验证 (1) 的 `write lines` **≤ 26**（当前 36）——**这是硬门槛**。
2. `tests/test_p1_neural_takeover.py::TestKpiBaseline::test_control_write_count_shrunk` 转 **PASS**。
3. `tests/test_p1_neural_takeover.py` **全绿**（含 `test_remaining_writes_are_guardrails_or_llm`）。
4. `tests/test_bridge.py` 与 `tests/test_coach_dopamine.py` 的**通过集合不缩小**（`test_bridge.py` 有 6 条在 win32 基线 `environment` 类中，本次实测**当前已通过**——不得因本次改动让它们重新失败）。
5. `scripts/check_regressions.py` 的 `NEW failures` **= 0**；`--strict` 下允许因「基线条目转为通过」而非零（这正是期望的改善信号），但**必须逐条解释**。
6. **禁止项**：`KPI_LINES` / `KPI_ASSIGNMENTS` 的值**必须仍为 26**（`Select-String -Path fly64\tests\test_p1_neural_takeover.py -Pattern 'KPI_LINES|KPI_ASSIGNMENTS'` 可判）。

#### 前置依赖
* **强依赖行动 2**：必须**先**用 `check_regressions.py --update` 把「36 处」吸收为已知基线，
  否则本次「减少写点」会让 `test_control_write_count_shrunk` 从「基线登记为 test-drift」突然变成不同状态，
  干扰「NEW failures = 0」的判定。
* 与行动 4/6 有轻度耦合（都改 `fly64/fly64/model.py` 的多巴胺/LIF 电流），**建议行动 8 排在行动 4、6 之后**避免冲突。

#### 预估工作量
**3–6 人日**（分类与豁免表 1 d、每批 ≤6 处改造 0.5 d × 3–4 批、回归与行为验证 1–2 d）。
⚠️ **这是 12 项里工作量最大、行为风险最高的一项**，建议**在 P2 阶段中期启动**，不要与 P0 并行。

#### 风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| 为求绿而**提高 KPI 预算**（作弊） | 验收 (6) 强制预算仍为 26 | 无（禁止项） |
| 改动决策类写入点 → 运动行为退化（撞墙/卡死/不跳） | 每批 ≤6 处；每批后跑 `test_bridge.py`/`test_coach_dopamine.py` + `--strict` | `git restore fly64/fly64/main.py`（单文件回滚，代价可控） |
| 把护栏写入点误删 → 安全性退化 | 类别 (a) 明确**保留**并登记豁免 | 同上 |
| 与行动 4/6 同时改 `model.py` 产生冲突 | 排期上**串行**（行动 4 → 6 → 8） | 同上 |
| 行为退化无法被离线测试捕捉 | **必须**在 WSL 侧做一次 ≥10 min 的真实会话观察（速度/跳/跌落/卡死计数与改动前对比） | 同上 |

---

### 行动 9 — 教练通路契约测试 【P2-9】

> **必须重写**：旧执行计划要求写 `CoachContract()`、`coach.contract.is_active("implicit_advice")`、
> `coach.serialize()/deserialize()`、`scene_memory.set_danger(...)`、`contract.emit(...)`、`@contract.on(...)`
> —— `CoachContract` / `contract.emit` / `is_active` / `serialize` **全仓 0 命中**。
> 报告 L287 说的「t13 资产可复用」**实际资产是** `fly64/plugin/strategy_writer.py` + `fly64/scripts/audit_contract_pairs.py`；
> 并且已有更贴近目标的现成测试：`fly64/tests/test_coach_contract.py`（**`TestAuditToolIsPresent::test_audit_script_exists` 验证审计脚本存在**）。

#### 目标与动机
把报告的目标「写端（`strategy_writer`）→ 读端（`main.py` / `model.py`）**自动双向校验**」落到**真实存在的资产**上。
现有覆盖（`fly64/tests/test_coach_contract.py`，本次实测通过）已包含：
`TestEveryAdvertisedKeyHasAConsumer`（`:91`，含 `:92 test_no_dead_knob_is_advertised`、`:131 test_the_known_dead_knobs_are_all_gone`）、
`TestSanitizerDropsTheDeadKey`（`:139`）、`TestAuditToolIsPresent`（`:158`）。
**缺口**：这些是**静态键表一致性**检查，**没有**「写一个策略 → 真读回来 → 行为真的变了」的**往返（roundtrip）**证据。

#### 涉及文件

| 路径 | 状态 | 角色 |
|---|---|---|
| `fly64/tests/test_coach_contract.py` | 存在（`_read_keys()` @ `:51`、`consumed()` fixture @ `:83`、3 个 class） | **扩展对象** |
| `fly64/plugin/strategy_writer.py` | 存在（`:27 STRATEGY_PATH = SKILL_DIR / "active_strategy.json"`；`:32 class StrategyWriter`；`:54` 写 `active_strategy.json`；`:75` 合并 `dialogue_decision`） | 写端 |
| `fly64/fly64/main.py` | 存在（`:807 def load_active_strategy(path)`；`:757 def apply_strategy_update`；`:367-374` `/active_strategy-update` 端点；`:987 _active_strategy = dict(ACTIVE_STRATEGY_DEFAULTS)`；`:1225-1304` 热加载消费 `exploration/escape/command/dopamine` 段） | 读端 |
| `fly64/skills/active_strategy.json` | 存在 | 传递介质 |
| `fly64/scripts/audit_contract_pairs.py` | 存在（`ARTIFACTS["skills/active_strategy.json"]` @ `:165`） | 静态双向校验器 |
| `fly64/tests/test_strategy_passthrough.py` | 存在（`:19 from fly64.main import load_active_strategy`） | 相关既有覆盖 |
| `fly64/tests/test_strategy_update_endpoint.py` | 存在（`:33`、`:58-65` 「payload → file → `load_active_strategy()`」的决定性测试） | **已有往返雏形** |
| `fly64/tests/test_dialogue_llm_decision.py` | 存在（原子写、`.tmp` 不残留、损坏文件自愈，`:203-246`） | 相关既有覆盖 |
| `fly64/tests/test_plugin_mhr.py` | 存在（`:259 class TestStrategyWriter`，`:269 from fly64.main import load_active_strategy`） | 相关既有覆盖 |
| `fly64/tests/test_coach_roundtrip.py` | **[待新增]** | 新往返门禁 |
| `fly64/plugin/coach_outcomes.py` | 存在（outcome 归因 + curriculum） | 通路闭环的一环 |
| `fly64/tests/test_coach_pipeline.py` | 存在（`:169-200 TestStrategyExecution` 断言策略参数到达 `active_strategy.json` 且被 `load_active_strategy` 读到） | ⚠️ **它依赖 HTTP 端点**，在 win32 基线中登记为 `unknown`（见行动 2 的分类对象） |

#### 实施步骤

1. 新增 `fly64/tests/test_coach_roundtrip.py`（**离线，用 `tmp_path`，不碰真实 `skills/active_strategy.json`**）：
   * **写→读往返**：`StrategyWriter(strategy_path=tmp_path/"active_strategy.json").write(...)`（参数签名照 `test_autonomy_regression.py:89` 与 `test_plugin_mhr.py:89` 的既有用法）
     → `from fly64.main import load_active_strategy` 读回 → 断言**所有被广告的键**都出现在读回结果里；
   * **反向：读端消费证明**——对每个键在 `fly64/fly64/main.py` 中找出至少 1 处 `_active_strategy.get("<section>")` 读点（复用 `test_coach_contract.py:51 _read_keys` / `:83 consumed` 的机制，**不要重新发明**）；
   * **原子性**：写入过程中不产生可见的中间态（复用 `test_dialogue_llm_decision.py:213-214` 的 `.tmp` 断言口径）；
   * **损坏恢复**：写入 `"{corrupt"` 后 `load_active_strategy` 返回默认值而不抛异常（口径同 `test_dialogue_llm_decision.py:244-246`）；
   * **审计交叉**：断言 `audit_contract_pairs.py` 对 `skills/active_strategy.json` 的输出**不含** `[DEAD-WRITE]`（去重 `test_coach_contract.py:159 test_audit_script_exists` 的既有断言，避免重复）。
2. 扩展 `fly64/tests/test_coach_contract.py`：把「场景语义标签不得下沉进 `active_strategy.json`」这一既有约束（见 `test_what_i_see_protocol.py:378-380`）也在本文件显式断言一次（如未覆盖）。
3. **显式标注未验证项**：`test_coach_pipeline.py::TestServiceCycle` 的 2 条 `live-state` 条目（linux 基线）依赖**常驻服务日志**，Windows 上无法验收 → 在本行动交付物中标注「待 WSL/常驻服务环境验证」，**不得**为了让它变绿而弱化断言。

#### 验证命令

```powershell
# cwd = D:\codes\flygym\fly64
$py = "D:\codes\flygym\.venv\Scripts\python.exe"
$env:PYTHONIOENCODING = "utf-8"

# (1) 新往返门禁
& $py -m pytest tests\test_coach_roundtrip.py -q -p no:cacheprovider --basetemp .pytest-a9

# (2) 既有教练契约测试仍绿
& $py -m pytest tests\test_coach_contract.py -q -p no:cacheprovider --basetemp .pytest-a9b

# (3) 相邻既有覆盖不退化
& $py -m pytest tests\test_strategy_passthrough.py tests\test_strategy_update_endpoint.py tests\test_dialogue_llm_decision.py tests\test_plugin_mhr.py -q -p no:cacheprovider --basetemp .pytest-a9c

# (4) 静态双向校验无新增 dead-write
& $py scripts\audit_contract_pairs.py | Select-String -Pattern 'active_strategy|DEAD-WRITE'

# (5) 幻象 API 仍 0 命中
#     DSH grep: path=fly64, include=*.py, pattern=CoachContract|contract\.emit|is_active|\.serialize\(|set_danger

# (6) 无回归
& $py scripts\check_regressions.py --report .tmp\a9_failures.txt
```

#### 验收标准（可客观判定）

1. `fly64/tests/test_coach_roundtrip.py` 收集数 ≥ 5，**全绿**。
2. `tests/test_coach_contract.py` **全绿**（本次实测已通过，不得退化）。
3. `tests/test_strategy_passthrough.py`、`tests/test_strategy_update_endpoint.py`、`tests/test_dialogue_llm_decision.py` **全绿**（三者本次实测均不在 38 条基线中）。
4. `grep CoachContract|contract\.emit|\.serialize\(|set_danger` 在 `fly64/` 下命中 **0**。
5. `audit_contract_pairs.py` 对 `skills/active_strategy.json` 的 `[DEAD-WRITE]` 计数**不增加**。
6. 无回归：`NEW failures` ≤ 1 且只能是 KPI 那条。

#### 前置依赖
**依赖行动 2**。可与行动 5、7 并行。**不依赖**行动 8。

#### 预估工作量
**1.5–2.5 人日**。

#### 风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| 往返测试误写真实 `fly64/skills/active_strategy.json` | 一律用 `tmp_path`；`test_autonomy_regression.py:89` / `test_plugin_mhr.py:89` 已有同样的 fixture 用法可照抄 | `git restore fly64/skills/active_strategy.json`（被跟踪） |
| 重复已有覆盖 → 无效测试 | 步骤 1 明确「复用 `_read_keys()` / `consumed()`，不重新发明」；验收 5 去重 | 删冗余断言 |
| 弱化 `live-state` 断言以求绿 | 交付物中显式标注「待 WSL 验证」 | 无 |
| 新增测试触发 `.pytest-run` 污染 | §4.1 模板 | `git restore` + `git clean` |

---

### 行动 10 — 度量看板 【P3-10】

#### 目标与动机
报告目标：「Phase 6 收益仪表 + 排行榜 → 自动检测退化」，参考「t14 已就 `scripts/measure_evolution_health.py`」。

**实测现状**：数据侧**已就绪**，展示侧**完全没有**：

| 环节 | 实测 | 状态 |
|---|---|---|
| 度量工具 | `fly64/scripts/measure_evolution_health.py`（468 行）；本次实测 `--json` **exit 0**，输出 `phase6.trials_unique 68 / commits 1 / rollbacks 67 / commit_rate 0.0147 / inert_fraction 0.6667 / delta.p50 0.0 / delta_exactly_zero_fraction 0.6029` 与 `p44.usable_for_signature 0 / signature_reuse_rate 0.0 / outcome_verdicts {unchanged 21, worse 1, improved 8}` | ✅ |
| 趋势落盘 | `--snapshot` 追加 `fly64/skills/evolution_health_trend.jsonl`（**本次实测仅 1 行**，2026-09-18T07:11:59.266765+00:00） | ✅ 但**几乎空** |
| 大脑端点 | `fly64/fly64/main.py:202 elif path == "/evolution.json"`、`:217 "/evolution-log.json"` | ✅ 但有**别的**用途 |
| Web 消费 | `fly64/web/dashboard.js:1156-1185 updateEvolutionDisplay()` 读 `/evolution.json`，取 `brain_version` / `iterations[]`，写入 `brainVerPill` / `evoIterPill` / `evoHistory` | ✅ 但只是**版本与迭代列表**，**不含任何 Phase 6 收益指标** |
| 「排行榜」 | `grep leaderboard\|排行榜\|phase6\|health_trend` 在 `fly64/web/` 下 **0 命中** | ❌ **完全不存在** |

#### 涉及文件

| 路径 | 状态 | 角色 |
|---|---|---|
| `fly64/scripts/measure_evolution_health.py` | 存在（468 行；**无参 = `--phase6 --p44`**；`--snapshot` 是唯一有写副作用的开关） | 数据源（**不改**，或仅加 `--json` 字段） |
| `fly64/skills/evolution_health_trend.jsonl` | 存在（**1 行**） | 数据源 |
| `fly64/fly64/main.py` | 存在（`:198-330` 端点分发；`:202` /evolution.json；`:217` /evolution-log.json；`:2454` 注释「dashboard starts serving /evolution.json」） | 新增端点落点 |
| `fly64/web/dashboard.js` | 存在（1408 行；`:1156-1185`） | 前端改造点 |
| `fly64/web/index.html` | 存在（88 行；header 的 pill 区在 `:4`） | UI 挂载点 |
| `fly64/web/dashboard.css` | 存在（148 行） | 样式 |
| `fly64/web/evo-params.html` | 存在（10196 bytes，`:125` 读 `/evolution-log.json`） | 可参考的既有「演化面板」范式 |
| `fly64/tests/test_dashboard_protocol.py` | 存在（被 `.github/workflows/ci.yml:53` **`--ignore`**；由行动 11 处理） | 协议测试（改动需同步） |
| `fly64/tests/test_dashboard_js.py` | 存在（`:14 def test_javascript_reads_python_packet_and_rejects_corruption`） | 协议测试 |
| `fly64/tests/test_layout_contract.py` | **[待新增]**（行动 12 产出） | 行动 12 会覆盖 UI 布局；本行动改了 UI 则行动 12 的基线必须在其后建立 |

#### 实施步骤

1. **后端**：在 `fly64/fly64/main.py` 新增只读端点（照 `:198-330` 既有 `elif path == …` 的风格），
   两选一：`/evolution-health.json`（推荐，避免污染现有 `/evolution.json` 的 `iterations[]` 消费者）
   或把 `health` 子对象并入 `/evolution.json`（风险：`dashboard.js:1167` 的 `d.iterations` 逻辑与 `test_dashboard_js.py` 可能受影响）。
   **推荐新增独立端点**。数据来源：调用 `scripts/measure_evolution_health.py` 的**函数**（而非 subprocess）或读取 `skills/evolution_health_trend.jsonl`；
   ⚠️ **不得**在 HTTP 处理路径内同步跑 subprocess（`--phase6` 会读 7.8 MB 的 `skills/evolution_log.jsonl`，会阻塞主循环）。
   安全做法：主循环里每 N tick（与 `main.py:2074-2078` 的 `scene_save_counter >= 600` 同范式）**缓存**一次 JSON 到内存，端点只回读缓存。
2. **前端**：在 `fly64/web/dashboard.js` 的 `updateEvolutionDisplay()` 附近新增 `updateEvolutionHealth()`，
   渲染 4 个指标：`phase6.commit_rate`、`phase6.inert_fraction`、`phase6.delta.p50`、`p44.signature_reuse_rate`；
   在 `fly64/web/index.html` 的 header pill 区（`:4`）加一个 `id="evoHealthPill"`（照 `brainVerPill` 的 `class="repulsion-pill"` 范式）。
3. **排行榜（降级为「阶段收益表」）**：报告要的「排行榜」在仓库中**无任何定义**（谁排谁？按什么排？）。
   **降级方案**：改为渲染 `skills/evolution_health_trend.jsonl` 的**逐行趋势表**（ts + trials + commits + delta），
   数据真实、可判定、无需发明排名口径。
   ⚠️ **当前该文件只有 1 行**，所以「趋势」在数据积累前没有意义 → **必须先跑 ≥5 次 `--snapshot`** 或明确接受「表只有 1 行」的现状。
4. **同步协议测试**：`fly64/tests/test_dashboard_protocol.py` 与 `fly64/tests/test_dashboard_js.py` 若断言端点集合，必须同步更新。
5. **`--snapshot` 的写入是唯一副作用**：不要把它接进主循环自动跑（会每 tick 追加一行）。改为手动/定时（例如每日一次），并在文档中写清。

#### 验证命令

```powershell
# cwd = D:\codes\flygym\fly64
$py = "D:\codes\flygym\.venv\Scripts\python.exe"
$env:PYTHONIOENCODING = "utf-8"

# (1) 数据源仍是活的（对照基线：exit 0）
#     ⚠️ exit-code 判定必须【不带管道】：Select-Object -First 会提前终止上游进程，
#        使 $LASTEXITCODE = -1（`--json` 实际输出 93 行）。展示用途另行加管道。
& $py scripts\measure_evolution_health.py --json > $null; "EXIT=$LASTEXITCODE"      # 期望 0
& $py scripts\measure_evolution_health.py --json | Select-Object -First 20          # 仅用于查看
& $py scripts\measure_evolution_health.py --trend

# (2) 新端点存在（源码级 + 运行态）
& $py -c "s=open('fly64/main.py',encoding='utf-8').read();print('endpoint:', '/evolution-health.json' in s)"
Start-Sleep -Seconds 1; (Invoke-WebRequest -Uri 'http://127.0.0.1:8765/evolution-health.json' -TimeoutSec 5).StatusCode   # 需大脑在跑

# (3) 前端接线存在
Select-String -Path web\dashboard.js -Pattern 'evolution-health|evoHealth'
Select-String -Path web\index.html -Pattern 'evoHealthPill'

# (4) 协议测试
& $py -m pytest tests\test_dashboard_protocol.py tests\test_dashboard_js.py -q -p no:cacheprovider --basetemp .pytest-a10

# (5) 无回归
& $py scripts\check_regressions.py --report .tmp\a10_failures.txt
```

#### 验收标准（可客观判定）

1. 验证 (1) 的 `--json` **exit 0**，且 `phase6.inert_fraction == 0.6667`（当前基线值；行动 6 落地后应下降）。
2. 新增端点：源码级命中 ≥1，**且**大脑运行时 `GET` 返回 **200** 且 body 可 `json.loads`（需 WSL/本地大脑进程）。
3. `web/dashboard.js` 与 `web/index.html` 各命中 ≥1。
4. `tests/test_dashboard_protocol.py` + `tests/test_dashboard_js.py` **全绿**。
5. 主循环**不被阻塞**：改动后跑一次 ≥60 s 会话，`main.py` 的 tick 计数与改动前相比无数量级下降（WSL 侧观察；本机可标注「待验证」）。
6. 无回归：`NEW failures` ≤ 1 且只能是 KPI 那条。

#### 前置依赖
* **依赖行动 2**（回归门禁）。
* **与行动 12 有顺序依赖**：行动 10 改了 `web/index.html` / `dashboard.js` / `dashboard.css` → 行动 12 的布局基线必须**在行动 10 之后**建立。
* **与行动 6 有语义依赖（非阻塞）**：`inert_fraction` 是看板的关键指标，行动 6 落地后该指标才有意义的变化。

#### 预估工作量
**2.5–4 人日**（后端端点 + 缓存 1 d、前端 1 d、趋势表降级实现 0.5 d、协议测试同步 0.5–1 d、运行态验证 0.5 d）。

#### 风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| 在 HTTP 处理路径内跑 `measure_evolution_health.py` → 阻塞主循环 | 主循环内**缓存**，端点只读缓存（照 `scene_save_counter` 范式） | 关闭端点（前端退回 `catch(_){}`，`dashboard.js:1179` 已有该容错） |
| 改 `/evolution.json` 破坏 `brainVerPill`/`evoIterPill` | **新增独立端点**，不动 `/evolution.json` | `git restore fly64/web/*.html fly64/web/*.js` |
| 「排行榜」口径不存在 → 造指标 | **降级为趋势表**；若仍要排名，必须先定义口径并单独立项 | 删趋势表 UI |
| `evolution_health_trend.jsonl` 只有 1 行 → 看板空白 | 明示数据现状（1 行），并把「积累 ≥5 行」写成后续动作 | 无 |

---

### 行动 11 — WSL 测试 CI 【P3-11】

> **必须改口径**：报告原文「**WSL 测试 CI**：WSL 上运行全量测试（含 Windows 不可测项）」，参考「基线 11 失败可根治」。
> 实测：`.github/workflows/ci.yml` **已经存在**（66 行，`runs-on: ubuntu-latest`，Python 3.12，`working-directory: fly64`），
> 即「WSL 侧 CI」**已建成**。它的问题不是「不存在」，而是**覆盖面被主动裁剪**：
> `:51-58` 明确 `--ignore` 了 **6 个测试文件**（`test_bridge.py` / `test_dashboard_protocol.py` / `test_dashboard_js.py` /
> `test_plugin_mhr.py` / `test_service.py` / `test_autonomy_regression.py`）**且** `-k "not male_cns and not sm64"`，
> 并且**从不运行** `check_regressions.py`、**不消费** `known_failures.linux.json`。
> 另外「基线 11 失败」的数字本身已失效（实测 linux 基线 **24 条**）。
> 因此本行动 = **补齐既有 CI 覆盖面**，不是新建。

#### 目标与动机
让 linux 基线（24 条）真正成为门禁，并逐步收复 6 个被 ignore 的测试文件。

#### 涉及文件

| 路径 | 状态 | 角色 |
|---|---|---|
| `.github/workflows/ci.yml` | 存在（66 行，`timeout-minutes: 30`，`cache-dependency-path: fly64/requirements.txt`） | **唯一改造对象** |
| `fly64/tests/known_failures.linux.json` | 存在（24 条：`aspirational 16 / environment 1 / live-state 2 / test-drift 3 / unknown 2`） | **门禁基线（当前从未被 CI 消费）** |
| `fly64/scripts/check_regressions.py` | 存在（`--platform linux` + `--report` 支持） | 门禁工具 |
| `fly64/scripts/baseline_tool.py` | **[待新增]**（行动 2 产出） | 基线自检 |
| `fly64/requirements.txt` | 存在 | CI 依赖安装 |
| `fly64/pytest.ini` | 存在 | pytest 配置（若需固定 addopts 在此改） |
| `fly64/pyproject.toml` | **[不存在]** | ✗ 旧计划设想的落点，**禁用**；pytest 配置在 `pytest.ini` |

#### 实施步骤

1. **第一步（零风险）**：在 CI 中把 linux 基线变成门禁，**用 `--report` 模式避免 CI 重跑一遍 pytest**：
   ```yaml
   - name: Run tests (record failure list for the detector)
     run: |
       set +e
       python -m pytest tests/ -q -rf -p no:cacheprovider > /tmp/pytest.txt 2>&1
       tail -20 /tmp/pytest.txt
       exit 0
   - name: Regression gate against the linux baseline
     run: python scripts/check_regressions.py --report /tmp/pytest.txt
   ```
   ⚠️ **注意**：`check_regressions.py` 的 `--report` 用 `FAILED_RE = ^FAILED\s+(\S+)` 解析，所以 pytest **必须带 `-rf`**（短摘要含 `FAILED` 行）。
2. **第二步：逐步去掉 `--ignore`**（一次一个文件，按风险从低到高）：
   `test_autonomy_regression.py` → `test_dashboard_js.py` → `test_dashboard_protocol.py` → `test_plugin_mhr.py` → `test_service.py` → `test_bridge.py`。
   每去掉一个后，若该文件在 linux 上有失败，**必须**在 `known_failures.linux.json` 中登记（带 `cause` + 非空 `note`，否则 `test_regression_detector.py` 的格式门禁会红）。
3. **第三步：逐步放宽 `-k`**：`not male_cns` 的根因是 `.cache/malecns/weights.npz`（~1.3 GB）不在 CI 缓存（见 ci.yml:3 注释与 win32 基线 `test_invariants.py::test_full_graph_incoming_normalization` 的 note）；
   `not sm64` 的根因是原生桥二进制缺失（win32 note：`needs the native sm64 bridge binary, absent on Windows [WinError 2]`）。
   **建议**：`sm64` 相关在 CI 中**保持排除**并写清理由；`male_cns` 若能接受缓存体积则可解锁（需先测缓存命中与超时，`timeout-minutes: 30` 可能不够）。
4. **不要**在 CI 里跑 `--strict`（Linux 上「基线条目现在通过」是常见现象，见 win32 侧 9 条 environment 已转通过的同类现象），除非先 `--update` 收敛。
5. 把 CI 步骤与行动 2（`baseline_tool.py --check --platform linux`）、行动 3（`audit_contract_pairs.py`）**合并成同一次 YAML 改动**，减少冲突。

#### 验证命令

```powershell
# cwd = D:\codes\flygym\fly64 —— 本地只做"可解析性"验证，真正的 ubuntu 验证在 CI

# (1) --report 模式能被正确解析（用一次本地 pytest 的短摘要）
$py = "D:\codes\flygym\.venv\Scripts\python.exe"
& $py -m pytest tests\test_restlessness.py -q -rf -p no:cacheprovider --basetemp .pytest-a11 > .tmp\a11_reported.txt 2>&1
& $py scripts\check_regressions.py --report .tmp\a11_reported.txt --platform win32; "EXIT=$LASTEXITCODE"

# (2) linux 基线自检（行动 2 的工具）
& $py scripts\baseline_tool.py --check --platform linux

# (3) YAML 已挂载（3 处）
Select-String -Path ..\.github\workflows\ci.yml -Pattern 'ignored|--ignore|check_regressions|baseline_tool|audit_contract_pairs' | ForEach-Object { "$($_.LineNumber): $($_.Line.Trim())" }

# (4) linux 基线格式门禁（本机用 linux 基线跑，验证 schema 一致）
& $py -c "import json;d=json.load(open('tests/known_failures.linux.json',encoding='utf-8'));print('count==len:',d['count']==len(d['entries']));print('causes:',sorted({e['cause'] for e in d['entries']}))"
```

#### 验收标准（可客观判定）

1. `.github/workflows/ci.yml` 中同时出现：`-rf`、`check_regressions.py --report`、`baseline_tool.py --check --platform linux`（各命中 ≥1）。
2. CI 的 `--ignore` 数量从 **6** 下降到 **≤3**（解禁至少 3 个文件），**且** 每解禁一个都有相应的 linux 基线登记或全绿证据。
3. `check_regressions.py --report` 在 CI 中对 **linux** 平台运行（`--platform linux` 或依赖 `sys.platform`，二选一并在 YAML 注释里写明）。
4. linux 基线 `count == len(entries) == 24`（或收敛后的 N），**无 `unknown`**（与行动 2 的 `--list-unknown` 呼应）。
5. **CI 必须在合理时间内完成**：`timeout-minutes: 30` 不得被提高来掩盖耗时；若解禁后超时，则该文件回滚到 `--ignore` 并记录原因（**"回滚并记录" 是合格交付**）。
6. 本机（Windows）无法验收 CI 实际执行 → 交付物必须附「CI 运行链接/日志」或在无法触发 CI 时显式标注「待 CI 验证」。

#### 前置依赖
* **强依赖行动 2**（`baseline_tool.py` + linux 基线归类）**与行动 3**（同一个 YAML 的其余两步）。
  ⚠️ 三者的关系是「**同批次提交，无先后依赖**」——行动 2/3/11 都改 `.github/workflows/ci.yml`，任一先做都会与其余产生合并冲突；
  按行动 2 前置依赖的同一口径处理：**无严格拓扑顺序，可并行实施，提交时合并为一次 YAML 改动**。
* 与行动 10 / 12 无依赖，但**行动 10 改前端会新增 `test_dashboard_*` 的覆盖风险** → 建议行动 11 在行动 10 之后做最终一轮 `--ignore` 解禁。

#### 预估工作量
**1–2 人日**（YAML 0.5 d、逐个解禁与登记 0.5–1 d、超时/缓存调优 0.5 d）。

#### 风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| 解禁后 CI 超时（30 min 上限） | 逐文件解禁；超时就回滚该文件并记录（属合格交付） | 恢复对应 `--ignore` 行 |
| `--report` 解析不到 `FAILED` 行（漏 `-rf`） | YAML 里 `-rf` 与本步骤写在同一 `run` 块内；验收 (1) 本地预演 | 恢复为 CI 内直跑 `check_regressions.py`（慢但可靠） |
| linux 基线被 `--update` 污染（吸收真回归） | 同行动 2 的风险条款；`real-bug` 条目必须保留「真缺陷」note | `git restore fly64/tests/known_failures.linux.json` |
| 把 `pyproject.toml` / `.pre-commit-config.yaml` 当落点 | **本文件显式标注两者不存在**；落点只有 `.github/workflows/ci.yml` 与 `fly64/pytest.ini` | 无 |

---

### 行动 12 — CSS 契约测试 【P3-12】

#### 目标与动机
报告目标：「仪表板布局回归探测 → **自动截图 diff**」，动机「多次 CSS 回退历史教训」。

**实测现状：地基已存在，缺的是「契约」与「截图 diff」**：
`fly64/scripts/layout_audit.py`（91 行）**已经是一个 Playwright 布局门禁**，它：
启动 `fly64/web` 的临时静态服务器（`:45-50`），在 4 个视口（`:25 VIEWPORTS = [(1280,1050),(1440,1050),(1680,1050),(1920,1050)]`）渲染，
并以 **exit 1** 判定 4 条门禁：`G1` 水平溢出、`G2` 零尺寸 canvas、`G3` wide 模式下两列差 >5%、`G4` Auto 布局模式与视口匹配。

**两个缺口**：
1. **它不在任何门禁里**（`grep` 显示它未被 CI、未被任何测试引用）→ 有工具无约束。
2. **没有截图 diff**：只做几何探针（`PROBE` @ `:27-35`），不做像素比对；且 `playwright` **未安装在 `.venv`**（实测 `find_spec('playwright')` → `False`）。

另一处相关既有资产：`fly64/tests/test_seqlock_watchdog.py:86` 用 `(PROJECT/"web"/"dashboard.css").read_text()` 做**文本级** CSS 断言（`test_dashboard_freeze_pill_wiring` 相关）——这是本仓库既有的「CSS 契约」范式：**读 CSS 源码断言选择器存在**。本行动应同时提供文本级与渲染级两层。

#### 涉及文件

| 路径 | 状态 | 角色 |
|---|---|---|
| `fly64/scripts/layout_audit.py` | 存在（91 行，Playwright，4 门禁） | **扩展对象（加 `--baseline` 截图 diff）** |
| `fly64/web/index.html` | 存在（88 行） | 渲染对象 |
| `fly64/web/dashboard.css` | 存在（148 行） | 渲染对象 + 文本级契约目标 |
| `fly64/web/dashboard.js` | 存在（1408 行） | 渲染对象 |
| `fly64/web/monitor-preview.html` | 存在（30267 bytes，模拟数据预览页——**截图 diff 的理想稳定靶子**：不依赖 WSL 遥测） | 建议靶子 |
| `fly64/web/layout-wireframe.html` | 存在（15845 bytes） | 备用靶子 |
| `fly64/tests/test_seqlock_watchdog.py` | 存在（`:86` 读 `dashboard.css`；`:1109-1111` 相关的 `test_dashboard_freeze_pill_wiring`） | 文本级 CSS 契约范式来源 |
| `fly64/tests/test_layout_contract.py` | **[待新增]** | 文本级 + 渲染级契约测试 |
| `fly64/scripts/layout_baseline/` | **[待新增目录]** | 截图基线 PNG（**必须入库**，否则 diff 无参照） |
| `playwright`（pip 包 + chromium） | **[未安装]** | ⚠️ 前置：`& $py -m pip install playwright; & $py -m playwright install chromium`（需网络与 ~150 MB 下载） |

#### 实施步骤

1. **先建文本级契约（零依赖，立即可做）**：`fly64/tests/test_layout_contract.py` 读 `fly64/web/dashboard.css` 并断言关键选择器/规则存在：
   * `body.causal-off .causal-ui{display:none!important}`（实测在 `web/dashboard.css:8-9`）；
   * `.stale-pill`（实测在 `web/dashboard.css:108-109`）；
   * `fly64/web/index.html:4` 中的 `id="bridgeStalePill"` 与 `class="stale-pill"`；
   * `fly64/web/index.html:33` 的 `id="memoryHeatmap"`、`:40` 的 `id="stuckChart"`/`id="flowChart"`、`:83` 的 `id="coverageChart"`。
   * 断言 `fly64/web/dashboard.js` 中这些 id 的消费点存在（`$('bridgeStalePill')` 等）。
   这一层**无 playwright、无网络**，可立即进 CI，直接对抗「CSS 回退历史教训」。
2. **渲染级：把 `layout_audit.py` 接进门禁**。两条路：
   * 加入 CI（ubuntu，`pip install playwright && playwright install chromium`）—— ⚠️ 与行动 11 的 `timeout-minutes: 30` 竞争，可能需独立 job；
   * **或**（推荐先做）作为 `fly64/tests/test_layout_contract.py` 中的一个 `@pytest.mark.skipif(playwright unavailable)` 测试，本机有 playwright 时跳过、CI 装了就跑。
3. **截图 diff**：给 `layout_audit.py` 加 `--screenshot-dir` 与 `--baseline-dir`：
   * 首次运行（`--update-baseline`）把 4 个视口的 PNG 写入 `fly64/scripts/layout_baseline/`（**入库**）；
   * 后续运行逐像素比对，差异像素占比 > 阈值（建议 **0.5%**）→ exit 1 并输出差异图路径；
   * 靶子页建议用 `monitor-preview.html`（模拟数据，视图稳定）而非 `index.html`（依赖实时遥测，会自然波动导致假红）。
4. **明确不做**：不引入 `pixelmatch` / `resemble` 等 JS 生态（仓库 `fly64/web/vendor/` 只含 three.js；Python 侧用 Pillow 或 numpy 逐像素即可，避免新增前端构建链）。

#### 验证命令

```powershell
# cwd = D:\codes\flygym\fly64
$py = "D:\codes\flygym\.venv\Scripts\python.exe"
$env:PYTHONIOENCODING = "utf-8"

# (1) 文本级契约（零依赖，必须能跑）
& $py -m pytest tests\test_layout_contract.py -q -p no:cacheprovider --basetemp .pytest-a12

# (2) Playwright 可用性（当前 False → 安装后 True）
& $py -c "import importlib.util as u;print('playwright:',bool(u.find_spec('playwright')))"
# 安装（一次性，需网络）：
# & $py -m pip install playwright ; & $py -m playwright install chromium

# (3) 现有布局门禁仍可运行（安装 playwright 后）
& $py scripts\layout_audit.py; "EXIT=$LASTEXITCODE"        # 期望 exit 0

# (4) 截图 diff 基线生成 + 校验
& $py scripts\layout_audit.py --update-baseline --screenshot-dir scripts\layout_baseline
& $py scripts\layout_audit.py --baseline-dir scripts\layout_baseline; "EXIT=$LASTEXITCODE"

# (5) 反证：故意改坏 CSS 必须被捕获（门禁有效性验证）
#     临时把 dashboard.css 里 .stale-pill 的 display 改掉 → (1) 或 (4) 必须 exit 1 → 再 git restore

# (6) 无回归
& $py scripts\check_regressions.py --report .tmp\a12_failures.txt
```

#### 验收标准（可客观判定）

1. `fly64/tests/test_layout_contract.py` 收集数 ≥ 6，**在当前环境（无 playwright）下全绿**（文本级断言不依赖浏览器）。
2. 安装 playwright 后 `& $py scripts\layout_audit.py` **exit 0**（4 个视口全过 G1–G4）。
3. `fly64/scripts/layout_baseline/` 内 ≥4 个 PNG 被 git 跟踪（`git ls-files fly64/scripts/layout_baseline | Measure-Object -Line` ≥ 4）。
4. **门禁有效性反证**：故意改坏一处 CSS 后，(1) 或 (4) **必须 exit 1**；恢复后 exit 0。（**这是「契约测试真的在测」的唯一硬证据**，必须记录前后两次退出码。）
5. 无回归：`NEW failures` ≤ 1 且只能是 KPI 那条。
6. 新增依赖（playwright + chromium）**写入部署/CI 文档**，且不进入 `fly64/requirements.txt` 的强制路径（否则会拖慢/压垮行动 11 的 CI）——建议放 `fly64/requirements-dev.txt`（**[待新增]**）并在 CI 中按需安装。

#### 前置依赖
* **依赖行动 2**（回归门禁）。
* **依赖行动 10**（行动 10 改 `web/index.html` / `dashboard.js` / `dashboard.css` → **截图基线必须在行动 10 之后建立**，否则基线立刻过期）。
* 无其他依赖。

#### 预估工作量
**2–3.5 人日**（文本级契约 0.5 d、playwright 安装与 CI 接入 0.5–1 d、截图 diff 实现 1 d、反证与文档 0.5 d）。

#### 风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| 截图 diff 在 `index.html` 上频繁假红（实时遥测波动） | 靶子改用 `monitor-preview.html`（模拟数据）；阈值 0.5%；仅比对固定视口 | 关闭截图 diff，保留 `layout_audit.py` 几何门禁（已是既有能力） |
| playwright/chromium 下载 ~150 MB 拖慢 CI | 独立 CI job；放 `requirements-dev.txt`；本机缺失时 `skipif` | 从 CI 移除该步骤 |
| 基线 PNG 入库造成仓库膨胀 | 4 个视口 × 单页，PNG 体积可控；必要时降采样 | `git rm -r --cached fly64/scripts/layout_baseline` |
| 误改 `dashboard.css` 以让基线变绿 | 验收 (4) 的**反证步骤**强制证明门禁有效 | `git restore fly64/web/dashboard.css`（**务必先 git restore 再重跑基线**） |

---

## 3. 依赖图与分阶段排期

### 3.1 依赖图

```
[行动 2 基线工具+分类] ────────────────┐  (P0, 全局前置：所有行动的"无回归"门禁)
        │                              │
        ├── 同批 YAML ──> [行动 3 契约审计制度化] (P0)
        │                              │
        ├──────────────────────────────┼──────────────────────────┐
        ▼                              ▼                          ▼
[行动 1 SM64 自动重启]        [行动 5 课程晋级验证]      [行动 7 CX 回路验收]
   (P0，独立)                    (P1，独立)                 (P1，独立，离线可验收)
        │
[行动 2──update 吸收 10 条 NEW] ──> [行动 8 写 control 36→≤26]  (P2，最大工作量)
                                        ▲
[行动 4 场景→MB 闭环] (P1) ──接口耦合──> [行动 6 DAN 参数化] (P1)
        └────────────────────────────────┘  (若行动4选方案B则强耦合；选A则行动6不阻塞)

[行动 9 教练通路往返] (P2, 独立)

[行动 10 度量看板] (P3) ──必须先于──> [行动 12 CSS 契约/截图基线] (P3)
        └──同批 YAML──> [行动 11 补齐 CI 覆盖面] (P3)
```

> **关键路径（最长链）**：`行动 2 → 行动 4 → 行动 6 → 行动 8`
> 说明：行动 2 是**全局瓶颈**（12 项里有 11 项需要「无回归」判定）；行动 8 是**工作量最大项**（3–6 人日）且**必须排在行动 4/6 之后**以避免同改 `fly64/fly64/model.py`（见行动 8 前置依赖与 §3.2 批次表 B2→B3→B4）。

**可并行的行动组（无相互依赖，可多线推进）**：
* **组 A（P0，第一周）**：行动 1 ∥ 行动 2 → 行动 3（行动 3 必须与行动 2 同批提交，故写为串行收口）
* **组 B（P1，第二周，三线并行）**：行动 5 ∥ 行动 7 ∥ （行动 4 → 行动 6，二者串行）
* **组 C（P2，第三周）**：行动 9 ∥ 行动 8 的第一批（分类与豁免表）
* **组 D（P3，第四周）**：行动 10 → 行动 12 ∥ 行动 11

### 3.2 分阶段排期（按「批次」而非日历日，便于按可用人力伸缩）

| 批次 | 内容 | 并行度 | 预计人日 |
|---|---|---|---|
| **B1（P0 收口）** | 行动 2 → 行动 3（同批 YAML）；行动 1 并行开发 | 2 线 | 4–6.5 |
| **B2（P1 三线）** | 行动 5 ∥ 行动 7 ∥ 行动 4 | 3 线 | 4.5–8（取最长线） |
| **B3（P1 收尾 + P2 起）** | 行动 6（接行动 4）；行动 9 并行 | 2 线 | 4–6.5 |
| **B4（P2 重工）** | 行动 8（36→≤26，分 3–4 批） | 1 线（**独占**，避免与 `model.py` 冲突） | 3–6 |
| **B5（P3 收口）** | 行动 10 → 行动 12；行动 11 与二者同批 YAML | 2 线 | 6–9.5 |
| **合计** | 12 项 | — | **18.5–33.5 人日** |

> 单线（1 人）串行 → 约 **22–37 工作日**；
> 2 人并行 → 约 **14–22 工作日**；3 人并行 → 约 **11–17 工作日**（瓶颈在 B4 行动 8 的独占性）。
> **建议最小配置 = 2 人**：一人负责 P0（B1）+ 行动 8（B4），另一人负责 P1/P3 的独立项（B2/B3/B5）。

### 3.3 建议交付节奏（含明确里程碑）

| 里程碑 | 判定条件（全部可客观验证） |
|---|---|
| **M1「门禁可信」** | 行动 2 + 3 完成：`baseline_tool.py --check` 双平台 exit 0；`--list-unknown` 为空；`test_regression_detector.py` 6 passed；CI 同时挂载 3 个工具 |
| **M2「P0 缺口关闭」** | 行动 1 完成：`test_sm64_watchdog.py` ≥5 全绿；`test_seqlock_watchdog.py` 仍 11 passed；`NEW failures ≤1`（仅 KPI） |
| **M3「行为核心闭环」** | 行动 4 + 5 + 6 + 7 完成：三组新测试全绿；`inert_fraction` 从 0.6667 降到 ≤0.62；`scene_strategy_bindings.json` 出现危险场景条目 |
| **M4「去 Python 化达标」** | 行动 8 完成：`write lines ≤ 26`；`test_control_write_count_shrunk` PASS；`--strict` 的改善逐条解释 |
| **M5「可观测与防腐」** | 行动 9 + 10 + 11 + 12 完成：往返测试全绿；`/evolution-health.json` 返 200；CI `--ignore` ≤3；截图门禁反证通过 |

---

## 4. 附录

### 4.1 「跑测试」类验收的污染处理模板（**每个含 pytest 的行动都必须附**）

> ⚠️ **告诉你的真实发现**：`test_regression_detector.py` 内部调用 `check_regressions.py --report`，而后者的 `run_pytest()` **硬编码 `ROOT/.pytest-run`**，外部 `--basetemp` 无法重定向。
> 本文件各行动中的 `--basetemp .pytest-aN` 能减少直接 pytest 的污染，**但凡是含 `check_regressions.py` 调用的命令，污染必然发生**。
> 因此「清理」不是可选的降级方案，而是**每个 pytest 验收的强制步骤**。

```powershell
# cwd = D:\codes\flygym   —— 在跑任何 pytest 之前/之后各执行一次
git status --porcelain | Measure-Object -Line      # 期望：跑前 3–4，跑后可能 115

# 跑完测试后的标准清理（四行）——【强制执行，不可跳过】
git restore -- fly64/.pytest-run fly64/plugin/.consult_request.json fly64/skills/README.md
git clean -fd fly64/.pytest-run
git status --porcelain                             # 期望回到「原始未跟踪 + 本批次产出」
git diff --stat                                    # 期望：空（除本批次有意改动）
```

* `fly64/.pytest-run/` 有 **132 个文件被 git 跟踪**，且**未被 `.gitignore` 忽略**（`git check-ignore` rc=1）。
* `fly64/plugin/.consult_request.json` / `.consult_response.json` / `.pending_outcome.json` 是**被跟踪的运行期产物**，跑审计/测试会被改写。
* `--basetemp` 可缓解**直接 pytest** 的污染，但对 `check_regressions.py` 的硬编码 `.pytest-run` 路径无效（后者是污染最大来源：93 个已跟踪文件被改写）。**请勿依赖 `--basetemp` 作为干净运行的担保**。
* **根治方案（建议单独立项，不在本轮 12 项内）**：把 `fly64/.pytest-run/` 从 index 移除并写入 `fly64/.gitignore`。
  这属于仓库卫生改动，会一次性消除本文件所有行动的可复现性障碍。**本轮仅记录，不实施**（避免与 12 项行动的范围混淆）。

### 4.2 路径核对结果（本文件引用的**全部**路径，逐条 `Test-Path` 实测）

**说明**：以下 3 张表的每一行都由 `Test-Path`（Windows）实测生成，`EXISTS` / `MISSING` 为原始判定。

#### 表 A — 存在（`EXISTS`）：可直接引用，共 84 条

| # | 路径（相对仓库根） | 角色 |
|---|---|---|
| 1 | `agent.md` | 规则体系（1360 行） |
| 2 | `fly64/fly64/main.py` | 主循环 / `BRAIN_VERSION` / `bridge_stale` / HTTP 端点 |
| 3 | `fly64/fly64/bridge.py` | SeqlockWatchdog / SharedBridge |
| 4 | `fly64/fly64/mushroom_body.py` | MB / MBON / dopamine |
| 5 | `fly64/fly64/central_complex.py` | CX 环吸引子 |
| 6 | `fly64/fly64/memory.py` | MemoryController / navigation_vectors |
| 7 | `fly64/fly64/model.py` | FlyModel / DAN_* / scene_danger / cx 接线 |
| 8 | `fly64/fly64/scene_recognition.py` | SceneRecognizer / danger_level |
| 9 | `fly64/fly64/gain_modulation.py` | DopamineGainController |
| 10 | `fly64/fly64/instinct_bindings.py` | 本能绑定 |
| 11 | `fly64/fly64/replay.py` | 回放（DAN 常量注入） |
| 12 | `fly64/conftest.py` | 测试夹具宿主（**注意不在 `fly64/tests/`**） |
| 13 | `fly64/pytest.ini` | pytest 配置 |
| 14 | `fly64/requirements.txt` | CI 依赖 |
| 15 | `fly64/.gitignore` | 未忽略 `.pytest-run/` |
| 16 | `.gitignore` | 根忽略（含 `export logs/`） |
| 17 | `fly64/skills/skills.md` | 版本徽章 2.23.7 / 2.23.10 |
| 18 | `fly64/skills/evolution_history.json` | 79 条记录 |
| 19 | `fly64/skills/evolution_skill.py` | EvolutionHistory / record_brain_version |
| 20 | `fly64/skills/brain_tunable_params.json` | 21 参数 / 7 wired |
| 21 | `fly64/skills/scene_strategy_bindings.json` | 场景策略绑定 |
| 22 | `fly64/skills/coach_outcomes.jsonl` | 30 行 outcome |
| 23 | `fly64/skills/evolution_log.jsonl` | 7.8 MB 演化语料 |
| 24 | `fly64/skills/evolution_health_trend.jsonl` | 1 行趋势 |
| 25 | `fly64/skills/curriculum.json` | 课程状态（stage 1） |
| 26 | `fly64/skills/active_strategy.json` | 策略热加载文件 |
| 27 | `fly64/scripts/check_regressions.py` | 回归门禁（177 行） |
| 28 | `fly64/scripts/audit_contract_pairs.py` | 契约审计（322 行） |
| 29 | `fly64/scripts/measure_evolution_health.py` | 双环度量（468 行） |
| 30 | `fly64/scripts/consolidate.sh` | 启动契约 |
| 31 | `fly64/scripts/audit_motor_injections.py` | 运动注入审计 |
| 32 | `fly64/scripts/layout_audit.py` | Playwright 布局门禁（91 行） |
| 33 | `fly64/scripts/ver_append_r24.py` | KPI 预算轨迹（18→26） |
| 34 | `fly64/scripts/setup_sm64.sh` | SM64 构建 |
| 35 | `fly64/scripts/start_fly64_full.sh` | **SM64 启动命令出处** |
| 36 | `fly64/scripts/launch_full.sh` | 备用启动 |
| 37 | `fly64/tests/known_failures.win32.json` | win32 基线 38 条 |
| 38 | `fly64/tests/known_failures.linux.json` | linux 基线 24 条 |
| 39 | `fly64/tests/test_p1_neural_takeover.py` | KPI 判据 |
| 40 | `fly64/tests/test_seqlock_watchdog.py` | 看门狗 11 test |
| 41 | `fly64/tests/test_regression_detector.py` | 基线格式门禁 |
| 42 | `fly64/tests/test_evolution_history.py` | 版本记录 |
| 43 | `fly64/tests/test_plugin_mhr.py` | StrategyWriter 覆盖 |
| 44 | `fly64/tests/test_bridge.py` | 桥（6 条 environment） |
| 45 | `fly64/tests/test_dan_shaping.py` | DAN PIN |
| 46 | `fly64/tests/test_mbon_saturation.py` | 饱和（3 条 NEW） |
| 47 | `fly64/tests/test_evo_tunable.py` | 参数范围（1 条 NEW） |
| 48 | `fly64/tests/test_evolution_capability.py` | 演化能力（2 条 NEW） |
| 49 | `fly64/tests/test_tunable_wiring.py` | 接线（1 条 NEW） |
| 50 | `fly64/tests/test_phase6_fitness_inputs.py` | Phase6 输入（1 条 NEW） |
| 51 | `fly64/tests/test_autonomy_regression.py` | 版本契约（unknown） |
| 52 | `fly64/tests/test_coach_pipeline.py` | 教练管线（unknown + 2 live-state） |
| 53 | `fly64/tests/test_coach_contract.py` | **教练契约（行动 9 扩展对象）** |
| 54 | `fly64/tests/test_coach_outcomes.py` | PIN 测试（行动 5） |
| 55 | `fly64/tests/test_curriculum_unknown_metric.py` | 三态（行动 5） |
| 56 | `fly64/tests/test_restlessness.py` | scene_danger 制动（行动 4 回归保护） |
| 57 | `fly64/tests/test_mushroom_body.py` | MB 覆盖（行动 4 回归保护） |
| 58 | `fly64/tests/test_gain_modulation.py` | 增益调制（行动 4/6） |
| 59 | `fly64/tests/test_strategy_passthrough.py` | 策略透传（行动 9） |
| 60 | `fly64/tests/test_strategy_update_endpoint.py` | 往返雏形（行动 9） |
| 61 | `fly64/tests/test_dialogue_llm_decision.py` | 原子写（行动 9） |
| 62 | `fly64/tests/test_what_i_see_protocol.py` | 语义标签不下沉 |
| 63 | `fly64/tests/test_dashboard_protocol.py` | 仪表板协议（CI ignore） |
| 64 | `fly64/tests/test_dashboard_js.py` | JS 协议（CI ignore） |
| 65 | `fly64/tests/test_service.py` | 服务（CI ignore） |
| 66 | `fly64/tests/test_optic_flow.py` | `test_flow_computation_performance`（**real-bug**） |
| 67 | `fly64/tests/test_invariants.py` | `test_launcher_lock_blocks_duplicate`（**real-bug**） |
| 68 | `fly64/plugin/service.py` | 自治服务（无重启逻辑） |
| 69 | `fly64/plugin/watchdog.sh` | **行动 1 的模板** |
| 70 | `fly64/plugin/runner.py` | 10 s 技能周期 |
| 71 | `fly64/plugin/strategy_writer.py` | **写端（行动 9）** |
| 72 | `fly64/plugin/scene_context.py` | SceneMemory（同名异物之一） |
| 73 | `fly64/plugin/coach_outcomes.py` | 课程状态机（行动 5） |
| 74 | `fly64/plugin/llm_consult.py` | 咨询（含 3 处 DEAD-WRITE） |
| 75 | `fly64/plugin/.consult_request.json` / `.consult_response.json` / `.pending_outcome.json` | 审计输入（被跟踪的运行期产物） |
| 76 | `.github/workflows/ci.yml` | **唯一 CI 落点** |
| 77 | `fly64/web/index.html` / `dashboard.js` / `dashboard.css` / `evo-params.html` / `monitor-preview.html` / `layout-wireframe.html` / `memory-heatmap.js` / `trajectory.html` / `trajectory-height.js` | 前端资产 |
| 78 | `fly64/config/`（目录） | 存在但**空目标**（无 `color_profiles.json`） |
| 79 | `fly64/patches/sm64ex-fly64.patch` | SM64 补丁 |
| 80 | `fly64/.tmp/`（目录） | 含 59 个一次性 `.sh`（实测 `(Get-ChildItem fly64/.tmp -Filter *.sh -File).Count` = 59） |
| 81 | `docs/fly64_execution_plan.md` | **历史版本（保留，不修改）** |
| 82 | `docs/fly64_export_logs_analysis_report.md` | 被核对报告 |
| 83 | `docs/analysis/plan-v2/00-facts.md` | T0 事实基准 |
| 84 | `docs/analysis/plan-v2/01-reconciliation.md` | T1 核对基准 |

#### 表 B — 确认**不存在**（`MISSING`）：本文件**不引用其作为前置**，并逐条给出替代方案

| # | 不存在的路径 | 谁在引用它 | 本文件的处置 |
|---|---|---|---|
| **B1** | `fly64/tests/known_failures.json` | 报告 L228/L249；`check_regressions.py:13,53`（文档串与 legacy 回退）；`test_regression_detector.py:8,62`（文档串） | **显式禁用**。替代：`fly64/tests/known_failures.win32.json` / `.linux.json`（平台作用域）。按字面 `open('tests/known_failures.json')` 会 `FileNotFoundError`。行动 2 步骤 0 强制「import 复用 `baseline_path()`」 |
| **B2** | `fly64/plugin/evolution_logs.py` | 旧执行计划 P1-6 | **整条废弃**（旧计划最危险的一条）。替代：行动 6 改 `fly64/skills/brain_tunable_params.json` + `fly64/fly64/model.py` 的 `DAN_*` |
| **B3** | `fly64/config/color_profiles.json` | 旧执行计划 P1-5 / P3-12 | **不引用**。替代：颜色配置真值在 `fly64/fly64/scene_recognition.py:394 SM64_COLOR_PROFILES`，运行期实例在 `:619 self.color_profiles`。若需外置配置文件，属「待新增」，须单独立项 |
| **B4** | `fly64/pyproject.toml` | 旧执行计划 P3-11 | **禁用**。替代落点：`.github/workflows/ci.yml`（唯一）+ `fly64/pytest.ini`（已存在） |
| **B5** | `.pre-commit-config.yaml` | 旧执行计划 P3-11 | **禁用**。同上；若确需 pre-commit，属「待新增」且超出本轮 12 项范围 |
| **B6** | `fly64/plugin/fly64-service.pid` / `fly64/plugin/service.log` | `watchdog.sh:10-11` 的运行时依赖 | **标注为运行期产物**。行动 1 步骤 1 明确「pid 文件不存在即 dead」的陷阱，要求用 `pgrep -f "us_pc.*skip-intro"` 判 SM64 |
| **B7** | `fly64/plugin/service_status.json` | `audit_contract_pairs.py:204`（ARTIFACTS） | **合法 `absent`**（本次实测审计输出即为 `absent`），不视为缺陷 |
| **B7b** | `fly64/plugin/watchdog.log`（及行动 1 的 `sm64-restart.pid`） | 行动 1 实施步骤 2（沿用 `plugin/watchdog.sh:12` 的 `WATCHDOG_LOG` 范式） | **运行期落盘产物，预期不存在**；由 `sm64_watchdog.sh` 首次触发时创建。✅ 实测 `git check-ignore -v fly64/plugin/watchdog.log` → **rc=0，命中根 `.gitignore:23 *.log`**（`service.log` 同）→ `.log` **已在忽略范围内，无须改动**。⚠️ 但 `*.pid` 实测 **rc=1（未被忽略）**：行动 1 交付时应在 `fly64/.gitignore` 增加 `plugin/*.pid`，否则重启 pid 会进 `git status` |
| **B7c** | `.cache/malecns/weights.npz`（~1.3 GB） | 行动 11 步骤 3（`-k "not male_cns"` 的根因路径）；`.github/workflows/ci.yml:3` 注释 | **本机不存在**（实测 `Test-Path fly64/.cache` → `False`）。它是 CI 侧需手动下载缓存的重型数据（ci.yml:3 自述 ~1.3 GB），**不是本计划的交付物**。行动 11 的「`male_cns` 是否解锁」依赖它，属**外部前置**，未解锁不构成缺陷 |
| **B8** | `fly64/skills/coach_advice.json` | `audit_contract_pairs.py:199`（ARTIFACTS） | **合法 `absent`**（同上） |
| **B9** | `fly64/setup.cfg` / `fly64/tox.ini` | 无（本文件核对项） | 无影响；pytest 配置在 `fly64/pytest.ini` |
| **B10** | `fly64/tests/conftest.py` | 报告 T1 §「`tests/conftest.py`」的措辞 | **仅路径措辞偏差**。真实位置 `fly64/conftest.py`（单文件）。引用夹具时**不得**写 `fly64/tests/conftest.py` |
| **B11** | `playwright`（pip 包，非路径） | 行动 12 | **显式前置**：`& $py -m pip install playwright; & $py -m playwright install chromium`（需网络，~150 MB）。建议入 `fly64/requirements-dev.txt`（**[待新增]**）。行动 12 的文本级契约层不依赖它 |

#### 表 C — 本计划**待新增**的资产（不存在的路径，但由行动产出）

| # | 待新增路径 | 产出行动 | 备注 |
|---|---|---|---|
| C1 | `fly64/plugin/sm64_watchdog.sh` | 行动 1 | 复用 `plugin/watchdog.sh` 结构与 `scripts/start_fly64_full.sh:58-61` 的启动命令 |
| C2 | `fly64/tests/test_sm64_watchdog.py` | 行动 1 | ≥5 断言，离线可跑 |
| C3 | `fly64/scripts/baseline_tool.py` | 行动 2 | `--check` / `--diff` / `--list-unknown`，**只读** |
| C4 | `fly64/tests/test_scene_danger_learning.py` | 行动 4 | ≥5 断言；断言 `mushroom.dopamine` 变负 |
| C5 | `fly64/scripts/replay_curriculum.py` | 行动 5 | `--from-jsonl` / `--synthetic`，**只写 `fly64/.tmp/`** |
| C6 | `fly64/tests/test_curriculum_end_to_end.py` | 行动 5 | ≥4 断言 |
| C7 | `fly64/tests/test_cx_navigation_loop.py` | 行动 7 | ≥6 断言；**离线、无 playwright** |
| C8 | `fly64/tests/test_coach_roundtrip.py` | 行动 9 | ≥5 断言；用 `tmp_path` |
| C9 | `fly64/tests/test_layout_contract.py` | 行动 12 | ≥6 断言；文本级层零依赖 |
| C10 | `fly64/scripts/layout_baseline/`（目录 + ≥4 PNG） | 行动 12 | 截图基线，**必须入库** |
| C11 | `fly64/requirements-dev.txt` | 行动 12（建议） | playwright 等开发期依赖，不进 CI 强制路径 |
| C12 | `docs/fly64_execution_plan_v2.md` | **本任务（T2）** | 本文件 |

### 4.3 本文件可靠性声明（能与不能）

**能（可复现）**：
* 所有数字均可用 §0.2 / §4.1 的命令在本机重跑复现；
* 所有 `EXISTS` 路径均经 `Test-Path` 实测；
* 本次为撰写本文件所做的**新增实测**包括：`audit_contract_pairs.py` exit 0 + `TOTAL 8`；`test_seqlock_watchdog.py` + `test_coach_contract.py` + `TestKpiBaseline` 共 21 项（20 passed / 1 failed = KPI）；`test_regression_detector.py` 6 项（5 passed / 1 failed）；`playwright` 不可用；`evolution_health_trend.jsonl` 仅 1 行；9 个 `DAN_*` 常量与 `brain_tunable_params.json` 无 DAN 键；CX 回路已在主循环接线（`main.py:2033-2072` / `model.py:1741-1760`）；3 条 `unknown` 基线条目的具体 id。

**不能（本机 Windows 无法实测，交付前必须由 WSL 侧确认）**：
* 行动 1 的**运行态**（SM64 被 kill 后是否真被重启、`bridge_stale` 是否真转 false）；
* 「WSL 自治服务正在常驻运行」（T0 §8 N5 / T1 U-01）；
* 行动 8 的真实运动行为不退化（需 ≥10 min 会话观察）；
* 行动 10 的 tick 不阻塞、`/evolution-health.json` 返 200；
* 行动 11 的 CI 实际执行（需触发 GitHub Actions）；
* 行动 12 的 Playwright 渲染（本机无 playwright；安装后还需网络）；
* `export logs/` 的 10 个 zip 内容（**未解包**，避免污染工作树）—— 因此报告中「7 会话 / 211 条 CJK 消息 / 41 MB / 16 子代理」等会话内计数**均未验证**。

**本次撰写本文件对仓库的影响**：只新增 `docs/fly64_execution_plan_v2.md` 一个文件；
未修改任何代码、测试、基线、CI 或既有文档（`docs/fly64_execution_plan.md` 与 `docs/fly64_export_logs_analysis_report.md` **原样保留**）。
`fly64/.pytest-run/` 未被执行 pytest 污染（本次运行均使用 `--basetemp .pytest-aN` 独立目录并已清理）。

---

*文件结束。本文件共覆盖 12 项行动（P0×3 / P1×3 / P2×3 / P3×3），与 `docs/fly64_export_logs_analysis_report.md` §5 逐项对应，无丢失、无自造。*
