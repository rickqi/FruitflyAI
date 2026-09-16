#!/bin/bash
for p in $(pgrep -f 'python'); do
  exe=$(readlink /proc/$p/exe 2>/dev/null)
  cwd=$(readlink /proc/$p/cwd 2>/dev/null)
  cmd=$(tr '\0' ' ' < /proc/$p/cmdline 2>/dev/null | head -c 120)
  echo "$p | $cwd | $cmd"
done | grep -iv 'pgrep\|tmp_check'
