'use strict';
// 号码互发测试台 · 演示版前端（无依赖）。数据全部来自本机 server.py。

const $ = (s, el = document) => el.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

// ---------------------------------------------------------------- 图标（细线条）
const P = {
  overview: '<rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/>',
  play: '<polygon points="6 3 20 12 6 21 6 3"/>',
  history: '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/>',
  phone: '<rect x="5" y="2" width="14" height="20" rx="2"/><path d="M12 18h.01"/>',
  settings: '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>',
  logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>',
  refresh: '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>',
  lock: '<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
  user: '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
  eye: '<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
  download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>',
  stop: '<rect x="6" y="6" width="12" height="12" rx="1"/>',
  arrow: '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
  back: '<path d="m15 18-6-6 6-6"/>',
  search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
  info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
  inbox: '<polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  flask: '<path d="M10 2v7.31"/><path d="M14 9.3V2"/><path d="M8.5 2h7"/><path d="M14 9.3a6.5 6.5 0 1 1-4 0"/>',
  device: '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 7h6M9 11h6M9 15h3"/><circle cx="15" cy="16" r="1"/>',
  upload: '<path d="M12 16V4"/><path d="m7 9 5-5 5 5"/><path d="M5 20h14"/>',
  link: '<path d="M10 13a5 5 0 0 0 7.54.54l1.82-1.82a5 5 0 0 0-7.07-7.07l-1.04 1.04"/><path d="M14 11a5 5 0 0 0-7.54-.54l-1.82 1.82a5 5 0 0 0 7.07 7.07l1.04-1.04"/>',
};
const icon = (n, cls = 'i') => `<svg class="${cls}" viewBox="0 0 24 24">${P[n] || ''}</svg>`;

