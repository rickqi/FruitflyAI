#!/bin/bash
echo "== procs =="
pgrep -af 'fly64.main|sm64.us' | grep -v grep
echo "== brain log =="
tail -8 /tmp/fly64_run.log
echo "== flow probe =="
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8765/flow.json
