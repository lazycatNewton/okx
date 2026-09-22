# frontend

OKX 行情连接服务前端（REQ-001 核心闭环阶段）。桌面 Web，React + TypeScript + Vite。

## 当前已实现范围

- 登录页（用户名密码，走后端会话 Cookie）。
- 产品选择器（SPOT/SWAP 切换、`instId` 搜索、仅 `live` 可选）。
- Tab 栏：每个已选产品一个 Tab，选择/取消选择即时创建/关闭。
- 产品面板：M02 K 线图（`1s`/`5m`/`15m`/`1D` 周期切换，REST 轮询）、M01 行情卡片、M05 五档盘口表格
  （M01/M05 走独立的 WebSocket 数据层，`snapshot`→`update` 语义）。
- 独立实时数据层 `marketDataStore.ts`：封装 `/ws/app` 建连、指数退避重连、
  `activate-product`/`deactivate-product` 状态维护；渲染组件只读取规范化状态，不直连 WebSocket。

尚未实现（下一步）：M10-M16/M22/M23/M25 面板、全局侧边栏、K 线通过 WebSocket 实时更新
（目前 M02 走 REST 轮询，未接入 `/ws/app` 的 K 线推送）。

## 本地开发

```bash
npm install
npm run dev       # http://localhost:5173，代理 /api 与 /ws 到 http://127.0.0.1:8000
npm run build     # tsc -b && vite build
npm run lint      # oxlint
npm test          # 数据合并、展示规则等单元测试
npm run test:charts # 独立 Vite + Chromium，验证 K 线切换、时间排序、实时合并与可见范围
```

首次运行浏览器测试前安装 Chromium：`npx playwright install chromium`。浏览器测试使用固定模拟行情，拦截全部 API 请求，不需要登录，也不连接后端或 OKX；会自动启动和关闭独立的本机测试服务器。

`vite.config.ts` 中的开发代理假定后端运行在 `127.0.0.1:8000`；生产部署时改为真实后端地址或反向代理配置。
