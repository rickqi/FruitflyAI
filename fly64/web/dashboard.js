const $ = id => document.getElementById(id);
const CYAN = '#6cdaed', GOLD = '#ffca72', INK = '#f0f4f8', MUTED = '#b0bdcc';
// --- Causal-viz kill-switch (rollback plan §3) ---
// Priority: URL ?noviz=1 > localStorage['fly64.causal']. When disabled, every
// causal-chain section/overlay/control MUST carry class "causal-ui" so
// body.causal-off collapses them back to the pre-causal layout. Existing
// panels (health gauge, pills, #decision, etc.) are never tagged causal-ui
// and are unaffected.
const causalParam = (typeof location === 'object' && location.search)
  ? new URLSearchParams(location.search).get('noviz') : null;
const causalOff = causalParam === '1'
  || (causalParam === null && typeof localStorage === 'object'
      && localStorage.getItem('fly64.causal') === 'off');
if (typeof window === 'object') {
  window.__CAUSAL_ENABLED = !causalOff;
  if (causalOff) document.body.classList.add('causal-off');
}

// ── Layout mode toggle: Auto (two-column ≥1400px) / Wide / Single ──────
// body.layout-wide drives the CSS (dashboard.css); this decides when to set
// it. Auto follows matchMedia so plain resizing keeps working, Wide/Single
// override it and persist in localStorage('fly64.layout').
const LAYOUT_KEY = 'fly64.layout';
const wideMQ = (typeof matchMedia === 'function') ? matchMedia('(min-width:1400px)') : null;
function layoutMode() {
  return (typeof localStorage === 'object' && localStorage.getItem(LAYOUT_KEY)) || 'auto';
}
function applyLayout() {
  const mode = layoutMode();
  const wide = mode === 'wide' || (mode === 'auto' && (!wideMQ || wideMQ.matches));
  document.body.classList.toggle('layout-wide', wide);
  const btn = typeof document === 'object' ? document.getElementById('layoutBtn') : null;
  if (btn) {
    btn.textContent = 'Layout: ' + (mode === 'auto' ? 'Auto' : mode === 'wide' ? 'Wide' : 'Single');
    btn.classList.toggle('active', mode !== 'auto');
    btn.title = mode === 'auto'
      ? 'Auto — two-column at ≥1400px. Click to force Wide.'
      : mode === 'wide' ? 'Wide forced. Click to force Single.' : 'Single forced. Click to return to Auto.';
  }
}
function repaintLayout() { if (typeof displayed === 'undefined' || !displayed) return; render(displayed); renderHistoryCharts(); }
if (typeof document === 'object') {
  applyLayout();
  const lb = document.getElementById('layoutBtn');
  if (lb) lb.onclick = () => {
    const next = layoutMode() === 'auto' ? 'wide' : layoutMode() === 'wide' ? 'single' : 'auto';
    if (typeof localStorage === 'object') localStorage.setItem(LAYOUT_KEY, next);
    applyLayout();
    repaintLayout();  // column change resizes every canvas
  };
  if (wideMQ && wideMQ.addEventListener) wideMQ.addEventListener('change', () => { applyLayout(); repaintLayout(); });
}
const states = ['off · F8', 'receiving', 'stale · released', 'torn · released', 'disconnected'];
let meta, latest, displayed, history = [], frozen = false, receivedAt = 0, lastSeq = 0, brainRenderer, measuredLocations, streamError = '';
const number = (n, digits=1) => Number.isFinite(n) ? n.toFixed(digits) : '—';

// Unified canvas sizing: CSS box (clientWidth/Height) is the single source of
// truth; backing store follows ×dpr (capped at 2). Idempotent — no clientWidth
// feedback loop, no repeated clears. Returns null when the canvas is hidden.
function fitCanvas(canvas) {
  const d = Math.min(window.devicePixelRatio || 1, 2);
  const w = canvas.clientWidth, h = canvas.clientHeight;
  if (!w || !h) return null;
  const W = Math.round(w * d), H = Math.round(h * d);
  const ctx = canvas.getContext('2d');
  if (canvas.width !== W || canvas.height !== H) { canvas.width = W; canvas.height = H; }
  ctx.setTransform(d, 0, 0, d, 0, 0);
  ctx.clearRect(0, 0, w, h);
  return { ctx, w, h };
}

export function decodePacket(buffer) {
  if (buffer.byteLength < 8) throw Error('Incomplete dashboard header');
  const bytes = new Uint8Array(buffer), view = new DataView(buffer);
  if (String.fromCharCode(...bytes.slice(0,4)) !== 'F643') throw Error('Dashboard protocol mismatch; reload');
  const end = 8 + view.getUint32(4, true);
  if (end > bytes.length) throw Error('Incomplete dashboard metadata');
  const data = JSON.parse(new TextDecoder().decode(bytes.subarray(8,end)));
  if (data.schema !== 3 || data.width !== 256 || data.height !== 128 || !Number.isInteger(data.n) || data.n < 1 || !Array.isArray(data.rows) || !data.rows.length) throw Error('Invalid dashboard metadata');
  const pixels = data.width * data.height * 3;
  if (end + data.n + 2*pixels !== bytes.length) throw Error('Incomplete dashboard payload');
  return {data, activity: bytes.slice(end,end+data.n), eyes: bytes.slice(end+data.n,end+data.n+pixels), change: bytes.slice(end+data.n+pixels)};
}

function image(id, pixels) {
  const ctx = $(id).getContext('2d'), frame = ctx.createImageData(256,128);
  for (let i=0,j=0;i<pixels.length;i+=3,j+=4) {frame.data[j]=pixels[i];frame.data[j+1]=pixels[i+1];frame.data[j+2]=pixels[i+2];frame.data[j+3]=255;}
  ctx.putImageData(frame,0,0);
}

function chart(id, series, min, max, threshold, marks=false) {
  const fit = fitCanvas($(id)); if (!fit) return;
  const canvas=$(id),ctx=fit.ctx,w=fit.w,h=fit.h;
  const left=30,right=w-8,top=18,bottom=h-(id==='stickChart'?18:5);
  const end=displayed.data.rows.at(-1).t,start=end-10;
  const x=t=>left+(t-start)/10*(right-left),y=v=>bottom-(v-min)/(max-min)*(bottom-top);
  ctx.font='12px -apple-system, sans-serif';ctx.lineWidth=1;ctx.fillStyle=MUTED;
  for (const v of [...new Set([min,0,max])]) {ctx.strokeStyle='#354250';ctx.beginPath();ctx.moveTo(left,y(v));ctx.lineTo(right,y(v));ctx.stroke();ctx.fillText(v,0,y(v)+4);}
  for (let age=10;age>=0;age-=2) {const xx=x(end-age);ctx.strokeStyle='#202a34';ctx.beginPath();ctx.moveTo(xx,top);ctx.lineTo(xx,bottom);ctx.stroke();ctx.textAlign=age===0?'right':'left';if(id==='stickChart')ctx.fillText(age===0?'now':`−${age}s`,xx,h-3);}ctx.textAlign='left';
  if (threshold !== null) {ctx.strokeStyle=INK;ctx.setLineDash([2,3]);ctx.beginPath();ctx.moveTo(left,y(threshold));ctx.lineTo(right,y(threshold));ctx.stroke();ctx.setLineDash([]);ctx.fillStyle=INK;ctx.fillText(`gate > ${threshold} Hz`,left+4,12);}
  else {ctx.fillStyle=CYAN;ctx.fillText(id==='stickChart'?'x = steering':'left = solid',left+4,12);ctx.fillStyle=GOLD;ctx.fillText(id==='stickChart'?'y = forward':'right = dashed',left+120,12);}
  if(max===10){ctx.fillStyle=MUTED;ctx.textAlign='right';ctx.fillText('▲ >10 Hz',right,12);ctx.textAlign='left';}
  ctx.save();ctx.beginPath();ctx.rect(left,top,right-left,bottom-top);ctx.clip();
  for (const [key,color,dash] of series) {ctx.strokeStyle=color;ctx.lineWidth=1.6;ctx.setLineDash(dash||[]);ctx.beginPath();let previous=null;
    for (const row of history) {if(row.t>end||row.t<start)continue;const value=row[key];if(!Number.isFinite(value)||key.startsWith('game_')&&row.game_state!==1){previous=null;continue;}
      if(previous===null||row.t-previous>.031)ctx.moveTo(x(row.t),y(value));else ctx.lineTo(x(row.t),y(value));previous=row.t;
    }ctx.stroke();
    // Keep the useful range fixed; explicitly mark, rather than hide, overflow.
    if(max===10)for(const row of history){if(row.t<start||row.t>end||row[key]<=max)continue;const xx=x(row.t);ctx.fillStyle=color;ctx.beginPath();ctx.moveTo(xx,top);ctx.lineTo(xx-3,top+5);ctx.lineTo(xx+3,top+5);ctx.closePath();ctx.fill();}
  }ctx.setLineDash([]);
  if(marks)for(const row of history){if(row.t<start||row.t>end)continue;if(row.jump_event){ctx.fillStyle=GOLD;ctx.fillRect(x(row.t)-1,top,2,10);}if(row.game_a&&row.game_state===1){ctx.fillStyle=CYAN;ctx.fillRect(x(row.t)-1,bottom-4,2,4);}}
  ctx.restore();
}

