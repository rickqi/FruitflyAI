"""T3 handshake: the DSH host agent answers a consult request through files.

Incident this file closes (A3 §5.4 / P1-4)
------------------------------------------
This module used to be a *script*: it defined no test function, so pytest merely
*imported* it — and the import ran the handshake for real, rewriting the
git-tracked production artifacts ``plugin/.consult_request.json`` and
``plugin/.consult_response.json`` (their contents matched the literals in the old
lines 10-16 byte for byte).  Any ``pytest tests`` run therefore mutated live
coach files, and the suite's result depended on / perturbed the running system.

Now the exchange is confined to ``tmp_path``:

* ``GLMConsultant(request_path=..., response_path=...)`` — never the module
  defaults (``plugin/.consult_request.json`` / ``.consult_response.json``);
* the "DSH agent" is a real watcher thread on the temporary request file, so the
  file-handshake transport itself is still exercised (not stubbed away);
* the production paths are asserted unchanged locally, and
  ``fly64/conftest.py`` fails the whole session if any protected artifact moves.
"""
from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

import pytest

FLY64_ROOT = Path(__file__).resolve().parent.parent
if str(FLY64_ROOT) not in sys.path:
    sys.path.insert(0, str(FLY64_ROOT))

from plugin.llm_consult import (ConsultError, GLMConsultant,  # noqa: E402
                                REQUEST_PATH, RESPONSE_PATH)

#: The reply the original script's fake DSH agent wrote (kept verbatim: it is the
#: captured shape of a real DSH-coach handshake answer).
DSH_REPLY = {
    "advice": "[DSH 教官] 演示：检测到 micro_loop 零位移，向 opening 扇区方向突围 2.5s",
    "strategy": {"exploration": {"turn_bias": 0.4}},
}

#: How long the fake DSH agent keeps answering.  Comfortably longer than the
#: consultant's own timeout so a slow machine cannot make the test flaky.
RESPONDER_BUDGET_S = 30.0


def _spawn_dsh_responder(request_path: Path, response_path: Path,
                         stop: threading.Event) -> threading.Thread:
    """Watch for the consult request and answer it, like the DSH host agent.

    Re-writes the reply whenever it is missing: the subagent transport *unlinks*
    ``response_path`` before it starts polling, so a one-shot writer can have its
    answer deleted before the consumer looks for it.
    """
    blob = json.dumps(DSH_REPLY, ensure_ascii=False)

    def _worker():
        deadline = time.time() + RESPONDER_BUDGET_S
        while time.time() < deadline and not stop.is_set():
            try:
                if request_path.exists() and not response_path.exists():
                    response_path.write_text(blob, encoding="utf-8")
            except OSError:
                pass  # transient (file being replaced) — retry next tick
            time.sleep(0.02)

    thread = threading.Thread(target=_worker, daemon=True,
                              name="fake-dsh-responder")
    thread.start()
    return thread


def _tmp_consultant(tmp_path: Path, **kw) -> GLMConsultant:
    """A subagent consultant whose request/response files live in tmp_path."""
    kw.setdefault("transport", "subagent")
    kw.setdefault("timeout", 10.0)
    return GLMConsultant(request_path=tmp_path / "consult_request.json",
                         response_path=tmp_path / "consult_response.json", **kw)


def _fingerprint(path: Path):
    try:
        return (True, path.read_bytes())
    except FileNotFoundError:
        return (False, b"")


# ── the handshake ───────────────────────────────────────────────────────

def test_dsh_agent_answers_consult_request(tmp_path):
    """The file handshake completes and the reply is parsed into advice+strategy."""
    consultant = _tmp_consultant(tmp_path)
    stop = threading.Event()
    responder = _spawn_dsh_responder(consultant.request_path,
                                     consultant.response_path, stop)
    try:
        out = consultant.consult({"kind": "test", "stuck_duration": 100.0},
                                 frame_b64=None)
    finally:
        stop.set()
        responder.join(timeout=5.0)

    assert out["advice"] == DSH_REPLY["advice"]
    # the sanitised strategy survives parse_response -> sanitize_strategy
    assert out["strategy"]["exploration"]["turn_bias"] == pytest.approx(0.4)

    # the request really went through the file (not through a stub)
    request = json.loads(consultant.request_path.read_text(encoding="utf-8"))
    assert request["context"]["kind"] == "test"
    assert request["context"]["stuck_duration"] == 100.0
    assert "kind" not in request          # consult(), not consult_dialogue()
    assert "教练" in request["prompt"]     # the coach prompt, not the dialogue one
    assert consultant.response_path.exists()


def test_no_response_raises_consult_error(tmp_path):
    """A silent DSH agent must fail loudly, not return empty advice.

    ``timeout`` is tiny and no responder is started, so the wait loop exits at
    once: this pins the transport's failure mode without spending 120 s.
    """
    consultant = _tmp_consultant(tmp_path, timeout=0.05)
    with pytest.raises(ConsultError):
        consultant.consult({"kind": "test"}, frame_b64=None)


def test_handshake_never_touches_production_paths(tmp_path):
    """Regression pin for the A3 §5.4 incident.

    Asserts on the LIVE paths themselves (``plugin/.consult_request.json`` /
    ``.consult_response.json``) rather than on "my call used tmp_path": the
    incident was precisely an implicit write to those two files.
    """
    before = {p: _fingerprint(p) for p in (REQUEST_PATH, RESPONSE_PATH)}
    consultant = _tmp_consultant(tmp_path)
    stop = threading.Event()
    responder = _spawn_dsh_responder(consultant.request_path,
                                     consultant.response_path, stop)
    try:
        consultant.consult({"kind": "test", "stuck_duration": 1.0},
                           frame_b64=None)
    finally:
        stop.set()
        responder.join(timeout=5.0)

    after = {p: _fingerprint(p) for p in (REQUEST_PATH, RESPONSE_PATH)}
    assert after == before, (
        "the handshake test wrote production artifacts: %s"
        % [str(p) for p in (REQUEST_PATH, RESPONSE_PATH) if after[p] != before[p]])


if __name__ == "__main__":  # still runnable as a script, but only on purpose
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
