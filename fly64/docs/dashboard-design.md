# Reading the fly model

The aim is to answer three questions without decoding a rotating sculpture:
what changed in the view, why did the controller act, and where are the active
cells? This is instrumentation of an engineered model, not access to a fly's
thoughts. Coincident activity alone does not establish a causal pathway.

## Design research

- [ONS: Why less interactivity can be more](https://digitalblog.ons.gov.uk/2021/08/19/why-less-interactivity-can-be-more/)
  recommends showing important comparisons up front with small time-series
  charts and concise annotations. Applied here: motor pools and controls are
  visible together on one time axis, rather than hidden behind tabs.
- [NN/g: Memory Recognition and Recall in User Interfaces](https://www.nngroup.com/articles/recognition-and-recall/)
  explains why visible context reduces the need to remember things. Applied
  here: pool names, units, gates, line keys, and game status sit next to the data.
- [Datawrapper: Which color scale to use when visualizing data](https://www.datawrapper.de/blog/which-color-scale-to-use-in-data-vis)
  distinguishes unordered categories from ordered magnitudes. Applied here:
  cyan/gold identify traces, while a single dark-to-light ramp encodes firing
  rate. Line styles and text also identify traces. There is no rainbow scale,
  arbitrary activity threshold, or frame-by-frame rescaling of brightness.

These are design guidelines, not a usability study of this dashboard. Removing
rotation, retaining a short history, and separating inferred controls from game
acknowledgements are design decisions for this particular loop.

## What each instrument means

| Instrument | Meaning | Limit |
| --- | --- | --- |
| Eye previews | Cone-sampled left/right first-person views, 256×128 RGB | Engineered optics; not UV or an exact display of each photoreceptor |
| Change image | Absolute luminance difference between successive distinct frame sequence numbers, using 0.2126R + 0.7152G + 0.0722B | Not optical flow, motion direction, or the per-tick afferent current |
| Left/right change % | Mean absolute luminance difference within each preview's valid mask, divided by 255 | Retained until the next new frame; a stalled input is identified by frame age |
| Pool traces | Mean spikes per member per second over the last 13 neural ticks | A 260 ms rolling window; startup uses the actual number of ticks so far |
| Forward gate | DNg100 rate greater than 0.4 Hz produces positive raw forward input | Smoothing and the dead zone can still make the sent stick zero |
| Steering pools | Left and right DNa02/DNg13 rates; right minus left drives x | An engineered decoder, not a fitted fly-to-Mario policy |
| Jump gate and marks | DNp01/DNp10 above 2 Hz plus an elapsed 0.8 s cooldown requests A; gold marks retain the exact request ticks | Cyan marks sample the latest game-reported A state; they are not a ground-contact detector |
| Stick traces | Solid lines: neural requests. Dashed lines: last observed game-applied axes | Game acknowledgements are asynchronous samples, not matched same-frame receipts. Stale/disabled samples are gaps, not invented zeroes |
| Fixed map | Located cells in the cache's normalized X/Y projection, brightness 0–50 Hz | Not a neuropil map. Locations may be soma or to-soma annotation points. Overlap hides cells. Unlocated cells are omitted only from the drawing |
| Population selector | Members of the actual decoder/input arrays | Pool labels identify the engineering use of annotated cell types, not mental faculties |

Motor rate charts use a fixed 0–10 Hz range to make low-rate changes legible;
triangles explicitly mark samples above 10 Hz. Numeric readouts remain uncapped.
Stick uses −70 to +70. One spike per 20 ms tick makes 50 Hz the maximum;
the map retains that full 0–50 Hz scale. Map bytes quantize it to 256 levels (about
0.196 Hz per step). Pool traces retain unquantized rates. Selected population
means include members without known positions. The default whole-model mean
uses quantized map data and is marked as such.

The model still uses raw spikes/cell/tick internally. Display conversion divides
by 0.02 s. The existing raw controller is `y=clip((forwardHz-0.4)*40,0,70)` and
`x=clip((rightHz-leftHz)*22,-70,70)`, followed by the existing 0.78/0.22 EMA,
dead zone of 8, and integer conversion. None of these dynamics were changed.

Freeze holds the displayed packet, eye images, map, and ten-second chart history.
It does not stop the game, controls, recording, or neural updates. Resume starts
a fresh chart history instead of drawing a line across the missing interval.
Connection status remains live while frozen. Missing streamed ticks also break
traces. The compact layout fits the launcher's 840×900 window: fixed-height
vision and anatomy strips surround a flexible stack of traces. Only the bottom
trace repeats the shared time-axis labels. Units, gates, and acknowledgements
remain visible; longer explanations live here instead of on the dashboard.
Small screens and enlarged text may still scroll rather than clip information.

## Data-oriented implementation

`fly64/telemetry.py` is a read-only observer. A 13×N byte ring plus N byte counts
tracks rolling spike rates for all neurons. This avoids retaining dense float
history or changing the connectome. Every 20 ms tick contributes one small
named record; 5–10 Hz display packets batch those records without averaging
away controller events. The browser retains at most ten seconds of records
and the latest full-neuron/eye snapshots. Freeze retains one additional snapshot.

The old F642 dashboard protocol is replaced, not supported in parallel.
The native shared-memory bridge and deterministic replay format are unchanged.
F643 packets contain:

1. Little-endian `<4sI`: magic `F643`, then JSON byte length.
2. UTF-8 JSON: schema 3, sequence, dimensions, number of cells, rate scale,
   rolling-window length, all pending per-tick records, and performance counters.
3. N uint8 firing-rate values.
4. 256×128×3 uint8 eye-preview bytes.
5. 256×128×3 uint8 luminance-change preview bytes.

Receivers check magic, schema, dimensions, and exact byte count. Only local
allowlisted assets are served. The page needs no CDN, external font, frontend
package install, or cloud service. Browser rendering follows incoming samples;
there is no rotating camera, continuous animation loop, or animated avatar.

Tests cover exact rolling counts, startup normalization, rate quantization,
per-tick timestamps, preview change persistence, protocol sizing, and identical
spikes/voltages/controls with and without observation. Existing replay,
retina, decoder, and bridge tests still apply.
