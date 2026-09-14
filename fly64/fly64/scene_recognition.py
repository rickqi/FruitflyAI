"""SM64 scene recognition with profile-based level matching.

Provides a SceneRecognizer that scores current visual features (from the FlyModel)
against pre-defined SM64 level profiles using quantile matching. Returns the most
likely level name, confidence, and tags for the current scene.

Profiles use P05 / P50 / P95 quantile-based feature distributions to express
the expected range of each visual signal for a given SM64 level.
"""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from typing import Any

import numpy as np


# ---------------------------------------------------------------------------
# Quantile profile definition helpers
# ---------------------------------------------------------------------------

QuantileProfile = dict[str, dict[str, float]]
"""Per-level feature profile: feature_name → {"p05": float, "p50": float, "p95": float}"""

LevelProfile = dict[str, Any]
"""Full level entry: {"name": str, "tags": list[str], "features": QuantileProfile}"""


_EPS = 1e-8


def score_quantile_match(value: float, p05: float, p50: float, p95: float) -> float:
    """Score one feature value against its P05/P50/P95 profile.

    Returns a contribution score in [-2.0, +1.5]:
      +1.0 to +1.5  — value is within [P05, P95]; bonus for being close to P50.
      -0.5  — value is just outside one tail (gap < 0.1).
      -1.0  — moderate deviation.
      -2.0  — severe mismatch (gap > 0.3 from the nearest bound).

    The result is non-linear so a single out-of-range feature does not
    immediately tank the total score, while a severe mismatch still
    carries weight.
    """
    if p05 <= value <= p95:
        # Bonus for closeness to median: 0 when at edge, +0.5 when at P50
        p50_nearness = 1.0 - min(abs(value - p50) / max((p95 - p05) / 2, _EPS), 1.0)
        return 1.0 + 0.5 * p50_nearness

    if value < p05:
        gap = p05 - value
        spread = max(p50 - p05, _EPS)
        ratio = gap / spread
    else:  # value > p95
        gap = value - p95
        spread = max(p95 - p50, _EPS)
        ratio = gap / spread

    if ratio <= 0.5:
        return -0.5
    elif ratio <= 2.0:
        return -1.0
    else:
        return -2.0


def score_quantile_profile(features: dict[str, float],
                            profile: QuantileProfile,
                            weights: dict[str, float] | None = None) -> float:
    """Score a full feature dict against a quantile-based profile.

    Returns the weighted sum of per-feature quantile-match scores,
    normalised to [-1, +1] range.
    """
    total_weight = 0.0
    weighted_sum = 0.0

    for key, spec in profile.items():
        w = 1.0 if weights is None else weights.get(key, 1.0)
        total_weight += w
        if key in features:
            contrib = score_quantile_match(features[key],
                                           spec["p05"], spec["p50"], spec["p95"])
            weighted_sum += w * contrib
        else:
            weighted_sum += w * -1.0  # missing feature ← mild penalty

    if total_weight < _EPS:
        return 0.0
    return weighted_sum / total_weight


# ---------------------------------------------------------------------------
# SM64 Level Profiles — 14 major courses
# ---------------------------------------------------------------------------
# Each profile gives expected P05 / P50 / P95 ranges for visual features
# extracted by fly64's retina pipeline.  Features are in [0, 1] unless
# otherwise noted.

