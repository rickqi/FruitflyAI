import numpy as np

from fly64.model import FlyModel, SceneMemory


def frame(left=0, right=0):
    value = np.zeros((256, 384, 3), np.uint8)
    value[:, :192] = left
    value[:, 192:] = right
    return value


def test_retina_responds_to_luminance_and_change():
    model = FlyModel(demo=True)
    dark = model.encode_retina(frame(0, 0))
    bright_change = model.encode_retina(frame(255, 255))
    assert dark.mean() == 0
    assert bright_change.mean() > 0.9


def test_deterministic_spikes():
    a, b = FlyModel(demo=True, seed=10), FlyModel(demo=True, seed=10)
    image = frame(30, 220)
    for i in range(30):
        ca, sa = a.step(image, now=i * a.dt)
        cb, sb = b.step(image, now=i * b.dt)
        np.testing.assert_array_equal(sa, sb)
        assert ca == cb


def test_controls_are_bounded_and_jump_debounced():
    model = FlyModel(demo=True)
    model.activity[model.forward] = 1
    model.activity[model.turn_right] = 1
    model.activity[model.jump_nodes] = 1
    control, _ = model.step(frame(255, 255), now=1.0)
    assert -70 <= control.x <= 70
    assert 0 <= control.y <= 70
    if control.jump:
        second, _ = model.step(frame(255, 255), now=1.1)
        assert not second.jump


def test_model_cliff_properties():
    """Model exposes cliff_history, cliff_confirmed, cliff_rate properties."""
    model = FlyModel(demo=True)
    # Initial state
    assert model.cliff_history == []
    assert not model.cliff_confirmed
    assert model.cliff_rate == 0.0

    # After stepping with green terrain, flow_cliff is set
    green = np.full((256, 384, 3), (60, 180, 60), dtype=np.uint8)
    for i in range(5):
        model.step(green, now=i * model.dt)
    assert len(model.cliff_history) == 5
    assert isinstance(model.cliff_confirmed, bool)
    assert isinstance(model.cliff_rate, float)
    # After enough steps the queue fills to maxlen
    for i in range(10):
        model.step(green, now=(5 + i) * model.dt)
    assert len(model.cliff_history) == 10

    # cliff_rate is non-negative when green stays steady
    assert model.cliff_rate >= -0.001  # effectively zero (steady state)
    assert isinstance(model.flow_cliff, float)  # backward compatible


# ======================================================================
# SceneMemory — visual short-term memory & scene change detection
# ======================================================================


def test_scene_memory_initial():
    """Fresh SceneMemory has empty buffer, zero statistics, no scene change."""
    sm = SceneMemory(buffer_size=30)
    assert sm.scene_mean == 0.0
    assert sm.scene_var == 0.0
    assert sm.scene_change is False
    assert sm.scene_change_rate == 0.0
    assert sm.buffer_as_array is None


def test_scene_memory_buffer_fill():
    """Buffer fills incrementally; statistics available after 2+ frames."""
    sm = SceneMemory(buffer_size=30)
    assert len(sm.scene_buffer) == 0

    # First frame: mean = first value, var = 0, no scene_change
    result = sm.update(0.5)
    assert result["scene_mean"] == 0.5
    assert result["scene_var"] == 0.0
    assert result["scene_change"] is False
    assert result["buffer_fill"] == 1

    # Second frame: mean and var computed with 2 values
    result = sm.update(0.5)
    assert result["scene_mean"] == 0.5
    assert result["scene_var"] == 0.0
    assert result["buffer_fill"] == 2

    # After 30 frames, buffer is full
    for _ in range(28):
        sm.update(0.5)
    assert len(sm.scene_buffer) == 30
    assert sm.buffer_as_array is not None
    assert len(sm.buffer_as_array) == 30


def test_scene_memory_constant_input():
    """All-identical values produce zero variance, no scene change."""
    sm = SceneMemory(buffer_size=10)
    for _ in range(15):
        result = sm.update(0.5)
    assert sm.scene_mean == 0.5
    assert sm.scene_var == 0.0
    assert sm.scene_change is False


def test_scene_memory_var_grows_with_spread():
    """Larger spread in buffer values produces larger variance."""
    sm = SceneMemory(buffer_size=5)
    # Tight cluster: [0.49, 0.50, 0.51, 0.50, 0.49]
    for v in [0.49, 0.50, 0.51, 0.50, 0.49]:
        sm.update(v)
    var_tight = sm.scene_var

    sm.reset()
    # Wide spread: [0.1, 0.3, 0.5, 0.7, 0.9]
    for v in [0.1, 0.3, 0.5, 0.7, 0.9]:
        sm.update(v)
    var_wide = sm.scene_var

    assert var_wide > var_tight


