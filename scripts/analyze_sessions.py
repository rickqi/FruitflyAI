#!/usr/bin/env python3
"""Extract and summarize all DSH session logs for project analysis."""
import json, os

dst = "D:\\codes\\flygym\\.tmp\\sessions"
output = []

for d in sorted(os.listdir(dst)):
    dp = os.path.join(dst, d)
    if not os.path.isdir(dp):
        continue

    jsonls = []
    for root, dirs, fnames in os.walk(dp):
        for f in fnames:
            if "session" in f and f.endswith(".jsonl"):
                jsonls.append(os.path.join(root, f))
    jsonls.sort(key=os.path.getsize, reverse=True)

    session_data = {"name": d, "files": []}

    for jl in jsonls[:3]:
        sz = os.path.getsize(jl)
        rel = os.path.relpath(jl, dp)

        msgs = []
        file_changes = set()
        types = {}

        with open(jl, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    t = rec.get("type", "")
                    types[t] = types.get(t, 0) + 1

                    if t == "user/message":
                        text = rec.get("data", {}).get("text", "")
                        if text:
                            msgs.append(text[:300])

                    elif t == "command/run" and rec.get("data", {}).get("name") == "edit":
                        fp = rec.get("data", {}).get("args", {}).get("file_path", "")
                        if fp:
                            file_changes.add(fp)

                    elif t == "tool/use":
                        tool = rec.get("data", {}).get("name", "")
                        if tool in (
                            "brain_analyze", "brain_risk_map", "brain_steer",
                            "ghb_analyze", "ghb_query", "ghb_reports",
                            "oa_analyze", "oa_execute", "oa_approve_task",
                            "agent_teams_create", "agent_teams_approve",
                        ):
                            msgs.append("[TOOL:%s]" % tool)

                except json.JSONDecodeError:
                    pass

        session_data["files"].append({
            "rel": rel,
            "sizeKB": sz // 1024,
            "types": types,
            "user_msgs": msgs[:25],
            "file_changes": sorted(file_changes)[:15],
        })

    output.append(session_data)

# Print overview
for s in sorted(output, key=lambda x: x["files"][0]["sizeKB"] if x["files"] else 0, reverse=True):
    main = s["files"][0] if s["files"] else {}
    print("--- %s ---" % s["name"][:50])
    print("  Size: %dKB | UserMsgs: %d | ToolCalls: %d" % (
        main.get("sizeKB", 0),
        main.get("types", {}).get("user/message", 0),
        main.get("types", {}).get("tool/use", 0),
    ))
    print("  Files: %s" % main.get("file_changes", [])[:5])
    first_msgs = main.get("user_msgs", [])[:5]
    for m in first_msgs:
        print("  > %s" % m[:120])
    last_msgs = main.get("user_msgs", [])[-3:]
    if last_msgs and last_msgs != first_msgs[-3:]:
        print("  ...")
        for m in last_msgs:
            print("  < %s" % m[:120])
    print()