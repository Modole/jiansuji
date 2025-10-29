(function(){
  const ENDPOINT = '/api/data/measurements';
   const CMD_ENDPOINT = '/api/command/set/data';
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
      const res = await fetch('/static/config/points-mapping.json');
      pointsMap = await res.json();
    }catch(e){
      console.warn('加载点位映射失败，使用默认占位', e);
      pointsMap = {};
      ALL_KEYS.forEach(k => pointsMap[k] = `ADDR_${k.toUpperCase()}`);
    }
  }

  async function loadCommandsMap(){
    try{
      const res = await fetch('/static/config/commands-mapping.json');
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
      // 后端要求字段名为 `command`
      const payload = { command: cmd, ...(params || {}), addr: meta.address || meta.addr };
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
    const h = canvas.clientHeight || 120;
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
      // 确保canvas尺寸正确设置
      setTimeout(() => {
        setupChartCanvas(cv);
        drawChart(key); // 初始空图
      }, 100);
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
    for(let i=1;i<6;i++){
      const x = (w/6) * i;
      ctx.moveTo(x,0); ctx.lineTo(x,h);
    }
    ctx.stroke();

    // 底部轴线
    ctx.strokeStyle = '#cbd5e1';
    ctx.beginPath(); ctx.moveTo(0, h-0.5); ctx.lineTo(w, h-0.5); ctx.stroke();

    // 绘制曲线
    ctx.strokeStyle = entry.color;
    ctx.lineWidth = 2.5; ctx.lineJoin='round'; ctx.lineCap='round';
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

    // 新增：静/动页导出 & 滞回查看（确保动态加载后可用）
    document.getElementById('static-view-hysteresis')?.addEventListener('click', openCurveModalHysteresis);
    document.getElementById('static-export-csv')?.addEventListener('click', exportStaticCSV);
    document.getElementById('static-export-hysteresis')?.addEventListener('click', exportHysteresisCSV);
    document.getElementById('dynamic-export-csv')?.addEventListener('click', exportDynamicCSV);
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
      setTestingState(true, currentTestLabel());
    });
    document.getElementById('cmd-stop')?.addEventListener('click', () => {
      sendCommand('stop_test');
      setTestingState(false);
    });
    document.getElementById('cmd-estop')?.addEventListener('click', () => {
      sendCommand('emergency_stop');
      setTestingState(false);
    });
    document.getElementById('cmd-reset')?.addEventListener('click', () => {
      sendCommand('reset', { scope: 'dynamic' });
      setTestingState(false);
    });
  }

  async function init(){
    showPage(location.hash || '#home');
    setActiveNav();
    await loadPointsMap();
    await loadCommandsMap();
    await loadMotorModels();
    initHeaderMotorSelect();
    bindToolbar();
    bindControls();
    initCharts();
    window.addEventListener('resize', resizeAllCharts);
    // 首次刷新一次，便于显示
    refresh(ALL_KEYS);
  }

  // 暴露必要函数供动态加载器调用
  window.AppPublic = { bindToolbar, bindControls, initCharts, refresh, KEYS_STATIC, KEYS_DYNAMIC, setActiveNav };

  document.addEventListener('DOMContentLoaded', init);
})();

// 曲线与导出模块
const curveStore = { 
  hysteresis: [],
  realTimeData: [],
  isRecording: false,
  recordingStartTime: null
};

// 实时滞回曲线数据记录器
class HysteresisRecorder {
  constructor() {
    this.data = [];
    this.isRecording = false;
    this.startTime = null;
    this.recordInterval = null;
    this.storageKey = 'hysteresis_realtime_data';
    
    // 三种曲线类型的数据存储
    this.forwardData = [];
    this.reverseData = [];
    this.hysteresisData = [];
  }

  // 开始记录
  startRecording() {
    if (this.isRecording) return;
    
    this.isRecording = true;
    this.startTime = Date.now();
    this.data = [];
    this.forwardData = [];
    this.reverseData = [];
    this.hysteresisData = [];
    
    // 清除旧的缓存数据
    this.clearCache();
    
    // 每100ms记录一次数据点
    this.recordInterval = setInterval(() => {
      this.recordDataPoint();
    }, 100);
    
    console.log('开始记录滞回曲线数据');
  }

  // 停止记录
  stopRecording() {
    if (!this.isRecording) return;
    
    this.isRecording = false;
    
    if (this.recordInterval) {
      clearInterval(this.recordInterval);
      this.recordInterval = null;
    }
    
    // 分离数据为三种曲线类型
    this.separateCurveData();
    
    // 保存到缓存
    this.saveToCache();
    
    console.log(`记录完成，共记录 ${this.data.length} 个数据点`);
    console.log(`正向曲线: ${this.forwardData.length} 点, 反向曲线: ${this.reverseData.length} 点`);
  }

  // 记录单个数据点
  async recordDataPoint() {
    try {
      // 获取当前的角位移和扭矩数据
      const currentTime = Date.now();
      const relativeTime = currentTime - this.startTime;
      
      // 从Node-RED获取实时数据
      const realTimeData = await this.fetchRealTimeData();
      
      const dataPoint = {
        angle: (realTimeData.angle ?? this.simulateAngleData(relativeTime)),
        torque: (realTimeData.torque ?? this.simulateTorqueData(relativeTime)),
        timestamp: currentTime,
        relativeTime: relativeTime
      };
      
      this.data.push(dataPoint);
      
      // 实时保存到缓存（每10个点保存一次以提高性能）
      if (this.data.length % 10 === 0) {
        this.saveToCache();
      }
      
    } catch (error) {
      console.error('记录数据点失败:', error);
    }
  }

  // 从Node-RED获取实时数据
  async fetchRealTimeData() {
    try {
      const response = await fetch('/api/data/current', { cache: 'no-store' });
      if (response.ok) {
        const data = await response.json();
        // 仅当服务返回数字时使用；否则返回null以触发模拟回退
        const angle = typeof data.angle === 'number' ? data.angle : null;
        const torque = typeof data.torque === 'number' ? data.torque : null;
        return { angle, torque };
      }
    } catch (error) {
      console.warn('获取Node-RED实时数据失败，继续使用模拟回退:', error);
    }
    return { angle: null, torque: null };
  }

  // 分离数据为三种曲线类型
  separateCurveData() {
    if (this.data.length === 0) return;
    
    // 按时间排序
    const sortedData = [...this.data].sort((a, b) => a.timestamp - b.timestamp);
    
    this.forwardData = [];
    this.reverseData = [];
    this.hysteresisData = [...sortedData]; // 完整的滞回曲线包含所有点
    
    // 分析角位移变化趋势
    for (let i = 0; i < sortedData.length; i++) {
      if (i === 0) {
        // 第一个点默认为正向
        this.forwardData.push(sortedData[i]);
        continue;
      }
      
      const prevAngle = sortedData[i-1].angle;
      const currAngle = sortedData[i].angle;
      
      // 判断角位移变化方向
      if (currAngle > prevAngle) {
        // 角位移增加 - 正向
        this.forwardData.push(sortedData[i]);
      } else if (currAngle < prevAngle) {
        // 角位移减少 - 反向
        this.reverseData.push(sortedData[i]);
      }
    }
  }

  // 获取指定类型的曲线数据
  getCurveData(curveType = 'hysteresis') {
    switch (curveType) {
      case 'forward':
        return this.forwardData;
      case 'reverse':
        return this.reverseData;
      case 'hysteresis':
      default:
        return this.hysteresisData;
    }
  }

