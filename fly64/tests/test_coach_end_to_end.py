#!/usr/bin/env python3
"""P0-5 PIN — the coach chain, end to end, as ONE regression (release gate).

WHY THIS FILE EXISTS
--------------------
A2 §4 (root-cause meta-layer) and A3 S1/S5: all six links of the coach chain
were individually "file writable, mechanism present, unit test green", and yet
**nobody asserted chain-wise that advice text → behaviour change → evidence**.
That is why 73 coach-related user messages over 10 days were needed to find
defects that a single end-to-end assertion would have caught in seconds.

This file walks the chain link by link, on the real code, with a throw-away
workspace (nothing here touches ``skills/active_strategy.json``,
``skills/coach_outcomes.jsonl`` or ``runtime/coach_frames`` — see the
``chain`` fixture):

  ① trigger   plugin/runner.check_help_needed  (the P0-4 gate; the form that
                                                used to return None)
  ② consult   a fake consultant (no network: the LLM segment is not the target
                                    here — D7/D8/D9 live in ④⑤⑥)
  ③ frame     plugin/runner.save_consult_frame  → real PNG evidence (P2-2)
  ④ write     plugin/strategy_writer.write_strategy → merge, not overwrite
  ⑤ keys      fly64/main.load_active_strategy + apply_strategy_update
  ⑥ consumer  the brain's real read points must return the coach's value
              instead of their hardcoded fallback
  ⑦ outcome   plugin/coach_outcomes row must carry keys + a non-empty
              scene_label + non-zero deltas

RED → GREEN (the stated acceptance)
-----------------------------------
Run from ``fly64/`` on the pre-P0-4 tree (git commit ``aeac935``, e.g.
``git worktree add --detach .tmp/pristine_head aeac935``) with this file copied
into ``tests/``::

    python -m pytest tests/test_coach_end_to_end.py -q

The core assertion fails there — ``consulted is True`` — because the runner's
trigger cannot see the high-speed weave form (A2 §1.2 D2); the frame-evidence
and reader assertions fail with it.  On the fixed tree the file passes.
"""
from __future__ import annotations

import ast
import base64
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent          # fly64/
sys.path.insert(0, str(ROOT))

from fly64 import main as brain_main                    # noqa: E402
from fly64.memory import MemoryController               # noqa: E402
from plugin import coach_outcomes as co                 # noqa: E402
from plugin.runner import PluginRunner                  # noqa: E402
from plugin.strategy_writer import StrategyWriter       # noqa: E402

MAIN_SRC = ROOT / "fly64" / "main.py"
MEMORY_SRC = ROOT / "fly64" / "memory.py"

#: Scene label in the production form (CJK, as the scene recogniser emits it).
SCENE = "熔岩地#6f2a"
SCENE_HASH = "6f2a11"

#: The memory snapshot the brain publishes (/memory.json) in the reported form:
#: median speed 316 u/s but only 28 u of net displacement over 60 s, loop 0.93,
#: stuck 54.2 s rising, health 0.62 — and the classifier still says ``idle``.
#: ``check_help_needed()`` returned ``None`` for exactly this snapshot.
WEAVE_MEMORY = {
    "stuck_duration": 54.2,
    "anomaly_state": "idle",
    "health_score": 0.62,
    "reflex_active": True,
    "reflex_ineffective": False,
    "disp_60s": 28.0,
    "median_speed": 316.0,
    "loop_score": 0.93,
    "escape_behavior": True,
    "scene_name": SCENE,
    "scene_label": SCENE,
    "scene_id": SCENE_HASH,
    "position": {"x": 120.0, "y": 120.0, "z": -40.0},
    "pos_y": 120.0,
}

#: A genuinely progressing fly at the same speed (316 u/s × 60 s = 18960 u):
#: the negative control — the coach must NOT be woken.
PROGRESS_MEMORY = dict(WEAVE_MEMORY, disp_60s=18960.0, stuck_duration=12.0,
                       health_score=0.9)

#: What the coach answers with.  ``turn_bias`` stays inside the brain's
#: [0, 0.25] clamp (main.py:1320) so the value the reader sees is the value
#: written; ``commit_ticks`` is read from the ``escape`` section, ``turn_bias``
#: from ``exploration`` — i.e. the assertion is cross-section aware on purpose
#: (a wrong-section read returns the reader's default, see
#: ``test_coach_values_reach_the_consumers_not_the_fallbacks``).
COACH_STRATEGY = {
    "exploration": {"turn_bias": 0.18, "bold_explore_stuck_s": 20.0},
    "escape": {"commit_ticks": 125},
    "fallen_recovery": {"mode": "directional_climb"},
}