SM64_LEVEL_PROFILES: dict[str, LevelProfile] = {
    "bob_omb_battlefield": {
        "name": "炮弹战场",
        "tags": ["outdoor", "grass", "mountain", "enemies"],
        "features": {
            "sky_score":        {"p05": 0.55, "p50": 0.75, "p95": 0.95},
            "wall_score":       {"p05": 0.00, "p50": 0.10, "p95": 0.30},
            "ramp_score":       {"p05": 0.10, "p50": 0.30, "p95": 0.55},
            "opening_score":    {"p05": 0.10, "p50": 0.25, "p95": 0.45},
            "enclosure_score":  {"p05": 0.00, "p50": 0.05, "p95": 0.15},
            "ground_angle":     {"p05": 0.50, "p50": 0.75, "p95": 0.95},
            "sky_blue_index":   {"p05": 0.30, "p50": 0.50, "p95": 0.75},
            "danger_red_index": {"p05": 0.00, "p50": 0.04, "p95": 0.12},
            "saturation_mean":  {"p05": 0.15, "p50": 0.30, "p95": 0.50},
            "color_contrast":   {"p05": 0.10, "p50": 0.25, "p95": 0.45},
            "uv_appx_mean":     {"p05": 0.15, "p50": 0.30, "p95": 0.55},
            "blue_dom":         {"p05": 0.05, "p50": 0.15, "p95": 0.35},
            "on_energy":        {"p05": 0.03, "p50": 0.08, "p95": 0.18},
            "emd_on_total":     {"p05": 0.01, "p50": 0.04, "p95": 0.12},
        },
    },
    "whomps_fortress": {
        "name": "石块堡垒",
        "tags": ["outdoor", "stone", "fortress", "walls"],
        "features": {
            "sky_score":        {"p05": 0.25, "p50": 0.45, "p95": 0.65},
            "wall_score":       {"p05": 0.30, "p50": 0.50, "p95": 0.75},
            "ramp_score":       {"p05": 0.05, "p50": 0.15, "p95": 0.35},
            "opening_score":    {"p05": 0.10, "p50": 0.25, "p95": 0.45},
            "enclosure_score":  {"p05": 0.05, "p50": 0.15, "p95": 0.35},
            "ground_angle":     {"p05": 0.60, "p50": 0.80, "p95": 0.98},
            "sky_blue_index":   {"p05": 0.10, "p50": 0.25, "p95": 0.45},
            "danger_red_index": {"p05": 0.00, "p50": 0.02, "p95": 0.08},
            "saturation_mean":  {"p05": 0.10, "p50": 0.20, "p95": 0.35},
            "color_contrast":   {"p05": 0.08, "p50": 0.18, "p95": 0.35},
            "uv_appx_mean":     {"p05": 0.08, "p50": 0.18, "p95": 0.35},
            "blue_dom":         {"p05": 0.02, "p50": 0.08, "p95": 0.20},
            "on_energy":        {"p05": 0.02, "p50": 0.06, "p95": 0.15},
            "emd_on_total":     {"p05": 0.01, "p50": 0.03, "p95": 0.10},
        },
    },
    "jolly_roger_bay": {
        "name": "海盗船港湾",
        "tags": ["outdoor", "water", "beach", "ship"],
        "features": {
            "sky_score":        {"p05": 0.40, "p50": 0.60, "p95": 0.85},
            "wall_score":       {"p05": 0.00, "p50": 0.08, "p95": 0.25},
            "ramp_score":       {"p05": 0.05, "p50": 0.15, "p95": 0.35},
            "opening_score":    {"p05": 0.10, "p50": 0.25, "p95": 0.50},
            "enclosure_score":  {"p05": 0.00, "p50": 0.05, "p95": 0.15},
            "ground_angle":     {"p05": 0.60, "p50": 0.80, "p95": 1.00},
            "sky_blue_index":   {"p05": 0.50, "p50": 0.70, "p95": 0.90},
            "danger_red_index": {"p05": 0.00, "p50": 0.02, "p95": 0.08},
            "saturation_mean":  {"p05": 0.15, "p50": 0.30, "p95": 0.50},
            "color_contrast":   {"p05": 0.10, "p50": 0.25, "p95": 0.45},
            "uv_appx_mean":     {"p05": 0.35, "p50": 0.55, "p95": 0.80},
            "blue_dom":         {"p05": 0.25, "p50": 0.45, "p95": 0.70},
            "on_energy":        {"p05": 0.02, "p50": 0.06, "p95": 0.15},
            "emd_on_total":     {"p05": 0.01, "p50": 0.03, "p95": 0.10},
        },
    },
    "cool_cool_mountain": {
        "name": "冷冽雪山",
        "tags": ["outdoor", "snow", "mountain", "cold"],
        "features": {
            "sky_score":        {"p05": 0.50, "p50": 0.70, "p95": 0.90},
            "wall_score":       {"p05": 0.00, "p50": 0.08, "p95": 0.25},
            "ramp_score":       {"p05": 0.15, "p50": 0.35, "p95": 0.60},
            "opening_score":    {"p05": 0.10, "p50": 0.25, "p95": 0.45},
            "enclosure_score":  {"p05": 0.00, "p50": 0.03, "p95": 0.10},
            "ground_angle":     {"p05": 0.40, "p50": 0.65, "p95": 0.90},
            "sky_blue_index":   {"p05": 0.30, "p50": 0.55, "p95": 0.75},
            "danger_red_index": {"p05": 0.00, "p50": 0.01, "p95": 0.05},
            "saturation_mean":  {"p05": 0.00, "p50": 0.05, "p95": 0.15},
            "color_contrast":   {"p05": 0.05, "p50": 0.12, "p95": 0.25},
            "uv_appx_mean":     {"p05": 0.20, "p50": 0.40, "p95": 0.65},
            "blue_dom":         {"p05": 0.15, "p50": 0.35, "p95": 0.55},
            "on_energy":        {"p05": 0.02, "p50": 0.06, "p95": 0.14},
            "emd_on_total":     {"p05": 0.01, "p50": 0.03, "p95": 0.10},
        },
    },
    "big_boos_haunt": {
        "name": "幽灵公馆",
        "tags": ["indoor", "dark", "haunted", "mansion"],
        "features": {
            "sky_score":        {"p05": 0.00, "p50": 0.03, "p95": 0.10},
            "wall_score":       {"p05": 0.45, "p50": 0.65, "p95": 0.85},
            "ramp_score":       {"p05": 0.00, "p50": 0.05, "p95": 0.15},
            "opening_score":    {"p05": 0.05, "p50": 0.15, "p95": 0.35},
            "enclosure_score":  {"p05": 0.50, "p50": 0.70, "p95": 0.90},
            "ground_angle":     {"p05": 0.70, "p50": 0.85, "p95": 1.00},
            "sky_blue_index":   {"p05": 0.00, "p50": 0.02, "p95": 0.08},
            "danger_red_index": {"p05": 0.00, "p50": 0.03, "p95": 0.10},
            "saturation_mean":  {"p05": 0.05, "p50": 0.12, "p95": 0.25},
            "color_contrast":   {"p05": 0.05, "p50": 0.15, "p95": 0.30},
            "uv_appx_mean":     {"p05": 0.02, "p50": 0.08, "p95": 0.20},
            "blue_dom":         {"p05": 0.00, "p50": 0.02, "p95": 0.08},
            "on_energy":        {"p05": 0.01, "p50": 0.04, "p95": 0.12},
            "emd_on_total":     {"p05": 0.01, "p50": 0.03, "p95": 0.08},
        },
    },
    "hazy_maze_cave": {
        "name": "幽暗洞穴",
        "tags": ["underground", "cave", "dark", "water"],
        "features": {
            "sky_score":        {"p05": 0.00, "p50": 0.01, "p95": 0.05},
            "wall_score":       {"p05": 0.55, "p50": 0.75, "p95": 0.90},
            "ramp_score":       {"p05": 0.00, "p50": 0.05, "p95": 0.15},
            "opening_score":    {"p05": 0.10, "p50": 0.25, "p95": 0.50},
            "enclosure_score":  {"p05": 0.70, "p50": 0.85, "p95": 0.98},
            "ground_angle":     {"p05": 0.20, "p50": 0.45, "p95": 0.70},
            "sky_blue_index":   {"p05": 0.00, "p50": 0.01, "p95": 0.05},
            "danger_red_index": {"p05": 0.00, "p50": 0.01, "p95": 0.05},
            "saturation_mean":  {"p05": 0.05, "p50": 0.12, "p95": 0.25},
            "color_contrast":   {"p05": 0.03, "p50": 0.10, "p95": 0.22},
            "uv_appx_mean":     {"p05": 0.02, "p50": 0.06, "p95": 0.18},
            "blue_dom":         {"p05": 0.00, "p50": 0.02, "p95": 0.08},
            "on_energy":        {"p05": 0.01, "p50": 0.03, "p95": 0.10},
            "emd_on_total":     {"p05": 0.00, "p50": 0.02, "p95": 0.06},
        },
    },
    "lethal_lava_land": {
        "name": "致命熔岩地",
        "tags": ["outdoor", "lava", "hell", "danger"],
        "features": {
            "sky_score":        {"p05": 0.25, "p50": 0.45, "p95": 0.65},
            "wall_score":       {"p05": 0.00, "p50": 0.08, "p95": 0.25},
            "ramp_score":       {"p05": 0.05, "p50": 0.15, "p95": 0.35},
            "opening_score":    {"p05": 0.05, "p50": 0.15, "p95": 0.35},
            "enclosure_score":  {"p05": 0.00, "p50": 0.05, "p95": 0.15},
            "ground_angle":     {"p05": 0.55, "p50": 0.75, "p95": 0.90},
            "sky_blue_index":   {"p05": 0.15, "p50": 0.30, "p95": 0.50},
            "danger_red_index": {"p05": 0.55, "p50": 0.75, "p95": 0.92},
            "saturation_mean":  {"p05": 0.40, "p50": 0.60, "p95": 0.80},
            "color_contrast":   {"p05": 0.15, "p50": 0.30, "p95": 0.55},
            "uv_appx_mean":     {"p05": 0.08, "p50": 0.18, "p95": 0.35},
            "blue_dom":         {"p05": 0.02, "p50": 0.06, "p95": 0.18},
            "on_energy":        {"p05": 0.02, "p50": 0.06, "p95": 0.15},
            "emd_on_total":     {"p05": 0.01, "p50": 0.03, "p95": 0.10},
        },
    },
    "dire_dire_docks": {
        "name": "深水船坞",
        "tags": ["indoor", "water", "docks", "dark"],
        "features": {
            "sky_score":        {"p05": 0.00, "p50": 0.03, "p95": 0.10},
            "wall_score":       {"p05": 0.25, "p50": 0.45, "p95": 0.65},
            "ramp_score":       {"p05": 0.00, "p50": 0.05, "p95": 0.15},
            "opening_score":    {"p05": 0.10, "p50": 0.25, "p95": 0.45},
            "enclosure_score":  {"p05": 0.40, "p50": 0.60, "p95": 0.80},
            "ground_angle":     {"p05": 0.60, "p50": 0.80, "p95": 1.00},
            "sky_blue_index":   {"p05": 0.00, "p50": 0.02, "p95": 0.08},
            "danger_red_index": {"p05": 0.00, "p50": 0.01, "p95": 0.04},
            "saturation_mean":  {"p05": 0.10, "p50": 0.20, "p95": 0.35},
            "color_contrast":   {"p05": 0.05, "p50": 0.15, "p95": 0.28},
            "uv_appx_mean":     {"p05": 0.30, "p50": 0.50, "p95": 0.72},
            "blue_dom":         {"p05": 0.15, "p50": 0.35, "p95": 0.55},
            "on_energy":        {"p05": 0.01, "p50": 0.04, "p95": 0.10},
            "emd_on_total":     {"p05": 0.00, "p50": 0.02, "p95": 0.06},
        },
    },
    "snowmans_land": {
        "name": "雪人领地",
        "tags": ["outdoor", "snow", "ice", "mountain"],
        "features": {
            "sky_score":        {"p05": 0.50, "p50": 0.70, "p95": 0.92},
            "wall_score":       {"p05": 0.00, "p50": 0.06, "p95": 0.20},
            "ramp_score":       {"p05": 0.10, "p50": 0.28, "p95": 0.55},
            "opening_score":    {"p05": 0.10, "p50": 0.25, "p95": 0.45},
            "enclosure_score":  {"p05": 0.00, "p50": 0.03, "p95": 0.10},
            "ground_angle":     {"p05": 0.40, "p50": 0.65, "p95": 0.88},
            "sky_blue_index":   {"p05": 0.20, "p50": 0.38, "p95": 0.60},
            "danger_red_index": {"p05": 0.00, "p50": 0.01, "p95": 0.04},
            "saturation_mean":  {"p05": 0.00, "p50": 0.04, "p95": 0.12},
            "color_contrast":   {"p05": 0.04, "p50": 0.10, "p95": 0.22},
            "uv_appx_mean":     {"p05": 0.15, "p50": 0.30, "p95": 0.52},
            "blue_dom":         {"p05": 0.05, "p50": 0.15, "p95": 0.32},
            "on_energy":        {"p05": 0.02, "p50": 0.05, "p95": 0.14},
            "emd_on_total":     {"p05": 0.01, "p50": 0.03, "p95": 0.10},
        },
    },
    "wet_dry_world": {
        "name": "干湿世界",
        "tags": ["outdoor", "water", "pipes", "platforms"],
        "features": {
            "sky_score":        {"p05": 0.35, "p50": 0.55, "p95": 0.75},
            "wall_score":       {"p05": 0.05, "p50": 0.15, "p95": 0.35},
            "ramp_score":       {"p05": 0.05, "p50": 0.15, "p95": 0.30},
            "opening_score":    {"p05": 0.10, "p50": 0.25, "p95": 0.45},
            "enclosure_score":  {"p05": 0.00, "p50": 0.05, "p95": 0.15},
            "ground_angle":     {"p05": 0.55, "p50": 0.75, "p95": 0.95},
            "sky_blue_index":   {"p05": 0.20, "p50": 0.40, "p95": 0.60},
            "danger_red_index": {"p05": 0.00, "p50": 0.02, "p95": 0.08},
            "saturation_mean":  {"p05": 0.15, "p50": 0.28, "p95": 0.45},
            "color_contrast":   {"p05": 0.10, "p50": 0.22, "p95": 0.40},
            "uv_appx_mean":     {"p05": 0.20, "p50": 0.40, "p95": 0.60},
            "blue_dom":         {"p05": 0.08, "p50": 0.18, "p95": 0.38},
            "on_energy":        {"p05": 0.02, "p50": 0.06, "p95": 0.14},
            "emd_on_total":     {"p05": 0.01, "p50": 0.03, "p95": 0.10},
        },
    },
    "tall_tall_mountain": {
        "name": "高高山顶",
        "tags": ["outdoor", "mountain", "grass", "sky"],
        "features": {
            "sky_score":        {"p05": 0.75, "p50": 0.88, "p95": 0.98},
            "wall_score":       {"p05": 0.00, "p50": 0.05, "p95": 0.18},
            "ramp_score":       {"p05": 0.10, "p50": 0.25, "p95": 0.50},
            "opening_score":    {"p05": 0.08, "p50": 0.20, "p95": 0.40},
            "enclosure_score":  {"p05": 0.00, "p50": 0.02, "p95": 0.08},
            "ground_angle":     {"p05": 0.45, "p50": 0.70, "p95": 0.92},
            "sky_blue_index":   {"p05": 0.40, "p50": 0.60, "p95": 0.85},
            "danger_red_index": {"p05": 0.00, "p50": 0.02, "p95": 0.06},
            "saturation_mean":  {"p05": 0.12, "p50": 0.25, "p95": 0.42},
            "color_contrast":   {"p05": 0.08, "p50": 0.20, "p95": 0.40},
            "uv_appx_mean":     {"p05": 0.25, "p50": 0.45, "p95": 0.70},
            "blue_dom":         {"p05": 0.08, "p50": 0.20, "p95": 0.40},
            "on_energy":        {"p05": 0.02, "p50": 0.06, "p95": 0.15},
            "emd_on_total":     {"p05": 0.01, "p50": 0.03, "p95": 0.10},
        },
    },
    "tiny_huge_island": {
        "name": "大巨岛",
        "tags": ["outdoor", "beach", "island", "cliff"],
        "features": {
            "sky_score":        {"p05": 0.50, "p50": 0.70, "p95": 0.90},
            "wall_score":       {"p05": 0.00, "p50": 0.08, "p95": 0.25},
            "ramp_score":       {"p05": 0.08, "p50": 0.20, "p95": 0.40},
            "opening_score":    {"p05": 0.10, "p50": 0.25, "p95": 0.45},
            "enclosure_score":  {"p05": 0.00, "p50": 0.03, "p95": 0.10},
            "ground_angle":     {"p05": 0.40, "p50": 0.65, "p95": 0.88},
            "sky_blue_index":   {"p05": 0.35, "p50": 0.55, "p95": 0.80},
            "danger_red_index": {"p05": 0.00, "p50": 0.02, "p95": 0.08},
            "saturation_mean":  {"p05": 0.15, "p50": 0.30, "p95": 0.50},
            "color_contrast":   {"p05": 0.10, "p50": 0.25, "p95": 0.45},
            "uv_appx_mean":     {"p05": 0.20, "p50": 0.40, "p95": 0.62},
            "blue_dom":         {"p05": 0.10, "p50": 0.25, "p95": 0.45},
            "on_energy":        {"p05": 0.02, "p50": 0.06, "p95": 0.14},
            "emd_on_total":     {"p05": 0.01, "p50": 0.03, "p95": 0.10},
        },
    },
    "tick_tock_clock": {
        "name": "滴答时钟",
        "tags": ["indoor", "clock", "gears", "mechanical"],
        "features": {
            "sky_score":        {"p05": 0.00, "p50": 0.02, "p95": 0.08},
            "wall_score":       {"p05": 0.25, "p50": 0.45, "p95": 0.65},
            "ramp_score":       {"p05": 0.00, "p50": 0.05, "p95": 0.15},
            "opening_score":    {"p05": 0.05, "p50": 0.15, "p95": 0.35},
            "enclosure_score":  {"p05": 0.50, "p50": 0.70, "p95": 0.88},
            "ground_angle":     {"p05": 0.65, "p50": 0.82, "p95": 0.98},
            "sky_blue_index":   {"p05": 0.00, "p50": 0.01, "p95": 0.05},
            "danger_red_index": {"p05": 0.00, "p50": 0.02, "p95": 0.08},
            "saturation_mean":  {"p05": 0.15, "p50": 0.30, "p95": 0.55},
            "color_contrast":   {"p05": 0.20, "p50": 0.40, "p95": 0.65},
            "uv_appx_mean":     {"p05": 0.05, "p50": 0.15, "p95": 0.30},
            "blue_dom":         {"p05": 0.00, "p50": 0.02, "p95": 0.06},
            "on_energy":        {"p05": 0.01, "p50": 0.04, "p95": 0.12},
            "emd_on_total":     {"p05": 0.01, "p50": 0.03, "p95": 0.08},
        },
    },
    "rainbow_ride": {
        "name": "彩虹天路",
        "tags": ["outdoor", "sky", "platforms", "colorful"],
        "features": {
            "sky_score":        {"p05": 0.85, "p50": 0.95, "p95": 1.00},
            "wall_score":       {"p05": 0.00, "p50": 0.03, "p95": 0.12},
            "ramp_score":       {"p05": 0.02, "p50": 0.08, "p95": 0.20},
            "opening_score":    {"p05": 0.05, "p50": 0.15, "p95": 0.30},
            "enclosure_score":  {"p05": 0.00, "p50": 0.01, "p95": 0.05},
            "ground_angle":     {"p05": 0.35, "p50": 0.55, "p95": 0.80},
            "sky_blue_index":   {"p05": 0.55, "p50": 0.75, "p95": 0.95},
            "danger_red_index": {"p05": 0.00, "p50": 0.03, "p95": 0.12},
            "saturation_mean":  {"p05": 0.30, "p50": 0.50, "p95": 0.70},
            "color_contrast":   {"p05": 0.35, "p50": 0.55, "p95": 0.78},
            "uv_appx_mean":     {"p05": 0.40, "p50": 0.60, "p95": 0.85},
            "blue_dom":         {"p05": 0.25, "p50": 0.45, "p95": 0.70},
            "on_energy":        {"p05": 0.02, "p50": 0.06, "p95": 0.16},
            "emd_on_total":     {"p05": 0.01, "p50": 0.03, "p95": 0.10},
        },
    },
}


