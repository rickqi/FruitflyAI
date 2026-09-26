#!/usr/bin/env python3
"""
Structured summary for the NEW/updated export logs of 2026-09-24 -> 2026-09-26.

Reuses the VERIFIED extractor core (`scripts/session_log_extract.py`:
parse_session / classify_tool / classify_themes / epoch_ms_to_str) so all
tool/call accounting is byte-identical to the checked extractor, then adds:

  * zip / export metadata (exportedAt, size, member counts)
  * full-file independent tool/call recount (line-level, not head-only)
  * sub-agent (delegated session) statistics
  * wall-clock coverage / date range per session (UTC + local UTC+8)
  * version-to-version incremental diffs for 6c53f724 and 51f62457
  * baseline self-check against the previous round's numbers
    (f953d3fd=2443, 38542b1c=2644, 27ed0979=1121, 1f8fbe04=816)

Input :  .tmp/sessions-new/            (produced by scripts/extract_new_sessions.py)
Output:  docs/analysis/session-summary-0924-0926.json  (UTF-8, ensure_ascii=False)

Usage:
    python scripts/session_summary_new_logs.py
"""
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from session_log_extract import (  # noqa: E402  (verified extractor core)
    parse_session,
    epoch_ms_to_str,
)

NEW_BASE = os.path.join(ROOT, ".tmp", "sessions-new")
OLD_BASE = os.path.join(ROOT, ".tmp", "sessions")
MANIFEST = os.path.join(NEW_BASE, "_extract_manifest.json")
OUT_PATH = os.path.join(ROOT, "docs", "analysis", "session-summary-0924-0926.json")

LOCAL_TZ = timezone(timedelta(hours=8))  # Asia/Shanghai (clientTimeZone in exports)

# Previous round's measured values for the OLD sessions -> self-check baseline.
BASELINE = {
    "f953d3fd": 2443,
    "38542b1c": 2644,
    "27ed0979": 1121,
    "1f8fbe04": 816,
}

# label -> session id prefix, for readability
LABELS = [
    "99cab60f-latest",
    "6c53f724-v1",
    "6c53f724-v2",
    "6c53f724-v3",
    "51f62457-v1",
    "51f62457-v2",
]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def local_str(ms):
    if not ms:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S")


def local_date(ms):
    if not ms:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=LOCAL_TZ).strftime("%Y-%m-%d")


def day_range(first_ms, last_ms):
    """Inclusive list of local dates covered by [first_ms, last_ms]."""
    if not first_ms or not last_ms:
        return []
    d0 = datetime.fromtimestamp(first_ms / 1000, tz=LOCAL_TZ).date()
    d1 = datetime.fromtimestamp(last_ms / 1000, tz=LOCAL_TZ).date()
    days = []
    d = d0
    while d <= d1:
        days.append(d.isoformat())
        d = d + timedelta(days=1)
    return days


def find_jsonl(session_dir):
    for name in ("session.v4.jsonl", "session.v3.jsonl", "session.jsonl"):
        p = os.path.join(session_dir, name)
        if os.path.isfile(p):
            return p
    return None


TOOL_CALL_RE = re.compile(rb'"type"\s*:\s*"tool/call"')


def normalize_path(p):
    """Workspace-relative POSIX path (as recorded by write/edit file_path)."""
    if not p:
        return p
    q = p.replace("\\", "/")
    root = ROOT.replace("\\", "/")
    if q.lower().startswith(root.lower() + "/"):
        return q[len(root) + 1:]
    # drive-letter absolute path outside the workspace -> keep as-is
    return q


def counting_evidence(path):
    """Demonstrate the sampling error the full-file count avoids.

    The previous round's 122x distortion came from deciding a tool/call total
    from a partial read.  This records what a head-only read of the same file
    would have produced, so the full-file numbers are auditable.
    """
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()
    def n_tc(seq):
        return sum(1 for l in seq if '"type":"tool/call"' in l[:80]
                   or '"type": "tool/call"' in l[:80])
    full = n_tc(lines)
    out = {"totalLines": len(lines), "fullFileToolCalls": full}
    for frac in (0.1, 0.2, 0.5):
        head = n_tc(lines[:int(len(lines) * frac)])
        out[f"headOnly{int(frac * 100)}pct"] = {
            "toolCalls": head,
            "undercountFactor": round(full / head, 1) if head else None,
        }
    return out


