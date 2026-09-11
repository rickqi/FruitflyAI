# Super Mario 64 ROM — Setup Guide for Fly64

## ROM Required

You need an **unmodified US Super Mario 64 .z64 ROM**.
The decompiled sm64ex project requires it to extract game assets.

| Property | Value |
|----------|-------|
| **ROM** | Super Mario 64 (USA), uncompressed `.z64` |
| **SHA-1** | `9bef1128717f958171a4afac3ed78ee2bb4e86ce` |
| **Target path** | `~/fly64/.cache/sm64ex/baserom.us.z64` |

> ⚠️ A modified ROM (ROM hack, corrupted dump) will **not** work.
> The build script enforces the SHA-1 check and exits with an error on mismatch.

---

## Quick Steps

### 1. Obtain the ROM

- **Recommended**: Dump from your own original N64 cartridge.
- **Alternative**: If you legally own a copy, use a verified No-Intro dump.

### 2. Verify the SHA-1 (Windows)

```powershell
Get-FileHash "path\to\your\rom.z64" -Algorithm SHA1
```

Confirm the output is:
```
9bef1128717f958171a4afac3ed78ee2bb4e86ce
```

### 3. Place the ROM into WSL

```powershell
# From Windows PowerShell — copy into WSL
wsl cp /mnt/d/path/to/your/baserom.us.z64 ~/fly64/.cache/sm64ex/baserom.us.z64
```

Or directly from a Windows path:
```powershell
wsl cp /mnt/d/roms/sm64.us.z64 ~/fly64/.cache/sm64ex/baserom.us.z64
```

### 4. Build sm64ex

Inside WSL (Ubuntu terminal):

```bash
cd ~/fly64
bash scripts/setup_sm64.sh ~/fly64/.cache/sm64ex/baserom.us.z64
```

Build time: ~2–10 minutes.

### 5. Run Fly64

```bash
cd ~/fly64
source .venv/bin/activate
./run-fly64 --rom ~/fly64/.cache/sm64ex/baserom.us.z64
```

Open the dashboard at **http://127.0.0.1:8765/** while the demo runs.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| **ROM validation failed** | SHA-1 mismatch. Get an unmodified US ROM. |
| **`sha1sum: command not found`** | `sudo apt-get install coreutils` |
| **`mingw-w64` build issue** | `sudo apt-get install -y mingw-w64` then retry |
| **Build already started** | Close existing sm64ex window first. |

---

### Pre-Configured Environment Status

| Component | Status |
|-----------|--------|
| WSL Ubuntu | ✅ Ready |
| gcc, make, SDL2, GLEW | ✅ Installed |
| sm64ex repo (commit `d7ca2c04`) | ✅ Cloned |
| Fly64 patch | ✅ Applied |
| Build script (WSL-adapted) | ✅ Ready |
| **ROM (`baserom.us.z64`)** | ❌ **You provide this** |
| Build output | ⏳ Pending ROM |