  // 模拟角位移数据（实际应从传感器获取）
  simulateAngleData(time) {
    const t = time / 1000; // 转换为秒
    const period = 10; // 10秒一个周期
    const amplitude = 5; // 角位移幅度
    return amplitude * Math.sin(2 * Math.PI * t / period) + 0.1 * Math.random();
  }

  // 模拟扭矩数据（实际应从传感器获取）
  simulateTorqueData(time) {
    const t = time / 1000;
    const period = 10;
    const amplitude = 8;
    const hysteresis = 0.5; // 滞回偏移
    const phase = Math.sin(2 * Math.PI * t / period) > 0 ? hysteresis : -hysteresis;
    return amplitude * Math.sin(2 * Math.PI * t / period) + phase + 0.1 * Math.random();
  }

  // 保存到浏览器缓存
  saveToCache() {
    try {
      const cacheData = {
        data: this.data,
        forwardData: this.forwardData,
        reverseData: this.reverseData,
        hysteresisData: this.hysteresisData,
        startTime: this.startTime,
        lastUpdate: Date.now()
      };
      sessionStorage.setItem(this.storageKey, JSON.stringify(cacheData));
    } catch (error) {
      console.error('保存到缓存失败:', error);
    }
  }

  // 从缓存加载数据
  loadFromCache() {
    try {
      const cached = sessionStorage.getItem(this.storageKey);
      if (cached) {
        const cacheData = JSON.parse(cached);
        this.data = cacheData.data || [];
        this.forwardData = cacheData.forwardData || [];
        this.reverseData = cacheData.reverseData || [];
        this.hysteresisData = cacheData.hysteresisData || [];
        this.startTime = cacheData.startTime;
        return this.data;
      }
    } catch (error) {
      console.error('从缓存加载失败:', error);
    }
    return [];
  }

  // 清除缓存
  clearCache() {
    try {
      sessionStorage.removeItem(this.storageKey);
    } catch (error) {
      console.error('清除缓存失败:', error);
    }
  }

  // 获取当前数据
  getData() {
    return this.data;
  }

  // 获取带时间轴的数据
  getDataWithTimeAxis() {
    return this.data.map(point => ({
      ...point,
      timeLabel: new Date(point.timestamp).toLocaleTimeString(),
      elapsedSeconds: point.relativeTime / 1000
    }));
  }

  // 获取记录时长信息
  getRecordingDuration() {
    if (!this.startTime) return 0;
    
    const endTime = this.data.length > 0 ? 
      this.data[this.data.length - 1].timestamp : 
      Date.now();
    
    return (endTime - this.startTime) / 1000; // 返回秒数
  }

  // 检查是否有缓存数据
  hasCachedData() {
    try {
      return sessionStorage.getItem(this.storageKey) !== null;
    } catch (error) {
      return false;
    }
  }
}

// 全局滞回曲线记录器实例
const hysteresisRecorder = new HysteresisRecorder();

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
  // 优先使用实时记录的数据
  if (hysteresisRecorder.hasCachedData()) {
    const cachedData = hysteresisRecorder.loadFromCache();
    if (cachedData && cachedData.length > 0) {
      console.log(`使用缓存的实时数据，共 ${cachedData.length} 个点`);
      return cachedData;
    }
  }
  
  // 如果正在记录，返回当前记录的数据
  if (hysteresisRecorder.isRecording) {
    const currentData = hysteresisRecorder.getData();
    if (currentData.length > 0) {
      console.log(`使用正在记录的数据，共 ${currentData.length} 个点`);
      return currentData;
    }
  }
  
  // 尝试从后端API获取数据
  try {
    const resp = await fetchGetJson('/api/data/hysteresis');
    if (resp && Array.isArray(resp.points)) {
      return resp.points;
    }
  } catch (e) { 
    console.log('后端API不可用，使用模拟数据'); 
  }
  
  // 最后回退到模拟数据（开发环境），生产环境返回空集
  return (window.IS_PRODUCTION ? [] : makeMockHysteresis());
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

  const xTicks = opts.xTicks || 5;
  const yTicks = opts.yTicks || 5;
  // grid lines
  ctx.strokeStyle = '#e5e7eb';
  ctx.lineWidth = 1;
  for (let i=1;i<xTicks;i++) {
    const xx = pad + (w*i)/xTicks;
    ctx.beginPath(); ctx.moveTo(xx, pad); ctx.lineTo(xx, pad+h); ctx.stroke();
  }
  for (let i=1;i<yTicks;i++) {
    const yy = pad + (h*i)/yTicks;
    ctx.beginPath(); ctx.moveTo(pad, yy); ctx.lineTo(pad+w, yy); ctx.stroke();
  }
  
  // axes
  ctx.strokeStyle = '#374151';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(pad, pad); ctx.lineTo(pad, pad+h); // Y axis
  ctx.moveTo(pad, pad+h); ctx.lineTo(pad+w, pad+h); // X axis
  ctx.stroke();
  
  // axis labels
  ctx.fillStyle = '#374151';
  ctx.font = '12px sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText(opts.xLabel || 'X', pad + w/2, canvas.clientHeight - 8);
  ctx.save();
  ctx.translate(12, pad + h/2);
  ctx.rotate(-Math.PI/2);
  ctx.fillText(opts.yLabel || 'Y', 0, 0);
  ctx.restore();
  
  // title
  if (opts.title) {
    ctx.fillStyle = '#111827';
    ctx.font = 'bold 14px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(opts.title, canvas.clientWidth / 2, 20);
  }
  
  // curve
  if (points.length >= 2) {
    ctx.strokeStyle = opts.strokeColor || '#3b82f6';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(scaleX(points[0].angle), scaleY(points[0].torque));
    for (let i = 1; i < points.length; i++) {
      ctx.lineTo(scaleX(points[i].angle), scaleY(points[i].torque));
    }
    if (opts.closePath) {
      ctx.closePath();
    }
    ctx.stroke();
    
    // data points
    ctx.fillStyle = opts.strokeColor || '#3b82f6';
    for (const pt of points) {
      ctx.beginPath();
      ctx.arc(scaleX(pt.angle), scaleY(pt.torque), 2, 0, 2*Math.PI);
      ctx.fill();
    }
  }
  
  // tick labels
  ctx.fillStyle = '#6b7280';
  ctx.font = '10px sans-serif';
  ctx.textAlign = 'center';
  for (let i = 0; i <= xTicks; i++) {
    const val = minX + (maxX - minX) * i / xTicks;
    const xx = pad + (w * i) / xTicks;
    ctx.fillText(val.toFixed(2), xx, pad + h + 15);
  }
  ctx.textAlign = 'right';
  for (let i = 0; i <= yTicks; i++) {
    const val = minY + (maxY - minY) * (yTicks - i) / yTicks;
    const yy = pad + (h * i) / yTicks;
    ctx.fillText(val.toFixed(2), pad - 5, yy + 3);
  }
}