function initBrain(positions, measured) {
  const canvas=$('brain'),gl=canvas.getContext('webgl',{antialias:false});
  if(!gl){canvas.setAttribute('aria-label','WebGL unavailable; population rates remain available');return ()=>{};}
  const shader=(type,source)=>{const s=gl.createShader(type);gl.shaderSource(s,source);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(s));return s;};
  const program=gl.createProgram();
  gl.attachShader(program,shader(gl.VERTEX_SHADER,'attribute vec3 p;attribute float a;uniform float aspect;uniform float pointSize;varying float rate;void main(){gl_Position=vec4(p.x*.78/aspect,p.y*.78,0.,1.);gl_PointSize=pointSize;rate=a;}'));
  gl.attachShader(program,shader(gl.FRAGMENT_SHADER,'precision mediump float;uniform float context;varying float rate;void main(){gl_FragColor=vec4(mix(mix(vec3(.16,.19,.23),vec3(1.),rate),vec3(.09,.12,.16),context),1.);}'));
  gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error('Brain shader link failed');gl.useProgram(program);
  const posBuffer=gl.createBuffer(),actBuffer=gl.createBuffer();
  const subsets={all:Uint32Array.from(measured.flatMap((v,i)=>v?[i]:[]))};
  for(const [key,ids]of Object.entries(meta.groups))subsets[key]=Uint32Array.from(ids.filter(i=>measured[i]));
  const contextBuffer=gl.createBuffer(),contextPoints=new Float32Array(subsets.all.length*3);
  subsets.all.forEach((id,i)=>contextPoints.set(positions.subarray(id*3,id*3+3),i*3));
  gl.bindBuffer(gl.ARRAY_BUFFER,contextBuffer);gl.bufferData(gl.ARRAY_BUFFER,contextPoints,gl.STATIC_DRAW);
  let selected=null,ids;
  return activity=>{
    const key=$('population').value;
    if(selected!==key){selected=key;ids=subsets[key];const points=new Float32Array(ids.length*3);ids.forEach((id,i)=>points.set(positions.subarray(id*3,id*3+3),i*3));gl.bindBuffer(gl.ARRAY_BUFFER,posBuffer);gl.bufferData(gl.ARRAY_BUFFER,points,gl.STATIC_DRAW);}
    const rates=Uint8Array.from(ids,id=>activity[id]);
    canvas.width=Math.round(canvas.clientWidth*(window.devicePixelRatio||1));canvas.height=Math.round(canvas.clientHeight*(window.devicePixelRatio||1));gl.viewport(0,0,canvas.width,canvas.height);gl.clearColor(.043,.063,.09,1);gl.clear(gl.COLOR_BUFFER_BIT);gl.useProgram(program);
    gl.uniform1f(gl.getUniformLocation(program,'aspect'),canvas.width/canvas.height);
    if(key!=='all'){
      gl.uniform1f(gl.getUniformLocation(program,'context'),1);gl.uniform1f(gl.getUniformLocation(program,'pointSize'),1);
      gl.bindBuffer(gl.ARRAY_BUFFER,contextBuffer);const p=gl.getAttribLocation(program,'p');gl.enableVertexAttribArray(p);gl.vertexAttribPointer(p,3,gl.FLOAT,false,0,0);
      const a=gl.getAttribLocation(program,'a');gl.disableVertexAttribArray(a);gl.vertexAttrib1f(a,0);gl.drawArrays(gl.POINTS,0,subsets.all.length);
    }
    gl.uniform1f(gl.getUniformLocation(program,'context'),0);gl.uniform1f(gl.getUniformLocation(program,'pointSize'),key==='all'?2:6);
    gl.bindBuffer(gl.ARRAY_BUFFER,posBuffer);let loc=gl.getAttribLocation(program,'p');gl.enableVertexAttribArray(loc);gl.vertexAttribPointer(loc,3,gl.FLOAT,false,0,0);
    gl.bindBuffer(gl.ARRAY_BUFFER,actBuffer);gl.bufferData(gl.ARRAY_BUFFER,rates,gl.DYNAMIC_DRAW);loc=gl.getAttribLocation(program,'a');gl.enableVertexAttribArray(loc);gl.vertexAttribPointer(loc,1,gl.UNSIGNED_BYTE,true,0,0);gl.drawArrays(gl.POINTS,0,ids.length);
  };
}

function render(packet) {
  displayed=packet;const d=packet.data,r=d.rows.at(-1);
  image('retina',packet.eyes);drawEyeGap(r);image('change',packet.change);drawStrip(packet.eyes,r);
  $('unwrapLR').textContent=`ΔL ${pct(r.contrast_left)} · ΔR ${pct(r.contrast_right)}`;
  $('frameAge').textContent=`Frame ${number(r.frame_age*1000,0)} ms old`;
  $('contrast').textContent=d.has_comparison?`Δ light  L ${number(r.contrast_left*100)}% · R ${number(r.contrast_right*100)}%`:'Waiting for frame pair';
  $('visualRate').textContent=`R1–R8 ${number(r.visual)} Hz${d.visual_connected?'':' · disconnected'}`;
  const turn=r.x===0?'neutral steering':r.x<0?'left steering':'right steering';
  $('decision').textContent=`${r.y?'Forward':'Idle'} · ${turn} · jump ${r.jump_event?'requested':r.cooldown>0?`wait ${number(r.cooldown,2)} s`:r.jump>2?'ready':'below gate'}`;
  $('forwardValue').textContent=`${number(r.forward)} Hz → y ${r.y}`;
  $('steeringValue').textContent=`L ${number(r.left)} · R ${number(r.right)} · Δ ${number(r.right-r.left)}`;
  $('jumpValue').textContent=`${number(r.jump)} Hz · ${number(r.cooldown,2)} s wait`;
  $('stickValue').textContent=`x ${r.x} → ${r.game_state===1?r.game_x:'—'} · y ${r.y} → ${r.game_state===1?r.game_y:'—'}`;
  chart('forwardChart',[['forward',CYAN]],0,10,.4);
  chart('steeringChart',[['left',CYAN],['right',GOLD,[5,3]]],0,10,null);
  chart('jumpChart',[['jump',INK]],0,10,2,true);
  chart('stickChart',[['x',CYAN],['y',GOLD],['game_x',CYAN,[3,3]],['game_y',GOLD,[3,3]]],-70,70,null);
  // Phase 3 motor expansion: strike (B) / crouch (Z) pool rates.  Rows only
  // carry these keys when the backend exposes the pools; render when present.
  if (d.rows.length && ('strike' in d.rows[0] || 'crouch' in d.rows[0])) {
    chart('jumpChart',[['jump',INK],['strike',PURPLE],['crouch',GREEN]],0,10,2,true);
  }
  $('gameState').textContent=`Game: ${states[r.game_state]||'unknown'}`;
  $('jumpState').textContent=`A: gold request / cyan received${r.game_state===1?` · ack ${number(r.game_age,0)} ms`:''}`;
  const key=$('population').value,ids=key==='all'?null:meta.groups[key],total=ids?ids.length:meta.n;
  const located=ids?ids.filter(i=>measuredLocations[i]).length:meta.measured;
  $('populationInfo').textContent=`${located.toLocaleString()} located · ${(total-located).toLocaleString()} unlocated`;
  const rate=key==='all'?packet.activity.reduce((a,b)=>a+b,0)/meta.n/255*50:r[key];
  $('populationRate').textContent=`Mean ${number(rate)} Hz${key==='all'?' ≈':''} · ${d.window_ticks*20} ms`;
  brainRenderer?.(packet.activity);
  $('performance').textContent=`${number(r.t,1)} s · ${number(d.rtf,2)}× real time · step ${number(d.latency_ms)} ms · ${number(d.rss_mb,0)} MB · ${d.dropped} dropped`;
  for (const row of d.rows) sampleRing(row);
  drawSectors(r);
  renderTimelineTick(r);
  renderCausal(r);
}

// ── Causal chain card (P0 · pure-frontend derivation, degrades to '—') ──
const PURPLE = '#9d7bff', GREEN = '#7dff9d', RED = '#ff3c3c';
const hz = v => Number.isFinite(v) ? v.toFixed(1) : '—';
const pct = v => Number.isFinite(v) ? `${Math.round(v * 100)}%` : '—';
const PRIORITY = { dialogue: 5, cliff_reflex: 4, anomaly_reflex: 3, escape: 2, jump: 1, steering: 0 };
// Phase 2 motor expansion: CPG primitives sit at cascade priority 4.5
// (between escape and jump).  Source arrives as "cpg_primitive:<name>".
const CPG_PRIORITY = 1.5;
const cpgPriority = src => (typeof src === 'string' && src.startsWith('cpg_primitive:')) ? CPG_PRIORITY : PRIORITY[src];
const CAUSAL_TARGET = { raw: null, signal: 'row-forward', neural: 'row-forward', judge: '#memory-title', action: 'row-stick' };

