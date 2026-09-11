# Technical notes

For the short run/build instructions, see [the README](../README.md).

Measured connectome wiring does **not** establish recovered fly physiology,
behavior, experience, or consciousness. Dynamics, visual projection and Mario
motor mappings are engineered approximations. No trained policy, scripted
gameplay, or direct image-to-motor shortcut is used.

## Developer commands

Run these from your project folder after the first successful build.
Replace the ROM path with your own file:

```sh
./run-fly64 --synthetic             # explicitly labeled 4,096-cell test fixture
./run-fly64 --rom "/path/to/baserom.us.z64" --duration 90
.venv/bin/pytest -q
PYTHONPATH=. .venv/bin/python scripts/validate_causality.py
.venv/bin/python -m fly64.replay artifacts/latest-replay.index.json
```

Stop the existing demo before launching another. The synthetic fixture does not
use the full MaleCNS graph or SM64.

Tested with project-local Python 3.14; the launcher also supports selecting
Python 3.12. Tested package versions are in `requirements-lock.txt`.

## Data and limitations

- Official [MaleCNS v1.0](https://male-cns.janelia.org/download/) minimum-confidence
  0.5 tables. Exactly **166,700** cells with non-empty superclass annotations,
  including the 94 `tbc` annotations. Status-only filtering would incorrectly
  remove many photoreceptors; no such filter is used.
- **25,582,938** directed weighted connections with both endpoints in the retained
  cells. No connection-strength threshold or speed-driven pruning. The source's
  151,856,684 rows also include unannotated segments/fragments.
- Weight = original synapse count × presynaptic sign / incoming absolute-weight
  sum. GABA, glutamate and histamine are modeled as inhibitory; other or unknown
  transmitters as excitatory. Receptor-dependent and neuromodulatory effects are
  omitted; these signs are approximations, not universal biological rules.
- The cache manifest includes source URLs, SHA-256 hashes, exact counts and
  preprocessing rules. Float32 CSR is cached; runtime CSC spike-event propagation
  visits every outgoing edge of every spiking neuron. Zero-spike columns
  contribute exactly zero: sparse evaluation is not graph pruning.
- 6,006 R1–R8 photoreceptors sample a six-face first-person cubemap. The authors'
  [optic-column assignments](https://github.com/flyconnectome/2025malecns) map
  2,628 cells directly. Another 3,242 have connectivity-derived column estimates.
  **136 still use a deterministic within-eye proxy.** The cached 64×48 column
  coordinates now index angular directions, not the human framebuffer.
  Their angular registration is an approximation, not measured MaleCNS optics.
- **140,638 measured soma/to-soma positions** are available to the stationary
  dashboard map. **26,062** cells with missing locations are excluded from the
  map, not the simulation. Rate summaries use actual input/decoder populations,
  not invented anatomical regions. The cache's proxy coordinates are not drawn.
- The model can collide, get stuck, or die. No star-completion or natural
  fly-behavior claim is made.

## Dynamics and controller

Every 20 ms:
`v ← exp(-dt/0.1)·v + 1.5·W·spikes + 0.180 + noise + retina`.

Noise is seeded Bernoulli background activity (1.2 Hz, amplitude 0.22); default
seed 64. Voltage threshold 1 resets to 0. Retinal current is injected **only**
into photoreceptors. Global tonic current and synaptic gain were calibrated to
make visual perturbations observable downstream; they are not measured
physiological parameters. Luminance, green opponency and absolute temporal
contrast form the retinal drive.

A 13-tick (~260 ms) descending-neuron spike window controls Mario:

- DNg100 forward activity; right-minus-left DNa02/DNg13 steering.
- DNp01/DNp10 burst threshold >0.04 spikes/cell/tick, 800 ms simulation-time
  cooldown. The native game holds A for exactly two game frames per event.
- EMA 0.78/0.22, 8-unit dead zone, stick bounds ±70/127.

Neural updates target 50 Hz, framebuffer capture 10 Hz. Dashboard publishing
drops from 10 to 5 Hz below 0.95 real-time factor. Neural updates and graph edges
are never discarded to catch up. Real-time factor is simulated / elapsed time.

The dashboard shows retinal input and inter-frame brightness change, named
motor-pool rates and thresholds, requested versus observed game controls, and
a stationary firing-rate map. See [signal definitions and display research](dashboard-design.md).
A neural request alone does not prove the game accepted it.

## Bridge and replay

`runtime/fly64_bridge.bin`: v2, 128-byte little-endian header then 294,912 RGB bytes.
The 384×256 top-down atlas has front/right/back on row one and left/up/down on row two.
Magic/version: offsets 0/8; frame/control seqlocks: 12/16; game-owned enable: 20;
heartbeat: 24; signed stick x/y: 32/33; buttons: 34; jump event: 36. Game
acknowledgements occupy 40–63. Both processes use POSIX `CLOCK_MONOTONIC`.
Eye x/y/z and yaw radians are float32 at 64–79, game frame uint32 at 80,
and six-view capture milliseconds float32 at 84. These share the RGB seqlock.
Python's macOS `monotonic_ns()` uses a different clock and must not be substituted.
Readers reject odd/changed sequences. Reads are bounded; neural controls release
after 250 ms stale heartbeat.

Replay schema 3 is a JSON index plus compressed NPZ chunks. **Every neural tick**
records timestamp, exact cubemap frame index, camera pose/game frame, spikes and
requested controls; the index includes seed, dynamics parameters and the retinal
calibration. Identical consecutive images are stored once per chunk, losslessly.
Background compression bounds memory. Old v1 bridge/schema-2 replay data is
rejected: record a new run. Dashboard magic F643 sends 256×128 paired-eye and
change previews, rolling firing rates, and every intervening tick's telemetry.
Replay verification recomputes every spike and controller output without SM64,
on the same code/runtime. Floating-point ordering may differ across architectures.

## Separate first-person vision

The native GL renderer uses a private 128×128 color/depth framebuffer and six
90-degree views. No extra game ticks, window swaps, HUD, or menus run. Perspective,
camera, and animation updates are suppressed during the observational traversal;
object state is restored afterward. Each face uses its own projection, culling and
billboards. The original human framebuffer is never used as neural input.

The supported scene is Bob-omb Battlefield. Generated effects/cannon overlays
are excluded from the sensory pass (BOB has ENVFX_MODE_NONE). Other levels'
generated effects are not supported. The stock tiled sky background is drawn
from the sensory direction; it is not a physically calibrated spherical sky.

The eye origin is Mario position +120 world units vertically, with Mario's body
yaw and a level horizon. Both eyes share that origin (zero stereo baseline).
Mario's own mesh is hidden only in the eye passes. Neural stick x/y is interpreted
relative to body yaw at the game input stage; human stick vectors take precedence
and keep stock camera-relative behavior. Physics and action selection are unchanged.

Angular bounds: left −135°…+8.5°, right −8.5°…+135°, elevation ±72°.
The h1/h2-derived cached column order is stretched over these bounds. This is an
explicit approximate registration; no measured optical-axis correspondence is claimed.
Each receptor averages seven spherical samples: central weight 0.25, six ring
weights 0.125 at radius √2×2°. Face choice is per ray, so cones cross cube seams.
Indices are precomputed arrays; sampling does not touch or prune the graph.
Preview discs use equidistant fisheye projection, masked to the eye field.

The [research references below](#research-references) explain the optical design
basis. Our angular registration, acceptance width, temporal rate and RGB channels
remain engineered approximations.

Set `FLY64_VERIFY_VISION=/absolute/path/to/report.json` when launching to run a
same-tick native audit: perturb observer camera state, require bit-identical
retinal pixels, and require the human framebuffer and Mario/tick to stay unchanged.
The game exits with an error if this check fails.
This does not promise bit-identical replay of the game engine.

## Validation

Tests cover normalization, signed propagation, dense/event equivalence, retinal
response, all-tick deterministic replay, steering signs, jump debounce, torn
packets, native two-frame A, stale release and a **real Python-to-C clock test**.
First-person tests cover cube axes, face seams, eye fields, fisheye masking,
pose/pixel seqlock consistency, old-protocol rejection and lossless replay
deduplication. The native isolation audit also tests body-relative steering.
Causality compares live/frozen/disconnected frames with the same seed and requires
different motor outputs for the connected trials.

Local results are written to `artifacts/causality.json`,
`artifacts/soak-report.json`, replay chunks, logs and recordings when those
runs complete. The soak checks execution stability, not biological validity.

## Research references

### Used as data or source code

- [MaleCNS v1.0 download and attribution](https://male-cns.janelia.org/download/):
  neuron annotations and weighted connections used by the neural model.
- [MaleCNS supplemental optic-column assignments](https://github.com/flyconnectome/2025malecns/blob/67767d2233657983993ff6c2be48e836a935863c/supplemental_data/optic-column-type-assignments-v1.0.xlsx):
  pinned column labels used to order photoreceptors. They do not provide the
  calibrated optical directions assigned in this demo.
- [sm64ex source at the pinned commit](https://github.com/sm64pc/sm64ex/tree/d7ca2c04364a6dd0dac58b47151e04e26887e6f0):
  native renderer, game simulation and controller implementation patched here.

### Informed the optical design

- Wang-Chen et al. (2024), [*NeuroMechFly v2: simulating embodied sensorimotor
  control in adult Drosophila*](https://www.nature.com/articles/s41592-024-02497-y),
  *Nature Methods* 21, 2353–2362. DOI: `10.1038/s41592-024-02497-y`.
  Extended Data Fig. 3 describes wide-angle eye views, fisheye correction and
  averaging into ommatidia; its roughly 270° horizontal field and 17° overlap
  informed our angular bounds. We do not run FlyGym or use its trained controllers.
- [*Eye structure shapes neuron function in Drosophila motion vision*](https://www.nature.com/articles/s41586-025-09276-5)
  (2025), *Nature*. DOI: `10.1038/s41586-025-09276-5`.
  Supports treating visual directions as spherical geometry rather than a flat
  screen grid. This demo does not import the paper's optical-axis registration.

### Further reading, not used in the shipped mapping

- Straw Lab's [Drosophila eye map](https://github.com/strawlab/drosophila_eye_map)
  contains digitized Buchner (1971) ommatidial directions under a BSD license.
  It is a possible basis for a future calibrated registration. No directions or
  code from that repository are bundled or loaded by this implementation.

The six-face render, zero eye baseline, fixed eye height, angular registration,
seven-sample acceptance cone, RGB encoding and body-relative Mario controls are
our engineering choices. None of these citations validates the complete demo as
a physiological model of fly vision or behavior.

## Attribution and private assets

MaleCNS: Berg et al., *Sexual dimorphism in the complete connectome of the
Drosophila male central nervous system*,
[data and CC-BY terms](https://male-cns.janelia.org/download/).
Optic assignments pinned to supplemental commit
`67767d2233657983993ff6c2be48e836a935863c`.

SM64: [sm64pc/sm64ex](https://github.com/sm64pc/sm64ex/tree/d7ca2c04364a6dd0dac58b47151e04e26887e6f0),
pinned commit `d7ca2c04364a6dd0dac58b47151e04e26887e6f0`.

The supplied ROM, extracted Nintendo assets, native binary, dataset caches,
browser profiles and recordings are gitignored. The US ROM SHA-1 is
`9bef1128717f958171a4afac3ed78ee2bb4e86ce`. It is copied only into the private
build cache for extraction, never into source deliverables or distributed.
