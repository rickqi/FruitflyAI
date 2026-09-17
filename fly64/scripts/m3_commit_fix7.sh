#!/bin/bash
set -e
cd /mnt/d/codes/flygym/fly64
python3 -m pytest tests/ -q 2>&1 | tail -1
cd /mnt/d/codes/flygym
git add fly64/fly64/main.py fly64/skills/skills.md \
    fly64/skills/evolution_history.json fly64/scripts/ver_append_fix7.py \
    fly64/scripts/fix7_deploy_restart.sh fly64/scripts/m6_state_probe.py
git commit -q -m 'fix(main): R31-fix7 adaptive below-ground escape burst

fallen at y=-954 with fixed 1.5s burst could never reset physics.
New burst duration is adaptive:
  base 1.5s + depth_factor (+3s per 500u below -200) + stuck_aggression
  (+1s per 20s stuck) capped at 12s; slight x oscillation helps find
  terrain edge.  Maths at y=-954: 1.5+4.5+0.25=6.3s burst.
Pin test coverage: main.py compilation + deployment restart.'
git push origin master 2>&1 | tail -2