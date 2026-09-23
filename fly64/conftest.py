"""Test-session isolation: the suite must never write what the running system owns.

Two incidents, one rule.

1. Evidence corpus (t9).  A test run wrote into the LIVE evidence paths —
   ``skills/coach_outcomes.jsonl`` and ``plugin/.pending_outcome.json``.  The
   corpus shrank from 45 real coach outcomes to 30 synthetic test rows, and
   because ``*.jsonl`` is git-ignored and the Windows mirror was stale, the real
   evidence was unrecoverable.  That corpus was the sole basis for the P4.4
   instinct-consolidation promotion evidence and for curriculum ok/fail streaks.
   → ``FLY64_EVIDENCE_DIR`` is redirected to a temp dir below.

2. Coach / strategy artifacts (P1-4, A3 §5.4).  Three modules wrote live files:
   * ``tests/test_t3_handshake.py`` had NO test function, so pytest only
     *imported* it — and the import ran the handshake for real, rewriting the
     git-tracked ``plugin/.consult_request.json`` / ``.consult_response.json``
     (byte-level proof: A3 §5.4; reproduced here at 23:20:59, hash
     C439DF3A→968A40B1);
   * ``tests/test_phase6_fitness_inputs.py`` called the real ``_inject()``
     through ``BrainMutator.evaluate()``, writing the brain's
     ``skills/active_strategy.json`` and bumping ``__generation`` — measured
     +3 per run (326 → 332 while this guard was being written), i.e. every test
     run poisoned the parameter state EVO reads;
   * the guard itself then exposed two more (fixed in the same pass).
   → the offending tests now write to ``tmp_path``, and everything below fails
   the session if a protected artifact is changed *by the test process* anyway.

What fails, and what only warns
-------------------------------
The guard compares fingerprints taken at session start / before each test with
the ones taken afterwards; that part is purely session-internal (never "is the
git tree clean", which would fire on any pre-existing live change).

Because a shared checkout can also be moved by *another* writer during the same
window (a concurrent pytest session, the live brain/coach), the guard attributes
each change:

* **written by this test process** (tracked by intercepting the write
  primitives, see ``_install_write_tracker``) → HARD FAILURE, and the test that
  did it is named;
* **changed but never written by this process** → a loud warning naming the file
  and both hashes, but no failure: failing another agent's session for a file it
  never touched is how a guard turns into noise and gets switched off.

Measured on the full suite: of 7 flagged transitions, 3 were real in-process
writers (``test_phase6_fitness_inputs.py``) and 4 fell inside tests that are
clean when run alone — i.e. they came from concurrent processes.  The split is
what makes the guard usable in this workspace.

Known limitation: a write performed by a *subprocess* of the test (``python -c``,
a shell script) is not attributable and is therefore reported as a warning
rather than a failure.  All writers found in this repository are in-process.

Shared-workspace caveat
-----------------------
Fingerprints are per session, so a pre-existing dirty artifact is never reported
(the working tree carried such a file all along: ``skills/active_strategy.json``
and ``plugin/.consult_request.json`` are dirty at HEAD in practice).  Only
movement *during* the session counts.
"""
from __future__ import annotations

import atexit
import builtins
import hashlib
import os
import shutil
import tempfile
from pathlib import Path

import pytest

# ── 1. evidence-dir redirect (t9 incident) ───────────────────────────────
_EVIDENCE_DIR = tempfile.mkdtemp(prefix="fly64-test-evidence-")
os.environ["FLY64_EVIDENCE_DIR"] = _EVIDENCE_DIR

atexit.register(shutil.rmtree, _EVIDENCE_DIR, True)


# ── 2. production-artifact guard (P1-4) ──────────────────────────────────
FLY64_ROOT = Path(__file__).resolve().parent

#: Live artifacts owned by the running coach / brain.  Tests may READ them
#: (config assertions are legitimate) but must never mutate them: a mutated
#: artifact both corrupts the running system and makes the test result depend on
#: run order/state.  Extend this tuple whenever a new live artifact appears —
#: the guard is only as good as this list.
PRODUCTION_ARTIFACTS = (
    "plugin/.consult_request.json",
    "plugin/.consult_response.json",
    "skills/active_strategy.json",
    "skills/coach_advice.json",
)

#: resolved-path -> fly64-relative name, and the cheap basename pre-filter used
#: by the write tracker (a process opens far more files than it writes here).
_WATCHED_PATHS = {str((FLY64_ROOT / rel).resolve()): rel
                  for rel in PRODUCTION_ARTIFACTS}
_WATCHED_NAMES = {Path(rel).name for rel in PRODUCTION_ARTIFACTS}


def _fingerprint(path: Path):
    """(exists, sha256, size) — enough to catch any rewrite, cheap enough to
    take around every test."""
    try:
        blob = path.read_bytes()
    except FileNotFoundError:
        return (False, "", 0)
    except OSError as exc:  # unreadable (locked/in use) — still worth reporting
        return (True, "unreadable:%s" % exc.errno, -1)
    return (True, hashlib.sha256(blob).hexdigest(), len(blob))


