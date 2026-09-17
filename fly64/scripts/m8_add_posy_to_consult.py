"""Add pos_y to each help/consult context dict in plugin/runner.py.

HISTORY / WHY THIS FILE NOW FAILS LOUDLY
----------------------------------------
The first version of this script applied the three dict replacements below but
its definition-insertion `replace` never matched the source:

    searched:  '            stuck = float(mem.get("stuck_duration", 0.0))\n'
               '        no_reflex = not mem.get("reflex_active", False)'

but in runner.py `stuck = float(...)` sits at 8-space indentation and an
`if self._prim_zero_run >= 3:` block separates it from `no_reflex`.  `str.replace`
returns the string unchanged when there is no match, so the script printed
"pos_y added to consult context" and exited 0 while `pos_y_ctx` stayed
undefined — and every help-escalation path then raised NameError, i.e. the
coach crashed exactly when the fly was stuck.

This version anchors on the real source and refuses to write an undefined name.
"""
import pathlib
import sys

p = pathlib.Path("plugin/runner.py")
s = p.read_text()
before = s

# Replace each context dict to add pos_y from the memory snapshot
s = s.replace(
    '''"help_reason": "primitive_ineffective",
                "scene_name": mem.get("scene_name", "?"),
                "position": mem.get("position") or {},''',
    '''"help_reason": "primitive_ineffective",
                "scene_name": mem.get("scene_name", "?"),
                "position": mem.get("position") or {},
                "pos_y": pos_y_ctx,'''
)
s = s.replace(
    'position": mem.get("position") or {},\n                "diagnosis": "",',
    'position": mem.get("position") or {},\n                "pos_y": pos_y_ctx,\n                "diagnosis": "",'
)
s = s.replace(
    'position": mem.get("position") or {},\n                "diagnosis": f"weighted help score',
    'position": mem.get("position") or {},\n                "pos_y": pos_y_ctx,\n                "diagnosis": f"weighted help score'
)

# Add the pos_y extraction before the first return (idempotent, anchored).
ANCHOR = ('        stuck = float(mem.get("stuck_duration", 0.0))\n'
          '        if self._prim_zero_run >= 3:')
REPLACEMENT = ('        stuck = float(mem.get("stuck_duration", 0.0))\n'
               '        pos_y_ctx = mem.get("pos_y", None) '
               'or (mem.get("position") or {}).get("y", None)\n'
               '        if self._prim_zero_run >= 3:')
if "pos_y_ctx = " not in s:
    if ANCHOR not in s:
        print("ABORT: definition anchor not found in plugin/runner.py — "
              "refusing to leave pos_y_ctx undefined", file=sys.stderr)
        raise SystemExit(1)
    s = s.replace(ANCHOR, REPLACEMENT, 1)

if s == before:
    print("no change (already applied)")
else:
    p.write_text(s)
    print("pos_y added to consult context")

if "pos_y_ctx = " not in s:
    print("ABORT: pos_y_ctx still undefined after patching", file=sys.stderr)
    raise SystemExit(1)
