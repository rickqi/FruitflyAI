#!/bin/bash
cd /mnt/d/codes/flygym/fly64
git stash -q 2>/dev/null
python3 -m pytest tests/test_coach_pipeline.py tests/test_trajectory_height.py tests/test_evolution_capability.py::TestEvoRound10 tests/test_memory.py::test_repulsion_positive_with_many_revisits tests/test_p1_neural_takeover.py::TestKpiBaseline -q 2>&1 | grep FAILED > /tmp/sub_base.txt
git checkout -- skills/evolution_history.json skills/skills.md fly64/skills/evolution_history.json 2>/dev/null
git stash pop 2>/dev/null
python3 -m pytest tests/test_coach_pipeline.py tests/test_trajectory_height.py tests/test_evolution_capability.py::TestEvoRound10 tests/test_memory.py::test_repulsion_positive_with_many_revisits tests/test_p1_neural_takeover.py::TestKpiBaseline -q 2>&1 | grep FAILED > /tmp/sub_now.txt
diff /tmp/sub_base.txt /tmp/sub_now.txt
git stash list | wc -l
