"""Hold a nonblocking process-tree lock across the shell launcher."""
import fcntl
import os
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve().parent
(root / "runtime").mkdir(exist_ok=True)
lock = os.open(root / "runtime/launcher.lock", os.O_CREAT | os.O_RDWR, 0o600)
try:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    sys.exit("Fly64 is already running. Close the game before starting another instance.")
os.set_inheritable(lock, True)
os.environ["FLY64_LOCKED"] = "1"
os.execv(sys.argv[1], sys.argv[1:])
