#!/bin/bash
set -e
cd /mnt/d/codes/flygym/fly64
python3 -m pytest tests/ -q 2>&1 | tail -1
cd /mnt/d/codes/flygym
git add fly64/fly64/main.py fly64/fly64/memory.py fly64/tests/test_memory.py \
    fly64/skills/skills.md fly64/skills/evolution_history.json \
    fly64/scripts/ver_append_fix5.py fly64/scripts/fix5_deploy_restart.sh
git commit -q -m 'fix(memory): R31-fix5 micro_loop reflex cy=0->30 zig-zag not spin-in-place

User reported Mario appears stuck during micro_loop; analysis showed the
reflex turn phase produced pure rotation (x=69, y=0) with alternating
hard turns cancelling translation visibly spinning in place.

Fix: turn phase cy=0 to 30 so oscillation produces zig-zag forward instead.
All memory tests pass (2 pre-existing KeyError baseline).'
git push origin master 2>&1 | tail -2