// 多序列叠加绘制，支持直线/曲线样式
function drawMultiXYCurves(canvasId, seriesList, opts={}) {
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
  const all = seriesList.flatMap(s => s.points || []);
  if (!all.length || w<=0 || h<=0) return;
  const xs = all.map(p => p.angle);
  const ys = all.map(p => p.torque);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const scaleX = v => pad + (w * (v - minX)) / ((maxX - minX) || 1);
  const scaleY = v => pad + h - (h * (v - minY)) / ((maxY - minY) || 1);
  const xTicks = opts.xTicks || 5;
  const yTicks = opts.yTicks || 5;
  // grid
  ctx.strokeStyle = '#e5e7eb'; ctx.lineWidth = 1;
  for (let i=1;i<xTicks;i++){const xx=pad+(w*i)/xTicks;ctx.beginPath();ctx.moveTo(xx,pad);ctx.lineTo(xx,pad+h);ctx.stroke();}
  for (let i=1;i<yTicks;i++){const yy=pad+(h*i)/yTicks;ctx.beginPath();ctx.moveTo(pad,yy);ctx.lineTo(pad+w,yy);ctx.stroke();}
  // axes
  ctx.strokeStyle='#374151'; ctx.lineWidth=2;
  ctx.beginPath(); ctx.moveTo(pad,pad); ctx.lineTo(pad,pad+h); ctx.moveTo(pad,pad+h); ctx.lineTo(pad+w,pad+h); ctx.stroke();
  // labels
  ctx.fillStyle='#374151'; ctx.font='12px sans-serif'; ctx.textAlign='center';
  ctx.fillText(opts.xLabel||'X', pad+w/2, canvas.clientHeight-8);
  ctx.save(); ctx.translate(12, pad+h/2); ctx.rotate(-Math.PI/2); ctx.fillText(opts.yLabel||'Y', 0, 0); ctx.restore();
  // draw each series
  const style = opts.lineStyle || 'straight';
  for (const s of seriesList){
    const pts = s.points||[]; if (pts.length<2) continue;
    ctx.strokeStyle = s.color || '#3b82f6';
    ctx.lineWidth = s.lineWidth || 2;
    ctx.beginPath();
    const x0=scaleX(pts[0].angle), y0=scaleY(pts[0].torque);
    ctx.moveTo(x0,y0);
    if (style==='curve'){
      for (let i=1;i<pts.length-1;i++){
        const x=scaleX(pts[i].angle), y=scaleY(pts[i].torque);
        const xn=scaleX(pts[i+1].angle), yn=scaleY(pts[i+1].torque);
        const xc=(x+xn)/2, yc=(y+yn)/2;
        ctx.quadraticCurveTo(x,y,xc,yc);
      }
      ctx.lineTo(scaleX(pts[pts.length-1].angle), scaleY(pts[pts.length-1].torque));
    } else {
      for (let i=1;i<pts.length;i++){
        ctx.lineTo(scaleX(pts[i].angle), scaleY(pts[i].torque));
      }
    }
    if (s.closePath){ ctx.closePath(); }
    ctx.stroke();
  }
}

function drawSelectedCurves(){
  const showH = document.getElementById('show-hysteresis')?.checked ?? true;
  const showF = document.getElementById('show-forward')?.checked ?? true;
  const showR = document.getElementById('show-reverse')?.checked ?? true;
  const lineStyle = document.getElementById('line-style-select')?.value || 'straight';
  const series = [];
  if (hysteresisRecorder.hasCachedData()){
    if (showH) series.push({ points: hysteresisRecorder.getCurveData('hysteresis'), color:'#3b82f6' });
    if (showF) series.push({ points: hysteresisRecorder.getCurveData('forward'), color:'#10b981' });
    if (showR) series.push({ points: hysteresisRecorder.getCurveData('reverse'), color:'#f59e0b' });
  } else {
    if (showH && (curveStore.hysteresis?.length)) series.push({ points: curveStore.hysteresis, color:'#3b82f6' });
    if (showF && (curveStore.forward?.length)) series.push({ points: curveStore.forward, color:'#10b981' });
    if (showR && (curveStore.reverse?.length)) series.push({ points: curveStore.reverse, color:'#f59e0b' });
  }
  if (!series.length) return;
  drawMultiXYCurves('curve-canvas', series, { xLabel:'角位移', yLabel:'扭矩', lineStyle });
}

function openCurveModalHysteresis() {
  const modal = document.getElementById('curve-modal');
  const title = document.getElementById('modal-title');
  title.textContent = '滞回曲线（扭矩-角位移）';
  modal.classList.remove('hidden');
  
  // 初始化记录控制按钮
  initRecordingControls();
  
  // 初始化曲线类型选择器
  initCurveTypeSelector();
  
  setTimeout(async () => {
    const points = await fetchHysteresisPoints();
    curveStore.hysteresis = points;
    
    // 检测是否为滞回曲线数据（闭合路径）
    let isClosedCurve = false;
    if (points && points.length >= 3) {
      const first = points[0];
      const last = points[points.length - 1];
      const tolerance = 0.01; // 容差值
      isClosedCurve = Math.abs(first.angle - last.angle) < tolerance && 
                      Math.abs(first.torque - last.torque) < tolerance;
    }
    
    // 根据选择的显示开关绘制多曲线
    drawSelectedCurves();
    
    // 更新状态显示
    updateRecordingStatus();
  }, 0);
}

// 初始化曲线类型选择器
function initCurveTypeSelector() {
  const selector = document.getElementById('curve-type-select');
  if (selector) {
    selector.addEventListener('change', (e) => {
      drawSelectedCurves();
    });
  }
  document.getElementById('show-hysteresis')?.addEventListener('change', drawSelectedCurves);
  document.getElementById('show-forward')?.addEventListener('change', drawSelectedCurves);
  document.getElementById('show-reverse')?.addEventListener('change', drawSelectedCurves);
  document.getElementById('line-style-select')?.addEventListener('change', drawSelectedCurves);
}

// 根据曲线类型绘制曲线
function drawCurveByType(curveType) {
  let points = [];
  let color = '#3b82f6'; // 默认蓝色
  let label = '完整滞回曲线';
  
  if (hysteresisRecorder.hasCachedData()) {
    // 使用缓存的分离数据
    points = hysteresisRecorder.getCurveData(curveType);
  } else {
    // 使用存储的数据
    points = curveStore.hysteresis || [];
  }
  
  // 设置不同曲线类型的颜色和标签
  switch (curveType) {
    case 'forward':
      color = '#10b981';
      label = '正向曲线';
      break;
    case 'reverse':
      color = '#f59e0b';
      label = '反向曲线';
      break;
    case 'hysteresis':
    default:
      color = '#3b82f6';
      label = '完整滞回曲线';
      break;
  }
  
  // 检测是否为滞回曲线数据（闭合路径）
  let isClosedCurve = false;
  if (points && points.length >= 3 && curveType === 'hysteresis') {
    const first = points[0];
    const last = points[points.length - 1];
    const tolerance = 0.01; // 容差值
    isClosedCurve = Math.abs(first.angle - last.angle) < tolerance && 
                    Math.abs(first.torque - last.torque) < tolerance;
  }
  
  drawXYCurve('curve-canvas', points, { 
    xLabel: '角位移', 
    yLabel: '扭矩',
    closePath: isClosedCurve,
    strokeColor: color,
    title: label
  });
}

