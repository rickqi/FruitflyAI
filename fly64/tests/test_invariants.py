from pathlib import Path
import struct
import subprocess
import numpy as np
from scipy import sparse
from fly64.bridge import SharedBridge, FRAME_BYTES, HEADER_SIZE
from fly64.model import FlyModel
from fly64.main import Replay
from fly64.replay import verify

ROOT = Path(__file__).resolve().parent.parent

def test_torn_frames_return_last_good_frame(tmp_path):
    with SharedBridge(tmp_path / "bridge") as b:
        b.write_frame(bytes([41]) * FRAME_BYTES)
        expected = b.read_frame()
        struct.pack_into("<I", b.mm, 12, 3)
        b.mm[HEADER_SIZE:] = bytes([99]) * FRAME_BYTES
        assert b.read_frame() == expected

def test_signed_event_propagation_matches_dense():
    m = FlyModel(demo=True)
    m.spikes[m.rng.choice(m.n, 200, replace=False)] = 1
    expected = m.w @ m.spikes
    actual = np.asarray(m.w[:, np.flatnonzero(m.spikes)].sum(axis=1)).ravel()
    np.testing.assert_allclose(actual, expected, atol=1e-6)
    assert m.w.data.min() < 0 < m.w.data.max()

def test_no_visual_motor_shortcut():
    a, b = FlyModel(demo=True), FlyModel(demo=True)
    a.w = sparse.csc_matrix((a.n,a.n),dtype=np.float32)
    b.w = a.w.copy()
    for i in range(50):
        ca, _ = a.step(np.zeros((256,384,3),np.uint8))
        cb, _ = b.step(np.full((256,384,3),255,np.uint8))
        assert ca == cb

def test_bilateral_decoder_and_jump():
    m = FlyModel(demo=True)
    m.v[m.turn_right] = 1.5
    m.v[m.jump_nodes] = 1.5
    control, _ = m.step(np.zeros((256,384,3),np.uint8),0)
    assert control.x > 0 and control.jump
    m.v[m.jump_nodes] = 1.5
    assert not m.step(np.zeros((256,384,3),np.uint8),.1)[0].jump

def test_replay_all_ticks(tmp_path):
    m = FlyModel(demo=True, seed=23)
    r = Replay(tmp_path / "test.npz", 23, True)
    for i in range(30):
        frame = np.full((256,384,3),i*7,np.uint8)
        c, s = m.step(frame, i*.02)
        r.add(i*.02, frame, c, s)
    r.close()
    assert verify(tmp_path / "test.index.json", tmp_path) == 30

def test_native_bridge(tmp_path):
    target = tmp_path / "bridge-test"
    subprocess.run(["clang", "-I", str(ROOT / "tests/stubs"), str(ROOT / "tests/bridge_harness.c"), "-o", str(target)], check=True)
    subprocess.run([str(target)], check=True)
    with SharedBridge(tmp_path / "actual-clock.bin") as bridge:
        bridge.write_control(-35, 67, True)
        subprocess.run([str(target), str(bridge.path)], check=True)

def test_full_graph_incoming_normalization():
    w = sparse.load_npz(ROOT / ".cache/malecns/weights.npz")
    assert w.shape == (166700,166700)
    sums = np.asarray(abs(w).sum(axis=1)).ravel()
    np.testing.assert_allclose(sums[sums>0], 1, atol=2e-6)

def test_launcher_lock_blocks_duplicate(tmp_path):
    import os
    import sys
    launcher = tmp_path / "launcher"
    launcher.write_text("#!/bin/sh\nprintf 'ready\\n'\nsleep 2\n")
    launcher.chmod(0o755)
    command = [sys.executable, str(ROOT / "scripts/locked_launcher.py"), str(launcher)]
    first = subprocess.Popen(command, stdout=subprocess.PIPE, text=True)
    try:
        assert first.stdout.readline().strip() == "ready"
        second = subprocess.run(command, capture_output=True, text=True)
        assert second.returncode != 0 and "already running" in second.stderr
    finally:
        first.wait(timeout=5)
