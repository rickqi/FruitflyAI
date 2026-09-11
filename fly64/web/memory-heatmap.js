/**
 * Memory heatmap renderer for Fly64 SpatialMemoryMap.
 * Draws a 50×50 grid of visited cells with color gradient.
 * Self-refreshes every 1s via /memory.json fetch.
 */
const $ = id => document.getElementById(id);

export function initMemoryHeatmap() {
  const canvas = $('memoryHeatmap');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const info = $('memoryInfo');
  let lastData = null;

  async function fetchMemory() {
    try {
      const r = await fetch('/memory.json');
      if (!r.ok) throw Error('HTTP ' + r.status);
      lastData = await r.json();
      render();
    } catch (e) {
      // silent — dashboard may start before memory module
    }
  }

  function render() {
    if (!lastData) return;
    const d = lastData;
    const w = canvas.clientWidth, h = canvas.clientHeight;
    const device = window.devicePixelRatio || 1;
    canvas.width = Math.round(w * device);
    canvas.height = Math.round(h * device);
    ctx.scale(device, device);

    // Determine grid extent from heatmap data
    const xs = d.xs || [], zs = d.zs || [], heats = d.heats || [];
    if (!xs.length) {
      ctx.fillStyle = '#10151c';
      ctx.fillRect(0, 0, w, h);
      updateInfo(d);
      return;
    }

    const minX = Math.min(...xs), maxX = Math.max(...xs);
    const minZ = Math.min(...zs), maxZ = Math.max(...zs);
    const rangeX = Math.max(maxX - minX, 1);
    const rangeZ = Math.max(maxZ - minZ, 1);
    const pad = 20;

    // Map world coords to canvas pixels
    const px = (v, mn, rng) => pad + (v - mn) / rng * (w - 2 * pad);
    const py = (v, mn, rng) => h - pad - (v - mn) / rng * (h - 2 * pad);

    // Clear
    ctx.fillStyle = '#10151c';
    ctx.fillRect(0, 0, w, h);

    // Draw cells as circles
    const cellR = Math.max(2, Math.min(6, (w - 2 * pad) / Math.max(Math.sqrt(xs.length), 1) * 0.4));
    for (let i = 0; i < xs.length; i++) {
      const heat = heats[i];
      const cx = px(xs[i], minX, rangeX);
      const cy = py(zs[i], minZ, rangeZ);
      // Blue (cold/unvisited) → Green → Yellow → Red (hot/visited)
      const t = Math.min(1, Math.max(0, heat));
      const r = Math.round(30 + t * 220);      // 30 → 250
      const g = Math.round(180 - t * 160);      // 180 → 20
      const b = Math.round(220 - t * 200);      // 220 → 20
      ctx.fillStyle = `rgb(${r},${g},${b})`;
      ctx.beginPath();
      ctx.arc(cx, cy, cellR, 0, Math.PI * 2);
      ctx.fill();
    }

    // Draw current position marker
    if (d.cell_x !== undefined && d.cell_z !== undefined) {
      const mx = px(d.cell_x, minX, rangeX);
      const my = py(d.cell_z, minZ, rangeZ);
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(mx, my, cellR + 3, 0, Math.PI * 2);
      ctx.stroke();
      ctx.fillStyle = '#ffffff';
      ctx.beginPath();
      ctx.arc(mx, my, 2, 0, Math.PI * 2);
      ctx.fill();
    }

    updateInfo(d);
  }

  function updateInfo(d) {
    if (!info) return;
    info.innerHTML = `
      <strong>Stuck</strong> ${d.stuck_score} · ${d.stuck_duration}s
      &nbsp; <strong>Loop</strong> ${d.loop_score}
      &nbsp; <strong>Novelty</strong> ${d.novelty}
      ${d.escape_behavior ? '<span style="color:#ff6b6b">⚠ ESCAPE</span>' : ''}
      · <span class="muted">${d.visited_cells} cells</span>
    `;
  }

  // Refresh every 1s
  fetchMemory();
  setInterval(fetchMemory, 1000);
}