// 初始化记录控制按钮
function initRecordingControls() {
  const startBtn = document.getElementById('start-recording');
  const stopBtn = document.getElementById('stop-recording');
  const clearBtn = document.getElementById('clear-data');
  
  // 开始记录按钮
  startBtn.onclick = () => {
    hysteresisRecorder.startRecording();
    startBtn.disabled = true;
    stopBtn.disabled = false;
    updateRecordingStatus();
    
    // 开始实时更新曲线
    startRealTimeUpdate();
  };
  
  // 停止记录按钮
  stopBtn.onclick = () => {
    hysteresisRecorder.stopRecording();
    startBtn.disabled = false;
    stopBtn.disabled = true;
    updateRecordingStatus();
    
    // 停止实时更新
    stopRealTimeUpdate();

    // 停止后异步保存采集的滞回曲线到后端
    (async () => {
      try {
        const pointsToSave = hysteresisRecorder.getData();
        if (Array.isArray(pointsToSave) && pointsToSave.length > 0) {
          await fetch('/api/data/hysteresis', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ points: pointsToSave, timestamp: Date.now() })
          });
          if (typeof toast === 'function') toast('采集的滞回数据已保存', 'success');
        } else {
          if (typeof toast === 'function') toast('无采集数据可保存', 'warn');
        }
      } catch (e) {
        console.warn('保存滞回数据失败:', e);
        if (typeof toast === 'function') toast('保存滞回数据失败', 'error');
      }
    })();
    
    // 最后更新一次曲线
    setTimeout(async () => {
      const points = await fetchHysteresisPoints();
      curveStore.hysteresis = points;
      drawXYCurve('curve-canvas', points, { 
        xLabel:'角位移', 
        yLabel:'扭矩',
        closePath: false // 实时数据通常不闭合
      });
    }, 100);
  };
  
  // 清除数据按钮
  clearBtn.onclick = () => {
    if (confirm('确定要清除所有记录的数据吗？')) {
      hysteresisRecorder.clearCache();
      hysteresisRecorder.data = [];
      updateRecordingStatus();
      
      // 清空曲线显示
      const canvas = document.getElementById('curve-canvas');
      if (canvas) {
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
      }
    }
  };
}

// 更新记录状态显示
function updateRecordingStatus() {
  const indicator = document.getElementById('recording-indicator');
  const info = document.getElementById('recording-info');
  const timeAxisInfo = document.getElementById('time-axis-info');
  const durationDisplay = document.getElementById('duration-display');
  const pointsCount = document.getElementById('points-count');
  
  if (hysteresisRecorder.isRecording) {
    indicator.className = 'status-indicator recording';
    info.textContent = `正在记录... 已记录 ${hysteresisRecorder.data.length} 个数据点`;
    
    // 显示时间轴信息
    if (timeAxisInfo) {
      timeAxisInfo.style.display = 'block';
      const duration = hysteresisRecorder.getRecordingDuration();
      durationDisplay.textContent = `${duration.toFixed(1)}秒`;
      pointsCount.textContent = hysteresisRecorder.data.length;
    }
  } else if (hysteresisRecorder.hasCachedData()) {
    const cachedData = hysteresisRecorder.loadFromCache();
    indicator.className = 'status-indicator cached';
    info.textContent = `已缓存 ${cachedData.length} 个数据点 (${new Date(hysteresisRecorder.startTime).toLocaleTimeString()})`;
    
    // 显示时间轴信息
    if (timeAxisInfo) {
      timeAxisInfo.style.display = 'block';
      const duration = hysteresisRecorder.getRecordingDuration();
      durationDisplay.textContent = `${duration.toFixed(1)}秒`;
      pointsCount.textContent = cachedData.length;
    }
  } else {
    indicator.className = 'status-indicator idle';
    info.textContent = '点击"开始记录"开始实时数据采集';
    
    // 隐藏时间轴信息
    if (timeAxisInfo) {
      timeAxisInfo.style.display = 'none';
    }
  }
}

// 实时更新定时器
let realTimeUpdateInterval = null;

// 开始实时更新曲线
function startRealTimeUpdate() {
  if (realTimeUpdateInterval) return;
  
  realTimeUpdateInterval = setInterval(async () => {
    if (hysteresisRecorder.isRecording) {
      const points = hysteresisRecorder.getData();
      if (points.length > 0) {
        curveStore.hysteresis = points;
        drawXYCurve('curve-canvas', points, { 
          xLabel:'角位移', 
          yLabel:'扭矩',
          closePath: false
        });
        updateRecordingStatus();
      }
    }
  }, 500); // 每500ms更新一次显示
}

// 停止实时更新曲线
function stopRealTimeUpdate() {
  if (realTimeUpdateInterval) {
    clearInterval(realTimeUpdateInterval);
    realTimeUpdateInterval = null;
  }
}

// 页面刷新时清除缓存
window.addEventListener('beforeunload', () => {
  // 如果不在记录状态，清除缓存
  if (!hysteresisRecorder.isRecording) {
    hysteresisRecorder.clearCache();
  }
});

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
  document.getElementById('curve-export-image')?.addEventListener('click', () => {
    const canvas = document.getElementById('curve-canvas');
    if (!canvas) return;
    const url = canvas.toDataURL('image/png');
    const a = document.createElement('a');
    a.href = url;
    a.download = `滞回曲线_${Date.now()}.png`;
    document.body.appendChild(a);
    a.click();
    a.remove();
  });
  document.getElementById('start-test')?.addEventListener('click', () => setTestingState(true, currentTestLabel()));
  document.getElementById('stop-test')?.addEventListener('click', () => setTestingState(false));
  document.getElementById('emergency-stop')?.addEventListener('click', () => setTestingState(false));
  document.getElementById('reset-btn')?.addEventListener('click', () => setTestingState(false));
});

window.addEventListener('resize', () => {
  const modal = document.getElementById('curve-modal');
  if (modal && !modal.classList.contains('hidden')) {
    drawSelectedCurves();
  }
});

