'use strict';

import { api } from './api.js';
import { 
  el, 
  toast, 
  setLoading, 
  showError, 
  vClass, 
  V_LABEL, 
  formatLog, 
  onVisibilityChange 
} from './ui.js';
import { config } from './config.js';

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// ========== 全局状态 ==========
let coverage = null;
let pool = { devices: [] };
let mqPolling = null;
let isPageVisible = true;

// ========== 页面可见性管理 ==========
onVisibilityChange((visible) => {
  isPageVisible = visible;
  if (config.polling.pauseWhenHidden && !visible && mqPolling) {
    // 页面隐藏时暂停轮询
    console.log('Page hidden, pausing MQ polling');
  }
});

// ========== Tab 切换 ==========
function showTab(name) {
  if (!document.getElementById('tab-' + name)) name = 'overview';
  
  $$('.tab').forEach((b) => {
    b.classList.toggle('active', b.dataset.tab === name);
    b.setAttribute('aria-selected', b.dataset.tab === name);
  });
  
  $$('.tab-page').forEach((p) => {
    p.hidden = p.id !== 'tab-' + name;
    p.setAttribute('aria-hidden', p.id !== 'tab-' + name);
  });
}

$$('.tab').forEach((btn) => {
  btn.addEventListener('click', () => {
    history.replaceState(null, '', '#' + btn.dataset.tab);
    showTab(btn.dataset.tab);
  });
});

showTab(location.hash.slice(1));

// ========== 覆盖情况 ==========
async function loadCoverage() {
  try {
    setLoading('#cov-meta', true, '正在读取覆盖情况...');
    
    coverage = await api.getCoverage();
    renderCoverage();
    
    toast.success('覆盖情况加载成功');
  } catch (err) {
    showError('#cov-meta', '读取覆盖情况失败：' + err.message);
    toast.error('读取覆盖情况失败：' + err.message);
  }
}

function renderCoverage() {
  const c = coverage;
  const m = c.meta || {};
  
  // 渲染元信息
  $('#cov-meta').textContent = c.run_id
    ? `最近 MQ 批次 ${c.run_id}（${c.started} – ${c.finished}）· ${m.broker || ''} · client_id ${m.client_id || ''} · 节点 ${m.node || ''}`
    : '尚未运行 MQ 第一层测试；以下全部为未测。';
  
  // 渲染计数芯片
  const chips = $('#cov-counts');
  chips.innerHTML = '';
  for (const [k, cls] of [['通过', 'pass'], ['失败', 'fail'], ['未测', 'none']]) {
    chips.append(el('span', { className: 'chip ' + cls }, `${k} ${c.counts[k]}`));
  }
  chips.append(el('span', { className: 'chip' }, '共 68 项'));

  // 渲染矩阵
  renderMatrix();
  
  // 渲染明细表
  renderDetail();
  
  // 渲染其他层级列表
  $$('.layer-list').forEach(renderLayerList);
}

function renderMatrix() {
  const mb = $('#matrix').querySelector('tbody');
  mb.innerHTML = '';
  
  const createCell = (entries) => {
    const td = el('td');
    for (const e of entries) {
      const code = el('code', { 
        className: 'id ' + vClass(e.verdict),
        title: `${e.id}${e.t ? ' · ' + e.t : ''} · ${e.verdict}`
      }, e.id.slice(0, 8) + (e.t ? ' ' + e.t : ''));
      
      td.append(code, ' ');
    }
    return td;
  };
  
  for (const r of coverage.matrix) {
    mb.append(el('tr', {},
      el('td', {}, r.action),
      createCell(r.success),
      createCell(r.reject),
      createCell(r.boundary)
    ));
  }
  
  // 矩阵外项目
  $('#extras').textContent = coverage.extras.length
    ? '矩阵外：' + coverage.extras.map((e) => `${e.t} ${e.action} ${e.id.slice(0, 8)} ${e.verdict}`).join('；')
    : '';
}

