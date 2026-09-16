#!/bin/bash
set -e
cd /mnt/d/codes/flygym
git diff stash@{0}^! -- . \
  ':(exclude)fly64/tests/test_escape_release.py' \
  ':(exclude)fly64/skills/README.md' \
  ':(exclude)fly64/skills/active_strategy.json' \
  > /tmp/stash_rest.patch
echo "patch lines: $(wc -l < /tmp/stash_rest.patch)"
cd /mnt/d/codes/flygym/fly64
git apply --check /tmp/stash_rest.patch && git apply /tmp/stash_rest.patch && echo "PATCH APPLIED (3 conflict files skipped)"
cd /mnt/d/codes/flygym && git stash drop
echo "stash dropped; remaining: $(git stash list | wc -l)"
