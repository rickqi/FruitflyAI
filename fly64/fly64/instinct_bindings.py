"""Scene → strategy instinct bindings (P4.4, t3/t7/t9).

The coach (GLM) tunes strategy parameters per stuck episode; when the SAME
scene keeps improving under the SAME *salient* parameter set, that set is
promoted to an *instinct*: the brain applies it directly on scene entry and the
coach is no longer consulted for that scene.

Data flow
---------
    coach consult -> active_strategy.json -> behaviour -> outcome window
                                                            |
                              coach_outcomes.resolve_outcome -> record_outcome
                                                            |
                                      skills/scene_strategy_bindings.json
                                                            |
                     main.py hot-reload: get_binding(scene) -> merge params

The JSON file is the interface between the coach side (plugin/) and the brain
(fly64/), so no cross-package import is required at runtime.

Why a *salient* signature and not the whole parameter dict (t9 root cause)
------------------------------------------------------------------------
The first implementation fingerprinted every key of every bound section.  Real
data killed it: the coach re-tunes on every consult, so 11 outcomes from one
scene produced 13 mutually distinct fingerprints, and no signature ever
reached the promotion threshold.  The mechanism was wired, tested, and
*structurally unreachable* — the same class of defect as the t6 passthrough bug.

Evidence from the recorded corpus (45 outcomes) at several granularities:

    signature granularity        distinct sigs (致命熔岩地)   promotable (improved>=2)
    exact, all sections                     13                        0
    quantized, all 5 params                 12                        0
    mode + turn_bias + stuck_bucket         10                        1 (2 imp / 1 worse)
    mode + turn_bias                         6                        2 (2/0 and 2/2)
    mode only                                2                        2

So the signature is quantized down to the parameters that actually reach the
behaviour pipeline (``fallen_recovery.mode``, ``exploration.turn_bias``,
``escape.stuck_threshold_s`` bucketed), while episode-specific knobs
(``command.heading``, ``command.duration_s``, ``climb_period``,
``persist_seconds``, ``reverse_seconds``, ``bold_explore_stuck_s``) are
deliberately EXCLUDED — they vary every episode and would re-fragment the
evidence without adding causal content.

Promotion rule
--------------
``improved >= PROMOTE_MIN_IMPROVED`` clean improvements *since the last worse*.
A ``worse`` verdict falsifies the signature: it demotes a promoted binding AND
zeroes the improvement counter, so a signature must re-earn promotion on fresh
evidence.  Cumulative totals are kept for audit.

NOTE ON CURRENT EVIDENCE (recorded negative result, t9): at the granularity
above the corpus yields *zero* promotable signatures — the best candidate is
``mode=directional_climb|turn_bias=0.8|stuck_threshold_s=5`` at 2 improved / 1
worse, and the ``mode+turn_bias`` view of the same data is 2 improved / 2 worse.
Promotion is therefore correctly refusing, and the instinct path stays dormant
until the evidence base grows.  Do NOT lower the gate to manufacture a
promotion: an instinct bound from a contradicted two-sample record is exactly
the fake-progress failure the curriculum ladder was fixed for.  Use
:func:`binding_status` to see how far each candidate is from qualifying.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

#: Redirectable so a TEST session can never write the live binding store into
#: the working tree (see tests/conftest.py).  The runtime passes nothing here
#: and gets the real skills/ path.
_EVIDENCE_DIR = os.environ.get("FLY64_EVIDENCE_DIR")
BINDINGS_PATH = (Path(_EVIDENCE_DIR) / "scene_strategy_bindings.json"
                 if _EVIDENCE_DIR
                 else Path(__file__).resolve().parent.parent / "skills"
                 / "scene_strategy_bindings.json")
PROMOTE_MIN_IMPROVED = 2
DEMOTE_ON_WORSE = True

#: sections that participate in a binding (what the behaviour pipeline reads)
BOUND_SECTIONS = ("exploration", "escape", "fallen_recovery")

#: (section, key, quantum) — quantum None means categorical.  This tuple IS the
#: signature definition; widening it re-fragments the evidence (see module docs).
SALIENT_PARAMS = (
    ("fallen_recovery", "mode", None),
    ("exploration", "turn_bias", 0.1),
    ("escape", "stuck_threshold_s", 5.0),
)

VERDICTS = ("improved", "unchanged", "worse")


def scene_key(scene_label: Optional[str]) -> str:
    """Scene identity for binding: the label prefix before the '#' hash.

    Labels look like "致命熔岩地 #f3f9"; the hash drifts with lighting, the
    prefix is stable, so bindings key on the prefix.

    MEASURED, not assumed (scripts/measure_scene_identity.py, 24 samples over
    2 minutes of live flight through one area):

        distinct label prefixes :  2   (墙体·通道 x22, 墙体·山坡 x1)
        distinct scene hashes   : 10   (2d989f x7, c69edb x8, then 8 singles)
        label -> hashes         : 1-to-many
        hash  -> labels         : 1-to-1

    So the hash is the FASTER-drifting field (it changed roughly every 15 s) and
    the prefix holds for minutes at a time.  Keying on the hash instead would be
    strictly worse: each bucket would receive ~2 samples before drifting away,
    and the promotion gate needs >=2 clean improvements *in one bucket*, so a
    hash key would make promotion unreachable — the very defect EVO-058 removed.

    Residual, deliberately NOT "fixed": the prefix still changes when the
    terrain composition genuinely changes (墙体·通道 -> 墙体·山坡 is a corridor
    becoming a slope).  Splitting evidence there is correct behaviour, not
    drift, so no aliasing/normalisation is applied.

    Note the actual cause of promotion not being reached yet is PARAMETER
    fragmentation, not scene identity: the live store shows one scene with four
    salient signatures whose turn_bias differs (0.6 / 0.7 / 0.8).  The coach
    explores a different parameter set per consult, so a bucket rarely sees two
    clean improvements.  That is inherent to exploration and should ease now
    that coach parameters actually reach behaviour (EVO-062/t6).
    """
    if not scene_label:
        return ""
    return str(scene_label).split("#")[0].strip()


def _quantize(value, quantum):
    if quantum is None:
        return value
    try:
        return round(round(float(value) / quantum) * quantum, 4)
    except (TypeError, ValueError):
        return value


def salient_signature(keys: dict) -> str:
    """Tolerant, quantized fingerprint of the behaviour-driving parameters."""
    keys = keys or {}
    parts = []
    for section, key, quantum in SALIENT_PARAMS:
        sec = keys.get(section)
        value = sec.get(key) if isinstance(sec, dict) else None
        parts.append(f"{section}.{key}={_quantize(value, quantum)}")
    return "|".join(parts)


def _fingerprint(keys: dict) -> str:
    """Backwards-compatible alias for the pre-t9 exact fingerprint.

    Retained for audit tooling; the promotion path uses
    :func:`salient_signature` instead.
    """
    parts = []
    for section in BOUND_SECTIONS:
        value = (keys or {}).get(section)
        if isinstance(value, dict):
            for k in sorted(value):
                parts.append(f"{section}.{k}={value[k]}")
    return "|".join(parts)


def load_bindings(path: Path = BINDINGS_PATH) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_bindings(bindings: dict, path: Path = BINDINGS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(bindings, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def extract_params(keys: dict) -> dict:
    """The parameter sections a binding carries (only the bound sections)."""
    return {s: dict((keys or {})[s]) for s in BOUND_SECTIONS
            if isinstance((keys or {}).get(s), dict)}


def binding_params(keys: dict) -> dict:
    """Exactly the parameters the signature discriminates, sectioned.

    Coherence requirement: the brain applies every key of a promoted binding,
    so a key that the signature does NOT discriminate would let two outcomes
    share a signature while implying different behaviour.  The bound parameter
    set is therefore restricted to :data:`SALIENT_PARAMS`; everything else
    (``reverse_seconds``, ``bold_explore_stuck_s``, ``climb_period``,
    ``persist_seconds``) stays owned by the coach / defaults and is merged
    under the binding at hot-reload time.

    Values are QUANTIZED, so they are the canonical representative of the
    signature class rather than whichever raw value happened to arrive last.
    Without this, ``turn_bias=0.81`` and ``turn_bias=0.79`` would share a
    signature yet bind different numbers — the same incoherence in a subtler
    form.
    """
    keys = keys or {}
    out: dict = {}
    for section, key, quantum in SALIENT_PARAMS:
        sec = keys.get(section)
        if isinstance(sec, dict) and key in sec:
            out.setdefault(section, {})[key] = _quantize(sec[key], quantum)
    return out


def _new_bucket(sig: str, params: dict) -> dict:
    return {
        "signature": sig,
        "params": params,
        "improved": 0,            # since the last `worse` (the promotion gate)
        "unchanged": 0,
        "worse": 0,               # since the last `worse` (0 or 1 by construction)
        "total_improved": 0,      # audit, never reset
        "total_worse": 0,
        "promoted": False,
        "first_seen": time.time(),
    }


def _scene_entry(bindings: dict, scene: str) -> dict:
    entry = bindings.get(scene)
    # tolerate the pre-t9 flat shape (one row per scene, no buckets)
    if isinstance(entry, dict) and "buckets" not in entry:
        sig = entry.get("fingerprint") or "legacy"
        params = entry.get("params") if isinstance(entry.get("params"), dict) else {}
        bucket = _new_bucket(sig, params)
        for v in VERDICTS:
            bucket[v] = int(entry.get(v, 0) or 0)
        bucket["total_improved"] = bucket["improved"]
        bucket["total_worse"] = bucket["worse"]
        bucket["promoted"] = bool(entry.get("promoted"))
        entry = {"scene": scene, "buckets": {sig: bucket},
                 "promoted": bucket["promoted"], "promoted_signature": sig,
                 "migrated_from_flat": True}
        bindings[scene] = entry
    elif not isinstance(entry, dict):
        entry = {"scene": scene, "buckets": {}, "promoted": False,
                 "promoted_signature": None}
        bindings[scene] = entry
    entry.setdefault("buckets", {})
    entry.setdefault("promoted", False)
    entry.setdefault("promoted_signature", None)
    return entry


def record_outcome(scene_label: Optional[str], keys: dict, verdict: str,
                   deltas: Optional[dict] = None,
                   path: Path = BINDINGS_PATH) -> Optional[dict]:
    """Update binding evidence from one resolved outcome.

    Returns the signature bucket (promoted or not), or None when the scene or
    the key material is unusable.
    """
    scene = scene_key(scene_label)
    params = binding_params(keys)
    if not scene or not params:
        return None
    sig = salient_signature(keys)

    bindings = load_bindings(path)
    entry = _scene_entry(bindings, scene)
    bucket = entry["buckets"].get(sig)
    if not isinstance(bucket, dict):
        bucket = _new_bucket(sig, params)
        entry["buckets"][sig] = bucket
    # keep the newest observed parameter set for auditability (salient keys only)
    bucket["params"] = params

    counted = verdict if verdict in VERDICTS else "unchanged"
    bucket[counted] = int(bucket.get(counted, 0)) + 1
    if counted == "improved":
        bucket["total_improved"] = int(bucket.get("total_improved", 0)) + 1

    # --- falsification: a worse verdict resets the improvement evidence ---
    if counted == "worse":
        bucket["total_worse"] = int(bucket.get("total_worse", 0)) + 1
        bucket["improved"] = 0
        bucket["unchanged"] = 0
        bucket["worse_reset_at"] = time.time()
        if DEMOTE_ON_WORSE and bucket.get("promoted"):
            bucket["promoted"] = False
            bucket["demoted_at"] = time.time()
            if entry.get("promoted_signature") == sig:
                entry["promoted"] = False
                entry["promoted_signature"] = None

    bucket["last_verdict"] = verdict
    bucket["last_deltas"] = dict(deltas or {})
    bucket["last_seen"] = time.time()

    # --- promotion: a clean record since the last worse ---
    if not bucket.get("promoted") and bucket["improved"] >= PROMOTE_MIN_IMPROVED:
        bucket["promoted"] = True
        bucket["promoted_at"] = bucket.get("promoted_at") or time.time()
        entry["promoted"] = True
        entry["promoted_signature"] = sig

    entry["updated_at"] = time.time()
    bindings[scene] = entry
    save_bindings(bindings, path)
    return bucket


def get_binding(scene_label: Optional[str],
                path: Path = BINDINGS_PATH) -> Optional[dict]:
    """Promoted parameter sections for a scene, or None.

    Used by the brain on strategy hot-reload: a promoted binding overrides the
    coach for that scene (that is the whole point of instinct consolidation).
    """
    scene = scene_key(scene_label)
    if not scene:
        return None
    entry = load_bindings(path).get(scene)
    if not isinstance(entry, dict):
        return None

    if "buckets" in entry:
        sig = entry.get("promoted_signature")
        bucket = (entry["buckets"] or {}).get(sig) if sig else None
        if not isinstance(bucket, dict) or not bucket.get("promoted"):
            return None
        params = bucket.get("params")
    else:                                        # legacy flat shape
        if not entry.get("promoted"):
            return None
        params = entry.get("params")
    return dict(params) if isinstance(params, dict) else None


def binding_status(path: Path = BINDINGS_PATH) -> dict:
    """How far every candidate signature is from promotion.

    Recorded negative result surface (t9): promotion refuses on the current
    corpus, and this makes the reason observable instead of silent.
    """
    bindings = load_bindings(path)
    rows = []
    for scene, entry in bindings.items():
        if not isinstance(entry, dict):
            continue
        buckets = entry.get("buckets") or {}
        for sig, b in buckets.items():
            if not isinstance(b, dict):
                continue
            imp = int(b.get("improved", 0) or 0)
            rows.append({
                "scene": scene,
                "signature": sig,
                "improved": imp,
                "unchanged": int(b.get("unchanged", 0) or 0),
                "worse": int(b.get("worse", 0) or 0),
                "promoted": bool(b.get("promoted")),
                "needed": max(0, PROMOTE_MIN_IMPROVED - imp),
                "qualifies": bool(b.get("promoted")) or imp >= PROMOTE_MIN_IMPROVED,
            })
    rows.sort(key=lambda r: (-r["improved"], r["scene"]))
    return {
        "scenes": len(bindings),
        "signatures": len(rows),
        "promoted": sum(1 for r in rows if r["promoted"]),
        "qualifying": sum(1 for r in rows if r["qualifies"]),
        "promote_min_improved": PROMOTE_MIN_IMPROVED,
        "rows": rows,
    }


def summary(path: Path = BINDINGS_PATH) -> dict:
    """Compact view for telemetry / CLI (one row per scene)."""
    bindings = load_bindings(path)
    out = []
    for scene, entry in bindings.items():
        if not isinstance(entry, dict):
            continue
        buckets = entry.get("buckets") or {}
        if not isinstance(buckets, dict):
            buckets = {}
        best = {}
        for b in buckets.values():
            if not isinstance(b, dict):
                continue
            if not best or (bool(b.get("promoted")), int(b.get("improved", 0) or 0)) > \
                    (bool(best.get("promoted")), int(best.get("improved", 0) or 0)):
                best = b
        out.append({
            "scene": scene,
            "improved": int(best.get("improved", 0) or 0),
            "worse": int(best.get("worse", 0) or 0),
            "promoted": bool(entry.get("promoted")),
            "signatures": len(buckets),
        })
    out.sort(key=lambda r: -r["improved"])
    return {
        "scenes": len(out),
        "promoted": sum(1 for r in out if r["promoted"]),
        "rows": out,
    }
