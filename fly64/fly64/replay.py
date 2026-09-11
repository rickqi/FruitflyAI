"""Exact, tick-by-tick neural replay without SM64."""
import argparse
import json
from pathlib import Path
import numpy as np
from .model import FlyModel
from .retina import CALIBRATION


def verify(index: Path, cache: Path):
    manifest = json.loads(index.read_text())
    if manifest.get("schema") != 3 or manifest.get("retina") != CALIBRATION:
        raise ValueError("Replay requires schema 3 and the exact spherical retinal calibration")
    model = FlyModel(cache, demo=manifest["fixture"], seed=manifest["seed"])
    for name in ("tonic_current", "synaptic_gain"):
        if name in manifest.get("parameters", {}):
            setattr(model, name, manifest["parameters"][name])
    count = 0
    for name in manifest["chunks"]:
        with np.load(index.parent / name) as archive:
            data = {key: archive[key] for key in archive.files}
        for i, (t, frame_index, expected) in enumerate(zip(data["timestamps"], data["frame_indices"], data["controls"])):
            frame = data["frames"][frame_index]
            control, spikes = model.step(frame, float(t))
            actual = (control.x, control.y, int(control.jump))
            if not np.array_equal(actual, expected):
                raise AssertionError(f"control mismatch at tick {count}: {actual} != {expected}")
            a, b = data["spike_offsets"][i:i+2]
            np.testing.assert_array_equal(spikes, data["spikes"][a:b], err_msg=f"spike mismatch tick {count}")
            count += 1
    return count


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("index", type=Path)
    p.add_argument("--cache", type=Path, default=Path(__file__).resolve().parent.parent / ".cache/malecns")
    args = p.parse_args()
    print(f"PASS exact replay: {verify(args.index, args.cache):,} neural ticks")