export function judgeText(r) {
  if (!Number.isFinite(r.cliff_conf)) return 'awaiting causal fields (P1 telemetry)';
  // t16 P0-3: dialogue pause is the top-priority action — never mask it as
  // "neutral steering" while the brain waits for the coach decision.
  if (r.decision_source === 'dialogue') {
    const ld = (typeof window !== 'undefined' && window.__LLM_DECISION) || {};
    if (ld.status === 'waiting')
      return `⏸ DIALOGUE PAUSED · awaiting coach decision (${Math.round(ld.wait_s || 0)}s / 600s)`;
    if (ld.action) return `DIALOGUE · coach decision: ${ld.action}`;
    return 'DIALOGUE · handling (LLM path or habituation guard)';
  }
  if (r.decision_source === 'cliff_reflex')
    return `CLIFF REFLEX preempts steering (conf ${number(r.cliff_conf, 2)}${r.cliff_confirmed ? ' · confirmed' : ''})`;
  if (r.decision_source === 'escape')
    return `escape (stuck ${number(r.stuck_conf, 2)}) preempts forward gate ${r.gate_forward ? '✓' : '✗'}`;
  if (typeof r.decision_source === 'string' && r.decision_source.startsWith('cpg_primitive:')) {
    const prim = r.decision_source.slice('cpg_primitive:'.length);
    return `CPG PRIMITIVE · ${prim} phase script active${r.ctrl_z ? ' · Z' : ''}${r.ctrl_b ? ' · B' : ''}`;
  }
  const gate = r.gate_forward ? 'gate 0.4 Hz ✓' : 'gate 0.4 Hz ✗';
  const turn = Math.abs(r.right - r.left) > .1 ? `R-turn ${hz(r.right)} vs L ${hz(r.left)}` : 'neutral';
  return `${turn} · forward ${hz(r.forward)} ${gate}`;
}

export function explain(r) {
  return [
    { stage: 'raw',    cls: '',    detail: `t=${number(r.t, 2)}s · ΔL ${pct(r.contrast_left)} / ΔR ${pct(r.contrast_right)}` },
    { stage: 'signal', cls: 'sig', detail: `flow asym ${number(r.flow_asymmetry, 2)} · loom ${number(r.flow_looming, 2)} · cliff ${number(r.flow_cliff, 2)}${Number.isFinite(r.cliff_conf) ? ` (conf ${number(r.cliff_conf, 2)})` : ''}` },
    { stage: 'neural', cls: 'neu', detail: `fwd ${hz(r.forward)}${r.gate_forward ? ' ✓gate' : r.gate_forward === undefined ? '' : ' ✗'} · L ${hz(r.left)} · R ${hz(r.right)} · jump ${hz(r.jump)}${r.gate_jump ? ' ✓' : ''}${Number.isFinite(r.strike) ? ` · strike ${hz(r.strike)} · crouch ${hz(r.crouch)}` : ''}` },
    { stage: 'judge',  cls: 'jud', detail: judgeText(r) },
    { stage: 'action', cls: 'act', detail: `x=${r.x ?? '—'} y=${r.y ?? '—'}${r.jump_event ? ' +JUMP' : ''}${r.ctrl_b ? ' +B' : ''}${r.ctrl_z ? ' +Z' : ''} → ack ${Number.isFinite(r.game_age) ? number(r.game_age, 0) : '—'}ms` },
  ].map(seg => cpgPriority(r.decision_source) > 1 && seg.stage === 'neural'
    ? { ...seg, preempted: true } : seg);
}

let lastCausal = 0;
function renderCausal(r) {
  if (typeof window === 'object' && window.__CAUSAL_ENABLED === false) return;
  const now = performance.now();
  if (!r.force && now - lastCausal < 200) return;
  lastCausal = now;
  try {
    const host = $('causalChain'); if (!host) return;
    const src = $('causalSource');
    if (src) src.textContent = r.decision_source ? `decision_source: ${r.decision_source}` : 'decision_source: — (P1)';
    host.innerHTML = explain(r).map(s =>
      `<div class="chain-seg ${s.cls}${s.preempted ? ' preempted' : ''}" data-stage="${s.stage}" tabindex="0" role="button" aria-label="${s.stage}: ${s.detail}">
         <span class="chain-label">${s.stage.toUpperCase()}</span><span class="chain-detail">${s.detail}</span>
         <span class="chain-tip" hidden>${s.detail}</span></div>`).join('<span class="chain-arrow">←</span>');
  } catch (error) { /* causal card must never break the render pipeline (rollback plan §4) */ }
}

// Drill-down: click a chain segment → scroll to its panel + 1.5s flash (event delegation)
if (typeof document !== 'undefined') {
  document.addEventListener('click', event => {
    const seg = event.target.closest?.('.chain-seg');
    if (!seg) return;
    const targetId = CAUSAL_TARGET[seg.dataset.stage];
    const target = targetId ? (targetId.startsWith('#') ? document.getElementById(targetId.slice(1)) : document.getElementById(targetId)) : null;
    if (!target) return;
    target.scrollIntoView({ behavior: 'smooth', block: 'center' });
    target.classList.add('causal-flash');
    setTimeout(() => target.classList.remove('causal-flash'), 1500);
  });
}

// ── P2 · Sector overlay + 4-lane causal timeline + jump-freeze replay ──

// 16 sectors: 8 azimuth bands x upper/lower, drawn in FISHEYE space.
// The backend sectors are angular (8 x 33.75° bands over [-135°,+135°]); the
// preview is an equidistant fisheye per eye (90° half-FOV in a 128px circle).
// A pixel-uniform grid misaligns with both — instead we compute each preview
// pixel's sector with the same projection math as retina.py (lines 244-257)
// and render per-pixel: active sectors tinted cyan, sector boundaries as
// subtle dark edges, outside-FOV pixels untouched. Every eye circle is fully
// covered; no "black middle cells", no uncovered periphery.

function buildSectorMaps() {
  const W = 256, H = 128;
  const sector = new Uint8Array(W * H);           // 0 = outside FOV, 1..16
  const sub = new Uint8Array(W * H);              // 0 = outside FOV, 1..32 (8.4375° bands)
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
      // Bit order matches backend: az{i}_upper = i*2, az{i}_lower = i*2+1
      sector[i] = band * 2 + (el >= 0 ? 0 : 1) + 1;        // 1..16
      sub[i] = Math.min(31, Math.max(0, Math.floor((az + 135) / 8.4375))) + 1;  // 1..32
    }
  }
  return { sector, sub };
}

let SECTOR_MAPS = null;
function drawSectors(row) {
  const cv = $('retinaOverlay'); if (!cv) return;
  const ctx = cv.getContext('2d');
  ctx.clearRect(0, 0, cv.width, cv.height);
  if (!Number.isInteger(row?.sector_active)) return;
  if (!SECTOR_MAPS) SECTOR_MAPS = buildSectorMaps();
  const { sector: SM, sub: SB } = SECTOR_MAPS;
  const W = cv.width, H = cv.height;
  const img = ctx.createImageData(W, H);
  const d = img.data;
  for (let i = 0; i < W * H; i++) {
    const s = SM[i];
    if (!s) continue;
    const active = (row.sector_active >> (s - 1)) & 1;
    const x = i % W, y = (i / W) | 0;
    const lS = x > 0 ? SM[i - 1] : 0, tS = y > 0 ? SM[i - W] : 0;
    const mainEdge = (lS && lS !== s) || (tS && tS !== s);
    const sb = SB[i];
    const lB = x > 0 ? SB[i - 1] : 0, tB = y > 0 ? SB[i - W] : 0;
    const subEdge = !mainEdge && ((lB && lB !== sb) || (tB && tB !== sb));
    const o = i * 4;
    if (active) {
      d[o] = 108; d[o + 1] = 218; d[o + 2] = 237;            // CYAN #6cdaed
      d[o + 3] = mainEdge ? 230 : subEdge ? 130 : 78;        // fill + edges
    } else if (mainEdge) {
      d[o] = 53; d[o + 1] = 66; d[o + 2] = 80; d[o + 3] = 190; // #354250 boundary
    } else if (subEdge) {
      d[o] = 53; d[o + 1] = 66; d[o + 2] = 80; d[o + 3] = 70;  // faint sub-grid
    }
  }
  ctx.putImageData(img, 0, 0);
}

// ── Unwrapped signal-space view: 270°(az) × 144°(el) equirectangular strip ──
// Every strip pixel maps linearly to (az, el); the fisheye preview pixel that
// shows that direction is found via the forward fisheye projection, so the
// strip is a distortion-corrected reprojection of the live eye image. The 16
// sectors tile it as perfect rectangles — 100% coverage, visually obvious.

function buildStripLUT(W, H) {
  const lut = new Int32Array(W * H).fill(-1);
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      const az = -135 + (x + .5) / W * 270;
      const el = 72 - (y + .5) / H * 144;
      const eye = az < 0 ? 0 : 1;                    // closer eye centre
      const a = (eye === 0 ? -63.25 : 63.25) * Math.PI / 180;
      const azr = az * Math.PI / 180, elr = el * Math.PI / 180;
      const cer = Math.cos(elr);
      const rx = Math.sin(azr) * cer, ry = Math.sin(elr), rz = Math.cos(azr) * cer;
      const ca = Math.cos(a), sa = Math.sin(a);
      const lx = ca * rx - sa * rz, ly = ry, lz = sa * rx + ca * rz;
      const theta = Math.acos(Math.max(-1, Math.min(1, lz)));
      if (theta >= Math.PI / 2) continue;             // beyond fisheye reach
      const rho = theta / (Math.PI / 2), st = Math.sin(theta);
      const uu = lx / st * rho, vv = ly / st * rho;
      const fx = Math.min(127, Math.max(0, Math.floor((uu + 1) * 64)));
      const fy = Math.min(127, Math.max(0, Math.floor((1 - vv) * 64)));
      lut[y * W + x] = (fy * 256 + eye * 128 + fx) * 3;   // RGB index into packet.eyes
    }
  }
  return lut;
}

