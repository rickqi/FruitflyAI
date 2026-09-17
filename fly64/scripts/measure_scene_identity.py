#!/usr/bin/env python3
"""Measure scene-identity stability: is the LABEL prefix or the HASH the stable key?

`instinct_bindings.scene_key()` keys bindings on the label prefix before '#',
justified by the comment "the hash drifts with lighting, the prefix is stable".
Live telemetry now shows composite prefixes drifting too (天空·山坡 / 通道·山坡 /
墙体·通道 / 山坡), so that justification must be measured rather than assumed.

This samples (scene_label, scene_hash) pairs from the live dashboard and reports
which component is stable enough to key a binding on.
"""
import json
import sys
import time
import urllib.request
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "http://127.0.0.1:8765"
SAMPLES = 24
INTERVAL = 5.0


def flow():
    return json.load(urllib.request.urlopen(BASE + "/flow.json", timeout=6))


def memory():
    return json.load(urllib.request.urlopen(BASE + "/memory.json", timeout=6))


def prefix(label):
    return str(label or "").split("#")[0].strip()


def main():
    pairs = []
    print("sampling %d x %.0fs ..." % (SAMPLES, INTERVAL))
    for i in range(SAMPLES):
        try:
            f = flow()
            m = memory()
            label = f.get("scene_name") or m.get("scene_label") or ""
            h = f.get("scene_hash") or ""
            pairs.append((prefix(label), h, label))
        except Exception as e:
            print("  sample %d failed: %s" % (i, e))
        if i < SAMPLES - 1:
            time.sleep(INTERVAL)

    if not pairs:
        print("no samples")
        return 1

    labels = Counter(p[0] for p in pairs)
    hashes = Counter(p[1] for p in pairs if p[1])
    print("\n=== samples: %d ===" % len(pairs))
    print("distinct label prefixes : %d  %s" % (len(labels), dict(labels)))
    print("distinct hashes         : %d  %s" % (len(hashes), dict(hashes)))

    # is the mapping 1:1 or many-to-many?
    label_to_hash = defaultdict(set)
    hash_to_label = defaultdict(set)
    for lab, h, _ in pairs:
        if h:
            label_to_hash[lab].add(h)
            hash_to_label[h].add(lab)
    multi_hash = {k: sorted(v) for k, v in label_to_hash.items() if len(v) > 1}
    multi_label = {k: sorted(v) for k, v in hash_to_label.items() if len(v) > 1}
    print("\nlabel -> multiple hashes : %s" % (multi_hash or "none"))
    print("hash  -> multiple labels : %s" % (multi_label or "none"))

    # is any prefix a composite that shares components with another?
    comps = defaultdict(set)
    for lab in labels:
        for c in lab.split("·"):
            comps[c].add(lab)
    shared = {c: sorted(v) for c, v in comps.items() if len(v) > 1}
    print("\ncomponents shared across prefixes (drift evidence): %s"
          % (shared or "none"))

    print("\n=== raw sample log ===")
    for lab, h, full in pairs:
        print("  %-22s hash=%-8s full=%r" % (lab, h, full))

    print("\n=== verdict ===")
    print("  label prefixes seen      : %d" % len(labels))
    print("  hashes seen              : %d" % len(hashes))
    if len(hashes) == 1 and hashes:
        print("  -> the HASH is stable within this window; label prefix is not")
    elif len(labels) == 1:
        print("  -> the LABEL is stable within this window")
    else:
        print("  -> BOTH drift within this window: neither single field is a "
              "sound binding key; bindings need the level identity")
    return 0


if __name__ == "__main__":
    sys.exit(main())