#: EVO-owned state that must survive a coach write (EVO-072 / A2 D7).
EVO_SEED = {
    "__generation": 152,
    "exploration": {"turn_bias": 0.25, "evolved_only_key": 0.77},
    "escape": {"commit_ticks": 50, "forward_accum_max": 0.2066},
}


# ── helpers ───────────────────────────────────────────────────────────────
def _raw_rgb_b64(width: int = 320, height: int = 240) -> str:
    """A real 320×240×3 raw-RGB frame (the /screen.json payload form)."""
    pixels = bytes([0, 0, 0, 120, 80, 40]) * (width * height // 2)
    return base64.b64encode(pixels).decode("ascii")


class _FakeConsultant:
    """Stands in for the GLM client: ② must not need the network."""

    def __init__(self, strategy: dict):
        self.model = "glm-e2e-stub"
        self.strategy = strategy
        self.calls: list = []

    def consult(self, context: dict, frame_b64):
        self.calls.append(context)
        return {"advice": "wire the weave: shorten the breakout commit",
                "strategy": json.loads(json.dumps(self.strategy))}


def _fetcher(screen_b64: str):
    endpoints = {
        "/memory.json": dict(WEAVE_MEMORY),
        "/flow.json": {"scene_hash": SCENE_HASH, "scene_name": SCENE},
        "/evolution.json": {},
        "/help.json": {},
        "/screen.json": {"screen_b64": screen_b64},
    }
    return lambda endpoint: endpoints.get(endpoint, {})


def _readpoints(src_path: Path, attr: str) -> set:
    """``getattr(<obj>, "<attr>", <default>)`` read points in a source file.

    Derived from the real sources (AST) rather than hardcoded, so the
    consumer assertion in this file cannot silently drift away from the code
    it claims to pin (the failure mode of A2 D7/D8/D9: "the mechanism exists,
    the report says success, nothing reaches behaviour").
    """
    tree = ast.parse(src_path.read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name) and node.func.id == "getattr"
                and len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
                and node.args[1].value == attr):
            default = node.args[2] if len(node.args) > 2 else None
            found.add(default.value if isinstance(default, ast.Constant) else None)
    return found


def _reader_defaults(key: str, src_path: Path = MAIN_SRC) -> set:
    """Hardcoded defaults for ``<something>.get("<key>", <default>)`` in main.py."""
    tree = ast.parse(src_path.read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute) and node.func.attr == "get"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value == key
                and len(node.args) > 1 and isinstance(node.args[1], ast.Constant)):
            found.add(node.args[1].value)
    return found


@pytest.fixture
def chain(tmp_path, monkeypatch):
    """A real runner + real writer wired to a throw-away workspace.

    Isolation matters here for the same reason ``tests/conftest.py`` exists:
    a test run once clobbered the live ``coach_outcomes.jsonl``.  So this
    fixture redirects every path the chain writes to:

      * ``active_strategy.json`` / ``coach_advice.json`` → ``tmp_path``
      * consult frames → ``tmp_path/coach_frames`` via the class attribute the
        runner reads (``PluginRunner.FRAME_DIR``), so the P2-2 evidence path is
        exercised for real without writing ``runtime/coach_frames``
      * ``coach_outcomes.jsonl`` / ``.pending_outcome.json`` / ``curriculum``
        → the session evidence dir set by ``tests/conftest.py``
        (``FLY64_EVIDENCE_DIR``); asserted, not assumed, by
        ``test_outcome_row_carries_keys_scene_label_and_nonzero_deltas``
    """
    co.clear_pending()                      # no stale window from another test
    frame_dir = tmp_path / "coach_frames"
    monkeypatch.setattr(PluginRunner, "FRAME_DIR", frame_dir)

    strategy_path = tmp_path / "active_strategy.json"
    advice_path = tmp_path / "coach_advice.json"
    strategy_path.write_text(json.dumps(EVO_SEED), encoding="utf-8")

    writer = StrategyWriter(strategy_path=strategy_path, advice_path=advice_path)
    consultant = _FakeConsultant(COACH_STRATEGY)
    runner = PluginRunner(fetcher=_fetcher(_raw_rgb_b64()), consultant=consultant,
                          writer=writer)
    runner._prim_zero_run = 0
    return SimpleNamespace(runner=runner, consultant=consultant, writer=writer,
                           strategy_path=strategy_path, advice_path=advice_path,
                           frame_dir=frame_dir)


def _written(chain) -> dict:
    return json.loads(chain.strategy_path.read_text(encoding="utf-8"))


