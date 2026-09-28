/**
 * API 模块：封装所有后端请求
 */

class ApiClient {
  constructor(baseUrl = '') {
    this.baseUrl = baseUrl;
    this.retryAttempts = 3;
    this.retryDelay = 1000;
  }

  /**
   * 带重试的 fetch 封装
   */
  async fetchWithRetry(url, options = {}, attempt = 1) {
    try {
      const resp = await fetch(this.baseUrl + url, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
      });
      
      const data = await resp.json();
      
      if (!resp.ok) {
        throw new Error(data.error || `HTTP ${resp.status}`);
      }
      
      return data;
    } catch (err) {
      if (attempt < this.retryAttempts) {
        await this.sleep(this.retryDelay * attempt);
        return this.fetchWithRetry(url, options, attempt + 1);
      }
      throw err;
    }
  }

  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  // 覆盖情况
  async getCoverage() {
    return this.fetchWithRetry('/api/mq/coverage');
  }

  // MQ 测试
  async startMqRun(includeT43) {
    return this.fetchWithRetry('/api/mq/run', {
      method: 'POST',
      body: JSON.stringify({ include_t43: includeT43 }),
    });
  }

  async startMqRepeat(n, intervalS) {
    return this.fetchWithRetry('/api/mq/repeat', {
      method: 'POST',
      body: JSON.stringify({ n, interval_s: intervalS, include_t43: false }),
    });
  }

  async getMqStatus() {
    return this.fetchWithRetry('/api/mq/status');
  }

  // 号池测试
  async getPool() {
    return this.fetchWithRetry('/api/pool');
  }

  async runPoolTest(deviceIds) {
    return this.fetchWithRetry('/api/run', {
      method: 'POST',
      body: JSON.stringify({ device_ids: deviceIds }),
    });
  }

  // 导出报告
  getReportUrl() {
    return this.baseUrl + '/api/mq/report.md';
  }
}

export const api = new ApiClient();
