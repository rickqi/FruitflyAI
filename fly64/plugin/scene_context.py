#!/usr/bin/env python3
"""Scene context aggregator for what_i_see protocol (t21+ / Brain 2.14.x).

Consumes dashboard /flow.json and /memory.json endpoints and assembles a
structured ``SceneContext`` dataclass that represents what the fly's visual
system actually perceives — terrain classification, optic flow, detected
targets, navigation state, plasticity metrics — plus auto-generated scene
tags for the instructor-layer LLM prompt.

Architecture
------------
This module lives in the plugin layer (coach/LLM side).  It reads existing
dashboard JSON endpoints and never touches the brain model, retina, or
connectome directly.  The principle of "语义不下沉" (semantics do not
descend) is maintained: scene tags are consumed by the LLM coach, never
injected into ``active_strategy.json`` for brain hot-reload.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional


# ── scene tag generation thresholds ─────────────────────────────────────
TAG_RULES: list[tuple[str, str, float | bool, str]] = [
    # (tag_label, flow_json_key, min_threshold, comparator)
    # comparator: "gte" = >= threshold, "lte" = <= threshold, "eq" = equal
    ("室内场景", "enclosure_score", 0.65, "gte"),
    ("开阔天空", "sky_score", 0.50, "gte"),
    ("有门框", "door_frame_score", 0.30, "gte"),
    ("悬崖警告", "cliff_detected", True, "eq"),
    ("碰撞威胁", "looming", 0.15, "gte"),
    ("走廊狭窄(None)", "terrain", "corridor", "eq"),
    ("水域前方", "terrain", "water", "eq"),
    ("封闭室内", "terrain", "indoor", "eq"),
    ("墙壁前方", "terrain", "wall_ahead", "eq"),
    ("检测到移动目标", "target_count", 1, "gte"),
    ("长时间卡住", "stuck_duration", 60.0, "gte"),
    ("对话激活", "dialogue_active", True, "eq"),
]

NAV_ANOMALY_TAG_MAP: dict[str, str] = {
    "stuck_ramp": "异常态:斜坡卡住",
    "oscillating": "异常态:原地摆动",
    "wall_stuck": "异常态:撞墙卡住",
    "micro_loop": "异常态:微循环编织",
}

PLASTICITY_KEYS = (
    "mb_mbon_forward", "mb_dopamine", "dopamine_gain_avg",
    "learning_progress", "mushroom_weight_changes",
)


# ── structured context ─────────────────────────────────────────────────


@dataclass
class TerrainScores:
    wall_score: float = 0.0
    ramp_score: float = 0.0
    sky_score: float = 0.0
    enclosure_score: float = 0.0
    ground_angle: float = 0.0
    door_frame_score: float = 0.0
    opening_score: float = 0.0
    opening_width: float = 0.0


@dataclass
class OpticFlowSummary:
    asymmetry: float = 0.0
    true_asymmetry: float = 0.0
    looming: float = 0.0
    cliff: float = 0.0
    tau: Optional[float] = None
    hrc_asymmetry: float = 0.0
    local_motion: float = 0.0
    local_motion_detected: bool = False


@dataclass
class TargetTracks:
    count: int = 0
    tracks: list[dict] = field(default_factory=list)


@dataclass
class SceneMemory:
    scene_hash: str = ""
    scene_label: str = ""
    scene_match: float = 0.0
    revisit_count: int = 0


@dataclass
class FlyVision:
    terrain: str = "mixed"
    terrain_scores: TerrainScores = field(default_factory=TerrainScores)
    optic_flow: OpticFlowSummary = field(default_factory=OpticFlowSummary)
    targets: TargetTracks = field(default_factory=TargetTracks)
    scene_context: SceneMemory = field(default_factory=SceneMemory)


@dataclass
class MotorState:
    decision_source: str = "steering"
    forward_rate: float = 0.0
    turn_bias: float = 0.0
    jump_rate: float = 0.0
    gate_forward: bool = False
    gate_jump: bool = False


@dataclass
class NavigationState:
    heading: Optional[float] = None
    heading_rate: float = 0.0
    stuck_duration: float = 0.0
    anomaly_state: str = "idle"
    disp_60s: Optional[float] = None
    coverage_pct: float = 0.0


@dataclass
class PlasticityState:
    mb_mbon_forward: Optional[float] = None
    mb_dopamine: Optional[float] = None
    dopamine_gain_avg: Optional[float] = None
    learning_progress: Optional[float] = None


@dataclass
class ConsultHistory:
    last_advice: str = ""
    last_strategy: dict = field(default_factory=dict)
    last_terrain: str = "mixed"
    same_scene_consults: int = 0
    improvement_since_last: Optional[bool] = None


@dataclass
class FrameDelta:
    changed_scene: bool = False
    terrain_changed: bool = False
    stuck_trend: str = "stable"  # improving | worsening | stable
    displacement_60s: Optional[float] = None
    new_targets_detected: bool = False


@dataclass
class SceneContext:
    """Complete what_i_see structured context for the LLM coach."""

    frame_ts: float = 0.0
    fly_vision: FlyVision = field(default_factory=FlyVision)
    motor_state: MotorState = field(default_factory=MotorState)
    navigation: NavigationState = field(default_factory=NavigationState)
    plasticity: Optional[PlasticityState] = None
    scene_tags: list[str] = field(default_factory=list)
    consult_history: ConsultHistory = field(default_factory=ConsultHistory)
    frame_delta: Optional[FrameDelta] = None


# ── context assembly ────────────────────────────────────────────────────


def _get_safe(data: dict, *keys: str, default: Any = 0.0) -> Any:
    """Deep get with fallback."""
    current = data
    for k in keys:
        if isinstance(current, dict):
            current = current.get(k, {})
        else:
            return default
    return current if current is not None else default


def assemble_terrain_scores(flow: dict) -> TerrainScores:
    return TerrainScores(
        wall_score=_get_safe(flow, "wall_score"),
        ramp_score=_get_safe(flow, "ramp_score"),
        sky_score=_get_safe(flow, "sky_score"),
        enclosure_score=_get_safe(flow, "enclosure_score"),
        ground_angle=_get_safe(flow, "ground_angle"),
        door_frame_score=_get_safe(flow, "door_frame_score"),
        opening_score=_get_safe(flow, "opening_score"),
        opening_width=_get_safe(flow, "opening_width"),
    )


def assemble_optic_flow(flow: dict) -> OpticFlowSummary:
    tau = _get_safe(flow, "tau", default=None)
    return OpticFlowSummary(
        asymmetry=_get_safe(flow, "asymmetry"),
        true_asymmetry=_get_safe(flow, "true_asymmetry"),
        looming=_get_safe(flow, "looming"),
        cliff=_get_safe(flow, "cliff"),
        tau=tau if tau is not None else None,
        hrc_asymmetry=_get_safe(flow, "hrc_asymmetry"),
        local_motion=_get_safe(flow, "local_motion"),
        local_motion_detected=bool(_get_safe(flow, "local_motion_detected", default=False)),
    )


def assemble_targets(flow: dict) -> TargetTracks:
    count = int(_get_safe(flow, "target_count", default=0))
    tracks = _get_safe(flow, "target_tracks", default=[])
    if not isinstance(tracks, list):
        tracks = []
    return TargetTracks(count=count, tracks=tracks)


def assemble_scene_memory(flow: dict, mem: dict) -> SceneMemory:
    return SceneMemory(
        scene_hash=_get_safe(flow, "scene_hash", default=""),
        scene_label=_get_safe(mem, "scene_label", default=""),
        scene_match=_get_safe(flow, "scene_match"),
        revisit_count=_get_safe(mem, "revisit_count", default=0),
    )


def assemble_motor_state(flow: dict, mem: dict) -> MotorState:
    return MotorState(
        decision_source=_get_safe(flow, "decision_source", default="steering"),
        forward_rate=float(_get_safe(mem, "forward_rate", default=0.0)),
        turn_bias=float(_get_safe(mem, "turn_bias", default=0.0)),
        jump_rate=float(_get_safe(mem, "jump_rate", default=0.0)),
        gate_forward=bool(_get_safe(flow, "gate_forward", default=False)),
        gate_jump=bool(_get_safe(flow, "gate_jump", default=False)),
    )


def assemble_navigation(mem: dict) -> NavigationState:
    return NavigationState(
        heading=_get_safe(mem, "heading", default=None),
        heading_rate=_get_safe(mem, "heading_rate", default=0.0),
        stuck_duration=_get_safe(mem, "stuck_duration"),
        anomaly_state=str(_get_safe(mem, "anomaly_state", default="idle")),
        disp_60s=_get_safe(mem, "disp_60s", default=None),
        coverage_pct=_get_safe(mem, "coverage_pct", default=0.0),
    )


def assemble_plasticity(flow: dict) -> Optional[PlasticityState]:
    """Return PlasticityState only when at least one key is present and > 0."""
    has_any = any(
        _get_safe(flow, k, default=0) for k in PLASTICITY_KEYS
    )
    if not has_any:
        return None
    return PlasticityState(
        mb_mbon_forward=_get_safe(flow, "mb_mbon_forward", default=None),
        mb_dopamine=_get_safe(flow, "mb_dopamine", default=None),
        dopamine_gain_avg=_get_safe(flow, "dopamine_gain_avg", default=None),
        learning_progress=_get_safe(flow, "learning_progress", default=None),
    )


# ── scene tag generation ────────────────────────────────────────────────


def generate_scene_tags(flow: dict, mem: dict) -> list[str]:
    """Auto-generate semantic scene tags from existing dashboard data.

    Each rule in TAG_RULES checks one field against a threshold.  Tags are
    derived solely from the fly's own perceptual data and carry no external
    semantic knowledge — the LLM coach uses them to understand what the fly
    "notices" in its environment.
    """
    tags: list[str] = []

    # Threshold-based tags from flow.json
    for label, key, threshold, comparator in TAG_RULES:
        actual = _get_safe(flow, key, default=_get_safe(mem, key, default=None))
        if actual is None:
            # Try memory as fallback
            actual = _get_safe(mem, key, default=None)
        if actual is None:
            continue
        match comparator:
            case "gte":
                if isinstance(actual, (int, float)) and actual >= threshold:
                    tags.append(label)
            case "lte":
                if isinstance(actual, (int, float)) and actual <= threshold:
                    tags.append(label)
            case "eq":
                if isinstance(threshold, bool):
                    if bool(actual) == threshold:
                        tags.append(label)
                elif actual == threshold:
                    tags.append(label)

    # Anomaly state tag from memory
    anomaly = _get_safe(mem, "anomaly_state", default="idle")
    if anomaly != "idle" and anomaly in NAV_ANOMALY_TAG_MAP:
        tags.append(NAV_ANOMALY_TAG_MAP[anomaly])

    # Revisit tag from memory
    revisit = int(_get_safe(mem, "revisit_count", default=0))
    if revisit >= 3:
        tags.append(f"重复回访(第{revisit}次)")
    elif revisit >= 1:
        tags.append(f"已回访(第{revisit}次)")

    # Enrich terrain-based tags with scores
    for score_key, prefix in [
        ("enclosure_score", "围闭度"),
        ("sky_score", "天空度"),
        ("door_frame_score", "门框度"),
    ]:
        val = _get_safe(flow, score_key, default=None)
        if val is not None and val > 0.01:
            matching_tags = [t for t in tags if prefix in t]
            if matching_tags:
                tags.remove(matching_tags[0])
                tags.append(f"{prefix}({val:.2f})")

    return tags


# ── prompt summary builder ──────────────────────────────────────────────


def build_scene_context_summary(ctx: SceneContext) -> str:
    """Build a human-readable summary of the fly's perception.

    This string is injected into the LLM coach prompt so it understands
    what the fly actually perceives vs what the game frame shows.
    """
    v = ctx.fly_vision
    n = ctx.navigation
    m = ctx.motor_state

    lines = [
        f"场景标签: {ctx.scene_tags}",
        f"地形分类: {v.terrain}",
        f"  围闭度={v.terrain_scores.enclosure_score:.2f} "
        f"天空度={v.terrain_scores.sky_score:.2f} "
        f"门框度={v.terrain_scores.door_frame_score:.2f}",
    ]

    of = v.optic_flow
    lines.extend([
        f"光流: 不对称={of.asymmetry:.3f} "
        f"(heading补偿后={of.true_asymmetry:.3f})",
        f"  looming碰撞={of.looming:.3f} "
        f"悬崖信号={of.cliff:.3f} "
        f"τ碰撞时间={of.tau if of.tau else '∞'}",
    ])

    if v.targets.count > 0:
        lines.append(f"小目标追踪: {v.targets.count}个活跃目标")
    else:
        lines.append("小目标追踪: 无")

    lines.extend([
        f"场景记忆: {v.scene_context.scene_hash} "
        f"(回访{v.scene_context.revisit_count}次, "
        f"匹配度{v.scene_context.scene_match:.2f})",
        f"异常态: {n.anomaly_state} "
        f"(卡住{n.stuck_duration:.0f}s "
        f"60s位移={n.disp_60s if n.disp_60s else 'N/A'}u)",
        f"决策源: {m.decision_source} "
        f"前向={m.forward_rate:.1f}Hz "
        f"转向偏置={m.turn_bias:.2f}",
    ])

    p = ctx.plasticity
    if p and p.mb_mbon_forward is not None:
        lines.append(
            f"蘑菇体: forward MBON={p.mb_mbon_forward:.3f} "
            f"多巴胺={p.mb_dopamine if p.mb_dopamine else 'N/A'} "
            f"学习进度={p.learning_progress if p.learning_progress else 'N/A'}"
        )

    fd = ctx.frame_delta
    if fd:
        delta_parts = []
        if fd.changed_scene:
            delta_parts.append("场景已切换")
        if fd.terrain_changed:
            delta_parts.append("地形变化")
        delta_parts.append(f"卡住趋势:{fd.stuck_trend}")
        if fd.new_targets_detected:
            delta_parts.append("新目标出现")
        lines.append("跨帧变化: " + "; ".join(delta_parts))

    ch = ctx.consult_history
    if ch.last_advice and ch.same_scene_consults > 0:
        lines.append(
            f"咨询历史: 同一场景第{ch.same_scene_consults + 1}次咨询, "
            f"上次建议=\"{ch.last_advice[:60]}\" "
            f"改善={'是' if ch.improvement_since_last else '否'}"
        )

    return "\n".join(lines)


# ── main assembly ────────────────────────────────────────────────────────


def assemble_scene_context(flow: dict, mem: dict,
                           consult_history: Optional[dict] = None,
                           prev_context: Optional[SceneContext] = None,
                           ) -> SceneContext:
    """Assemble a full SceneContext from dashboard JSON endpoints.

    Parameters
    ----------
    flow : dict
        Parsed ``/flow.json`` payload.
    mem : dict
        Parsed ``/memory.json`` payload.
    consult_history : dict, optional
        The existing ``coach_advice.json`` payload (latest advice + history).
    prev_context : SceneContext, optional
        Previous consult's scene context for delta comparison.

    Returns
    -------
    SceneContext
    """
    fly_vision = FlyVision(
        terrain=str(_get_safe(flow, "terrain", default="mixed")),
        terrain_scores=assemble_terrain_scores(flow),
        optic_flow=assemble_optic_flow(flow),
        targets=assemble_targets(flow),
        scene_context=assemble_scene_memory(flow, mem),
    )
    motor = assemble_motor_state(flow, mem)
    nav = assemble_navigation(mem)
    plast = assemble_plasticity(flow)
    tags = generate_scene_tags(flow, mem)

    # Consult history
    hist = ConsultHistory()
    if isinstance(consult_history, dict):
        adv = consult_history.get("advice", "")
        if adv:
            hist.last_advice = str(adv)
        strat = consult_history.get("strategy")
        if isinstance(strat, dict):
            hist.last_strategy = strat
        hist.last_terrain = fly_vision.terrain
        # Count how many consults in this same scene
        his = consult_history.get("history")
        if isinstance(his, list):
            same_scene = sum(
                1 for h in his[-10:]
                if isinstance(h, dict)
                and str(h.get("context", {}).get("scene_name", ""))
                == fly_vision.scene_context.scene_label
            )
            hist.same_scene_consults = same_scene

    # Frame delta vs previous context
    fd: Optional[FrameDelta] = None
    if prev_context is not None:
        fd = FrameDelta(
            changed_scene=(
                prev_context.fly_vision.terrain != fly_vision.terrain
                or prev_context.fly_vision.scene_context.scene_hash
                != fly_vision.scene_context.scene_hash
            ),
            terrain_changed=prev_context.fly_vision.terrain != fly_vision.terrain,
            stuck_trend=(
                "improving"
                if nav.stuck_duration < prev_context.navigation.stuck_duration
                else "worsening" if nav.stuck_duration > prev_context.navigation.stuck_duration
                else "stable"
            ),
            displacement_60s=nav.disp_60s,
            new_targets_detected=(
                fly_vision.targets.count > prev_context.fly_vision.targets.count
            ),
        )
        # Improvement: did stuck_duration decrease vs last consult?
        if hist.last_advice and prev_context.navigation.stuck_duration > 0:
            hist.improvement_since_last = (
                nav.stuck_duration < prev_context.navigation.stuck_duration
            )

    return SceneContext(
        frame_ts=time.time(),
        fly_vision=fly_vision,
        motor_state=motor,
        navigation=nav,
        plasticity=plast,
        scene_tags=tags,
        consult_history=hist,
        frame_delta=fd,
    )


def scene_context_to_dict(ctx: SceneContext) -> dict:
    """Convert SceneContext to a JSON-safe dict for prompt embedding."""
    return json.loads(json.dumps(asdict(ctx), ensure_ascii=False, default=str))