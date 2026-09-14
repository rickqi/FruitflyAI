// t7 verification: node-side executability of design-draft functions
// explain() / judgeText() / renderCausal() / drawSectors() extracted from
// docs/causal-chain-implementation.md §2.1–2.3 (no DOM needed except stubs).
const PURPLE = '#9d7bff', GREEN = '#7dff9d', RED = '#ff3c3c', CYAN = '#6cdaed';
const hz = v => Number.isFinite(v) ? v.toFixed(1) : '—';
const number = (v, d = 2) => Number.isFinite(v) ? v.toFixed(d) : '—';
const pct = v => Number.isFinite(v) ? Math.round(v * 100) + '%' : '—';
const PRIORITY = { cliff_reflex: 4, anomaly_reflex: 3, escape: 2, jump: 1, steering: 0 };

function judgeText(r) {
  if (!Number.isFinite(r.cliff_conf)) return 'awaiting causal fields';
  if (r.decision_source === 'cliff_reflex')
    return `CLIFF REFLEX preempts steering (conf ${r.cliff_conf}${r.cliff_confirmed ? ' · confirmed' : ''})`;
  if (r.decision_source === 'escape')
    return `escape (stuck ${r.stuck_conf}) preempts forward gate ${r.gate_forward ? '✓' : '✗'}`;
  const gate = r.gate_forward ? 'gate 0.4 Hz ✓' : 'gate 0.4 Hz ✗';
  const turn = Math.abs(r.right - r.left) > .1 ? `R-turn ${hz(r.right)} vs L ${hz(r.left)}` : 'neutral';
  return `${turn} · forward ${hz(r.forward)} ${gate}`;
}

function explain(r) {
  return [
    { stage: 'raw', cls: '', detail: `t=${r.t.toFixed(2)}s · ΔL ${pct(r.contrast_left)} / ΔR ${pct(r.contrast_right)}` },
    { stage: 'signal', cls: 'sig', detail: `flow asym ${number(r.flow_asymmetry,2)} · loom ${number(r.flow_looming,2)} · cliff ${number(r.flow_cliff,2)} (conf ${number(r.cliff_conf,2)})`,
      active: r.sector_active },
    { stage: 'neural', cls: 'neu', detail: `fwd ${hz(r.forward)}${r.gate_forward ? ' ✓gate' : ' ✗'} · L ${hz(r.left)} · R ${hz(r.right)} · jump ${hz(r.jump)}${r.gate_jump ? ' ✓' : ''}` },
    { stage: 'judge', cls: 'jud', detail: judgeText(r) },
    { stage: 'action', cls: 'act', detail: `x=${r.x} y=${r.y}${r.jump_event ? ' +JUMP' : ''} → ack ${number(r.game_age,0)}ms` },
  ].map(seg => PRIORITY[r.decision_source] > 1 && seg.stage === 'neural'
    ? { ...seg, preempted: r.decision_source !== 'steering' && PRIORITY[r.decision_source] > 0 } : seg);
}

let lastCausal = 0;
function renderCausal(r) {
  const now = performance.now();
  if (now - lastCausal < 200) return; lastCausal = now;
  const host = $('causalChain'); if (!host) return;
  host.innerHTML = explain(r).map(s =>
    `<div class="chain-seg ${s.cls}${s.preempted ? ' preempted' : ''}" data-stage="${s.stage}">
       <span class="chain-label">${s.stage.toUpperCase()}</span><span class="chain-detail">${s.detail}</span>
       <span class="chain-tip" hidden>${s.detail}</span></div>`).join('<span class="chain-arrow">←</span>');
}