function renderDetail() {
  const layer = $('#f-layer').value;
  const verdict = $('#f-verdict').value;
  const body = $('#detail').querySelector('tbody');
  body.innerHTML = '';
  
  for (const r of coverage.rows) {
    if (layer && r.layer !== layer) continue;
    if (verdict && !r.verdict.startsWith(verdict)) continue;
    
    const taskIds = r.task_ids.map((id) => 
      el('code', { className: 'id', title: id }, id.slice(0, 8))
    );
    
    body.append(el('tr', {},
      el('td', { className: 'nowrap', title: r.section || '' }, r.id),
      el('td', { className: 'meta nowrap' }, r.layer),
      el('td', { title: '判据：' + r.criterion }, r.title),
      el('td', {}, el('span', { className: 'badge ' + vClass(r.verdict) }, r.verdict)),
      el('td', {}, ...taskIds),
      el('td', { className: 'meta nowrap' }, r.time || ''),
      el('td', { className: 'meta' }, r.summary || r.reason || '')
    ));
  }
}

function renderLayerList(table) {
  const layers = table.dataset.layer.split(',');
  const withLayer = table.querySelectorAll('th').length === 5;
  const body = table.querySelector('tbody');
  body.innerHTML = '';
  
  for (const r of coverage.rows.filter((x) => layers.includes(x.layer))) {
    const tds = [el('td', { className: 'nowrap' }, r.id)];
    if (withLayer) tds.push(el('td', { className: 'meta nowrap' }, r.layer));
    tds.push(
      el('td', { title: '判据：' + r.criterion }, r.title),
      el('td', {}, el('span', { className: 'badge ' + vClass(r.verdict) }, r.verdict)),
      el('td', { className: 'meta' }, r.summary || r.reason || '')
    );
    body.append(el('tr', {}, ...tds));
  }
}

$('#f-layer').addEventListener('change', renderDetail);
$('#f-verdict').addEventListener('change', renderDetail);

// ========== MQ 第一层测试 ==========
class MqPoller {
  constructor() {
    this.timerId = null;
    this.interval = config.polling.interval;
    this.isRunning = false;
  }

  async start(isRepeat = false) {
    $('#mq-run').disabled = true;
    $('#mq-repeat').disabled = true;
    
    try {
      let data;
      if (isRepeat) {
        const n = Number($('#rep-n').value);
        const intervalS = Number($('#rep-interval').value);
        data = await api.startMqRepeat(n, intervalS);
      } else {
        const includeT43 = $('#mq-t43').checked;
        data = await api.startMqRun(includeT43);
      }
      
      toast.success('MQ 测试已启动');
      this.poll();
    } catch (err) {
      $('#mq-state').textContent = '无法开始：' + err.message;
      toast.error('无法开始：' + err.message);
      this.reset();
    }
  }

  async poll() {
    if (config.polling.pauseWhenHidden && !isPageVisible) {
      // 页面隐藏时延长轮询间隔
      this.timerId = setTimeout(() => this.poll(), config.polling.maxInterval);
      return;
    }

    try {
      const s = await api.getMqStatus();
      
      // 更新日志
      const log = $('#mq-log');
      log.hidden = s.log.length === 0;
      if (s.log.length > 0) {
        log.innerHTML = formatLog(s.log);
        log.scrollTop = log.scrollHeight;
      }
      
      // 更新复现结果
      if (s.repeat) {
        renderRepeat(s.repeat);
      }
      
      if (s.running) {
        this.isRunning = true;
        $('#mq-run').disabled = true;
        $('#mq-repeat').disabled = true;
        
        const done = s.log.filter((l) => /\[(pass|fail|untested|partial|insufficient|info)\]/.test(l)).length;
        $('#mq-state').textContent = `运行中… 已完成 ${done} 条判定`;
        
        this.timerId = setTimeout(() => this.poll(), this.interval);
      } else {
        this.isRunning = false;
        this.reset();
        
        if (s.error) {
          $('#mq-state').textContent = '运行中止：' + s.error;
          toast.error('运行中止：' + s.error);
        } else if (s.repeat) {
          $('#mq-state').textContent = `复现完成：${s.repeat.repeat_id}`;
          toast.success('复现完成');
        } else if (s.run_id) {
          $('#mq-state').textContent = `完成：批次 ${s.run_id}，覆盖总览已更新。`;
          toast.success('MQ 测试完成');
          loadCoverage();
        } else {
          $('#mq-state').textContent = '';
        }
      }
    } catch (err) {
      console.error('Poll error:', err);
      // 使用指数退避
      this.interval = Math.min(this.interval * config.polling.backoffMultiplier, config.polling.maxInterval);
      this.timerId = setTimeout(() => this.poll(), this.interval);
    }
  }

