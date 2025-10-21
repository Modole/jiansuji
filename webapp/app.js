(function(){
  const ENDPOINT = 'http://127.0.0.1:1880/get/datas';
  const CMD_ENDPOINT = 'http://127.0.0.1:1880/set/data';
  const KEYS_STATIC = ['unidirectional_error','lost_motion','backlash','torsional_stiffness'];
  const KEYS_DYNAMIC = ['start_torque','no_load_accuracy','variable_load_accuracy','peak_load_accuracy','transmission_efficiency','noise_level'];
  const ALL_KEYS = [...KEYS_STATIC, ...KEYS_DYNAMIC];

  let autoStaticTimer = null;
  let autoDynamicTimer = null;
  let pointsMap = null; // 从 config 加载
  let commandsMap = null; // 命令映射

  // 路由
  function showPage(hash){
    const pageId = (hash || '#home').replace('#','');
    document.querySelectorAll('.page').forEach(p => p.classList.add('hidden'));
    const el = document.getElementById(`page-${pageId}`);
    if(el) el.classList.remove('hidden');
  }

  function setActiveNav(){
    const hash = location.hash || '#home';
    document.querySelectorAll('.nav-link').forEach(a => {
      if(a.getAttribute('href') === hash) a.classList.add('active');
      else a.classList.remove('active');
    });
  }

  window.addEventListener('hashchange', () => { showPage(location.hash); setActiveNav(); resizeAllCharts(); });

  // 状态显示
  function setConnStatus(ok, ts){
    const dot = document.getElementById('conn-status');
    const last = document.getElementById('last-update');
    dot.classList.remove('online','offline');
    dot.classList.add(ok ? 'online' : 'offline');
    last.textContent = ok ? `最近更新时间：${formatTs(ts)}` : '未连接';
  }
  function formatTs(ts){
    try { return new Date(ts || Date.now()).toLocaleString(); } catch(e){ return String(ts || ''); }
  }

  function showToast(msg, type){
    const host = document.getElementById('toast-container');
    if(!host) return;
    const el = document.createElement('div');
    el.className = `toast ${type || ''}`.trim();
    el.textContent = msg;
    host.appendChild(el);
    setTimeout(() => {
      el.style.opacity = '0';
      el.style.transition = 'opacity 200ms';
      setTimeout(() => host.removeChild(el), 220);
    }, 2200);
  }

  // 加载点位映射
  async function loadPointsMap(){
    try{
      const res = await fetch('./config/points-mapping.json');
      pointsMap = await res.json();
    }catch(e){
      console.warn('加载点位映射失败，使用默认占位', e);
      pointsMap = {};
      ALL_KEYS.forEach(k => pointsMap[k] = `ADDR_${k.toUpperCase()}`);
    }
  }

  async function loadCommandsMap(){
    try{
      const res = await fetch('./config/commands-mapping.json');
      commandsMap = await res.json();
    }catch(e){
      console.warn('加载命令映射失败，使用默认占位', e);
      commandsMap = {
        set_load_level: { address: 'CMD_SET_LOAD' },
        set_speed_rpm: { address: 'CMD_SET_SPEED' },
        start_test: { address: 'CMD_START' },
        stop_test: { address: 'CMD_STOP' },
        emergency_stop: { address: 'CMD_ESTOP' },
        reset: { address: 'CMD_RESET' },
        sample_static: { address: 'CMD_SAMPLE_STATIC' }
      };
    }
  }

  // 统一接口 POST
  async function fetchPostJson(url, payload){
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload || {})
    });
    if(!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  }

  async function sendCommand(cmd, params){
    try{
      const meta = commandsMap?.[cmd] || {};
      const payload = { cmd, params: params || {}, addr: meta.address || meta.addr };
      const raw = await fetchPostJson(CMD_ENDPOINT, payload);
      showToast(`命令已下发：${cmd}`, 'success');
      return raw;
    }catch(e){
      console.error('命令下发失败', e);
      showToast(`命令失败：${cmd}`, 'error');
      throw e;
    }
  }

  // 数据归一化
  function normalizeData(raw){
    const out = { timestamp: Date.now(), values: {} };
    if(!raw) return out;
    // 常见结构适配
    if(raw.timestamp) out.timestamp = raw.timestamp;
    if(raw.values && typeof raw.values === 'object') {
      out.values = raw.values;
      return out;
    }
    // 数组 points
    if(Array.isArray(raw.points || raw.data)){
      const arr = raw.points || raw.data;
      arr.forEach(p => {
        const key = p.key || p.name || p.addr || '';
        if(!key) return;
        out.values[key] = { addr: p.addr, value: p.value, unit: p.unit };
      });
      return out;
    }
    // 兜底：直接认为 raw 是 values
    if(typeof raw === 'object') {
      out.values = raw;
    }
    return out;
  }

  // 本地 Mock（接口不可用时）
  function makeMock(){
    const rnd = (min,max)=> (min + Math.random()*(max-min));
    const now = Date.now();
    const values = {
      unidirectional_error: { addr: pointsMap?.unidirectional_error, value: rnd(0.01,0.08), unit: 'arcmin' },
      lost_motion: { addr: pointsMap?.lost_motion, value: rnd(0.01,0.08), unit: 'arcmin' },
      backlash: { addr: pointsMap?.backlash, value: rnd(0.005,0.05), unit: 'arcmin' },
      torsional_stiffness: { addr: pointsMap?.torsional_stiffness, value: rnd(8,18), unit: 'N·m/deg' },
      start_torque: { addr: pointsMap?.start_torque, value: rnd(0.2,0.8), unit: 'N·m' },
      no_load_accuracy: { addr: pointsMap?.no_load_accuracy, value: rnd(0.02,0.08), unit: 'arcmin' },
      variable_load_accuracy: { addr: pointsMap?.variable_load_accuracy, value: rnd(0.03,0.12), unit: 'arcmin', load_level: [25,50,75,100][Math.floor(Math.random()*4)] },
      peak_load_accuracy: { addr: pointsMap?.peak_load_accuracy, value: rnd(0.04,0.15), unit: 'arcmin' },
      transmission_efficiency: { addr: pointsMap?.transmission_efficiency, value: rnd(85,97), unit: '%' },
      noise_level: { addr: pointsMap?.noise_level, value: rnd(55,70), unit: 'dB(A)' }
    };
    return { timestamp: now, values };
  }

  // 轻量趋势图
  const chartStore = {}; // { key: { canvas, data: [], color } }
  const MAX_POINTS = 120;

  function pickColor(key){
    return KEYS_STATIC.includes(key) ? '#2563eb' : '#16a34a';
  }
  function setupChartCanvas(canvas){
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth || canvas.parentElement?.clientWidth || 320;
    const h = canvas.clientHeight || 80;
    canvas.width = Math.floor(w * dpr);
    canvas.height = Math.floor(h * dpr);
    const ctx = canvas.getContext('2d');
    ctx.setTransform(dpr,0,0,dpr,0,0);
    return { ctx, w, h };
  }
  function initCharts(){
    document.querySelectorAll('.chart[data-key]').forEach(cv => {
      const key = cv.dataset.key;
      chartStore[key] = chartStore[key] || { canvas: cv, data: [], color: pickColor(key) };
      drawChart(key); // 初始空图
    });
  }
  function pushChartData(key, value){
    if(value == null || !Number.isFinite(Number(value))) return;
    const entry = chartStore[key];
    if(!entry) return;
    entry.data.push(Number(value));
    if(entry.data.length > MAX_POINTS) entry.data.shift();
  }
  function drawChart(key){
    const entry = chartStore[key];
    if(!entry || !entry.canvas) return;
    const { ctx, w, h } = setupChartCanvas(entry.canvas);
    ctx.clearRect(0,0,w,h);
    const data = entry.data;
    if(!data || data.length < 2) {
      ctx.fillStyle = '#9ca3af';
      ctx.font = '12px system-ui';
      ctx.fillText('等待数据...', 10, h/2);
      return;
    }
    const min = Math.min(...data);
    const max = Math.max(...data);
    const span = max - min;
    const pad = span === 0 ? (Math.abs(max) * 0.1 + 1e-6) : span * 0.1;
    const yMin = min - pad;
    const yMax = max + pad;
    const dx = w / (data.length - 1);

    // 背景网格
    ctx.strokeStyle = '#e5e7eb';
    ctx.lineWidth = 1;
    ctx.beginPath();
    for(let i=1;i<4;i++){
      const y = (h/4) * i;
      ctx.moveTo(0,y); ctx.lineTo(w,y);
    }
    ctx.stroke();

    // 绘制曲线
    ctx.strokeStyle = entry.color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    data.forEach((v,i) => {
      const x = i * dx;
      const y = h - ( (v - yMin) / (yMax - yMin) ) * h;
      if(i === 0) ctx.moveTo(x,y); else ctx.lineTo(x,y);
    });
    ctx.stroke();

    // 末端点
    const lastX = (data.length - 1) * dx;
    const lastY = h - ( (data[data.length-1] - yMin) / (yMax - yMin) ) * h;
    ctx.fillStyle = entry.color;
    ctx.beginPath(); ctx.arc(lastX, lastY, 3, 0, Math.PI*2); ctx.fill();
  }
  function resizeAllCharts(){ Object.keys(chartStore).forEach(drawChart); }

  // 更新卡片显示
  function updateCards(packet){
    const { timestamp, values } = packet || {};
    setConnStatus(!!values, timestamp);
    ALL_KEYS.forEach(key => {
      const valEl = document.querySelector(`.value[data-key="${key}"]`);
      const tsEl = document.querySelector(`.timestamp[data-key-ts="${key}"]`);
      const v = values?.[key]?.value;
      if(valEl) valEl.textContent = (v == null ? '--' : Number(v).toFixed(3));
      if(tsEl) tsEl.textContent = formatTs(timestamp);

      // 推送到趋势图并重绘
      if(v != null) {
        pushChartData(key, Number(v));
        drawChart(key);
      }

      if(key === 'variable_load_accuracy'){
        const lvlEl = document.getElementById('var-load-level');
        if(lvlEl) {
          const lvl = values?.[key]?.load_level;
          lvlEl.textContent = `载荷：${lvl == null ? '--' : lvl}`;
        }
      }
    });
  }

  // 手动刷新（按页面 key 列表发送）
  async function refresh(keys){
    try{
      const payload = { keys, addrs: keys.map(k => pointsMap?.[k]).filter(Boolean) };
      const raw = await fetchPostJson(ENDPOINT, payload);
      const packet = normalizeData(raw);
      updateCards(packet);
    }catch(e){
      console.warn('接口异常，使用本地Mock', e);
      updateCards(makeMock());
    }
  }

  function bindToolbar(){
    const sBtn = document.getElementById('static-refresh');
    const sAuto = document.getElementById('static-auto');
    const dBtn = document.getElementById('dynamic-refresh');
    const dAuto = document.getElementById('dynamic-auto');

    sBtn?.addEventListener('click', () => refresh(KEYS_STATIC));
    dBtn?.addEventListener('click', () => refresh(KEYS_DYNAMIC));

    sAuto?.addEventListener('change', (ev) => {
      if(ev.target.checked){
        autoStaticTimer && clearInterval(autoStaticTimer);
        autoStaticTimer = setInterval(() => refresh(KEYS_STATIC), 1500);
      } else {
        autoStaticTimer && clearInterval(autoStaticTimer);
        autoStaticTimer = null;
      }
    });
    dAuto?.addEventListener('change', (ev) => {
      if(ev.target.checked){
        autoDynamicTimer && clearInterval(autoDynamicTimer);
        autoDynamicTimer = setInterval(() => refresh(KEYS_DYNAMIC), 1500);
      } else {
        autoDynamicTimer && clearInterval(autoDynamicTimer);
        autoDynamicTimer = null;
      }
    });
  }

  function bindControls(){
    // 静态页
    document.getElementById('cmd-sample-static')?.addEventListener('click', async () => {
      try{ await sendCommand('sample_static'); refresh(KEYS_STATIC); }catch(e){}
    });
    document.getElementById('cmd-reset-static')?.addEventListener('click', () => {
      sendCommand('reset', { scope: 'static' });
    });

    // 动态页
    const loadInput = document.getElementById('cmd-load-level');
    const speedInput = document.getElementById('cmd-speed-rpm');
    const typeSelect = document.getElementById('cmd-test-type');

    document.getElementById('cmd-set-load')?.addEventListener('click', async () => {
      const val = Number(loadInput?.value);
      if(Number.isFinite(val)) { await sendCommand('set_load_level', { level: val }); }
      else { showToast('请输入有效载荷等级(数字)', 'error'); }
    });
    document.getElementById('cmd-set-speed')?.addEventListener('click', async () => {
      const val = Number(speedInput?.value);
      if(Number.isFinite(val)) { await sendCommand('set_speed_rpm', { rpm: val }); }
      else { showToast('请输入有效转速(数字)', 'error'); }
    });
    document.getElementById('cmd-start')?.addEventListener('click', async () => {
      const payload = {
        test_type: typeSelect?.value || 'start_torque',
        level: Number(loadInput?.value),
        rpm: Number(speedInput?.value)
      };
      await sendCommand('start_test', payload);
      refresh(KEYS_DYNAMIC);
    });
    document.getElementById('cmd-stop')?.addEventListener('click', () => {
      sendCommand('stop_test');
    });
    document.getElementById('cmd-estop')?.addEventListener('click', () => {
      sendCommand('emergency_stop');
    });
    document.getElementById('cmd-reset')?.addEventListener('click', () => {
      sendCommand('reset', { scope: 'dynamic' });
    });
  }

  async function init(){
    showPage(location.hash || '#home');
    setActiveNav();
    await loadPointsMap();
    await loadCommandsMap();
    bindToolbar();
    bindControls();
    initCharts();
    window.addEventListener('resize', resizeAllCharts);
    // 首次刷新一次，便于显示
    refresh(ALL_KEYS);
  }

  document.addEventListener('DOMContentLoaded', init);
})();

