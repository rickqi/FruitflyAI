"""
Telemetry audit: flow_json key manifest generator, startup validation,
and dead-value vitality detection.

Part of t4 B6 (telemetry drift regression) + B7 (dead-value telemetry).
"""

from __future__ import annotations

import json
import math
import time
from collections import deque
from pathlib import Path
from typing import Any, Optional


# ── Pattern-field key extractor (B6) ──────────────────────────────────

def _extract_condition_keys(pattern: dict) -> set[str]:
    """Return all field names referenced in a single pattern's conditions."""
    cond = pattern.get("conditions", {})
    keys: set[str] = set()
    for key in cond:
        # Skip computed/internal keys that aren't telemetry fields
        if key.startswith("_"):
            continue
        keys.add(key)
    return keys


def generate_key_manifest(patterns_path: Optional[Path] = None) -> dict:
    """Generate the canonical key manifest from default_patterns.json.

    Returns a dict with:
      - source         : path or "<built-in DEFAULT_PATTERNS>"
      - pattern_count  : number of patterns parsed
      - required_keys  : sorted list of unique field names referenced
                         in pattern conditions
      - generated_at   : ISO timestamp
    """
    if patterns_path is None:
        patterns_path = (Path(__file__).resolve().parent.parent
                         / "skills" / "default_patterns.json")

    source_label = str(patterns_path)
    all_keys: set[str] = set()
    pattern_count = 0

    try:
        data = json.loads(patterns_path.read_text(encoding="utf-8"))
        patterns = data.get("patterns", [])
        pattern_count = len(patterns)
        for pat in patterns:
            all_keys |= _extract_condition_keys(pat)
    except Exception as exc:
        source_label = f"ERROR loading {patterns_path}: {exc}"

    return {
        "source": source_label,
        "pattern_count": pattern_count,
        "required_keys": sorted(all_keys),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


# ── Startup key validator (B6) ────────────────────────────────────────

class FlowKeyValidator:
    """Validate runtime flow_json/memory_json keys against the canonical manifest.

    Usage::

        validator = FlowKeyValidator()
        validator.check(flow_json_dict, name="flow_json")
        # -> validator.missing_keys, validator.extra_keys populated
        # -> validator.summary() returns human-readable report
    """

    def __init__(self, manifest: Optional[dict] = None):
        if manifest is None:
            manifest = generate_key_manifest()
        self.manifest = manifest
        self.required_keys: set[str] = set(manifest.get("required_keys", []))
        self.missing_keys: list[str] = []
        self.extra_keys: list[str] = []
        self.last_check_time = 0.0

    def check(self, actual: dict, name: str = "flow_json") -> dict:
        """Compare ``actual`` keys against the manifest.

        Returns a dict with missing/extra lists and a passed flag.
        """
        actual_keys = set(actual.keys())
        self.missing_keys = sorted(self.required_keys - actual_keys)
        self.extra_keys = sorted(actual_keys - self.required_keys)
        self.last_check_time = time.time()
        result = {
            "source": name,
            "required": len(self.required_keys),
            "present": len(self.required_keys & actual_keys),
            "missing": self.missing_keys,
            "extra": self.extra_keys,
            "passed": len(self.missing_keys) == 0,
        }
        return result

    def summary(self) -> str:
        """One-line human-readable status."""
        parts = []
        if self.missing_keys:
            parts.append(f"missing={len(self.missing_keys)} ({','.join(self.missing_keys[:6])})")
        if self.extra_keys:
            parts.append(f"extra={len(self.extra_keys)}")
        if not parts:
            return "✓ all pattern-condition keys present"
        return "; ".join(parts)


# ── Dead-value detector (B7) ──────────────────────────────────────────

class DeadValueDetector:
    """Detect telemetry fields whose value has not meaningfully changed
    over a rolling window.

    A field is flagged as "dead" when, for N consecutive observations,
    its absolute or relative change stays below a threshold.  Fields that
    are inherently static (booleans, strings, counts with tight range)
    are handled separately.

    Usage::

        dvd = DeadValueDetector(window=100, abs_thresh=1e-4, rel_thresh=0.01)
        dvd.push(flow_json_snapshot)        # every publish tick
        findings = dvd.get_dead_fields()    # returns list of field reports
    """

    def __init__(self, window: int = 100,
                 abs_threshold: float = 1e-4,
                 rel_threshold: float = 0.01,
                 min_observations: int = 20):
        self.window = window
        self.abs_threshold = abs_threshold
        self.rel_threshold = rel_threshold
        self.min_observations = min_observations

        # Per-field rolling ring: list of (timestamp, value) pairs
        self._history: dict[str, deque[tuple[float, float]]] = {}
        # Known static fields to skip (booleans, strings, etc.)
        self._skip_fields: set[str] = set()

    def _classify(self, key: str, val: Any) -> str:
        """Classify a field value type: 'numeric', 'bool', 'string', 'null', 'other'."""
        if val is None:
            return "null"
        if isinstance(val, bool):
            return "bool"
        if isinstance(val, (int, float)):
            return "numeric" if not math.isnan(val) and not math.isinf(val) else "other"
        if isinstance(val, str):
            return "string"
        return "other"

    def push(self, snapshot: dict) -> None:
        """Feed one observation (flow_json dict) into the detector."""
        now = time.time()
        for key, val in snapshot.items():
            kind = self._classify(key, val)

            # Skip non-numeric — dead-value detection only for numeric fields
            if kind != "numeric":
                self._skip_fields.add(key)
                continue

            if key not in self._history:
                self._history[key] = deque(maxlen=self.window)
            self._history[key].append((now, float(val)))

    def get_dead_fields(self, exclude: Optional[set[str]] = None) -> list[dict]:
        """Return list of dead-field reports.

        Each report::

            {
                "field": "asymmetry",
                "mean_value": 0.023,
                "std_dev": 3.2e-6,
                "unchanged_frames": 98,
                "severity": "warning",    # "warning" | "stale" | "ok"
                "since": 12345.6,
            }

        Returns empty list when all fields are healthy.
        """
        exclude = exclude or set()
        reports: list[dict] = []

        for key, hist in self._history.items():
            if key in exclude or key in self._skip_fields:
                continue
            if len(hist) < self.min_observations:
                continue

            vals = [v for _, v in hist]
            n = len(vals)
            mean_val = sum(vals) / n
            # Population std-dev
            variance = sum((v - mean_val) ** 2 for v in vals) / n
            std_dev = math.sqrt(variance)

            # How many trailing items are effectively unchanged?
            unchanged = 0
            if n >= 2:
                last_val = vals[-1]
                for v in reversed(vals[:-1]):
                    delta = abs(v - last_val)
                    if delta < self.abs_threshold:
                        unchanged += 1
                    else:
                        break

            if std_dev < self.abs_threshold and unchanged >= self.min_observations // 2:
                # The field has been essentially constant over the window
                reports.append({
                    "field": key,
                    "mean_value": round(mean_val, 6),
                    "std_dev": round(std_dev, 8),
                    "unchanged_frames": unchanged,
                    "severity": "stale",
                    "since": hist[0][0],
                })
            elif unchanged >= int(self.window * 0.8):
                # Trailing values barely changing
                reports.append({
                    "field": key,
                    "mean_value": round(mean_val, 6),
                    "std_dev": round(std_dev, 8),
                    "unchanged_frames": unchanged,
                    "severity": "warning",
                    "since": hist[-unchanged][0] if unchanged > 0 else hist[0][0],
                })

        reports.sort(key=lambda r: r["severity"])
        return reports

    def reset(self) -> None:
        self._history.clear()
        self._skip_fields.clear()


# ── Convenience: build the telemetry-audit section for dash publish ──

def build_telemetry_audit_section(
    key_validator: FlowKeyValidator,
    dead_detector: DeadValueDetector,
    flow_snapshot: dict,
) -> dict:
    """Build a compact telemetry audit dict for inclusion in flow_json."""
    key_result = key_validator.check(flow_snapshot) if flow_snapshot else {}
    dead_fields = dead_detector.get_dead_fields()

    section: dict = {}
    if key_result:
        section["key_check"] = {
            "passed": key_result.get("passed", False),
            "missing": key_result.get("missing", [])[:6],
            "missing_count": len(key_result.get("missing", [])),
        }
    if dead_fields:
        stale = [d["field"] for d in dead_fields if d["severity"] == "stale"]
        warnings = [d["field"] for d in dead_fields if d["severity"] == "warning"]
        section["dead_fields"] = {
            "stale": stale[:8],
            "stale_count": len(stale),
            "warning": warnings[:8],
            "warning_count": len(warnings),
            "total": len(dead_fields),
        }
    return section