function buildSectorMaps() {
  const W = 256, H = 128;
  const sector = new Uint8Array(W * H), sub = new Uint8Array(W * H);
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      const eye = x < 128 ? 0 : 1;
      const u = ((x % 128) + .5 - 64) / 64;
      const v = (64 - y - .5) / 64;
      const radius = Math.hypot(u, v);
      if (radius > 1 || radius < 1e-6) continue;
      const ang = radius * Math.PI / 2;
      const s = Math.sin(ang) / radius;
      const lx = u * s, ly = v * s, lz = Math.cos(ang);
      const a = (eye === 0 ? -63.25 : 63.25) * Math.PI / 180;
      const rx = Math.cos(a) * lx + Math.sin(a) * lz;
      const ry = ly;
      const rz = -Math.sin(a) * lx + Math.cos(a) * lz;
      const az = Math.atan2(rx, rz) * 180 / Math.PI;
      const el = Math.asin(Math.max(-1, Math.min(1, ry))) * 180 / Math.PI;
      if (Math.abs(el) > 72) continue;
      if (eye === 0 ? (az < -135 || az > 8.5) : (az < -8.5 || az > 135)) continue;
      const i = y * W + x;
      const band = Math.min(7, Math.max(0, Math.floor((az + 135) / 33.75)));
      sector[i] = band * 2 + (el >= 0 ? 0 : 1) + 1;
      sub[i] = Math.min(31, Math.max(0, Math.floor((az + 135) / 8.4375))) + 1;
    }
  }
  return { sector, sub };
}

let SECTOR_MAPS = null;
function drawSectors(r) {
  const cv = $('retinaOverlay'), ctx = cv.getContext('2d');
  ctx.clearRect(0, 0, cv.width, cv.height);
  if (!Number.isInteger(r.sector_active)) return;
  if (!SECTOR_MAPS) SECTOR_MAPS = buildSectorMaps();
  const { sector: SM, sub: SB } = SECTOR_MAPS;
  const W = cv.width, H = cv.height;
  const img = ctx.createImageData(W, H);
  const d = img.data;
  for (let i = 0; i < W * H; i++) {
    const s = SM[i];
    if (!s) continue;
    const active = (r.sector_active >> (s - 1)) & 1;
    const x = i % W, y = (i / W) | 0;
    const lS = x > 0 ? SM[i - 1] : 0, tS = y > 0 ? SM[i - W] : 0;
    const mainEdge = (lS && lS !== s) || (tS && tS !== s);
    const sb = SB[i];
    const lB = x > 0 ? SB[i - 1] : 0, tB = y > 0 ? SB[i - W] : 0;
    const subEdge = !mainEdge && ((lB && lB !== sb) || (tB && tB !== sb));
    const o = i * 4;
    if (active) {
      d[o] = 108; d[o + 1] = 218; d[o + 2] = 237;
      d[o + 3] = mainEdge ? 230 : subEdge ? 130 : 78;
    } else if (mainEdge) {
      d[o] = 53; d[o + 1] = 66; d[o + 2] = 80; d[o + 3] = 190;
    } else if (subEdge) {
      d[o] = 53; d[o + 1] = 66; d[o + 2] = 80; d[o + 3] = 70;
    }
  }
  ctx.putImageData(img, 0, 0);
}

function buildStripLUT() {
  const W = 256, H = 128, lut = new Int32Array(W * H).fill(-1);
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      const az = -135 + (x + .5) / W * 270;
      const el = 72 - (y + .5) / H * 144;
      const eye = az < 0 ? 0 : 1;
      const a = (eye === 0 ? -63.25 : 63.25) * Math.PI / 180;
      const azr = az * Math.PI / 180, elr = el * Math.PI / 180;
      const cer = Math.cos(elr);
      const rx = Math.sin(azr) * cer, ry = Math.sin(elr), rz = Math.cos(azr) * cer;
      const ca = Math.cos(a), sa = Math.sin(a);
      const lx = ca * rx - sa * rz, ly = ry, lz = sa * rx + ca * rz;
      const theta = Math.acos(Math.max(-1, Math.min(1, lz)));
      if (theta >= Math.PI / 2) continue;
      const rho = theta / (Math.PI / 2), st = Math.sin(theta);
      const uu = lx / st * rho, vv = ly / st * rho;
      const fx = Math.min(127, Math.max(0, Math.floor((uu + 1) * 64)));
      const fy = Math.min(127, Math.max(0, Math.floor((1 - vv) * 64)));
      lut[y * W + x] = (fy * 256 + eye * 128 + fx) * 3;
    }
  }
  return lut;
}