let STRIP_LUT = null, STRIP_LUT_KEY = '';
// ΔL/ΔR drawn in the bottom-centre gap between the two eye circles
// (x≈86..170 at y≥120 lies outside both fisheye circles → always black).
function drawEyeGap(r) {
  const ctx = $('retina').getContext('2d');
  ctx.font = '9px monospace'; ctx.textAlign = 'center'; ctx.fillStyle = CYAN;
  ctx.fillText(`ΔL ${pct(r.contrast_left)} · ΔR ${pct(r.contrast_right)}`, 128, 125);
  ctx.textAlign = 'left';
}
function drawStrip(eyes, row) {
  const cv = $('retinaUnwrap'); if (!cv || !eyes) return;
  const ctx = cv.getContext('2d');
  const W = cv.width, H = cv.height, key = W + 'x' + H;
  if (STRIP_LUT_KEY !== key) { STRIP_LUT = buildStripLUT(W, H); STRIP_LUT_KEY = key; }
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
  const bw = W / 8, bh = H / 2;
  for (let b = 0; b < 8; b++) {
    const x0 = b * bw;
    for (let half = 0; half < 2; half++) {
      const y0 = half * bh, bit = b * 2 + half;
      ctx.strokeStyle = '#354250'; ctx.lineWidth = 1;
      ctx.strokeRect(x0 + .5, y0 + .5, bw - 1, bh - 1);
      if (active >> bit & 1) {
        ctx.fillStyle = 'rgba(108,218,237,0.28)';
        ctx.fillRect(x0 + 1, y0 + 1, bw - 2, bh - 2);
        ctx.strokeStyle = CYAN; ctx.lineWidth = 1.5;
        ctx.strokeRect(x0 + 1.5, y0 + 1.5, bw - 3, bh - 3); ctx.lineWidth = 1;
      }
    }
  }
  ctx.fillStyle = 'rgba(176,189,204,0.85)'; ctx.font = '8px sans-serif';
  [-135, -67.5, 0, 67.5, 135].forEach(az => {
    const x = Math.round((az + 135) / 270 * W);
    ctx.fillText(az + '°', Math.min(W - 24, Math.max(1, x + 2)), 8);
  });
}

// 120s ring buffer, 0.25s sampling, filled from every arriving row.
let ringBuffer = [];
function sampleRing(r) {
  if (!ringBuffer.length || r.t - ringBuffer[ringBuffer.length - 1].t >= .25) {
    ringBuffer.push(r);
    while (ringBuffer.length && r.t - ringBuffer[0].t > 120) ringBuffer.shift();
  }
}

let replayRow = null;   // set while inspecting/jumped to a past sample
function drawTimeline() {
  const cv = $('timeline'); if (!cv) return;
  const fit = fitCanvas(cv); if (!fit) return;
  const ctx = fit.ctx, w = fit.w, h = fit.h;   // h comes from CSS (#timeline height)
  const rows = ringBuffer;
  if (rows.length < 2) { ctx.fillStyle = MUTED; ctx.font = '11px sans-serif'; ctx.fillText('waiting for samples…', 8, 16); return; }
  const t1 = rows[rows.length - 1].t, t0 = t1 - Math.min(120, t1 - rows[0].t);
  const X = t => (t - t0) / (t1 - t0) * (w - 8) + 4;
  // Four lanes scale with the CSS height instead of assuming 120px
  const laneH = (h - 8) / 4;
  const lanes = [[4, 4 + laneH], [4 + laneH, 4 + 2 * laneH], [4 + 2 * laneH, 4 + 3 * laneH], [4 + 3 * laneH, 4 + 4 * laneH]];
  const laneLabels = ['flow', 'pools Hz', 'judge', 'action'];
  ctx.font = '9px sans-serif'; ctx.fillStyle = MUTED;
  lanes.forEach(([, y2], i) => {
    ctx.strokeStyle = '#1a2430'; ctx.strokeRect(4.5, lanes[i][0] + .5, w - 10, y2 - lanes[i][0] - 1);
    ctx.fillText(laneLabels[i], 7, lanes[i][0] + 10);
  });
  const line = (key, color, lo, hi, y1, y2) => {
    ctx.strokeStyle = color; ctx.beginPath();
    let started = false;
    for (const r of rows) if (r.t >= t0 && Number.isFinite(r[key])) {
      const y = y2 - Math.max(0, Math.min(1, (r[key] - lo) / (hi - lo))) * (y2 - y1 - 4) - 2;
      started ? ctx.lineTo(X(r.t), y) : (ctx.moveTo(X(r.t), y), started = true);
    }
    ctx.stroke();
  };
  // Lane 1: flow signals (-1..1)
  line('flow_asymmetry', CYAN, -1, 1, lanes[0][0], lanes[0][1]);
  line('flow_looming', GOLD, -1, 1, lanes[0][0], lanes[0][1]);
  line('flow_cliff', RED, -1, 1, lanes[0][0], lanes[0][1]);
  // Lane 2: pool rates (0..10 Hz) with gates
  line('forward', CYAN, 0, 10, lanes[1][0], lanes[1][1]);
  line('left', '#3fa8bc', 0, 10, lanes[1][0], lanes[1][1]);
  line('right', GOLD, 0, 10, lanes[1][0], lanes[1][1]);
  ctx.strokeStyle = '#536170'; ctx.setLineDash([2, 3]);
  for (const gate of [.4, 2]) {
    const y = lanes[1][1] - (gate / 10) * (lanes[1][1] - lanes[1][0] - 4) - 2;
    ctx.beginPath(); ctx.moveTo(4, y); ctx.lineTo(w - 6, y); ctx.stroke();
  }
  ctx.setLineDash([]);
  // Lane 3: judgement bands — purple where gate_forward, red ▲ where cliff_confirmed
  ctx.fillStyle = 'rgba(157,123,255,.55)';
  for (let i = 1; i < rows.length; i++) {
    const r = rows[i];
    if (r.t >= t0 && r.gate_forward) ctx.fillRect(X(rows[i - 1].t), lanes[2][0] + 2, Math.max(1, X(r.t) - X(rows[i - 1].t)), lanes[2][1] - lanes[2][0] - 6);
  }
  ctx.fillStyle = RED; ctx.font = '8px sans-serif';
  for (const r of rows) if (r.t >= t0 && r.cliff_confirmed) ctx.fillText('▲', X(r.t) - 3, lanes[2][0] + 10);
  // Lane 4: action — x stepped line (-80..80) + gold jump ticks
  ctx.strokeStyle = GREEN; ctx.beginPath();
  let started = false;
  for (const r of rows) if (r.t >= t0 && Number.isFinite(r.x)) {
    const y = lanes[3][1] - ((r.x + 80) / 160) * (lanes[3][1] - lanes[3][0] - 4) - 2;
    started ? ctx.lineTo(X(r.t), y) : (ctx.moveTo(X(r.t), y), started = true);
  }
  ctx.stroke();
  ctx.fillStyle = GOLD;
  for (const r of rows) if (r.t >= t0 && r.jump_event) ctx.fillRect(X(r.t) - 1, lanes[3][0] + 2, 2, 5);
  // Replay cursor
  if (replayRow && replayRow.t >= t0) {
    ctx.strokeStyle = PURPLE; ctx.setLineDash([3, 3]);
    ctx.beginPath(); ctx.moveTo(X(replayRow.t), 4); ctx.lineTo(X(replayRow.t), h - 6); ctx.stroke();
    ctx.setLineDash([]);
  }
  // P3 causal arcs: cliff_confirmed rising edge → next x sign flip (+ms label)
  try { drawArcs(ctx, rows, t0, t1, X, lanes, w); } catch {}
}

function drawArcs(ctx, rows, t0, t1, X, lanes, w) {
  let edge = null;
  let lastX = null;
  let prevConfirmed = false;
  for (const r of rows) {
    if (r.t < t0) { prevConfirmed = !!r.cliff_confirmed; if (Number.isFinite(r.x) && r.x !== 0) lastX = r.x; continue; }
    if (edge === null) {
      if (r.cliff_confirmed && !prevConfirmed) edge = { t0: r.t, x0: lastX };
      prevConfirmed = !!r.cliff_confirmed;
      if (Number.isFinite(r.x) && r.x !== 0) lastX = r.x;
      continue;
    }
    // Searching for the response: x sign flip vs pre-edge direction
    if (Number.isFinite(r.x) && r.x !== 0 && lastX !== null && Math.sign(r.x) !== Math.sign(lastX)) {
      if (r.t - edge.t0 <= 1.5) {
        const xa = X(edge.t0), xb = X(r.t);
        ctx.strokeStyle = 'rgba(157,123,255,.8)';
        ctx.beginPath();
        ctx.moveTo(xa, lanes[2][1] - 2);
        ctx.quadraticCurveTo((xa + xb) / 2, lanes[2][0] - 8, xb, lanes[3][0] + 2);
        ctx.stroke();
        ctx.fillStyle = PURPLE; ctx.font = '9px sans-serif';
        ctx.fillText(`+${Math.round((r.t - edge.t0) * 1000)}ms`, Math.max(6, (xa + xb) / 2 - 14), lanes[2][0] - 2);
      }
      edge = null;
    } else if (Number.isFinite(r.x) && r.x !== 0) lastX = r.x;
    if (r.t > t1) break;
  }
}