function initMotorManagement() {
  const addBtn = document.getElementById('add-motor-btn');
  const editBtn = document.getElementById('edit-motor-btn');
  const deleteBtn = document.getElementById('delete-motor-btn');
  const modal = document.getElementById('motor-edit-modal');
  const modalTitle = document.getElementById('motor-modal-title');
  const modalClose = document.getElementById('motor-modal-close');
  const nameInput = document.getElementById('motor-name-input');
  const saveBtn = document.getElementById('motor-save-btn');
  const cancelBtn = document.getElementById('motor-cancel-btn');
  
  let editingMotorIndex = -1;
  
  // 添加电机
  if (addBtn) {
    addBtn.addEventListener('click', () => {
      editingMotorIndex = -1;
      modalTitle.textContent = '添加电机';
      nameInput.value = '';
      clearModalForm();
      showModal();
    });
  }
  
  // 编辑电机
  if (editBtn) {
    editBtn.addEventListener('click', () => {
      const modelSelect = document.getElementById('motor-model-select');
      const selectedModel = modelSelect?.value;
      if (!selectedModel || selectedModel === 'Custom') {
        if (typeof toast === 'function') toast('无法编辑默认电机', 'warn');
        return;
      }
      
      editingMotorIndex = MOTOR_MODELS.findIndex(m => m.name === selectedModel);
      if (editingMotorIndex === -1) {
        if (typeof toast === 'function') toast('未找到选中的电机', 'warn');
        return;
      }
      
      modalTitle.textContent = '编辑电机';
      const motor = MOTOR_MODELS[editingMotorIndex];
      nameInput.value = motor.name;
      fillModalForm(motor);
      showModal();
    });
  }
  
  // 删除电机
  if (deleteBtn) {
    deleteBtn.addEventListener('click', () => {
      const modelSelect = document.getElementById('motor-model-select');
      const selectedModel = modelSelect?.value;
      if (!selectedModel || selectedModel === 'Custom') {
        if (typeof toast === 'function') toast('无法删除默认电机', 'warn');
        return;
      }
      
      if (confirm(`确定要删除电机 "${selectedModel}" 吗？`)) {
        const index = MOTOR_MODELS.findIndex(m => m.name === selectedModel);
        if (index > 0) { // 保护第一个默认电机
          MOTOR_MODELS.splice(index, 1);
          saveCustomMotors();
          populateModelSelect();
          
          // 切换到第一个电机
          const first = MOTOR_MODELS[0];
          if (first) {
            applySettingsToForm({ model: first.name, ...getDefaultFor(first.name) });
            updateSettingsLabels({ model: first.name });
          }
          
          if (typeof toast === 'function') toast('电机已删除');
        }
      }
    });
  }
  
  // 模态框关闭
  if (modalClose) {
    modalClose.addEventListener('click', hideModal);
  }
  
  if (cancelBtn) {
    cancelBtn.addEventListener('click', hideModal);
  }
  
  // 保存电机
  if (saveBtn) {
    saveBtn.addEventListener('click', () => {
      const name = nameInput.value.trim();
      if (!name) {
        if (typeof toast === 'function') toast('请输入电机型号名称', 'warn');
        return;
      }
      
      // 检查名称是否重复（编辑时排除自己）
      const existingIndex = MOTOR_MODELS.findIndex(m => m.name === name);
      if (existingIndex !== -1 && existingIndex !== editingMotorIndex) {
        if (typeof toast === 'function') toast('电机型号名称已存在', 'warn');
        return;
      }
      
      const motorData = {
        name: name,
        rated_voltage: parseFloat(document.getElementById('modal-motor-rated-voltage').value) || 0,
        rated_current: parseFloat(document.getElementById('modal-motor-rated-current').value) || 0,
        max_torque: parseFloat(document.getElementById('modal-motor-max-torque').value) || 0,
        rated_speed: parseFloat(document.getElementById('modal-motor-rated-speed').value) || 0,
        pole_pairs: parseInt(document.getElementById('modal-motor-pole-pairs').value) || 0,
        inertia: parseFloat(document.getElementById('modal-motor-inertia').value) || 0,
        encoder_resolution: parseInt(document.getElementById('modal-motor-encoder-res').value) || 0
      };
      
      if (editingMotorIndex === -1) {
        // 添加新电机
        MOTOR_MODELS.push(motorData);
      } else {
        // 编辑现有电机
        MOTOR_MODELS[editingMotorIndex] = motorData;
      }
      
      saveCustomMotors();
      populateModelSelect();
      
      // 选中新添加或编辑的电机
      const modelSelect = document.getElementById('motor-model-select');
      if (modelSelect) {
        modelSelect.value = name;
        applySettingsToForm({ model: name, ...motorData });
        updateSettingsLabels({ model: name });
      }
      
      hideModal();
      if (typeof toast === 'function') toast(editingMotorIndex === -1 ? '电机已添加' : '电机已更新');
    });
  }
  
  function showModal() {
    if (modal) modal.classList.remove('hidden');
  }
  
  function hideModal() {
    if (modal) modal.classList.add('hidden');
  }
  
  function clearModalForm() {
    document.getElementById('modal-motor-rated-voltage').value = '';
    document.getElementById('modal-motor-rated-current').value = '';
    document.getElementById('modal-motor-max-torque').value = '';
    document.getElementById('modal-motor-rated-speed').value = '';
    document.getElementById('modal-motor-pole-pairs').value = '';
    document.getElementById('modal-motor-inertia').value = '';
    document.getElementById('modal-motor-encoder-res').value = '';
  }
  
  function fillModalForm(motor) {
    document.getElementById('modal-motor-rated-voltage').value = motor.rated_voltage || '';
    document.getElementById('modal-motor-rated-current').value = motor.rated_current || '';
    document.getElementById('modal-motor-max-torque').value = motor.max_torque || '';
    document.getElementById('modal-motor-rated-speed').value = motor.rated_speed || '';
    document.getElementById('modal-motor-pole-pairs').value = motor.pole_pairs || '';
    document.getElementById('modal-motor-inertia').value = motor.inertia || '';
    document.getElementById('modal-motor-encoder-res').value = motor.encoder_resolution || '';
  }
  
  function saveCustomMotors() {
    // 保存除第一个默认电机外的所有电机到数据库
    const customMotors = MOTOR_MODELS.slice(1);
    
    // 使用API保存到数据库
    customMotors.forEach(async (motor) => {
      try {
        const response = await fetch('/api/motors/custom', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            name: motor.name,
            rated_voltage: motor.rated_voltage,
            rated_current: motor.rated_current,
            max_torque: motor.max_torque,
            rated_speed: motor.rated_speed,
            pole_pairs: motor.pole_pairs,
            inertia: motor.inertia,
            encoder_resolution: motor.encoder_resolution
          })
        });
        
        if (!response.ok) {
          console.warn('保存电机配置失败:', motor.name);
        }
      } catch (error) {
        console.error('保存电机配置异常:', error);
      }
    });
  }
}

/* ========== 设置页面：型号与参数记忆 ==========
   - 加载电机型号列表
   - 读取/保存设置到服务器与本地
   - 表单联动与展示
*/
const SETTINGS_KEY = 'motor_settings';
const SETTINGS_API = '/api/settings';
const MOTOR_MODELS_URL = '/static/config/motor-models.json';
let MOTOR_MODELS = [];
let SETTINGS = null;

