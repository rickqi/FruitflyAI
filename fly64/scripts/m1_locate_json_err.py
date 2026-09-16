import json
try:
    json.load(open("skills/fix_catalog.json"))
    print("VALID")
except json.JSONDecodeError as e:
    print("ERROR:", e.msg, "line", e.lineno, "col", e.colno)
    lines = open("skills/fix_catalog.json", errors="replace").read().splitlines()
    line = lines[e.lineno - 1]
    lo = max(0, e.colno - 60)
    print("context:", repr(line[lo:e.colno + 60]))
    print("bad char:", repr(line[e.colno - 1:e.colno + 2]))
