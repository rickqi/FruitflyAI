"""PIN tests: rule 17 strict version-increment enforcement.

Versions must strictly advance across the record chain — no reuse, no
downgrade, no canonical drift from main.py.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skills.evolution_skill import (version_chain_audit,  # noqa: E402
                                    _semver)


class TestSemver:
    def test_valid(self):
        assert _semver("2.19.3") == (2, 19, 3)
        assert _semver("1.0.0") == (1, 0, 0)

    @pytest.mark.parametrize("bad", ["2.11.x", "1.0.x", "abc", "", "2.19"])
    def test_invalid_returns_none(self, bad):
        assert _semver(bad) is None


def _rec(bv=None, sv=None):
    return {"brain_version": bv, "skill_version": sv}


class TestVersionChainAudit:
    def test_clean_chain_passes(self):
        records = [_rec("2.19.0", "3.1.0"), _rec("2.19.1", "3.1.0"),
                   _rec("2.19.2", "3.1.0"), _rec("2.19.3", "3.1.1")]
        issues = version_chain_audit(records, {"brain": "2.19.3", "skill": "3.1.1"},
                                     "2.19.3", "3.1.1")
        assert issues == []

    def test_canonical_behind_max_record_fails(self):
        records = [_rec("2.19.3", None)]
        issues = version_chain_audit(records, {"brain": "2.19.0", "skill": "3.1.1"},
                                     "2.19.0", "3.1.1")
        assert issues and "落后" in issues[0]

    def test_main_mismatch_fails(self):
        issues = version_chain_audit([], {"brain": "2.19.3", "skill": "3.1.1"},
                                     "2.18.0", "3.1.1")
        assert issues and "BRAIN_VERSION" in issues[0]

    def test_skill_downgrade_fails(self):
        records = [_rec(None, "3.1.1")]
        issues = version_chain_audit(records, {"brain": "2.19.3", "skill": "3.0.0"},
                                     "2.19.3", "3.0.0")
        assert issues and "skill" in issues[0]

    def test_legacy_nonsemver_labels_tolerated(self):
        records = [_rec("1.0.x", None), _rec("2.11.x", None), _rec("2.19.3", "3.1.1")]
        issues = version_chain_audit(records, {"brain": "2.19.3", "skill": "3.1.1"},
                                     "2.19.3", "3.1.1")
        assert issues == []