async function fetchJSON(url, options) {
  const res = await fetch(url, options);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

async function loadMotorModels() {
  try {
    // 首先尝试从API加载自定义电机
    const response = await fetch('/api/motors/custom');
    if (response.ok) {
      const result = await response.json();
      if (result.success && Array.isArray(result.data)) {
        const customMotors = result.data.map(motor => ({
          name: motor.name,
          rated_voltage: motor.rated_voltage,
          rated_current: motor.rated_current,
          max_torque: motor.max_torque,
          rated_speed: motor.rated_speed,
          pole_pairs: motor.pole_pairs,
          inertia: motor.inertia,
          encoder_resolution: motor.encoder_resolution
        }));
        
        MOTOR_MODELS = [
          { name: 'Custom', rated_voltage: 48, rated_current: 5.0, max_torque: 2.5, rated_speed: 3000, pole_pairs: 4, inertia: 0.000015, encoder_resolution: 2048 },
          ...customMotors
        ];
        return;
      }
    }
    
    // 如果API失败，尝试从静态文件加载（并做字段归一化）
    const list = await fetchJSON(MOTOR_MODELS_URL);
    const normalized = (Array.isArray(list) ? list : []).map(m => ({
      name: m.name || m.model || 'Custom',
      rated_voltage: m.rated_voltage,
      rated_current: m.rated_current,
      max_torque: m.max_torque ?? m.max_torque_nm,
      rated_speed: m.rated_speed ?? m.rated_speed_rpm,
      pole_pairs: m.pole_pairs,
      inertia: m.inertia ?? m.inertia_kgm2,
      encoder_resolution: m.encoder_resolution
    }));
    MOTOR_MODELS = normalized;
    if (!MOTOR_MODELS.find(x => x.name === 'Custom')) {
      MOTOR_MODELS.unshift({ name: 'Custom', rated_voltage: 48, rated_current: 5.0, max_torque: 2.5, rated_speed: 3000, pole_pairs: 4, inertia: 0.000015, encoder_resolution: 2048 });
    }
  } catch (e) {
    console.warn('loadMotorModels failed', e);
    // 最后的兜底方案：从localStorage加载自定义电机（向后兼容）
    const customMotors = JSON.parse(localStorage.getItem('custom_motors') || '[]');
    MOTOR_MODELS = [
      { name: 'Custom', rated_voltage: 48, rated_current: 5.0, max_torque: 2.5, rated_speed: 3000, pole_pairs: 4, inertia: 0.000015, encoder_resolution: 2048 },
      ...customMotors
    ];
  }
}

function populateModelSelect() {
  const sel = document.getElementById('motor-model-select');
  if (!sel) return;
  sel.innerHTML = '';
  MOTOR_MODELS.forEach((m) => {
    const opt = document.createElement('option');
    opt.value = m.name;
    opt.textContent = m.name;
    sel.appendChild(opt);
  });
}

function getDefaultFor(name) {
  const found = MOTOR_MODELS.find((x) => x.name === name) || MOTOR_MODELS[0];
  if (!found) return {};
  if (found.defaults && Object.keys(found.defaults).length) return found.defaults;
  // 回退：若无 defaults，使用模型自身字段作为默认参数
  const keys = ['rated_voltage','rated_current','max_torque','rated_speed','pole_pairs','inertia','encoder_resolution'];
  const obj = { model: found.name };
  keys.forEach(k => { if (found[k] !== undefined) obj[k] = found[k]; });
  return obj;
}

function setField(id, val) {
  const el = document.getElementById(id);
  if (!el) return;
  if (val !== undefined && val !== null) el.value = val;
}

function applySettingsToForm(s) {
  if (!s) return;
  setField('motor-model-select', s.model || (MOTOR_MODELS[0]?.name || ''));
  setField('motor-rated-voltage', s.rated_voltage);
  setField('motor-rated-current', s.rated_current);
  setField('motor-max-torque', s.max_torque);
  setField('motor-rated-speed', s.rated_speed);
  setField('motor-pole-pairs', s.pole_pairs);
  setField('motor-inertia', s.inertia);
  setField('motor-encoder-res', s.encoder_resolution);
}

function collectSettingsFromForm() {
  const get = (id) => document.getElementById(id);
  const model = get('motor-model-select')?.value || 'Custom';
  return {
    model,
    rated_voltage: parseFloat(get('motor-rated-voltage')?.value || 0),
    rated_current: parseFloat(get('motor-rated-current')?.value || 0),
    max_torque: parseFloat(get('motor-max-torque')?.value || 0),
    rated_speed: parseFloat(get('motor-rated-speed')?.value || 0),
    pole_pairs: parseInt(get('motor-pole-pairs')?.value || 0),
    inertia: parseFloat(get('motor-inertia')?.value || 0),
    encoder_resolution: parseInt(get('motor-encoder-res')?.value || 0),
  };
}

function updateSettingsLabels(s) {
  const model = s?.model || '--';
  const el1 = document.getElementById('current-model');
  const el2 = document.getElementById('header-model');
  if (el1) el1.textContent = model;
  if (el2) el2.textContent = model;
}

// 顶部导航电机选择器初始化与联动
function initHeaderMotorSelect() {
  const sel = document.getElementById('header-motor-select');
  if (!sel) return;
  sel.innerHTML = '';
  MOTOR_MODELS.forEach(m => {
    const opt = document.createElement('option');
    opt.value = m.name;
    opt.textContent = m.name;
    sel.appendChild(opt);
  });

  let model = (SETTINGS && SETTINGS.model) || null;
  if (!model) {
    try {
      const raw = localStorage.getItem(SETTINGS_KEY);
      const s = raw ? JSON.parse(raw) : null;
      model = s?.model;
      if (s) SETTINGS = Object.assign({}, s);
    } catch(_) {}
  }
  if (!model) model = MOTOR_MODELS[0]?.name || 'Custom';
  sel.value = model;
  updateSettingsLabels({ model });

  sel.addEventListener('change', async () => {
    const name = sel.value;
    const defaults = getDefaultFor(name);
    const payload = { model: name, ...defaults };
    SETTINGS = payload;
    updateSettingsLabels(SETTINGS);
    try {
      await fetch(SETTINGS_API, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ settings: payload })
      });
      localStorage.setItem(SETTINGS_KEY, JSON.stringify(payload));
    } catch (_) {
      localStorage.setItem(SETTINGS_KEY, JSON.stringify(payload));
    }
    const settingsSel = document.getElementById('motor-model-select');
    if (settingsSel) settingsSel.value = name;
    // 同步设置页字段（若存在）
    if (typeof applySettingsToForm === 'function') {
      applySettingsToForm(SETTINGS);
    }
  });
}

function setSourceLabel(src) {
  const el = document.getElementById('settings-source');
  if (el) el.textContent = src;
}

async function initSettingsPage() {
  if (!document.getElementById('page-settings')) return;

  await loadMotorModels();
  populateModelSelect();

  let source = 'server';
  try {
    const data = await fetchJSON(SETTINGS_API);
    SETTINGS = normalizeServerSettings(data?.settings ?? data) || null;
    // 标记生产环境，控制前端回退逻辑
    window.IS_PRODUCTION = (data?.env === 'production' || data?.debug === false);
    setSourceLabel('server');
  } catch (e) {
    source = 'local';
    setSourceLabel('local');
    try {
      const raw = localStorage.getItem(SETTINGS_KEY);
      SETTINGS = raw ? JSON.parse(raw) : null;
    } catch (_) {
      SETTINGS = null;
    }
  }

  if (!SETTINGS) {
    const first = MOTOR_MODELS[0]?.name || 'Custom';
    SETTINGS = { model: first, ...getDefaultFor(first) };
  }

  applySettingsToForm(SETTINGS);
  updateSettingsLabels(SETTINGS);

  const modelSel = document.getElementById('motor-model-select');
  if (modelSel) {
    modelSel.addEventListener('change', () => {
      const name = modelSel.value;
      const defaults = getDefaultFor(name);
      applySettingsToForm({ model: name, ...defaults });
      updateSettingsLabels({ model: name });
    });
  }

  const btnSave = document.getElementById('settings-save');
  if (btnSave) {
    btnSave.addEventListener('click', async () => {
      const payload = collectSettingsFromForm();
      try {
        await fetch(SETTINGS_API, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ settings: payload }),
        });
        localStorage.setItem(SETTINGS_KEY, JSON.stringify(payload));
        SETTINGS = payload;
        updateSettingsLabels(SETTINGS);
        if (typeof toast === 'function') toast('设置已保存');
      } catch (e) {
        localStorage.setItem(SETTINGS_KEY, JSON.stringify(payload));
        SETTINGS = payload;
        updateSettingsLabels(SETTINGS);
        if (typeof toast === 'function') toast('服务器不可用，仅本地保存', 'warn');
      }
    });
  }

  const btnReset = document.getElementById('settings-reset');
  if (btnReset) {
    btnReset.addEventListener('click', async () => {
      try {
        await fetch(`${SETTINGS_API}/reset`, { method: 'POST' });
        const name = MOTOR_MODELS[0]?.name || 'Custom';
        const defaults = getDefaultFor(name);
        applySettingsToForm({ model: name, ...defaults });
        localStorage.removeItem(SETTINGS_KEY);
        SETTINGS = { model: name, ...defaults };
        updateSettingsLabels(SETTINGS);
        if (typeof toast === 'function') toast('已恢复默认设置');
      } catch (e) {
        const name = MOTOR_MODELS[0]?.name || 'Custom';
        const defaults = getDefaultFor(name);
        applySettingsToForm({ model: name, ...defaults });
        localStorage.removeItem(SETTINGS_KEY);
        SETTINGS = { model: name, ...defaults };
        updateSettingsLabels(SETTINGS);
        if (typeof toast === 'function') toast('服务器不可用，恢复到默认', 'warn');
      }
    });
  }

  // 初始化数据连接配置
  initConnectionSettings();
  
  // 初始化电机管理功能
  initMotorManagement();
}