// Timeline interaction: hover = inspect causal card of nearest sample;
// click = jump & freeze at that sample (reuses frozen semantics).
function timelineTime(clientX, cv) {
  const rect = cv.getBoundingClientRect();
  const frac = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
  const rows = ringBuffer; if (rows.length < 2) return null;
  const t1 = rows[rows.length - 1].t, t0 = t1 - Math.min(120, t1 - rows[0].t);
  const target = t0 + frac * (t1 - t0);
  return rows.reduce((best, r) => Math.abs(r.t - target) < Math.abs(best.t - target) ? r : best, rows[0]);
}

let lastTimeline = 0;
function renderTimelineTick(r) {
  const now = performance.now();
  if (now - lastTimeline < 1000) return;
  lastTimeline = now;
  try { drawTimeline(); } catch (error) { /* never break render pipeline */ }
}

if (typeof document !== 'undefined') {
  document.addEventListener('mousemove', event => {
    const cv = $('timeline');
    if (!cv || !cv.matches(':hover') || window.__CAUSAL_ENABLED === false) return;
    const r = timelineTime(event.clientX, cv);
    if (r) { try { renderCausal({ ...r, force: true }); } catch {} }
  });
  document.addEventListener('click', event => {
    const cv = $('timeline');
    if (!cv || !cv.contains(event.target) || window.__CAUSAL_ENABLED === false) return;
    const r = timelineTime(event.clientX, cv);
    if (!r) return;
    replayRow = r; frozen = true; $('freeze').textContent = 'Resume live';
    renderCausal({ ...r, force: true });
    drawTimeline();
    const info = $('timelineInfo');
    if (info) info.textContent = `inspecting t=${number(r.t, 2)}s · click Freeze/Resume to return live`;
  });
  // Escape table row → jump timeline to t-2s before the event and freeze
  document.addEventListener('click', event => {
    if (window.__CAUSAL_ENABLED === false) return;
    const tr = event.target.closest?.('tr.causal-jump');
    if (!tr) return;
    const tEvent = parseFloat(tr.dataset.t);
    if (!Number.isFinite(tEvent) || ringBuffer.length < 2) return;
    const target = tEvent - 2;
    const r = ringBuffer.reduce((best, s) => Math.abs(s.t - target) < Math.abs(best.t - target) ? s : best, ringBuffer[0]);
    replayRow = r; frozen = true; $('freeze').textContent = 'Resume live';
    renderCausal({ ...r, force: true });
    try { drawTimeline(); } catch {}
    $('timeline')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  });
}

async function start() {
  const response=await fetch('/metadata.json');if(!response.ok)throw Error('Cannot load model metadata');meta=await response.json();$('model').textContent=meta.label.startsWith('DEMO')?'Synthetic fixture':`MaleCNS · ${meta.n.toLocaleString()} neurons`;
  const [pos,mask]=await Promise.all(['/positions.bin','/measured.bin'].map(path=>fetch(path).then(r=>{if(!r.ok)throw Error('Cannot load anatomy');return r.arrayBuffer();})));
  if(pos.byteLength!==meta.n*12||mask.byteLength!==meta.n)throw Error('Anatomy size mismatch');
  measuredLocations=Array.from(new Uint8Array(mask));brainRenderer=initBrain(new Float32Array(pos),measuredLocations);
  function connect() {
    const ws=new WebSocket(`ws://${location.hostname}:${meta.ws}`);ws.binaryType='arraybuffer';
    ws.onmessage=event=>{try{const packet=decodePacket(event.data);if(packet.data.n!==meta.n){location.reload();return;}
      if(packet.data.seq<=lastSeq){history=[];frozen=false;$('freeze').textContent='Freeze display';}
      lastSeq=packet.data.seq;receivedAt=performance.now();latest=packet;
      if(!frozen){history.push(...packet.data.rows);const cutoff=packet.data.rows.at(-1).t-10;history=history.filter(r=>r.t>=cutoff);render(packet);}
      $('freeze').disabled=false;
    }catch(error){streamError=error.message;$('status').textContent=streamError;$('status').dataset.state='bad';ws.close(1002);}};
    ws.onclose=()=>{receivedAt=0;if(!streamError)setTimeout(connect,1500);};
  }
  connect();
  $('freeze').onclick=()=>{frozen=!frozen;$('freeze').textContent=frozen?'Resume live':'Freeze display';if(!frozen){replayRow=null;const info=$('timelineInfo');if(info)info.textContent='hover = inspect · click = jump & freeze';}if(!frozen&&latest){history=latest.data.rows.slice();render(latest);}};
  $('population').onchange=()=>{if(displayed)render(displayed);};
  // Resize handling: observe the chart canvases themselves (covers window
  // resize AND two-column layout changes), with a window-resize fallback.
  const repaint = () => { if (displayed) render(displayed); renderHistoryCharts(); };
  if (typeof ResizeObserver !== 'undefined') {
    const ro = new ResizeObserver(repaint);
    ['forwardChart','steeringChart','jumpChart','stickChart','timeline','stuckChart','flowChart','coverageChart','memoryHeatmap'].forEach(id => { const el = $(id); if (el) ro.observe(el); });
  }
  window.addEventListener('resize', repaint);
  setInterval(()=>{const stale=!receivedAt||performance.now()-receivedAt>1000;$('status').textContent=streamError||(stale?'Disconnected / stale':frozen?'Display frozen · game runs':'Live');$('status').dataset.state=stale?'bad':'ok';},250);
}
if (typeof document !== 'undefined') start().catch(error=>{$('status').textContent=error.message;$('status').dataset.state='bad';});
// Lazy-init memory heatmap when the section exists
import('./memory-heatmap.js').then(m => m.initMemoryHeatmap()).catch(() => {});

// ── History charts (stuck trend + optic flow) ──────────────────────────

let historyData = [];

async function fetchHistory() {
  try {
    const r = await fetch('/history.json');
    if (r.ok) historyData = await r.json();
    renderHistoryCharts();
  } catch (_) {}
}

const CYAN2 = '#6cdaed', GOLD2 = '#ffca72', INK2 = '#f0f4f8', MUTED2 = '#b0bdcc';

function renderHistoryCharts() {
  if (!historyData.length) return;

  // ── Stuck Trend chart ──
  const stuckCanvas = $('stuckChart');
  if (stuckCanvas) {
    const fit = fitCanvas(stuckCanvas); if (fit) {
    const ctx = fit.ctx, w = fit.w, h = fit.h;
    const top = 10, bottom = h - 2, left = 4, right = w - 4;
    const range = bottom - top;

    // Get the last 60s of data
    const now = historyData.length > 0 ? historyData[historyData.length - 1].t : 60;
    const cutoff = now - 60;
    const pts = historyData.filter(p => p.t >= cutoff);
    if (pts.length < 2) return;

    // X/Y mapping
    const xpos = (t) => left + (t - cutoff) / 60 * (right - left);
    const ypos = (v) => bottom - v * range;

    // Grid lines
    ctx.strokeStyle = '#303a45';
    ctx.lineWidth = 0.5;
    for (let s = 0; s <= 60; s += 15) {
      const xx = xpos(cutoff + s);
      ctx.beginPath(); ctx.moveTo(xx, top); ctx.lineTo(xx, bottom); ctx.stroke();
    }
    ctx.fillStyle = MUTED2;
    ctx.font = '9px -apple-system, sans-serif';
    ctx.fillText('0', left, bottom + 9);
    ctx.fillText('1', left, top + 9);

    // Threshold line at 0.8
    ctx.strokeStyle = '#ff6b6b';
    ctx.lineWidth = 0.5;
    ctx.setLineDash([2, 3]);
    ctx.beginPath(); ctx.moveTo(left, ypos(0.8)); ctx.lineTo(right, ypos(0.8)); ctx.stroke();
    ctx.setLineDash([]);

    // Draw stuck_score line with color per segment
    ctx.lineWidth = 1.5;
    for (let i = 1; i < pts.length; i++) {
      const a = pts[i - 1], b = pts[i];
      const val = (a.stuck_score + b.stuck_score) / 2;
      // Color gradient: green (low) → yellow → red (high)
      const t = Math.min(1, Math.max(0, val));
      const r = Math.round(30 + t * 225);
      const g = Math.round(200 - t * 180);
      const bv = Math.round(80 - t * 60);
      ctx.strokeStyle = `rgb(${r},${g},${bv})`;
      ctx.beginPath();
      ctx.moveTo(xpos(a.t), ypos(a.stuck_score));
      ctx.lineTo(xpos(b.t), ypos(b.stuck_score));
      ctx.stroke();
    }
    }
  }

  // ── Optic Flow chart ──
  const flowCanvas = $('flowChart');
  if (flowCanvas) {
    const fit = fitCanvas(flowCanvas); if (fit) {
    const ctx = fit.ctx, w = fit.w, h = fit.h;
    const top = 10, bottom = h - 2, left = 4, right = w - 4;
    const range = bottom - top;

    const now = historyData.length > 0 ? historyData[historyData.length - 1].t : 60;
    const cutoff = now - 60;
    const pts = historyData.filter(p => p.t >= cutoff);
    if (pts.length < 2) return;

    const xpos = (t) => left + (t - cutoff) / 60 * (right - left);
    const ypos = (v) => bottom - v * range;

    ctx.strokeStyle = '#303a45';
    ctx.lineWidth = 0.5;
    for (let s = 0; s <= 60; s += 15) {
      const xx = xpos(cutoff + s);
      ctx.beginPath(); ctx.moveTo(xx, top); ctx.lineTo(xx, bottom); ctx.stroke();
    }
    ctx.fillStyle = MUTED2;
    ctx.font = '9px -apple-system, sans-serif';
    ctx.fillText('0', left, bottom + 9);
    ctx.fillText('1', left, top + 9);

    // 0.3 reference line
    ctx.strokeStyle = '#536170';
    ctx.lineWidth = 0.5;
    ctx.setLineDash([2, 3]);
    ctx.beginPath(); ctx.moveTo(left, ypos(0.3)); ctx.lineTo(right, ypos(0.3)); ctx.stroke();
    ctx.setLineDash([]);

    // Draw three flow lines
    const flowSeries = [
      { key: 'asymmetry', color: CYAN2, label: 'asym' },
      { key: 'looming', color: GOLD2, label: 'loom' },
      { key: 'cliff', color: MUTED2, label: 'cliff' },
    ];
    ctx.lineWidth = 1.2;
    for (const series of flowSeries) {
      ctx.strokeStyle = series.color;
      ctx.beginPath();
      let started = false;
      for (const p of pts) {
        const v = p[series.key];
        if (v === undefined) { started = false; continue; }
        const xx = xpos(p.t), yy = ypos(v);
        if (!started) { ctx.moveTo(xx, yy); started = true; }
        else ctx.lineTo(xx, yy);
      }
      ctx.stroke();
      // Label at the end
      if (pts.length > 0) {
        const last = pts[pts.length - 1];
        ctx.fillStyle = series.color;
        ctx.font = '8px -apple-system, sans-serif';
        ctx.fillText(series.label, right - 30, top + 4 + flowSeries.indexOf(series) * 10);
      }
    }

    // Overlay cliff_confirmed markers (red vertical bars)
    if (pts.length > 0) {
      for (const p of pts) {
        if (p.cliff_confirmed) {
          const xx = xpos(p.t);
          ctx.strokeStyle = '#ff3c3c';
          ctx.lineWidth = 1;
          ctx.globalAlpha = 0.5;
          ctx.beginPath();
          ctx.moveTo(xx, top);
          ctx.lineTo(xx, bottom);
          ctx.stroke();
          ctx.globalAlpha = 1;
        }
      }
    }
    }
  }
}