# ---------------------------------------------------------------------------
# Color-based disambiguation profiles (P1a color opponent signals)
# ---------------------------------------------------------------------------
# These profiles use opponent-color and hue features to disambiguate levels
# that share similar spatial structure but differ in colour palette
# (e.g. Cool Cool Mountain vs Snowman's Land).

SM64_COLOR_PROFILES: dict[str, QuantileProfile] = {
    "bob_omb_battlefield": {
        "rg_opponent_mean": {"p05": 0.00, "p50": 0.05, "p95": 0.15},
        "by_opponent_mean": {"p05": 0.05, "p50": 0.15, "p95": 0.30},
        "uv_appx_mean":     {"p05": 0.15, "p50": 0.30, "p95": 0.55},
        "saturation_mean":  {"p05": 0.15, "p50": 0.30, "p95": 0.50},
    },
    "whomps_fortress": {
        "rg_opponent_mean": {"p05": 0.02, "p50": 0.08, "p95": 0.18},
        "by_opponent_mean": {"p05": 0.02, "p50": 0.08, "p95": 0.20},
        "uv_appx_mean":     {"p05": 0.08, "p50": 0.18, "p95": 0.35},
        "saturation_mean":  {"p05": 0.10, "p50": 0.20, "p95": 0.35},
    },
    "jolly_roger_bay": {
        "rg_opponent_mean": {"p05": 0.00, "p50": 0.03, "p95": 0.10},
        "by_opponent_mean": {"p05": 0.20, "p50": 0.40, "p95": 0.65},
        "uv_appx_mean":     {"p05": 0.35, "p50": 0.55, "p95": 0.80},
        "saturation_mean":  {"p05": 0.15, "p50": 0.30, "p95": 0.50},
    },
    "cool_cool_mountain": {
        "rg_opponent_mean": {"p05": 0.00, "p50": 0.02, "p95": 0.08},
        "by_opponent_mean": {"p05": 0.20, "p50": 0.40, "p95": 0.60},
        "uv_appx_mean":     {"p05": 0.20, "p50": 0.40, "p95": 0.65},
        "saturation_mean":  {"p05": 0.00, "p50": 0.05, "p95": 0.15},
    },
    "big_boos_haunt": {
        "rg_opponent_mean": {"p05": 0.00, "p50": 0.02, "p95": 0.08},
        "by_opponent_mean": {"p05": 0.00, "p50": 0.02, "p95": 0.08},
        "uv_appx_mean":     {"p05": 0.02, "p50": 0.08, "p95": 0.20},
        "saturation_mean":  {"p05": 0.05, "p50": 0.12, "p95": 0.25},
    },
    "hazy_maze_cave": {
        "rg_opponent_mean": {"p05": 0.00, "p50": 0.02, "p95": 0.08},
        "by_opponent_mean": {"p05": 0.00, "p50": 0.02, "p95": 0.06},
        "uv_appx_mean":     {"p05": 0.02, "p50": 0.06, "p95": 0.18},
        "saturation_mean":  {"p05": 0.05, "p50": 0.12, "p95": 0.25},
    },
    "lethal_lava_land": {
        "rg_opponent_mean": {"p05": 0.25, "p50": 0.45, "p95": 0.70},
        "by_opponent_mean": {"p05": 0.00, "p50": 0.02, "p95": 0.08},
        "uv_appx_mean":     {"p05": 0.08, "p50": 0.18, "p95": 0.35},
        "saturation_mean":  {"p05": 0.40, "p50": 0.60, "p95": 0.80},
    },
    "dire_dire_docks": {
        "rg_opponent_mean": {"p05": 0.00, "p50": 0.02, "p95": 0.08},
        "by_opponent_mean": {"p05": 0.15, "p50": 0.30, "p95": 0.50},
        "uv_appx_mean":     {"p05": 0.30, "p50": 0.50, "p95": 0.72},
        "saturation_mean":  {"p05": 0.10, "p50": 0.20, "p95": 0.35},
    },
    "snowmans_land": {
        "rg_opponent_mean": {"p05": 0.00, "p50": 0.01, "p95": 0.04},
        "by_opponent_mean": {"p05": 0.05, "p50": 0.15, "p95": 0.30},
        "uv_appx_mean":     {"p05": 0.20, "p50": 0.38, "p95": 0.60},
        "saturation_mean":  {"p05": 0.00, "p50": 0.05, "p95": 0.15},
    },
    "wet_dry_world": {
        "rg_opponent_mean": {"p05": 0.00, "p50": 0.04, "p95": 0.12},
        "by_opponent_mean": {"p05": 0.05, "p50": 0.15, "p95": 0.32},
        "uv_appx_mean":     {"p05": 0.20, "p50": 0.40, "p95": 0.60},
        "saturation_mean":  {"p05": 0.15, "p50": 0.28, "p95": 0.45},
    },
    "tall_tall_mountain": {
        "rg_opponent_mean": {"p05": 0.00, "p50": 0.03, "p95": 0.10},
        "by_opponent_mean": {"p05": 0.08, "p50": 0.20, "p95": 0.38},
        "uv_appx_mean":     {"p05": 0.25, "p50": 0.45, "p95": 0.70},
        "saturation_mean":  {"p05": 0.12, "p50": 0.25, "p95": 0.42},
    },
    "tiny_huge_island": {
        "rg_opponent_mean": {"p05": 0.00, "p50": 0.03, "p95": 0.12},
        "by_opponent_mean": {"p05": 0.08, "p50": 0.20, "p95": 0.40},
        "uv_appx_mean":     {"p05": 0.20, "p50": 0.40, "p95": 0.62},
        "saturation_mean":  {"p05": 0.15, "p50": 0.30, "p95": 0.50},
    },
    "tick_tock_clock": {
        "rg_opponent_mean": {"p05": 0.00, "p50": 0.03, "p95": 0.10},
        "by_opponent_mean": {"p05": 0.00, "p50": 0.02, "p95": 0.08},
        "uv_appx_mean":     {"p05": 0.05, "p50": 0.15, "p95": 0.30},
        "saturation_mean":  {"p05": 0.15, "p50": 0.30, "p95": 0.55},
    },
    "rainbow_ride": {
        "rg_opponent_mean": {"p05": 0.05, "p50": 0.15, "p95": 0.30},
        "by_opponent_mean": {"p05": 0.20, "p50": 0.40, "p95": 0.60},
        "uv_appx_mean":     {"p05": 0.40, "p50": 0.60, "p95": 0.85},
        "saturation_mean":  {"p05": 0.30, "p50": 0.50, "p95": 0.70},
    },
}


