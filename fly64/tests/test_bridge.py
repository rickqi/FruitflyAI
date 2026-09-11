import struct

import numpy as np

from fly64.bridge import A_BUTTON, FRAME_BYTES, HEADER, SharedBridge


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
