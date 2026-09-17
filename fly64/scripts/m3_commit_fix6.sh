#!/bin/bash
set -e
cd /mnt/d/codes/flygym/fly64
python3 -m pytest tests/ -q 2>&1 | tail -1
cd /mnt/d/codes/flygym
git add fly64/fly64/main.py fly64/fly64/memory.py fly64/skills/skills.md \
    fly64/skills/evolution_history.json fly64/tests/test_memory.py \
    fly64/scripts/ver_append_fix6.py fly64/scripts/fix6_deploy_restart.sh
git commit -q -m 'fix(anomaly): R31-fix6 micro_loop disp_60s gate — progress prevents false stuck

micro_loop stuck_duration was saturating (~96s) even after R31-fix5 added
cy=30 forward component, because the anomaly classifier only looks at turn
pattern, not displacement. Real data showed disp_60s>3000u + coverage growth
but stuck_duration kept climbing.

Fix: _detect_micro_loop Tier 2 adds disp_60s gate: when displacement > 300u
AND loop_score < 0.8, the pattern is "zig-zag progress" not true stuck.
disp_60s threaded through _vote -> update -> MemoryController.anomaly.update.
Memory tests 100 passed (2 baseline KeyError).'
git push origin master 2>&1 | tail -2