def snapshot_artifacts() -> dict:
    """Fingerprint every protected artifact, keyed by its fly64/-relative path."""
    return {rel: _fingerprint(FLY64_ROOT / rel) for rel in PRODUCTION_ARTIFACTS}


def _describe(before, after) -> str:
    (b_exists, b_sha, b_size) = before
    (a_exists, a_sha, a_size) = after
    if b_exists and not a_exists:
        return "DELETED (was %d B, sha %s)" % (b_size, b_sha[:12])
    if a_exists and not b_exists:
        return "CREATED (%d B, sha %s)" % (a_size, a_sha[:12])
    return ("MODIFIED (%d B -> %d B, sha %s -> %s)"
            % (b_size, a_size, b_sha[:12], a_sha[:12]))


def artifact_changes(before: dict, after: dict) -> dict:
    """{relative path: description} for every protected artifact that moved."""
    changes = {}
    for rel in PRODUCTION_ARTIFACTS:
        old, new = before.get(rel), after.get(rel)
        if old != new:
            changes[rel] = _describe(old, new)
    return changes


def _bullets(changes: dict) -> str:
    return "\n".join("  %-36s %s" % (rel, desc)
                     for rel, desc in sorted(changes.items()))


_REDIRECT_HINT = (
    "Redirect the write instead, e.g.\n"
    "    StrategyWriter(strategy_path=tmp_path / 'active_strategy.json',\n"
    "                   advice_path=tmp_path / 'coach_advice.json')\n"
    "    GLMConsultant(request_path=tmp_path / 'req.json',\n"
    "                  response_path=tmp_path / 'resp.json', ...)\n"
    "    pytest.mark.usefixtures('sandboxed_skill_dir')   # for _inject()/skills\n"
    "    PluginRunner(..., writer=..., consultant=..., fetcher=...)\n"
    "Guard: fly64/conftest.py (PRODUCTION_ARTIFACTS)."
)


def _failure_message(changes: dict, where: str) -> str:
    return (
        "PRODUCTION ARTIFACT GUARD (P1-4 test isolation) FAILED: the test session "
        "%s\n\n%s\n\n"
        "These paths belong to the RUNNING system (coach plugin / brain), not to "
        "the test suite, and this process is what wrote them: the test would "
        "corrupt live state and make its own result depend on prior runs.\n%s"
        % (where, _bullets(changes), _REDIRECT_HINT)
    )


def _external_warning(changes: dict) -> str:
    return (
        "PRODUCTION ARTIFACT GUARD (P1-4): production artifact(s) moved during "
        "this session but were NOT written by this test process:\n\n%s\n\n"
        "Nothing in this session is failing for it — a concurrent writer (another "
        "pytest session in this shared checkout, or the live brain/coach) is the "
        "likely author.  If it was another pytest session, that session has a "
        "test that still writes production: find it with its own guard output."
        % _bullets(changes)
    )


# ── in-process write attribution ─────────────────────────────────────────

#: Protected artifacts written by THIS process, filled in by the tracker below.
_IN_PROCESS_WRITES: set = set()
_TRACKER_ORIGINALS = None


def _note_write(target) -> None:
    """Record ``target`` if it is one of the protected artifacts (cheap first)."""
    if _TRACKER_ORIGINALS is None:
        return
    try:
        if os.path.basename(os.fspath(target)) not in _WATCHED_NAMES:
            return
        rel = _WATCHED_PATHS.get(str(Path(os.fspath(target)).resolve()))
    except (TypeError, ValueError, OSError):
        return
    if rel:
        _IN_PROCESS_WRITES.add(rel)


def _install_write_tracker() -> None:
    """Intercept the write primitives so a change can be attributed.

    Only the paths named in ``PRODUCTION_ARTIFACTS`` are recorded; everything
    else falls straight through to the original implementation.
    """
    global _TRACKER_ORIGINALS
    if _TRACKER_ORIGINALS is not None:
        return

    def write_text(self, *args, **kwargs):
        _note_write(self)
        return originals["write_text"](self, *args, **kwargs)

    def write_bytes(self, *args, **kwargs):
        _note_write(self)
        return originals["write_bytes"](self, *args, **kwargs)

    def path_open(self, *args, **kwargs):
        mode = args[0] if args else kwargs.get("mode", "r")
        if isinstance(mode, str) and any(ch in mode for ch in "wax+"):
            _note_write(self)
        return originals["path_open"](self, *args, **kwargs)

    def _open(file, *args, **kwargs):
        mode = args[0] if args else kwargs.get("mode", "r")
        if isinstance(mode, str) and any(ch in mode for ch in "wax+"):
            _note_write(file)
        return originals["open"](file, *args, **kwargs)

    def replace(src, dst, *args, **kwargs):
        _note_write(dst)
        return originals["replace"](src, dst, *args, **kwargs)

    def rename(src, dst, *args, **kwargs):
        _note_write(dst)
        return originals["rename"](src, dst, *args, **kwargs)

    originals = {
        "write_text": Path.write_text, "write_bytes": Path.write_bytes,
        "path_open": Path.open, "open": builtins.open,
        "replace": os.replace, "rename": os.rename,
    }
    Path.write_text, Path.write_bytes, Path.open = write_text, write_bytes, path_open
    builtins.open = _open
    os.replace, os.rename = replace, rename
    _TRACKER_ORIGINALS = originals