def tool_calls_by_date(path):
    """tool/call count bucketed by local (UTC+8) calendar date."""
    import collections
    c = collections.Counter()
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if '"tool/call"' not in line:
                continue
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("type") != "tool/call":
                continue
            t = rec.get("time")
            c[local_date(t) if t else "unknown"] += 1
    return dict(sorted(c.items()))


def independent_tool_call_count(path):
    """Byte-level recount of tool/call occurrences (independent of the parser).

    Streams the WHOLE file; never samples the head.
    """
    n = 0
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1 << 22)
            if not chunk:
                break
            n += len(TOOL_CALL_RE.findall(chunk))
    return n


def line_level_stats(path):
    """Independent per-record-type tally straight off the raw lines."""
    import collections
    c = collections.Counter()
    bad = 0
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                bad += 1
                continue
            c[rec.get("type", "?")] += 1
    return c, bad


def subagent_catalog(path):
    """childId -> catalog entry for every subagent/catalog record in the parent log."""
    out = {}
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if "subagent/catalog" not in line:
                continue
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("type") != "subagent/catalog":
                continue
            d = rec.get("data", {})
            cid = d.get("childId")
            if cid:
                out[cid] = {
                    "childId": cid,
                    "label": d.get("label"),
                    "mode": d.get("mode"),
                    "childCreatedAt": d.get("childCreatedAt"),
                }
    return out