// 曲线与导出模块
const curveStore = { hysteresis: [] };

function exportCSV(rows, filename) {
  if (!Array.isArray(rows) || rows.length === 0) return;
  const csv = rows.map(r => r.map(x => x == null ? '' : String(x)).join(',')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const a = document.createElement('a');
  const url = URL.createObjectURL(blob);
  a.href = url; a.download = filename; document.body.appendChild(a); a.click();
  setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 0);
}

async function fetchGetJson(url) { const r = await fetch(url, { cache: 'no-store' }); if (!r.ok) throw new Error('HTTP '+r.status); return r.json(); }

function collectCurrentValues(pageId) {
  const page = document.getElementById(pageId);
  const cards = page ? page.querySelectorAll('.card') : [];
  const ts = new Date().toISOString().replace('T',' ').replace('Z','');
  const rows = [["时间", ts]];
  cards.forEach(card => {
    const titleEl = card.querySelector('h3');
    const valEl = card.querySelector('.value');
    const title = titleEl ? titleEl.textContent.trim() : '';
    const value = valEl ? valEl.textContent.trim() : '';
    rows.push([title, value]);
  });
  return rows;
}

function exportStaticCSV() { const rows = collectCurrentValues('page-static'); exportCSV(rows, `静态结果_${Date.now()}.csv`); showToast('静态结果已导出', 'success'); }
function exportDynamicCSV() { const rows = collectCurrentValues('page-dynamic'); exportCSV(rows, `动态结果_${Date.now()}.csv`); showToast('动态结果已导出', 'success'); }