  reset() {
    clearTimeout(this.timerId);
    this.timerId = null;
    this.interval = config.polling.interval;
    $('#mq-run').disabled = false;
    $('#mq-repeat').disabled = false;
  }

  stop() {
    this.reset();
    this.isRunning = false;
  }
}

mqPolling = new MqPoller();

function renderRepeat(r) {
  $('#rep-result').hidden = false;
  
  $('#rep-summary').textContent = 
    `${r.repeat_id}：${r.runs} 次；代码${r.same_code ? '同一版本' : '版本不一致'}；` +
    `运行指纹${r.run_fingerprint_consistent ? '一致' : '不一致'}；环境${r.environment_consistent ? '一致' : '有变化'}；` +
    `deterministic 稳定 ${r.deterministic_stable}/${r.deterministic_total}；翻转：${r.flipped.join(', ') || '无'}。证据：${r.evidence_dir}`;
  
  const body = $('#rep-table').querySelector('tbody');
  body.innerHTML = '';
  
  for (const c of r.cases) {
    const counts = {};
    for (const v of c.verdicts) {
      const label = V_LABEL[v] || v;
      counts[label] = (counts[label] || 0) + 1;
    }
    
    body.append(el('tr', {},
      el('td', { className: 'nowrap' }, c.id),
      el('td', { className: 'meta' }, c.stability),
      el('td', {}, Object.entries(counts).map(([k, n]) => `${k}×${n}`).join('、')),
      el('td', {}, el('span', { className: 'badge ' + (c.stable ? 'pass' : 'fail') }, c.stable ? '稳定' : '翻转')),
      el('td', { className: 'meta' }, c.changed_fields.join(', ') || '—')
    ));
  }
}

$('#mq-run').addEventListener('click', () => mqPolling.start(false));
$('#mq-repeat').addEventListener('click', () => mqPolling.start(true));

// ========== 号池测试 ==========
async function loadPool() {
  try {
    $('#meta').textContent = '正在读取号池…';
    $('#devices').innerHTML = '';
    
    pool = await api.getPool();
    renderDevices();
    
    const lines = pool.devices.reduce((n, d) => n + d.lines.length, 0);
    $('#meta').textContent = `VoCat: ${pool.base} · 设备 ${pool.devices.length} · 线路 ${lines}`;
    
    toast.success('号池加载成功');
  } catch (err) {
    $('#meta').textContent = '读取号池失败：' + err.message;
    toast.error('读取号池失败：' + err.message);
  }
}

