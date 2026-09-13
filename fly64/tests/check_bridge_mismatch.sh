#!/bin/bash
p=2796
echo "exe: $(readlink /proc/$p/exe)"
echo "cwd: $(readlink /proc/$p/cwd)"
echo "started: $(ps -o lstart= -p $p)"
echo "--- writers of each bridge (last 30s mtime) ---"
for b in /tmp/f64b /tmp/f64b_traj; do
  echo "$b mtime: $(stat -c %y $b)"
done
echo "--- fuser ---"
fuser -v /tmp/f64b 2>&1 | head -3
fuser -v /tmp/f64b_traj 2>&1 | head -3
echo "--- flow.json live ---"
curl -s http://127.0.0.1:8765/flow.json | python3 -c 'import json,sys; d=json.load(sys.stdin); print("brain_version:", d.get("brain_version"), "| visual(frame_age):", d.get("frame_age","n/a"), "| scene:", d.get("scene_name"))' 2>&1