// Start history fetch cycle when the chart canvases exist
if (typeof document !== 'undefined' && $('stuckChart')) {
  fetchHistory();
  setInterval(fetchHistory, 1000);
}

// ── Escape event table ─────────────────────────────────────────────

let escapeData = [];

async function fetchEscapeEvents() {
  try {
    const r = await fetch('/events.json');
    if (r.ok) {
      const data = await r.json();
      escapeData = data.events || [];
      renderEscapeTable(data);
    }
  } catch (_) {}
}

const escapeReasonLabels = { stuck: 'Stuck', fallen: 'Fall', flow: 'Flow', cliff: 'Cliff' };
const escapeReasonClasses = { stuck: 'reason-stuck', fallen: 'reason-fallen', flow: 'reason-flow', cliff: 'reason-cliff' };

function renderEscapeTable(data) {
  const tbody = $('escapeBody');
  if (!tbody) return;
  const events = data.events || [];
  const counters = data.counters || {};

  // Update event count
  const countEl = $('escapeCount');
  if (countEl) {
    const total = counters.total_escapes || 0;
    const falls = counters.total_falls || 0;
    countEl.textContent = `${total} escapes · ${falls} falls`;
  }

  // Build rows (most recent first, last 50)
  let html = '';
  const reversed = [...events].reverse().slice(0, 50);
  for (const ev of reversed) {
    const reasonClass = escapeReasonClasses[ev.reason] || '';
    const reasonLabel = escapeReasonLabels[ev.reason] || ev.reason;
    const dur = ev.duration !== undefined ? ev.duration.toFixed(1) + 's' : '—';
    const dist = ev.distance_moved !== undefined ? ev.distance_moved.toFixed(0) + 'u' : '—';
    const time = ev.timestamp !== undefined ? ev.timestamp.toFixed(1) + 's' : '—';
    const jumpable = ev.timestamp !== undefined && window.__CAUSAL_ENABLED !== false;
    html += `<tr${jumpable ? ` class="causal-jump" data-t="${ev.timestamp}" title="click: jump timeline to t-${number(ev.timestamp,1)}s"` : ''}><td>${time}</td><td class="${reasonClass}">${reasonLabel}</td><td>${dur}</td><td>${dist}</td></tr>`;
  }
  if (!html) {
    html = '<tr><td colspan="4" class="escape-empty">No escape events yet</td></tr>';
  }
  tbody.innerHTML = html;
}

// ── Coverage trend chart ───────────────────────────────────────────

function renderCoverageChart() {
  const canvas = $('coverageChart');
  if (!canvas || !historyData.length) return;

  const fit = fitCanvas(canvas); if (!fit) return;
  const ctx = fit.ctx, w = fit.w, h = fit.h;

  const top = 10, bottom = h - 2, left = 4, right = w - 4;
  const range = bottom - top;

  // Get last 60s of data with coverage_pct
  const now = historyData.length > 0 ? historyData[historyData.length - 1].t : 60;
  const cutoff = now - 60;
  const pts = historyData.filter(p => p.t >= cutoff && p.coverage_pct !== undefined);
  if (pts.length < 2) return;

  const minCov = Math.min(...pts.map(p => p.coverage_pct));
  const maxCov = Math.max(...pts.map(p => p.coverage_pct));
  const covRange = Math.max(maxCov - minCov, 1);

  const xpos = (t) => left + (t - cutoff) / 60 * (right - left);
  const ypos = (v) => bottom - (v - minCov) / covRange * range;

  // Grid lines
  ctx.strokeStyle = '#303a45';
  ctx.lineWidth = 0.5;
  for (let s = 0; s <= 60; s += 15) {
    const xx = xpos(cutoff + s);
    ctx.beginPath(); ctx.moveTo(xx, top); ctx.lineTo(xx, bottom); ctx.stroke();
  }
  ctx.fillStyle = '#b0bdcc';
  ctx.font = '9px -apple-system, sans-serif';
  ctx.fillText(minCov.toFixed(0) + '%', left, bottom + 9);
  ctx.fillText(maxCov.toFixed(0) + '%', left, top + 9);

  // Draw coverage line
  ctx.strokeStyle = '#6cdaed';
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  for (let i = 0; i < pts.length; i++) {
    const xx = xpos(pts[i].t), yy = ypos(pts[i].coverage_pct);
    if (i === 0) ctx.moveTo(xx, yy);
    else ctx.lineTo(xx, yy);
  }
  ctx.stroke();

  // Fill below line
  ctx.lineTo(xpos(pts[pts.length - 1].t), bottom);
  ctx.lineTo(xpos(pts[0].t), bottom);
  ctx.closePath();
  ctx.fillStyle = 'rgba(108, 218, 237, 0.1)';
  ctx.fill();
}

// Start escape event cycle and extend history fetch to include coverage chart
if (typeof document !== 'undefined') {
  fetchEscapeEvents();
  setInterval(fetchEscapeEvents, 2000);

  // Patch renderHistoryCharts to also update coverage chart
  const _origRender = renderHistoryCharts;
  renderHistoryCharts = function() {
    _origRender();
    renderCoverageChart();
  };
}

// ── JSON data export ───────────────────────────────────────────────

