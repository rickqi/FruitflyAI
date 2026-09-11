#!/usr/bin/env python3
"""Run the three documented full-model visual-causality checks."""

from pathlib import Path
import numpy as np
import json

from fly64.model import FlyModel


ROOT = Path(__file__).resolve().parent.parent


def run(frames: np.ndarray, connected: bool):
    model = FlyModel(ROOT / ".cache" / "malecns", seed=64)
    model.visual_connected = connected
    controls, temporal, spikes = [], [], []
    for i, frame in enumerate(frames):
        control, fired = model.step(frame, now=i * model.dt)
        controls.append((control.x, control.y, int(control.jump)))
        temporal.append(model.temporal_energy)
        spikes.append(len(fired))
    return np.asarray(controls), np.asarray(temporal), np.asarray(spikes)


def main():
    index = json.loads((ROOT / "artifacts/latest-replay.index.json").read_text())
    if index.get("schema") != 3:
        raise ValueError("Record a new first-person run before testing causality")
    sequences = []
    for name in index["chunks"][:3]:
        with np.load(ROOT / "artifacts" / name) as chunk:
            sequences.append(chunk["frames"][chunk["frame_indices"]])
    source = np.concatenate(sequences)
    source = source[np.flatnonzero(source.mean(axis=(1,2,3)) > 20)[0]:]
    sample = source[:1000]
    frozen = np.repeat(sample[:1], len(sample), axis=0)

    live_control, live_temporal, live_spikes = run(sample, True)
    frozen_control, frozen_temporal, frozen_spikes = run(frozen, True)
    disconnected_live, _, _ = run(sample, False)
    disconnected_frozen, _, _ = run(frozen, False)

    assert live_temporal[1:].mean() > frozen_temporal[1:].mean() + 1e-5
    assert not np.array_equal(live_spikes, frozen_spikes)
    assert not np.array_equal(live_control, frozen_control), "No demonstrated downstream motor effect"
    assert np.array_equal(disconnected_live, disconnected_frozen)
    print("PASS live frames change visual/downstream activity")
    print("PASS frozen frames reduce temporal-contrast activity")
    print("PASS disconnected visual afferents remove frame-dependent motor changes")
    print(f"mean temporal contrast: live={live_temporal[1:].mean():.6f}, frozen={frozen_temporal[1:].mean():.6f}")
    report = dict(neurons=166700, ticks=len(sample),
        mean_contrast_live=float(live_temporal[1:].mean()),
        mean_contrast_frozen=float(frozen_temporal[1:].mean()),
        motor_ticks_different=int(np.any(live_control!=frozen_control,axis=1).sum()),
        disconnected_motor_ticks_different=int(np.any(disconnected_live!=disconnected_frozen,axis=1).sum()))
    (ROOT / "artifacts/causality.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