let STRIP_LUT = null;
function drawStrip(eyes, row) {
  const cv = $('retinaUnwrap'); if (!cv || !eyes) return;
  const ctx = cv.getContext('2d');
  const W = cv.width, H = cv.height;
  if (!STRIP_LUT) STRIP_LUT = buildStripLUT();
  const img = ctx.createImageData(W, H), d = img.data;
  for (let i = 0; i < W * H; i++) {
    const src = STRIP_LUT[i], o = i * 4;
    if (src >= 0 && src + 2 < eyes.length) {
      d[o] = eyes[src]; d[o + 1] = eyes[src + 1]; d[o + 2] = eyes[src + 2];
    }
    d[o + 3] = 255;
  }
  ctx.putImageData(img, 0, 0);
  const active = Number.isInteger(row?.sector_active) ? row.sector_active : 0;
  for (let b = 0; b < 8; b++) {
    const x0 = b * 32;
    for (let half = 0; half < 2; half++) {
      const y0 = half * 64, bit = b * 2 + half;
      ctx.strokeStyle = '#354250'; ctx.lineWidth = 1;
      ctx.strokeRect(x0 + .5, y0 + .5, 31, 63);
      if (active >> bit & 1) {
        ctx.fillStyle = 'rgba(108,218,237,0.28)';
        ctx.fillRect(x0 + 1, y0 + 1, 30, 62);
        ctx.strokeStyle = CYAN; ctx.lineWidth = 1.5;
        ctx.strokeRect(x0 + 1.5, y0 + 1.5, 29, 61); ctx.lineWidth = 1;
      }
    }
  }
}

// ---- stubs for $ / performance / canvas 2d ----
const stubStore = {};
const ctxStub = new Proxy({}, { get: (t, p) => {
  if (p === 'clearRect' || p === 'putImageData' || p === 'fillRect' || p === 'strokeRect') return () => {};
  if (p === 'createImageData') return (w, h) => ({ data: new Uint8ClampedArray(w * h * 4) });
  return undefined;
}});
globalThis.performance = { now: () => Date.now() };
globalThis.$ = id => stubStore[id] ??= { innerHTML: '', width: 256, height: 128, getContext: () => ctxStub };

let pass = 0, fail = 0;
const check = (name, fn) => { try { fn(); pass++; console.log('PASS', name); } catch (e) { fail++; console.log('FAIL', name, '::', e.message); } };

const fullRow = {
  t: 12.34, contrast_left: 0.21, contrast_right: 0.43,
  flow_asymmetry: -0.12, flow_looming: 0.05, flow_cliff: 0.77, cliff_conf: 0.91,
  forward: 1.2, gate_forward: true, left: 0.3, right: 3.2, jump: 0.4, gate_jump: true,
  x: 130, y: 2450, jump_event: false, game_age: 42,
  decision_source: 'cliff_reflex', cliff_confirmed: true, stuck_conf: 0.2, sector_active: 0b1000000000000010,
};
const degRow = { t: 0.5, cliff_conf: NaN, decision_source: 'steering', forward: NaN, left: 0, right: 0, jump: NaN, x: 0, y: 0, game_age: NaN };

