# 00 — 仓库事实核验与基线采集（T0）

> 任务：t1 [T0] — 仓库事实核验与基线采集
> 执行者：repo-auditor
> 采集时间：2026-09-20（本地会话时区 UTC / 系统本地时间）
> 采集主机：Windows，`sys.platform = win32`
> 解释器：`D:\codes\flygym\.venv\Scripts\python.exe`（Python 3.11.9，MSC v.1938 64bit）
> 命令工作目录：除特别标注外，**命令 cwd 见每条命令块中的 `# cwd=`** 行
> 采集方式：全部为第一手实测（命令 + 原始输出）。凡未能实测者，集中在第 8 节列明。

---

## 0. 结论摘要（先看这里）

| 编号 | 事实 | 判定（对照 `docs/fly64_export_logs_analysis_report.md`） |
|---|---|---|
| F1 | `BRAIN_VERSION = "2.23.11"` @ `fly64/fly64/main.py:39` | 报告 ✅ 一致（报告 L4 写 v2.23.6，但 `docs/fly64_execution_plan.md` L4 写 2.23.11 且指向第 39 行——**报告与执行计划自相矛盾**，实测以 main.py 为准 = 2.23.11） |
| F2 | git HEAD `1badb407…`，分支 `master`，采集前未提交改动 = 3（全为未跟踪） | 报告未声明，本次为首手基线 |
| F3 | win32 基线 `count=38` / `len(entries)=38`；linux `count=24` / `len(entries)=24`（字段与实际条数**一致**） | 报告 ❌ **偏差**：报告 L170/L228/L249/L252 称“36 条” |
| F4 | `agent.md` = **1360 行**（117938 字节，LF，无 BOM） | 报告 ✅ 一致（L4 称 1360 行）；⚠️ PowerShell `Get-Content` 因编码误判给出 **921**，属**工具假象**，非事实 |
| F5 | `audit_contract_pairs.py` / `check_regressions.py` / `measure_evolution_health.py` 均存在于 `fly64/scripts/`，CLI 见第 5 节 | 报告 ✅ 路径存在（均须相对 `fly64/` 解析） |
| F6 | `check_regressions.py` 实测**退出码 1**，非因 baseline 缺失（baseline 命中 `known_failures.win32.json`），而因 **10 条 NEW 失败** | 报告未直接声明退出码，但“基线 36 条 / 11 失败”口径均与实测不符 → 见 F7 |
| F7 | `python -m pytest` 实测 **38 failed, 929 passed, 36 skipped**（216.43s） | 报告 ❌ **严重偏差**：报告 L226 称“~482 通过 / 11 基线失败”，L238/L294 再次称“11 基线失败” |
| F8 | `main.py` 直接写 `control` = **36 行 / 36 处赋值**（KPI 预算 26 → **当前超标 10**） | 报告 ❌ **偏差**：报告 L167/L236/L286 称“35→12 处 / ~12 处” |
| F9 | `fly64/skills/evolution_history.json` = **79 条 records**，**51 个唯一 brain_version 值**（含 1 个字面量 `"None"` → 非空唯一值 **50**） | 报告 ✅ 79 一致；“51 个唯一脑版本”按字面统计成立，但 51 中含字面量 `"None"` 与 `2.11.x` 等非语义版本，**语义唯一版本 = 50** |
| F10 | `check_regressions.py` 会把 pytest 产物写入 **git 已跟踪**的 `fly64/.pytest-run/`（`git ls-files` = 132 个文件），每跑一次回归即污染工作树（实测 115 条改动条目） | 报告未声明 → **新发现，影响后续所有“实测”的可复现性** |

**对下游计划的直接含义（非推测，仅为事实推论边界）**：
- 计划 v2 中凡引用“基线 36 条 / 11 失败 / 写 control 12 处”的行动条目，其**验收基线必须改写为**：win32 38 条、linux 24 条、pytest 38 failed & 929 passed、写 control 36 处。
- 计划 v2 中凡要求“跑 `check_regressions.py` 作为门禁”的条目，必须先解决 `fly64/.pytest-run/` 被跟踪导致的**工作树污染**，否则门禁输出与 `git status` 不可复现。

---

## 1. BRAIN_VERSION 实测（任务项 1）

```powershell
# cwd = D:\codes\flygym
Select-String -Path fly64\fly64\main.py -Pattern 'BRAIN_VERSION' -AllMatches | ForEach-Object { "$($_.LineNumber): $($_.Line.Trim())" }
```

原始输出：

```
39: BRAIN_VERSION = "2.23.11"  # R31-fix12: oscillating displacement gate (progress breaks self-loop)
57: "brain_version": BRAIN_VERSION,
1548: "brain_version": BRAIN_VERSION,
1556: "brain_version": BRAIN_VERSION,
1565: "brain_version": BRAIN_VERSION,
2191: "brain_version": BRAIN_VERSION,
2263: "brain_version": BRAIN_VERSION,
```

**事实**：

| 项 | 值 |
|---|---|
| 定义行号 | **`fly64/fly64/main.py:39`** |
| 值 | **`"2.23.11"`** |
| 同文件行内注释 | `R31-fix12: oscillating displacement gate (progress breaks self-loop)` |
| 引用该常量的 `brain_version` 遥测键 | 第 57、1548、1556、1565、2191、2263 行（共 6 处） |
| 文件总行数 | 2471 行（python `splitlines()`，117938-byte 无关；见第 4 节说明） |

**交叉核对（同一次 grep 覆盖 `fly64/**/*.py`）**：除 `main.py:39` 外无任何其它 `BRAIN_VERSION = "..."` 定义处。`fly64/scripts/check_version.py`、`fly64/tests/check_version.py`、`fly64/scripts/wsl_check2.py` 均以 `from fly64.main import BRAIN_VERSION` 方式读取，非独立定义。

**同仓库内的版本号互相矛盾（实测）**：

