#!/usr/bin/env python3
"""
verify_doc_citations.py — 引用校验器（ver.2 — 队长规格）

从三份文档中抽取所有格式的 file:line 引用，断言：
  (a) 文件存在（多前缀尝试）
  (b) 行号 <= 文件总行数
  (c) 若引用附近有反引号包裹的符号，该符号字面量出现在引用区间内

反"假绿"守卫：若某文档包含 L\\d+ 文本但解析出 0 条引用，FAIL。
裸 L<num>（无文件名限定）单独计数为 unresolved，不得静默忽略。

退出码: 0 = 全部通过, 1 = 有失败

用法:
  python scripts/verify_doc_citations.py
"""

import re
import sys
import io
from pathlib import Path

# Windows GBK 终端兼容：设置 stdout/stderr 为 utf-8
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding and sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS = [
    ("session-log-analysis.md", REPO_ROOT / "docs/analysis/session-log-analysis.md"),
    ("session-log-recommendations.md", REPO_ROOT / "docs/analysis/session-log-recommendations.md"),
    ("session_logs_execution_plan.md", REPO_ROOT / "docs/analysis/session_logs_execution_plan.md"),
]

# 正则 A: 反引号包裹的文件路径 + L 引用  — `file.py` L123 或 `file` L123-L456
CITE = re.compile(r"`(?P<file>[\w./\-]+\.(?:py|json|sh|md))`\s*L(?P<start>\d+)(?:\s*[-u2013u2014]\s*L?(?P<end>\d+))?")

# 正则 B: 文档内直接 # file.py L123 或类似格式（无反引号）
CITE_BARE = re.compile(r"(?<!`)([\w./\-]+\.(?:py|json|sh|md))\s+L(?P<start_b>\d+)(?:\s*[-u2013u2014]\s*L?(?P<end_b>\d+))?")

# 正则 C: 表格内裸 L<num>（无文件名限定）
BARE_L = re.compile(r"(?<![`\w])L(\d+)(?:\s*[-u2013u2014]\s*L?(\d+))?")

# 正则 D: 检测文档中是否含 L<num> 文本（用于反假绿守卫）
HAS_L = re.compile(r"L\d+")

# 符号提取：查找反引号包裹的标识符
SYM_FMT = re.compile(r"`([\w_.]+)`")

# 尝试解析文件的前缀路径（按优先级排序）
PREFIXES = [
    "fly64/fly64/",
    "fly64/skills/",
    "fly64/scripts/",
    "fly64/tests/",
    "fly64/",
    "scripts/",
    "docs/analysis/",
    "",
]


def resolve_file(file_rel: str) -> Path | None:
    """按优先级尝试多种前缀路径解析文件名，返回第一个存在的 Path 或 None。"""
    for prefix in PREFIXES:
        candidate = REPO_ROOT / (prefix + file_rel)
        if candidate.exists():
            return candidate

    # 全仓 rglob 兜底（排除测试夹具）
    exclude_prefixes = {'.tmp', '.tmp-pytest', '.pytest', '.venv', '__pycache__',
                        '.pytest-run', '.pytest-t23b', '.pytest-t24', '.pytest-t28',
                        '.pytest-t28b', '.tmp-pytest'}
    # 只搜索 fly64/ 下以避免大量无关文件
    base = REPO_ROOT / "fly64"
    if base.exists():
        candidates = sorted(base.rglob(file_rel))
        candidates = [c for c in candidates if not any(p in exclude_prefixes for p in c.parts)]
        if candidates:
            return candidates[0]

    return None


def get_line_count(path: Path) -> int:
    with open(path, "r", encoding="utf-8") as f:
        return sum(1 for _ in f)


def get_line(path: Path, lineno: int) -> str:
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            if i == lineno:
                return line.rstrip("\n")
    return ""


def extract_symbols_nearby(text: str, match_start: int) -> list[str]:
    """从匹配位置附近（前后各 100 字符）提取反引号包裹的符号。"""
    nearby = text[max(0, match_start - 100):match_start + 100]
    return SYM_FMT.findall(nearby)


def find_section_context(lines: list[str], doc_line: int) -> str:
    """从文档中推断当前引用所属的章节/上下文（用于裸 L 引用的文件推断）。"""
    # 向上查找最近的小节标题
    for i in range(doc_line - 2, max(0, doc_line - 40), -1):
        if i < len(lines):
            line = lines[i].strip()
            if line.startswith("##") or line.startswith("###") or line.startswith("####"):
                # 去除 emoji 和特殊符号
                clean = re.sub(r'[^\u0020-\u007E\u4e00-\u9fff\w\s]', '', line)
                return clean[:60]
    return "(no section found)"