async function fetchHysteresisPoints() {
  try {
    const resp = await fetchGetJson('/get/datas?hysteresis=1');
    if (resp && resp.hysteresis && Array.isArray(resp.hysteresis)) {
      return resp.hysteresis;
    }
  } catch (e) { /* fallback to mock */ }
  return makeMockHysteresis();
}

function makeMockHysteresis(count=240, T=10, backlash=0.6, k=0.8) {
  const pts = [];
  for (let i=0;i<count;i++){
    const u = i/(count-1);
    const half = (u < 0.5);
    const t = half ? (u*2*T - T) : ((u-0.5)*2*T - T); // -T..+T..-T
    const hysteresisOffset = (t>=0 ? backlash/2 : -backlash/2);
    const angle = k*t + hysteresisOffset + 0.1*Math.sin(4*u*Math.PI);
    pts.push({ angle, torque: t });
  }
  return pts;
}

function drawXYCurve(canvasId, points, opts={}) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const dpr = window.devicePixelRatio || 1;
  canvas.width = canvas.clientWidth * dpr;
  canvas.height = canvas.clientHeight * dpr;
  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr,0,0,dpr,0,0);
  ctx.clearRect(0,0,canvas.clientWidth, canvas.clientHeight);
  const pad = 40;
  const w = canvas.clientWidth - pad*2;
  const h = canvas.clientHeight - pad*2;
  if (w <= 0 || h <= 0 || !points || points.length < 2) return;
  const xs = points.map(p => p.angle);
  const ys = points.map(p => p.torque);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const scaleX = v => pad + (w * (v - minX)) / ((maxX - minX) || 1);
  const scaleY = v => pad + h - (h * (v - minY)) / ((maxY - minY) || 1);
  // axes
  ctx.strokeStyle = '#cbd5e1'; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(pad, pad); ctx.lineTo(pad, pad+h); ctx.lineTo(pad+w, pad+h); ctx.stroke();
  // polyline
  ctx.strokeStyle = '#2563eb'; ctx.lineWidth = 2; ctx.beginPath();
  points.forEach((p, i) => { const x = scaleX(p.angle), y = scaleY(p.torque); if (i===0) ctx.moveTo(x,y); else ctx.lineTo(x,y); });
  ctx.stroke();
  // labels
  ctx.fillStyle = '#374151'; ctx.font = '12px system-ui';
  if (opts.xLabel) ctx.fillText(opts.xLabel, pad+w-36, pad+h+24);
  if (opts.yLabel) ctx.fillText(opts.yLabel, 8, pad+12);
}