```powershell
# cwd = D:\codes\flygym
Get-ChildItem fly64, docs, scripts -Recurse -File -Include *.md,*.py,*.json |
  Select-String -Pattern 'BRAIN_VERSION \*\*2\.23|2\.23\.(7|8|9|10|11)'
```

原始输出（压缩为要点）：

| 位置 | 声明的 BRAIN_VERSION |
|---|---|
| `fly64/fly64/main.py:39` | **2.23.11** |
| `fly64/skills/skills.md:3` | **2.23.7**（SKILL_VERSION 3.4.2） |
| `fly64/skills/skills.md:70` | **2.23.10**（SKILL_VERSION 3.4.2） |
| `docs/fly64_execution_plan.md:4,109` | **2.23.11**（并明确标注“`main.py` 第 39 行”） |
| `docs/fly64_export_logs_analysis_report.md:4,149` | **2.23.6**（称“最新记录为 t17（Brain v2.23.6, Skill 3.4.2）”） |
| `fly64/skills/evolution_history.json` → `canonical_versions` | `{"brain": "2.23.6", "skill": "3.4.2", "as_of": "2026-09-18T01:08:22.683057+08:00"}` |

即：**同一仓库同时对 BRAIN_VERSION 存在 2.23.6 / 2.23.7 / 2.23.10 / 2.23.11 四种声明**。`agent.md` 规则 8「版本三处同步（强制契约）」与规则 15「`--history-check` 必须 OK」在实测状态下**不成立**（对应测试见第 6 节 NEW 失败列表第 1 项）。

---

## 2. git 状态实测（任务项 2）

```powershell
# cwd = D:\codes\flygym
git rev-parse HEAD
git rev-parse --abbrev-ref HEAD
git status --porcelain
git log -1 --format="%H%n%ad%n%s" --date=iso
git describe --tags --always
git rev-list --count HEAD
git rev-parse --abbrev-ref --symbolic-full-name '@{u}'
```

原始输出：

```
1badb4072d27116a967bfaa3dd1d614c133881b9
master
?? .omo/
?? docs/fly64_execution_plan.md
?? docs/fly64_export_logs_analysis_report.md
1badb4072d27116a967bfaa3dd1d614c133881b9
2026-09-20 18:21:21 +0800
chore: add export logs/ to gitignore
causal-baseline-241-g1badb40
305
origin/master
```

**采集前（pristine）基线**：

| 项 | 值 |
|---|---|
| HEAD commit | `1badb4072d27116a967bfaa3dd1d614c133881b9` |
| 分支 | `master`（上游 `origin/master`） |
| HEAD 提交时间 | 2026-09-20 18:21:21 +0800 |
| HEAD 提交标题 | `chore: add export logs/ to gitignore` |
| `git describe` | `causal-baseline-241-g1badb40`（305 个提交） |
| **未提交改动数（`git status --porcelain` 行数）** | **3** |
| 其中：已修改 / 已删除 / 未跟踪 | 0 / 0 / **3** |
| 3 条明细 | `?? .omo/`、`?? docs/fly64_execution_plan.md`、`?? docs/fly64_export_logs_analysis_report.md` |
| `git diff --cached --name-only` | 0（无暂存内容） |

> ⚠️ **重要限定**：以上 3 条是**本次任何测试执行之前**的快照。执行第 6 节的 `check_regressions.py`（它会内部跑全量 pytest）之后，同一命令返回 **115 条**（M=45 / D=66 / ??=4），因为 pytest 写入的 `fly64/.pytest-run/` 中 **132 个文件被 git 跟踪**（见第 6 节）。引用“未提交改动数”时必须注明采集时点。

---

## 3. 已知失败基线实测（任务项 3）

```powershell
# cwd = D:\codes\flygym  (统计脚本经 python - 从 stdin 执行, sys.platform=win32)
```
统计脚本核心：`json.load(open(...))` → 打印 `count` 字段、`len(entries)`、`set(id)` 去重数、`collections.Counter(cause)`。

### 3.1 `fly64/tests/known_failures.win32.json`

```json
{ "platform": "win32", "recorded_at": "2026-09-18T08:05:26.164237+00:00", "count": 38, "entries": [ ... ] }
```

原始输出：

```
--- fly64\tests\known_failures.win32.json
  count field    : 38
  len(entries)   : 38
  platform       : win32 | recorded_at: 2026-09-18T08:05:26.164237+00:00
  unique ids     : 38
  cause dist     : {'aspirational': 16, 'environment': 14, 'real-bug': 2, 'test-drift': 3, 'unknown': 3}
  top-level keys : ['platform', 'recorded_at', 'count', 'entries']
```

| 项 | 值 |
|---|---|
| `count` 字段 | **38** |
| `len(entries)` 实际条数 | **38**（**一致**，无漂移） |
| `entries.id` 去重后 | **38**（无重复条目） |
| `cause` 分布 | `aspirational=16`、`environment=14`、`real-bug=2`、`test-drift=3`、`unknown=3`（合计 38） |
| 有 `cause` 但 `note` 为空的条目 | 0（但 `unknown` 类共 3 条，其 `note` 本身合法为空串） |
| 文件字节数 / 最后修改 | 11228 bytes / 2026-09-18 16:05:26 |
| 引入该文件的 commit | `d37c15ea92829e5934f688176b0202cf5d4c2442`（2026-09-18 16:08:05 `EVO-071 follow-up: compute_flow dead-code removal + performance threshold update`） |
| 是否被 git 跟踪 | **是**（`git ls-files` 命中） |

### 3.2 `fly64/tests/known_failures.linux.json`

原始输出：

```
--- fly64\tests\known_failures.linux.json
  count field    : 24
  len(entries)   : 24
  platform       : linux | recorded_at: 2026-09-18T08:07:39.713106+00:00
  unique ids     : 24
  cause dist     : {'aspirational': 16, 'environment': 1, 'live-state': 2, 'test-drift': 3, 'unknown': 2}
  top-level keys : ['platform', 'recorded_at', 'count', 'entries']
```

