#!/bin/bash
set -e
cd /mnt/d/codes/flygym/fly64
python3 -m pytest tests/ -q 2>&1 | tail -1
cd /mnt/d/codes/flygym
git add fly64/fly64/main.py fly64/plugin/runner.py \
    fly64/skills/evolution_history.json \
    fly64/scripts/ver_append_fix8.py fly64/scripts/fix8_deploy_restart.sh \
    fly64/scripts/m7_coach_check.py fly64/scripts/m8_add_posy_to_consult.py \
    fly64/scripts/m8_check_posy.py fly64/scripts/m8_coach_analysis.py
git commit -q -m 'feat(coach): R31-fix8 command.turn_and_go consumer + pos_y telemetry (2.23.5)

Coach advice was a dead protocol: prompt demanded {command:{heading,duration,y}}
but the brain never consumed it.  Now main.py reads active_strategy.command
and executes P-I heading tracking (yaw_diff -> control.x) with timed duration.
Also: pos_y field added to memory_json (for coach context) and runner.py
threads it into all consult escalation paths so the GLM knows altitude
(e.g. y=-954 void cannot be escaped by "walk toward the door").
Full cpts 28 baseline green.'
git push origin master 2>&1 | tail -2