function openCurveModalHysteresis() {
  const modal = document.getElementById('curve-modal');
  const title = document.getElementById('modal-title');
  title.textContent = '滞回曲线（扭矩-角位移）';
  modal.classList.remove('hidden');
  setTimeout(async () => {
    const points = await fetchHysteresisPoints();
    curveStore.hysteresis = points;
    drawXYCurve('curve-canvas', points, { xLabel:'角位移', yLabel:'扭矩' });
  }, 0);
}

function closeCurveModal() { const modal = document.getElementById('curve-modal'); modal.classList.add('hidden'); }
function exportHysteresisCSV() {
  const pts = (curveStore.hysteresis && curveStore.hysteresis.length) ? curveStore.hysteresis : makeMockHysteresis();
  const rows = [["角位移","扭矩"], ...pts.map(p => [p.angle, p.torque])];
  exportCSV(rows, `滞回曲线_${Date.now()}.csv`);
  showToast('滞回曲线已导出', 'success');
}

// 检测状态条
function setTestingState(on, labelText) {
  const el = document.getElementById('test-status');
  const label = document.getElementById('test-type-label');
  if (!el || !label) return;
  label.textContent = labelText || '--';
  if (on) el.classList.remove('hidden'); else el.classList.add('hidden');
}
function currentTestLabel() {
  const L = document.getElementById('dyn-load')?.value || '';
  const N = document.getElementById('dyn-speed')?.value || '';
  const cycles = document.getElementById('dyn-cycles')?.value || '';
  return `L=${L}, N=${N}, 周期=${cycles}`;
}