| 项 | 值 |
|---|---|
| `count` 字段 | **24** |
| `len(entries)` 实际条数 | **24**（**一致**） |
| `cause` 分布 | `aspirational=16`、`environment=1`、`live-state=2`、`test-drift=3`、`unknown=2`（合计 24） |
| 文件字节数 / 最后修改 | 7749 bytes / 2026-09-18 16:07:39 |
| 引入 commit | 同 `d37c15ea92829e5934f688176b0202cf5d4c2442` |
| 是否被 git 跟踪 | **是** |

### 3.3 两平台交集实测

原始输出：

```
--- cross
  win32 unique: 38 linux unique: 24
  intersection: 22
  win32-only  : 16
  linux-only  : 2
```

| 项 | 值 |
|---|---|
| 交集 | 22 |
| 仅 win32 | 16 |
| 仅 linux | 2 |

`live-state` 分类**只出现在 linux 基线**（2 条，均为 `tests/test_coach_pipeline.py::TestServiceCycle::*`，读取常驻服务日志）。

### 3.4 报告中与之冲突的原话（原文摘录，便于比对）

| 报告位置 | 原话 | 实测 |
|---|---|---|
| L170 | `| 回归基线 | v2.23.5 | 36 条已知失败基线分类管理 |` | win32 = 38 |
| L226 | `| 总测试用例 | ~482 通过 / 11 基线失败（Windows 环境） |` | 929 passed / 38 failed |
| L228 | `| 基线管理 | tests/known_failures.json —— 36 条基线（13 env + 余下分类） |` | 文件为 `known_failures.win32.json`（无未限定名文件，见下）；38 条；env = 14 |
| L238 | `| LSP 状态 | 11 基线失败（均为 Windows 环境问题：clock_gettime_ns/invariants/retina） |` | 38 failed，其中 14 为 environment |
| L252 | `### 4.4 已知基线失败（36 条）` 及下表“Windows 环境 13” | | 38 条 / environment 14 |
| L294 | `| 11 | **WSL 测试 CI** | ... | 基线 11 失败可根治 |` | 38 failed |

**补充实测**：`fly64/tests/known_failures.json`（未限定名的 legacy 文件）**不存在**（`Test-Path` → `False`）。`check_regressions.py:41-54` 的 `baseline_path()` 逻辑为“优先 `known_failures.<sys.platform>.json`，否则回退 legacy”，实测 win32 下**命中 scoped 文件**，未走 legacy 分支。

---

## 4. `agent.md` 行数实测（任务项 4）

```powershell
# cwd = D:\codes\flygym
python - <<'PY'
from pathlib import Path
b = Path("agent.md").read_bytes()
print("size bytes           :", len(b))
print("BOM                  :", b[:3] == b"\xef\xbb\xbf", b[:3])
print("count of \\n          :", b.count(b"\n"))
print("count of \\r\\n        :", b.count(b"\r\n"))
t = b.decode("utf-8")
print("len(splitlines())    :", len(t.splitlines()))
PY
```

原始输出：

```
size bytes           : 117938
BOM                  : False b'# F'
count of \n          : 1359
count of \r\n        : 0
count of bare \r     : 0
split('\n') elements : 1360
lines if file ends with \n => logical lines: 1360
len(splitlines())    : 1360
```

| 项 | 值 |
|---|---|
| **`agent.md` 实际行数** | **1360** |
| 字节数 | 117938 |
| 行尾 | 全 `LF`（`\r\n` 计数 0，裸 `\r` 计数 0） |
| BOM | 无 |
| 路径 | 仓库根 `D:\codes\flygym\agent.md`（**`fly64/agent.md` 不存在**，实测 `NOT FOUND`） |
| 文件数 | 全仓库仅此一份 `agent.md`（排除 `.venv` / `.git` / `node_modules` 后穷举） |

### ⚠️ 工具假象警告（重要，影响后续所有行数统计）

```powershell
# cwd = D:\codes\flygym
(Get-Content agent.md).Count                 # → 921       ❌ 错误
(Get-Content fly64\fly64\main.py).Count      # → 2464      ❌ 错误
```

Python 实测对照：

```
agent.md                                                     1360 lines
fly64/fly64/main.py                                          2471 lines
fly64/skills/skills.md                                        367 lines
fly64/scripts/check_regressions.py                            177 lines
fly64/scripts/audit_contract_pairs.py                         322 lines
fly64/scripts/measure_evolution_health.py                     468 lines
docs/fly64_export_logs_analysis_report.md                     314 lines
fly64/tests/test_p1_neural_takeover.py                        267 lines
```

**结论**：本仓库源码/文档含大量 UTF-8 中文，PowerShell `Get-Content` 在默认编码下**低估行数约 32%**（agent.md：921 vs 1360）。**任何行数类事实必须用 Python（`read_bytes().decode('utf-8').splitlines()`）采集**，否则会产生系统性假偏差。报告 L4 的“agent.md 1360 行”**是正确的**。

---

## 5. 三个报告相关脚本的存在性与 CLI（任务项 5）

```powershell
# cwd = D:\codes\flygym
foreach ($n in @('audit_contract_pairs.py','check_regressions.py','measure_evolution_health.py')) {
  $p = "fly64\scripts\$n"
  if (Test-Path $p) { "$n : EXISTS ($((Get-Item $p).Length) bytes)" } else { "$n : NOT FOUND" } }
```

原始输出：

```
audit_contract_pairs.py : EXISTS (11795 bytes)
check_regressions.py : EXISTS (6424 bytes)
measure_evolution_health.py : EXISTS (20246 bytes)
```

全仓库穷举（按文件名）也仅命中同一组路径：

```
D:\codes\flygym\fly64\scripts\audit_contract_pairs.py
D:\codes\flygym\fly64\scripts\check_regressions.py
D:\codes\flygym\fly64\scripts\measure_evolution_health.py
```

`fly64/scripts/` 下文件总数 = **111**。

### 5.1 `audit_contract_pairs.py`（322 行）

