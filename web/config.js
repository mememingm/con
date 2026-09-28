/**
 * 配置文件
 */

export const config = {
  // 轮询配置
  polling: {
    interval: 1500,           // 轮询间隔（毫秒）
    maxInterval: 10000,       // 最大轮询间隔（用于指数退避）
    backoffMultiplier: 1.5,   // 退避倍数
    pauseWhenHidden: true,    // 页面隐藏时暂停轮询
  },

  // API 重试配置
  api: {
    retryAttempts: 3,
    retryDelay: 1000,
  },

  // Toast 配置
  toast: {
    duration: 3000,
    maxVisible: 3,
  },

  // 表格分页配置
  table: {
    pageSize: 50,
    virtualScrollThreshold: 100, // 超过此行数时启用虚拟滚动
  },

  // WebSocket 配置（预留）
  websocket: {
    enabled: false,
    url: 'ws://localhost:8768/ws',
    reconnectDelay: 3000,
    maxReconnectAttempts: 5,
  },
};