# ---------------------------------------------------------------------------
# Motion-based disambiguation profiles (P1b EMD / HRC signals)
# ---------------------------------------------------------------------------

SM64_MOTION_PROFILES: dict[str, QuantileProfile] = {
    "bob_omb_battlefield": {
        "emd_on_total":     {"p05": 0.01, "p50": 0.04, "p95": 0.12},
        "emd_off_total":    {"p05": 0.01, "p50": 0.03, "p95": 0.10},
        "emd_horizontal":   {"p05": 0.02, "p50": 0.06, "p95": 0.18},
        "emd_vertical":     {"p05": 0.01, "p50": 0.04, "p95": 0.12},
    },
    "whomps_fortress": {
        "emd_on_total":     {"p05": 0.01, "p50": 0.03, "p95": 0.10},
        "emd_off_total":    {"p05": 0.01, "p50": 0.02, "p95": 0.08},
        "emd_horizontal":   {"p05": 0.01, "p50": 0.04, "p95": 0.14},
        "emd_vertical":     {"p05": 0.01, "p50": 0.03, "p95": 0.10},
    },
    "jolly_roger_bay": {
        "emd_on_total":     {"p05": 0.01, "p50": 0.03, "p95": 0.10},
        "emd_off_total":    {"p05": 0.01, "p50": 0.03, "p95": 0.08},
        "emd_horizontal":   {"p05": 0.01, "p50": 0.04, "p95": 0.14},
        "emd_vertical":     {"p05": 0.01, "p50": 0.03, "p95": 0.10},
    },
    "cool_cool_mountain": {
        "emd_on_total":     {"p05": 0.01, "p50": 0.03, "p95": 0.10},
        "emd_off_total":    {"p05": 0.01, "p50": 0.03, "p95": 0.08},
        "emd_horizontal":   {"p05": 0.01, "p50": 0.05, "p95": 0.15},
        "emd_vertical":     {"p05": 0.01, "p50": 0.03, "p95": 0.10},
    },
    "big_boos_haunt": {
        "emd_on_total":     {"p05": 0.01, "p50": 0.03, "p95": 0.08},
        "emd_off_total":    {"p05": 0.00, "p50": 0.02, "p95": 0.06},
        "emd_horizontal":   {"p05": 0.01, "p50": 0.03, "p95": 0.10},
        "emd_vertical":     {"p05": 0.00, "p50": 0.02, "p95": 0.06},
    },
    "hazy_maze_cave": {
        "emd_on_total":     {"p05": 0.00, "p50": 0.02, "p95": 0.06},
        "emd_off_total":    {"p05": 0.00, "p50": 0.01, "p95": 0.05},
        "emd_horizontal":   {"p05": 0.00, "p50": 0.02, "p95": 0.08},
        "emd_vertical":     {"p05": 0.00, "p50": 0.01, "p95": 0.05},
    },
    "lethal_lava_land": {
        "emd_on_total":     {"p05": 0.01, "p50": 0.03, "p95": 0.10},
        "emd_off_total":    {"p05": 0.01, "p50": 0.03, "p95": 0.08},
        "emd_horizontal":   {"p05": 0.01, "p50": 0.04, "p95": 0.14},
        "emd_vertical":     {"p05": 0.01, "p50": 0.03, "p95": 0.10},
    },
    "dire_dire_docks": {
        "emd_on_total":     {"p05": 0.00, "p50": 0.02, "p95": 0.06},
        "emd_off_total":    {"p05": 0.00, "p50": 0.01, "p95": 0.05},
        "emd_horizontal":   {"p05": 0.00, "p50": 0.02, "p95": 0.08},
        "emd_vertical":     {"p05": 0.00, "p50": 0.01, "p95": 0.05},
    },
    "snowmans_land": {
        "emd_on_total":     {"p05": 0.01, "p50": 0.03, "p95": 0.10},
        "emd_off_total":    {"p05": 0.01, "p50": 0.03, "p95": 0.08},
        "emd_horizontal":   {"p05": 0.01, "p50": 0.04, "p95": 0.14},
        "emd_vertical":     {"p05": 0.01, "p50": 0.03, "p95": 0.10},
    },
    "wet_dry_world": {
        "emd_on_total":     {"p05": 0.01, "p50": 0.03, "p95": 0.10},
        "emd_off_total":    {"p05": 0.01, "p50": 0.03, "p95": 0.08},
        "emd_horizontal":   {"p05": 0.01, "p50": 0.04, "p95": 0.14},
        "emd_vertical":     {"p05": 0.01, "p50": 0.03, "p95": 0.10},
    },
    "tall_tall_mountain": {
        "emd_on_total":     {"p05": 0.01, "p50": 0.03, "p95": 0.10},
        "emd_off_total":    {"p05": 0.01, "p50": 0.03, "p95": 0.08},
        "emd_horizontal":   {"p05": 0.01, "p50": 0.04, "p95": 0.15},
        "emd_vertical":     {"p05": 0.01, "p50": 0.03, "p95": 0.10},
    },
    "tiny_huge_island": {
        "emd_on_total":     {"p05": 0.01, "p50": 0.03, "p95": 0.10},
        "emd_off_total":    {"p05": 0.01, "p50": 0.03, "p95": 0.08},
        "emd_horizontal":   {"p05": 0.01, "p50": 0.04, "p95": 0.14},
        "emd_vertical":     {"p05": 0.01, "p50": 0.03, "p95": 0.10},
    },
    "tick_tock_clock": {
        "emd_on_total":     {"p05": 0.01, "p50": 0.03, "p95": 0.08},
        "emd_off_total":    {"p05": 0.00, "p50": 0.02, "p95": 0.06},
        "emd_horizontal":   {"p05": 0.01, "p50": 0.03, "p95": 0.10},
        "emd_vertical":     {"p05": 0.00, "p50": 0.02, "p95": 0.06},
    },
    "rainbow_ride": {
        "emd_on_total":     {"p05": 0.01, "p50": 0.03, "p95": 0.10},
        "emd_off_total":    {"p05": 0.01, "p50": 0.03, "p95": 0.08},
        "emd_horizontal":   {"p05": 0.01, "p50": 0.04, "p95": 0.14},
        "emd_vertical":     {"p05": 0.01, "p50": 0.03, "p95": 0.10},
    },
}