```powershell
# cwd = D:\codes\flygym
D:\codes\flygym\.venv\Scripts\python.exe fly64\scripts\audit_contract_pairs.py --help
```

原始输出：

```
usage: audit_contract_pairs.py [-h] [--json] [--all]

options:
  -h, --help  show this help message and exit
  --json
  --all       also print keys classified ok
EXIT=0
```

| 项 | 值 |
|---|---|
| argparse 选项 | `--json`、`--all`（无其它） |
| 默认 baseline 路径 | **无 baseline 概念**；硬编码 `ARTIFACTS` 字典（9 个契约产物，`ROOT = Path(__file__).resolve().parent.parent` = `fly64/`）；对每个产物读**实时文件**（`live_keys(rel)`），文件不存在即记 `absent` |
| 其它无参可运行性 | ✅ 实测 `--help` 与无参运行均 exit 0 |

### 5.2 `check_regressions.py`（177 行）

```powershell
# cwd = D:\codes\flygym
D:\codes\flygym\.venv\Scripts\python.exe fly64\scripts\check_regressions.py --help
```

原始输出：

```
usage: check_regressions.py [-h] [--report REPORT] [--strict] [--update]
                            [--platform PLATFORM]

options:
  -h, --help           show this help message and exit
  --report REPORT
  --strict
  --update
  --platform PLATFORM
EXIT=0
```

| 项 | 值 |
|---|---|
| argparse 选项 | `--report`、`--strict`、`--update`、`--platform`（默认 `sys.platform`） |
| **默认 baseline 路径** | `ROOT/tests/known_failures.<platform>.json`，其中 `ROOT = Path(__file__).resolve().parent.parent` = **`fly64/`**；若 scoped 文件不存在则回退 `ROOT/tests/known_failures.json`（L41–54） |
| 实测 win32 下的解析结果 | `fly64/tests/known_failures.win32.json`（存在 → 命中，未回退） |
| `--update` 行为 | 用本次结果**重写** baseline 文件（`count = len(entries)`） |
| 退出码语义 | `rc = 1 if new else 0`；`--strict` 时若存在“基线条目已通过”亦置 1 |
| 运行 pytest 的方式 | `sys.executable -m pytest -q -rf --basetemp ROOT/.pytest-run -p no:cacheprovider`，`cwd=ROOT`，并把 `TMP`/`TEMP` 指向 `fly64/.pytest-run` |

### 5.3 `measure_evolution_health.py`（468 行）

```powershell
# cwd = D:\codes\flygym
D:\codes\flygym\.venv\Scripts\python.exe fly64\scripts\measure_evolution_health.py --help
```

原始输出：

```
usage: measure_evolution_health.py [-h] [--phase6] [--p44] [--snapshot] [--trend] [--json]

options:
  -h, --help  show this help message and exit
  --phase6
  --p44
  --snapshot  append a trend row (implies both sections)
  --trend     print the accumulated trend and exit
  --json
EXIT=0
```

| 项 | 值 |
|---|---|
| argparse 选项 | `--phase6`、`--p44`、`--snapshot`、`--trend`、`--json` |
| 默认参数行为 | **不带任何开关 = `--phase6 --p44`**（L364-365）；`--snapshot` 隐含两者 |
| 默认输入路径（`ROOT = fly64/`） | `skills/evolution_log.jsonl`、`skills/brain_tunable_params.json`、`skills/scene_strategy_bindings.json`、`skills/coach_outcomes.jsonl` |
| 唯一有写副作用的开关 | `--snapshot` → **追加** `skills/evolution_health_trend.jsonl`；其余全只读（文档串自述 “Both sections are read-only”） |
| 无 baseline 概念 | 是（自带基线常量在 `--phase6` 的打印文案里，见下） |

**实测运行结果（`--json`，cwd=`fly64/`，exit 0）**：

```json
{
 "generated_at": "2026-09-20T13:58:10.599075+00:00",
 "phase6": {
  "trials_unique": 68, "params_total": 21, "params_wired": 7, "params_inert": 14,
  "inert_fraction": 0.6667, "commits": 1, "rollbacks": 67, "commit_rate": 0.0147,
  "delta": {"min": -0.0443, "p50": 0.0, "max": 0.0397, "mean": -0.0018},
  "delta_exactly_zero": 41, "delta_exactly_zero_fraction": 0.6029,
  "delta_abs_lt_threshold": 66, "delta_abs_lt_threshold_fraction": 0.9706,
  "commits_by_wired_dims_moved": {"4": 1},
  "commits_by_inert_dims_moved": {"12": 1},
  "noise_commits": 0, "noise_commit_fraction": 0.0,
  "moved_dimensions_total": {"wired": 264, "inert": 798, "inert_share": 0.7514}
 },
 "phase6_instrumented_trials": 0,
 "p44": {
  "scenes": 1, "signatures": 2, "promoted": 0, "by_improved": {"1": 2},
  "outcomes_total_lines": 30,
  "outcome_verdicts": {"unchanged": 21, "worse": 1, "improved": 8},
  "usable_for_signature": 0,
  "skipped_no_scene_label": 30, "skipped_no_keys": 0,
  "distinct_signatures_from_outcomes": 0,
  "outcomes_reusing_an_existing_signature": 0,
  "signature_reuse_rate": 0.0
 }
}
```

> 注：`p44.scene` 值实测为 UTF-8 中文场景名（非 ASCII 直出时 Windows 控制台会乱码；加 `PYTHONIOENCODING=utf-8` 后正常）。此处未回填场景名字面值以免引入转写误差，需要时由下游脚本直接读取 JSON。

### 5.4 `audit_contract_pairs.py` 实测运行（cwd=`fly64/`，exit 0）

末尾原始输出：

