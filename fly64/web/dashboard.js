const $ = id => document.getElementById(id);
const CYAN = '#6cdaed', GOLD = '#ffca72', INK = '#f0f4f8', MUTED = '#b0bdcc';
const states = ['off · F8', 'receiving', 'stale · released', 'torn · released', 'disconnected'];
let meta, latest, displayed, history = [], frozen = false, receivedAt = 0, lastSeq = 0, brainRenderer, measuredLocations, streamError = '';
const number = (n, digits=1) => Number.isFinite(n) ? n.toFixed(digits) : '—';

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
  const canvas=$(id),ctx=canvas.getContext('2d'),w=canvas.clientWidth,h=canvas.clientHeight,d=window.devicePixelRatio||1;
  canvas.width=Math.round(w*d);canvas.height=Math.round(h*d);ctx.scale(d,d);
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
  image('retina',packet.eyes);image('change',packet.change);
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
  $('gameState').textContent=`Game: ${states[r.game_state]||'unknown'}`;
  $('jumpState').textContent=`A: gold request / cyan received${r.game_state===1?` · ack ${number(r.game_age,0)} ms`:''}`;
  const key=$('population').value,ids=key==='all'?null:meta.groups[key],total=ids?ids.length:meta.n;
  const located=ids?ids.filter(i=>measuredLocations[i]).length:meta.measured;
  $('populationInfo').textContent=`${located.toLocaleString()} located · ${(total-located).toLocaleString()} unlocated`;
  const rate=key==='all'?packet.activity.reduce((a,b)=>a+b,0)/meta.n/255*50:r[key];
  $('populationRate').textContent=`Mean ${number(rate)} Hz${key==='all'?' ≈':''} · ${d.window_ticks*20} ms`;
  brainRenderer?.(packet.activity);
  $('performance').textContent=`${number(r.t,1)} s · ${number(d.rtf,2)}× real time · step ${number(d.latency_ms)} ms · ${number(d.rss_mb,0)} MB · ${d.dropped} dropped`;
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
  $('freeze').onclick=()=>{frozen=!frozen;$('freeze').textContent=frozen?'Resume live':'Freeze display';if(!frozen&&latest){history=latest.data.rows.slice();render(latest);}};
  $('population').onchange=()=>{if(displayed)render(displayed);};
  window.addEventListener('resize',()=>{if(displayed)render(displayed);});
  setInterval(()=>{const stale=!receivedAt||performance.now()-receivedAt>1000;$('status').textContent=streamError||(stale?'Disconnected / stale':frozen?'Display frozen · game runs':'Live');$('status').dataset.state=stale?'bad':'ok';},250);
}
if (typeof document !== 'undefined') start().catch(error=>{$('status').textContent=error.message;$('status').dataset.state='bad';});