// 事件绑定（新增）
window.addEventListener('DOMContentLoaded', () => {
  document.getElementById('static-view-hysteresis')?.addEventListener('click', openCurveModalHysteresis);
  document.getElementById('modal-close')?.addEventListener('click', closeCurveModal);
  document.querySelector('#curve-modal .modal-overlay')?.addEventListener('click', closeCurveModal);
  document.getElementById('curve-export-csv')?.addEventListener('click', exportHysteresisCSV);
  document.getElementById('static-export-csv')?.addEventListener('click', exportStaticCSV);
  document.getElementById('dynamic-export-csv')?.addEventListener('click', exportDynamicCSV);
  document.getElementById('static-export-hysteresis')?.addEventListener('click', exportHysteresisCSV);
  document.getElementById('start-test')?.addEventListener('click', () => setTestingState(true, currentTestLabel()));
  document.getElementById('stop-test')?.addEventListener('click', () => setTestingState(false));
  document.getElementById('emergency-stop')?.addEventListener('click', () => setTestingState(false));
  document.getElementById('reset-btn')?.addEventListener('click', () => setTestingState(false));
});

window.addEventListener('resize', () => {
  const modal = document.getElementById('curve-modal');
  if (modal && !modal.classList.contains('hidden') && curveStore.hysteresis.length) {
    drawXYCurve('curve-canvas', curveStore.hysteresis, { xLabel:'角位移', yLabel:'扭矩' });
  }
});