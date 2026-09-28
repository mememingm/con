/**
 * UI 渲染模块
 */

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

/**
 * 创建 DOM 元素的辅助函数
 */
export function el(tag, props = {}, ...kids) {
  const node = Object.assign(document.createElement(tag), props);
  for (const kid of kids) {
    if (kid != null) {
      node.append(kid);
    }
  }
  return node;
}

/**
 * 显示/隐藏加载指示器
 */
export function setLoading(selector, isLoading, text = '加载中...') {
  const element = $(selector);
  if (!element) return;
  
  if (isLoading) {
    element.innerHTML = `<span class="loading-indicator">${text}</span>`;
  }
}

/**
 * 显示错误消息
 */
export function showError(selector, message) {
  const element = $(selector);
  if (!element) return;
  
  element.innerHTML = `<span class="error-message">⚠️ ${message}</span>`;
}

/**
 * Toast 通知
 */
class Toast {
  constructor() {
    this.container = null;
    this.init();
  }

  init() {
    if (this.container) return;
    
    this.container = el('div', { 
      className: 'toast-container',
      setAttribute: (name, value) => this.container.setAttribute(name, value)
    });
    this.container.setAttribute('aria-live', 'polite');
    this.container.setAttribute('aria-atomic', 'true');
    document.body.append(this.container);
  }

  show(message, type = 'info', duration = 3000) {
    const toast = el('div', { 
      className: `toast toast-${type}`,
      textContent: message 
    });
    
    this.container.append(toast);
    
    // 触发动画
    setTimeout(() => toast.classList.add('show'), 10);
    
    // 自动移除
    if (duration > 0) {
      setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
      }, duration);
    }
    
    return toast;
  }

  success(message, duration) {
    return this.show(message, 'success', duration);
  }

  error(message, duration) {
    return this.show(message, 'error', duration);
  }

  info(message, duration) {
    return this.show(message, 'info', duration);
  }
}

export const toast = new Toast();

/**
 * 判定类型映射
 */
export const VERDICT_CLASS = { '通过': 'pass', '失败': 'fail', '未测': 'none' };
export const V_LABEL = { 
  pass: '通过', 
  fail: '失败', 
  untested: '未测', 
  insufficient: '证据不足', 
  partial: '未测（部分观察）' 
};

export function vClass(verdict) {
  return VERDICT_CLASS[verdict] || 'none';
}

/**
 * 格式化日志输出（语法高亮）
 */
export function formatLog(logLines) {
  return logLines.map(line => {
    // 高亮不同的判定类型
    line = line.replace(/\[(pass)\]/g, '<span class="log-pass">[$1]</span>');
    line = line.replace(/\[(fail)\]/g, '<span class="log-fail">[$1]</span>');
    line = line.replace(/\[(untested|insufficient|partial)\]/g, '<span class="log-warn">[$1]</span>');
    line = line.replace(/\[(info)\]/g, '<span class="log-info">[$1]</span>');
    
    // 高亮任务 ID
    line = line.replace(/\b([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})\b/g, 
      '<span class="log-id">$1</span>');
    
    return line;
  }).join('\n');
}

/**
 * 页面可见性检测
 */
export function onVisibilityChange(callback) {
  document.addEventListener('visibilitychange', () => {
    callback(!document.hidden);
  });
}

/**
 * 节流函数
 */
export function throttle(func, delay) {
  let lastCall = 0;
  return function (...args) {
    const now = Date.now();
    if (now - lastCall >= delay) {
      lastCall = now;
      func.apply(this, args);
    }
  };
}

/**
 * 防抖函数
 */
export function debounce(func, delay) {
  let timeout;
  return function (...args) {
    clearTimeout(timeout);
    timeout = setTimeout(() => func.apply(this, args), delay);
  };
}