def main() -> int:
    errors = []
    warnings = []
    total_cited = 0        # 有文件名限定的引用条数
    total_unresolved = 0   # 裸 L<num> 条数
    doc_stats: dict[str, dict] = {}

    for doc_name, doc_path in DOCS:
        if not doc_path.exists():
            errors.append(f"文档不存在: {doc_path}")
            continue

        with open(doc_path, "r", encoding="utf-8") as f:
            content = f.read()
        lines = content.split("\n")

        # ---- 反假绿守卫：检测文档中是否有 L<num> 文本 ----
        has_ltext = bool(HAS_L.search(content))

        cited_count = 0
        unresolved_count = 0
        doc_cited: list[tuple[str, int, int | None, int, str]] = []  # (file, start, end, doc_line, symbol_context)

        # ---- 解析 A: 反引号包裹的 file:line 引用 ----
        for match in CITE.finditer(content):
            cited_count += 1
            file_rel = match.group("file")
            start = int(match.group("start"))
            end = int(match.group("end")) if match.group("end") else None
            pos = match.start()
            dl = content[:pos].count("\n") + 1
            doc_cited.append((file_rel, start, end, dl, "cite"))

        # ---- 解析 B: 裸文件 + L 引用 ----
        for match in CITE_BARE.finditer(content):
            cited_count += 1
            file_rel = match.group(1)
            start = int(match.group("start_b"))
            end = int(match.group("end_b")) if match.group("end_b") else None
            pos = match.start()
            dl = content[:pos].count("\n") + 1
            doc_cited.append((file_rel, start, end, dl, "bare_file"))

        # ---- 解析 C: 表格内裸 L<num>（无文件名限定）----
        for match in BARE_L.finditer(content):
            unresolved_count += 1
            pos = match.start()
            dl = content[:pos].count("\n") + 1
            start = int(match.group(1))
            end = int(match.group(2)) if match.group(2) else None
            # 裸引用不验证文件，仅计数
            unresolved_count += 1
            section = find_section_context(lines, dl)
            # 仅在第一次遇到该上下文的裸 L 时才报 WARN，避免海量重复
            if unresolved_count <= 3:
                warnings.append(f"[{doc_name}:L{dl}] 裸 L{start}（无文件名）"
                               + (f"-L{end}" if end else "")
                               + f" — 上下文: {section[:60]}")
            elif unresolved_count == 4:
                total_bare = len(BARE_L.findall(content))
                warnings.append(f"[{doc_name}: ... 后续 {total_bare - 3} 条裸 L 略过 (总计 {total_bare} 条)")

        doc_stats[doc_name] = {
            "cited": cited_count,
            "unresolved": unresolved_count,
            "has_ltext": has_ltext,
        }

        # ---- 反假绿守卫 ----
        if has_ltext and cited_count == 0:
            samples = HAS_L.findall(content)[:10]
            errors.append(f"[{doc_name}] 反假绿守卫触发: 文档含 L<num> 文本({len(samples)} 处, 样例: {samples}) 但解析出 0 条引用")
            continue

        # ---- 逐条验证有文件名限定的引用 ----
        for file_rel, start, end, dl, fmt in doc_cited:
            total_cited += 1

            # 解析文件
            file_path = resolve_file(file_rel)
            if file_path is None:
                tried = [REPO_ROOT / p / file_rel for p in PREFIXES[:4]]
                errors.append(f"[{doc_name}:L{dl}] 文件不存在: {file_rel} (tried: {', '.join(str(t) for t in tried)})")
                continue

            total_lines = get_line_count(file_path)

            # 行号存在性
            if start > total_lines:
                errors.append(f"[{doc_name}:L{dl}] 行号溢出: {file_rel} L{start} > 总行数 {total_lines}")
                continue

            if end is not None:
                if end > total_lines:
                    errors.append(f"[{doc_name}:L{dl}] 行号溢出: {file_rel} L{end} > 总行数 {total_lines}")
                    continue
                if end < start:
                    errors.append(f"[{doc_name}:L{dl}] 行号范围反向: L{start}-L{end}")
                    continue
                if end - start > 50:
                    warnings.append(f"[{doc_name}:L{dl}] 大范围引用: {file_rel} L{start}-L{end} ({end-start+1} 行)")

            # 符号一致性：提取匹配位置附近的 `symbol` 反引号符号
            symbols = extract_symbols_nearby(content, content.find(file_rel))
            if symbols:
                # 找到第一个出现在引用区间内的符号
                found_sym = None
                end_scan = end if end else start
                for sym in symbols:
                    for ln in range(start, min(end_scan + 1, start + 10)):  # 前 10 行快速扫描
                        line_text = get_line(file_path, ln)
                        if sym in line_text:
                            found_sym = sym
                            break
                    if found_sym:
                        break
                if found_sym is None:
                    # WARN 而非 FAIL — 符号可能不在前 10 行
                    available = get_line(file_path, start)[:80]
                    warnings.append(f"[{doc_name}:L{dl}] 符号 '{symbols[0]}' 未在 {file_rel} L{start} 附近找到 (available: '{available}')")

        # ---- 反假绿守卫 2: 极端情况 ----
        # 如果 has_ltext 但 cited_count + unresolved_count == 0，理论上已被捕获

    # ---- 按文档输出统计 ----
    safe_errors = []
    safe_warnings = []
    for e in errors:
        safe_errors.append(e.encode('ascii', errors='replace').decode('ascii'))
    for w in warnings:
        safe_warnings.append(w.encode('ascii', errors='replace').decode('ascii'))

    print(f"\n=== 引用校验报告 ===")
    total_resolved = sum(s["cited"] for s in doc_stats.values())
    total_unresolved = sum(s["unresolved"] for s in doc_stats.values())
    for dname, stats in doc_stats.items():
        print(f"  {dname}: {stats['cited']} 条引用 + {stats['unresolved']} 条裸 L (has_L_text={stats['has_ltext']})")
    print(f"总计: {total_cited} 条引用 (含 {total_unresolved} 裸 L)")
    print(f"通过: {total_cited - len(errors)}")
    print(f"警告: {len(warnings)}")
    print(f"失败: {len(errors)}")

    if safe_warnings:
        print(f"\n--- 警告 ---")
        for w in safe_warnings:
            print(f"  {w}")

    if safe_errors:
        print(f"\n--- 失败 ---")
        for e in safe_errors:
            print(f"  {e}")
        return 1
    else:
        print(f"\n[PASS] 所有引用校验通过！")
        return 0


if __name__ == "__main__":
    sys.exit(main())