```
### plugin/.consult_request.json
    scanned 2 .py + 0 web file(s), 4 keys
    [DEAD-WRITE      ] context.kind                                 w=1 r=0 decl=0
        W plugin/llm_consult.py:304
    [loop-read-only  ] context.stuck_duration                       w=0 r=0 decl=1

### plugin/.consult_response.json
    scanned 2 .py + 0 web file(s), 4 keys
    [DEAD-WRITE      ] strategy.exploration                         w=1 r=0 decl=0
        W plugin/llm_consult.py:128
    [DEAD-WRITE      ] strategy.exploration.turn_bias               w=1 r=0 decl=0
        W plugin/llm_consult.py:130

### skills/coach_advice.json
    absent

### plugin/service_status.json
    absent

==============================================================================
TOTAL dead-writes + silent-defaults: 8
```

| 项 | 值 |
|---|---|
| 退出码 | **0**（工具正常，非门禁类型） |
| `TOTAL dead-writes + silent-defaults` | **8** |
| `--all` 亦实测 exit 0（未崩溃） | ✅ |

---

## 6. `check_regressions.py` 实测退出码与输出（任务项 6）

```powershell
# cwd = D:\codes\flygym\fly64
D:\codes\flygym\.venv\Scripts\python.exe scripts\check_regressions.py
# 实测耗时 218.2 s
```

原始输出（完整）：

```
running pytest ...
==============================================================================
REGRESSION CHECK  (baseline win32, 38 entries)
==============================================================================
  failing now      : 38
  still failing    : 28 (known)
  NEW failures     : 10
  baseline entries that now PASS : 10
  known failures by cause: aspirational=16, environment=5, real-bug=2, test-drift=3, unknown=2

  !!! NEW FAILURES (a regression, or an unclassified pre-existing one):
      tests/test_dan_shaping.py::TestDanShaping::test_lowered_reward_weakens_mbon_saturation
      tests/test_evo_tunable.py::TestEvoTunable::test_params_have_ranges
      tests/test_evolution_capability.py::TestWallCornerPattern::test_pattern_in_catalog
      tests/test_evolution_capability.py::TestWallCornerPattern::test_pattern_matches_on_mismatch
      tests/test_mbon_saturation.py::TestMbonSaturationHomeostasis::test_mbon_returns_to_dynamic_range_after_scaling
      tests/test_mbon_saturation.py::TestMbonSaturationHomeostasis::test_saturated_column_scaling_fires
      tests/test_mbon_saturation.py::TestMbonSaturationHomeostasis::test_saturation_events_counter_increments
      tests/test_phase6_fitness_inputs.py::TestNoSilentDefaults::test_real_sample_reports_no_missing_inputs
      tests/test_regression_detector.py::TestBaselineIsWellFormed::test_every_entry_has_a_cause_and_note
      tests/test_tunable_wiring.py::TestPanelMarksInertSliders::test_panel_disables_inert_sliders

  baseline entries that now pass (refresh with --update):
      tests/test_bridge.py::test_bridge_round_trip
      tests/test_bridge.py::test_game_status_reads_applied_bz_bits
      tests/test_bridge.py::test_simulator_does_not_override_game_toggle
      tests/test_bridge.py::test_write_control_b_and_z_combined
      tests/test_bridge.py::test_write_control_level_buttons_do_not_stick
      tests/test_bridge.py::test_write_control_z_button
      tests/test_invariants.py::test_torn_frames_return_last_good_frame
      tests/test_regression_detector.py::TestDetectorDetects::test_reports_clean_against_its_own_baseline
      tests/test_retina.py::test_clean_break_rejects_old_images_and_protocol
      tests/test_retina.py::test_pose_and_pixels_share_the_frame_seqlock

  pytest: 38 failed, 929 passed, 36 skipped in 216.43s (0:03:36)
EXITCODE=1
```

### 6.1 直接回答任务项 6 的两个子问题

| 子问题 | 实测答案 |
|---|---|
| 是否因 **baseline 缺失** 而失败？ | **否**。输出首行明确 `(baseline win32, 38 entries)`，即成功解析到 `fly64/tests/known_failures.win32.json` 并读到 38 条。 |
| 是否因 **路径不符** 而失败？ | **否**。`ROOT=fly64/` 推导正确；`cwd=fly64/` 下 `scripts/check_regressions.py` 正常执行；内部 pytest 亦以 `cwd=fly64/` 运行成功（929 passed）。 |
| 那么为何 exit=1？ | **因为 10 条 NEW failures**（`rc = 1 if new else 0`，`check_regressions.py:168`）。 |

### 6.2 与基线相关的两项附带实测

1. **`environment` 类失败数由 14 降到 5（“now failing”口径）**：输出行 `known failures by cause: aspirational=16, environment=5, real-bug=2, test-drift=3, unknown=2` 只统计**当前仍在失败**的基线条目（合计 28），因此 environment 显示 5 而非基线文件里的 14。
2. **10 条“已通过”的基线条目全部集中在 environment(9) + unknown(1)**；其中 6 条属 `test_bridge.py::*`（`clock_gettime_ns` 类）。这说明**基线的 environment 注释在当前主机已部分过期**，`--strict` 会因此额外失败。

### 6.3 ⚠️ 新发现：跑一次回归会污染 git 工作树

```powershell
# cwd = D:\codes\flygym
git ls-files fly64/.pytest-run | Measure-Object -Line      # → 132
git status --porcelain | Measure-Object -Line              # 采集前 3 → 跑完 pytest 后 115
git check-ignore -v fly64/.pytest-run/...                  # rc=1（未被忽略）
```

| 项 | 实测 |
|---|---|
| `fly64/.pytest-run/` 中被 git 跟踪的文件数 | **132** |
| `fly64/.gitignore` 是否忽略 `.pytest-run/` | **未列出**（只忽略 `.venv/ .cache/ runtime/ artifacts/ private/ rom/ *.z64 *.n64 *.v64 __pycache__/ .pytest_cache/ .DS_Store`） |
| 根 `.gitignore` 是否忽略 | 也未列出（`git check-ignore` rc=1） |
| 跑 pytest 后 `git status --porcelain` 行数 | **115**（M=45 / D=66 / ??=4） |
| 根 `.gitignore` 中新增的忽略项 | `export logs/`（HEAD 提交即为此） |

