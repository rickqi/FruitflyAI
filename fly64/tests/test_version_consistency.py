"""Version consistency tests — agent.md rule 8 enforcement.

Ensures BRAIN_VERSION is synchronised across all three declared locations:
  fly64/fly64/main.py — authoritative constant
  fly64/skills/skills.md — header badge (two occurrences)
  fly64/skills/evolution_history.json — canonical_versions.brain
"""

import json
import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent  # fly64/
SKILLS_DIR = PROJECT_ROOT / "skills"
MAIN_PY = PROJECT_ROOT / "fly64" / "main.py"
SKILLS_MD = SKILLS_DIR / "skills.md"
HISTORY_JSON = SKILLS_DIR / "evolution_history.json"


def _get_brain_version_from_main() -> str:
    """Parse BRAIN_VERSION assignment from main.py (the authoritative source)."""
    src = MAIN_PY.read_text(encoding="utf-8")
    m = re.search(r'^BRAIN_VERSION\s*=\s*"([^"]+)"', src, re.MULTILINE)
    assert m, f"BRAIN_VERSION not found in {MAIN_PY}"
    return m.group(1)


def _get_brain_versions_from_skills_md() -> list[str]:
    """Extract every BRAIN_VERSION **X.Y.Z** badge from skills.md."""
    src = SKILLS_MD.read_text(encoding="utf-8")
    return re.findall(r'BRAIN_VERSION \*\*(\d+\.\d+\.\d+)\*\*', src)


def _get_canonical_brain_from_history() -> str:
    """Read canonical_versions.brain from evolution_history.json."""
    data = json.loads(HISTORY_JSON.read_text(encoding="utf-8"))
    return data["canonical_versions"]["brain"]


EXPECTED = "2.23.11"


class TestVersionConsistency:
    """agent.md rule 8: version tri-sync (main.py ↔ skills.md ↔ history)."""

    def test_main_py_is_expected(self):
        """main.py declares the expected BRAIN_VERSION."""
        assert _get_brain_version_from_main() == EXPECTED

    def test_skills_md_badges_match_main(self):
        """Every BRAIN_VERSION badge in skills.md matches main.py."""
        badges = _get_brain_versions_from_skills_md()
        assert len(badges) >= 2, (
            f"Expected at least 2 BRAIN_VERSION badges in skills.md, "
            f"found {len(badges)}: {badges}"
        )
        for i, badge in enumerate(badges):
            assert badge == EXPECTED, (
                f"skills.md badge #{i + 1} is {badge!r}, expected {EXPECTED!r}"
            )

    def test_history_canonical_matches_main(self):
        """evolution_history.json canonical_versions.brain matches main.py."""
        canonical = _get_canonical_brain_from_history()
        assert canonical == EXPECTED, (
            f"canonical_versions.brain is {canonical!r}, expected {EXPECTED!r}"
        )

    def test_all_three_sources_agree(self):
        """All version declarations across main.py, skills.md, and history agree."""
        main_v = _get_brain_version_from_main()
        badges = _get_brain_versions_from_skills_md()
        canonical = _get_canonical_brain_from_history()

        for badge in badges:
            assert badge == main_v, f"skills.md badge {badge!r} != main.py {main_v!r}"
        assert canonical == main_v, (
            f"canonical_versions.brain {canonical!r} != main.py {main_v!r}"
        )