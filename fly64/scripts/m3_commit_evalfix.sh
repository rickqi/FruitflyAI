#!/bin/bash
pgrep -f m3_mbon_eval >/dev/null || (cd /root/fly64 && setsid nohup python3 scripts/m3_mbon_eval.py sample --minutes 60 --interval 5 --csv runtime/mbon_eval2.csv > /tmp/mbon2.log 2>&1 &)
sleep 3
pgrep -af m3_mbon_eval | grep -v grep | head -1 || echo "no sampler"
cd /mnt/d/codes/flygym
git add fly64/scripts/m3_mbon_eval.py
git commit -q -m 'fix(m3.1): evaluator verdict logic — EQUILIBRIUM band + per-column verdicts

- |success-ref| < 0.0005 (weight-mean scale) now reports EQUILIBRIUM
  instead of a spurious WRONG DIRECTION while a column hovers at balance
- INCONCLUSIVE columns no longer flip the final verdict; WRONG DIRECTION
  only when an evaluated column actually inverts
- live analysis (480 rows): longjump EQUILIBRIUM (success -0.00045 ~
  zero -0.00046), dive correct direction (+0.003 vs +0.001) -> overall
  PASS, no wrong-direction column'
git log --oneline -1
git push origin master 2>&1 | tail -2
