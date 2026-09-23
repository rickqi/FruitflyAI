#!/bin/bash
# Verify the coach advice -> brain consumption chain, live.
B=http://127.0.0.1:8765
echo "=== coach_advice.json (latest) ==="
python3 - <<'PY'
import json
try:
    d=json.load(open('/root/fly64/skills/coach_advice.json',encoding='utf-8'))
    print('  model :', d.get('model'))
    print('  ts    :', d.get('ts') or d.get('timestamp'))
    print('  source:', d.get('source'))
    adv=(d.get('advice') or '')
    print('  advice:', adv[:200].replace('\n',' '))
    st=d.get('strategy') or {}
    print('  strategy keys:', list(st.keys())[:12])
    for k,v in list(st.items())[:8]:
        print('     %-34s %s' % (k, str(v)[:70]))
except Exception as e:
    print('  ERR', e)
PY
echo
echo "=== active_strategy.json (what the brain hot-loads) ==="
python3 - <<'PY'
import json
try:
    d=json.load(open('/root/fly64/skills/active_strategy.json',encoding='utf-8'))
    print('  __generation:', d.get('__generation'))
    for sec in ('exploration','escape','reflex','coach','memory','navigation'):
        s=d.get(sec)
        if isinstance(s,dict):
            print('  [%s] %s' % (sec, ', '.join('%s=%s'%(k,str(v)[:24]) for k,v in list(s.items())[:6])))
except Exception as e:
    print('  ERR', e)
PY
echo
echo "=== does the brain report the coach values as APPLIED? ==="
curl -s -m 5 $B/memory.json | python3 -c "
import json,sys
d=json.load(sys.stdin)
ca=d.get('coach_applied')
print('  coach_applied:', json.dumps(ca,ensure_ascii=False)[:400] if ca else '(absent)')
"
echo
echo "=== is the brain still consuming new advice? (strategy file mtime vs now) ==="
stat -c '  active_strategy.json mtime: %y' /root/fly64/skills/active_strategy.json | cut -c1-40
date '+  now                       : %Y-%m-%d %H:%M:%S'
echo
echo "=== service health ==="
python3 - <<'PY'
import json
try:
    d=json.load(open('/root/fly64/plugin/service_status.json',encoding='utf-8'))
    h=d.get('health') or {}
    print('  health:', json.dumps(h,ensure_ascii=False)[:300])
    print('  cycle :', d.get('cycle'), '| last_error:', str(d.get('last_error'))[:80])
except Exception as e:
    print('  ERR', e)
PY