async function exportTelemetryData() {
  const sources = [
    { key: 'memory', url: '/memory.json' },
    { key: 'flow', url: '/flow.json' },
    { key: 'events', url: '/events.json' },
    { key: 'history', url: '/history.json' },
    { key: 'bridge', url: '/bridge-status.json' },
    { key: 'metadata', url: '/metadata.json' },
  ];

  const payload = { exported_at: new Date().toISOString() };
  for (const src of sources) {
    try {
      const r = await fetch(src.url);
      if (r.ok) payload[src.key] = await r.json();
    } catch (_) {
      payload[src.key] = null;
    }
  }

  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `fly64-telemetry-${Date.now()}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// Wire export button
if (typeof document !== 'undefined') {
  const exportBtn = $('exportData');
  if (exportBtn) exportBtn.onclick = exportTelemetryData;
}

// ── Health strip update ──────────────────────────────────────────────

async function updateHealthStrip() {
  try {
    const r = await fetch('/memory.json');
    if (!r.ok) return;
    const d = await r.json();
    const hp = $('healthPill');
    if (hp) {
      const h = d.health_score !== undefined ? Math.round(d.health_score * 100) : 0;
      hp.textContent = `Health ${h}%`;
      hp.dataset.health = h > 60 ? 'high' : h > 30 ? 'mid' : 'low';
    }
    const rp = $('repulsionPill');
    if (rp) {
      const v = d.revisit_penalty !== undefined ? d.revisit_penalty : 0;
      rp.textContent = `↖ ${(v * 100).toFixed(0)}`;
    }
    const ap = $('anomalyPill');
    if (ap) {
      const state = d.anomaly_state || 'idle';
      ap.textContent = state === 'idle' ? '—' : state;
      ap.dataset.state = state === 'idle' ? '' : state;
    }
    // note-health bar was removed (health dedup: gauge + pill are the two
    // remaining, non-redundant presentations).
    const ns = $('noteStats');
    if (ns) {
      const v = d.revisit_penalty !== undefined ? d.revisit_penalty : 0;
      const state = d.anomaly_state || 'idle';
      // t16 P0-4: coach-breakout / reflex-ineffectiveness badges — these
      // memory fields existed but were never surfaced.
      const badges =
        (d.forced_bold_explore ? '<span class="note-stat" style="color:#ffca72">🏃 BOLD breakout</span>' : '') +
        (d.reflex_ineffective ? '<span class="note-stat" style="color:#ff7a7a">⚠ reflex ineffective</span>' : '');
      ns.innerHTML = '<span class="note-stat">↖ Repel ' + (v * 100).toFixed(0) + '</span><span class="note-stat">' + (state === 'idle' ? '⚪ OK' : '🔴 ' + state) + '</span>' + badges;
    }
    // Option B: health gauge
    renderHealthGauge(d.health_score !== undefined ? d.health_score : 0);
  } catch (_) {}
}

// ── Health gauge (Option B) ──────────────────────────────────────────

function renderHealthGauge(value) {
  const canvas = $('healthGauge');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  // Fixed pixel size — prevents canvas feedback-loop growth
  // (clientWidth → attribute ×dpr → clientWidth grows each frame if CSS missing)
  const size = 110;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const target = size * dpr;
  if (canvas.width !== target || canvas.height !== target) {
    canvas.width = target;
    canvas.height = target;
  }
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const w = size, h = size;
  const cx = w / 2, cy = h / 2, r = Math.min(cx, cy) - 8;
  ctx.clearRect(0, 0, w, h);
  // Background arc
  ctx.beginPath();
  ctx.arc(cx, cy, r, 0.75 * Math.PI, 2.25 * Math.PI);
  ctx.strokeStyle = '#1a2430';
  ctx.lineWidth = 12;
  ctx.stroke();
  // Value arc
  const val = Math.max(0, Math.min(1, value));
  const endAngle = 0.75 * Math.PI + val * 1.5 * Math.PI;
  ctx.beginPath();
  ctx.arc(cx, cy, r, 0.75 * Math.PI, endAngle);
  ctx.strokeStyle = val > 0.6 ? '#2a8a3a' : val > 0.3 ? '#b8860b' : '#8b2020';
  ctx.lineWidth = 12;
  ctx.lineCap = 'round';
  ctx.stroke();
  // Percentage text
  ctx.fillStyle = '#edf1f5';
  ctx.font = 'bold ' + Math.round(r * 0.5) + 'px -apple-system, sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(Math.round(val * 100) + '%', cx, cy - 4);
  ctx.fillStyle = '#aebac7';
  ctx.font = Math.round(r * 0.22) + 'px -apple-system, sans-serif';
  ctx.fillText('Health', cx, cy + Math.round(r * 0.35));
}

// Start health strip refresh
if (typeof document !== 'undefined') {
  updateHealthStrip();
  setInterval(updateHealthStrip, 2000);
}

// ── Scene identification + local motion display ──────────────────────

// t16 P2-1: single shared /flow.json fetch — the old code had two timers
// (updateSceneDisplay + updateEvolutionDisplay fallback) hitting the same
// endpoint every 2s.  Consumers read `latestFlow`.
let latestFlow = null;
let latestFlowPromise = null;
async function fetchFlowOnce() {
  try {
    const r = await fetch('/flow.json');
    if (r.ok) latestFlow = await r.json();
  } catch (_) {}
  return latestFlow;
}
function getFlow() {
  if (!latestFlowPromise)
    latestFlowPromise = fetchFlowOnce().finally(() => { latestFlowPromise = null; });
  return latestFlowPromise;
}

async function updateSceneDisplay() {
  try {
    const d = await getFlow();
    if (!d) return;
    const sn = $('sceneName');
    if (sn) {
      const name = d.scene_name || '…';
      const hash = d.scene_hash || '';
      const sv = d.skill_version || '';
      // t16 P1-2: terrain / underwater context chip (flow fields existed
      // but were never surfaced).
      const chips = [];
      if (d.terrain) chips.push('<span class="chip">' + d.terrain + '</span>');
      if (d.underwater) chips.push('<span class="chip chip-warn">🌊 underwater</span>');
      if (d.interactive_near) chips.push('<span class="chip chip-warn">door/sign near</span>');
      sn.innerHTML = 'Scene: ' + name + (hash ? ' · #' + hash : '') +
        (sv ? ' <span class="skill-tag">[Skill v' + sv + ']</span>' : '') +
        (chips.length ? ' ' + chips.join(' ') : '');
    }
    const lm = $('localMotion');
    if (lm) {
      const v = d.local_motion !== undefined ? d.local_motion : 0;
      const det = d.local_motion_detected;
      lm.innerHTML = 'Local motion: ' + v.toFixed(3) +
        (det ? ' <span class="motion-warn">⚠ moving object</span>' : ' <span class="motion-clear">(clear)</span>');
    }
    renderLlmDecision(d.llm_decision);
    // t19: SM64 freeze watchdog — red pill while the shared-memory bridge
    // is stale (frame seq stagnant >5s while the brain keeps ticking).
    const bs = $('bridgeStalePill');
    if (bs) bs.hidden = !d.bridge_stale;
  } catch (_) {}
}

// ── LLM dialogue decision pill (pause-wait mode) ─────────────────────

function renderLlmDecision(dec) {
  const pill = $('llmDecisionPill');
  if (typeof window !== 'undefined') window.__LLM_DECISION = dec || null;
  if (!pill) return;
  if (!dec || (!dec.status || dec.status === 'idle')) {
    pill.hidden = true;
    return;
  }
  const act = dec.action || '…';
  const icon = {press_a: '🅰', press_b: '🅱', none: '⏸'}[act] || '⏸';
  if (dec.status === 'waiting') {
    pill.hidden = false;
    pill.style.color = '#ffca72';
    // t16 P0-1: countdown against the 600 s budget
    const w = Math.round(dec.wait_s != null ? dec.wait_s : 0);
    pill.textContent = '🤖 LLM waiting ' + w + 's / 600s';
    pill.title = 'Dialogue detected — brain paused, waiting for GLM decision '
      + '(max 10 min, then autonomous A). Reason so far: ' + (dec.reason || '—');
  } else if (dec.status === 'decided') {
    pill.hidden = false;
    pill.style.color = '#4cdf7c';
    pill.textContent = icon + ' LLM ' + act;
    pill.title = 'LLM dialogue decision: ' + (dec.reason || act);
  } else {  // timeout
    pill.hidden = false;
    pill.style.color = '#ff7a7a';
    pill.textContent = '⏱ LLM timeout → A';
    pill.title = 'LLM decision timed out — autonomous A-press fallback. '
      + (dec.reason || '');
  }
}

if (typeof document !== 'undefined') {
  updateSceneDisplay();
  setInterval(updateSceneDisplay, 2000);
}

// ── Evolution iteration history + brain version ──────────────────────

async function updateEvolutionDisplay() {
  try {
    let r = await fetch('/evolution.json');
    let d = r.ok ? await r.json() : {};
    if (!d.brain_version) {
      // t16 P2-1: reuse the shared flow snapshot instead of a second fetch
      const fr = await getFlow();
      if (fr) d.brain_version = fr.brain_version;
    }
    const bv = $('brainVerPill');
    if (bv) bv.textContent = 'Brain v' + (d.brain_version || '—');
    const iters = d.iterations || [];
    const ep = $('evoIterPill');
    if (ep) ep.textContent = 'EVO #' + iters.length;
    const hist = $('evoHistory');
    if (hist) {
      hist.innerHTML = iters.slice().reverse().map(it => {
        const caps = (it.capabilities || []).join(' ');
        return '<div class="evo-item">#' + it.iter + ' v' + (it.brain_version || '?') +
          ' · ' + (it.time || '') + '<br><span class="evo-cap">' +
          (caps || 'no findings') + '</span></div>';
      }).join('') || '<div class="evo-item">no iterations yet</div>';
    }
  } catch (_) {}
}

if (typeof document !== 'undefined') {
  updateEvolutionDisplay();
  setInterval(updateEvolutionDisplay, 3000);
}

// ── L2 coach-help: SOS badge + snapshot panel ────────────────────────

let lastHelpB64 = '';

// Raw-RGB base64 → browser-decodable data URI.  Accepts either an already
// encoded image (PNG magic returned as-is) or a raw w*h*3 byte string, which
// is painted through a canvas + toDataURL.  This is the conversion the coach
// snapshot thumbnail needs (backend sends raw RGB, no PNG header).
// flipY: the game-side screen capture is raw glReadPixels output, which is
// bottom-up (the cubemap atlas path flips its rows, the screen path does not),
// so the screen thumbnail needs an explicit vertical flip.
function snapshotDataUri(b64, w, h, label, flipY) {
  try {
    const bin = atob(b64);
    const n = bin.length;
    if (n > 8 && bin.charCodeAt(0) === 0x89 && bin.charCodeAt(1) === 0x50)
      return 'data:image/png;base64,' + b64;           // already PNG/JPEG/etc.
    if (n !== w * h * 3) return '';
    const rgb = new Uint8Array(n);
    for (let i = 0; i < n; i++) rgb[i] = bin.charCodeAt(i);
    const cv = document.createElement('canvas');
    cv.width = w; cv.height = h;
    const ctx = cv.getContext('2d');
    const frame = ctx.createImageData(w, h);
    const rowBytes = w * 3;
    for (let y = 0; y < h; y++) {
      const srcRow = flipY ? (h - 1 - y) : y;
      for (let x = 0; x < w; x++) {
        const s = srcRow * rowBytes + x * 3, o = (y * w + x) * 4;
        frame.data[o] = rgb[s]; frame.data[o + 1] = rgb[s + 1];
        frame.data[o + 2] = rgb[s + 2]; frame.data[o + 3] = 255;
      }
    }
    ctx.putImageData(frame, 0, 0);
    const img = $('helpFrame');
    if (img) img.title = 'coach snapshot · ' + label + ' · ' + w + '×' + h + (flipY ? ' · flipped' : '');
    return cv.toDataURL('image/png');
  } catch (error) { return ''; }
}

export function renderHelpSnapshot(d) {
  const pill = $('helpPill');
  const panel = $('helpPanel');
  if (!pill || !panel) return !!d && d.help_reason != null;
  const active = !!d && d.help_reason != null;
  pill.hidden = !active;
  panel.hidden = !active;
  // Auto-expand the <details> fold when a help request becomes active so the
  // snapshot thumbnail is immediately visible without a manual click.
  const fold = $('helpFold');
  if (fold) fold.open = active;
  if (!active) return false;
  const pos = d.position || {};
  const posTxt = (pos.x !== undefined ? `x=${pos.x} ` : '') +
    (pos.y !== undefined ? `y=${pos.y} ` : '') + (pos.z !== undefined ? `z=${pos.z}` : '');
  const fields = [
    ['scene', d.scene_name || '—'],
    ['position', posTxt || '—'],
    ['reason', d.help_reason],
    ['diagnosis', d.diagnosis || '—'],
    ['ts', d.ts != null ? new Date(d.ts * 1000).toLocaleTimeString() : '—'],
  ];
  const dl = $('helpFields');
  if (dl) dl.innerHTML = fields.map(([k, v]) =>
    `<dt>${k}</dt><dd title="${String(v).replace(/"/g, '&quot;')}">${v}</dd>`).join('');
  const img = $('helpFrame');
  if (img) {
    // Backend contract: frame_b64 / screen_b64 are RAW RGB byte strings
    // (128×128×3 forward cubemap face, 320×240×3 game screen) — NOT PNG.
    // Prefixing them with data:image/png never decoded, which is why the
    // coach snapshot had no thumbnail.  screen_b64 (real game view showing
    // Mario) is preferred; the cubemap face is the fallback.
    const src = d.screen_b64 ? snapshotDataUri(d.screen_b64, 320, 240, 'screen', true)
              : d.frame_b64 ? snapshotDataUri(d.frame_b64, 128, 128, 'cubemap face')
              : '';
    if (src && src !== lastHelpB64) {
      lastHelpB64 = src;
      img.src = src;
      img.hidden = false;
    } else if (!src) {
      img.removeAttribute('src');
    }
  }
  const rl = $('helpReasonLabel');
  if (rl) rl.textContent = d.help_reason || '';
  return true;
}

