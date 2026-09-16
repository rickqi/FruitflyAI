#!/usr/bin/env python3
"""t22 regression: trajectory 3D height visualisation.

Node exercises the real pure helpers (web/trajectory-height.js) with a mock
trajectory whose heights span 50-200 (gradient + vertical segment count);
Python asserts the trajectory.html wiring (vertex color attribute,
LineSegments, auto ground Y, recent_path yAt sampling).
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "web" / "trajectory.html"
UTILS = ROOT / "web" / "trajectory-height.js"


@pytest.mark.skipif(shutil.which("node") is None, reason="Node not installed")
def test_height_helpers_with_mock_50_200_trajectory():
    """Mock trajectory heights 50-200: gradient exists, vert count > 0."""
    result = subprocess.run(["node", "--input-type=module", "-e", """
import assert from 'node:assert/strict';
import {heightColor, verticalSegmentCount, autoGroundY} from './web/trajectory-height.js';
// mock trajectory: 400 points, height sweeping 50 -> 200 (with jitter)
const pts = Array.from({length: 400}, (_, i) => ({y: 50 + (i / 399) * 150 + (i % 7)}));
// 1) gradient: low -> blue-ish, high -> red-ish, monotonic red rise
const lo = heightColor(0), hi = heightColor(1), mid = heightColor(0.5);
assert.ok(lo[2] > lo[0], 'low point is blue-dominant');
assert.ok(hi[0] > hi[2], 'high point is red-dominant');
assert.ok(hi[0] > mid[0] && mid[0] > lo[0], 'red channel monotonic rising');
assert.ok(hi[2] < mid[2] && mid[2] < lo[2], 'blue channel monotonic falling');
// per-point colors across the mock differ end-to-end
const c0 = heightColor((pts[0].y - 50) / 150), cN = heightColor((pts[399].y - 50) / 150);
assert.notDeepEqual(c0.map(v => +v.toFixed(3)), cN.map(v => +v.toFixed(3)));
// 2) vertical reference lines: count > 0, exact step contract (step grows
//    with n so a full 6000-point buffer stays ~601 segments)
const seg = verticalSegmentCount(400);
assert.ok(seg > 0 && seg <= 400, seg);
assert.equal(verticalSegmentCount(0), 0);
assert.equal(verticalSegmentCount(1), 0);
assert.equal(verticalSegmentCount(6000), 300);   // step=20 → 300 drops
// 3) auto ground Y: first point wins, baseline 120 fallback
assert.equal(autoGroundY([{y: 57}]), 57);
assert.equal(autoGroundY([], 120), 120);
console.log('height helpers OK');
"""], capture_output=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr.decode()


def test_trajectory_html_wiring():
    src = HTML.read_text(encoding="utf-8")
    # 1) vertex colour attribute + vertexColors materials
    assert "pathGeo.setAttribute('color'" in src
    assert "LineBasicMaterial({vertexColors:true})" in src
    assert "PointsMaterial({vertexColors:true" in src
    assert "heightColor(" in src
    # 2) vertical reference LineSegments to the ground baseline
    assert "THREE.LineSegments" in src
    assert "GROUND_Y=120" in src
    assert "vertGeo.setDrawRange" in src
    # 3) grid rides auto-detected ground height (first point / baseline)
    assert "grid.position.y=autoGroundY(pts)" in src
    util = UTILS.read_text(encoding="utf-8")
    assert "baseline = 120" in util
    # 4) recent_path uses real sampled height instead of fixed y0+4
    assert "yAt(c.x,c.z)+4" in src
    assert "y0+4" not in src
    # diagnostics hook exposed
    assert "__heightState" in src
