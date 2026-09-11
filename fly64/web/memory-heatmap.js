/**
 * Memory heatmap renderer for Fly64 SpatialMemoryMap.
 * Draws a 50×50 grid of visited cells with color gradient,
 * trajectory overlay, and escape event markers with hover tooltips.
 * Self-refreshes every 1s via /memory.json fetch.
 */
const $ = id => document.getElementById(id);

export function initMemoryHeatmap() {
  const canvas = $('memoryHeatmap');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const info = $('memoryInfo');
  let lastData = null;
  let lastTrajectory = [];
  let lastEvents = [];
  let lastCounters = {};
  let lastFlow = null;
  let lastDeadEnds = [];

  // Tooltip setup
  const tooltip = document.createElement('div');
  tooltip.className = 'heatmap-tooltip';
  tooltip.style.cssText =
    'position:absolute;pointer-events:none;background:#1a2330;color:#f0f4f8;' +
    'border:1px solid #6cdaed;border-radius:4px;padding:4px 8px;font-size:11px;' +
    'white-space:nowrap;z-index:100;display:none;';
  canvas.parentElement.style.position = 'relative';
  canvas.parentElement.appendChild(tooltip);

  // Store rendered event positions for hit-testing
  let hitAreas = [];

  async function fetchAll() {
    try {
      const [memResp, trajResp, evResp, flowResp] = await Promise.all([
        fetch('/memory.json'),
        fetch('/trajectory.json'),
        fetch('/events.json'),
        fetch('/flow.json'),
      ]);
      if (memResp.ok) lastData = await memResp.json();
      if (trajResp.ok) lastTrajectory = await trajResp.json();
      if (evResp.ok) {
        const evData = await evResp.json();
        lastEvents = evData.events || [];
        lastCounters = evData.counters || {};
      }
      if (flowResp.ok) lastFlow = await flowResp.json();
      render();
    } catch (e) {
      // silent — dashboard may start before memory/trajectory/events
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

    // Extract dead-end cell coordinates
    lastDeadEnds = d.dead_end_cells || [];

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

    // Draw trajectory overlay (last 500 points as a path)
    if (lastTrajectory.length > 1) {
      const trajPts = lastTrajectory.filter(p =>
        p.x >= minX && p.x <= maxX && p.z >= minZ && p.z <= maxZ
      );
      if (trajPts.length > 1) {
        ctx.strokeStyle = 'rgba(108, 218, 237, 0.5)';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        for (let i = 0; i < trajPts.length; i++) {
          const cx = px(trajPts[i].x, minX, rangeX);
          const cy = py(trajPts[i].z, minZ, rangeZ);
          if (i === 0) ctx.moveTo(cx, cy);
          else ctx.lineTo(cx, cy);
        }
        ctx.stroke();
        // Fade-out glow at the trail head (oldest point)
        ctx.strokeStyle = 'rgba(108, 218, 237, 0.15)';
        ctx.lineWidth = 3;
        ctx.beginPath();
        const head = trajPts[0];
        ctx.arc(px(head.x, minX, rangeX), py(head.z, minZ, rangeZ), 3, 0, Math.PI * 2);
        ctx.stroke();
      }
    }

    // Draw dead-end cell markers (X marks on known dead-end grid positions)
    if (lastDeadEnds.length > 0) {
      const cellW = (w - 2 * pad) / Math.max(Math.sqrt(xs.length || 1), 1) * 0.8;
      const deadEndSize = Math.max(3, cellW * 0.3);
      ctx.strokeStyle = 'rgba(255, 60, 60, 0.7)';
      ctx.lineWidth = 1.5;
      for (const [dex, dez] of lastDeadEnds) {
        const mx = px(dex * 200 + 100, minX, rangeX);
        const my = py(dez * 200 + 100, minZ, rangeZ);
        ctx.beginPath();
        ctx.moveTo(mx - deadEndSize, my - deadEndSize);
        ctx.lineTo(mx + deadEndSize, my + deadEndSize);
        ctx.moveTo(mx + deadEndSize, my - deadEndSize);
        ctx.lineTo(mx - deadEndSize, my + deadEndSize);
        ctx.stroke();
      }
    }

    // Build hit areas and draw escape event markers (reason-color-coded)
    hitAreas = [];
    const activeEscapes = lastEvents.filter(e => e.outcome === 'still_escaping');
    const pastEscapes = lastEvents.filter(e => e.outcome === 'resolved').slice(-10);
    const markerSize = cellR + 5;

    function getReasonStyle(reason, isResolved) {
      const alpha = isResolved ? 0.4 : 0.9;
      switch (reason) {
        case 'fallen': return { fill: `rgba(255,60,60,${alpha})`, shape: 'x' };
        case 'stuck':  return { fill: `rgba(255,200,50,${alpha})`, shape: 'circle' };
        case 'flow':
        case 'cliff':  return { fill: `rgba(50,180,255,${alpha})`, shape: 'diamond' };
        default:       return { fill: `rgba(200,200,200,${alpha})`, shape: 'circle' };
      }
    }

    function drawMarker(cx, cy, style) {
      ctx.fillStyle = style.fill;
      ctx.strokeStyle = style.fill;
      ctx.lineWidth = 2;
      if (style.shape === 'x') {
        ctx.beginPath();
        ctx.moveTo(cx - markerSize, cy - markerSize);
        ctx.lineTo(cx + markerSize, cy + markerSize);
        ctx.moveTo(cx + markerSize, cy - markerSize);
        ctx.lineTo(cx - markerSize, cy + markerSize);
        ctx.stroke();
      } else if (style.shape === 'diamond') {
        ctx.beginPath();
        ctx.moveTo(cx, cy - markerSize);
        ctx.lineTo(cx + markerSize, cy);
        ctx.lineTo(cx, cy + markerSize);
        ctx.lineTo(cx - markerSize, cy);
        ctx.closePath();
        ctx.fill();
      } else {
        ctx.beginPath();
        ctx.arc(cx, cy, markerSize, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    for (const ev of [...activeEscapes, ...pastEscapes]) {
      const ex = ev.position.x;
      const ez = ev.position.z;
      if (ex < minX || ex > maxX || ez < minZ || ez > maxZ) continue;
      const mx = px(ex, minX, rangeX);
      const my = py(ez, minZ, rangeZ);
      const isResolved = ev.outcome === 'resolved';
      const style = getReasonStyle(ev.reason, isResolved);
      drawMarker(mx, my, style);
      // Store hit area for tooltip
      hitAreas.push({ cx: mx, cy: my, r: markerSize + 3, event: ev });
    }

    // Draw current position marker (on top of everything)
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

    // Flash canvas border when cliff is confirmed
    if (lastFlow && lastFlow.cliff_confirmed) {
      canvas.style.transition = 'box-shadow 0.1s';
      canvas.style.boxShadow = 'inset 0 0 12px 2px #ff3c3c';
      setTimeout(() => {
        canvas.style.transition = 'box-shadow 0.5s';
        canvas.style.boxShadow = 'none';
      }, 300);
    }
  }

  // Hover tooltip on canvas
  canvas.addEventListener('mousemove', (e) => {
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    let found = null;
    for (const area of hitAreas) {
      const dx = mx - area.cx;
      const dy = my - area.cy;
      if (dx * dx + dy * dy <= area.r * area.r) {
        found = area.event;
        break;
      }
    }
    if (found) {
      const reasonLabels = { stuck: 'Stuck', fallen: 'Fall', flow: 'Flow Avoid', cliff: 'Cliff' };
      tooltip.style.display = 'block';
      tooltip.style.left = (e.clientX - rect.left + 12) + 'px';
      tooltip.style.top = (e.clientY - rect.top - 10) + 'px';
      tooltip.innerHTML =
        `<strong>${reasonLabels[found.reason] || found.reason}</strong>` +
        ` · ${found.duration.toFixed(1)}s` +
        ` · pos (${found.position.x}, ${found.position.z})` +
        ` · ${found.outcome === 'resolved' ? 'Resolved' : 'Active'}` +
        (found.distance_moved ? ` · ${found.distance_moved.toFixed(0)}u` : '');
    } else {
      tooltip.style.display = 'none';
    }
  });
  canvas.addEventListener('mouseleave', () => { tooltip.style.display = 'none'; });

  function updateInfo(d) {
    if (!info) return;
    const activeEsc = lastEvents.filter(e => e.outcome === 'still_escaping').length;
    const c = lastCounters;
    let escHtml = '';
    if (d.escape_behavior) {
      escHtml = ' <span style="color:#ff6b6b">⚠ ESCAPE</span>';
    }
    if (activeEsc > 0) {
      escHtml += ` <span style="color:#ff6b6b">· ${activeEsc} active</span>`;
    }
    let counterHtml = '';
    if (c.total_escapes !== undefined) {
      counterHtml = `<br><span class="muted">${c.total_escapes} escapes · ${c.total_falls} falls · ${c.total_flow_avoid} avoids</span>`;
    }

    // Coverage and exploration indicator
    let coverageHtml = '';
    if (d.coverage_pct !== undefined) {
      const pct = d.coverage_pct;
      const pctColor = pct < 10 ? '#ff6b6b' : (pct < 25 ? '#ffc832' : '#4cdf7c');
      coverageHtml = ` <span style="color:${pctColor}">■ ${pct}%</span>`;
    }
    if (d.exploration_speed !== undefined) {
      coverageHtml += ` <span class="muted">${d.exploration_speed.toFixed(2)} cells/min</span>`;
    }
    if (d.dead_end_count !== undefined && d.dead_end_count > 0) {
      coverageHtml += ` <span style="color:#ff6b6b">✕ ${d.dead_end_count}</span>`;
    }

    // Cliff status from flow data
    let cliffHtml = '';
    if (lastFlow) {
      const rf = lastFlow;
      if (rf.cliff_confirmed) {
        cliffHtml = ' <span style="color:#ff3c3c;font-weight:bold">🚨 CLIFF! Turn away</span>';
      } else if (rf.cliff < 0.3 && rf.cliff_rate < -0.01) {
        cliffHtml = ' <span style="color:#ffc832">⚠ Approaching edge</span>';
      } else {
        cliffHtml = ' <span style="color:#4cdf7c">✅ Safe</span>';
      }
      if (rf.cliff_rate !== undefined) {
        cliffHtml += ` <span class="muted">rate ${rf.cliff_rate.toFixed(3)}</span>`;
      }
    }

    info.innerHTML = `
      <strong>Stuck</strong> ${d.stuck_score} · ${d.stuck_duration}s
      &nbsp; <strong>Loop</strong> ${d.loop_score}
      &nbsp; <strong>Novelty</strong> ${d.novelty}
      ${escHtml}
      · <span class="muted">${d.visited_cells} cells</span>
      ${counterHtml}
      <br><strong>Coverage</strong> ${coverageHtml}
      <br><strong>Cliff</strong> ${cliffHtml}
    `;
  }

  // Refresh every 1s
  fetchAll();
  setInterval(fetchAll, 1000);
}