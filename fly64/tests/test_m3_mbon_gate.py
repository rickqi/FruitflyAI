"""M3.2: MBON-assisted longjump gating — source contract tests."""
import re
import sys
from pathlib import Path

MAIN = Path(__file__).resolve().parent.parent / "fly64" / "main.py"


def _src() -> str:
    return MAIN.read_text(encoding="utf-8")


def test_mbon_gate_threshold_present():
    s = _src()
    assert "_lj_stuck_need = 3.0" in s, "default rule threshold missing"
    assert "_lj_stuck_need = 1.5" in s, "MBON-bonus threshold missing"


def test_mbon_gate_reads_longjump_column():
    s = _src()
    assert re.search(r"mbon_outputs\[8\]\) > 0", s), \
        "gate must read the longjump_bias column (index 8)"


def test_mbon_gate_used_by_longjump_branch():
    s = _src()
    assert re.search(r"stuck_duration > _lj_stuck_need", s), \
        "longjump branch must consume the adaptive threshold"
    # old hard-coded threshold must be gone from the longjump branch
    assert not re.search(r"longjump\" in _wl and _cpg_ramp\n\s*and memory_ctrl\.stuck_duration > 3\.0", s)
