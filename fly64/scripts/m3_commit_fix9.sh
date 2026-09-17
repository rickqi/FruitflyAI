#!/bin/bash
set -e
cd /mnt/d/codes/flygym/fly64
python3 -m pytest tests/ -q 2>&1 | tail -1
cd /mnt/d/codes/flygym
git add fly64/fly64/main.py fly64/fly64/model.py \
    fly64/tests/test_coach_dopamine.py fly64/skills/evolution_history.json \
    fly64/scripts/ver_append_fix9.py fly64/scripts/fix9_deploy_restart.sh \
    fly64/scripts/m9_verify_loop.py fly64/scripts/m8_coach_analysis.py
git commit -q -m 'feat(dopamine): R31-fix9 coach→dopamine pathway — GLM advice drives learning (2.23.6)

Coach output was a behaviour-only channel; now it reaches the dopamine
system directly.  active_strategy["dopamine"] {"bias": ±0.3} applies a
sustained shift to the MB dopamine signal; {"setback": ±1.0} fires a
one-shot pulse via add_setback.  Both feed into KC→MBON three-factor
plasticity — the coach can now tag scenes as rewarding or aversive.
Tests: 7 cases (parsing/model integration/wiring contract).'
git push origin master 2>&1 | tail -2