function initConnectionSettings() {
  // 从数据库加载连接配置
  loadConnectionSettings();
  
  const collectionInput = document.getElementById('data-collection-url');
  const writeInput = document.getElementById('data-write-url');
  const collectionStatus = document.getElementById('collection-status');
  const writeStatus = document.getElementById('write-status');
  
  async function loadConnectionSettings() {
    try {
      const response = await fetch('/api/settings/connection');
      if (response.ok) {
        const result = await response.json();
        if (result.success && result.data) {
          const collectionUrl = result.data.data_collection_url?.value || '';
          const writeUrl = result.data.data_write_url?.value || '';
          
          // 设置输入框的值
          if (collectionInput) collectionInput.value = collectionUrl;
          if (writeInput) writeInput.value = writeUrl;
          
          // 更新状态显示
          updateConnectionStatus();
          return;
        }
      }
    } catch (error) {
      console.warn('从数据库加载连接配置失败，使用localStorage兜底:', error);
    }
    
    // 兜底方案：从localStorage加载
    const collectionUrl = localStorage.getItem('data-collection-url') || '';
    const writeUrl = localStorage.getItem('data-write-url') || '';
    
    // 设置输入框的值
    if (collectionInput) collectionInput.value = collectionUrl;
    if (writeInput) writeInput.value = writeUrl;
    
    // 更新状态显示
    updateConnectionStatus();
  }
  
  function updateConnectionStatus() {
    const collection = collectionInput?.value?.trim() || '';
    const write = writeInput?.value?.trim() || '';
    
    if (collectionStatus) collectionStatus.textContent = collection ? '已配置' : '未配置';
    if (writeStatus) writeStatus.textContent = write ? '已配置' : '未配置';
  }

  // 测试连接按钮
  const testBtn = document.getElementById('connection-test');
  if (testBtn) {
    testBtn.addEventListener('click', async () => {
      const collection = collectionInput?.value?.trim() || '';
      const write = writeInput?.value?.trim() || '';
      
      if (!collection && !write) {
        if (typeof toast === 'function') toast('请先配置连接地址', 'warn');
        return;
      }
      
      // 使用API测试连接
      let results = [];
      
      if (collection) {
        try {
          const response = await fetch('/api/settings/test-connection', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: collection })
          });
          
          if (response.ok) {
            const result = await response.json();
            if (result.success && result.data) {
              const testResult = result.data;
              if (testResult.success) {
                results.push(`采集地址连接成功 (${testResult.response_time}ms)`);
                if (collectionStatus) collectionStatus.textContent = '连接正常';
              } else {
                results.push(`采集地址连接失败: ${testResult.message}`);
                if (collectionStatus) collectionStatus.textContent = '连接失败';
              }
            }
          }
        } catch (e) {
          results.push('采集地址测试异常');
          if (collectionStatus) collectionStatus.textContent = '测试异常';
        }
      }
      
      if (write) {
        try {
          const response = await fetch('/api/settings/test-connection', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: write })
          });
          
          if (response.ok) {
            const result = await response.json();
            if (result.success && result.data) {
              const testResult = result.data;
              if (testResult.success) {
                results.push(`写入地址连接成功 (${testResult.response_time}ms)`);
                if (writeStatus) writeStatus.textContent = '连接正常';
              } else {
                results.push(`写入地址连接失败: ${testResult.message}`);
                if (writeStatus) writeStatus.textContent = '连接失败';
              }
            }
          }
        } catch (e) {
          results.push('写入地址测试异常');
          if (writeStatus) writeStatus.textContent = '测试异常';
        }
      }
      
      if (typeof toast === 'function') {
        results.forEach(msg => toast(msg, msg.includes('成功') ? 'success' : 'warn'));
      }
    });
  }

  // 保存配置按钮
  const saveBtn = document.getElementById('connection-save');
  if (saveBtn) {
    saveBtn.addEventListener('click', async () => {
      const collection = collectionInput?.value?.trim() || '';
      const write = writeInput?.value?.trim() || '';
      
      try {
        // 保存到数据库
        const response = await fetch('/api/settings/connection', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            data_collection_url: collection,
            data_write_url: write
          })
        });
        
        if (response.ok) {
          const result = await response.json();
          if (result.success) {
            // 更新状态显示
            updateConnectionStatus();
            
            if (typeof toast === 'function') toast('连接配置已保存到数据库', 'success');
            return;
          }
        }
        
        throw new Error('API保存失败');
      } catch (error) {
        console.warn('保存到数据库失败，使用localStorage兜底:', error);
        
        // 兜底方案：保存到localStorage
        localStorage.setItem('data-collection-url', collection);
        localStorage.setItem('data-write-url', write);
        
        // 更新状态显示
        updateConnectionStatus();
        
        if (typeof toast === 'function') toast('连接配置已保存到本地存储', 'warn');
      }
    });
  }
  
  // 监听输入框变化，实时更新状态
  if (collectionInput) {
    collectionInput.addEventListener('input', updateConnectionStatus);
  }
  
  if (writeInput) {
    writeInput.addEventListener('input', updateConnectionStatus);
  }
}

function normalizeServerSettings(data) {
  if (!data || typeof data !== 'object') return null;
  return {
    model: data.model || 'Custom',
    rated_voltage: parseFloat(data.rated_voltage) || 0,
    rated_current: parseFloat(data.rated_current) || 0,
    max_torque: parseFloat(data.max_torque) || 0,
    rated_speed: parseFloat(data.rated_speed) || 0,
    pole_pairs: parseInt(data.pole_pairs) || 0,
    inertia: parseFloat(data.inertia) || 0,
    encoder_resolution: parseInt(data.encoder_resolution) || 0
  };
}

function toast(message, type = 'info') {
  const container = document.getElementById('toast-container') || document.body;
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;
  toast.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    padding: 12px 16px;
    border-radius: 4px;
    color: white;
    font-size: 14px;
    z-index: 10000;
    opacity: 0;
    transition: opacity 0.3s;
  `;
  
  switch(type) {
    case 'success': toast.style.backgroundColor = '#10b981'; break;
    case 'error': toast.style.backgroundColor = '#ef4444'; break;
    case 'warn': toast.style.backgroundColor = '#f59e0b'; break;
    default: toast.style.backgroundColor = '#3b82f6';
  }
  
  container.appendChild(toast);
  setTimeout(() => toast.style.opacity = '1', 10);
  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => container.removeChild(toast), 300);
  }, 3000);
}

function showPageFromHash() {
  const hash = (location.hash || '#home').replace('#', '');
  document.querySelectorAll('.page').forEach((p) => p.classList.add('hidden'));
  const page = document.getElementById(`page-${hash}`);
  if (page) page.classList.remove('hidden');
  document.querySelectorAll('.nav-link').forEach((a) => {
    const target = a.getAttribute('href');
    a.classList.toggle('active', target === `#${hash}`);
  });
}

window.addEventListener('hashchange', () => {
  showPageFromHash();
  if (location.hash === '#settings') initSettingsPage();
});

