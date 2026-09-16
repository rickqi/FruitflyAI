import struct

import numpy as np
import pytest

from fly64.bridge import (A_BUTTON, B_BUTTON, B_EVENT_OFF, FRAME_BYTES, HEADER,
                          SharedBridge, Z_EVENT_OFF, Z_TRIG)


def test_bridge_round_trip(tmp_path):
    path = tmp_path / "bridge.bin"
    with SharedBridge(path) as bridge:
        pixels = bytes(np.arange(FRAME_BYTES, dtype=np.uint8))
        bridge.write_frame(pixels)
        seq, observed = bridge.read_frame()
        assert seq % 2 == 0
        assert observed == pixels
        bridge.write_control(-40, 65, True)
        values = HEADER.unpack_from(bridge.mm)
        assert values[6:9] == (-40, 65, A_BUTTON)


def test_simulator_does_not_override_game_toggle(tmp_path):
    with SharedBridge(tmp_path / "bridge.bin") as bridge:
        struct.pack_into("<I", bridge.mm, 20, 0)
        bridge.write_control(10, 20, False)
        assert bridge.enabled is False


@pytest.mark.skipif(struct.calcsize("<I") != 4, reason="requires 32-bit uint")
def test_write_control_z_button(tmp_path):
    """v2.14.0 Phase 1: Z trigger reaches the buttons field + event counter."""
    with SharedBridge(tmp_path / "bridge.bin") as bridge:
        bridge.write_control(0, 40, False, z=True)
        buttons = HEADER.unpack_from(bridge.mm)[8]
        assert buttons & Z_TRIG
        assert not buttons & A_BUTTON
        assert not buttons & B_BUTTON
        assert struct.unpack_from("<I", bridge.mm, Z_EVENT_OFF)[0] == 1
        assert struct.unpack_from("<I", bridge.mm, B_EVENT_OFF)[0] == 0
        status = bridge.game_status()
        # game_status reads the *game-applied* buttons (written back by the C
        # side); with no game consumer in the test they stay 0 — keys must
        # exist and default False.
        assert status["z"] is False and status["b"] is False


def test_write_control_b_and_z_combined(tmp_path):
    with SharedBridge(tmp_path / "bridge.bin") as bridge:
        bridge.write_control(0, 0, False, b=True, z=True)
        buttons = HEADER.unpack_from(bridge.mm)[8]
        assert buttons == (B_BUTTON | Z_TRIG)
        assert struct.unpack_from("<I", bridge.mm, Z_EVENT_OFF)[0] == 1
        assert struct.unpack_from("<I", bridge.mm, B_EVENT_OFF)[0] == 1


def test_write_control_level_buttons_do_not_stick(tmp_path):
    """b/z are level-written each tick; a tick without them clears the bits."""
    with SharedBridge(tmp_path / "bridge.bin") as bridge:
        bridge.write_control(0, 0, False, z=True)
        bridge.write_control(0, 0, False)
        assert not HEADER.unpack_from(bridge.mm)[8] & Z_TRIG
        # But the event counter persists — game-side pulse keeps 2 frames.
        assert struct.unpack_from("<I", bridge.mm, Z_EVENT_OFF)[0] == 1


def test_game_status_reads_applied_bz_bits(tmp_path):
    """game_status b/z reflect the game-applied buttons at offset 46."""
    with SharedBridge(tmp_path / "bridge.bin") as bridge:
        # Simulate the C side writing back applied buttons (offset 46).
        struct.pack_into("<H", bridge.mm, 46, B_BUTTON | Z_TRIG)
        status = bridge.game_status()
        assert status["b"] is True and status["z"] is True
        struct.pack_into("<H", bridge.mm, 46, A_BUTTON)
        status = bridge.game_status()
        assert status["jump"] is True and status["b"] is False and status["z"] is False
