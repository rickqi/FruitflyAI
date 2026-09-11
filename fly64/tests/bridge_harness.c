/* Executes the real game's bridge implementation without OpenGL or a ROM. */
#include "../.cache/sm64ex/src/pc/fly64_bridge.c"
#include <assert.h>
int main(int argc, char **argv) {
    if (argc == 2) {
        setenv("FLY64_BRIDGE", argv[1], 1);
        OSContPad live = {0};
        fly64_bridge_read_controller(&live);
        assert(live.stick_x == -35 && live.stick_y == 67 && (live.button & A_BUTTON));
        puts("PASS real Python-to-native clock and controller packet");
        fly64_bridge_shutdown();
        return 0;
    }
    struct Fly64Shared fixture = {0};
    OSContPad pad = {0};
    shared = &fixture;
    fixture.h.enabled = 1;
    fixture.h.control_seq = 2;
    fixture.h.heartbeat_ns = monotonic_ns();
    fixture.h.stick_x = -35; fixture.h.stick_y = 67;
    fixture.h.reserved = 1;
    fly64_bridge_read_controller(&pad);
    assert(pad.stick_x == -35 && pad.stick_y == 67 && (pad.button & A_BUTTON));
    pad = (OSContPad){0}; fly64_bridge_read_controller(&pad);
    assert(pad.button & A_BUTTON);
    pad = (OSContPad){0}; fly64_bridge_read_controller(&pad);
    assert(!(pad.button & A_BUTTON));
    fixture.h.heartbeat_ns = monotonic_ns() - FLY64_STALE_NS - 1;
    pad = (OSContPad){0}; fly64_bridge_read_controller(&pad);
    assert(!pad.stick_x && !pad.stick_y && !pad.button);
    fixture.h.control_seq = 3; fixture.h.heartbeat_ns = monotonic_ns();
    pad = (OSContPad){0}; fly64_bridge_read_controller(&pad);
    assert(!pad.stick_x && !pad.stick_y && !pad.button);
    puts("PASS native bridge: controls, exactly two A frames, stale release, torn packet rejection");
    shared = NULL;
    return 0;
}
