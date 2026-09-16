// t22: pure helpers for the 3D height visualisation — kept three-free so
// they are unit-testable in Node (tests/test_trajectory_height.py).

// Blue (low, t=0) → red (high, t=1).  Writes RGB floats into `out` and
// returns it (three.js BufferAttribute-friendly).
export function heightColor(t, out = [0.25, 0.55, 1.0]) {
  const c = Math.max(0, Math.min(1, t));
  out[0] = 0.25 + 0.75 * c;   // red rises
  out[1] = 0.55 - 0.35 * c;   // green dips
  out[2] = 1.0 - 0.7 * c;     // blue falls
  return out;
}

// Vertical reference lines: one drop-line from every Nth path point to the
// ground baseline, N chosen so a full buffer yields ≤ ~334 GPU segments.
export function verticalSegmentCount(n) {
  if (n < 2) return 0;
  const step = Math.max(1, Math.floor(n / 300));
  return Math.floor((n - 1) / step) + 1;
}

export function verticalStep(n) {
  return n < 2 ? 1 : Math.max(1, Math.floor(n / 300));
}

// Ground baseline auto-detection: first trajectory point's height, falling
// back to the SM64 ground plane (y=120) when no points exist.
export function autoGroundY(points, baseline = 120) {
  return points && points.length ? points[0].y : baseline;
}