document.addEventListener('DOMContentLoaded', () => {
  showPageFromHash();
  initSettingsPage();
});
// ... 新增：历史图表与PNG导出 =====
(function () {
  const historyKeySelect = document.getElementById('history-key-select');
  const viewHistoryBtn = document.getElementById('view-history');
  const exportHistoryPngBtn = document.getElementById('export-history-png');
  const modal = document.getElementById('curve-modal');
  const modalTitle = document.getElementById('modal-title');
  const modalClose = document.getElementById('modal-close');
  const curveCanvas = document.getElementById('curve-canvas');
  const exportCurveCsvBtn = document.getElementById('curve-export-csv');
  const exportCurvePngBtn = document.getElementById('curve-export-png');

  if (!modal || !curveCanvas) return;

  const ctx = curveCanvas.getContext('2d');
  let currentSeries = [];
  let currentKey = '';

  function openModal(title) {
    modal.classList.remove('hidden');
    modalTitle.textContent = title || '曲线';
    setTimeout(() => {
      curveCanvas.width = modal.querySelector('.modal-content').clientWidth - 32;
      curveCanvas.height = 320;
      drawSeries();
    }, 0);
  }
  function closeModal() {
    modal.classList.add('hidden');
  }
  modalClose && modalClose.addEventListener('click', closeModal);

  function drawSeries() {
    const w = curveCanvas.width;
    const h = curveCanvas.height;
    ctx.clearRect(0, 0, w, h);
    // 背景
    ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--panel-bg').trim() || '#fff';
    ctx.fillRect(0, 0, w, h);
    // 坐标轴
    ctx.strokeStyle = '#999';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(40, h - 30);
    ctx.lineTo(w - 10, h - 30);
    ctx.moveTo(40, h - 30);
    ctx.lineTo(40, 10);
    ctx.stroke();

    if (!currentSeries || currentSeries.length === 0) return;

    // 归一化数据到画布
    const xs = currentSeries.map(p => p.x);
    const ys = currentSeries.map(p => p.y);
    const minX = Math.min(...xs), maxX = Math.max(...xs);
    const minY = Math.min(...ys), maxY = Math.max(...ys);
    const px = x => 40 + (x - minX) / (maxX - minX || 1) * (w - 60);
    const py = y => (h - 30) - (y - minY) / (maxY - minY || 1) * (h - 50);

    ctx.strokeStyle = '#1f7ae0';
    ctx.lineWidth = 2;
    ctx.beginPath();
    currentSeries.forEach((p, i) => {
      const X = px(p.x), Y = py(p.y);
      if (i === 0) ctx.moveTo(X, Y); else ctx.lineTo(X, Y);
    });
    ctx.stroke();

    // 标题
    ctx.fillStyle = '#333';
    ctx.font = '14px system-ui, -apple-system, Segoe UI, Roboto';
    ctx.fillText(currentKey, 50, 24);
  }

  async function fetchHistorySeries(key) {
    // 这里先用本地最近数据模拟；实际可以改为从后端拉取历史曲线
    // 模拟生成一条平滑曲线
    const series = Array.from({ length: 120 }).map((_, i) => {
      const x = i / 6;
      const y = Math.sin(i / 12) * 5 + (Math.random() - 0.5) * 0.8;
      return { x, y };
    });
    return series;
  }

  viewHistoryBtn && viewHistoryBtn.addEventListener('click', async () => {
    currentKey = historyKeySelect ? historyKeySelect.value : '曲线';
    currentSeries = await fetchHistorySeries(currentKey);
    openModal('历史曲线 - ' + currentKey);
  });

  // 导出PNG
  function downloadDataUrl(dataUrl, filename) {
    const a = document.createElement('a');
    a.href = dataUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }
  function exportCanvasAsPNG(canvas, filename) {
    const url = canvas.toDataURL('image/png');
    downloadDataUrl(url, filename);
  }
  exportHistoryPngBtn && exportHistoryPngBtn.addEventListener('click', async () => {
    currentKey = historyKeySelect ? historyKeySelect.value : '曲线';
    currentSeries = await fetchHistorySeries(currentKey);
    openModal('历史曲线 - ' + currentKey);
    setTimeout(() => exportCanvasAsPNG(curveCanvas, `${currentKey}-history.png`), 50);
  });
  exportCurvePngBtn && exportCurvePngBtn.addEventListener('click', () => {
    exportCanvasAsPNG(curveCanvas, `${currentKey || 'curve'}-export.png`);
  });

  // 关闭遮罩关闭
  modal && modal.querySelector('.modal-overlay')?.addEventListener('click', closeModal);

  // 新增：事件委托，解决动态加载时按钮不可用
  document.addEventListener('click', async (e) => {
    const id = e.target && e.target.id;
    if (id === 'view-history') {
      currentKey = document.getElementById('history-key-select')?.value || '曲线';
      currentSeries = await fetchHistorySeries(currentKey);
      openModal('历史曲线 - ' + currentKey);
    } else if (id === 'export-history-png') {
      currentKey = document.getElementById('history-key-select')?.value || '曲线';
      currentSeries = await fetchHistorySeries(currentKey);
      openModal('历史曲线 - ' + currentKey);
      setTimeout(() => exportCanvasAsPNG(curveCanvas, `${currentKey}-history.png`), 50);
    }
  });
})();

// ===== 设置页输入和按钮浅色保障 =====
(function ensureLightInputs() {
  const page = document.getElementById('page-settings');
  if (!page) return;
  const forceLight = el => {
    el.style.background = 'var(--input-bg)';
    el.style.color = 'var(--text)';
    el.style.borderColor = 'var(--border)';
  };
  page.querySelectorAll('input, select, button').forEach(forceLight);
})();

// ===== 动态页面加载与按页初始化 =====
(function pageLoader(){
  const host = document.getElementById('page-host');
  if(!host) return;

  const cssPrefix = 'css-page-';
  function ensurePageCSS(name){
    // 移除其它页面CSS
    Array.from(document.querySelectorAll(`link[id^="${cssPrefix}"]`)).forEach(l => l.remove());
    // 加载当前页面CSS
    const id = `${cssPrefix}${name}`;
    if(!document.getElementById(id)){
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.id = id;
      link.href = `/static/css/pages/${name}.css`;
      document.head.appendChild(link);
    }
  }

  async function loadPage(name){
    try{
      const res = await fetch(`/static/templates/pages/${name}.html`, { cache: 'no-store' });
      const html = await res.text();
      host.innerHTML = html;
      ensurePageCSS(name);
      // 使用公开的导航高亮，退化到showPageFromHash
      if(window.AppPublic && typeof window.AppPublic.setActiveNav === 'function'){
        window.AppPublic.setActiveNav();
      } else {
        try{ showPageFromHash(); }catch(_){}
      }
      initFor(name);
    }catch(e){
      console.warn('加载页面失败', name, e);
      host.innerHTML = `<section class="page"><div class="card">无法加载页面：${name}</div></section>`;
    }
  }

  function initFor(name){
    if(name === 'home'){
      return;
    }
    if(name === 'static'){
      // 绑定工具栏/控件与图表初始化
      window.AppPublic?.bindToolbar?.();
      window.AppPublic?.bindControls?.();
      window.AppPublic?.initCharts?.();
      window.AppPublic?.refresh?.(window.AppPublic?.KEYS_STATIC || []);
      return;
    }
    if(name === 'dynamic'){
      window.AppPublic?.bindToolbar?.();
      window.AppPublic?.bindControls?.();
      window.AppPublic?.initCharts?.();
      window.AppPublic?.refresh?.(window.AppPublic?.KEYS_DYNAMIC || []);
      return;
    }
    if(name === 'settings'){
      initSettingsPage();
      return;
    }
  }

  function currentPageName(){
    const hash = (location.hash || '#home').replace('#','');
    return ['home','static','dynamic','settings'].includes(hash) ? hash : 'home';
  }

  window.addEventListener('hashchange', () => loadPage(currentPageName()));
  document.addEventListener('DOMContentLoaded', () => loadPage(currentPageName()));
})();