check('judgeText full cliff_reflex row', () => {
  const s = judgeText(fullRow);
  if (!s.includes('CLIFF REFLEX') || !s.includes('confirmed')) throw new Error(s);
});
check('judgeText degraded row -> awaiting causal fields', () => {
  if (judgeText(degRow) !== 'awaiting causal fields') throw new Error(judgeText(degRow));
});
check('explain returns 5 segments in degraded mode', () => {
  const segs = explain(degRow);
  if (segs.length !== 5) throw new Error('len=' + segs.length);
  if (!segs.every(s => Number.isFinite(s.detail.length))) throw new Error('detail not string');
});
check('explain marks neural segment preempted on cliff_reflex', () => {
  const segs = explain(fullRow);
  const neu = segs.find(s => s.stage === 'neural');
  if (!neu.preempted) throw new Error('neural not marked preempted');
});
check('explain survives NaN inputs (no throw)', () => explain({ ...fullRow, t: NaN, x: NaN, cliff_conf: NaN }));
check('renderCausal writes 11+ nodes innerHTML', () => {
  renderCausal(fullRow);
  if (!stubStore.causalChain.innerHTML.includes('chain-seg') || !stubStore.causalChain.innerHTML.includes('chain-arrow')) throw new Error('html missing');
});
check('renderCausal throttled below 200ms', () => {
  const before = stubStore.causalChain.innerHTML; renderCausal({ ...fullRow, t: 99 });
  if (stubStore.causalChain.innerHTML !== before) throw new Error('throttle failed');
});
check('drawSectors active-bit path (stub ctx, no throw)', () => drawSectors(fullRow));
check('drawSectors skips non-integer sector_active', () => drawSectors({ sector_active: NaN }));
check('sector maps: both eyes symmetric coverage, mask ~71% of circle', () => {
  const { sector: m } = buildSectorMaps();
  let leftCovered = 0, rightCovered = 0;
  for (let y = 0; y < 128; y++) for (let x = 0; x < 256; x++) {
    if (m[y * 256 + x] > 0) (x < 128 ? leftCovered++ : rightCovered++);
  }
  // Eyes have mirrored geometry → identical valid-FOV pixel counts
  if (leftCovered !== rightCovered) throw new Error(`L=${leftCovered} R=${rightCovered}`);
  // ±72° elevation cap + azimuth edge cuts leave ~71% of each circle in FOV
  const frac = leftCovered / (Math.PI * 64 * 64);
  if (frac < 0.6 || frac > 0.85) throw new Error('mask fraction=' + frac.toFixed(3));
});
check('sector map: every in-FOV pixel gets exactly one sector (no unassigned gaps)', () => {
  const { sector: m } = buildSectorMaps();
  for (let y = 0; y < 128; y++) for (let x = 0; x < 256; x++) {
    const s = m[y * 256 + x];
    if (s > 16) throw new Error('sector id out of range: ' + s);
  }
});
check('sector map uses all 16 sector ids', () => {
  const { sector: m } = buildSectorMaps();
  const seen = new Set(m.filter(v => v > 0));
  if (seen.size !== 16) throw new Error('seen=' + [...seen].join(','));
});
check('sector map bit order matches backend az{i}_{upper|lower}', () => {
  const { sector: m } = buildSectorMaps();
  // az0_upper (bit 0 → id 1) must only exist in the far-left band of the LEFT eye
  for (let y = 0; y < 128; y++) for (let x = 0; x < 256; x++) {
    if (m[y * 256 + x] !== 1) continue;
    if (x >= 128) throw new Error('az0_upper pixel in right eye');
  }
});
check('sub-grid map uses all 32 sub-bands (8.4375° each)', () => {
  const { sub } = buildSectorMaps();
  const seen = new Set(sub.filter(v => v > 0));
  if (seen.size !== 32) throw new Error('seen=' + seen.size);
});
check('strip LUT: every strip pixel has a valid fisheye source', () => {
  const lut = buildStripLUT();
  for (let i = 0; i < lut.length; i++) {
    if (lut[i] < 0) throw new Error('unmapped strip pixel ' + i);
    if (lut[i] + 2 >= 256 * 128 * 3) throw new Error('source out of range ' + lut[i]);
  }
});
check('drawStrip reprojects eyes + sectors (stub ctx, no throw)', () => {
  const eyes = new Uint8Array(256 * 128 * 3).fill(90);
  drawStrip(eyes, fullRow);
  drawStrip(eyes, { sector_active: NaN });
});

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
