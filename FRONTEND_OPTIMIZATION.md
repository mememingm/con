# 前端优化说明

## 本次优化内容

### 1. 代码重构与模块化

- **模块拆分**：将原来的单一 `app.js` 拆分为多个模块：
  - `api.js`：API 请求封装，包含重试机制
  - `ui.js`：UI 渲染辅助函数和工具
  - `config.js`：配置集中管理
  - `app.js`：主应用逻辑

- **ES6 模块**：使用 ES6 模块化语法，提高代码可维护性

### 2. API 请求优化

- **重试机制**：API 请求失败时自动重试（最多 3 次）
- **请求延迟**：失败重试时使用递增延迟
- **统一错误处理**：集中处理 HTTP 错误

```javascript
// 示例：带重试的 API 调用
async fetchWithRetry(url, options = {}, attempt = 1) {
  try {
    const resp = await fetch(url, options);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return await resp.json();
  } catch (err) {
    if (attempt < this.retryAttempts) {
      await this.sleep(this.retryDelay * attempt);
      return this.fetchWithRetry(url, options, attempt + 1);
    }
    throw err;
  }
}
```

### 3. 用户体验提升

- **Toast 通知**：操作成功/失败时显示友好的通知消息
- **加载指示器**：数据加载时显示动画提示
- **日志语法高亮**：日志中的关键词（pass/fail/ID）高亮显示
- **页面可见性检测**：页面隐藏时减少轮询频率，节省资源

### 4. 轮询优化

- **智能轮询**：
  - 页面隐藏时自动延长轮询间隔
  - 请求失败时使用指数退避策略
  - 可配置的轮询参数

```javascript
// 配置示例
polling: {
  interval: 1500,           // 正常轮询间隔
  maxInterval: 10000,       // 最大间隔（退避上限）
  backoffMultiplier: 1.5,   // 退避倍数
  pauseWhenHidden: true,    // 页面隐藏时暂停
}
```

### 5. 可访问性改进

- **ARIA 属性**：为交互元素添加 `aria-label`、`aria-selected`、`aria-hidden`
- **焦点可见性**：明显的焦点指示器（`:focus-visible`）
- **语义化 HTML**：保持原有的良好 HTML 结构

### 6. 样式增强

新增样式：
- Toast 通知动画
- 加载指示器动画
- 日志语法高亮
- 更好的焦点样式
- 响应式改进（移动端 Toast）

### 7. 性能优化

- **选择器缓存**：减少重复的 DOM 查询
- **事件委托**：适当使用事件委托减少监听器数量
- **条件渲染**：避免不必要的 DOM 更新

## 文件结构

```
web/
├── index.html       # 主页面（更新为模块化引入）
├── styles.css       # 样式文件（新增样式）
├── app.js           # 主应用逻辑（重构）
├── api.js           # API 请求模块（新增）
├── ui.js            # UI 工具模块（新增）
└── config.js        # 配置模块（新增）
```

## 向后兼容性

- 所有 API 接口保持不变
- HTML 结构保持不变
- CSS 类名保持不变
- 功能完全兼容原有实现

## 未来可扩展功能

代码已预留扩展点：

1. **WebSocket 支持**：`config.js` 中已有 WebSocket 配置
2. **表格分页**：配置中预留分页参数
3. **虚拟滚动**：大数据量表格优化预留
4. **更多 Toast 类型**：可轻松扩展通知类型

## 浏览器兼容性

- 现代浏览器（Chrome/Firefox/Safari/Edge 最新版本）
- ES6 模块支持
- Fetch API 支持
- 不支持 IE11（需要 polyfill）

## 测试建议

1. 测试页面加载和 Tab 切换
2. 测试 MQ 测试启动和轮询
3. 测试号池加载和设备选择
4. 测试错误处理（断网场景）
5. 测试页面隐藏/显示时的轮询行为
6. 测试 Toast 通知显示

## 配置说明

所有配置集中在 `config.js`，可根据需要调整：

```javascript
export const config = {
  polling: {
    interval: 1500,           // 轮询间隔（毫秒）
    maxInterval: 10000,       // 最大轮询间隔
    backoffMultiplier: 1.5,   // 退避倍数
    pauseWhenHidden: true,    // 页面隐藏时暂停
  },
  api: {
    retryAttempts: 3,         // API 重试次数
    retryDelay: 1000,         // 重试延迟（毫秒）
  },
  toast: {
    duration: 3000,           // Toast 显示时长（毫秒）
    maxVisible: 3,            // 最多同时显示数量
  },
};
```

## 优化效果

- ✅ 代码可维护性提升：模块化、清晰的职责分离
- ✅ 用户体验改善：Toast 通知、加载提示、语法高亮
- ✅ 性能优化：智能轮询、页面可见性检测
- ✅ 健壮性增强：API 重试、错误处理
- ✅ 可访问性改进：ARIA 属性、焦点样式
- ✅ 易于扩展：配置化、预留扩展点