// ---------------------------------------------------------------- 工具
const pad = n => String(n).padStart(2, '0');
function fmtTime(t) {
  if (t == null) return '—';
  const d = typeof t === 'number' ? new Date(t * 1000) : new Date(t);
  if (isNaN(d)) return '—';
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}
const clock = t => { const d = new Date(t * 1000); return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`; };
const pctText = v => v == null ? '—' : `${v.toFixed(1)}%`;
const rateCls = v => v == null ? '' : v >= 95 ? 'ok' : v >= 80 ? 'warn' : 'bad';
const secText = v => v == null ? '—' : `${v.toFixed(1)} 秒`;
const MODE_NAME = { relay: '接力互发', pairs: '两两互发', pair: '指定一对', cross_pool: '号池轮询互发' };
const STATUS = {
  waiting: ['排队中', 'grey'], submitting: ['提交中', 'info'], submitted: ['已提交', 'info'], accepted: ['等待对方收到', 'info'],
  delivered: ['已到达', 'ok'], send_failed: ['发送失败', 'bad'], undelivered: ['未到达', 'bad'], cancelled: ['已停止未发出', 'grey'],
};
const RUN_STATE = { running: ['测试中', 'info'], done: ['已完成', 'ok'], stopped: ['已停止', 'warn'] };
const pill = (text, cls) => `<span class="pill ${cls}">${esc(text)}</span>`;
const statusPill = s => pill(...(STATUS[s] || [s, 'grey']));
const devName = d => `设备 ${d}`;

function ring(v) {
  const r = 26, c = 2 * Math.PI * r, p = v == null ? 0 : Math.max(0, Math.min(100, v));
  const col = { ok: '#10B981', warn: '#F59E0B', bad: '#EF4444', '': '#CBD5E1' }[rateCls(v)];
  return `<svg class="ring" viewBox="0 0 64 64"><circle cx="32" cy="32" r="${r}" fill="none" stroke="#EEF0F3" stroke-width="7"/>
    <circle cx="32" cy="32" r="${r}" fill="none" stroke="${col}" stroke-width="7" stroke-linecap="round"
    stroke-dasharray="${(c * p / 100).toFixed(1)} ${c.toFixed(1)}" transform="rotate(-90 32 32)" style="transition:stroke-dasharray .5s"/></svg>`;
}
const bar = (v, cls) => `<div class="bar ${cls ?? rateCls(v)}"><i style="width:${v == null ? 0 : Math.max(0, Math.min(100, v))}%"></i></div>`;
const rateCell = v => `<div class="rate-cell">${bar(v)}<b class="num c-${rateCls(v)}">${pctText(v)}</b></div>`;
// 只有明确收到 online=false 才显示“离线”；在线但还没有回传 IMEI 时显示“未读取”。
const imeiDisplay = deviceOrLine => {
  if (deviceOrLine?.online === false) return '离线';
  const imei = String(deviceOrLine?.imei || '').trim();
  if (imei) return imei;
  return deviceOrLine?.online === true ? '未读取' : '未上报';
};

function toast(msg) {
  const t = $('#toast'); t.textContent = msg; t.hidden = false;
  clearTimeout(toast.timer); toast.timer = setTimeout(() => { t.hidden = true; }, 2600);
}
function confirmBox(title, text, okText = '确定') {
  return new Promise(res => {
    const root = $('#modal-root');
    root.innerHTML = `<div class="modal-bg"><div class="modal" role="dialog" aria-modal="true"><h3>${esc(title)}</h3><p>${text}</p>
      <div class="actions"><button class="btn" data-a="no">取消</button><button class="btn primary" data-a="yes">${esc(okText)}</button></div></div></div>`;
    root.onclick = e => { const a = e.target.dataset.a || (e.target.classList.contains('modal-bg') ? 'no' : null); if (a) { root.innerHTML = ''; res(a === 'yes'); } };
  });
}

class ApiError extends Error { constructor(status, msg) { super(msg); this.status = status; } }
async function api(path, body) {
  const opt = { credentials: 'same-origin', headers: {} };
  if (body !== undefined) { opt.method = 'POST'; opt.headers = { 'Content-Type': 'application/json', 'X-Requested-With': 'sms-console' }; opt.body = JSON.stringify(body); }
  let r;
  try { r = await fetch(path, opt); } catch { throw new ApiError(0, '连不上测试台服务，请确认 server.py 还在运行'); }
  const data = await r.json().catch(() => ({}));
  if (r.status === 401 && path !== '/api/login') { S.me = null; stopPoll(); renderLogin(data.error); throw new ApiError(401, data.error); }
  if (!r.ok) throw new ApiError(r.status, data.error || `出错了（HTTP ${r.status}）`);
  return data;
}

// ---------------------------------------------------------------- 全局状态
const S = { me: null, meta: {}, numbers: [], numbersInfo: {}, settings: null, offline: false };
let pollTimer = null;
function stopPoll() { clearInterval(pollTimer); pollTimer = null; }
function poll(fn, ms) { stopPoll(); pollTimer = setInterval(() => fn().catch(() => {}), ms); }

// ---------------------------------------------------------------- 登录
function renderLogin(err) {
  stopPoll();
  $('#app').innerHTML = `<div class="login"><form class="login-card" id="login-form" autocomplete="on">
    <div class="eyebrow">eSIM OPERATIONS</div><h1>设备与短信测试台</h1><p class="sub">识别 EC20、整理号池，并在开始测试前看清每个号码</p>
    ${err && err !== '请先登录' ? `<div class="login-err">${esc(err)}</div>` : '<div id="login-err-slot"></div>'}
    <div class="field"><label for="u">用户名</label><div class="input-wrap">${icon('user')}<input id="u" name="username" autocomplete="username" required></div></div>
    <div class="field"><label for="p">密码</label><div class="input-wrap">${icon('lock')}<input id="p" name="password" type="password" autocomplete="current-password" required>
      <button type="button" class="icon-btn" id="eye" aria-label="显示密码">${icon('eye')}</button></div></div>
    <button class="btn primary block" id="login-btn">登录 ${icon('arrow')}</button>
    <button class="btn block offline-btn" id="demo-btn" type="button">进入离线演示</button>
    <div class="login-note">VoCat 在线时读取实时设备；远程关闭时可用本地缓存继续体验，不会发送真实短信</div></form></div>`;
  $('#eye').onclick = () => { const p = $('#p'); p.type = p.type === 'password' ? 'text' : 'password'; };
  $('#u').focus();
  $('#demo-btn').onclick = async () => {
    const btn = $('#demo-btn'); btn.disabled = true; btn.textContent = '准备离线数据…';
    try { S.me = await api('/api/demo-session', {}); S.offline = true; await boot(); }
    catch (x) { btn.disabled = false; btn.textContent = '进入离线演示'; toast(x.message); }
  };
  $('#login-form').onsubmit = async e => {
    e.preventDefault();
    const btn = $('#login-btn'); btn.disabled = true; btn.firstChild.textContent = '登录中… ';
    try {
      const me = await api('/api/login', { username: $('#u').value, password: $('#p').value });
      S.me = me; S.offline = false; await boot();
    } catch (x) {
      btn.disabled = false; btn.firstChild.textContent = '登录 ';
      const old = $('.login-err'); if (old) old.remove();
      $('#login-form .sub').insertAdjacentHTML('afterend', `<div class="login-err">${esc(x.message)}</div>`);
    }
  };
}

// ---------------------------------------------------------------- 外壳
const NAV = [['overview', '总览', 'overview'], ['run', '开始测试', 'play'], ['imei', 'IMEI识别', 'device'], ['records', '测试记录', 'history'], ['numbers', '号码列表', 'phone'], ['settings', '系统设置', 'settings']];
function shell(active) {
  if (!$('.shell')) {
    $('#app').innerHTML = `<div class="shell"><aside class="side"><div class="brand">eSIM 设备测试台</div><nav class="nav">
      ${NAV.map(([k, t, i]) => `<a href="#/${k}" data-k="${k}">${icon(i)}<span>${t}</span></a>`).join('')}</nav>
      <div class="me"><div class="avatar">${icon('user')}</div><div class="who"><b>${esc(S.me.user)}</b><span>Administrator</span></div>
      <button class="btn icon-only" id="logout" title="退出登录">${icon('logout')}</button></div></aside>
      <div class="main"><header class="top"><b id="crumb"></b><div class="grow"></div>
      <span class="demo-pill ${S.offline ? 'offline' : ''}">${icon(S.offline ? 'info' : 'flask')}${S.offline ? '离线演示 · 本地缓存' : '演示模式 · 数据为模拟'}</span><span class="ver">${esc(S.meta.version || '')}</span></header>
      <nav class="mobile-nav">${NAV.map(([k, t]) => `<a href="#/${k}" data-k="${k}">${t}</a>`).join('')}</nav>
      <main class="content" id="page"></main></div></div>`;
    $('#logout').onclick = async () => { await api('/api/logout', {}).catch(() => {}); S.me = null; S.offline = false; location.hash = ''; renderLogin(); };
  }
  document.querySelectorAll('[data-k]').forEach(a => a.classList.toggle('on', a.dataset.k === active));
  $('#crumb').textContent = (NAV.find(n => n[0] === active) || [])[1] || '';
  return $('#page');
}
const head = (title, desc, actions = '') => `<div class="page-head"><div><h1>${title}</h1>${desc ? `<p>${desc}</p>` : ''}</div><div class="actions">${actions}</div></div>`;
const loading = () => `<div class="card"><div class="skeleton" style="width:40%"></div><div class="skeleton"></div><div class="skeleton" style="width:70%"></div></div>`;
const errorBox = (msg, retry = 'retry') => `<div class="alert bad">${icon('info')}<span style="flex:1">${esc(msg)}</span><button class="btn" data-act="${retry}">重试</button></div>`;

async function loadNumbers(refresh) {
  const d = await api('/api/numbers' + (refresh ? '?refresh=1' : ''));
  S.numbers = d.numbers || []; S.numbersInfo = d;
  return d;
}

// ---------------------------------------------------------------- 页面：总览
function kpiCards(o, extra) {
  return `<div class="grid4">
    <div class="card kpi">${ring(o.send_rate)}<div><div class="label">发送成功率</div><div class="big num c-${rateCls(o.send_rate)}">${pctText(o.send_rate)}</div><div class="small">成功 ${o.sent_ok} / 共 ${o.total} 条</div></div></div>
    <div class="card kpi">${ring(o.arrive_rate)}<div><div class="label">到达率</div><div class="big num c-${rateCls(o.arrive_rate)}">${pctText(o.arrive_rate)}</div><div class="small">到达 ${o.arrived} / 共 ${o.total} 条</div></div></div>
    <div class="card kpi"><div><div class="label">平均到达用时</div><div class="big num">${secText(o.avg_latency_s)}</div><div class="small">从发出到对方收到</div></div></div>
    <div class="card kpi"><div><div class="label">测试总条数</div><div class="big num">${o.total}</div><div class="small">${extra}</div></div></div></div>`;
}
async function pageOverview(el) {
  el.innerHTML = head('总览', '号池短信互发的整体情况', `<button class="btn" data-act="refresh">${icon('refresh')}刷新</button><a class="btn primary" href="#/run">${icon('play')}开始测试</a>`) + loading();
  const draw = async () => {
    const d = await api('/api/overview');
    const o = d.summary, L = d.latest, R = d.real;
    const latest = L ? `<div class="card"><div class="card-title">最近一次测试<a href="#/records/${esc(L.batch)}">查看详情 →</a></div>
      <div class="latest"><div class="kv"><span>批次号</span><b class="mono">${esc(L.batch)}</b> <span class="tag">演示</span></div>
      <div class="kv"><span>开始时间</span><b class="num">${fmtTime(L.started)}</b></div><div class="kv"><span>发法</span><b>${esc(L.mode_name)}</b></div>
      <div class="kv"><span>号码 / 条数</span><b class="num">${L.number_count} 个 / ${L.summary.overall.planned} 条</b></div>
      <div class="kv"><span>发送成功率</span><b class="num c-${rateCls(L.summary.overall.send_rate)}">${pctText(L.summary.overall.send_rate)}</b></div>
      <div class="kv"><span>到达率</span><b class="num c-${rateCls(L.summary.overall.arrive_rate)}">${pctText(L.summary.overall.arrive_rate)}</b></div>
      <div class="kv"><span>状态</span>${pill(...RUN_STATE[L.state])}</div></div></div>`
      : `<div class="card"><div class="empty">${icon('inbox')}<div>还没有演示测试，去「开始测试」跑一次吧</div></div></div>`;
    const real = R.total ? `<div class="card"><div class="card-title">真实验证 <span class="tag real">真实</span><a href="#/records/real">查看明细 →</a></div>
      <div class="real-card"><div><div class="big num">${R.arrived} / ${R.total} 条到达</div><div class="muted">2026-09-22 用 VoCat 真实发送 · 平均 ${secText(R.avg_latency_s)} · 受每小时 10 条限制，只发了这些</div></div></div></div>` : '';
    const deviceById = new Map((d.devices || []).map(v => [String(v.id ?? v.device_id ?? ''), v]));
    const devices = (d.devices || []).length ? `<div class="device-overview-grid">${d.devices.map(v => `<div class="device-overview"><div class="device-overview-head"><span class="device-mark">${icon('device')}</span><div><b>${esc(v.name || poolName(v))}</b><small>${v.online === false ? '离线' : v.online === true ? '在线' : '状态未知'}</small></div>${v.online === true ? pill('在线', 'ok') : v.online === false ? pill('离线', 'grey') : pill('未知', 'warn')}</div><div class="device-overview-meta"><span>IMEI <b class="mono">${esc(imeiDisplay(v))}</b></span><span>号码 <b>${v.number_count || 0}</b> · 就绪 <b>${v.ready_count || 0}</b></span><span>配置档案 <b>${v.profile_count ?? '—'}</b></span></div></div>`).join('')}</div>` : `<div class="empty">${icon('device')}<div>还没有设备库存，去「IMEI 识别」导入或刷新</div></div>`;
    const nums = d.numbers.length ? `<div class="num-grid">${d.numbers.map(n => {
      const low = (n.send_rate != null && n.send_rate < 80) || (n.receive_rate != null && n.receive_rate < 80);
      const numberDevice = deviceById.get(String(n.device ?? n.pool_id ?? ''));
      return `<div class="num-card ${low ? 'low' : ''} ${n.ready ? '' : 'off'}"><div class="top-row"><span class="mono">${esc(n.number)}</span></div>
        <div class="dev"><span class="dot ${n.ready ? 'on' : ''}"></span>${esc(n.device_name)} · IMEI ${esc(imeiDisplay({...n, online: numberDevice?.online ?? n.online}))} · ${n.ready ? '就绪' : '未就绪'}</div>
        <div class="mini"><span>发送</span>${bar(n.send_rate)}<b>${pctText(n.send_rate)}</b></div>
        <div class="mini"><span>接收</span>${bar(n.receive_rate)}<b>${pctText(n.receive_rate)}</b></div></div>`;
    }).join('')}</div>` : `<div class="empty">${icon('phone')}<div>还没有读到号码</div></div>`;
    el.innerHTML = head('总览', '号池短信互发的整体情况（演示数据）', `<button class="btn" data-act="refresh">${icon('refresh')}刷新</button><a class="btn primary" href="#/run">${icon('play')}开始测试</a>`)
      + kpiCards(o, `共 ${d.run_count} 批测试${o.cancelled ? ` · 另有 ${o.cancelled} 条停止未发出` : ''}`)
      + `<div class="card"><div class="card-title">设备与号池 <span class="muted">${d.devices?.length || 0} 台 EC20 · <a href="#/imei">管理 IMEI 关联 →</a></span></div>${devices}</div>`
      + latest + real
      + `<div class="card"><div class="card-title">号码状态<span class="muted">${d.numbers.length} 个号码 · 来自 VoCat 号池（只读）</span></div>${nums}</div>`;
  };
  el.onclick = e => { const a = e.target.closest('[data-act]'); if (a) draw().then(() => toast('已刷新')).catch(x => toast(x.message)); };
  try { await draw(); } catch (x) { if (x.status !== 401) el.innerHTML = head('总览', '') + errorBox(x.message); return; }
  poll(draw, 3000);
}

// ---------------------------------------------------------------- 页面：开始测试
const F = { scope: 'pool', pool: '', poolFrom: '', poolTo: '', sel: 'all', manual: new Set(), q: '', status: '', role: 'from', mode: 'relay', a: '', b: '', rounds: 1, gap: 0.5 };
let liveBatch = null;
const seen = new Set();
const readyNums = () => S.numbers.filter(n => n.ready);
const poolId = n => String(n.device ?? n.pool_id ?? 'unknown');
const poolName = n => `EC20 ${n.device ?? n.pool_id ?? '未知'}`;
const poolList = () => {
  const rows = new Map(S.numbers.map(n => [poolId(n), { id: poolId(n), name: n.pool_name || poolName(n), imei: n.imei || '' }]));
  (S.numbersInfo.devices || []).forEach(d => rows.set(String(d.id), {
    id: String(d.id), name: d.name || poolName({ device: d.id }), imei: d.imei || '', online: d.online,
    present: d.present, profile_count: d.profile_count, reason: d.reason,
  }));
  return [...rows.values()];
};
const poolRows = id => S.numbers.filter(n => poolId(n) === id);
const poolReady = id => poolRows(id).filter(n => n.ready);
function ensurePoolDefaults() {
  const ps = poolList(); if (!ps.length) return;
  if (!ps.some(p => p.id === F.pool)) F.pool = ps[0].id;
  if (!ps.some(p => p.id === F.poolFrom)) F.poolFrom = ps[0].id;
  if (!ps.some(p => p.id === F.poolTo) || F.poolTo === F.poolFrom) F.poolTo = ps.find(p => p.id !== F.poolFrom)?.id || '';
}
function pickedPartition() {
  ensurePoolDefaults();
  const r = readyNums();
  if (F.mode === 'pair') {
    const selected = [F.a, F.b].filter(Boolean).map(x => r.find(n => poolId(n) === F.pool && n.number === x)).filter(Boolean);
    return { all: selected, source: selected.slice(0, 1), target: selected.slice(1, 2) };
  }
  if (F.scope === 'cross') {
    const base = r.filter(n => poolId(n) === F.poolFrom || poolId(n) === F.poolTo);
    const selected = F.sel === 'manual' ? base.filter(n => F.manual.has(n.number)) : base;
    return { all: selected, source: selected.filter(n => poolId(n) === F.poolFrom), target: selected.filter(n => poolId(n) === F.poolTo) };
  }
  let selected = r.filter(n => poolId(n) === F.pool);
  if (F.sel === 'manual') selected = selected.filter(n => F.manual.has(n.number));
  return { all: selected, source: selected, target: [] };
}
function switchPool(id) {
  if (F.pool === id) return;
  F.pool = id; F.manual.clear(); F.q = ''; F.a = ''; F.b = '';
}
function pickedNumbers() {
  return pickedPartition().all.map(n => n.number);
}
function planCount(part) {
  if (F.mode === 'pair') return part.source.length === 1 && part.target.length === 1 && F.a !== F.b ? 2 * F.rounds : 0;
  if (F.mode === 'cross_pool') return part.source.length && part.target.length ? Math.max(part.source.length, part.target.length) * 2 * F.rounds : 0;
  const n = part.all.length;
  if (n < 2) return 0;
  return (F.mode === 'pairs' ? Math.ceil(n / 2) * 2 : n) * F.rounds;
}
function pairPreview(nums) {
  if (nums.length < 2) return '<div class="pair-preview">至少需要 2 个就绪号码；仅有 1 个时，请选择另一台 EC20 或刷新号码。</div>';
  const groups = [];
  for (let i = 0; i < nums.length; i += 2) groups.push([nums[i], nums[i + 1] || nums[0]]);
  return `<div class="pair-preview"><b>首轮自动配对 · ${groups.length} 组 / ${groups.length * 2} 条</b>
    <ol>${groups.slice(0, 6).map(([a, b]) => `<li><span class="mono">${esc(a.number)} ↔ ${esc(b.number)}</span></li>`).join('')}</ol>
    ${groups.length > 6 ? `<p>另有 ${groups.length - 6} 组，全部参与测试。</p>` : ''}
    <div>每组互发 2 条。${nums.length % 2 ? '最后一个号码与本轮第一个补配，所有号码都会参与。' : '相邻号码配成一组。'}下一轮轮换起点。</div></div>`;
}
const DIAG = {
  relay: '<svg class="diag" viewBox="0 0 64 24"><circle cx="8" cy="12" r="4" fill="currentColor"/><circle cx="32" cy="12" r="4" fill="currentColor"/><circle cx="56" cy="12" r="4" fill="currentColor"/><path d="M14 12h11M38 12h11" stroke="currentColor" stroke-width="2" marker-end="url(#ah)"/><defs><marker id="ah" viewBox="0 0 6 6" refX="5" refY="3" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0 6 3 0 6z" fill="currentColor"/></marker></defs></svg>',
  pairs: '<svg class="diag" viewBox="0 0 64 24"><circle cx="8" cy="12" r="4" fill="currentColor"/><circle cx="26" cy="12" r="4" fill="currentColor"/><circle cx="38" cy="12" r="4" fill="currentColor"/><circle cx="56" cy="12" r="4" fill="currentColor"/><path d="M13 9h8M21 15h-8M43 9h8M51 15h-8" stroke="currentColor" stroke-width="2"/></svg>',
  pair: '<svg class="diag" viewBox="0 0 64 24"><circle cx="12" cy="12" r="5" fill="currentColor"/><circle cx="52" cy="12" r="5" fill="currentColor"/><path d="M19 8h26M45 16H19" stroke="currentColor" stroke-width="2"/></svg>',
  cross_pool: '<svg class="diag" viewBox="0 0 64 24"><circle cx="10" cy="12" r="5" fill="currentColor"/><circle cx="54" cy="12" r="5" fill="currentColor"/><path d="M17 8h30M47 16H17" stroke="currentColor" stroke-width="2"/></svg>',
};
function planPreview() {
  const part = pickedPartition(), count = planCount(part), ps = poolList();
  const name = id => ps.find(p => p.id === id)?.name || '未选择';
  let groups = [], hint = '';
  if (F.mode === 'pairs') return pairPreview(part.all);
  if (F.mode === 'cross_pool') {
    if (part.source.length && part.target.length) {
      groups = Array.from({length: Math.max(part.source.length, part.target.length)}, (_, i) =>
        [part.source[i % part.source.length], part.target[i % part.target.length]]);
    }
    hint = '每组双向各发 1 条。较小号池的号码会重复参与，保证每个号码都发、都收。';
  } else if (F.mode === 'pair' && count) groups = [[part.source[0], part.target[0]]];
  else if (F.mode === 'relay' && count) groups = part.all.map((n, i) => [n, part.all[(i + 1) % part.all.length]]);
  return `<div class="pair-preview"><b>首轮配对预览</b><p>${esc(F.scope === 'cross' ? name(F.poolFrom) + ' ↔ ' + name(F.poolTo) : name(F.pool))}</p>
    ${groups.length ? `<ol>${groups.slice(0, 6).map(([a, b]) => `<li class="mono">${esc(a.number)} ${F.mode === 'relay' ? '→' : '↔'} ${esc(b.number)}</li>`).join('')}</ol>${groups.length > 6 ? `<p>另有 ${groups.length - 6} 组参与。</p>` : ''}` : '<p>选择就绪号码后，这里会显示收发关系。</p>'}
    <p>${hint || (F.mode === 'relay' ? '首轮首尾相接，每个号码发 1 条、收 1 条；后续轮次改变接收对象。' : '两个不同号码双向互发。')}</p></div>`;
}
function drawPlan() {
  const el = $('#plan-preview'); if (!el) return;
  const part = pickedPartition(), count = planCount(part);
  el.innerHTML = `<div class="card-title">本次计划<span class="tag">模拟</span></div>
    <div class="plan-summary"><div><span>参与号码</span><b>${part.all.length}</b></div><div><span>消息总数</span><b>${count}</b></div><div><span>轮数</span><b>${F.rounds}</b></div></div>
    ${planPreview()}<p class="muted">${count ? `${esc(MODE_NAME[F.mode])} · 共 ${count} 条模拟消息` : '尚未满足开始条件'}。仅模拟，不发送真实短信。</p>`;
}
function selectionProblem(part) {
  if (!poolList().length) return '尚未读取到设备，请刷新号码。';
  if (F.mode === 'cross_pool' && (!part.source.length || !part.target.length)) return 'A、B 两个号池都至少需要选择 1 个就绪号码。';
  if (F.mode === 'pair' && (!F.a || !F.b || F.a === F.b || part.all.length !== 2)) return '请选择两个不同的就绪号码。';
  if (part.all.length < 2) return '至少选择 2 个就绪号码；未就绪号码不能参与测试。';
  if (planCount(part) > 2000) return '每批最多 2000 条，请减少号码或轮数。';
  return '';
}
function visibleNumberRows() {
  const q = F.q.trim().toLowerCase();
  return S.numbers.filter(n => (F.scope === 'cross' ? [F.poolFrom, F.poolTo].includes(poolId(n)) : poolId(n) === F.pool)
    && (!q || `${n.number} ${poolName(n)} ${n.line_id ?? ''}`.toLowerCase().includes(q))
    && (!F.status || String(n.ready) === F.status));
}
function poolRole(id) {
  if (F.scope !== 'cross') return '';
  if (String(id) === String(F.poolFrom)) return 'A 号池';
  if (String(id) === String(F.poolTo)) return 'B 号池';
  return '';
}
function renderNumberGroups(rows, withCheckbox = true) {
  const ids = [];
  const preferred = F.scope === 'cross' ? [F.poolFrom, F.poolTo] : [F.pool];
  [...preferred, ...rows.map(poolId)].forEach(id => {
    if (id && !ids.includes(id)) ids.push(id);
  });
  const groups = ids.map(id => ({ id, rows: rows.filter(n => poolId(n) === id) })).filter(g => g.rows.length);
  if (!groups.length) return '<div class="empty">没有匹配的号码</div>';
  return groups.map(group => {
    const p = poolList().find(x => String(x.id) === String(group.id)) || { name: poolName({ device: group.id }) };
    const role = poolRole(group.id);
    const ready = group.rows.filter(n => n.ready).length;
    const selected = group.rows.filter(n => F.manual.has(n.number)).length;
    const roleClass = role === 'A 号池' ? 'role-a' : role === 'B 号池' ? 'role-b' : '';
    const roleText = role || '当前号池';
    return `<section class="pick-group" aria-label="${esc(roleText)} ${esc(p.name)}">
      <div class="pick-group-head"><div class="pick-group-title"><span class="pool-role ${roleClass}">${roleText}</span><b>${esc(p.name)}</b></div><span>${ready} 个就绪 · 已选 ${selected}</span></div>
      <div class="pick-group-rows">${group.rows.map(x => `<label class="${x.ready ? '' : 'dis'}">${withCheckbox ? `<input type="checkbox" data-num="${esc(x.number)}" ${F.manual.has(x.number) ? 'checked' : ''} ${x.ready ? '' : 'disabled'}>` : ''}<span class="mono number-value">${esc(x.number)}</span><span class="dev"><strong>${role ? `${role} · ` : ''}${esc(poolName(x))}</strong><br>${esc(imeiDisplay({...x, imei: x.imei || p.imei, online: p.online ?? x.online}))} · ${x.ready ? '就绪' : esc(x.unavailable_reason || '线路尚未就绪')}</span></label>`).join('')}</div>
    </section>`;
  }).join('');
}
function drawForm() {
  const box = $('#run-form'); if (!box) return;
  ensurePoolDefaults();
  const ps = poolList(), part = pickedPartition(), count = planCount(part), problem = selectionProblem(part);
  const secs = count ? Math.ceil((count - 1) * F.gap + (S.settings?.latency_max || 5) + 3) : 0;
  const opts = (sel, other) => '<option value="">选择号码</option>' + poolReady(F.pool).map(x => `<option value="${esc(x.number)}" ${sel === x.number ? 'selected' : ''} ${other === x.number ? 'disabled' : ''}>${esc(x.number)}</option>`).join('');
  const modes = F.scope === 'cross' ? [['cross_pool', '跨池双向互发', '按较大池配对，每组双向发送']] : [['relay', '号池内接力', '依次发送，首尾相接'], ['pairs', '自动分组互发', '两两双向，奇数补配'], ['pair', '指定一对', '选两个不同号码互发']];
  const poolOptions = id => ps.map(p => `<option value="${esc(p.id)}" ${p.id === id ? 'selected' : ''}>${esc(p.name)} · ${poolReady(p.id).length} 个就绪</option>`).join('');
  box.innerHTML = `
    <div class="inventory-meta"><span>VoCat：${esc(S.meta.vocat || '当前连接')}<br>读取时间 ${fmtTime(S.numbersInfo.fetched_at)}</span><button type="button" class="btn" id="refresh-numbers">刷新号码</button></div>
    ${S.numbersInfo.warning ? `<div class="alert warn">${esc(S.numbersInfo.warning)}</div>` : ''}
    <div class="group"><h2><span class="step">1</span>选择号池范围</h2>
      <div class="seg"><button type="button" data-scope="pool" aria-pressed="${F.scope === 'pool'}" class="${F.scope === 'pool' ? 'on' : ''}">单台 EC20 内部</button><button type="button" data-scope="cross" aria-pressed="${F.scope === 'cross'}" class="${F.scope === 'cross' ? 'on' : ''}" ${ps.length < 2 ? 'disabled' : ''}>两台 EC20 之间</button></div>
      ${F.scope === 'cross' ? `<div class="pool-route"><label>A 号池<select id="pool-from">${poolOptions(F.poolFrom)}</select></label><button type="button" class="btn" data-swap="1" aria-label="交换 A、B 号池">⇄</button><label>B 号池<select id="pool-to">${ps.filter(p => p.id !== F.poolFrom).map(p => `<option value="${esc(p.id)}" ${p.id === F.poolTo ? 'selected' : ''}>${esc(p.name)} · ${poolReady(p.id).length} 个就绪</option>`).join('')}</select></label></div><div class="seg role-pick"><button type="button" data-role="from" class="${F.role === 'from' ? 'on' : ''}">点击卡片选择 A 池</button><button type="button" data-role="to" class="${F.role === 'to' ? 'on' : ''}">点击卡片选择 B 池</button></div>` : ''}
      <div class="pool-cards">${ps.map(p => {
        const active = F.scope === 'pool' ? F.pool === p.id : [F.poolFrom, F.poolTo].includes(p.id);
        const role = F.scope === 'cross' ? (F.poolFrom === p.id ? 'A 池 · ' : F.poolTo === p.id ? 'B 池 · ' : '') : '';
        return `<button type="button" class="pool-card ${active ? 'active' : ''}" data-pool="${esc(p.id)}" aria-pressed="${active}" title="设备 ID：${esc(p.id)}"><b>${role}${esc(p.name)}</b><span>${p.online === false ? '离线' : p.online === true ? '在线' : '状态未知'} · ${poolReady(p.id).length} 个就绪</span><small>IMEI：${esc(imeiDisplay(p))}</small><small>配置档案 ${p.profile_count ?? '—'} · 已识别号码 ${poolRows(p.id).length}</small>${p.reason ? `<small class="pool-reason">${esc(p.reason)}</small>` : ''}</button>`;
      }).join('') || '<div class="empty">尚未读取到设备</div>'}</div>
      <p class="muted">每台 EC20 是一个号池。配置档案不等于就绪号码；未就绪设备保留展示。</p>
    </div>
    <div class="group"><h2><span class="step">2</span>选择互发方式</h2><div class="modes">${modes.map(([k,t,d]) => `<button type="button" class="mode ${F.mode === k ? 'on' : ''}" data-mode="${k}" aria-pressed="${F.mode === k}">${DIAG[k]}<b>${t}</b><span>${d}</span></button>`).join('')}</div></div>
    <div class="group"><h2><span class="step">3</span>选择号码</h2>
      ${F.mode === 'pair' ? `<div class="pair-sel"><label>号码 A<select id="pa">${opts(F.a,F.b)}</select></label><span aria-hidden="true">↔</span><label>号码 B<select id="pb">${opts(F.b,F.a)}</select></label></div>` : `
      <div class="seg"><button type="button" data-sel="all" class="${F.sel === 'all' ? 'on' : ''}">${F.scope === 'cross' ? 'A、B 号池全部就绪号码' : '号池全部就绪号码'}</button><button type="button" data-sel="manual" class="${F.sel === 'manual' ? 'on' : ''}">手动选择</button></div>
      ${F.sel === 'manual' ? `<div class="number-tools"><input id="q" aria-label="搜索号码或设备" placeholder="搜索号码或设备" value="${esc(F.q)}"><select id="number-status" aria-label="号码状态"><option value="">全部状态</option><option value="true" ${F.status === 'true' ? 'selected' : ''}>就绪</option><option value="false" ${F.status === 'false' ? 'selected' : ''}>未就绪</option></select></div><div class="actions"><button type="button" class="btn" data-pick="filtered">选中筛选结果中的就绪号码</button><button type="button" class="btn" data-pick="clear">清空选择</button></div>
      <div class="pick-list">${renderNumberGroups(visibleNumberRows(), true)}</div>` : `<details class="pool-numbers"><summary>查看所选 ${part.all.length} 个就绪号码</summary><div class="pick-list">${renderNumberGroups(part.all, false)}</div></details>`}`}
      <div class="picked">已选 <b>${part.all.length}</b> 个号码${F.scope === 'cross' ? ` · A 池 ${part.source.length} / B 池 ${part.target.length}` : ''}</div>
    </div>
    <div class="group"><h2><span class="step">4</span>参数与执行</h2><div class="params"><div><label for="rounds">轮数（1～5）</label><div class="stepper"><button type="button" data-step="-1" aria-label="减少轮数">−</button><input id="rounds" value="${F.rounds}" inputmode="numeric"><button type="button" data-step="1" aria-label="增加轮数">+</button></div></div><div><label for="gap">每条间隔（秒）</label><input id="gap" class="num-input" type="number" min="0.1" max="10" step="0.1" value="${F.gap}"></div></div></div>
    <div id="plan-preview"></div><div class="run-action"><div class="estimate">共 <b>${count}</b> 条 · 预计 <b>${secs} 秒</b><small>仅模拟收发，不会发送真实短信</small></div>${problem ? `<p class="c-warn" role="status">${problem}</p>` : ''}<button class="btn primary block" id="start" ${problem ? 'disabled' : ''}>开始模拟测试</button></div>`;
  drawPlan();
}

function bindForm() {
  const box = $('#run-form');
  box.onclick = e => {
    const t = e.target.closest('[data-pool],[data-scope],[data-sel],[data-mode],[data-step],[data-swap],[data-role],[data-pick]'); if (!t) return;
    if (t.dataset.swap) { [F.poolFrom, F.poolTo] = [F.poolTo, F.poolFrom]; drawForm(); return; }
    if (t.dataset.role) { F.role = t.dataset.role; drawForm(); return; }
    if (t.dataset.pick === 'clear') { F.manual.clear(); drawForm(); return; }
    if (t.dataset.pick === 'filtered') { visibleNumberRows().filter(n => n.ready).forEach(n => F.manual.add(n.number)); drawForm(); return; }
    if (t.dataset.pool) {
      if (F.scope === 'pool') switchPool(t.dataset.pool);
      else if (F.role === 'to' && t.dataset.pool !== F.poolFrom) F.poolTo = t.dataset.pool;
      else if (F.role === 'from' && t.dataset.pool !== F.poolTo) F.poolFrom = t.dataset.pool;
    }
    if (t.dataset.scope) { F.scope = t.dataset.scope; F.mode = F.scope === 'cross' ? 'cross_pool' : 'relay'; F.sel = 'all'; }
    if (t.dataset.sel) F.sel = t.dataset.sel;
    if (t.dataset.mode) F.mode = t.dataset.mode;
    if (t.dataset.step) F.rounds = Math.max(1, Math.min(5, F.rounds + +t.dataset.step));
    drawForm();
  };
  box.onchange = e => {
    const t = e.target;
    if (t.dataset.num) t.checked ? F.manual.add(t.dataset.num) : F.manual.delete(t.dataset.num);
    if (t.id === 'pool') switchPool(t.value);
    if (t.id === 'pool-from') { F.poolFrom = t.value; if (F.poolTo === F.poolFrom) F.poolTo = poolList().find(p => p.id !== F.poolFrom)?.id || ''; }
    if (t.id === 'pool-to') F.poolTo = t.value;
    if (t.id === 'number-status') F.status = t.value;
    if (t.id === 'pa') { F.a = t.value; if (F.a && F.a === F.b) F.b = ''; }
    if (t.id === 'pb') { F.b = t.value; if (F.b && F.b === F.a) F.a = ''; }
    if (t.id === 'rounds') F.rounds = Math.max(1, Math.min(5, parseInt(t.value) || 1));
    if (t.id === 'gap') F.gap = Math.max(0.1, Math.min(10, parseFloat(t.value) || 0.5));
    if (t.id !== 'q') drawForm();
  };
  box.oninput = e => {
    if (e.target.id !== 'q') return;
    F.q = e.target.value; const pos = e.target.selectionStart; drawForm();
    const q = $('#q'); q.focus(); q.setSelectionRange(pos, pos);
  };
  box.addEventListener('click', async e => {
    const refresh = e.target.closest('#refresh-numbers');
    if (refresh) {
      refresh.disabled = true;
      try { const info = await loadNumbers(true); F.a = ''; F.b = ''; drawForm(); toast(info.stale ? '刷新失败，保留上次号码；请查看提示' : '已刷新号码'); }
      catch (x) { refresh.disabled = false; toast(x.message); }
      return;
    }
    if (!e.target.closest('#start')) return;
    const part = pickedPartition(), nums = part.all.map(n => n.number), count = planCount(part);
    if (!count || count > 2000) return toast('请选择至少两个号码，每批最多 2000 条');
    if (F.mode === 'pair' && (!F.a || !F.b || F.a === F.b)) return toast('请选择两个不同的就绪号码');
    if (F.mode === 'cross_pool' && (!part.source.length || !part.target.length)) return toast('两个号池都至少需要一个就绪号码');
    const ok = await confirmBox('开始测试', `将生成 <b>${count}</b> 条演示消息，本批次将使用当前选择的号码。确定开始？`, '确定开始');
    if (!ok) return;
    try {
      const run = await api('/api/runs', { mode: F.mode, numbers: nums, pair: F.mode === 'pair' ? [F.a, F.b] : undefined,
        pool_from: F.mode === 'cross_pool' ? F.poolFrom : undefined, pool_to: F.mode === 'cross_pool' ? F.poolTo : undefined,
        pool_id: F.scope === 'pool' ? F.pool : undefined, rounds: F.rounds, gap: F.gap });
      liveBatch = run.batch; seen.clear(); toast(`已开始：${run.batch}`); await drawLive();
    } catch (x) { toast(x.message); }
  });
}
function steps(m, now) {
  const done = t => now >= t;
  const lbl = (t, text, cls) => `<div class="st ${cls}">${text}${cls === 'done' || cls === 'fail' ? `<small class="num">${clock(t)}</small>` : ''}</div>`;
  if (m.status === 'send_failed') return lbl(m.t_submit, '提交失败', 'fail') + lbl(0, '运营商受理', '') + lbl(0, '对方已收到', '');
  const s1 = done(m.t_submit) ? 'done' : 'doing';
  const s2 = done(m.t_accept) ? 'done' : s1 === 'done' ? 'doing' : '';
  let s3 = m.status === 'delivered' ? 'done' : m.status === 'undelivered' ? 'fail' : s2 === 'done' ? 'doing' : '';
  return lbl(m.t_submit, '已提交', s1) + lbl(m.t_accept, '运营商受理', s2) + lbl(m.t_end, m.status === 'undelivered' ? '未收到' : '对方已收到', s3);
}
async function drawLive() {
  const box = $('#live'); if (!box) return;
  const d = await api('/api/runs/current');
  if (d.state === 'running' && !liveBatch) liveBatch = d.batch;
  if (!box.isConnected) return;
  if (d.state === 'idle' || d.batch !== liveBatch) {
    box.innerHTML = `<div class="live-empty"><div><svg viewBox="0 0 120 90" fill="none" stroke="#CBD5E1" stroke-width="2"><rect x="10" y="14" width="44" height="30" rx="8"/><rect x="66" y="46" width="44" height="30" rx="8"/><path d="M54 30h18l-6-6M66 60H48l6 6"/></svg>
      <div>设置好后点击「开始测试」，进度会显示在这里</div></div></div>`;
    return;
  }
  const o = d.summary.overall, now = d.now;
  const denom = o.planned - o.cancelled, doneN = o.total;
  const progress = denom ? doneN * 100 / denom : 100;
  const list = d.messages.filter(m => m.status !== 'waiting' && m.status !== 'cancelled').sort((a, b) => b.t_start - a.t_start).slice(0, 80);
  const scroll = $('.stream', box)?.scrollTop || 0;
  const banner = d.state === 'running' ? '' : `<div class="banner ${d.state === 'stopped' ? 'stopped' : ''}">${icon(d.state === 'stopped' ? 'stop' : 'check')}
    <span class="grow">${d.state === 'stopped' ? '测试已停止' : '测试完成'} · 发送成功率 ${pctText(o.send_rate)} · 到达率 ${pctText(o.arrive_rate)}${o.cancelled ? ` · ${o.cancelled} 条未发出` : ''}</span>
    <a class="btn" href="#/records/${esc(d.batch)}">查看详情</a></div>`;
  box.innerHTML = `${banner}<div class="live-head">${pill(...RUN_STATE[d.state])}<span class="mono">${esc(d.batch)}</span><span class="tag">演示</span>
      <span class="muted num">${fmtTime(d.started)} · ${esc(d.mode_name)}</span><span class="grow"></span>
      ${d.state === 'running' ? `<button class="btn danger" id="stop">${icon('stop')}停止测试</button>` : ''}</div>
    <div class="progress-line"><span>已处理 <b class="num">${doneN}</b> / <span class="num">${denom}</span> 条</span><span class="num muted">${progress.toFixed(0)}%</span></div>
    <div class="bar big">${`<i style="width:${progress}%"></i>`}</div>
    <div class="live-kpis"><div><span>当前发送成功率</span><b class="num c-${rateCls(o.send_rate)}">${pctText(o.send_rate)}</b></div>
      <div><span>当前到达率</span><b class="num c-${rateCls(o.arrive_rate)}">${pctText(o.arrive_rate)}</b></div>
      <div><span>平均到达用时</span><b class="num">${secText(o.avg_latency_s)}</b></div></div>
    <div class="card-title" style="margin-bottom:8px">实时短信<span class="muted">最新的在最上面${list.length >= 80 ? ' · 只显示最近 80 条' : ''}</span></div>
    <div class="stream">${list.map(m => {
      const fresh = !seen.has(m.seq); seen.add(m.seq);
      const took = m.status === 'delivered' ? `用时 ${secText(m.latency_s)}` : m.reason ? esc(m.reason) : `${(now - m.t_start).toFixed(1)} 秒`;
      return `<div class="msg ${fresh ? 'fresh' : ''}"><span class="seq num">#${m.seq}</span><div>
        <div class="route"><span class="mono">${esc(m.sender)}</span><small>${esc(m.sender_pool_name || '默认号池')} · ${esc(devName(m.sender_dev))}</small>${icon('arrow')}<span class="mono">${esc(m.receiver)}</span><small>${esc(m.receiver_pool_name || '默认号池')} · ${esc(devName(m.receiver_dev))}</small></div>
        <div class="steps">${steps(m, now)}</div></div><div class="right">${statusPill(m.status)}<small class="num">${took}</small></div></div>`;
    }).join('') || '<div class="empty">正在准备第一条…</div>'}</div>`;
  $('.stream', box).scrollTop = scroll;
  const stop = $('#stop');
  if (stop) stop.onclick = async () => {
    if (!await confirmBox('停止测试', '还没开始的短信将不再发出（不计入成功率）。确定停止？', '停止')) return;
    try { await api('/api/runs/current/stop', {}); toast('已停止'); drawLive(); } catch (x) { toast(x.message); }
  };
}
async function pageRun(el) {
  el.innerHTML = head('开始测试', '一台 EC20 就是一个号池，选择其中的号码进行模拟互发（每批最多 2000 条）') + loading();
  try {
    await Promise.all([S.numbers.length ? null : loadNumbers(), S.settings ? null : api('/api/settings').then(s => { S.settings = s; })]);
  } catch (x) { if (x.status !== 401) el.innerHTML = head('开始测试', '') + errorBox(x.message); return; }
  el.innerHTML = head('开始测试', '一台 EC20 就是一个号池，选择其中的号码进行模拟互发（每批最多 2000 条）')
    + `<div class="run-layout"><div class="card" id="run-form"></div><div class="card" id="live"></div></div>`;
  drawForm(); bindForm();
  await drawLive().catch(() => {});
  poll(drawLive, 1000);
}

// ---------------------------------------------------------------- 页面：测试记录
const RF = { mode: '', q: '' };
async function pageRecords(el) {
  el.innerHTML = head('测试记录', '每一批测试的结果') + loading();
  let runs;
  try { runs = await api('/api/runs'); } catch (x) { if (x.status !== 401) el.innerHTML = head('测试记录', '') + errorBox(x.message); return; }
  const draw = () => {
    const list = runs.filter(r => (!RF.mode || r.mode === RF.mode) && (!RF.q || r.batch.toLowerCase().includes(RF.q.toLowerCase())));
    el.innerHTML = head('测试记录', '每一批测试的结果，点「查看」看每条短信的发出 / 收到对照')
      + `<div class="tabs"><a href="#/records" class="on">演示测试 <span class="muted num">${runs.length}</span></a><a href="#/records/real">真实验证 <span class="tag real">真实</span></a></div>
      <div class="card"><div class="filters"><select id="fm"><option value="">全部发法</option>${Object.entries(MODE_NAME).map(([k, v]) => `<option value="${k}" ${RF.mode === k ? 'selected' : ''}>${v}</option>`).join('')}</select>
      <div class="search">${icon('search')}<input id="fq" placeholder="搜索批次号" value="${esc(RF.q)}"></div></div>
      ${list.length ? `<div class="table-wrap"><table><thead><tr><th>批次号</th><th>开始时间</th><th>发法</th><th>号码数</th><th>条数</th><th>发送成功率</th><th>到达率</th><th>平均用时</th><th>状态</th><th>操作</th></tr></thead><tbody>
      ${list.map(r => { const o = r.summary.overall; return `<tr><td><span class="mono">${esc(r.batch)}</span> <span class="tag">演示</span></td><td class="num">${fmtTime(r.started)}</td><td>${esc(r.mode_name)}</td>
        <td class="num">${r.number_count}</td><td class="num">${o.total}${o.cancelled ? ` <span class="muted">(+${o.cancelled} 未发)</span>` : ''}</td><td>${rateCell(o.send_rate)}</td><td>${rateCell(o.arrive_rate)}</td>
        <td class="num">${secText(o.avg_latency_s)}</td><td>${pill(...RUN_STATE[r.state])}</td><td><a href="#/records/${esc(r.batch)}">查看</a></td></tr>`; }).join('')}</tbody></table></div>`
      : `<div class="empty">${icon('inbox')}<div>${runs.length ? '没有符合条件的记录' : '还没有测试记录'}</div></div>`}</div>`;
    $('#fm').onchange = e => { RF.mode = e.target.value; draw(); };
    $('#fq').oninput = e => { RF.q = e.target.value; const p = e.target.selectionStart; draw(); const q = $('#fq'); q.focus(); q.setSelectionRange(p, p); };
  };
  draw();
}
function bubbleRows(msgs, real) {
  return msgs.map(m => {
    const got = m.status === 'delivered';
    const recvText = real ? m.received_text : m.text;
    const same = got && recvText === m.text;
    const planned = m.status === 'cancelled';
    const res = `${statusPill(m.status)}${got ? `<span class="num">${secText(m.latency_s)}</span><span class="${same ? 'same' : 'diff'}">${same ? '✓ 内容一致' : '✕ 内容不一致'}</span>` : m.reason ? `<span class="muted">${esc(m.reason)}</span>` : ''}`;
    return `<div class="brow"><span class="seq num muted">#${m.seq}</span>
      <div class="bubble ${planned ? 'none' : 'out'}"><div class="who"><span class="mono">${esc(m.sender)}</span> · ${esc(devName(m.sender_dev))} ${planned ? '计划发出（未发送）' : '发出'}</div><div class="txt">${esc(m.text)}</div></div>
      <div class="bubble ${got ? 'in' : 'none'}"><div class="who"><span class="mono">${esc(m.receiver)}</span> · ${esc(devName(m.receiver_dev))} 收到</div><div class="txt">${got ? esc(recvText) : '（没有收到）'}</div></div>
      <div class="res">${res}</div></div>`;
  }).join('');
}
function perNumberTable(rows) {
  if (!rows.length) return '<div class="empty">暂无数据</div>';
  return `<div class="table-wrap"><table><thead><tr><th>号码</th><th>设备</th><th>作为发送方</th><th>发送成功率</th><th>作为接收方</th><th>接收成功率</th></tr></thead><tbody>
    ${rows.map(p => `<tr><td class="mono">${esc(p.number)}</td><td>${esc(devName(p.device))}</td>
      <td class="num">${p.sent ? `${p.sent_ok} / ${p.sent}` : '<span class="muted">未测</span>'}</td><td>${p.sent ? rateCell(p.send_rate) : ''}</td>
      <td class="num">${p.expected_in ? `${p.received} / ${p.expected_in}` : '<span class="muted">未测</span>'}</td><td>${p.expected_in ? rateCell(p.receive_rate) : ''}</td></tr>`).join('')}</tbody></table></div>`;
}
function poolResultTable(msgs) {
  const by = new Map();
  msgs.filter(m => ['delivered', 'send_failed', 'undelivered'].includes(m.status)).forEach(m => {
    const from = String(m.sender_pool || 'pool-default');
    const to = String(m.receiver_pool || 'pool-default');
    const fromName = m.sender_pool_name || '默认号池';
    const toName = m.receiver_pool_name || '默认号池';
    const a = by.get(from) || { id: from, name: fromName, sent: 0, sentOk: 0, expected: 0, received: 0 };
    const b = from === to ? a : (by.get(to) || { id: to, name: toName, sent: 0, sentOk: 0, expected: 0, received: 0 });
    a.sent++; a.sentOk += m.status !== 'send_failed';
    b.expected++; b.received += m.status === 'delivered';
    by.set(from, a); by.set(to, b);
  });
  const rows = [...by.values()].sort((a, b) => a.name.localeCompare(b.name));
  if (!rows.length) return '';
  return `<div class="card"><div class="card-title">号池统计<span class="muted">按发送和接收号池汇总</span></div><div class="table-wrap"><table><thead><tr><th>号池</th><th>发送条数</th><th>发送成功率</th><th>应接收</th><th>实际接收</th><th>接收成功率</th></tr></thead><tbody>${rows.map(p => `<tr><td><b>${esc(p.name)}</b><small class="muted">${esc(p.id)}</small></td><td class="num">${p.sent}</td><td>${rateCell(p.sent ? p.sentOk * 100 / p.sent : null)}</td><td class="num">${p.expected}</td><td class="num">${p.received}</td><td>${rateCell(p.expected ? p.received * 100 / p.expected : null)}</td></tr>`).join('')}</tbody></table></div></div>`;
}
async function pageRecordDetail(el, id) {
  const real = id === 'real';
  el.innerHTML = loading();
  let d;
  try { d = await api(real ? '/api/real' : `/api/runs/${encodeURIComponent(id)}`); }
  catch (x) { if (x.status !== 401) el.innerHTML = `<a class="back" href="#/records">${icon('back')}返回测试记录</a>` + errorBox(x.message); return; }
  let limit = 50, showCancelled = false;
  const draw = () => {
    const o = d.summary.overall;
    const sent = d.messages.filter(m => m.status !== 'cancelled');
    const cancelled = d.messages.filter(m => m.status === 'cancelled');
    const title = real ? '真实验证 <span class="tag real">真实</span>' : `<span class="mono">${esc(d.batch)}</span> <span class="tag">演示</span>`;
    const desc = real ? `2026-09-22 用 VoCat 真实发送（批次 ${d.batches.map(b => esc(b.batch)).join('、')}）。受 VoCat 每小时 10 条的限制，被挡住没发出的已排除。`
      : `${fmtTime(d.started)} · ${esc(d.mode_name)} · ${d.number_count} 个号码 · ${d.rounds} 轮 · 操作人 ${esc(d.user)} · 模拟数据`;
    el.innerHTML = `<a class="back" href="#/records${real ? '' : ''}">${icon('back')}返回测试记录</a>`
      + head(title, desc, real ? '' : `${pill(...RUN_STATE[d.state])}<a class="btn" href="/api/runs/${esc(d.batch)}.csv">${icon('download')}导出 CSV</a>`)
      + (real ? `<div class="alert ok">${icon('check')}这是真实发送的结果，不是模拟数据。</div>` : '')
      + kpiCards(o, real ? '真实发出的条数' : (o.cancelled ? `另有 ${o.cancelled} 条停止未发出` : `共计划 ${o.planned} 条`))
      + `<div class="card"><div class="card-title">每条短信<span class="muted">左边是发出的内容，右边是对方收到的内容</span></div><div class="bubbles">
        ${bubbleRows(sent.slice(0, limit), real)}</div>
        ${sent.length > limit ? `<div class="more"><button class="btn" data-act="more">再显示 50 条（还有 ${sent.length - limit} 条）</button></div>` : ''}
        ${cancelled.length ? (showCancelled ? `<div class="bubbles" style="margin-top:10px">${bubbleRows(cancelled, real)}</div>`
          : `<div class="alert warn" style="margin:12px 0 0;cursor:pointer" data-act="cancelled">${icon('info')}另有 ${cancelled.length} 条因停止测试未发出（不计入成功率）· 点击展开</div>`) : ''}</div>
       ${poolResultTable(sent)}<div class="card"><div class="card-title">每个号码</div>${perNumberTable(d.summary.per_number)}</div>`;
  };
  el.onclick = e => {
    const a = e.target.closest('[data-act]'); if (!a) return;
    if (a.dataset.act === 'more') limit += 50;
    if (a.dataset.act === 'cancelled') showCancelled = true;
    draw();
  };
  draw();
  if (!real && d.state === 'running') poll(async () => { d = await api(`/api/runs/${encodeURIComponent(id)}`); draw(); if (d.state !== 'running') stopPoll(); }, 1500);
}

// ---------------------------------------------------------------- 页面：号码列表
const NF = { pool: '', device: '', ready: '' };
async function pageNumbers(el, refresh) {
  const actions = `<button class="btn primary" data-act="refresh">${icon('refresh')}刷新</button>`;
  el.innerHTML = head('号码列表', '数据来自 VoCat 号池（只读）', actions) + loading();
  let d, info;
  try { info = await loadNumbers(refresh); d = await api('/api/overview'); }
  catch (x) { if (x.status !== 401) el.innerHTML = head('号码列表', '数据来自 VoCat 号池（只读）', actions) + errorBox(x.message, 'refresh'); el.onclick = e => { if (e.target.closest('[data-act]')) pageNumbers(el, true); }; return; }
  const devices = (info.devices || []).map(x => String(x.id));
  const poolOptions = [...new Map((info.devices || []).map(x => [String(x.id), x.name || poolName({device: x.id})])).entries()];
  d.numbers.forEach(n => { if (!poolOptions.some(([id]) => id === poolId(n))) poolOptions.push([poolId(n), poolName(n)]); if (!devices.includes(String(n.device))) devices.push(String(n.device)); });
  const draw = () => {
    const list = d.numbers.filter(n => (!NF.pool || poolId(n) === NF.pool) && (!NF.device || n.device === NF.device) && (NF.ready === '' || String(n.ready) === NF.ready));
    el.innerHTML = head('号码列表', `数据来自 VoCat 号池（只读）· 读取时间 ${fmtTime(info.fetched_at)}`, actions)
      + (info.warning ? `<div class="alert warn">${icon('info')}${esc(info.warning)}</div>` : '')
      + `<div class="card"><div class="filters"><select id="np"><option value="">全部号池</option>${poolOptions.map(([id, name]) => `<option value="${esc(id)}" ${NF.pool === id ? 'selected' : ''}>${esc(name)}</option>`).join('')}</select><select id="nd"><option value="">全部设备</option>${devices.map(x => `<option value="${esc(x)}" ${NF.device === x ? 'selected' : ''}>${esc(devName(x))}</option>`).join('')}</select>
        <select id="nr"><option value="">全部状态</option><option value="true" ${NF.ready === 'true' ? 'selected' : ''}>就绪</option><option value="false" ${NF.ready === 'false' ? 'selected' : ''}>未就绪</option></select>
        <span class="muted" style="align-self:center">共 ${list.length} 个</span></div>
      ${list.length ? `<div class="table-wrap"><table><thead><tr><th>号池</th><th>IMEI</th><th>号码</th><th>EC20 / 线路</th><th>是否就绪</th><th>累计发送成功率</th><th>累计接收成功率</th><th>最近测试时间</th></tr></thead><tbody>
        ${list.map(n => { const device = (info.devices || []).find(x => String(x.id) === String(poolId(n))); return `<tr><td>${esc(poolName(n))}</td><td class="mono">${esc(imeiDisplay({...n, imei: n.imei || device?.imei, online: device?.online ?? n.online}))}</td><td class="mono">${esc(n.number)}</td><td>${esc(poolName(n))}${n.line_id != null ? ' · 线路 ' + esc(n.line_id) : ''}</td><td>${n.ready ? pill('就绪', 'ok') : pill('未就绪', 'grey')}</td>
          <td>${n.sent ? rateCell(n.send_rate) : '<span class="muted">未测</span>'}</td><td>${n.expected_in ? rateCell(n.receive_rate) : '<span class="muted">未测</span>'}</td>
          <td class="num">${n.last_tested ? fmtTime(n.last_tested) : '<span class="muted">—</span>'}</td></tr>`; }).join('')}</tbody></table></div>`
        : `<div class="empty">${icon('phone')}<div>没有符合条件的号码</div></div>`}
      <div class="muted" style="margin-top:12px;font-size:12px">成功率按演示测试累计计算。</div></div>`;
     $('#np').onchange = e => { NF.pool = e.target.value; draw(); };
     $('#nd').onchange = e => { NF.device = e.target.value; draw(); };
    $('#nr').onchange = e => { NF.ready = e.target.value; draw(); };
  };
  el.onclick = e => { if (e.target.closest('[data-act="refresh"]')) pageNumbers(el, true).then(() => toast('已从 VoCat 重新读取号码')); };
  draw();
}

// ---------------------------------------------------------------- 页面：IMEI 识别与 EC20 关联
const IMEI_PAGE = {
  q: "", selected: "", data: null, lookup: null,
  manualImei: "", manualLookup: null, manualLoading: false, manualError: "",
  batchText: "", batchResults: [], batchLoading: false, batchError: "",
  savedRecords: null, savedError: "", saving: false,
};
const imeiOnlineText = value => value === true ? "在线" : value === false ? "离线" : "状态未知";
const imeiModelStatus = value => ({
  matched: ["已识别", "ok"], ambiguous: ["多个候选", "warn"],
  unknown: ["数据源未收录", "grey"], invalid: ["IMEI 无效", "bad"], missing: ["未提供 IMEI", "grey"],
}[value] || [value || "未查询", "grey"]);
const imeiDeviceLabel = d => String(d?.name || d?.device_id || "未命名设备").trim();
const imeiPoolLabel = d => String(d?.pool_name || d?.pool_id || "未分配号池").trim();
const parseImeiBatch = text => String(text || "").split(/[\s,;，；、]+/).filter(Boolean);
const imeiCandidateDetails = result => (result.candidates || []).length > 1
  ? `<details><summary>查看 ${result.candidates.length} 个候选</summary>${result.candidates.map(c => `<div>${esc(c.brand)} · ${esc(c.specs)}</div>`).join("")}</details>` : "";

function pageImei(el) {
  const active = () => el.isConnected && location.hash === '#/imei' && !!S.me;
  el.innerHTML = head("IMEI 设备识别", "从 VoCat 读取 EC20 和 IMEI，核对设备型号、号池与号码状态") + loading();

  const visibleDevices = () => {
    const q = IMEI_PAGE.q.trim().toLowerCase();
    return (IMEI_PAGE.data?.devices || []).filter(d => !q || [
      d.device_id, d.name, d.imei, ...(d.imeis || []), d.pool_name,
    ].join(" ").toLowerCase().includes(q));
  };
  const selectedDevice = () => (IMEI_PAGE.data?.devices || [])
    .find(d => String(d.device_id) === String(IMEI_PAGE.selected));

  const draw = () => {
    if (!active()) return;
    const rows = visibleDevices();
    const device = selectedDevice() || rows[0];
    if (device && String(IMEI_PAGE.selected) !== String(device.device_id)) {
      IMEI_PAGE.selected = String(device.device_id);
    }
    const model = IMEI_PAGE.lookup?.result;
    const manualModel = IMEI_PAGE.manualLookup?.result;
    const sourceLive = IMEI_PAGE.data?.source === "VoCat";
    const sourceLabel = sourceLive ? "实时 VoCat" : "最近缓存";
    const sourceClass = sourceLive ? "ok" : "warn";
    const online = device ? imeiOnlineText(device.online) : "状态未知";
    const modelStatus = model ? imeiModelStatus(model.status) : ["查询中", "info"];
    const candidates = model?.candidates || [];
    const deviceInfo = device ? [
      ["设备名称", imeiDeviceLabel(device)],
      ["device_id", device.device_id || "—"],
      ["完整 IMEI", device.imei || "未读取"],
      ["IMEI 来源", device.imei_source || "VoCat 设备快照"],
      ["在线状态", online],
      ["号池", imeiPoolLabel(device)],
    ] : [];

    const deviceButtons = rows.map(d => "<button type=\"button\" class=\"imei-query-device " +
      (String(d.device_id) === String(IMEI_PAGE.selected) ? "on" : "") +
      "\" data-imei-device=\"" + esc(d.device_id) + "\">" +
      "<span class=\"query-device-title\"><b>" + esc(imeiDeviceLabel(d)) + "</b>" +
      pill(imeiOnlineText(d.online), d.online === true ? "ok" : d.online === false ? "grey" : "warn") +
      "</span><span class=\"mono\">" + esc(d.imei || "未读取") + "</span>" +
      "<small>" + esc(imeiPoolLabel(d)) + " · 就绪 " + (d.ready_count ?? 0) + "/" + (d.number_count ?? 0) + "</small></button>").join("");

    const modelCandidates = model?.status === "ambiguous" && candidates.length
      ? "<div class=\"query-candidates\"><b>候选记录</b>" + candidates.map(c =>
          "<div><strong>" + esc(c.brand || "未知品牌") + "</strong><span>" +
          esc(c.specs || "型号信息未提供") + "</span></div>").join("") + "</div>" : "";

    const manualCandidates = manualModel?.status === "ambiguous" && (manualModel.candidates || []).length
      ? "<div class=\"query-candidates\"><b>候选记录</b>" + manualModel.candidates.map(c =>
          "<div><strong>" + esc(c.brand || "未知品牌") + "</strong><span>" +
          esc(c.specs || "型号信息未提供") + "</span></div>").join("") + "</div>" : "";
    const manualStatus = manualModel ? imeiModelStatus(manualModel.status) : ["等待查询", "grey"];
    const batchResults = IMEI_PAGE.batchResults || [];
    const batchMatched = batchResults.filter(x => x.result?.status === "matched").length;
    const batchResultRows = batchResults.length ? batchResults.map((row, index) => {
      const result = row.result || {};
      const status = imeiModelStatus(result.status);
      return "<tr><td class=\"num\">" + (index + 1) + "</td><td class=\"mono\">" + esc(row.imei) +
        "</td><td>" + pill(status[0], status[1]) + "</td><td class=\"mono\">" + esc(result.tac || "—") +
        "</td><td>" + esc(result.manufacturer || "—") + "</td><td>" + esc(result.model || "—") + imeiCandidateDetails(result) +
        "</td><td>" + esc(result.device_type || "数据源未提供") + "</td></tr>";
    }).join("") : "<tr><td colspan=\"7\"><div class=\"empty\">还没有批量查询结果</div></td></tr>";
    const savedRecords = IMEI_PAGE.savedRecords || [];
    const savedRows = savedRecords.length ? savedRecords.map(record => {
      const status = imeiModelStatus(record.format_status === 'invalid' ? 'invalid' : record.model_status);
      return "<tr><td class=\"mono\">" + esc(record.imei) + "</td><td class=\"mono\">" + esc(record.tac || "—") +
        "</td><td>" + pill(status[0], status[1]) + "</td><td>" + esc(record.brand || "—") + "</td><td>" +
        esc(record.model || "—") + imeiCandidateDetails(record) + "<span class=\"table-sub\">来源：" + esc(record.source || "—") +
        " · 类型：" + esc(record.device_type || "数据源未提供") + "</span></td><td>" + esc(record.created_at ? fmtTime(record.created_at) : "—") +
        "</td><td><button class=\"btn small\" data-act=\"imei-delete-record\" data-imei-record=\"" + esc(record.id) + "\">删除</button></td></tr>";
    }).join("") : "<tr><td colspan=\"7\"><div class=\"empty\">暂无保存记录</div></td></tr>";
    const manualResult = IMEI_PAGE.manualLoading
      ? "<div class=\"imei-manual-placeholder\" aria-live=\"polite\">" + icon("refresh") + "正在查询 TAC 数据源…</div>"
      : manualModel
        ? "<div class=\"query-model-status\"><span class=\"pill " + manualStatus[1] + "\">" + esc(manualStatus[0]) +
          "</span><span>" + esc(manualModel.source || "本地 IMEI 数据源") + "</span></div>" +
          "<div class=\"query-info-grid model-grid\"><div><span>完整 IMEI</span><b class=\"mono\">" + esc(manualModel.imei || "—") +
          "</b></div><div><span>TAC</span><b class=\"mono\">" + esc(manualModel.tac || "—") +
          "</b></div><div><span>厂商</span><b>" + esc(manualModel.manufacturer || "—") +
          "</b></div><div><span>型号</span><b>" + esc(manualModel.model || "—") +
          "</b></div><div><span>设备类型</span><b>" + esc(manualModel.device_type || (manualModel.status === "unknown" ? "数据源未提供" : "—")) +
          "</b></div></div>" + manualCandidates +
          "<div class=\"query-note\">" + (manualModel.status === "unknown" ? "该 TAC 当前未被数据源收录，不会猜测型号。" :
            manualModel.status === "invalid" ? "请输入 15 位数字 IMEI，并确认校验位正确。" :
          "查询结果来自 IMEI 数据源，用于设备型号和身份核对。") +
          (manualModel.imei ? "<div class=\"query-actions\"><button class=\"btn\" data-act=\"imei-save-manual\"" + (IMEI_PAGE.saving ? " disabled" : "") + ">保存此条记录</button></div>" : "") + "</div>"
        : "<div class=\"imei-manual-placeholder\">输入完整 IMEI 后，右侧会显示 TAC、厂商、型号和设备类型。</div>";

    el.innerHTML = head("IMEI 设备识别",
      "从 VoCat 读取 EC20 设备及其 IMEI，按完整 IMEI 的 TAC 识别厂商和型号",
      "<button class=\"btn\" data-act=\"imei-refresh\">" + icon("refresh") + "刷新 VoCat</button>")
      + "<div class=\"imei-source-banner " + (sourceLive ? "" : "stale") + "\">" +
        "<span>" + icon(sourceLive ? "check" : "info") + "<b>" + sourceLabel + "</b></span>" +
        "<span>" + esc(IMEI_PAGE.data?.warning || (sourceLive ? "设备和 IMEI 来自当前登录的 VoCat。" : "VoCat 暂时不可用，当前显示最近一次快照。")) + "</span>" +
        (IMEI_PAGE.data?.fetched_at ? "<small>读取时间 " + fmtTime(IMEI_PAGE.data.fetched_at) + "</small>" : "") + "</div>"
      + "<section class=\"card imei-manual-query\"><div class=\"card-title\">手动 IMEI 查询 <span class=\"muted\">不依赖 VoCat 设备选择，直接查询 IMEI 数据源</span></div>" +
        "<div class=\"imei-manual-layout\"><form id=\"imei-manual-form\" class=\"imei-manual-input\">" +
        "<label for=\"imei-manual-value\">输入完整 IMEI</label><div class=\"imei-manual-control\"><input id=\"imei-manual-value\" name=\"imei\" class=\"search-input mono\" inputmode=\"numeric\" autocomplete=\"off\" maxlength=\"15\" placeholder=\"例如 490154203237518\" value=\"" + esc(IMEI_PAGE.manualImei) + "\" required><button class=\"btn primary\" type=\"submit\"" + (IMEI_PAGE.manualLoading ? " disabled" : "") + ">" + icon("search") + "查询</button></div>" +
        "<div class=\"hint\">请输入 15 位数字 IMEI；查询只读取本地 TAC 数据源，不会修改 VoCat 设备。</div>" +
        (IMEI_PAGE.manualError ? "<div class=\"login-err imei-manual-error\" role=\"alert\">" + esc(IMEI_PAGE.manualError) + "</div>" : "") +
        "</form><div class=\"imei-manual-result\" aria-live=\"polite\"><div class=\"manual-result-title\">查询结果</div>" + manualResult + "</div></div></section>"
      + "<section class=\"card imei-batch-query\"><div class=\"card-title\">批量 IMEI 查询 <span class=\"muted\">每行一个 IMEI，单次最多 500 个</span></div>" +
        "<div class=\"imei-batch-layout\"><form id=\"imei-batch-form\" class=\"imei-batch-input\"><label for=\"imei-batch-value\">批量输入</label>" +
        "<textarea id=\"imei-batch-value\" class=\"mono\" rows=\"7\" placeholder=\"每行输入一个完整 IMEI\">" + esc(IMEI_PAGE.batchText) + "</textarea>" +
        "<div class=\"hint\">支持换行、空格、逗号或分号分隔；重复和无效输入会逐条显示。点击保存后，记录在刷新或重启后仍可查看。</div>" +
        (IMEI_PAGE.batchError ? "<div class=\"login-err imei-manual-error\" role=\"alert\">" + esc(IMEI_PAGE.batchError) + "</div>" : "") +
        "<button class=\"btn primary\" type=\"submit\"" + (IMEI_PAGE.batchLoading ? " disabled" : "") + ">" + icon("search") + (IMEI_PAGE.batchLoading ? "查询中…" : "批量查询") + "</button></form>" +
        "<div class=\"imei-batch-result\" aria-live=\"polite\" aria-busy=\"" + IMEI_PAGE.batchLoading + "\"><div class=\"batch-summary\"><span>" + (IMEI_PAGE.batchLoading ? "正在查询…" : "共 " + batchResults.length + " 条") + "</span><span>已识别 " + batchMatched + " 条</span><span>无效 " + batchResults.filter(x => !x.result?.valid).length + " 条</span>" +
        (batchResults.length ? "<button class=\"btn small\" data-act=\"imei-save-batch\"" + (IMEI_PAGE.saving ? " disabled" : "") + ">保存全部结果</button>" : "") + "</div>" +
        "<div class=\"table-wrap\"><table class=\"imei-result-table\"><thead><tr><th>#</th><th>IMEI</th><th>状态</th><th>TAC</th><th>厂商</th><th>型号</th><th>设备类型</th></tr></thead><tbody>" + batchResultRows + "</tbody></table></div></div></div></section>" +
      "<section class=\"card imei-saved-records\"><div class=\"card-title\">已保存的 IMEI 记录 <span class=\"muted\">" + (IMEI_PAGE.savedRecords === null ? "加载中…" : savedRecords.length + " 条 · 相同 IMEI 不重复保存") + "</span><button class=\"btn small\" data-act=\"imei-refresh-records\">刷新</button></div>" +
        (IMEI_PAGE.savedError ? "<div class=\"login-err imei-manual-error\" role=\"alert\">" + esc(IMEI_PAGE.savedError) + "</div>" : "") +
        "<div class=\"table-wrap\"><table class=\"imei-result-table\"><thead><tr><th>IMEI</th><th>TAC</th><th>状态</th><th>厂商</th><th>型号</th><th>保存时间</th><th>操作</th></tr></thead><tbody>" + savedRows + "</tbody></table></div></section>"
      + "<div class=\"imei-query-layout\"><aside class=\"card imei-query-sidebar\">" +
        "<div class=\"card-title\">VoCat 设备 <span class=\"muted\">" + rows.length + " 台</span></div>" +
        "<input id=\"imei-device-search\" class=\"search-input\" type=\"search\" aria-label=\"搜索 VoCat 设备或 IMEI\" placeholder=\"搜索设备名、设备 ID 或 IMEI\" value=\"" + esc(IMEI_PAGE.q) + "\">" +
        "<div class=\"imei-query-device-list\">" + (deviceButtons || "<div class=\"empty\">VoCat 当前没有匹配的 EC20 设备</div>") + "</div></aside>" +
        "<section class=\"imei-query-main\">" +
        (device ? "<div class=\"card\"><div class=\"card-title\">VoCat 设备信息 " + pill(sourceLabel, sourceClass) +
          "<span class=\"card-title-actions\">" + pill(online, device.online === true ? "ok" : device.online === false ? "grey" : "warn") + "</span></div>" +
          "<div class=\"query-info-grid\">" + deviceInfo.map(([label, value]) =>
            "<div><span>" + esc(label) + "</span><b class=\"" + (label.includes("IMEI") || label === "device_id" ? "mono" : "") + "\">" + esc(value) + "</b></div>").join("") + "</div>" +
          "<div class=\"query-stats\"><div><span>配置档案</span><b>" + (device.profile_count ?? "—") + "</b></div>" +
          "<div><span>号码总数</span><b>" + (device.number_count ?? 0) + "</b></div>" +
          "<div><span>就绪号码</span><b>" + (device.ready_count ?? 0) + "</b></div>" +
          "<div><span>设备状态</span><b>" + esc(device.reason || online) + "</b></div></div>" +
          (device.imeis?.length > 1 ? "<div class=\"query-note\">VoCat 线路还上报了其他 network_imei：" +
            device.imeis.slice(1).map(x => "<span class=\"mono\">" + esc(x) + "</span>").join("、") + "</div>" : "") +
          "<div class=\"query-actions\"><a class=\"btn primary\" href=\"#/run\" data-imei-run-pool=\"" + esc(device.pool_id) + "\">" +
            icon("play") + "去该号池测试</a></div></div>" +
          "<div class=\"card\"><div class=\"card-title\">型号识别结果 <span class=\"muted\">完整 IMEI → TAC（前 8 位）→ 本地 IMEI 数据源</span></div>" +
          "<div class=\"query-model-status\">" + pill(modelStatus[0], modelStatus[1]) + "<span>" + esc(model?.source || "正在查询 TAC 数据源…") + "</span></div>" +
          "<div class=\"query-info-grid model-grid\"><div><span>TAC</span><b class=\"mono\">" + esc(model?.tac || "—") + "</b></div>" +
          "<div><span>厂商</span><b>" + esc(model?.manufacturer || "—") + "</b></div>" +
          "<div><span>型号</span><b>" + esc(model?.model || "—") + "</b></div>" +
          "<div><span>设备类型</span><b>" + esc(model?.device_type || (model?.status === "unknown" ? "数据源未提供" : "—")) + "</b></div></div>" +
          modelCandidates +
          "<div class=\"query-note\">" + (model?.status === "unknown" ? "该 TAC 当前未被数据源收录，不会猜测型号。" :
            model?.status === "invalid" ? "VoCat 返回的 IMEI 未通过 15 位和 Luhn 校验，请先核对设备数据。" :
            "型号结果用于设备身份核对，不代表 USB 物理位置或短信能力。") + "</div>" +
          (model?.imei ? '<div class="query-actions"><button class="btn" data-act="imei-save-device"' + (IMEI_PAGE.saving ? ' disabled' : '') + '>保存此设备查询记录</button></div>' : '') + "</div>" :
          "<div class=\"card\"><div class=\"empty\">" + icon("device") + "<div>VoCat 当前没有设备数据</div><small>请确认已登录 VoCat，或点击刷新。</small></div></div>") +
        "</section></div>";

    const search = $("#imei-device-search");
    if (search) search.oninput = e => {
      IMEI_PAGE.q = e.target.value;
      draw();
      const next = $("#imei-device-search");
      next?.focus();
      next?.setSelectionRange(IMEI_PAGE.q.length, IMEI_PAGE.q.length);
    };
    const manualInput = $("#imei-manual-value");
    if (manualInput) manualInput.oninput = e => { IMEI_PAGE.manualImei = e.target.value; };
    const batchInput = $("#imei-batch-value");
    if (batchInput) batchInput.oninput = e => { IMEI_PAGE.batchText = e.target.value; };
  };

  const lookup = async () => {
    const device = selectedDevice();
    const result = device?.imei
      ? await api("/api/imei/lookup?imei=" + encodeURIComponent(device.imei))
      : { result: { status: "missing", source: "VoCat 未读取到完整 IMEI" } };
    if (selectedDevice()?.device_id !== device?.device_id) return;
    IMEI_PAGE.lookup = result;
    draw();
  };

  const reload = async () => {
    IMEI_PAGE.data = await api("/api/imei/devices");
    const rows = visibleDevices();
    if (!rows.some(d => String(d.device_id) === String(IMEI_PAGE.selected))) IMEI_PAGE.selected = rows[0]?.device_id || "";
    IMEI_PAGE.lookup = null;
    draw();
    await lookup();
  };

  const refreshSaved = async () => {
    try {
      const saved = await api("/api/imei");
      IMEI_PAGE.savedRecords = saved.records || [];
      IMEI_PAGE.savedError = "";
    } catch (x) {
      IMEI_PAGE.savedError = x.message;
    }
    draw();
  };

  const saveImeis = async imeis => {
    if (IMEI_PAGE.saving) return;
    const values = [...new Set((imeis || []).map(value => String(value || "").trim()).filter(Boolean))];
    if (!values.length) return;
    IMEI_PAGE.saving = true;
    draw();
    try {
      const saved = await api("/api/imei/save-results", { imeis: values });
      IMEI_PAGE.savedRecords = saved.records || [];
      IMEI_PAGE.savedError = "";
      toast("已保存 " + (saved.added ?? 0) + " 条 IMEI 记录" + (saved.ignored ? "，重复 " + saved.ignored + " 条" : ""));
    } catch (x) {
      toast(x.message);
    } finally {
      IMEI_PAGE.saving = false;
      draw();
    }
  };

  el.onclick = async e => {
    const device = e.target.closest("[data-imei-device]");
    if (device) {
      IMEI_PAGE.selected = device.dataset.imeiDevice;
      IMEI_PAGE.lookup = null;
      draw();
      await lookup().catch(x => toast(x.message));
      return;
    }
    const pool = e.target.closest("[data-imei-run-pool]");
    if (pool) {
      F.scope = "pool";
      F.mode = "pairs";
      switchPool(pool.dataset.imeiRunPool);
      return;
    }
    if (e.target.closest("[data-act=\"imei-refresh\"]")) await reload().catch(x => { if (x.status !== 401) toast(x.message); });
    if (e.target.closest("[data-act=\"imei-save-manual\"]")) await saveImeis([IMEI_PAGE.manualLookup?.result?.imei]);
    if (e.target.closest("[data-act=\"imei-save-device\"]")) await saveImeis([IMEI_PAGE.lookup?.result?.imei]);
    if (e.target.closest("[data-act=\"imei-save-batch\"]")) await saveImeis(IMEI_PAGE.batchResults.map(x => x.imei));
    if (e.target.closest("[data-act=\"imei-refresh-records\"]")) await refreshSaved();
    const del = e.target.closest("[data-act=\"imei-delete-record\"]");
    if (del) {
      const ok = await confirmBox("删除 IMEI 记录", "删除后只会移除本地保存记录，不会影响 VoCat 设备。");
      if (!ok) return;
      try {
        const saved = await api("/api/imei", { action: "delete", ids: [del.dataset.imeiRecord] });
        IMEI_PAGE.savedRecords = saved.records || [];
        draw();
        toast("已删除");
      } catch (x) { toast(x.message); }
    }
  };

  el.onsubmit = async e => {
    if (e.target?.id === "imei-batch-form") {
      e.preventDefault();
      if (IMEI_PAGE.batchLoading) return;
      IMEI_PAGE.batchText = String($("#imei-batch-value")?.value || "");
      IMEI_PAGE.batchError = "";
      const values = parseImeiBatch(IMEI_PAGE.batchText);
      IMEI_PAGE.batchResults = [];
      if (!values.length || values.length > 500) {
        IMEI_PAGE.batchError = values.length ? "单次最多查询 500 个 IMEI，请分批查询。" : "请至少输入一个 IMEI。";
        draw();
        return;
      }
      IMEI_PAGE.batchLoading = true;
      IMEI_PAGE.batchResults = [];
      draw();
      try {
        const batch = await api("/api/imei/batch-lookup", { imeis: values });
        IMEI_PAGE.batchResults = batch.results || [];
      } catch (x) {
        IMEI_PAGE.batchError = x.message;
      } finally {
        IMEI_PAGE.batchLoading = false;
        draw();
      }
      return;
    }
    if (e.target?.id !== "imei-manual-form") return;
    e.preventDefault();
    if (IMEI_PAGE.manualLoading) return;
    IMEI_PAGE.manualImei = String($("#imei-manual-value")?.value || "").trim();
    IMEI_PAGE.manualLookup = null;
    IMEI_PAGE.manualError = "";
    if (!/^\d{15}$/.test(IMEI_PAGE.manualImei)) {
      IMEI_PAGE.manualError = "请输入 15 位数字 IMEI。";
      draw();
      return;
    }
    IMEI_PAGE.manualLoading = true;
    draw();
    try {
      IMEI_PAGE.manualLookup = await api("/api/imei/lookup?imei=" + encodeURIComponent(IMEI_PAGE.manualImei));
    } catch (x) {
      IMEI_PAGE.manualError = x.message;
    } finally {
      IMEI_PAGE.manualLoading = false;
      draw();
    }
  };

  draw();
  refreshSaved();
  reload().catch(x => {
    if (x.status !== 401) {
      IMEI_PAGE.data = { devices: [], warning: x.message };
      draw();
    }
  });
}
// ---------------------------------------------------------------- 页面：系统设置
async function pageSettings(el) {
  el.innerHTML = head('系统设置', '发送模式和模拟参数') + loading();
  let s;
  try { s = S.settings = await api('/api/settings'); } catch (x) { if (x.status !== 401) el.innerHTML = head('系统设置', '') + errorBox(x.message); return; }
  const field = (k, label, unit, hint, step = '0.1') => `<div><label for="${k}">${label}</label><div class="unit"><input class="num-input num" type="number" id="${k}" step="${step}" value="${s[k]}"><span>${unit}</span></div>${hint ? `<div class="hint">${hint}</div>` : ''}</div>`;
  el.innerHTML = head('系统设置', '发送模式和模拟参数')
    + `<div class="card"><div class="card-title">发送模式</div><div class="mode-cards">
        <label class="mcard on"><input type="radio" name="sm" checked><div><b>演示模式（模拟数据）</b><p>号码是 VoCat 里的真实号码，收发过程全部模拟，不会发出任何短信，也不受限流影响。</p></div></label>
        <label class="mcard locked" title="本期锁定为演示模式"><input type="radio" name="sm" disabled><div><b>${icon('lock')}真实发送</b><p>本期锁定为演示模式，真实发送暂未开放。</p></div></label></div></div>
      <div class="card"><div class="card-title">模拟参数<span class="muted">只影响之后新开始的测试</span></div>
        <form id="sf" class="form-grid">
          ${field('fail_rate', '发送失败比例', '%', '模拟「提交失败」的比例，0～50')}
          ${field('undelivered_rate', '未到达比例', '%', '发出去了但对方没收到的比例，0～50')}
          ${field('latency_min', '到达用时 · 最短', '秒', '')}
          ${field('latency_max', '到达用时 · 最长', '秒', '之前真实测试平均约 1.9 秒')}
          <div style="grid-column:1/-1"><button class="btn primary">保存</button> <button type="button" class="btn" id="reset">恢复默认</button></div>
        </form></div>`;
  $('#reset').onclick = () => { Object.entries({ fail_rate: 1, undelivered_rate: 2, latency_min: 1, latency_max: 5 }).forEach(([k, v]) => { $('#' + k).value = v; }); };
  $('#sf').onsubmit = async e => {
    e.preventDefault();
    const body = { send_mode: 'demo' };
    ['fail_rate', 'undelivered_rate', 'latency_min', 'latency_max'].forEach(k => { body[k] = parseFloat($('#' + k).value); });
    try { S.settings = await api('/api/settings', body); toast('已保存'); } catch (x) { toast(x.message); }
  };
}

// ---------------------------------------------------------------- 路由
async function route() {
  if (!S.me) return;
  stopPoll();
  const [, page = 'overview', arg] = (location.hash.replace(/^#\/?/, '') || 'overview').match(/^([a-z-]+)(?:\/(.+))?/) || [];
  const key = NAV.some(n => n[0] === page) ? page : 'overview';
  const el = shell(key);
  el.onclick = null;
  el.onsubmit = null;
  window.scrollTo(0, 0);
  if (key === 'overview') return pageOverview(el);
  if (key === 'run') return pageRun(el);
  if (key === 'imei') return pageImei(el);
  if (key === 'records') return arg ? pageRecordDetail(el, arg) : pageRecords(el);
  if (key === 'numbers') return pageNumbers(el);
  if (key === 'settings') return pageSettings(el);
}
async function boot() {
  if (!location.hash) location.hash = '#/overview';
  loadNumbers().catch(() => {});
  route();
}
window.addEventListener('hashchange', route);
(async () => {
  S.meta = await fetch('/api/meta').then(r => r.json()).catch(() => ({}));
  try { S.me = await api('/api/me'); S.offline = !!S.me.offline; } catch { return; }
  boot();
})();

