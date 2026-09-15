#!/bin/bash
# Inventory: files that differ between WSL runtime and Windows repo
W=/root/fly64
D=/mnt/d/codes/flygym/fly64
for rel in fly64/main.py fly64/model.py fly64/memory.py fly64/retina.py fly64/telemetry.py \
           fly64/mushroom_body.py fly64/gain_modulation.py fly64/central_complex.py fly64/scene_recognition.py \
           plugin/service.py plugin/runner.py plugin/watchdog.sh plugin/llm_consult.py plugin/strategy_writer.py plugin/__init__.py \
           scripts/consolidate.sh scripts/phase2_gate.sh scripts/watchdog.sh \
           skills/evolution_skill.py skills/skills.md skills/__init__.py skills/README.md skills/default_patterns.json \
           web/dashboard.js web/index.html web/dashboard.css web/memory-heatmap.js \
           tests/test_evolution_capability.py tests/test_retina.py tests/test_dashboard_protocol.py \
           tests/test_service.py tests/test_autonomy_regression.py tests/test_mushroom_body.py tests/test_plugin_mhr.py \
           tests/test_memory.py tests/test_dashboard_js.py tests/check_version.py; do
  if [[ ! -f "$D/$rel" && -f "$W/$rel" ]]; then
    echo "WSL-ONLY: $rel"
  elif [[ -f "$D/$rel" && ! -f "$W/$rel" ]]; then
    echo "WIN-ONLY: $rel"
  elif [[ -f "$D/$rel" && -f "$W/$rel" ]]; then
    if ! cmp -s "$W/$rel" "$D/$rel"; then
      echo "DIFF:     $rel"
    fi
  fi
done
echo "=== version check (WSL) ==="
grep -m1 'BRAIN_VERSION = ' $W/fly64/main.py
