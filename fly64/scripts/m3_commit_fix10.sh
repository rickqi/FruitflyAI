#!/bin/bash
set -e
cd /mnt/d/codes/flygym/fly64
python3 -m pytest tests/ -q 2>&1 | tail -1
cd /mnt/d/codes/flygym
git add fly64/fly64/memory.py fly64/fly64/main.py \
    fly64/skills/evolution_history.json fly64/scripts/fix10_deploy_restart.sh
git commit -q -m 'fix(spatial): R31-fix10 loop_score decays under sustained displacement

2228s stuck with high loop and 480u/60s disp: loop_score stayed saturated
at 0.99+ because revisit counts never decayed even while making progress.
Now SpatialMemory.update accepts disp_60s; every 30 ticks with disp>500u
each window count drops by 1, so loop_score gradually falls even when
circling.  Anomaly detectors using loop_score naturally benefit.'
git push origin master 2>&1 | tail -2