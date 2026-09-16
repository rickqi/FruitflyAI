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


# ---------------------------------------------------------------------------
# Open-loop counterfactual (evolution-coach-roadmap P0-1)
#
# Re-simulate a recorded chunk with parameter overrides and MEASURE the neural
# response instead of asserting exact reproduction.  This answers "would the
# brain have behaved differently under this fix, on the same visual input?"
# Honest boundary: open-loop — the game world does not react to the altered
# controls, so this verifies the neural response change, not closed-loop escape.
# ---------------------------------------------------------------------------

def counterfactual(chunk: Path, cache: Path, overrides: dict | None = None,
                   max_ticks: int | None = None):
    """Re-simulate one recorded chunk under parameter overrides.

    chunk     : a self-contained replay chunk npz (schema 3, carries seed)
    overrides : {FlyModel attribute: value} applied after the manifest
                parameters (e.g. {"breakout_gain": 0.25} or class-level
                constants such as {"DAN_REWARD_EXPLORATION": 0.5})
    max_ticks : optional cap (a 500-tick chunk costs ~8-15ms * 500)

    Returns {"baseline": {...}, "override": {...}, "overrides": {...}} where
    each pass reports: ticks, jump_count, mean_y, mean_abs_x, y_positive_frac,
    mean_abs_mbon, dopamine_mean.
    """
    with np.load(chunk) as archive:
        data = {key: archive[key] for key in archive.files}
    if int(data.get("schema", 0)) != 3:
        raise ValueError("counterfactual requires a schema-3 replay chunk")
    seed = int(data["seed"])
    fixture = bool(data["fixture"])
    times = data["timestamps"]
    frames = data["frames"]
    frame_indices = data["frame_indices"]
    n = len(times)
    if max_ticks:
        n = min(n, max_ticks)

    def _pass(parameter_overrides: dict | None) -> dict:
        model = FlyModel(Path(cache), demo=fixture, seed=seed)
        if fixture:
            model.load_fixture_connectome()
        for name, value in (parameter_overrides or {}).items():
            setattr(model, name, value)
        jumps = 0
        ys, xs, mbons, das = [], [], [], []
        for i in range(n):
            frame = frames[frame_indices[i]]
            control, _spikes = model.step(frame, float(times[i]))
            ys.append(control.y)
            xs.append(control.x)
            jumps += int(control.jump)
            mushroom = getattr(model, "mushroom", None)
            if mushroom is not None and getattr(mushroom, "mbon_outputs", None) is not None:
                mbons.append(float(np.mean(np.abs(mushroom.mbon_outputs))))
                das.append(float(getattr(mushroom, "dopamine", 0.0)))
        import numpy as _np
        out = {
            "ticks": n,
            "jump_count": jumps,
            "mean_y": round(float(_np.mean(ys)), 3) if ys else 0.0,
            "mean_abs_x": round(float(_np.mean(np.abs(xs))), 3) if xs else 0.0,
            "y_positive_frac": round(sum(1 for v in ys if v > 0) / max(len(ys), 1), 3),
        }
        if mbons:
            out["mean_abs_mbon"] = round(float(_np.mean(mbons)), 4)
        if das:
            out["dopamine_mean"] = round(float(_np.mean(das)), 4)
        return out

    manifest_params = {}
    result = {"baseline": _pass(manifest_params)}
    if overrides:
        result["override"] = _pass(overrides)
        result["overrides"] = dict(overrides)
    return result
