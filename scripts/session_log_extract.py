#!/usr/bin/env python3
"""
Extract all DSH session logs and produce structured JSON summary.

Usage:
    python scripts/session_log_extract.py                     # extract & write summary
    python scripts/session_log_extract.py --check             # verify only (exit code)
    python scripts/session_log_extract.py --check-verbose     # verify + print details
"""
import json
import os
import re
import sys
from datetime import datetime, timezone

SESSIONS_BASE = os.path.join(os.path.dirname(__file__), "..", ".tmp", "sessions")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "analysis", "session-log-summary.json")


# ---------------------------------------------------------------------------
# Theme classification
# ---------------------------------------------------------------------------
THEME_PATTERNS = [
    ("brain-model",       re.compile(r"脑模型|果蝇|brain|神经元|复眼|视觉|运动模式|马里奥")),
    ("agent-teams",       re.compile(r"agent[\s._-]*team|/agent-teams")),
    ("ghb-cost-control",  re.compile(r"ghb|控费|保费|理赔|保险|Doris|保单")),
    ("dashboard-ui",      re.compile(r"仪表板|监控|dashboard|UI|监控界面|布局")),
    ("flygym-setup",      re.compile(r"安装|FlyGym|flygym|pip install|交互视图")),
    ("document-analysis", re.compile(r"分析.*文档|分析.*报告|分析当前|执行计划")),
    ("session-log-analysis", re.compile(r"会话日志|session\.log|session_logs|export logs")),
    ("system-diagnostics", re.compile(r"skill检查|当前状态|运行模式")),
    ("code-clone-analysis", re.compile(r"克隆|xquant|git\s*clone")),
]


def classify_themes(user_text: str) -> list:
    """Return list of theme tags based on user message content."""
    themes = []
    for tag, pattern in THEME_PATTERNS:
        if pattern.search(user_text):
            themes.append(tag)
    return themes if themes else ["general"]


# ---------------------------------------------------------------------------
# Tool categorisation
# ---------------------------------------------------------------------------
TOOL_CATEGORY_RULES = [
    (re.compile(r"^pwsh"),                             "pwsh"),
    (re.compile(r"^read\b"),                           "read"),
    (re.compile(r"^edit\b"),                           "edit"),
    (re.compile(r"^write\b"),                          "write"),
    (re.compile(r"^grep\b"),                           "grep"),
    (re.compile(r"^agent_teams_"),                     "agent_teams"),
    (re.compile(r"^brain_"),                           "brain"),
    (re.compile(r"^ghb_"),                             "ghb"),
    (re.compile(r"^oa_"),                              "oa"),
    (re.compile(r"^(subagent|subagent_fork)"),         "subagent"),
    (re.compile(r"^(glob|present|job_kill|job_output|job_list)"), "job_management"),
    (re.compile(r"^(ask_user_question|web_search|web_fetch)"),    "web_interaction"),
    (re.compile(r"^(create_goal|get_goal|update_goal)"),          "goal"),
    (re.compile(r"^(mcp__|skill)"),                    "skill_mcp"),
    (re.compile(r"^(workflow|ralph)"),                 "orchestration"),
    (re.compile(r"^(interrupt_agent|list_agents|send_message)"),  "agent_management"),
]


def classify_tool(tool_name: str) -> str:
    """Map raw tool name to a category string."""
    for pattern, category in TOOL_CATEGORY_RULES:
        if pattern.search(tool_name):
            return category
    return "other"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def epoch_ms_to_str(ms: int) -> str:
    """Convert epoch milliseconds to ISO-ish datetime string."""
    try:
        dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, OSError, OverflowError):
        return "unknown"


# Source kinds that are NOT typed by a human.  v4 exports (09-24..09-26) added
# a much richer set of injection kinds; all of them must be filtered out before
# picking "the first real user message" or building the theme corpus.
NON_HUMAN_SOURCE_KINDS = frozenset({
    "plugin",                  # v0/v3 exact form
    "agent-teams-command",
    "agent-teams",
    "agent-message",
    "subagent-settled",
    "skill-catalog",
    "runtime-context",
    "user-approval",
    "model-selection",
    "repeat-tool-reminder",
    "tool-jobs",
    "compact-checkpoint",
    "system",
    "goal",
})

