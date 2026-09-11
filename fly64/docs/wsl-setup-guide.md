# Fly64 WSL Setup Guide

## Current Status

| Step | Component | Status |
|------|-----------|--------|
| 1 | WSL Ubuntu 22.04 | ✅ Running |
| 2 | Build toolchain (gcc, make, python3) | ✅ Ready |
| 3 | Build libs (SDL2, GLEW, pkg-config) | ✅ Installed |
| 4 | Brain data (166.7K neurons, 25.6M edges) | ✅ Present |
| 5 | sm64ex repo (commit `d7ca2c04`) | ✅ Cloned |
| 6 | Fly64 patch (bridge/vision files) | ✅ Applied |
| 7 | Scripts (WSL-adapted `setup_sm64.sh`) | ✅ Ready |
| 8 | **Super Mario 64 US ROM (`baserom.us.z64`)** | ❌ **Needed** |
| 9 | sm64ex compiled binary | ⏳ Pending ROM |

---

## Step 1: Obtain a Super Mario 64 US ROM

You need an **unmodified US Super Mario 64 .z64 ROM**. This is a copyrighted
Nintendo asset and is **not** included in any repository. The decompiled sm64ex
project requires this ROM to extract game assets before compilation.

### Legal ways to obtain the ROM

| Method | Details |
|--------|---------|
| **Dump from cartridge** (recommended) | If you own an original SM64 N64 cartridge, dump it using a device like the Retrode2, GameShark, or a custom N64 flash cart. |
| **No-Intro ROM set** | The No-Intro ROM database catalogs verified dumps. Use a known-good No-Intro source you legally possess. |
| **Existing backup** | If you own the original game, a personal backup of your cartridge is considered legitimate. |

### Expected file identity

| Property | Value |
|----------|-------|
| **Game** | Super Mario 64 (USA) |
| **ROM type** | Uncompressed `.z64` (byte-swapped) — **not** `.v64` or `.n64` |
| **File name** | `baserom.us.z64` (will be placed at `~/fly64/.cache/sm64ex/baserom.us.z64`) |
| **SHA-1 checksum** | `9bef1128717f958171a4afac3ed78ee2bb4e86ce` |

> ⚠️ The build will **refuse** any ROM that does not match the exact SHA-1
> above. A modified ROM (ROM hack, patched version, corrupted dump) will fail
> validation.

### How to verify the ROM on Windows

Open **PowerShell** or **Command Prompt** and run:

```powershell
# PowerShell
Get-FileHash "path\to\Super Mario 64 (U).z64" -Algorithm SHA1
```

Verify the output matches `9bef1128717f958171a4afac3ed78ee2bb4e86ce`.

---

## Step 2: Place the ROM for WSL access

### Option A: Place the ROM inside WSL (recommended)

Copy the ROM from Windows to the WSL filesystem:

```powershell
# From PowerShell on Windows — adjust paths as needed
cp "D:\path\to\your\baserom.us.z64" "$env:USERPROFILE\AppData\Local\Packages\CanonicalGroupLimited.Ubuntu22.04LTS_79rhkp1fndgsc\LocalState\rootfs\root\"
```

Or more simply, place it in your project directory and copy it into WSL:

```powershell
# Place ROM in the fly64 workspace first, then in WSL:
wsl cp /mnt/d/codes/flygym/baserom.us.z64 ~/fly64/.cache/sm64ex/baserom.us.z64
```

### Option B: Mount the Windows drive path

Your Windows drives are available in WSL at `/mnt/<drive-letter>/`. For example,
a file at `D:\roms\sm64.us.z64` is accessible as `/mnt/d/roms/sm64.us.z64`.

---

## Step 3: Build sm64ex with the ROM

Once the ROM is in place inside WSL, run the adapted setup script:

```bash
# Inside WSL (Ubuntu terminal)
cd ~/fly64
bash scripts/setup_sm64.sh ~/fly64/.cache/sm64ex/baserom.us.z64
```

Or if the ROM is elsewhere:

```bash
cd ~/fly64
bash scripts/setup_sm64.sh /mnt/d/roms/sm64.us.z64
```

### What the script does

1. **Verifies the ROM** — SHA-1 check (`9bef1128717f958171a4afac3ed78ee2bb4e86ce`)
2. **Copies the ROM** — to `~/fly64/.cache/sm64ex/baserom.us.z64`
3. **Installs missing dependencies** — via `apt-get` if needed
4. **Builds sm64ex** — compiles the patched US build (single-threaded for reliability)

> ⏱️ Build time: approximately 2–10 minutes depending on WSL performance.

### Expected output

After a successful build, the binary will be at:

```
~/fly64/.cache/sm64ex/build/us_pc/sm64.us.f3dex2e
```

You can verify with:

```bash
ls -la ~/fly64/.cache/sm64ex/build/us_pc/sm64.us.f3dex2e
```

---

## Step 4: Run Fly64

```bash
cd ~/fly64
./run-fly64 --rom ~/fly64/.cache/sm64ex/baserom.us.z64
```

The first run will:
- Create Python virtual environment (`.venv`)
- Install Python dependencies
- Verify brain data
- Launch the SM64 emulation window and the Fly64 dashboard

> **Dashboard URL** (open while demo is running): http://127.0.0.1:8765/

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| **ROM validation failed** | Your ROM doesn't match SHA-1 `9bef1128717f958171a4afac3ed78ee2bb4e86ce`. Obtain an unmodified US Super Mario 64 ROM. |
| **`sha1sum: command not found`** | Run `sudo apt-get install coreutils` in WSL. |
| **Build fails on `mingw-w64`** | Run `sudo apt-get install -y mingw-w64` then re-run the setup script. |
| **`/mnt/d/` not found** | Your Windows drives are auto-mounted by WSL. If missing, run `wsl --mount` from PowerShell or check WSL settings. |
| **Permission denied on ROM** | Ensure the ROM file is readable in WSL: `chmod 644 /path/to/baserom.us.z64`. |
| **Already running** | Close the existing sm64ex window before starting a new instance. |
| **No dashboard** | Open http://127.0.0.1:8765/ while demo is running. Check that port 8765 is free. |

---

## Quick Reference

```bash
# Verify ROM SHA-1 (Windows PowerShell)
Get-FileHash "baserom.us.z64" -Algorithm SHA1

# Copy ROM into WSL (from Windows)
wsl cp /mnt/d/roms/sm64.us.z64 ~/fly64/.cache/sm64ex/baserom.us.z64

# Build sm64ex (in WSL)
cd ~/fly64 && bash scripts/setup_sm64.sh ~/fly64/.cache/sm64ex/baserom.us.z64

# Run Fly64 (in WSL)
cd ~/fly64 && ./run-fly64 --rom ~/fly64/.cache/sm64ex/baserom.us.z64
```

**Expected SHA-1:** `9bef1128717f958171a4afac3ed78ee2bb4e86ce`