function renderDevices() {
  const box = $('#devices');
  box.innerHTML = '';
  
  for (const dev of pool.devices) {
    const check = el('input', { 
      type: 'checkbox', 
      value: dev.id, 
      checked: true, 
      className: 'dev-cb',
      setAttribute: (name, value) => check.setAttribute(name, value)
    });
    check.setAttribute('aria-label', `设备 ${dev.id}`);
    check.addEventListener('change', updateRunState);
    
    const lines = el('ul');
    for (const ln of dev.lines) {
      lines.append(el('li', {}, `${ln.number || '(未命名)'} · ${ln.phase || '?'}`));
    }
    
    const dot = el('span', { 
      className: 'dot ' + (dev.healthy ? 'ok' : 'bad'),
      setAttribute: (name, value) => dot.setAttribute(name, value)
    });
    dot.setAttribute('aria-label', dev.healthy ? '健康' : '异常');
    
    box.append(el('label', { className: 'device' },
      check,
      el('div', {},
        el('div', { className: 'name' }, dot, `设备 ${dev.id} · ${dev.model || ''}`),
        el('div', { className: 'meta' }, `${dev.lifecycle || ''} · ${dev.lines.length} 线`),
        lines
      )
    ));
  }
  
  updateRunState();
}

function selectedIds() {
  return [...$$('.dev-cb')].filter((c) => c.checked).map((c) => c.value);
}

function updateRunState() {
  $('#run').disabled = selectedIds().length === 0;
}

async function runPoolTest() {
  const ids = selectedIds();
  if (!ids.length) return;
  
  $('#run').disabled = true;
  $('#run-status').textContent = `正在读取 ${ids.length} 台设备的 REST 基线…`;
  
  try {
    const data = await api.runPoolTest(ids);
    renderResult(data);
    $('#run-status').textContent = '完成。';
    toast.success('号池测试完成');
  } catch (err) {
    $('#run-status').textContent = '测试失败：' + err.message;
    toast.error('测试失败：' + err.message);
  } finally {
    updateRunState();
  }
}

function renderResult(r) {
  $('#result-panel').hidden = false;
  $('#run-id').textContent = 'run ' + r.run_id;
  
  const v = $('#verdict');
  v.className = 'verdict ' + (r.overall_pass ? 'pass' : 'fail');
  v.textContent = (r.overall_pass ? '✓ 全部通过' : '✗ 存在失败步骤') +
    ` · 号池就绪 ${r.pool_ready}/${r.pool_total}`;

  // 渲染步骤表
  const steps = $('#steps').querySelector('tbody');
  steps.innerHTML = '';
  for (const s of r.steps) {
    steps.append(el('tr', {},
      el('td', {}, s.step),
      el('td', {}, el('code', {}, s.endpoint)),
      el('td', {}, String(s.http)),
      el('td', {}, el('span', { className: 'badge ' + (s.ok ? 'pass' : 'fail') }, s.ok ? 'PASS' : 'FAIL')),
      el('td', { className: 'meta' }, s.note || '')
    ));
  }

  // 渲染号池明细
  const body = $('#pool').querySelector('tbody');
  body.innerHTML = '';
  
  const createCell = (v) => el('td', { className: v ? 'cell-ok' : 'cell-no' }, v ? '✓' : '✗');
  
  for (const p of r.pool) {
    body.append(el('tr', {},
      el('td', {}, p.number || '(未命名)'),
      el('td', {}, String(p.device)),
      el('td', { className: 'meta' }, p.phase || ''),
      createCell(p.sim_ready),
      createCell(p.ims_ready),
      createCell(p.tunnel_ready),
      createCell(p.sms_ready),
      el('td', {}, el('span', { className: 'badge ' + (p.ready ? 'pass' : 'fail') }, p.ready ? '就绪' : '未就绪'))
    ));
  }
  
  $('#pool-count').textContent = `(${r.pool_ready}/${r.pool_total})`;
  $('#evidence').textContent = '证据目录：' + r.evidence_dir;
}

$('#run').addEventListener('click', runPoolTest);
$('#reload').addEventListener('click', loadPool);

$('#selectAll').addEventListener('click', () => {
  $$('.dev-cb').forEach((c) => (c.checked = true));
  updateRunState();
});

$('#selectNone').addEventListener('click', () => {
  $$('.dev-cb').forEach((c) => (c.checked = false));
  updateRunState();
});

// ========== 初始化 ==========
loadCoverage();
mqPolling.poll(); // 初始检查状态
loadPool();