async function updateHelpDisplay() {
  try {
    const r = await fetch('/help.json');
    if (!r.ok) { renderHelpSnapshot(null); return; }
    renderHelpSnapshot(await r.json());
  } catch (_) {}
}

if (typeof document !== 'undefined') {
  updateHelpDisplay();
  setInterval(updateHelpDisplay, 2000);
  const hp = $('helpPill');
  if (hp) hp.onclick = () => {
    const p = $('helpPanel');
    if (p) p.hidden = !p.hidden;
  };
}

// ── LLM coach advice (fly64-mhr plugin /coach_advice.json) ───────────

function renderCoachAdvice(d) {
  const panel = $('coachPanel');
  if (!panel) return;
  const advice = (d && typeof d.advice === 'string') ? d.advice : '';
  panel.hidden = !advice;
  if (!advice) return;
  const ml = $('coachModelLabel');
  if (ml) ml.textContent = d.model ? ' · ' + d.model : '';
  const txt = $('coachAdviceText');
  if (txt) txt.textContent = advice;
  const hist = $('coachHistory');
  if (hist) {
    const items = Array.isArray(d.history) ? d.history.slice().reverse() : [];
    hist.innerHTML = items.map(h => {
      const t = h.ts != null ? new Date(h.ts * 1000).toLocaleTimeString() : '';
      const a = String(h.advice || '').slice(0, 140);
      return '<div class="evo-item">' + t + '<br><span class="evo-cap">' +
        a.replace(/&/g, '&amp;').replace(/</g, '&lt;') + '</span></div>';
    }).join('') || '<div class="evo-item">no consultations yet</div>';
  }
}

async function updateCoachAdviceDisplay() {
  try {
    const r = await fetch('/coach_advice.json');
    if (!r.ok) { renderCoachAdvice(null); return; }
    renderCoachAdvice(await r.json());
  } catch (_) {}
}

if (typeof document !== 'undefined') {
  updateCoachAdviceDisplay();
  setInterval(updateCoachAdviceDisplay, 5000);
}

// ── Coach strategy consumption panel (t16 P0-2) ──────────────────────
// Surfaces the operator keys from /active_strategy.json (served from
// skills/active_strategy.json by the brain's HTTP endpoint): what the
// coach last advised, when, and how it is being consumed — closing the
// "coach said it → is it working?" visibility loop.

async function updateCoachStrategy() {
  const fields = $('strategyFields');
  if (!fields) return;
  try {
    const r = await fetch('/active_strategy.json');
    if (!r.ok) { fields.innerHTML = '<span class="muted">/active_strategy.json unavailable</span>'; return; }
    const d = await r.json();
    const ex = d.exploration || {};
    const esc = d.escape || {};
    const dd = d.dialogue_decision;
    const row = (k, v, unit) => '<span class="note-stat"><b>' + k + '</b> ' + v +
      (unit ? ' <span class="muted">' + unit + '</span>' : '') + '</span>';
    const rows = [
      row('bold_explore_stuck_s', ex.bold_explore_stuck_s != null ? ex.bold_explore_stuck_s : '—', 's · smaller = faster breakout'),
      row('turn_bias', ex.turn_bias != null ? ex.turn_bias : '—', '0-1 strength'),
      row('stuck_threshold_s', esc.stuck_threshold_s != null ? esc.stuck_threshold_s : '—', 's · smaller = faster escape'),
    ];
    // EVO R21: surface fallen_recovery strategy (was hidden before)
    const fr = d.fallen_recovery;
    if (fr && fr.mode) rows.splice(1, 0,
      row('climb_mode', fr.mode, ''),
      row('climb_period', fr.climb_period != null ? fr.climb_period : '—', 's'),
      row('persist_seconds', fr.persist_seconds != null ? fr.persist_seconds : '—', 's'),
    );
    if (dd) rows.push(row('dialogue_decision', dd.action + (dd.timed_out ? ' (timeout→A)' : ''), dd.reason || ''));
    if (d.advice_ts) rows.push('<span class="note-stat muted">last write ' + new Date(d.advice_ts * 1000).toLocaleTimeString() + '</span>');
    fields.innerHTML = rows.join('');
    const src = $('strategySourceLabel');
    if (src) src.textContent = d.source ? '· ' + d.source : '';
  } catch (_) {}
}

if (typeof document !== 'undefined') {
  updateCoachStrategy();
  setInterval(updateCoachStrategy, 5000);
}

// ── Consult frame thumbnails (t21 wrap-up UI) ────────────────────────
// Lists runtime/coach_frames/*.png via /coach_frames (JSON index) and
// renders thumbnails inside the Coach Help Snapshot panel; clicking one
// opens the full-size frame (/coach_frames/<name>) in a new tab.

async function updateCoachFrames() {
  const host = $('coachFrames');
  if (!host) return;
  try {
    const r = await fetch('/coach_frames');
    if (!r.ok) return;
    const d = await r.json();
    const frames = Array.isArray(d.frames) ? d.frames : [];
    if (!frames.length) { host.innerHTML = '<span class="muted">No consult frames yet</span>'; return; }
    host.innerHTML = frames.slice(0, 8).map(f => {
      const m = /coach_(\d+(?:\.\d+)?)_(.+)\.png$/.exec(f);
      const t = m ? new Date(parseFloat(m[1]) * 1000).toLocaleString() : '';
      const reason = m ? m[2] : f;
      const safe = f.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
      return '<a href="/coach_frames/' + safe + '" target="_blank" rel="noopener" title="'
        + (t ? t + ' · ' : '') + reason + '">'
        + '<img src="/coach_frames/' + safe + '" alt="consult frame">'
        + '<span class="frame-name">' + reason + '</span></a>';
    }).join('');
  } catch (_) {}
}

if (typeof document !== 'undefined') {
  updateCoachFrames();
  setInterval(updateCoachFrames, 5000);
}