**影响**：任何“以 `git status` 干净度或 `git diff` 内容为证据”的验收步骤在本仓库当前状态下都不可复现；且 `check_regressions.py` 本身就会制造 132 个被跟踪产物文件的读写 + 约 75 个**未跟踪**的新增目录（编号递增的 `test_*1/`、`tmp*/`）。**这不是推测，是实测**（同一次会话内前后两次 `git status --porcelain` 分别为 3 与 115）。

**本任务已执行的清理（已恢复原状，供后续审计确认）**：

```powershell
# cwd = D:\codes\flygym
git restore -- fly64/.pytest-run fly64/plugin/.consult_request.json fly64/skills/README.md   # rc=0
git clean -fd fly64/.pytest-run                                                             # rc=0，移除约 75 个未跟踪目录/文件
git status --porcelain   # → 4 条（3 条原始未跟踪 + 本任务产出 docs/analysis/plan-v2/）
git diff --stat          # → 空（无已跟踪文件被改动）
```

> 即：本文件第 2 节的“未提交改动数 = 3”在清理后**依旧成立**；本任务未在本仓库留下除 `docs/analysis/plan-v2/00-facts.md` 之外的文件改动。

---

## 7. `main.py` 直接写 `control` 的处数（任务项 7）

**判据来源**：KPI 定义在 `fly64/tests/test_p1_neural_takeover.py:233-242`（`class TestKpiBaseline`），其正则与预算即本仓库的“直接写 control”官方口径：

```python
KPI_LINES = 26
KPI_ASSIGNMENTS = 26
def test_control_write_count_shrunk(self, main_src):
    lines = main_src.splitlines()
    write_lines = [i + 1 for i, l in enumerate(lines)
                   if re.search(r"\bcontrol\.\w+\s*=[^=]", l)]
    assignments = re.findall(r"\bcontrol\.\w+\s*=[^=]", main_src)
    assert len(write_lines) <= self.KPI_LINES, f"write lines {len(write_lines)}"
    assert len(assignments) <= self.KPI_ASSIGNMENTS, f"assignments {len(assignments)}"
```

### 7.1 grep 命令与计数

```powershell
# cwd = D:\codes\flygym   —— 等价于测试正则的 grep（PowerShell 计数）
Select-String -Path fly64\fly64\main.py -Pattern '\bcontrol\.\w+\s*=[^=]' -AllMatches |
  Measure-Object -Line
```

同口径的 python 精确计数（含逐处行号）：

```
PATTERN      : \bcontrol\.\w+\s*=[^=]
write LINES  : 36
assignments  : 36
```

**结果**：

| 项 | 实测值 | KPI 预算 | 结论 |
|---|---|---|---|
| 直接写 `control` 的**行数** | **36** | 26 | **超标 10** |
| 直接写 `control` 的**赋值次数** | **36** | 26 | **超标 10** |

36 处逐行清单（原始输出，行号 + 原始代码）：

```
  line 726   control.x = int(np.clip(round(control.x + dx), -80, 80))
  line 727   control.y = int(np.clip(round(control.y + dy), -80, 80))
  line 1319  control.x = turn_dir
  line 1320  control.y = -10  # brief reverse in SM64
  line 1336  control.x = int(cliff_turn_bias)
  line 1338  control.y = 8
  line 1400  control.x = action["control_x"]
  line 1401  control.y = action["control_y"]
  line 1402  control.jump = action["jump"]
  line 1608  control.x = int(60 * (1 if (model.step_count // 20) % 2 else -1))
  line 1609  control.y = -60
  line 1610  control.jump = False
  line 1616  control.x = 0
  line 1617  control.y = 0
  line 1618  control.jump = False
  line 1619  control.b = False
  line 1631  control.b = True
  line 1633  control.jump = True
  line 1639  control.jump = True   # autonomous A fallback
  line 1646  control.b = False
  line 1655  control._cmd_start = tick_start
  line 1656  control._cmd_active = True
  line 1668  control.x = int(max(-70, min(70, _yaw_diff * 40)))
  line 1669  control.y = int(_cmd.get("y", 70))
  line 1670  control.jump = bool(_cmd.get("jump", False))
  line 1672  control._cmd_active = False
  line 1682  control._below_ground_jump_start = time.monotonic()
  line 1683  control._below_ground_jumping = True
  line 1691  control.jump = True
  line 1694  control.x = int(30.0 * (_phase / 3.14159 - 1.0))
  line 1695  control.y = 70
  line 1697  control._below_ground_jumping = False
  line 1705  control.y = max(control.y, 70)
  line 1706  control.jump = True
  line 1882  control.jump = False
  line 1883  control.y = -70
```

### 7.2 该测试的实测结果

```powershell
# cwd = D:\codes\flygym
D:\codes\flygym\.venv\Scripts\python.exe -m pytest fly64\tests\test_p1_neural_takeover.py -k "control_write_count_shrunk" -q -p no:cacheprovider
```

原始输出（末尾）：

```
    def test_control_write_count_shrunk(self, main_src):
        ...
>       assert len(write_lines) <= self.KPI_LINES, f"write lines {len(write_lines)}"
E       AssertionError: write lines 36
E       assert 36 <= 26
E        +  where 36 = len([726, 727, 1319, 1320, 1336, 1338, ...])
E        +  and   26 = <test_p1_neural_takeover.TestKpiBaseline object ...>.KPI_LINES

fly64\tests\test_p1_neural_takeover.py:238: AssertionError
=========================== short test summary info ============================
FAILED fly64\tests\test_p1_neural_takeover.py::TestKpiBaseline::test_control_write_count_shrunk
1 failed, 21 deselected in 0.26s
EXIT=1
```

该测试在基线中被登记为 `test-drift`（win32 基线第 117-120 行），`note` 为 “asserts a control-write line count that drifted as the motor path changed”。

### 7.3 相关历史数字的实测出处