# ── ①→④ the coach must be woken, and the cycle must write ─────────────────
def test_weave_form_wakes_the_coach_and_writes_a_strategy(chain):
    """THE core assertion (A2 D2): this form used to return no help at all."""
    result = chain.runner.run_cycle()

    assert result.get("consulted") is True, (
        "coach not woken for the high-speed weave form: %r" % (result,))
    assert result.get("strategy_written") is True, result
    assert result.get("context", {}).get("help_reason") == "weave_no_progress", (
        result.get("context"))
    assert chain.consultant.calls, "consultant was never called"
    # ④ the strategy really is on disk for the brain to hot-reload
    written = _written(chain)
    assert written["exploration"]["turn_bias"] == pytest.approx(0.18)
    assert written["escape"]["commit_ticks"] == 125
    # …and the advice side-channel exists too (dashboard /coach_advice.json)
    advice = json.loads(chain.advice_path.read_text(encoding="utf-8"))
    assert advice["advice"] and advice["strategy"]["escape"]["commit_ticks"] == 125


def test_progressing_fly_is_not_escalated(chain):
    """Negative control: the P0-4 gate must not turn the coach into a spammer."""
    plain = _fetcher(_raw_rgb_b64())

    def _with_progress(endpoint):
        if endpoint == "/memory.json":
            return dict(PROGRESS_MEMORY)
        return plain(endpoint)

    chain.runner._fetcher = _with_progress
    result = chain.runner.run_cycle()
    assert result.get("consulted") is False, result
    assert result.get("detail") == "no help needed", result


# ── ④→⑤ the written values must reach the brain's reader ──────────────────
def test_written_values_reach_the_brain_reader(chain):
    """Write-then-read-back through the real reader, both sections checked."""
    chain.runner.run_cycle()
    loaded = brain_main.load_active_strategy(chain.strategy_path)

    assert loaded["exploration"]["turn_bias"] == pytest.approx(0.18)
    assert loaded["escape"]["commit_ticks"] == 125
    # cross-section awareness (plan P0-5 §2): a fix that passes only one
    # section through would still lose the other one's advice.
    assert "exploration" in loaded and "escape" in loaded


# ── ④ the coach write must merge, not erase EVO state (EVO-072 / D7) ──────
def test_coach_write_preserves_evo_state(chain):
    chain.runner.run_cycle()
    written = _written(chain)
    assert written["__generation"] == 152, "coach write reset the Phase 6 search"
    assert written["exploration"]["evolved_only_key"] == 0.77, (
        "an EVO parameter the coach did not mention was erased")
    assert written["escape"]["forward_accum_max"] == pytest.approx(0.2066)
    assert written["exploration"]["turn_bias"] == pytest.approx(0.18), (
        "the coach key must win over the pre-existing value")


# ── ⑤ the operator/EVO dotted id must not become a literal top-level key ──
def test_dotted_panel_id_lands_in_the_section(chain):
    """A2 D9 form (EVO-062): the slider reported success, behaviour never moved."""
    chain.runner.run_cycle()
    cur = _written(chain)
    applied, rejected = brain_main.apply_strategy_update(
        cur, {"escape.commit_ticks": 137})

    assert rejected == [], "the dotted id was rejected instead of resolved"
    assert applied == {"escape.commit_ticks": "escape.commit_ticks"}, applied
    assert cur["escape"]["commit_ticks"] == 137
    assert "escape.commit_ticks" not in cur, (
        "the id was written as a literal top-level key (D9)")
    chain.strategy_path.write_text(json.dumps(cur), encoding="utf-8")
    assert brain_main.load_active_strategy(
        chain.strategy_path)["escape"]["commit_ticks"] == 137