# Text-level injection markers that arrive with kind="user" in v4 exports.
INJECTION_TEXT_PREFIXES = (
    "<system-reminder>",
    "Current runtime context.",
    "The approval policy changed",
    "The sandbox mode changed",
)


def is_injected_text(text: str) -> bool:
    """Text-level filter for injections that still carry source.kind='user'."""
    stripped = text.lstrip()
    return stripped.startswith(INJECTION_TEXT_PREFIXES)


def is_real_user_message(source: dict) -> bool:
    """Heuristic: skip plugin/runtime/system/agent injected messages."""
    if not source:
        return True  # default: treat as real if no source info
    kind = source.get("kind", "")
    if not kind:
        return True
    # covers "plugin" and namespaced forms such as "plugin:dsh-agent-teams"
    if kind.startswith("plugin"):
        return False
    if kind in NON_HUMAN_SOURCE_KINDS:
        return False
    return True


def collect_user_texts(data: dict) -> list:
    """Extract all 'human' message texts from an agent/inbox/spliced event."""
    texts = []
    for msg in data.get("inserted", []):
        if msg.get("role") != "user":
            continue
        src = msg.get("source", {})
        if not is_real_user_message(src):
            continue
        content = msg.get("content", [])
        for part in content:
            if part.get("type") == "text":
                texts.append(part.get("text", ""))
    return texts


# ---------------------------------------------------------------------------
# Session file discovery
# ---------------------------------------------------------------------------
def find_session_jsonl(session_dir: str) -> tuple:
    """
    Return (filepath, format) for the main session JSONL.
    Prefers session.v4.jsonl > session.v3.jsonl > session.jsonl.
    (v4 was introduced by the 09-24..09-26 exports; older exports are v3/v0.)
    """
    for name, fmt in (("session.v4.jsonl", "v4"), ("session.v3.jsonl", "v3"),
                      ("session.jsonl", "v0")):
        p = os.path.join(session_dir, name)
        if os.path.isfile(p):
            return p, fmt
    return None, None


