#!/usr/bin/env bash
set -euo pipefail

cd /root/fly64
export PYTHONPATH=/root/fly64

echo "=== Python ==="
python3 --version
python3 -c "import time; print('clock OK:', time.clock_gettime_ns(time.CLOCK_MONOTONIC))"

echo "=== Dependencies ==="
python3 -c "import numpy; print('numpy', numpy.__version__)"
python3 -c "import scipy; print('scipy', scipy.__version__)"
python3 -c "import aiohttp; print('aiohttp', aiohttp.__version__)" 2>&1 || echo "aiohttp MISSING"
python3 -c "import PIL; print('Pillow', PIL.__version__)" 2>&1 || echo "Pillow MISSING"
python3 -c "import websockets; print('websockets', websockets.__version__)" 2>&1 || echo "websockets MISSING"

echo "=== Bridge test ==="
python3 -c "
import tempfile, os
p = tempfile.mktemp()
from fly64.bridge import SharedBridge
b = SharedBridge(p, create=True)
print('bridge OK:', b.path)
b.close()
os.unlink(p)
"

echo "=== Environment READY ==="