# Fly64

See: https://x.com/barrelshifter/status/2097004115826200898

The fly brain model got popular on social media. I decided to try to:

- Take the fly brain model from here: http://male-cns.janelia.org
- Make it play a game

I chose SM64 because I like SM64 and a decompiled version is available. I made
this work specifically on my Macbook (M2, 16 GB RAM).

You will need

- 1.1 GB space for the brain data
- a US mario 64 rom (for assets)
- Homebrew (mac)
- Google Chrome
- Standard dev tools (e.g. on a mac `xcode select --install`)

This code is *literally 100% vibe coded* with GPT Astra, and I did it just for
fun. I have not reviewed the code, so be cautious if you want to use this
for anything "real".

I'm posting this because people are interested/for educational purposes.

# Running it

I've only tested this on one macbook in existence.

```sh
cd "/path/to/fly64"
./run-fly64 --rom "/path/to/base_mario_64_rom.us.z64"
```

This

- Installs deps
- Downloads brain data
- Builds decompiled SM64
- Opens the SM64 build, and the demo window

This might take a while to download etc.

You need your own **unmodified US Super Mario 64 .z64 ROM**. It is not included
and can live anywhere on your computer; pass its path after `--rom`.

## Stop it

Click the game, then press **Escape**. Or press **Ctrl+C** in Terminal.

**F8** turns neural control on or off. Try **fn+F8** if your Mac uses media keys.

## Build without opening the demo

From your project folder, using the same ROM path:

```sh
./run-fly64 --prepare-data
./scripts/setup_sm64.sh "/path/to/baserom.us.z64"
```

## If something looks wrong

- **“Already running”:** close the existing game before starting another.
- **“ROM validation failed”:** use an unmodified US `.z64` ROM.
- **No dashboard:** open [the local dashboard](http://127.0.0.1:8765/) while the demo is running.
- **Mario isn't moving:** click the game and check F8. Look for **“Game: receiving”**
  and the **sent → received** values. Mario can also get stuck against walls.

## Record a video

Close any running demo first. From your project folder, using the same ROM path:

```sh
./scripts/record_demo.sh "/path/to/baserom.us.z64"
```

Requires macOS 15 or newer. Allow screen recording if macOS asks.
It launches the demo and saves a roughly 75-second MP4 in `artifacts/`.
Only the game and dashboard are recorded, without audio.

## How it works

This runs 3 programs:

- Mario
- the brain model
- the dashboard.

They form a loop:

```text
Mario's world → fly eyes → brain network → controller → Mario's world
```

### The fly has its own camera

You watch the normal third-person game. The fly sees from Mario's eye height.
Moving your camera does not move the fly's camera.

Ten times a second, the game takes six hidden pictures around Mario.
Each is 128 by 128 pixels. Together they cover a sphere.
The fly gets no HUD and cannot see Mario's own body.

Each eye cell samples light from a small patch of that sphere.
The two eyes cover about 270 degrees around Mario, not the full sphere.
The dashboard shows their views as two fisheye pictures.

The eyes follow Mario's heading. They stay level and do not bob with his head.
This is a simple model, not a measured copy of a fly's eyes. The game has RGB
colors, not the ultraviolet light a real fly can detect.

The code measures light, color, and changes between pictures.

It sends those signals to the modeled eye cells.

Most cell ordering comes from anatomy or connections in the data. Some is
estimated. The map from that order to viewing angles is also an estimate.

### Signals pass through the network

The network comes from MaleCNS, a map of a male fly's nerve cells and their
connections.

The wiring for the nerve cells comes from measured data.

The rules for how cells fire are specific to this repo.

Each cell has a number that stands in for its voltage. That number fades toward
zero. Signals from other cells can raise or lower it. When it reaches a set
level, the cell fires and resets. Its signal reaches other cells on the next step.
The model takes 50 steps a second.

We also add a steady background drive and repeatable noise. So the screen is
not the cause of every movement.

The code stores cells and connections as compact arrays of numbers.

### Some signals become Mario's controls

We read the last quarter-second of activity in a few chosen groups of cells:

- DNg100 controls forward movement.
- The right-minus-left difference in DNa02/DNg13 controls steering.
- A burst in DNp01/DNp10 triggers a jump.

The code smooths the stick, ignores small changes, and limits its strength.
Each jump holds A for two game frames.

There is a short wait before another jump.

These are rules we wrote to turn neural activity into game controls.

For the fly, forward means the way Mario faces. It does not mean the way your
camera faces. Human stick input still uses the normal game controls.

There are no simulated fly legs or muscles. There is no training, reward, or
goal to collect stars. Mario can walk into a wall and stay there.

### The game and model share a small block of memory

The game writes pictures into it. The model writes controls back. Both sides
check that a message is complete before reading it.

The model also sends an “I'm still here” signal. If it goes quiet for a quarter
of a second, the game releases the neural controls. Both programs use the same
clock to check this.

### The dashboard

Read it from top to bottom:

1. **Eyes:** what the fly sees, and what changed since the last picture.
2. **Controls:** which cell groups fired, which gates they crossed, and what
   controls reached the game. All charts show the same ten seconds.
3. **Brain:** a still map. Brighter cells fired more often. Pick a cell group
   to see where its known locations are.

Hz means spikes per cell per second. The rate uses the last 13 steps, or 260 ms.
The scales stay fixed. A small signal does not become bright just because
everything else is quiet.

Gold ticks on the jump chart are requests. Cyan ticks mean the game reported A.
Neither proves Mario left the ground. The game can ignore a jump in some states.

Click **Freeze display** to read one moment. The game keeps running.
Click **Resume live** to return; the charts start a fresh history.

Missing cell locations are left off the map. Those cells still run in the model.
Broad activity can come from the shared background drive, not just the eyes.
The display shows signals and rules. It cannot show what a fly thinks.

[Display design, signal definitions, and sources](docs/dashboard-design.md)

### Each step is saved

The code saves the pictures, spikes, controls, and random seed.

The replay tool can run those pictures through the model again and check that
the same spikes and controls come out.

It does not need Mario running to do that.

This is an experiment built from real wiring and simple rules.

It is not a validated living fly or a trained Mario player.

[Model details, limitations, and tests](docs/technical-notes.md)

## References

- [MaleCNS v1.0](https://male-cns.janelia.org/download/): the measured wiring.
- [sm64ex](https://github.com/sm64pc/sm64ex/tree/d7ca2c04364a6dd0dac58b47151e04e26887e6f0): the native Mario engine we patch.
- [NeuroMechFly v2](https://www.nature.com/articles/s41592-024-02497-y) (2024): a guide for wide-angle fly vision.
- [Eye structure shapes neuron function in Drosophila motion vision](https://www.nature.com/articles/s41586-025-09276-5) (2025): why eye geometry matters.

These sources informed the demo. They do not validate its brain dynamics or
its eye-to-neuron map. See [what comes from each source](docs/technical-notes.md#research-references).
