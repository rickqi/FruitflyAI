"""Test-session isolation for the evolution evidence base.

Why this exists (incident, t9): a test run wrote into the LIVE evidence paths —
``skills/coach_outcomes.jsonl`` and ``plugin/.pending_outcome.json``.  The
corpus shrank from 45 real coach outcomes to 30 synthetic test rows, and
because ``*.jsonl`` is git-ignored and the Windows mirror was stale, the real
evidence was unrecoverable.  That corpus was the sole basis for the P4.4
instinct-consolidation promotion evidence and for curriculum ok/fail streaks.

conftest.py is imported by pytest BEFORE the test modules, so setting the
override here happens before ``plugin.coach_outcomes`` / ``fly64.instinct_bindings``
evaluate their module-level path constants.

The variable is set unconditionally (not setdefault): a stray value inherited
from the environment must never be able to point a test session at production.
"""
import atexit
import os
import shutil
import tempfile

_EVIDENCE_DIR = tempfile.mkdtemp(prefix="fly64-test-evidence-")
os.environ["FLY64_EVIDENCE_DIR"] = _EVIDENCE_DIR

atexit.register(shutil.rmtree, _EVIDENCE_DIR, True)