# ── ⑤→⑥ the values must reach the consumers, not their fallbacks ──────────
def test_coach_values_reach_the_consumers_not_the_fallbacks(chain):
    """The behavioural end of the chain, without an SM64 environment.

    The brain's hot-reload lives inside ``main.run()`` (not callable headless),
    so the injected form is used — allowed by the plan, but it must still be
    anchored in the real consumer code:

      * the consumer objects are real (``MemoryController``);
      * the attribute names AND their fallback sentinels come from the sources
        (``memory.py`` line ~2094 for ``bold_explore_stuck_s``, ``main.py``
        line ~1687 for ``bold_turn_bias``) via AST, not from this test;
      * a wired consumer returns the coach's value, and the value differs from
        every sentinel a silent fallback would produce.
    """
    chain.runner.run_cycle()
    loaded = brain_main.load_active_strategy(chain.strategy_path)

    # what main.py:1319-1326 assigns at hot-reload, fed by the *file*
    mem = MemoryController()
    mem.bold_explore_stuck_s = float(loaded["exploration"]["bold_explore_stuck_s"])
    mem.bold_turn_bias = float(loaded["exploration"]["turn_bias"])

    # the real read points (the expressions the brain evaluates later)
    stuck_sentinels = _readpoints(MEMORY_SRC, "bold_explore_stuck_s")
    bias_sentinels = _readpoints(MAIN_SRC, "bold_turn_bias")
    assert 60.0 in stuck_sentinels, "memory.py no longer reads bold_explore_stuck_s"
    assert 69.0 in bias_sentinels, "main.py no longer reads bold_turn_bias"
    # the consumer read returns the coach's value …
    assert getattr(mem, "bold_explore_stuck_s", 60.0) == pytest.approx(20.0)
    assert getattr(mem, "bold_turn_bias", 69.0) == pytest.approx(0.18)
    # … and an unwired consumer would return a sentinel, so a silent fallback
    # (the "file changed, behaviour did not" failure) is detectable
    fresh = MemoryController()
    assert getattr(fresh, "bold_explore_stuck_s", 60.0) == 60.0
    assert getattr(fresh, "bold_turn_bias", 69.0) == 69.0
    # the reader-side defaults for these keys must not be what we read back
    assert 20.0 not in _reader_defaults("bold_explore_stuck_s")
    assert 0.18 not in _reader_defaults("turn_bias")


# ── ③ the consult frame must leave audit evidence (P2-2) ──────────────────
def test_consult_frame_evidence_is_written(chain):
    """``runtime/coach_frames`` must gain one PNG per consult (A2 ③).

    The runner's own ``save_consult_frame`` path runs unchanged; only the
    target directory is redirected (the fixture patches ``FRAME_DIR``), so this
    is evidence-path behaviour, not a stub.
    """
    result = chain.runner.run_cycle()
    assert result.get("consulted") is True, result
    frames = sorted(chain.frame_dir.glob("coach_*.png"))
    assert frames, "no consult frame persisted — 'what did the coach look at' " \
                   "is unanswerable (A2 ③)"
    assert frames[-1].read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert "weave_no_progress" in frames[-1].name, frames[-1].name


# ── ⑦ the outcome row must be usable for attribution (A2 D12) ────────────
def test_outcome_row_carries_keys_scene_label_and_nonzero_deltas(chain):
    """A2 D12: 30/30 live rows had an empty ``scene_label`` and an empty ``keys``
    — "which advice, and what did it change" had no answer.  The row is only
    as good as the memory snapshot, so this pins the propagation: a snapshot
    that carries a scene label and real memory keys must produce a row that
    carries them, with non-zero deltas after the window."""
    # evidence must never be the live corpus
    evidence_dir = os.environ.get("FLY64_EVIDENCE_DIR", "")
    assert evidence_dir, "tests/conftest.py must set FLY64_EVIDENCE_DIR"
    assert str(co.OUTCOMES_PATH).startswith(evidence_dir), (
        "coach_outcomes would write outside the test evidence dir: %s"
        % co.OUTCOMES_PATH)
    co.clear_pending()
    before = len(co.load_outcomes())

    pending = co.snapshot_outcome(COACH_STRATEGY, WEAVE_MEMORY,
                                  {"scene_hash": SCENE_HASH}, cycle=1,
                                  window_s=0.0, help_reason="weave_no_progress")
    co.save_pending(pending)
    # 30 s later the weave broke: displacement up, stuck down, health up
    later = dict(WEAVE_MEMORY, disp_60s=180.0, stuck_duration=20.0,
                 health_score=0.71)
    outcome = co.resolve_outcome(co.load_pending(), later)
    assert outcome is not None, "no outcome emitted for a resolved window"
    co.append_outcome(outcome)

    rows = co.load_outcomes()
    assert len(rows) == before + 1, "exactly one row must be appended"
    row = rows[-1]
    assert row["scene_label"] == SCENE, (
        "scene_label must survive snapshot → resolve → append (A2 D12)")
    assert row["keys"], "keys empty — 'which advice' has no answer"
    assert row["keys"]["escape"]["commit_ticks"] == 125
    assert row["deltas"]["disp_60s"] == pytest.approx(152.0), row["deltas"]
    assert any(v != 0 for v in row["deltas"].values()), (
        "all deltas zero — 'what changed' has no answer")
    assert row["verdict"] == "improved", row
    assert row["help_reason"] == "weave_no_progress"
    # the row must be usable by the next stage of the loop (curriculum)
    curriculum = co.update_curriculum(co.load_curriculum(), row, later)
    assert curriculum and curriculum["attempts"] >= 1, curriculum