def test_scene_change_triggered_by_3sigma():
    """scene_change flags when current value deviates > 3σ from buffer mean.

    Fill the buffer completely with a constant value so σ ≈ 0, then feed a
    different value.  Any deviation > 3×0 = 0 triggers the flag.
    """
    sm = SceneMemory(buffer_size=30, sigma_threshold=3.0)
    for _ in range(30):
        sm.update(0.50)
    # σ ≈ 0, no deviation
    assert not sm.scene_change

    # Tiny deviation from σ=0 → triggers
    result = sm.update(0.55)
    assert result["scene_change"] is True


def test_scene_change_near_boundary():
    """Values well within the 3σ band do NOT trigger scene_change.

    With 30 alternating entries (mean=0.50, σ≈0.02), the 3σ band spans
    [≈0.44, 0.56].  A value inside stays quiet; a value far outside triggers.
    """
    sm = SceneMemory(buffer_size=30, sigma_threshold=3.0)
    for v in [0.48, 0.52] * 15:
        sm.update(v)                     # mean=0.50, σ≈0.02
    assert not sm.scene_change           # 0.52 is well inside [0.44, 0.56]

    result = sm.update(0.80)             # far outside → triggers
    assert result["scene_change"] is True


def test_scene_change_rate():
    """scene_change_rate tracks fraction of recent frames flagged as changes.

    With buffer_size=30 and σ ≈ 0, each outlier frame reliably triggers
    scene_change.  The rolling rate grows with outliers then decays when
    consistent frames follow.
    """
    sm = SceneMemory(buffer_size=30, sigma_threshold=3.0)
    for _ in range(30):
        sm.update(0.50)
    assert sm.scene_change_rate == 0.0    # 0 changes

    # 3 outlier frames with σ=0 → each triggers scene_change
    for _ in range(3):
        sm.update(1.00)
    assert sm.scene_change_rate > 0.0

    # 20 more consistent frames push the True entries out of
    # the maxlen=10 rolling window, diluting the rate below 0.3
    for _ in range(20):
        sm.update(0.50)
    assert sm.scene_change_rate < 0.3


def test_scene_memory_reset():
    """reset() clears all state."""
    sm = SceneMemory(buffer_size=10)
    for v in [0.5, 0.6, 0.4, 0.7, 0.3, 0.5, 0.5, 0.5, 0.5, 0.5]:
        sm.update(v)
    assert len(sm.scene_buffer) == 10
    assert sm.scene_var > 0
    sm.reset()
    assert sm.scene_mean == 0.0
    assert sm.scene_var == 0.0
    assert sm.scene_change is False
    assert sm.scene_change_rate == 0.0
    assert len(sm.scene_buffer) == 0
    assert sm.buffer_as_array is None


def test_scene_memory_buffer_as_array_shape():
    """buffer_as_array returns (N,) array when buffer has entries."""
    sm = SceneMemory(buffer_size=15)
    assert sm.buffer_as_array is None
    for i in range(15):
        sm.update(i / 15.0)
    arr = sm.buffer_as_array
    assert arr is not None
    assert arr.shape == (15,)


def test_scene_memory_change_history():
    """_change_history tracks recent scene_change flags."""
    sm = SceneMemory(buffer_size=5, sigma_threshold=3.0)
    for _ in range(5):
        sm.update(0.50)
    # After 5 updates, _change_history has 5 entries (one per update)
    assert len(sm._change_history) == 5
    # All False since no changes
    assert sm.scene_change_rate == 0.0


def test_flymodel_scene_properties():
    """FlyModel exposes scene_mean, scene_var, scene_change, scene_change_rate."""
    model = FlyModel(demo=True)
    # Before any step
    assert model.scene_mean == 0.0
    assert model.scene_var == 0.0
    assert model.scene_change is False
    assert model.scene_change_rate == 0.0

    # After first step, buffer gets 1 entry
    model.step(frame(128, 128), now=0.0)
    # With only 1 frame, scene_mean == drive mean, var = 0
    assert model.scene_mean > 0  # retina responds
    assert model.scene_var == 0.0
    assert isinstance(model.scene_change, bool)

    # After more steps, statistics stabilise
    for i in range(35):
        model.step(frame(128, 128), now=(i + 1) * model.dt)
    assert model.scene_mean > 0
    assert model.scene_var >= 0.0
    assert isinstance(model.scene_change, bool)
    assert 0.0 <= model.scene_change_rate <= 1.0


def test_flymodel_reset_scene():
    """reset_scene() clears all scene memory state."""
    model = FlyModel(demo=True)
    for i in range(35):
        model.step(frame(128, 128), now=i * model.dt)
    assert len(model.scene_memory.scene_buffer) > 0
    model.reset_scene()
    assert len(model.scene_memory.scene_buffer) == 0
    assert model.scene_mean == 0.0
    assert model.scene_var == 0.0
    assert model.scene_change is False
    assert model.scene_change_rate == 0.0