def session_header(jpath):
    """First `session` record of a JSONL, if any."""
    try:
        with open(jpath, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if rec.get("type") == "session":
                    return rec
                return None
    except (OSError, json.JSONDecodeError):
        return None
    return None


def subagent_stats(session_dir):
    sub_dir = os.path.join(session_dir, "subagents")
    out = {
        "subagentCount": 0,
        "subagentToolCalls": 0,
        "subagentMessages": 0,
        "subagentTurns": 0,
        "subagentSteps": 0,
        "subagentToolCallMax": 0,
        "perSubagent": [],
    }
    if not os.path.isdir(sub_dir):
        return out
    ids = sorted(d for d in os.listdir(sub_dir) if os.path.isdir(os.path.join(sub_dir, d)))
    out["subagentCount"] = len(ids)
    for sid in ids:
        jp = find_jsonl(os.path.join(sub_dir, sid))
        if jp is None:
            continue
        c, _ = line_level_stats(jp)
        tc = c.get("tool/call", 0)
        hdr = session_header(jp) or {}
        out["subagentToolCalls"] += tc
        out["subagentMessages"] += c.get("user/message", 0)
        out["subagentTurns"] += c.get("turn/start", 0)
        out["subagentSteps"] += c.get("step/start", 0)
        out["subagentToolCallMax"] = max(out["subagentToolCallMax"], tc)
        out["perSubagent"].append({
            "subagentId": sid,
            "jsonlFile": os.path.relpath(jp, ROOT).replace("\\", "/"),
            "sizeBytes": os.path.getsize(jp),
            "toolCalls": tc,
            "messages": c.get("user/message", 0),
            "turns": c.get("turn/start", 0),
            "agentPreset": hdr.get("agentPreset"),
            "isSeeded": hdr.get("isSeeded"),
            "childSessionId": hdr.get("id"),
            "parentSession": hdr.get("parentSession"),
        })
    out["perSubagent"].sort(key=lambda x: -x["toolCalls"])
    return out


def user_messages(path, max_items=None, head=200):
    """All real human user messages (filters permission/plugin/runtime injections)."""
    from session_log_extract import is_real_user_message, is_injected_text
    msgs = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            typ = rec.get("type", "")
            data = rec.get("data", {})
            if typ == "user/message":
                src = data.get("source") or {}
                if not is_real_user_message(src):
                    continue
                text = "".join(p.get("text", "") for p in data.get("content", [])
                               if p.get("type") == "text")
                if not text or is_injected_text(text):
                    continue
                msgs.append({"time": rec.get("time"), "text": text})
            elif typ == "command/run":
                name = data.get("name", "")
                args = data.get("args", "")
                if name == "permission":
                    continue
                if isinstance(args, str) and args.strip():
                    msgs.append({"time": rec.get("time"), "text": args,
                                 "command": name})
    if max_items:
        msgs = msgs[:max_items]
    return msgs


def summarize(label, session_dir, manifest_entry=None):
    core = parse_session(session_dir)
    if core is None:
        raise RuntimeError(f"no session jsonl in {session_dir}")
    jp = find_jsonl(session_dir)
    raw_counts, bad_lines = line_level_stats(jp)
    indep = independent_tool_call_count(jp)

    sub = subagent_stats(session_dir)
    umsgs = user_messages(jp, max_items=None)
    catalog = subagent_catalog(jp)
    cataloged_dirs = [e for e in sub["perSubagent"] if e["subagentId"] in catalog]
    non_catalog_dirs = [e for e in sub["perSubagent"] if e["subagentId"] not in catalog]
    for e in sub["perSubagent"]:
        e["catalogedAsSubagent"] = e["subagentId"] in catalog
        if e["subagentId"] in catalog:
            e["catalogLabel"] = catalog[e["subagentId"]]["label"]
            e["catalogMode"] = catalog[e["subagentId"]]["mode"]

    first_ms = None
    last_ms = None
    with open(jp, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            t = rec.get("time")
            if isinstance(t, (int, float)) and t > 0:
                if first_ms is None or t < first_ms:
                    first_ms = t
                if last_ms is None or t > last_ms:
                    last_ms = t

    rec = dict(core)
    norm_files = {}
    for fc in core["fileChanges"]:
        np = normalize_path(fc["path"])
        entry = norm_files.setdefault(np, {"path": np, "tools": [], "rawPaths": []})
        if fc["tool"] not in entry["tools"]:
            entry["tools"].append(fc["tool"])
        if fc["path"] not in entry["rawPaths"]:
            entry["rawPaths"].append(fc["path"])
    norm_list = [norm_files[k] for k in sorted(norm_files)]
    for e in norm_list:
        e["tools"] = sorted(e["tools"])

    by_date = tool_calls_by_date(jp)
    coverage = day_range(first_ms, last_ms)

    rec.update({
        "label": label,
        "sessionId": core["sessionId"],
        "exportedAt": manifest_entry["zipMtime"] if manifest_entry else None,
        "exportedAtLocal": manifest_entry["zipMtimeLocal"] if manifest_entry else None,
        "zipName": manifest_entry["zipName"] if manifest_entry else None,
        "zipSizeBytes": manifest_entry["zipSizeBytes"] if manifest_entry else None,
        "zipSizeMB": round(manifest_entry["zipSizeBytes"] / 1048576, 2) if manifest_entry else None,
        "jsonlPath": os.path.relpath(jp, ROOT).replace("\\", "/"),

        "firstEventTimeUtc": core.get("firstEventTime"),
        "lastEventTimeUtc": core.get("lastEventTime"),
        "createdAtUtc": core.get("createdAt"),
        "createdAtLocal": local_str(core.get("createdAtEpoch")),
        "firstEventTimeLocal": local_str(first_ms),
        "lastEventTimeLocal": local_str(last_ms),
        "coverageDates": coverage,
        "activityGapDates": [d for d in coverage if d not in by_date],

        "userMessageCount": raw_counts.get("user/message", 0),
        "realUserMessageCount": len(umsgs),
        "assistantMessageCount": raw_counts.get("assistant/message", 0),
        "toolResultCount": raw_counts.get("tool/result", 0),
        "unparseableLines": bad_lines,
        "recordTypeCounts": dict(sorted(raw_counts.items(), key=lambda x: -x[1])),

        "independentToolCallCount": indep,
        "toolCallCountMatchesIndependent": indep == core["toolCallTotal_raw"],
        "countingEvidence": counting_evidence(jp),

        "subagentCount": sub["subagentCount"],
        "subagentCatalogRecordCount": len(catalog),
        "subagentCatalogedDirCount": len(cataloged_dirs),
        "subagentNonCatalogChildSessions": [
            {
                "dir": e["subagentId"],
                "childSessionId": e["childSessionId"],
                "agentPreset": e["agentPreset"],
                "isSeeded": e["isSeeded"],
                "parentSession": e["parentSession"],
                "toolCalls": e["toolCalls"],
                "explanation": ("present as a child session dir but has NO subagent/catalog "
                                "record in the parent log -> spawned outside the subagent "
                                "catalog (seeded / plugin-preset session, e.g. cordis)"),
            }
            for e in non_catalog_dirs
        ],
        "subagentToolCalls": sub["subagentToolCalls"],
        "subagentMessages": sub["subagentMessages"],
        "subagentTurns": sub["subagentTurns"],
        "subagentSteps": sub["subagentSteps"],
        "subagentToolCallMax": sub["subagentToolCallMax"],
        "perSubagent": sub["perSubagent"],

        "firstUserMessage": core["firstUserMessage"],
        "fileChangesNormalized": norm_list,
        "uniqueFilePathCount": len(norm_list),
        "uniqueFilePaths": [e["path"] for e in norm_list],
        "toolCallsByDate": by_date,
        "realUserMessages": [
            {"timeLocal": local_str(m["time"]), "command": m.get("command"), "text": m["text"]}
            for m in umsgs
        ],
    })
    return rec


def diff_versions(a, b, ka="a", kb="b"):
    """Incremental diff of two snapshots of the SAME session id."""
    fa = {json.dumps(x, sort_keys=True) for x in a["fileChanges"]}
    fb = {json.dumps(x, sort_keys=True) for x in b["fileChanges"]}
    new_files = [json.loads(x) for x in sorted(fb - fa)]
    na = {e["path"] for e in a.get("fileChangesNormalized", [])}
    nb = {e["path"] for e in b.get("fileChangesNormalized", [])}
    new_norm = sorted(nb - na)
    ra = a.get("rawToolTotals", {})
    rb = b.get("rawToolTotals", {})
    tool_delta = {}
    for k in sorted(set(ra) | set(rb)):
        if rb.get(k, 0) - ra.get(k, 0):
            tool_delta[k] = rb.get(k, 0) - ra.get(k, 0)
    return {
        "from": ka,
        "to": kb,
        "sessionId": a["sessionId"],
        "toolCallDelta": b["toolCallTotal"] - a["toolCallTotal"],
        "toolCallFrom": a["toolCallTotal"],
        "toolCallTo": b["toolCallTotal"],
        "messageDelta": b["userMessageCount"] - a["userMessageCount"],
        "realUserMessageDelta": b["realUserMessageCount"] - a["realUserMessageCount"],
        "turnDelta": b["turnCount"] - a["turnCount"],
        "stepDelta": b["stepCount"] - a["stepCount"],
        "subagentDelta": b["subagentCount"] - a["subagentCount"],
        "newFileChanges": new_files,
        "newFileChangeCount": len(new_files),
        "newFilePathsNormalized": new_norm,
        "newFilePathsNormalizedCount": len(new_norm),
        "newRealUserMessages": [m["text"][:300] for m in b["realUserMessages"][a["realUserMessageCount"]:]],
        "toolNameDelta": tool_delta,
        "coverageDatesNew": [d for d in b["coverageDates"] if d not in a["coverageDates"]],
    }


def baseline_selfcheck():
    """Re-parse the OLD sessions with the current core and compare to last round."""
    rows = []
    ok = True
    for dirname in sorted(os.listdir(OLD_BASE)):
        d = os.path.join(OLD_BASE, dirname)
        if not os.path.isdir(d):
            continue
        core = parse_session(d)
        if core is None:
            continue
        parts = core["sessionId"].split("-")
        sid8 = parts[1][:8] if len(parts) > 1 else ""
        is_canonical = sid8 in BASELINE and not re.search(r"\(\d+\)$", dirname)
        row = {
            "sessionDir": dirname,
            "sessionId": core["sessionId"],
            "id8": sid8,
            "format": core["format"],
            "toolCallTotal": core["toolCallTotal"],
            "messageCount": core["messageCount"],
            "baselineExpected": BASELINE.get(sid8),
            "isCanonicalBaselineRow": is_canonical,
        }
        if is_canonical:
            row["match"] = core["toolCallTotal"] == BASELINE[sid8]
            if not row["match"]:
                ok = False
        rows.append(row)

    canon = [r for r in rows if r["isCanonicalBaselineRow"]]
    return {
        "expected": BASELINE,
        "allMatched": ok,
        "sessions": rows,
        "canonicalBaselineRows": canon,
        "method": ("re-parsed the existing .tmp/sessions extraction with the CURRENT "
                   "verified core (parse_session) -- identical code path used for the "
                   "new exports, so a match proves the new numbers are comparable"),
    }


def main():
    with open(MANIFEST, "r", encoding="utf-8") as f:
        manifest = {m["label"]: m for m in json.load(f)}

    sessions = []
    for label in LABELS:
        d = os.path.join(NEW_BASE, label)
        if not os.path.isdir(d):
            print(f"[skip] {label}: not extracted", file=sys.stderr)
            continue
        sessions.append(summarize(label, d, manifest.get(label)))
        print(f"[ok] {label}: toolCalls={sessions[-1]['toolCallTotal']} "
              f"(independent={sessions[-1]['independentToolCallCount']}) "
              f"msgs={sessions[-1]['messageCount']} subagents={sessions[-1]['subagentCount']} "
              f"span={sessions[-1]['firstEventTimeLocal']} -> {sessions[-1]['lastEventTimeLocal']}")

    by_label = {s["label"]: s for s in sessions}

    def get(label):
        return by_label.get(label)

    version_diffs = []
    if get("6c53f724-v1") and get("6c53f724-v2"):
        version_diffs.append(diff_versions(get("6c53f724-v1"), get("6c53f724-v2"), "6c53f724-v1", "6c53f724-v2"))
    if get("6c53f724-v2") and get("6c53f724-v3"):
        version_diffs.append(diff_versions(get("6c53f724-v2"), get("6c53f724-v3"), "6c53f724-v2", "6c53f724-v3"))
    if get("6c53f724-v1") and get("6c53f724-v3"):
        version_diffs.append(diff_versions(get("6c53f724-v1"), get("6c53f724-v3"), "6c53f724-v1", "6c53f724-v3"))
    if get("51f62457-v1") and get("51f62457-v2"):
        version_diffs.append(diff_versions(get("51f62457-v1"), get("51f62457-v2"), "51f62457-v1", "51f62457-v2"))

    agg_tools = sum(s["toolCallTotal"] for s in sessions)
    agg_sub_tools = sum(s["subagentToolCalls"] for s in sessions)
    agg_files = sum(s["fileChangeCount"] for s in sessions)
    tool_breakdown = {}
    for s in sessions:
        for cat, cnt in s["toolCalls"].items():
            tool_breakdown.setdefault(cat, {"total": 0, "sessions": []})
            tool_breakdown[cat]["total"] += cnt
            tool_breakdown[cat]["sessions"].append(s["label"])
    theme_counts = {}
    for s in sessions:
        for t in s["themes"]:
            theme_counts[t] = theme_counts.get(t, 0) + 1

    # -- window timeline index: date -> which snapshot was active, how many tool calls --
    all_dates = sorted({d for s in sessions for d in s["coverageDates"]})
    timeline = {}
    for d in all_dates:
        entries = []
        for s in sessions:
            if d in s["coverageDates"]:
                entries.append({
                    "label": s["label"],
                    "sessionId": s["sessionId"],
                    "toolCallsOnDate": s["toolCallsByDate"].get(d, 0),
                    "exportedAtLocal": s["exportedAtLocal"],
                })
        timeline[d] = {
            "snapshotsActive": [e["label"] for e in entries],
            "toolCallsOnDate": {e["label"]: e["toolCallsOnDate"] for e in entries},
            "totalToolCallsOnDate": sum(e["toolCallsOnDate"] for e in entries),
        }

    focus_window = [d for d in all_dates if "2026-09-24" <= d <= "2026-09-26"]
    focus_timeline = {d: timeline[d] for d in focus_window}

    checks = []
    for s in sessions:
        checks.append({
            "check": f"{s['label']}-independent-toolcall-recount",
            "ok": s["toolCallCountMatchesIndependent"],
            "detail": f"parser={s['toolCallTotal']} byte-level={s['independentToolCallCount']}",
        })
        checks.append({
            "check": f"{s['label']}-tool-result-paired",
            "ok": s["toolResultCount"] >= s["toolCallTotal"],
            "detail": f"tool/call={s['toolCallTotal']} tool/result={s['toolResultCount']}",
        })
        checks.append({
            "check": f"{s['label']}-firstmsg-is-human",
            "ok": bool(s["firstUserMessage"]) and "danger-full-access" not in (s["firstUserMessage"] or ""),
            "detail": repr((s["firstUserMessage"] or "")[:80]),
        })
        checks.append({
            "check": f"{s['label']}-no-unparseable-lines",
            "ok": s["unparseableLines"] == 0,
            "detail": f"bad lines={s['unparseableLines']}",
        })
        checks.append({
            "check": f"{s['label']}-subagent-count-reconciled",
            "ok": (s["subagentCount"] == len(s["perSubagent"]) ==
                   s["subagentCatalogRecordCount"] + len(s["subagentNonCatalogChildSessions"])),
            "detail": (f"dirs={s['subagentCount']} parsed={len(s['perSubagent'])} "
                       f"catalog={s['subagentCatalogRecordCount']} "
                       f"non-catalog-children={len(s['subagentNonCatalogChildSessions'])}"),
        })
        checks.append({
            "check": f"{s['label']}-toolcall-date-buckets-sum",
            "ok": sum(s["toolCallsByDate"].values()) == s["toolCallTotal"],
            "detail": f"byDate={sum(s['toolCallsByDate'].values())} total={s['toolCallTotal']}",
        })
        checks.append({
            "check": f"{s['label']}-full-file-count-is-minimum",
            "ok": (s["countingEvidence"]["fullFileToolCalls"] == s["toolCallTotal"]
                   and all(v["undercountFactor"] is None or v["undercountFactor"] >= 1.0
                           for k, v in s["countingEvidence"].items() if k.startswith("headOnly"))),
            "detail": (f"full={s['countingEvidence']['fullFileToolCalls']} "
                       f"head10%={s['countingEvidence']['headOnly10pct']['toolCalls']} "
                       f"(x{s['countingEvidence']['headOnly10pct']['undercountFactor']} under)"),
        })
    checks.append({
        "check": "category-sum-equals-total-per-session",
        "ok": all(s["toolCallTotal"] == sum(s["toolCalls"].values()) for s in sessions),
        "detail": f"agg={agg_tools}",
    })

    baseline = baseline_selfcheck()
    checks.append({
        "check": "baseline-4-old-sessions-reproduced",
        "ok": baseline["allMatched"],
        "detail": json.dumps({r["id8"]: [r["toolCallTotal"], r["baselineExpected"]]
                              for r in baseline["canonicalBaselineRows"]}, ensure_ascii=False),
    })

    caveats = [
        "99cab60f-latest is the still-LIVE parent session of this extraction task "
        "(its sessionId equals the parent agent id). The snapshot ends 2026-09-26 "
        "13:31:45 local, ~1.5 min before the zip mtime, and the team "
        "'fly64-newlogs-0924-0926' was created 2026-09-26 13:34:56 -- AFTER this export. "
        "So its 09-24..09-26 content is PRE-team context, not this round's work "
        "(the string 'fly64-newlogs-0924-0926' does not appear in the snapshot). "
        "It also has a full-day activity gap: 0 tool/call records on 2026-09-25.",
        "6c53f724-v2 and 6c53f724-v3 carry BYTE-IDENTICAL sub-agent payloads "
        "(46/46 subagent jsonl files, sha256-verified out-of-band); all 46 sub-agents had "
        "already settled by the 2026-09-25 20:26 export. The v2->v3 growth "
        "(+46 tool/call, +8 turns, +8 user messages) is main-session-only.",
        "6c53f724 has 46 child-session directories under subagents/ but only 45 "
        "'subagent/catalog' records. The extra directory is session-9693cd5a-389a-4e27-a9ed-"
        "c6a3c6ec73ac (agentPreset=cordis, isSeeded=true, parentSession=session-6c53f724-...), "
        "a seeded plugin-preset child session spawned OUTSIDE the subagent catalog. "
        "This is a real spawn-path difference, not a counting error; both numbers are reported.",
        "51f62457 has 0 sub-agent directories (single-file exports) -- its 152/236 tool calls "
        "are all main-session, so it is the cleanest timing witness for 09-25 -> 09-26.",
        "fileChanges preserves the raw file_path strings from the log (mixed '\\\\' and '/' "
        "separators, some absolute D:\\\\codes\\\\flygym paths); use fileChangesNormalized / "
        "uniqueFilePaths / newFilePathsNormalized for workspace-relative POSIX paths when "
        "correlating with git.",
        "v4 export format (session.v4.jsonl) appears for the first time in these snapshots; "
        "6c53f724-v1 is still v3. scripts/session_log_extract.py was extended ADDITIVELY "
        "(v4 discovery, richer injection filtering, wall-clock coverage, optional "
        "--base/--out); the default base/output are unchanged and the old-base "
        "--check suite still passes 51/51 with the four baseline numbers intact.",
        "tool/call totals are whole-file counts: each is confirmed twice (JSON parser pass + "
        "independent byte-level regex pass) and 'countingEvidence' records what a head-only "
        "read of the same file would have yielded (10% of lines undercounts by ~8x).",
    ]

    output = {
        "meta": {
            "generatedAt": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S") + " UTC",
            "generator": "scripts/session_summary_new_logs.py",
            "coreExtractor": "scripts/session_log_extract.py::parse_session (now v4-aware)",
            "purpose": ("structured extraction of the export-logs snapshots newly added on "
                        "2026-09-26 13:33, covering 2026-09-24 -> 2026-09-26"),
            "scope": {
                "newOrUpdatedExports": [
                    {"label": "99cab60f-latest", "zip": "dsh-session-session-99cab60f-fada-4a9e-9d10-ababdd0f4373.zip",
                     "zipSizeMB": 12.58, "exportedLocal": "2026-09-26 13:33"},
                    {"label": "6c53f724-v1", "zip": "dsh-session-session-6c53f724-fab1-4db1-b7d5-5d00fff36265.zip",
                     "zipSizeMB": 4.94, "exportedLocal": "2026-09-24 16:03"},
                    {"label": "6c53f724-v2", "zip": "dsh-session-session-6c53f724-fab1-4db1-b7d5-5d00fff36265 (1).zip",
                     "zipSizeMB": 26.76, "exportedLocal": "2026-09-25 20:28"},
                    {"label": "6c53f724-v3", "zip": "dsh-session-session-6c53f724-fab1-4db1-b7d5-5d00fff36265 (2).zip",
                     "zipSizeMB": 26.90, "exportedLocal": "2026-09-26 12:30"},
                    {"label": "51f62457-v1", "zip": "dsh-session-session-51f62457-87fc-458d-ba9d-7d117ca67156.zip",
                     "zipSizeMB": 0.30, "exportedLocal": "2026-09-25 20:27"},
                    {"label": "51f62457-v2", "zip": "dsh-session-session-51f62457-87fc-458d-ba9d-7d117ca67156 (1).zip",
                     "zipSizeMB": 0.53, "exportedLocal": "2026-09-26 12:29"},
                ],
                "excluded": ("old snapshots (71c21f6d, 99cab60f (1)/(3), b2eeed98, d983cef5, ed4b8026, "
                             "f953d3fd, fdb47617, 27ed0979, 1f8fbe04, 38542b1c, 90dd512b) -- already "
                             "analysed in earlier rounds and read-only here"),
                "extractBase": ".tmp/sessions-new/",
                "untouched": [".tmp/sessions/", ".tmp/sessions_v3/", ".tmp/sessions_v5/"],
            },
            "methodNotes": [
                "tool/call counted by streaming EVERY record of the JSONL (no head sampling, no "
                "dedup by tool name) and independently re-counted at byte level -> two agreeing numbers.",
                "v4 export format (session.v4.jsonl) is new in these snapshots; the verified extractor "
                "was extended additively (v4 discovery + richer injection filtering + wall-clock "
                "coverage). Default base/output unchanged; old-base --check still passes.",
                "firstUserMessage filters source kinds plugin(:*)/agent-teams*/agent-message/"
                "subagent-settled/skill-catalog/runtime-context/user-approval/model-selection/"
                "repeat-tool-reminder/tool-jobs/compact-checkpoint/system/goal + permission command/run.",
                "times are epoch-ms in the log; local = UTC+8 (Asia/Shanghai, matches clientTimeZone).",
            ],
            "caveats": caveats,
        },
        "baselineSelfCheck": baseline,
        "sessions": sessions,
        "versionDiffs": version_diffs,
        "timelineIndex": {
            "allDates": all_dates,
            "focusWindow0924to0926": focus_timeline,
            "byDate": timeline,
            "note": ("per-date tool/call buckets let the downstream git-correlation task "
                     "attribute the 09-24 -> 09-26 work to concrete days; counts are main-session "
                     "tool/call records only (sub-agent sessions are aggregated per snapshot)"),
        },
        "aggregatedStats": {
            "sessionSnapshots": len(sessions),
            "uniqueSessionIds": len({s["sessionId"] for s in sessions}),
            "totalMainToolCalls": agg_tools,
            "totalSubagentToolCalls": agg_sub_tools,
            "totalToolCallsIncludingSubagents": agg_tools + agg_sub_tools,
            "totalFileChanges": agg_files,
            "totalUserMessages": sum(s["userMessageCount"] for s in sessions),
            "totalRealUserMessages": sum(s["realUserMessageCount"] for s in sessions),
            "totalTurns": sum(s["turnCount"] for s in sessions),
            "totalSteps": sum(s["stepCount"] for s in sessions),
            "totalSubagents": sum(s["subagentCount"] for s in sessions),
            "totalJsonlLines": sum(s["totalLines"] for s in sessions),
            "toolBreakdown": tool_breakdown,
            "themeCounts": dict(sorted(theme_counts.items(), key=lambda x: -x[1])),
        },
        "consistencyChecks": checks,
        "consistencyAllPassed": all(c["ok"] for c in checks),
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nWritten -> {OUT_PATH}")
    print(f"  snapshots={len(sessions)} main tool/call={agg_tools} "
          f"subagent tool/call={agg_sub_tools} file changes={agg_files}")
    print(f"  checks passed: {sum(1 for c in checks if c['ok'])}/{len(checks)}")
    for c in checks:
        if not c["ok"]:
            print(f"  FAIL {c['check']}: {c['detail']}")
    return output


if __name__ == "__main__":
    main()