```powershell
# cwd = D:\codes\flygym
Get-ChildItem fly64\skills, fly64\docs, docs -Recurse -File -Include *.md,*.json |
  Select-String -Pattern 'control.{0,20}(35|12)\s*(处|site|line)'
```

仅命中报告自身：

```
docs\fly64_export_logs_analysis_report.md:167: | 去 Python 化 | v2.8.0 | main.py 写 control 35→12 处 |
docs\fly64_export_logs_analysis_report.md:236: | main.py 直接写 control | ~12 处（从 35 处下降） |
docs\fly64_export_logs_analysis_report.md:286: | 8 | **main.py 写 control 清零** | 从 ~12 处降至 0，全 LIF 网络决策 | P1 进化轮（2.8.0）已移除 23 处 |
```

仓库中**可实测的** P1 KPI 预算演变记录只有：`fly64/scripts/ver_append_r24.py:37` 中 `"2.17.0 M1.1: ... P1 直写 KPI 预算化（18→26 附豁免表）"`。**“35→12 处”在仓库中找不到可核验的第二手来源**（不排除原文出自导出会话聊天记录，但导出 zip 未在本任务范围内解包）。

---

## 8. 无法实测的部分（明确列出，禁止外推）

| 编号 | 无法实测项 | 原因 | 已尝试的动作 |
|---|---|---|---|
| N1 | 报告“7 会话 × 79 条脑版本演化”中**7 个会话**的对应关系 | `export logs/` 下实为 **10 个 zip、9 个不同 session id**；报告点名的 `a909a5cd / 9e9d4023 / 047eec9d / 493fe29d` 四个短 id 在文件名中**不出现**（文件名可确认存在的只有 `38542b1c / 99cab60f / f953d3fd`） | 只做了目录枚举与文件名正则提取；**未解包 zip**（解包会显著扩大范围并污染工作树） |
| N2 | 报告 L107 “从 evolution_history.json（79 条记录）”的**时间跨度** | 79 条记录中只有 63 条含 `date`、16 条含 `recorded_at`；`canonical_versions.as_of = 2026-09-18T01:08:22+08:00`，**没有任何记录晚于 09-18**，与报告 L4/L21 的 “2026-09-20 / 09-11~09-20 9 天” 不一致 | 已统计字段频次（`date`=63、`recorded_at`=16）与 id 范围（`EVO-001`→`EVO-071`），未做跨源时间对账 |
| N3 | BRAIN_VERSION **2.23.7 / 2.23.8 / 2.23.9 / 2.23.10** 的对应 evolution_history 记录 | `evolution_history.json` 中 brain_version 最大值 = **2.23.6**（记录 EVO-069）；而 `skills.md:3/70` 与 `main.py:39` 分别声明 2.23.7 / 2.23.10 / 2.23.11 | 已全仓库 grep `2\.23\.(7|8|9|10|11)`，命中的文档均**无对应 history 记录** → 规则 15「无记录禁止递增」当前不成立 |
| N4 | `fly64/skills/evolution_log.jsonl` 中 “t27/t28”（skills.md L70 提及）的执行证据 | 属于运行期语料（7.8 MB），本任务范围内只做只读统计，未逐条核验 | 未展开 |
| N5 | WSL 侧（`/root/fly64`）的真实状态 | 本机为 Windows，未执行任何 WSL 命令 | 未尝试（超出 T0 范围） |
| N6 | 报告所称“16 个子代理背书执行”“211 条 CJK 用户消息”“41MB”等会话内计数 | 需要解包 `export logs/*.zip` 并统计 | 未尝试（同 N1） |
| N7 | `KNOWN_FAILURES` 的“真实”完整集合是否只含 38/24 条 | 只核验了文件自洽性（count 字段 == len(entries)），未核验其与真实失败集的完备性（除第 6 节给出的 10 NEW / 10 now-pass 偏差外） | 第 6 节即为该方向的实测证据 |
| N8 | `.pytest-t20/.pytest-t21/...` 等 11 个历史 pytest 产物目录的跟踪状态与内容 | 属既有仓库噪声，未逐目录核验 | 仅记录目录存在（见第 9 节） |

---

## 9. 其它首手采集到的仓库事实（与报告结论直接相关，供计划 v2 使用）

| 事实 | 实测值 / 证据 |
|---|---|
| 仓库根 | `D:\codes\flygym`（含 `.git`、`.venv`、`fly64/`、`docs/`、`scripts/`、`SM64/`、`export logs/`） |
| 实际项目根 | `fly64/`（`fly64/fly64/main.py`、`fly64/scripts/`、`fly64/tests/`、`fly64/skills/`、`fly64/plugin/`、`fly64/web/` 均在此） |
| 报告中的相对路径解析 | `scripts/…` → `fly64/scripts/…` ✅ 存在；`tests/…` → `fly64/tests/…` ✅ 存在；报告**未给出该解析规则的说明**（我已在任务中按此口径核验） |
| `fly64/scripts/` 文件数 | 111 |
| `fly64/tests/*.json` | 仅 2 个：`known_failures.linux.json`、`known_failures.win32.json` |
| 遗留 pytest 产物目录（`fly64/` 下） | `.pytest-run/`、`.pytest-t20/`、`.pytest-t21/`、`.pytest-t21b/`、`.pytest-t21c/`、`.pytest-t23/`、`.pytest-t23b/`、`.pytest-t24/`、`.pytest-t28/`、`.pytest-t28b/`、`.pytest_cache/`（共 11 个） |
| `fly64/scripts/audit_motor_injections.py`（基线 note 引用） | **存在**（`Test-Path` → True），未运行 |
| pytest 版本 | 9.1.1 |
| `.venv` 可导入 `fly64` 包 | 从仓库根运行 `python -c "import os;print(os.path.exists('fly64/fly64/main.py'))"` → True（真实导入需 `cwd=fly64/`，见第 5 节各脚本实际运行方式） |
| 报告与执行计划均为**未跟踪**文件 | `?? docs/fly64_execution_plan.md`、`?? docs/fly64_export_logs_analysis_report.md`（两者都不被 `.gitignore` 忽略） |
| 本任务产出路径是否被忽略 | `git check-ignore -v docs/analysis/plan-v2/00-facts.md` → rc=1（**未**被忽略，可正常入库） |
| 根 `.gitignore` 关键项 | 忽略 `runtime/`、`artifacts/`、`*.log`、**`*.jsonl`**、`.agent-teams/`、`export logs/`；**未**忽略 `.pytest-run/` |