# ---------------------------------------------------------------------------
# SceneRecognizer — profile-based scene identification
# ---------------------------------------------------------------------------

_SCENE_FEATURE_KEYS = [
    # Spatial / terrain scores
    "sky_score", "wall_score", "ramp_score", "opening_score",
    "enclosure_score", "ground_angle",
    # Color features
    "sky_blue_index", "danger_red_index",
    "saturation_mean", "color_contrast",
    "uv_appx_mean", "blue_dom",
    # Temporal / motion
    "on_energy", "emd_on_total",
]


class SceneRecognizer:
    """Profile-based SM64 scene recognition with persistent custom labels.

    Maintains a database of pre-defined SM64 level profiles and scores
    incoming feature vectors against them using quantile (P05/P50/P95)
    matching.  Supports persistent custom label assignment for newly
    encountered scene hashes.

    Attributes
    ----------
    profiles : dict
        Built-in SM64 level profiles (14 main courses).
    color_profiles : dict
        Color-only profiles for disambiguation.
    custom_labels : dict[str, dict]
        Persisted custom labels keyed by scene-hash prefix.
    _history : deque
        Rolling feature history (maxlen=300) for profile adaptation.
    _current_level : str | None
        Most recently recognised level ID.
    _current_confidence : float
        Confidence of the most recent recognition.
    _smooth_level : str | None
        EMA-smoothed level prediction (frame-to-frame stability).
    """

    def __init__(self, profiles_path: str | Path | None = None):
        self.profiles: dict[str, LevelProfile] = SM64_LEVEL_PROFILES
        self.color_profiles: dict[str, QuantileProfile] = SM64_COLOR_PROFILES
        self.motion_profiles: dict[str, QuantileProfile] = SM64_MOTION_PROFILES
        self.custom_labels: dict[str, dict] = {}
        self._history: deque[dict[str, float]] = deque(maxlen=300)
        self._current_level: str | None = None
        self._current_confidence: float = 0.0
        self._smooth_level: str | None = None
        self._smooth_alpha: float = 0.15  # EMA smoothing factor
        # EVO R16: online profile calibration + unknown-scene accounting
        self.adapt_enabled: bool = True
        self.adapt_lr: float = 0.01       # P50 drift rate toward observation
        self.unknown_scenes: dict[str, int] = {}   # scene_hash → tick count

        if profiles_path is not None:
            self.load(profiles_path)

    # ── Feature extraction ────────────────────────────────────────────

    @staticmethod
    def extract_features(model) -> dict[str, float]:
        """Extract a standardised feature dict from the model's current state.

        Collects all feature keys used in profile matching from the model's
        attributes (set during encode_retina / compute_flow).
        """
        features: dict[str, float] = {}
        for key in _SCENE_FEATURE_KEYS:
            features[key] = float(getattr(model, key, 0.0))

        # Also collect multi-channel raw means (P1a) when available
        for ck in ("rg_opponent_mean", "by_opponent_mean"):
            features[ck] = float(getattr(model, ck, 0.0))

        # Collect EMD compound signals (P1b)
        for mk in ("emd_horizontal", "emd_vertical",
                    "emd_on_total", "emd_off_total"):
            features[mk] = float(getattr(model, mk, 0.0))

        # Small target signals (P2)
        features["target_count"] = float(getattr(model, "target_count", 0))
        features["fg_fraction"] = float(getattr(model, "fg_fraction", 0.0))

        return features

    # ── Profile scoring ───────────────────────────────────────────────

    def score_profiles(self, features: dict[str, float],
                       top_k: int = 3) -> list[tuple[str, str, float, list[str]]]:
        """Score all known profiles against the current feature vector.

        Returns the top-k matches sorted by descending score, as
        ``(profile_id, level_name, score, tags)`` tuples.
        """
        scores: list[tuple[str, float]] = []

        for prof_id, prof in self.profiles.items():
            s = score_quantile_profile(features, prof["features"])
            # Boost by colour profile agreement when colour features are
            # available and a colour profile exists for this level.
            if prof_id in self.color_profiles:
                col_features = {k: features.get(k, 0.0)
                                for k in self.color_profiles[prof_id]}
                if any(v > 0.01 for v in col_features.values()):
                    col_score = score_quantile_profile(
                        features, self.color_profiles[prof_id])
                    s = 0.6 * s + 0.4 * col_score
            scores.append((prof_id, s))

        # Sort descending
        scores.sort(key=lambda x: x[1], reverse=True)

        result: list[tuple[str, str, float, list[str]]] = []
        for prof_id, score in scores[:top_k]:
            prof = self.profiles[prof_id]
            result.append((prof_id, prof["name"], score, prof["tags"]))
        return result

    # ── Main recognition entry ────────────────────────────────────────

    def recognize(self, model,
                  min_confidence: float = 0.20,
                  min_margin: float = 0.04) -> tuple[str, float, list[str]]:
        """Return the most likely SM64 level for the model's current view.

        Parameters
        ----------
        model : FlyModel
            The current model instance (its attributes hold flow signals).
        min_confidence : float
            Minimum confidence to accept a profile match.
        min_margin : float
            Minimum score gap between 1st and 2nd place to accept.

        Returns
        -------
        level_id : str
            Profile ID (empty string if nothing matches).
        confidence : float
            Normalised confidence score in [0, 1].
        tags : list[str]
            Level tags (empty if no match).
        """
        features = self.extract_features(model)
        self._history.append(features)

        scored = self.score_profiles(features, top_k=3)
        if not scored:
            self._current_level = None
            self._current_confidence = 0.0
            return ("", 0.0, [])

        best_id, best_name, best_score, best_tags = scored[0]
        margin = best_score - (scored[1][2] if len(scored) > 1 else -2.0)

        # Normalise score from [-1, +1] to [0, 1] confidence
        confidence = max(0.0, min(1.0, (best_score + 1.0) / 2.0))

        if best_score >= -0.2 and confidence >= min_confidence and margin >= min_margin:
            self._current_level = best_id
            self._current_confidence = confidence
            # EMA smoothing
            if self._smooth_level is None:
                self._smooth_level = best_id
            else:
                # Only update EMA when confidence is reasonable
                if confidence > 0.35:
                    self._smooth_level = best_id
            # EVO R16 · online profile calibration: drift the recognised
            # level's feature P50s a hair toward the observation (slow EMA)
            # so the profiles track real SM64 rendering over time.
            if self.adapt_enabled and confidence >= 0.6:
                self._adapt_profile(best_id, features)
            return (best_id, confidence, best_tags)
        else:
            self._current_level = None
            self._current_confidence = 0.0
            return ("", 0.0, [])

    def _adapt_profile(self, level_id: str,
                       features: dict[str, float]) -> None:
        """Nudge the matched profile's P50s toward the observation (η=0.01).

        Long-run effect: hand-tuned profiles converge to the true SM64
        rendering statistics without losing their P05/P95 guard bands.
        """
        prof = self.profiles.get(level_id)
        if prof is None:
            return
        for key, spec in prof["features"].items():
            obs = features.get(key)
            if obs is None:
                continue
            spec["p50"] = spec["p50"] * (1.0 - self.adapt_lr) + obs * self.adapt_lr
            # keep the guard bands centred on the drifting P50
            half = (spec["p95"] - spec["p05"]) / 2.0
            spec["p05"] = spec["p50"] - half
            spec["p95"] = spec["p50"] + half

    def note_unknown_scene(self, scene_hash: str) -> None:
        """Account for a scene hash that matched no profile (C3 telemetry)."""
        if scene_hash:
            self.unknown_scenes[scene_hash] = self.unknown_scenes.get(scene_hash, 0) + 1

    # ── Custom label management ───────────────────────────────────────

    def add_label(self, scene_hash: str, label: str,
                  tags: list[str] | None = None) -> None:
        """Persist a human-provided label for a scene hash prefix.

        Parameters
        ----------
        scene_hash : str
            The 4–12 character scene identifier (from memory_ctrl.scene_id).
        label : str
            Human-readable label (e.g. "秘密台阶").
        tags : list[str]
            Optional semantic tags.
        """
        entry = self.custom_labels.get(scene_hash, {})
        entry["label"] = label
        if tags is not None:
            entry["tags"] = tags
        self.custom_labels[scene_hash] = entry

    def get_label(self, scene_hash: str) -> str | None:
        """Return the custom label for *scene_hash*, or None."""
        entry = self.custom_labels.get(scene_hash)
        return entry.get("label") if entry else None

    # ── Persistence ───────────────────────────────────────────────────

    def save(self, path: str | Path) -> None:
        """Save custom labels and current state to JSON."""
        data = {
            "custom_labels": self.custom_labels,
            "current_level": self._current_level,
            "smooth_level": self._smooth_level,
        }
        Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def load(self, path: str | Path) -> None:
        """Load custom labels and state from JSON."""
        try:
            data = json.loads(Path(path).read_text())
            self.custom_labels = data.get("custom_labels", {})
            self._current_level = data.get("current_level")
            self._smooth_level = data.get("smooth_level")
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def reset(self) -> None:
        """Reset recognition state (not custom labels)."""
        self._history.clear()
        self._current_level = None
        self._current_confidence = 0.0
        self._smooth_level = None

    # ── Properties ────────────────────────────────────────────────────

    @property
    def current_level(self) -> str | None:
        return self._current_level

    @property
    def current_confidence(self) -> float:
        return self._current_confidence

    @property
    def smooth_level(self) -> str | None:
        return self._smooth_level