def _remove_write_tracker() -> None:
    global _TRACKER_ORIGINALS
    if _TRACKER_ORIGINALS is None:
        return
    Path.write_text = _TRACKER_ORIGINALS["write_text"]
    Path.write_bytes = _TRACKER_ORIGINALS["write_bytes"]
    Path.open = _TRACKER_ORIGINALS["path_open"]
    builtins.open = _TRACKER_ORIGINALS["open"]
    os.replace = _TRACKER_ORIGINALS["replace"]
    os.rename = _TRACKER_ORIGINALS["rename"]
    _TRACKER_ORIGINALS = None


#: Fingerprints taken before any test module is imported/collected, so a write
#: that happens at COLLECTION time (the test_t3_handshake.py failure mode) is
#: still visible at session end.  Refreshed in pytest_configure, which also keeps
#: a process that calls ``pytest.main()`` twice from comparing against a stale
#: snapshot.
_SESSION_SNAPSHOT = snapshot_artifacts()


def pytest_configure(config):
    global _SESSION_SNAPSHOT
    _SESSION_SNAPSHOT = snapshot_artifacts()
    config._fly64_artifact_violations = {}
    config._fly64_external_changes = {}
    _install_write_tracker()


@pytest.fixture(autouse=True)
def _fly64_production_artifact_guard(request):
    """Fail the offending TEST when it writes a production artifact.

    Autouse and function-scoped on purpose: it names the test that did it rather
    than only the session.  The session-level hooks below are the backstop for
    writes that happen before the first test runs (collection/import time).
    """
    before = snapshot_artifacts()
    writes_before = set(_IN_PROCESS_WRITES)
    yield
    changes = artifact_changes(before, snapshot_artifacts())
    if not changes:
        return
    mine = {rel: desc for rel, desc in changes.items()
            if rel in (_IN_PROCESS_WRITES - writes_before)}
    foreign = {rel: desc for rel, desc in changes.items() if rel not in mine}
    if foreign:  # reported once, in the terminal summary; never a failure
        request.config._fly64_external_changes.update(foreign)
    if mine:
        pytest.fail(_failure_message(
            mine, "WROTE production artifacts from inside a test:"), pytrace=False)


def pytest_sessionfinish(session, exitstatus):
    """Backstop: catch writes that happened outside any test (collection/import)."""
    changes = artifact_changes(_SESSION_SNAPSHOT, snapshot_artifacts())
    config = session.config
    config._fly64_artifact_violations = {
        rel: desc for rel, desc in changes.items() if rel in _IN_PROCESS_WRITES}
    config._fly64_external_changes.update(
        {rel: desc for rel, desc in changes.items()
         if rel not in _IN_PROCESS_WRITES})
    # A path this process wrote is never "somebody else's change": drop it from
    # the external notice so a real violation is not explained away twice.
    config._fly64_external_changes = {
        rel: desc for rel, desc in config._fly64_external_changes.items()
        if rel not in _IN_PROCESS_WRITES}
    if config._fly64_artifact_violations and session.exitstatus == pytest.ExitCode.OK:
        # Report failure with a non-zero exit code; the banner is printed in the
        # terminal summary below, which always runs.
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
    _remove_write_tracker()


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    violations = getattr(config, "_fly64_artifact_violations", None)
    external = getattr(config, "_fly64_external_changes", None)
    if violations:
        terminalreporter.write_sep("=", "PRODUCTION ARTIFACT GUARD FAILED (P1-4)")
        terminalreporter.write_line(_failure_message(
            violations,
            "WROTE production artifacts (detected at session end; an ERROR entry "
            "above names the test when the write happened inside one):"))
        terminalreporter.write_sep("=", "end production artifact guard")
    if external:
        terminalreporter.write_sep("-", "PRODUCTION ARTIFACT GUARD: external change")
        terminalreporter.write_line(_external_warning(external), yellow=True)
        terminalreporter.write_sep("-", "end external change notice")


# ── sandbox helpers for the known live writers ───────────────────────────

@pytest.fixture()
def sandboxed_skill_dir(tmp_path, monkeypatch):
    """Point ``skills.evolution_skill.SKILL_DIR`` at a per-test copy.

    ``BrainMutator._inject()`` writes ``SKILL_DIR/"active_strategy.json"`` — the
    very file the brain hot-reloads — and bumps its ``__generation``, so a test
    that drives the real injector mutates live parameter state.  The sandbox
    keeps the REAL writer under test (no production path, no behavioural stub)
    while the write lands in ``tmp_path``.
    """
    from skills import evolution_skill

    sandbox = tmp_path / "skills"
    sandbox.mkdir()
    live = FLY64_ROOT / "skills" / "active_strategy.json"
    try:
        if live.exists():
            shutil.copyfile(live, sandbox / "active_strategy.json")
    except OSError:
        pass  # a live writer held it — the injector simply starts from scratch
    monkeypatch.setattr(evolution_skill, "SKILL_DIR", sandbox, raising=True)
    return sandbox