# ---------------------------------------------------------------------------
# Parse one session
# ---------------------------------------------------------------------------
def parse_session(session_dir: str) -> dict:
    """Parse a single session directory and return its structured summary."""
    result_dirname = os.path.basename(session_dir)

    # Find session JSONL
    jsonl_path, fmt = find_session_jsonl(session_dir)
    if jsonl_path is None:
        return None

    file_size = os.path.getsize(jsonl_path)

    # Collect subagent directories
    subagent_dir = os.path.join(session_dir, "subagents")
    subagent_count = 0
    if os.path.isdir(subagent_dir):
        subagent_count = len([
            d for d in os.listdir(subagent_dir)
            if os.path.isdir(os.path.join(subagent_dir, d))
        ])

    # -----------------------------------------------------------------------
    # Stream-parse the JSONL
    # -----------------------------------------------------------------------
    session_id = None
    created_at_epoch = None
    title = None
    first_time = None
    last_time = None
    workspace_changes = []   # reserved (workspace/changes events carry only a turn id)
    record_time_count = 0

    tool_calls = {}          # category -> count
    raw_tool_totals = {}     # raw_tool_name -> count (for self-check)
    file_changes = set()     # "write:path" or "edit:path"
    total_lines = 0
    msg_count = 0
    turn_count = 0
    step_count = 0

    first_user_msg = None
    all_user_text_parts = []

    tool_call_count = 0  # total tool/call events

    with open(jsonl_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total_lines += 1
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue

            typ = rec.get("type", "")
            data = rec.get("data", {})

            # -- wall-clock coverage (v3/v4 records carry an epoch-ms "time") --
            t = rec.get("time")
            if isinstance(t, (int, float)) and t > 0:
                record_time_count += 1
                if first_time is None or t < first_time:
                    first_time = t
                if last_time is None or t > last_time:
                    last_time = t

            # -- session metadata --
            if typ == "session":
                session_id = rec.get("id", result_dirname)
                created_at_epoch = rec.get("createdAt")
                if rec.get("title"):
                    title = rec["title"]

            elif typ == "session/title":
                if data.get("title"):
                    title = data["title"]

            # -- turn & step tracking --
            elif typ == "turn/start":
                turn_count += 1
            elif typ == "step/start":
                step_count += 1

            # -- user messages --
            elif typ == "user/message":
                msg_count += 1
                source = data.get("source", {})
                content = data.get("content", [])
                text = ""
                for part in content:
                    if part.get("type") == "text":
                        text += part.get("text", "")
                if text:
                    if is_injected_text(text):
                        continue
                    all_user_text_parts.append(text)
                    if first_user_msg is None and is_real_user_message(source):
                        first_user_msg = text[:200]

            # -- command/run (agent-teams/other commands from user) --
            elif typ == "command/run":
                cmd_name = data.get("name", "")
                cmd_args = data.get("args", "")
                if cmd_name and isinstance(cmd_args, str) and cmd_args.strip():
                    # Skip permission commands
                    if cmd_name == "permission":
                        if first_user_msg is None:
                            pass  # don't set firstUserMsg from permission
                        continue
                    # Record as user-intent message
                    all_user_text_parts.append(cmd_args)
                    if first_user_msg is None:
                        first_user_msg = cmd_args[:200]

            # -- agent/inbox/spliced (injected messages including user's) --
            elif typ == "agent/inbox/spliced":
                for text in collect_user_texts(data):
                    if text:
                        all_user_text_parts.append(text)

            # -- tool/call (each actual tool invocation) --
            elif typ == "tool/call":
                tool_name = data.get("name", "")
                if tool_name:
                    tool_call_count += 1
                    raw_tool_totals[tool_name] = raw_tool_totals.get(tool_name, 0) + 1
                    cat = classify_tool(tool_name)
                    tool_calls[cat] = tool_calls.get(cat, 0) + 1

                    # Track file changes from write/edit
                    if tool_name in ("write", "edit"):
                        args_str = data.get("arguments", "")
                        if args_str:
                            try:
                                args = json.loads(args_str)
                                fp = args.get("file_path", "")
                                if fp:
                                    file_changes.add(f"{tool_name}:{fp}")
                            except (json.JSONDecodeError, TypeError):
                                pass

    # -- derive session id fallback --
    if session_id is None:
        session_id = result_dirname

    # -- first user message: if still None (or is permission), mark null --
    if first_user_msg is not None:
        # Clean up the first message
        first_user_msg = first_user_msg.strip()
        # Remove leading " danger-full-access" or permission leftovers
        first_user_msg = re.sub(r"^danger-full-access\s*", "", first_user_msg).strip()
    if not first_user_msg:
        first_user_msg = None  # explicit null

    # -- themes --
    all_text = " ".join(all_user_text_parts)
    themes = classify_themes(all_text)

    # -- file change details --
    file_change_list = []
    for entry in sorted(file_changes):
        tool, path = entry.split(":", 1)
        file_change_list.append({"tool": tool, "path": path})

    write_count = sum(1 for e in file_change_list if e["tool"] == "write")
    edit_count = sum(1 for e in file_change_list if e["tool"] == "edit")

    tool_call_total = sum(tool_calls.values())

    # -- creation time --
    created_str = epoch_ms_to_str(created_at_epoch) if created_at_epoch else "unknown"

    # -- wall-clock coverage --
    first_time_str = epoch_ms_to_str(first_time) if first_time else "unknown"
    last_time_str = epoch_ms_to_str(last_time) if last_time else "unknown"
    span_days = None
    if first_time and last_time:
        span_days = round((last_time - first_time) / 86400000.0, 3)

    return {
        "sessionId": session_id,
        "sessionDir": result_dirname,
        "title": title,
        "format": fmt,
        "createdAt": created_str,
        "createdAtEpoch": created_at_epoch,
        "firstEventTime": first_time_str,
        "lastEventTime": last_time_str,
        "spanDays": span_days,
        "timedRecordCount": record_time_count,
        "fileSizeBytes": file_size,
        "fileSizeKB": round(file_size / 1024, 1),
        "totalLines": total_lines,
        "messageCount": msg_count,
        "turnCount": turn_count,
        "stepCount": step_count,
        "subagentCount": subagent_count,

        # Tool stats
        "toolCallTotal_raw": tool_call_count,       # total tool/call records
        "toolCalls": tool_calls,
        "toolCallTotal": tool_call_total,
        "rawToolTotals": raw_tool_totals,           # for verification

        # File changes
        "fileChanges": file_change_list,
        "fileChangeCount": len(file_change_list),
        "writeCount": write_count,
        "editCount": edit_count,

        # Content
        "themes": themes,
        "firstUserMessage": first_user_msg,
    }


# ---------------------------------------------------------------------------
# Build aggregate stats
# ---------------------------------------------------------------------------
def build_aggregate_stats(sessions: list) -> dict:
    """Compute cross-session aggregations."""
    total_tool_calls = 0
    total_file_changes = 0
    total_messages = 0
    total_lines = 0
    total_size_kb = 0.0
    total_turns = 0
    total_steps = 0

    tool_breakdown = {}
    theme_counts = {}

    for s in sessions:
        total_tool_calls += s["toolCallTotal"]
        total_file_changes += s["fileChangeCount"]
        total_messages += s["messageCount"]
        total_lines += s["totalLines"]
        total_size_kb += s["fileSizeKB"]
        total_turns += s["turnCount"]
        total_steps += s["stepCount"]

        # tool breakdown
        for cat, cnt in s["toolCalls"].items():
            if cat not in tool_breakdown:
                tool_breakdown[cat] = {"total": 0, "sessionCount": 0}
            tool_breakdown[cat]["total"] += cnt

        # themes
        for theme in s["themes"]:
            theme_counts[theme] = theme_counts.get(theme, 0) + 1

    # session counts per tool category (second pass)
    for s in sessions:
        for cat in s["toolCalls"]:
            if cat in tool_breakdown:
                tool_breakdown[cat]["sessionCount"] = sum(
                    1 for x in sessions if cat in x["toolCalls"]
                )

    theme_breakdown = sorted(
        [{"theme": k, "count": v} for k, v in theme_counts.items()],
        key=lambda x: -x["count"],
    )

    return {
        "totalToolCalls": total_tool_calls,
        "totalFileChanges": total_file_changes,
        "totalMessages": total_messages,
        "totalLines": total_lines,
        "totalSizeKB": round(total_size_kb, 1),
        "totalTurns": total_turns,
        "totalSteps": total_steps,
        "themeBreakdown": theme_breakdown,
        "toolBreakdown": tool_breakdown,
    }


# ---------------------------------------------------------------------------
# Self-consistency checks
# ---------------------------------------------------------------------------
def check_consistency(sessions: list, aggregate: dict) -> list:
    """Run internal consistency checks. Return list of (check_name, ok_bool, detail)."""
    checks = []

    # 1. Aggregated totals match sum of per-session
    agg_tools = sum(s["toolCallTotal"] for s in sessions)
    checks.append((
        "aggregate-tool-call-sum",
        agg_tools == aggregate["totalToolCalls"],
        f"agg={aggregate['totalToolCalls']} vs sum={agg_tools}",
    ))

    agg_files = sum(s["fileChangeCount"] for s in sessions)
    checks.append((
        "aggregate-file-change-sum",
        agg_files == aggregate["totalFileChanges"],
        f"agg={aggregate['totalFileChanges']} vs sum={agg_files}",
    ))

    agg_msgs = sum(s["messageCount"] for s in sessions)
    checks.append((
        "aggregate-message-sum",
        agg_msgs == aggregate["totalMessages"],
        f"agg={aggregate['totalMessages']} vs sum={agg_msgs}",
    ))

    # 2. Per-session: toolCallTotal_raw == toolCallTotal (from categories)
    for s in sessions:
        sid = s["sessionId"][8:16]
        raw = s["toolCallTotal_raw"]
        cat_sum = s["toolCallTotal"]
        checks.append((
            f"session-{sid}-tool-raw-vs-cat",
            raw == cat_sum,
            f"raw_tool/call={raw} vs category_sum={cat_sum}",
        ))

    # 3. Per-session: rawToolTotals values sum matches toolCallTotal
    for s in sessions:
        sid = s["sessionId"][8:16]
        raw_sum = sum(s.get("rawToolTotals", {}).values())
        checks.append((
            f"session-{sid}-raw-tool-sum",
            raw_sum == s["toolCallTotal_raw"],
            f"raw_tool_sum={raw_sum} vs total_raw={s['toolCallTotal_raw']}",
        ))

    # 4. Per-session: fileChangeCount == len(fileChanges) == writeCount + editCount
    for s in sessions:
        sid = s["sessionId"][8:16]
        fcc = s["fileChangeCount"]
        fcl = len(s["fileChanges"])
        we = s["writeCount"] + s["editCount"]
        checks.append((
            f"session-{sid}-file-count-consistency",
            fcc == fcl == we,
            f"fileChangeCount={fcc} len(fileChanges)={fcl} write+edit={we}",
        ))

    # 5. No firstUserMessage contains "danger-full-access" or permission strings
    for s in sessions:
        sid = s["sessionId"][8:16]
        fmsg = s.get("firstUserMessage") or ""
        bad = "danger-full-access" in fmsg
        checks.append((
            f"session-{sid}-no-permission-in-firstmsg",
            not bad,
            f"firstUserMessage contains permission keyword: {repr(fmsg[:80])}" if bad else "ok",
        ))

    return checks


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    # Optional overrides: --base <dir> --out <json>  (defaults unchanged)
    base = SESSIONS_BASE
    out_path = OUTPUT_PATH
    argv = sys.argv[1:]
    for i, a in enumerate(argv):
        if a == "--base" and i + 1 < len(argv):
            base = argv[i + 1]
        elif a == "--out" and i + 1 < len(argv):
            out_path = argv[i + 1]

    # Discover session directories
    if not os.path.isdir(base):
        print(f"ERROR: sessions base not found: {base}", file=sys.stderr)
        sys.exit(1)

    session_dirs = sorted([
        d for d in os.listdir(base)
        if os.path.isdir(os.path.join(base, d))
    ])

    sessions = []
    for d in session_dirs:
        dp = os.path.join(base, d)
        result = parse_session(dp)
        if result is not None:
            sessions.append(result)

    # Build aggregate
    aggregate = build_aggregate_stats(sessions)
    unique_ids = len({s["sessionId"] for s in sessions})

    output = {
        "generatedAt": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "totalSessions": len(sessions),
        "uniqueSessionIds": unique_ids,
        "sessions": sessions,
        "aggregatedStats": aggregate,
    }

    # Run consistency checks
    checks = check_consistency(sessions, aggregate)
    all_ok = all(ok for _, ok, _ in checks)
    failed_checks = [check for check in checks if not check[1]]

    # --check mode
    if "--check" in sys.argv:
        verbose = "--check-verbose" in sys.argv
        if verbose:
            print(f"=== Consistency checks ({len(checks)} total) ===")
            for name, ok, detail in checks:
                status = "PASS" if ok else "FAIL"
                print(f"  [{status}] {name}: {detail}")

        if failed_checks:
            print(f"\nFAILED: {len(failed_checks)} check(s) failed:")
            for name, _, detail in failed_checks:
                print(f"  - {name}: {detail}")
            sys.exit(1)
        else:
            print(f"All {len(checks)} consistency checks PASSED.")
            sys.exit(0)

    # Print baseline verification for f953d3fd
    for s in sessions:
        if "f953d3fd" in s["sessionId"]:
            print(f"\nBaseline check for f953d3fd:")
            print(f"  tool/call total: {s['toolCallTotal']}")
            print(f"  tool categories: {dict(sorted(s['toolCalls'].items(), key=lambda x: -x[1]))}")

    if failed_checks:
        print(f"\nWARNING: {len(failed_checks)} consistency check(s) failed (data written anyway):")
        for name, _, detail in failed_checks:
            print(f"  - {name}: {detail}")

    # Write JSON output (after all reporting, so raw fields are still available)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    # Remove rawToolTotals from the output (used for verification only)
    for s in output["sessions"]:
        if "rawToolTotals" in s:
            del s["rawToolTotals"]
        if "toolCallTotal_raw" in s:
            del s["toolCallTotal_raw"]

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=4)

    print(f"\nWritten {len(sessions)} sessions to {out_path}")
    print(f"  totalToolCalls={aggregate['totalToolCalls']}")
    print(f"  totalFileChanges={aggregate['totalFileChanges']}")
    print(f"  totalMessages={aggregate['totalMessages']}")

    return output


if __name__ == "__main__":
    main()