#!/usr/bin/env python3
"""Extract AgentTeams team/member usage and recent activity across sessions."""
import io
import os
import re
import sys
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = r".tmp\sessions_v3"
pat_join = re.compile(r'joined the team "([^"]+)"')
pat_label = re.compile(r"agent-teams:([A-Za-z0-9._-]+):([A-Za-z0-9._-]+)")
pat_team_id = re.compile(r'"teamId"\s*:\s*"([^"]+)"')

teams = Counter()
members = Counter()

for root, _dirs, files in os.walk(ROOT):
    for fn in files:
        if not fn.endswith(".jsonl"):
            continue
        p = os.path.join(root, fn)
        try:
            fh = open(p, encoding="utf-8", errors="replace")
        except OSError:
            continue
        with fh:
            for line in fh:
                for m in pat_join.finditer(line):
                    teams[m.group(1)] += 1
                for m in pat_team_id.finditer(line):
                    teams[m.group(1)] += 1
                for m in pat_label.finditer(line):
                    members[(m.group(1), m.group(2))] += 1

print("=== TEAMS (%d unique) ===" % len(teams))
for t, n in teams.most_common(80):
    print("  %-46s %d" % (t, n))
print()
print("=== AGENTTEAMS (team, member) ===")
for (t, m), n in members.most_common(100):
    print("  %-38s %-26s %d" % (t, m, n))