---

## 10. 复现指引（下游如何一键重跑本文件全部数字）

```powershell
# 全部命令假定 cwd = D:\codes\flygym
$py = "D:\codes\flygym\.venv\Scripts\python.exe"
$env:PYTHONIOENCODING = "utf-8"     # 避免中文场景名/文档在 Windows 控制台乱码

# (1) BRAIN_VERSION
Select-String -Path fly64\fly64\main.py -Pattern 'BRAIN_VERSION' | ForEach-Object { "$($_.LineNumber): $($_.Line.Trim())" }

# (2) git
git rev-parse HEAD; git rev-parse --abbrev-ref HEAD; git status --porcelain | Measure-Object -Line

# (3) baseline count / cause 分布（务必用 python，勿用 Get-Content）
$py -c "import json,collections;[print(f,json.load(open(f,encoding='utf-8'))['count'],len(json.load(open(f,encoding='utf-8'))['entries']),dict(collections.Counter(e['cause'] for e in json.load(open(f,encoding='utf-8'))['entries']))) for f in ('fly64/tests/known_failures.win32.json','fly64/tests/known_failures.linux.json')]"

# (4) agent.md 行数（务必用 python）
$py -c "from pathlib import Path;print(len(Path('agent.md').read_bytes().decode('utf-8').splitlines()))"

# (5) CLI / 默认路径
$py fly64\scripts\audit_contract_pairs.py --help
$py fly64\scripts\check_regressions.py --help
$py fly64\scripts\measure_evolution_health.py --help

# (6) 回归门禁（约 218 s；注意会污染 fly64/.pytest-run/）
Push-Location fly64; $py scripts\check_regressions.py; Write-Host "EXIT=$LASTEXITCODE"; Pop-Location

# (7) 直接写 control 处数
$py -c "import re;src=open('fly64/fly64/main.py',encoding='utf-8').read();print(len([1 for l in src.splitlines() if re.search(r'\bcontrol\.\w+\s*=[^=]',l)]))"

# (8) 契约审计 / 双环度量
Push-Location fly64; $py scripts\audit_contract_pairs.py; $py scripts\measure_evolution_health.py --json; Pop-Location
```

---

## 11. 偏差清单（提交给 captain 的结构化摘要）

| ID | 严重度 | 报告声明 | 实测 | 位置（报告） |
|---|---|---|---|---|
| D1 | **high** | 测试基线 “~482 通过 / 11 基线失败” | **929 passed / 38 failed / 36 skipped** | L226, L238, L294 |
| D2 | **high** | 基线 “36 条（13 env + 余下分类）” | **win32 38 条（environment=14, aspirational=16, test-drift=3, real-bug=2, unknown=3）；linux 24 条** | L170, L228, L249-259 |
| D3 | **high** | “main.py 写 control 35→12 处 / ~12 处” | **36 行 / 36 处赋值**（KPI 预算 26，实测超标 10，测试 FAIL） | L167, L236, L286 |
| D4 | **high** | “最新记录为 t17（Brain v2.23.6, Skill 3.4.2）” | `main.py:39` = **2.23.11**；`skills.md` 内部又自相矛盾为 2.23.7 / 2.23.10；`evolution_history.json` canonical = 2.23.6 | L4, L149 |
| D5 | medium | 基线文件写作 `tests/known_failures.json` | 实际为平台作用域 `known_failures.win32.json` / `.linux.json`；legacy 未限定名文件**不存在** | L228, L249 |
| D6 | medium | “全部 7 个已导出 DSH 会话” | `export logs/` 实为 **10 个 zip / 9 个 session id**；报告点名的 4 个短 id 在文件名中不存在 | L4, L21 |
| D7 | medium | L107 误写 `gent.md`（应为 `agent.md`） | 文件名为 `agent.md`（仓库根） | L107 |
| D8 | low | 报告 L21/L4 称时间跨度至 2026-09-20 | `evolution_history.json` 无任何记录晚于 **2026-09-18**；`canonical_versions.as_of = 2026-09-18T01:08:22+08:00` | L4, L21 |
| D9 | low | “回归基线 ✅ tests/known_failures.json + check_regressions.py” | 工具就绪但**当前为红**（exit 1，10 NEW failures），且跑一次会污染 132 个被跟踪文件 | L249 |
| D10 | info | 报告“79 条记录 / 51 个唯一脑版本” | ✅ 实测 79 条；唯一值 51（含字面量 `"None"`；非空唯一 = **50**） | L4, L149 |

> **无偏差、已核验为真**：`agent.md` = 1360 行（L4）✅；79 条 evolution 记录（L4/L107/L149）✅；三个脚本均存在（L229/L230/L250）✅；`scripts/…`、`tests/…` 相对 `fly64/` 解析后路径均存在 ✅。

---

## 12. 给下游（计划 v2 撰写者）的三条硬约束

1. **数字必须回填成本文件的值**：38 / 24 / 14 / 16 / 3 / 2 / 3、929 / 38 / 36、36 行（非 12）、1360 行、2.23.11（非 2.23.6）。
2. **行数与 JSON 计数一律用 Python 采集**：PowerShell `Get-Content` 在本仓库会低估约 32%（agent.md 921 vs 1360）。
3. **任何“跑测试作为验收”的行动，必须显式声明 `fly64/.pytest-run/` 的污染处理**（该目录 132 个文件被跟踪、且未被 `.gitignore` 忽略），否则验收证据不可复现。
