# HANDOFF — OKX 需求完善交接

更新日期：2026-09-22 · 当前对应需求版本：0.47

## 1. 接手时先读

当前工作是与用户逐步完善 [okx-requirements.md](okx-requirements.md)，为后续对话实现提供明确规格。现在只做需求工作，尚未编写或运行行情服务，没有真实 WS 连接、账户权限验证或交易执行。

用户最新明确的文档分工：

- **okx-requirements.md**：结果性质的需求文档，保存已确认要实现的功能、参数、接口关联及确定的实现／验收要求。
- **HANDOFF.md**：需求完善过程的交接文档，保存当前进度、待定事项、证据缺口、候选方案和下一步。它不是另一份需求规格。

不要把助手的建议、尚未选择的接口或待讨论的设计提升为确定需求。每次相关讨论后同步更新交接；用户确认的结果同时更新需求正文。用户后来明确的指令优先于两份文档。

本轮再次确认：在后续完善 `okx-requirements.md` 的每次有效工作结束前，均须同步本文件的恢复点、待定事项、下一步和变更记录；这不代表后台自动更新，需由后续实际工作触发。

## 2. 当前进度与恢复点

### 0.68 移除 M11／补齐遗漏的 M16 迁移／S04 展示位置上移（2026-09-22）

用户先指令「去掉M16的前后端相关功能」（上一轮会话完成，但当时遗漏更新本文件与需求正文，且没有配套写删表迁移——`m16_risk_events` 表一直是孤儿表），本轮开场先补齐这两处遗漏；随后用户指令「去掉M11的前后端实现。将S04的展示位置上移，使与M01在同一行」。需求正文更新为 **0.47**，「已移除的能力」小节新增 M11／M16 两行。

**补齐 M16 遗留**：新迁移 `75fd54ac1bfe` drop `m16_risk_events` 表（`downgrade()` 可重建表结构，不恢复数据）；`okx-requirements.md` 多处仍写 M16 为在用能力，本轮一并改为「已移除」。

**M11（标记价格 K 线）移除**：

- 后端：`market_collector.py` 删除 `MARK_BARS`／`MARK_SOURCE_BARS`、`mark-price-candle{bar}` 订阅与消息分发分支；`parse_candle_row()` 不再按 `kind` 分列（M11 是 6 列、M02 是 9 列，现在只剩 M02 一种格式，签名简化为 `parse_candle_row(row)`）。`candle_backfill.py` 删除标记价格分支，`_backfill_one` 固定走 `get_history_candles`。`okx_client/rest.py` 删除 `get_history_mark_price_candles`。`realtime/hub.py` 的 `CHANNEL_KEYS` 删除 `candle:mark:*` 系列。`market_router.py` 的 `GET .../candles` 的 `kind` 参数收窄为只接受 `trade`。`db/models.py` 的 `CandleKind` 收窄为只剩 `TRADE`。新迁移 `ad4f1b5392f5`：先删 `candles.kind='MARK'` 的行，再把该列的 MySQL ENUM 从 `('TRADE','MARK')` 收窄为 `('TRADE')`（顺序同 0.66 的经验，避免残留行在严格模式下让 ALTER 失败）。
- 前端：`CandleChart.tsx` 删除 `MarkPriceChart` 与 `MARK_BARS`（`GenericCandleChart` 内部结构保留，现在只有 `CandleChart` 一个调用方）；`ProductPanel.tsx` 不再渲染标记价格图表；`chanOverlay.ts` 的 `ChanKind` 收窄为 `'trade'`；`useCandleData.ts`／`api.ts` 的 `kind` 参数同步收窄为 `'trade'`。
- 测试：`test_candle_parser.py`／`test_candle_policy.py`／`test_candle_backfill.py`／`test_candle_adjust.py`／`test_realtime_hub.py` 删除或改写 MARK 相关用例；浏览器测试 `chart-fixture.jsx`／`candleChart.test.mjs` 的 `?kind=mark` 变体一并移除。

**S04 展示位置上移**：`M25Panel.tsx` 的 `S04Chart` 改为独立 `export`，自带周期选择器（不再共享 `M25Panel` 的 `period` 状态），包一层 `panel numeric-card` 使其能和 `TickerCard` 等卡片一样放进 `product-panel-row`；`M25Panel` 本体只剩 S01／S05。`ProductPanel.tsx` 在 `product-panel-row` 内、`TickerCard` 之后插入 `<S04Chart instId={instId} />`（仅 `isSwap`）。

**顺带修复一个由 0.66 遗留的真实回归**：`npm test` 发现 `detailDisplay.test.ts` 断言 `detailLabel('bkPx')` 等 M16 字段标签，但 0.66/M16 removal 早把 `labels` 清空——测试实际是红的，说明那一轮移除后没有跑过前端单元测试。核实后发现 `detailLabel()`／`<DetailFields>` 组件此前**只有 `RiskEventsPanel.tsx` 一个调用方**，该组件已在 M16 移除时删除，`DetailFields.tsx` 因此完全孤儿；一并删除该组件，`detailDisplay.ts` 的 `labels`／`enums` 收窄为仍有直接调用方的 `instType`，测试改为只断言 `instType` 分支。

**验证**：后端 ruff／mypy／pytest **110 passed**（`alembic heads` 确认迁移链单一 head：`db01090c5c59→827106eec8f4→6060da89549d→a4c71e2f0b35→c93b5ad10e77→75fd54ac1bfe→ad4f1b5392f5`，未针对真实远程 MySQL 执行升级）；前端 `npm test` **22 passed**、`npm run test:charts`（Playwright 真实浏览器）**14 passed**、`tsc -b && vite build` 通过、`oxlint` 仅既有 `ProductSelector.tsx` 警告。**未做**：真实登录浏览器目视验证 S04 新位置的视觉效果与断点换行——本环境无法访问远程 MySQL／Redis／OKX 凭证，只验证了自动化测试与构建。

### 0.67 修复跨产品／周期的 K 线缺口、旧 OHLC 与显示精度（2026-09-22）

用户再次反馈蜡烛长度与实际数值不符、前后衔接有缺口，并明确产品／周期／成交价与标记价「都有」。本轮是既有需求的缺陷修复，没有新增能力或恢复已移除能力；需求版本仍为 **0.46**，第 4 节补录局部验证结果。

**证据与复现**（使用 diagnosing-bugs 流程先建立失败回归）：

- 本地 MySQL 只读审计发现当前四个股票永续（NVDA／SKHYNIX／SNDK／SPCX）最近 300 根 `5m` 各有 53 处时间断档，`1m` 各有 60 处、`15m` 各有 3 处，成交价与标记价均存在；样本内 OHLC 大小关系没有越界。不能把这些断档全部解释为正常市场跳空。
- 浏览器新增用例先失败：五位报价 `0.09277/0.09284/0.09271/0.09283` 的纵轴格式化结果全为 `0.09`；历史初次加载后，即使后端已补回中间 K 线与最终 OHLC，返回页面仍保留旧数据。像素测试排除了字段映射／蜡烛绘制比例本身错误：实体由开收差决定、影线由高低价决定。
- 后端新增用例先失败：`1H` 回填异常使顺序阶段循环退出，`5m` 等后续周期完全不执行；后台 wrapper 只记录异常，不重试。`aggregate_ny_day` 还会把缺纽约午夜的第一根小时开盘当成日开盘，并仅因已跨日而确认残缺日线。
- 附加浏览器用例先失败：将 UTC 时间平移成纽约墙上时间作为唯一键，秋季回拨时两个 01 点重合、去重丢失一小时 K 线。该问题是边界隐患，不是 9 月当前断档的原因。

**修复**：

- `candle_backfill.py`：各产品／类型／周期独立回填和失败重试，深历史与近期校对分开；近期校对失败不推进窗口，恢复后仍覆盖断线区间。所有 K 线回填请求共享进程内节流（每 0.12 秒放行一次，保守满足各 20 次／2 秒／IP 的限额），避免每个产品独立 sleep 形成并发突刺。`TaskGroup` 随产品移除／服务停止取消所有子任务；拒绝不前进的分页游标。校对间隔 30 秒是当前实现参数，不是新确认的可靠性指标。
- `market_collector.py`／`candle_cache.py`：REST 回填只接受已闭合行、只写历史，不再倒序逐根覆盖最新缓存／广播；数据库 upsert 与 Redis 原子更新均阻止闭合版本退回未闭合版本，缓存同时阻止较早时间替换最新时间。REST 的已闭合最终值仍能校正漏收终帧的历史 OHLC。
- `useCandleData.ts`：每 30 秒及页面重新可见／聚焦／网络恢复时重新读取本产品历史接口。REST 修正旧状态，但本次请求期间收到的 WS 仍优先；保留排序、闭合保护、取消旧请求和已有视窗锚点。浏览器从不直接访问 OKX。
- `candleData.ts`／`CandleChart.tsx`：按 OHLC 原始报价精度配置纵轴／十字光标价格；`time.ts` 将真实 UTC 秒作为图表键，用纽约格式化器渲染刻度和十字光标，避免 DST 重复键。S01／S05 图表同步接入相同格式化器，防止共享工具改变后退回 UTC 标签；没有改回固定 UTC−4 或 OKX 日线。
- `ny_day_candles.py`：验证午夜首根与连续小时序列，历史日必须覆盖到下一纽约午夜（23／24／25 小时）；仅全部源小时已确认且已跨日才确认日线。保留源 `confirm`，不写入缺日界或内部缺小时的残缺值，缓存不被晚到旧日线倒退。

**验证**：修复后再次只读查询真实数据库，上述四产品 × 两类图表 × `1m/5m/15m` 最新各 300 根、`1D` 各 80 根，时间缺口、OHLC 越界及已过期未闭合旧线均 **0**。这是运行中服务的数据状态复查，诊断脚本自身不写库、不读取账户表。后端 ruff／mypy／pytest **120 passed**；前端单元 **22 passed**、浏览器 **16 passed**（含十个蜡烛图类型／周期组合的像素高度、补数、视图保持、夏令时）、build 通过；lint 仅既有 ProductSelector 警告，后端仅既有 Nacos/Pydantic 弃用警告。

**接口依据**：okx-v5-api Skill **0.2.0**，核验日期 **2026-09-22**，站点 `okex`，已按 `sites.json` → `index/market.md` → `index.json` 核对方法／路径／支持／正文。相对路径：`docs/okex/zh/api/rest/market/historyCandles.md`、`historyMarkPriceCandles.md`，及 `docs/okex/zh/api/ws/public_channel/candles.md`、`markPriceCandle.md`。确认 M02 九列、M11 六列与 confirm 语义、分页上限 300／100、20 次／2 秒／IP；成交价保留 `adjust=forward`，标记价不加未支持的复权参数。

**边界与下一步**：本轮没有登录真实用户浏览器；浏览器回归使用隔离测试数据，真实数据核验来自只读数据库。已抽查窗口之外不作无缺口承诺，完整历史仍由回填任务尽力恢复。真实市场跳空和官方历史不可用保持原样，不拼接开收价、不制造 K 线。用户刷新前端加载新代码后可直接观察；如仍有具体异常，再用对应截图／时间段定位，而不是重新讨论已确定的时区或周期。

### 0.66 移除 M12／M14／M15／S09／S10／S11（2026-09-22）

用户指令：「去掉前后端关于 M12/M14/M15/S09/S10/S11 的实现」。这是**范围收缩**，不是缺陷修复；需求正文更新为 **0.46**，新增「已移除的能力」小节记录可追溯的移除清单。

**后端**：

- `collector/market_collector.py`：退订 `funding-rate`／`price-limit`／`estimated-price`，删除 `_store_funding_rate`／`_store_price_limit`／`_store_estimated_price` 三个落库方法与对应消息分发分支。
- `realtime/hub.py`：从 `CHANNEL_KEYS` 移除三个频道，浏览器激活产品时不再收到它们的 snapshot。
- `okx_client/rest.py`：删除 `get_margin_loan_ratio`（S09）、`get_funding_rate_history`（S10）、`get_premium_history`（S11）。
- `services/m25_stats.py`：删除 `backfill_dict_metric`（只服务 S10/S11 的 dict 行分页）、`_s09_row_to_payload`、`_resolve_ccy_set`、`ccy_from_uly`、`PERIODS_S09`、`S10_S11_POLL_SECONDS`、`_S09_5M_HISTORY_DAYS` 及三者的回填作业与轮询任务。**连带简化**：M25 不再需要由永续 `uly` 推导 `ccy`——那是 S09 独有的查询维度，现在全部指标都以永续 `instId` 查询，`start_m25_polling` 也因此不再需要先做一次数据库查询。
- `services/retention.py`：从 7 天滚动清理表移除三张表。
- `db/models.py`：删除 `FundingRate`／`PriceLimit`／`EstimatedPrice` 模型，`M25Metric` 收窄为 `S01/S04/S05`。
- 迁移 `c93b5ad10e77`：先删 `m25_stats` 中 S09／S10／S11 的行，再把 `metric` 的 MySQL ENUM 收窄为 `('S01','S04','S05')`（顺序不能反——残留行会让 ALTER 在严格模式下失败），最后 drop 三张表。`downgrade()` 重建表结构并放宽 ENUM，但不恢复数据（均可由 OKX 重新回填）。

**前端**：`types.ts` 删除 `FundingRateData`／`PriceLimitData`／`EstimatedPriceData` 与 `M25S09Period`；`marketDataStore.ts` 删除三个 channel 状态与分发分支；`SwapSnapshotCards.tsx` 删除三张卡片（只剩 M10／M13）；`ProductPanel.tsx` 不再传 `ccy`；`M25Panel.tsx` 删除 S09 图表、S09 周期选择器与 S10/S11 历史表格；`App.css` 清掉随之失效的 `.m25-history-*`／`.m25-subheading` 样式；`api.ts` 的 metric 联合类型收窄为 `'S01' | 'S04' | 'S05'`。

**测试**：删除只服务被移除能力的用例（`ccy_from_uly`、`_s09_row_to_payload`、`backfill_dict_metric` 分页）；原「S09 故障隔离」回归改写为 `test_backfill_m25_isolates_one_failing_product_from_others`——让 SPCX 的 S05 报错，断言 BTC 的 S01／S04／S05 与 SPCX 自身的 S01／S04 仍然落库，保住了 `return_exceptions=True` 这条真实事故的回归价值。`test_collector_swap_channels.py` 与 `test_realtime_hub.py` 改为**反向断言**：三个被移除的频道不得再出现在订阅集合与快照里。

**验证**：迁移已在真实本地 MySQL 执行——三张表已不存在，`m25_stats.metric` 实测为 `enum('S01','S04','S05')`，S09／S10／S11 共 21735 行已删除，S01／S04／S05 数据完好。全项目 ruff／mypy／pytest **110 passed**；前端 `npm test` 18 项、`tsc --noEmit`、`npm run lint`（仅既有 `ProductSelector.tsx` 警告）、`npm run build` 均通过。全仓 grep 确认实现侧已无残留引用，只剩两处“不得再出现”的回归断言。

**遗留**：本轮未登录真实浏览器目视确认面板（数据库与构建层已验证）。

### 0.65 全系统日线改为纽约自然日口径（2026-09-22）

用户指令：「矫正 S01 和 S05 的时间，该系统的所有时间都应该与 UTC-4，即纽约时间对齐」。需求正文更新为 **0.45**。

**诊断（已用本地 MySQL 真实数据核实）**：前端显示层没有问题（`frontend/src/time.ts` 已统一按 `America/New_York` 渲染，S01／S05 图表也走 `chartTimeInEt()`）。真正错位的是**数据本身的日线分桶口径**——`okx-v5-api` Skill 0.2.0 的 `longShortAccountRatioContract.md`、`openInestVolumeHistory.md`、`contractTakerVolume.md`、`historyCandles.md` 都写明 `period`／`bar` 的 `1D` 属于 **UTC+8 开盘价 K 线**，`1Dutc` 才是 UTC+0。库里实测印证：`m25_stats` 中 S01／S05 的 `1D` 行 `ts_ms` 全部落在 UTC `16:00`（例如 `1789488000000` = 2026-09-15 16:00 UTC），即**纽约时间中午 12:00**；`candles` 表 `bar='1D'` 同样是 UTC 16:00 口径。也就是说问题不止 S01／S05，M02／M11 日线和 S04 是同一个偏差。

**用户拍板的口径**（OKX 不提供纽约口径的日线分桶，只有 UTC+8 的 `1D` 和 UTC+0 的 `1Dutc`）：后端按纽约自然日重采样，范围覆盖全系统所有 `1D`。

**实现**：

- 新增 `backend/src/okx_backend/services/ny_day.py`：纽约自然日分桶工具（`ny_day_start_ms`、`ny_day_start_days_ago`、`next_ny_day_start_ms`、`group_by_ny_day`、`decimal_sum`），固定用 `zoneinfo` 的 `America/New_York`，不使用写死的 UTC-4——纽约 00:00 在 EDT 是 UTC 04:00、EST 是 UTC 05:00，切换当天的自然日分别是 23 小时和 25 小时。派生源固定为官方 `1H`（纽约 00:00 在两种偏移下都落在整点上）。
- 新增 `services/ny_day_candles.py`：由已入库的 `1H` 行按纽约自然日聚合出 `bar='1D'`（`o` 取当日首根开盘、`h`／`l` 取极值、`c` 取末根收盘、量字段求和、当日未结束则 `confirm=0`），写回 `candles` 表，因此查询接口、前端图表和 80 根保留策略口径不变。实时路径每收到一根 1H 就**从数据库重算**受影响的那一天（一天最多 24 行），而不是在内存里增量累加，保证进程重启／WS 重连／乱序推送后都能自愈。
- `collector/market_collector.py`：新增 `TRADE_SOURCE_BARS`／`MARK_SOURCE_BARS`，把订阅的 `candle1D`／`mark-price-candle1D` 换成 `candle1H`／`mark-price-candle1H`（两个频道已在 `docs/okex/zh/api/ws/public_channel/candles.md`、`markPriceCandle.md` 的频道名列表中核验存在）。`1H` 只作派生源：不写最新值缓存、不向浏览器广播，改为广播重算后的 `1D`。
- `services/candle_backfill.py`：回填 `1H` 到第 80 个纽约自然日 00:00，整轮结束后统一重算一次窗口内全部日线（回填是从新到旧分页的，逐根派生既慢又会反复得到不完整的当天）。`_backfill_one` 对 `1D` 显式抛错——`candle_cutoff_ms("1D")` 返回 `None`，一旦误走分页循环会因为永不满足停止条件而**无限翻页**。
- `services/candle_policy.py`／`retention.py`：`DAILY_CANDLE_KEEP` 收拢到 `candle_policy`；`1H` 按时长清理，窗口刚好覆盖 80 个纽约自然日。
- `services/m25_stats.py`：新增 `source_period()`（`1D` → `1H`）、`resample_ny_day()`、`ny_day_open()`（S01／S05／S09 这类时点快照取纽约当日 00:00 的读数）、`ny_day_taker_volume_sum()`（S04 是区间累计量，按日求和）。派生行的 payload 带 `srcPeriod`／`srcTs`／`srcHours` 标注官方来源。`_poll_forever` 改为批量落库（按日重采样必须拿到整批），`1D` 轮询间隔从 24 小时改为**每小时**、回看 48 根 1H，持续修正当天尚未结束的日线。**日界缺失即跳过**：分页窗口最老的一天通常只有半天数据，写进去会得到错误的日界值或残缺的日累计量。
- 迁移 `a4c71e2f0b35`：删除按 UTC+8 口径落库的 `candles.bar='1D'` 与 `m25_stats.period='1D'`。新旧口径时间戳不同、唯一键不会互相覆盖，不删会让"中午的日线"一直残留；这些都是派生数据，回填后可完全重建。
- 前端：`CandleChart.tsx`／`M25Panel.tsx` 在选中 `1D` 时显示"日线按纽约自然日（00:00 ET）划分"提示（新增 `.bar-hint` 样式），避免与交易所页面的日线逐根对不上时产生误解。

**真实数据验证（非模拟）**：迁移在真实本地 MySQL 执行；本机后端正以 `--reload` 运行并已加载新代码完成回填。重建后 `candles` 的 `1D` 共 **640 行 = 80 个自然日 × 4 产品 × 2 类（TRADE／MARK）**，逐行校验 `ny_day_start_ms(ts) == ts`，**0 行错位**；时间戳例如 `1789963200000` = UTC 2026-09-21 04:00 = 纽约 2026-09-21 00:00 −04:00。`m25_stats` 的 `1D` 重建为 S01／S05 各 8 天 × 4 产品、S04 8 天 × 4 产品 × 3 单位，payload 含 `srcPeriod: "1H"`／`srcTs`／`srcHours`。

**测试**：新增 `tests/test_ny_day.py`（16 项，重点覆盖夏令时：EDT／EST 的日界偏移、春季 23 小时日、秋季 25 小时日、跨切换往前数 N 天、OKX UTC+8 日界不等于纽约日界）、`tests/test_m25_stats.py` 新增 2 项（1D 轮询节奏与回看根数、1H→纽约日重采样落库）、`tests/test_candle_backfill.py` 改写为 4 项（源周期替换、1D 拒绝直接回填、1H 回填覆盖完整 80 日窗口且回填期不逐根派生）。全项目 ruff／mypy／pytest **113 passed**；前端 `npm test` 18 项、`tsc --noEmit`、`npm run build` 均通过。

**遗留**：本轮未登录真实浏览器逐个 Tab 目视确认图表（数据层已逐行校验）。S09 在当前已选的四个股票永续上没有杠杆借贷市场，`m25_stats` 无 S09 行，其纽约日线口径未获得真实数据验证。

### 0.64 修复 K 线排列错位（2026-09-22）

用户授权修复，并补充具体症状为“K 线排列错位”。本轮修复既有行为缺陷，没有新增功能需求；需求正文保持 0.44。0.63 的仅诊断状态已由本记录替代。

- `frontend/src/components/CandleChart.tsx`：周期选择与图表数据集分层，以 `instId + kind + bar` 为内部图表 key，切换时重新建立独立数据／图表／光标／叠加层状态，避免不同产品或周期串入同一 series。全部绘图、OHLC 和缠论使用同一份规范化时间序列；删除独立从 `live` 更新图表的第二条数据路径。普通更新及已存在的历史时间点使用增量更新；补入缺失的较早时间点时重建序列，并按原时间锚点恢复可见窗口，取消原先静默吞掉历史更新异常的行为。
- `frontend/src/useCandleData.ts`、`candleData.ts`：封装历史加载和实时累积，按原始时间戳排序、去重，历史响应与请求期间的全部实时记录合并，保护已闭合记录不被未闭合版本回退。切换时取消旧请求，历史失败时保留已接收记录并继续显示实时数据。`api.ts` 增加本产品历史分页游标和取消信号；秒线向本产品历史接口分页取得默认两小时窗口，不直接请求 OKX，不触发上游回填。
- 默认视图按既有需求恢复为分钟／秒线最近 2 小时、日线最近 7 天，保留其余已加载历史用于平移和缠论计算。浏览器测试还复现加载容器 `display:none` 引起自动宽度为零、首次时间范围随后被拉伸，已改为保留布局尺寸的 `visibility:hidden`。秒线设置更小的点间距下限，避免图表库默认 0.5px 将两小时折线截短；日常实时更新不重设默认视图。

验证按 diagnosing-bugs 的复现／回归流程进行：新增组件级浏览器测试最初为 8 失败／1 通过，修复后最终 **11 项浏览器测试全部通过**（包括后补的周期切换等待窗口、缺失旧 K 线插入与视图保持）。测试使用实际 React 组件与 Lightweight Charts、React StrictMode、固定模拟行情和可控 HTTP 返回顺序；覆盖成交价／标记价默认窗口、产品／周期隔离、历史与多根实时交错、同时间点覆盖、较早记录修正与插入、OHLC／缠论一致、失败后实时恢复和秒线分页。`npm test` **18 项通过**；`npm run build` 通过；`npm run lint` 无新增警告，仅既有 `ProductSelector.tsx` 的 set-state-in-effect 警告。已检查修复后的模拟截图。

新增 `playwright` 开发依赖与 `npm run test:charts`，测试位于 `frontend/tests/browser/`，自动启动隔离的本机 Vite／Chromium，使用临时独立缓存，拦截所有 API 请求，不依赖真实账户、后端或 OKX。运行方法见 `frontend/README.md`；最终截图暂存于 `/var/folders/wd/qr87wvmx0xd80m88gj_3rmmc0000gn/T/okx-chart-regression-oh8EYo/`，不是持久交付文件。

证据边界与下一步：已交付上述修复及可重复回归测试；本轮未登录真实行情页面，用户也尚未指定发生错位的产品／周期。后续如仍有真实画面异常，按具体产品、周期和触发操作核对；不将模拟行情测试表述为真实行情端到端验收。

### 0.63 前端 K 线显示混乱诊断（2026-09-22，仅诊断）

用户要求检查原因，本轮没有修改前后端实现或确认新需求；需求正文保持 0.44。按 diagnosing-bugs 流程，以隔离无头浏览器直接加载现有 `CandleChart.tsx`，拦截本产品历史接口并注入固定模拟数据及受控实时 props；没有登录账户、读取凭证、访问数据库或建立 OKX 连接。

已复现并通过单变量对照确认三处问题：

1. 默认显示范围不符合既有要求：`api.ts` 固定默认取 300 根，`CandleChart.tsx` 加载后调用 `fitContent()` 显示全部。300 根连续 5m 数据实际显示约 25 小时，在 1280px 测试窗口中柱间距约 3.9px，缠论笔／标记也被压在同一屏。仅在诊断浏览器中改为最近 2 小时范围后，对应断言通过，间距约 46px。
2. 同周期切换产品时保留旧图表数据：`App.tsx` 复用 `ProductPanel`，图表创建 effect 仅依赖 `bar`，清空 React `items` 不会清空图表 series；`datasetVersion` 也未按产品重置。新产品实时值先于历史响应到达时，可以混入旧产品的 series。模拟价格约 100 的旧产品切换至约 200 的新产品，观察到旧 300 根与新 1 根同时显示，价格轴被拉伸；仅使图表随产品重建后，该断言通过。
3. 历史响应覆盖先到的实时状态：`setItems(response.items)` 全量替换了已合并实时 K 线的状态，但独立 `series.update(live)` 又把最新蜡烛画回图表。实测 series 有 301 根、OHLC 查询映射仅 300 根，最新时间不存在于映射；缠论计算也读取这份 React 状态。仅在诊断浏览器中把响应改为按时间合并并保留先到实时数据后，两者均为 301 根，对应断言通过。这是用于定位原因的对照，不是已交付修复。

复现脚本和模拟截图暂存于 `/private/tmp/okx-chart-diagnosis.79UGl6/`（临时目录可能被系统清理）。命令 `node /private/tmp/okx-chart-diagnosis.79UGl6/repro.cjs` 基线为 3 项失败；分别追加 `window`、`switch`、`merge` 只让对应断言通过，其余仍失败。诊断变体仅修改被浏览器拦截的模块响应，不修改仓库源码。

证据缺口：用户尚未提供具体产品、周期或画面，以上为代码路径的确定缺陷，尚不能将用户真实页面的全部症状归因于其中某一项；没有完成登录后的真实行情视觉核对。下一步在用户要求修复时，分别处理默认可见范围、产品切换隔离和历史／实时合并，并增加组件级回归验证；保持既有缩放／平移不被普通实时更新重置的行为。当前没有新增业务待定项。

### 0.62 主面板全宽与左侧箭头（2026-09-15）

用户确认需求 0.44：解除页面固定宽度限制、顶部紧凑化、主面板保留全部信息并占满剩余空间；入口为视口左侧居中右箭头，展开后移至抽屉右沿并朝左。`index.css` 去掉 root 的 1126px 固定宽度、居中外边距和边框；`App.css` 局部收紧 h1、固定头部不收缩并明确主面板 flex 滚动边界；`App.tsx` 用独立箭头替代头部按钮。箭头与抽屉共享宽度变量、过渡时间和 reduced-motion 规则，层级 51 低于选择弹窗 1000。

验证：新增 3 项静态布局回归测试，前端合计 11 项通过，生产构建通过；lint 仅既有 ProductSelector 警告。沿用用户此前授权的无需登录检查范围，本轮未进行登录后真实页面视觉验收，不声称已测量实际窗口尺寸或真实交互。下一步登录后检查宽屏布局、箭头开合及弹窗层级。

### 0.61 产品导航迁至左侧抽屉（2026-09-15）

用户已最终确认并授权实现：默认收起的覆盖式抽屉、左右独立、列表纵向滚动、底部固定圆角“+”、左侧“×”确认取消选择、切换产品保持展开；删除当前项优先下一项再上一项，失败保留原界面并报错。有效结果已同步到需求 0.43。

实现位于 `frontend/src/components/ProductSidebar.tsx`、`App.tsx`、`App.css` 与 `productNavigation.ts`，替代已删除的 `TabBar.tsx`。增加滑入／滑出过渡、隐藏态 inert、防重复提交锁、失败提示和相邻项选择逻辑；复用现有选择接口，不修改后端，不主动删除历史数据。

验证：前端 8 项测试通过（新增 5 项相邻项选择测试），生产构建通过，lint 仅剩 `ProductSelector.tsx` 既有 set-state-in-effect 警告。真实页面停在登录页；用户明确选择先完成无需登录的检查，真实登录验收留待后续。因此不得声称已验证真实删除、重新登录不显示、历史数据保留、滚动与双侧栏视觉交互。下一步：登录后完成这些验收。独立代码审查发现选择窗口取消当前产品仍跳首项，已修正为与侧边栏“×”相同的 `nextActiveProduct` 规则；修正后 8 项测试及生产构建再次通过。现有测试仅覆盖导航纯函数与既有显示规则，尚未覆盖删除失败、确认取消及侧边栏交互的自动化集成测试。

已完成：全局安装官方 `okx-v5-api`；确认第一项功能 REQ-001 的地区、行情环境、现货／永续范围、产品自动发现与用户选择、数据类型、周期、五档深度、辅助数据、后端／数据库／Redis 系统组成，以及永久目录、7 天保存形式与混合首次启动回填。完整有效集合以需求正文为准，不在本文件另建一套接口规格。

**实现阶段已开始**（不再是纯需求讨论）：`backend/`（Python 3.13 + FastAPI + SQLAlchemy + Alembic）与 `frontend/`（React + TS + Vite）已落地核心闭环并通过真实联调：
- 登录/会话（Argon2 哈希、Redis 会话、5 次失败冻结 15 分钟、新浏览器挤出旧会话）。
- 产品发现与选择（真实调用 OKX Global REST `/api/v5/public/instruments`）。
- M01/M02/M05 持续采集：自实现 OKX WS 客户端（心跳、指数退避重连、连接代次、desired/active 订阅集合），写入 MySQL（去重 upsert）与 Redis 缓存。
- 浏览器 `/ws/app`：`activate-product`/`deactivate-product`，`snapshot`→`update`→`empty` 信封，已用真实 BTC-USDT/BTC-USDT-SWAP 数据验证。
- 服务重启后自动按已保存订阅配置恢复采集（未依赖浏览器重新选择）。

尚未实现：内部策略消费者接口 `/internal/v1/*`（按用户 Q4 约定推迟到有真实调用方时再做）；M23 未在真实 OKX API 凭证下完成端到端联调（代码路径含空数据集分支已实现并通过单元测试，本机开发环境未配置凭证）。M10-M16、M22、M25 全部面板与保存逻辑、前端全局侧边栏均已实现并经真实数据验证。M02/M11 K 线、M03 成交现已通过 `/ws/app` 实时推送，首次启动在后台分页回填，不阻塞实时采集。

**Nacos 远程配置**（参照 `/Users/lazycatnewton/development-repo/stock-view` 后端既有模式）：新增 `backend/src/okx_backend/nacos_config.py`，MySQL/Redis 账号密码可由 Nacos 远程配置提供；Nacos 客户端自身的连接信息（服务地址、命名空间、账号密码）来自服务器环境变量 `NACOS_*`（无 `OKX_APP_` 前缀）。`NACOS_ENABLED=false`（默认）时完全不影响现有本地开发路径。已验证：禁用时正常启动；`NACOS_ENABLED=true` 但 Nacos 不可达时启动直接失败退出（不静默回退到本地占位配置）。**Nacos 侧实际的 Data ID、Group 和远程配置 YAML 结构（`database.*`/`redis.*` 顶层键）尚未与用户核对**，当前实现假定与 stock-view 一致，接入真实 Nacos 前需要确认。

**开发环境说明**：远程 MySQL 连接信息用户尚未提供；当前本机用 Homebrew 安装的 MySQL（`SELECT VERSION()` 返回 `26.7.0`，即当前 Homebrew 发行的 MySQL 版本，非字面意义的“8.0.x”，但协议与本项目用到的特性——`INSERT ... ON DUPLICATE KEY UPDATE`、JSON 列——自 MySQL 8.0 起持续可用）与 Redis 8.10.1 做开发期替代验证，`backend/.env`（未提交仓库）指向本机实例。远程 MySQL 就绪后只需改写 `backend/.env` 的 `OKX_APP_MYSQL_*` 即可切换，代码不依赖本机环境；迁移已在该本机实例验证可执行（`alembic upgrade head` 生成全部 21 张业务表 + `alembic_version`）。

最近一次功能确认：已选产品持续采集，活动 Tab 仅控制浏览器实时分发；策略使用部署内 HTTP／WebSocket 并显式订阅；M25、M22、M23 刷新策略、S04 三单位采集与偏好保存、外部账户前置条件、浏览器和策略接口契约均已定。不要重复询问这些决定。

本轮完成文档整理：把原需求中的待定清单、架构建议、验收草案、工作模板和讨论历史移到本交接文档；需求正文只保留已确认范围、对应来源与已知接口限制。未选行情目录仍可在历史能力清单／Skill 中查询。

本轮已确认：通过 `GET /api/v5/public/instruments` 分别以 `SPOT` 和 `SWAP` 自动发现产品，再由用户选择订阅；发现不等于订阅。M22 保留全部自动发现的预测市场，不按分类、系列、事件或状态筛选。需求正文已记录参数、展示字段和限速依据。

本轮已确认：产品与订阅目录永久保存；其余已选数据按明确的时间序列、每秒快照、状态变更／修订事件或追加事件形式滚动保存 7 天。首次启动采用“尽量回填可用历史，无法回填的数据从启动时积累”的混合方式；启动前缺口不得伪造。

本轮已确认：前端载体为仅桌面 Web，不适配移动页面，且单人自用；访问 Web 必须使用本产品自身登录，不得使用 OKX API 凭证作为用户登录凭证。登录、会话和浏览器 HTTP／WebSocket 契约已在需求正文确定；控制台账户创建仍是本期外部前置条件。

本轮已确认：M23 在凭证未配置、鉴权失败、网络故障及账户未达 VIP1 时，前端均返回空数据集，不暴露错误详情；该规则不影响其他行情频道。登录会话仅在当前浏览器会话有效，关闭浏览器失效，无空闲超时，主动退出立即失效。产品选择与订阅配置永久作为唯一用户的全局配置保存。

本轮已确认：本产品使用用户名密码登录；密码以带盐的单向安全哈希保存，不保存明文，也不使用 OKX API 凭证。

本轮已确认：系统包含后端服务、持久化数据库和 Redis 缓存。数据库是永久配置与历史数据的事实来源，Redis 仅保存可重建的最新状态缓存。

本轮已确认：不提供自助注册；应用账户仅由最高权限控制台账户创建。用户名重复时创建失败，初始随机密码长度不超过 18 个字符且包含大小写字母、数字和特殊字符。

本轮已确认：最高权限控制台账户的初始化不属于本期范围；该控制台只能创建唯一一个应用使用者账户，保持单人自用范围。

本轮已确认：不提供忘记密码或密码恢复功能。

本轮已确认：用户名非空、仅允许小写英文字母、长度不超过 10 个字符。

**接下来的第一步：核验并补齐所有 OKX 调用的站点支持、参数、响应、分页、限速和字段依据，同时统一版本与验收案例。** 不要直接开始实现，也不要继续询问已经确定的采集生命周期、策略接口、M25 刷新／单位、账户前置条件、浏览器接口契约、产品状态、Tab 恢复、默认窗口、登录与会话、浏览器后端边界、缓存回退、M23 凭证边界、用户名、密码恢复范围、控制台初始化范围、唯一使用者限制、创建规则、配置保存范围、M23 空数据行为、前端载体、M22 范围、保存形式、回填策略、行情编号和周期。

本轮更正确认：每一个 Tab 对应一个用户选择的 OKX 产品；产品 Tab 内同时包含 K 线和该产品的其他数据面板，K 线不是独立 Tab。第一版展示每种产品适用的全部已选数据面板；M22／M23 作为全局共享辅助数据放在独立侧边栏，具体修改留待第一版完成后迭代。

本轮已确认：选择产品即创建 Tab，取消选择即关闭 Tab，未选产品时展示空白视图；K 线默认 `5m`、最近 2 小时，可切换已选周期；产品 Tab 使用卡片、图表、表格与事件列表的组合展示。M22／M23 侧边栏按时间倒序；不在前端标注数据缺口。初始密码交付不在本期范围。

## 3. 待定事项

### 优先推进的业务问题

当前无未决业务问题。剩余工作为接口事实复核、文档一致性和后续被明确暂缓的工程选型。

Nacos 远程配置的实际 Data ID、Group 和 YAML 字段结构（`backend/src/okx_backend/nacos_config.py` 假定与 `stock-view` 一致）尚未与用户核对；接入真实 Nacos 服务前需要确认。

日线口径已在 0.65 确认为纽约自然日，由官方 `1H` 派生；0.67 补上源数据完整性与确认状态校验。不得恢复 OKX 原生 `1D/1Dutc` 或固定 UTC−4。

### 用户明确暂缓的事项

性能／可靠性指标（延迟、漏数容忍、恢复时间、逐笔完整性）、具体技术栈和部署（运行位置、数据库／Redis 产品与拓扑、单／多实例）均暂缓，后续用户恢复讨论时再推进。后端、持久化数据库和 Redis 缓存已确定；其余现存架构与心跳数值只是候选，不能当成用户已批准。

## 4. 下一步顺序

当前实现恢复点以 0.68 为准：M11 移除、M16 迁移补齐、S04 展示位置上移均已完成代码与自动回归，尚未登录真实用户浏览器目视验收（本环境无远程 MySQL／Redis／OKX 凭证）。以下为原需求阶段的后续备忘，不得用它撤销已经获授权的实现或重复询问已确认事项。

1. 逐接口核验仍在范围内的 M10、M13、M22、M23 和 M25（S01／S04／S05）的参数、站点支持、分页、限速与响应字段；解决 REST 基地址资料冲突。M11、M16 已由用户指令移除，不再需要核验。
2. 将接口契约补为可验证的操作案例，统一需求、交接和版本历史表述。
3. 用户愿意继续时再讨论性能和部署；确定调用顺序、数据模型与恢复方案。
4. 完整性检查通过后，将需求标为可交付给下一次实现对话。不要因为已创建交接文档就认为需求已完成。

## 5. 接口证据与待核验点

当前使用 Skill 0.2.0，数据生成于 2026-08-27，2026-09-10 已做本地文档核验，未进行在线联调。

- M02 的 1s／5m／15m／1D 与 M11 的 1m／5m／15m／1D 已在频道枚举核对；M11 的旧 1s 意图已被用户改为 1m，不要重提自建 1s K 线。
- H01 已确认：以 `GET /api/v5/public/instruments` 的 `instType=SPOT` 与 `instType=SWAP` 自动发现产品，再由用户选择；全球站支持该接口，限速为每个 IP + 产品类型 20 次／2 秒。选择器展示所有 `state`，但仅 `live` 可选择；该结论已写入需求正文。
- 已核验 M22 的数据层级：预测市场**系列**（`seriesId`、`title`、`category`、`freq`、结算方式／标的）→ 某系列的**事件**（`eventId`、到期时间、状态）→ 某事件的**市场**（`instId`、行权区间、状态、结果／结算值）。系列、事件、市场分别由 `GET /api/v5/public/event-contract/series`、`/events`、`/markets` 获取；均仅全球站支持、各限速 10 次／2 秒／IP。M22 WS 的 `event-contract-markets` 只能以 `instType=EVENTS` 订阅所有事件合约市场状态更新及 floorStrike 生成，不推初始快照，也没有按 `seriesId`／`eventId` 过滤的订阅参数。
- H02 已确认：保留全部自动发现的预测市场，不按分类、系列、事件或状态过滤；以上三个 REST 接口提供初始完整层级，M22 WS 提供后续市场更新。需求正文已记录保存字段与调用顺序。
- H03 已确认：产品／订阅目录永久保存；其余对象采用逐对象定义的去重时间序列、每秒快照、状态修订或追加事件形式，并按业务时间滚动保留 7 天。首次启动先恢复并刷新目录，再以历史 K 线与 M25 接口尽量回填，未能回填的数据从 WS 首次成功接收起积累，启动前缺口必须保留。
- H04 已确认：单人自用桌面 Web 必须使用本产品自身登录；该认证不使用 OKX API 凭证。登录机制的具体选择拆分为 H06。
- M05 已选 books5，不应把旧 400 档增量重建方案当作本期要求；M06 已移除。
- M16 仅 SWAP；公共强平数据不能代表总强平量。M22 是独立辅助事件合约数据。
- M23 是本期已知需鉴权的频道，文档门槛 VIP1；未达门槛、未配置凭证、鉴权失败或网络故障时返回空均为用户确认的应用行为，不是交易所原生成功响应。
- H05 已确认：M23 未配置凭证、鉴权失败、网络故障和未达 VIP1 时，前端一律返回空数据集，不暴露错误详情，也不影响其他行情频道。
- H06 已确认：使用用户名密码登录，密码仅保存带盐的单向安全哈希，不使用 OKX API 凭证。
- H08 已确认：不提供自助注册；最高权限控制台创建唯一应用账户，用户名重复即失败，用户名非空、仅小写字母且最长 10 字符，初始随机密码不超过 18 个字符并包含大小写字母、数字和特殊字符。最高权限控制台初始化和密码恢复不在本期范围。
- H09 已确认：最高权限控制台只能创建唯一一个应用使用者账户，不扩展为多用户。
- H10 已确认：每个 Tab 对应一个用户选择的 OKX 产品，Tab 内包含 K 线与该产品适用的全部已选数据面板；K 线不再独立成 Tab。M22／M23 在独立全局侧边栏展示；第一版不裁剪面板，修改留待后续迭代。
- 第一版产品视图已补充：选择／取消选择产品立即创建／关闭 Tab；未选产品显示空白；K 线默认 `5m` 最近 2 小时且可切换已选周期；各类面板使用组合展示；M22／M23 按时间倒序；数据缺口不向前端标注。初始密码交付不在本期范围。
- H07 已确认：产品选择与订阅配置永久作为唯一用户的全局配置保存；关闭浏览器、会话结束和退出不改变配置，主动修改保留版本记录。
- 比例类指标不可未经确认自行聚合。
- S01／S04 的部分原文 instId 示例形如 BTC-USDT，虽标适用永续／交割，具体合法标识须再交叉核对，不能只凭样例去掉 SWAP 后缀。
- M25 S04 已确认提供 `unit` 选择器：`0` 为币、`1` 为合约、`2` 为 U，首次打开默认 `1`。三个单位分别查询、保存和展示，不做前端换算。
- M10、M13、M22 的完整请求过滤、返回字段、M25 各项分页／保留窗口和所有选定 REST 权限仍需形成完整调用规格；当前来源表不等于逐字段核验完成。M11、M16 已移除，不再需要。
- 全球站 `sites.json` 的 REST 为 www.okx.com，同版本 introduction 正文为 openapi.okx.com，已发现资料内部差异；选定 REST 接入配置时核实并记录依据，不静默消除冲突。
- M22 首次订阅不推快照；初始状态确定由全量系列、事件、市场 REST 调用建立，后续以 `event-contract-markets` WS 更新。
- 当前公共行情文档没有统一币对数上限；已核实建连 3 次/秒/IP、每连接登录／订阅／退订合计 480 次/小时、多频道参数长度 64 KB。480 不是产品数量，指定私有频道的 30 连接限制不适用于公共行情币对数。

## 6. 资料与环境

| 资料 | 位置与用途 |
| --- | --- |
| 结果需求 | [okx-requirements.md](okx-requirements.md)（本仓库） |
| 全局 Skill | [okx-v5-api/SKILL.md](/Users/lazycatnewton/.codex/skills/okx-v5-api/SKILL.md) |
| 可选历史目录 | `/Users/lazycatnewton/awesome/okx-chat/okx-api-catalog.md`，可能与全局 Skill 不同，不要求持续维护 |
| 官方旧快照 | `/Users/lazycatnewton/awesome/okx-chat/docs/okx-official/`，参考资料，不是正在使用的全局安装位置 |
| 快照来源记录 | `/Users/lazycatnewton/awesome/okx-chat/docs/okx-official-snapshot.json` |
| 目录生成脚本 | `/Users/lazycatnewton/awesome/okx-chat/scripts/build_okx_catalog.py`，仅操作该目录内的快照，不更新全局 Skill |
| 需求目录原址 | `/Users/lazycatnewton/awesome/okx-chat/`，保留了本文档迁移前的副本；后续维护只在本仓库进行，不要回头改那份副本 |

`okx-api.md` 已按用户要求退役删除，所有维护、引用与全文阅读期望已取消。不要恢复这份文档或以完成全量 API 阅读作为需求讨论前提。

Skill 查询：先读取 SKILL.md 与 sites.json 检查兼容性；按模块索引和 method + path 查 index.json，定位目标站点／语言正文；WS 单独搜索频道正文。记录版本、生成时间、核验日期和相对 Skill 路径；不凭记忆补参数，不把快照缺失直接断言成接口不存在。Skill 默认离线查询，按其更新流程与用户授权处理版本更新。

## 7. 未确认方案备忘

以下从旧需求迁入，仅供继续讨论，不是确定实施要求。部分选型已过时（如增量深度），必须结合现有 books5 范围裁剪。用户明确暂缓性能和部署，先不要主动推动这些选择。

#### 推荐架构（待确认）

以下是尚未确认的设计候选，性能与部署选择本轮暂不讨论。候选方案采用常驻后端中的行情连接模块，按需建立 public、business 两类 WS，复用同一条连接订阅多个产品。先作为应用内模块实现，后续按规模拆分为独立进程；不预设微服务或消息队列。

数据流：`OKX WS → 连接管理 → 订阅管理 → 数据解析与缓存 → 本应用 WS／SSE 或内部消费者`。REST 用于初始化和可恢复数据的补查，HTTP 客户端可复用连接，但不作为行情推送的替代协议。

| 模块 | 责任 |
| --- | --- |
| 连接管理 | 根据站点、环境、服务路径选地址；维护状态、心跳、断线重连；需要时才加载私有凭证 |
| 订阅管理 | 维护 desired／pending／active 集合；按完整订阅参数去重和引用计数；确认成功后标记 active；重连按最新 desired 恢复 |
| 数据处理 | 区分订阅回执、业务错误、心跳和行情；将价格、数量保留为十进制字符串；保存交易所时间与本地接收时间 |
| 缓存与分发 | 最新行情／五档快照按产品覆盖；K 线按站点、环境、产品、周期、开盘时间更新；分发给所有相同订阅的消费者 |
| 历史恢复 | 用 REST 获取初始 K 线并补查断线窗口；合并缓存的 WS 更新，禁止旧 REST 结果覆盖更新的实时值 |
| 状态与观测 | 分别报告连接状态、订阅状态、最后业务数据时间、延迟、重连次数、错误及数据缺口 |

订阅键至少包含 `site + environment + channel + instId`，若后续频道使用其他过滤参数，必须纳入规范化键。连接键按站点、环境、服务路径和鉴权身份区分。相同产品的公共行情可以复用上游连接；未来私有数据必须按账户隔离。

#### 连接和数据生命周期（实现建议）

1. 消费者请求订阅，例如 `BTC-USDT` 的 `tickers`。创建 desired 条目；已有上游订阅则复用，向新消费者先返回带时间和状态的缓存。
2. 建立 TLS WebSocket；普通公共行情直接发送 `subscribe`。订阅请求填写唯一 `id`，批量 `args` 控制在官方长度限制以内；处理每个频道的确认和错误。
3. 收到订阅确认后进入“已订阅／等待数据”；不能只凭 socket 打开就显示行情可用。首条有效数据到达后才更新该主题的数据就绪状态。
4. 心跳采用应用层文本 `ping`／`pong`。候选参数：20 秒未收到消息发送 `ping`，等待 10 秒仍无 `pong` 则重连；这些数值是项目建议，需配置化。收到 `pong` 不能更新“行情数据时间”。
5. 断线进入退避重连：候选 1、2、4、8 秒，最多 30 秒，加入随机抖动。所有连接共享出口 IP 建连预算；订阅调度遵守每连接操作额度。参数／权限错误单独标记，避免无限重连。
6. 每次重连生成新连接代次，忽略旧连接晚到的消息和计时器回调；按最新 desired 重新订阅，清理旧 pending／active，关闭多余连接。
7. 价格与五档深度恢复当前快照；K 线分页补查缺失区间，记录 `confirm`，已闭合状态不因旧消息回退。不能承诺通过 ticker 或快照重建断线期间每次价格变化。
8. 若使用增量深度，等待该 WS 自带快照，再按 `prevSeqId/seqId` 合并；检测断档后停止分发无效盘口并重新订阅获取快照。按官方序列规则处理无变化和序列重置，不把 REST 深度快照直接拼进 WS 增量流。
9. 无订阅者时可延迟退订，减少页面切换造成的频繁操作；退出时取消定时器、关闭连接。慢消费者使用有界队列；仅可合并快照／最新值，不能静默丢弃深度增量或需要逐笔完整性的事件。

连接状态候选：`DISCONNECTED → CONNECTING → SUBSCRIBING → CONNECTED`，失败进入 `BACKOFF`；需鉴权的扩展在订阅前增加 `AUTHENTICATING`。主题数据另维护“等待数据、可用、补数中、缺口／不可用”；因部分频道只在变化时推送，不能统一按短暂沉默判定数据失效。

#### 验收草案

| 场景 | 预期结果 |
| --- | --- |
| 没有任何 OKX 凭证 | 仍能订阅所选站点支持的普通 tickers、K 线、books5 |
| 两个消费者订阅同一主题 | 同一服务实例只建一个上游订阅；其中一个退出不会影响另一个 |
| 订阅参数错误 | 记录该主题失败原因，不伪报订阅成功，不持续高速重连 |
| 断网后恢复 | 在限速内自动恢复当前需要的订阅；缓存标明状态；K 线缺口得到补查或明确报告 |
| 服务重启／旧消息晚到 | 按启动配置恢复所需订阅；旧连接事件不能覆盖新连接状态 |
| 只有 pong、暂无成交 | 连接可存活；业务数据时间不被伪造刷新；按频道语义呈现最后数据时间 |
| 慢消费者／队列满 | 内存有上限，其他消费者不被阻塞；若发生不可合并的数据丢失，明确报告并重同步 |

补充候选：订阅引用计数、连接代次、有界队列、断线补数和数据就绪状态都需在后续规格中决定。当前尚无这些候选的测试结果。

## 8. 持续更新规则

- 每次用户确认、修改、撤回需求后，同步修改结果需求与本文件；先更新当前有效状态，再追加一条简短变更记录。
- 用户未确认的建议、问题、阻碍和新发现放本文件；不要把它们放入结果需求的功能清单。
- 已确认事项移出待定清单，记录结论所在需求章节；不要留下互相冲突的“待确认”标签。
- 下一步始终写成可执行动作；工作中断前更新完成内容、未完成内容、文件与验证状态。
- 需求正文保留稳定 REQ／M／S 编号和接口依据；交接只保留恢复工作必要的上下文，避免复制整份需求造成双重事实来源。
- 持续更新指后续本项目相关对话中的维护，不是无人触发的后台定时任务。

## 9. 完整性检查与规格整理指引

### 交付前检查

1. 每项功能的意图、范围与关键行为已确认，不留影响执行结果的歧义。
2. 实际用到的接口均已通过 `okx-v5-api` 查询，在本需求中记录可定位的正文路径、版本、核验日期与适用条件，影响实现的版本冲突已解决。
3. 请求参数能从明确输入推导，响应字段能映射到明确状态和用户输出。
4. 调用顺序、权限、模式、单位、限速、分页及异常恢复都已写清。
5. 技术栈和运行环境已选定，数据模型、模块职责和关键实现步骤足够支撑后续编码。
6. 验收场景有可观察的通过标准；REQ-001 按已确认的实盘行情范围验证，不要求模拟盘验收。

正式需求条目应在确认后包含：用户任务和范围、输入输出、关联接口（地区／版本／文档路径）、参数映射、调用顺序、状态及异常处理、存储口径、验收案例。不要把空模板复制成已确定功能；缺项在本文件跟踪。

## 10. 讨论变更历史

| 日期 | 版本 | 内容 |
| --- | --- | --- |
| 2026-09-22 | 0.64 | 根据用户授权及“K 线排列错位”补充完成修复：按产品／类型／周期隔离图表状态，统一历史与实时序列、OHLC 和缠论，处理乱序修正／插入并保留视图，恢复默认时间窗口与秒线本地分页。11 项浏览器回归、18 项单元测试和生产构建通过；无新增 lint 警告。需求仍为 0.44，未进行真实登录验收。 |
| 2026-09-22 | 0.63 | 完成 K 线显示混乱诊断：模拟浏览器复现默认范围过宽、切换产品残留旧 series、历史响应覆盖先到实时状态三项问题，单变量对照分别验证原因；源码未改、需求仍为 0.44。详细证据与下一步见恢复点 0.63。 |
| 2026-09-10 | 0.1 | 建立需求框架、记录已确认的文档目标、关联首版 API 索引；等待用户描述业务需求 |
| 2026-09-10 | 0.2 | 按用户要求先提供完整能力范围；下载官方分拆文档，新增跨地区 REST 全量索引和 WS 文档目录 |
| 2026-09-10 | 0.3 | 接口依据改为全局 `okx-v5-api`；取消独立 API 汇总文档的维护、引用、编号与全量审阅要求；需求规格直接关联 Skill 接口正文 |
| 2026-09-10 | 0.4 | 新增 REQ-001 行情连接服务草案；核验公共行情免鉴权、WS 路径与连接限制，记录订阅、心跳、重连、分发和补数设计 |
| 2026-09-10 | 0.5 | 确认双消费端、实盘、现货与合约、历史保留 7 天；增加地区、订阅限制和行情选择目录；性能与部署暂缓讨论 |
| 2026-09-10 | 0.6 | 确认全球站与现货／永续范围；说明行情编号支持多选，具体选择待用户确定 |
| 2026-09-10 | 0.7 | 记录现货和永续的行情选择；对 M16／M22 适用性、M06／M23 权限及 M25 子项保留明确待确认项 |
| 2026-09-10 | 0.8 | 暂移 M06；M16 仅永续；M22 辅助接入；M23 共享且不达 VIP1 返回空；记录 K 线周期与 M11 的 1s 能力缺口 |
| 2026-09-10 | 0.9 | M11 确定 1m／5m／15m／1D，M05 确定五档；列出 M25 的 S01～S11 候选、接口、周期和历史窗口 |
| 2026-09-10 | 0.10 | M25 确认 S01、S04、S05、S09、S10、S11，其他统计候选不纳入本期；统计周期待确认 |
| 2026-09-10 | 0.11 | 确认 S01／S04／S05 使用 5m／15m／1D，S09 使用 5m／1H／1D，S10／S11 按原始时间戳保存 |

| 2026-09-10 | 0.12 | 按用户明确分工创建 HANDOFF.md；迁出需求中的过程内容，保留已确认功能与来源；下一步确认订阅产品范围 |
| 2026-09-10 | 0.13 | 再次确认 HANDOFF.md 为需求完善过程的持续交接载体；明确每次实际工作结束时同步维护，未改动结果需求的功能范围 |
| 2026-09-11 | 0.14 | 确认现货与永续以产品自动发现后由用户选择开始；核验全球站 `GET /api/v5/public/instruments` 的 SPOT／SWAP 用法和限速，移除 H01，下一步推进 H02 |
| 2026-09-11 | 0.15 | 确认 M22 保留全部自动发现的预测市场；核验系列、事件、市场 REST 层级和全量 EVENTS WS 订阅，移除 H02，下一步推进 H03 |
| 2026-09-12 | 0.16 | 确认产品／订阅目录永久保存，其他对象的具体 7 天保存形式与滚动清理；确认混合首次启动回填，移除 H03，下一步推进 H04 |
| 2026-09-12 | 0.17 | 确认前端仅为桌面 Web、无需移动端适配、单人自用；H04 收敛为是否需要本产品自身登录 |
| 2026-09-12 | 0.18 | 确认单人桌面 Web 必须有本产品自身登录，移除 H04；新增 H06 跟踪登录机制，下一步推进 H05 |
| 2026-09-12 | 0.19 | 确认 M23 所有已讨论的不可用状态均向前端返回空数据集，移除 H05，下一步推进 H06 |
| 2026-09-12 | 0.20 | 确认浏览器会话边界：关闭浏览器失效、无空闲超时、退出立即失效；H06 收敛为登录机制，新增 H07 跟踪配置保存范围 |
| 2026-09-12 | 0.21 | 确认产品选择与订阅配置永久作为唯一用户的全局配置，移除 H07，下一步继续 H06 |
| 2026-09-12 | 0.22 | 确认用户名密码登录及密码不保存明文，移除 H06；新增 H08 跟踪初始账户、用户名规则和凭证恢复 |
| 2026-09-12 | 0.23 | 确认系统包含后端、持久化数据库与 Redis 缓存；明确数据库为持久化事实来源、Redis 为可重建最新状态缓存 |
| 2026-09-12 | 0.24 | 确认禁止自助注册、最高权限控制台创建账户、重名失败及随机初始密码规则；H08 收敛为控制台初始化与恢复，新增 H09 核对单人范围 |
| 2026-09-12 | 0.25 | 最高权限控制台初始化移出本期范围；确认控制台仅创建唯一使用者账户，移除 H09；H08 收敛为用户名规则与凭证恢复 |
| 2026-09-12 | 0.26 | 确认不提供密码恢复，H08 收敛为用户名格式规则 |
| 2026-09-12 | 0.27 | 确认用户名仅小写字母且最长 10 字符，移除 H08；新增 H10 跟踪桌面 Web 页面与数据视图 |
| 2026-09-12 | 0.28 | 确认每种数据视图独立 Tab、K 线独立展示及产品面板绑定规则；H10 收敛为其余 Tab 清单与交互 |
| 2026-09-12 | 0.29 | 更正 Tab 结构：每个 Tab 对应一个 OKX 产品，Tab 内含 K 线与产品面板；K 线不再独立 Tab |
| 2026-09-12 | 0.30 | 确认第一版每个产品 Tab 展示全部适用面板，M22／M23 放入独立全局侧边栏；移除 H10，下一步补齐接口调用规格 |
| 2026-09-12 | 0.31 | 确认产品 Tab 创建／关闭、空白初始视图、K 线默认与切换、面板组合形式、侧边栏倒序及不标注数据缺口；初始密码交付移出本期范围 |
| 2026-09-12 | 0.32 | 完成 grilling 决策收敛：确认 live 产品选择、Tab 恢复、默认时间窗口、结构化面板详情、M25 控制、侧边栏分页、会话与登录限制、浏览器后端边界、缓存回退、目录刷新及 M23 服务端凭证边界；需求正文更新为 0.31 |
| 2026-09-12 | 0.33 | 基于 Skill 0.2.0 核验并写入 M01～M16、M22、M23 和 M25 的核心／详情字段及主要调用参数；发现 M25 S04 的单位需用户确定 |
| 2026-09-12 | 0.34 | 确认 M25 S04 支持币、合约和 U 三种可选单位，默认合约；每个单位独立查询、保存和展示 |
| 2026-09-12 | 0.35 | 完成第二轮 grilling 收敛：确认持续采集、内部策略契约、REST 刷新策略、账户前置条件、浏览器 API 契约、S04 三单位持续回填与偏好保存；需求正文更新为 0.33 |
| 2026-09-12 | 0.36 | 完成待核验审查：固定 Global REST 基地址、补齐 M10～M16／M22／M23／M25 限速与分页依据，新增功能验收案例；需求正文更新为 0.34 |
| 2026-09-12 | 0.37 | 确认桌面前端采用 React + TypeScript + Vite；明确 WebSocket 数据层与渲染组件分离；需求正文更新为 0.35 |
| 2026-09-12 | 0.38 | 确认行情后端采用 Golang；未来 Python 策略／研究仅经内部接口消费行情；需求正文更新为 0.36 |
| 2026-09-12 | 0.39 | 需求、交接与 agent 约束文档迁入开发仓库 `/Users/lazycatnewton/development-repo/okx`；接口目录快照与生成脚本留在原需求目录；需求内容未变，仍为 0.36 |
| 2026-09-12 | 0.40 | 行情后端技术栈由 Golang 改为 Python，允许使用第三方 SDK `python-okx`（PyPI）承担部分 REST／WS 调用，但明确 SDK 不替代本需求确认的频道、参数、限速、存储与回填规则，也不替代 `okx-v5-api` Skill 的接口核验；需求正文更新为 0.37 |
| 2026-09-12 | 0.41 | 确认持久化数据库为 MySQL 8.0 及以上，且不部署在本机开发环境（远程实例）；数据库具体主机、拓扑与单／多实例仍待后续确定；需求正文更新为 0.38 |
| 2026-09-12 | 0.42 | 开始实现阶段：backend/frontend 落地核心闭环（登录/会话、产品发现与选择、Tab、M01/M02/M05 持续采集与浏览器 WS 分发），本机用 Homebrew MySQL/Redis 做开发期替代验证（远程 MySQL 连接信息尚未提供）；已用真实 OKX 全球站公共 REST/WS 联调通过；需求文档内容未变，仍为 0.38 |
| 2026-09-12 | 0.43 | 参照 stock-view 后端实现，为 backend 增加 Nacos 远程配置支持：MySQL/Redis 账号密码由 Nacos 远程配置提供，Nacos 客户端自身连接信息（服务地址/命名空间/账号密码）来自服务器环境变量；默认 `NACOS_ENABLED=false` 不影响现有本地开发路径；已验证禁用路径正常启动、Nacos 不可达时启动失败（不静默回退），新增 6 项单元测试；需求文档内容未变，Nacos 侧 Data ID/Group/YAML 结构尚未与用户核对，仍是按 stock-view 既有约定的假设 |
| 2026-09-13 | 0.44 | 用户反馈图表展示 K 线不接实时、周期缺 1m/30m、1s 应为折线图、需要更美观的图表实现、K 线保留策略改为 1D 80 根/分钟级 10 天且首次启动需补足下限；已实现：M02/M11 K 线与 M03 新增 trades 频道经 `/ws/app` 实时推送、K 线周期扩展为 1s/1m/5m/15m/30m/1D（标记价格无 1s）、CandleChart 改用 TradingView Lightweight Charts v5（1s 折线其余蜡烛）、新增 candle_policy.py 保留规则与 candle_backfill.py 后台分页回填（不阻塞实时）。需求正文更新为 0.39 |
| 2026-09-13 | 0.45 | 修复刷新后前端黑屏：Lightweight Charts 要求时间严格递增，回填/实时交错产生同秒重复记录时抛出未捕获异常导致 `#root` 被卸载；已按显示时间戳去重并新增 `AppErrorBoundary` 兜底渲染。修复 M11 6 字段 `confirm` 被误当第 6 列 `vol` 导致 `NOT NULL` 报错：新增 `parse_candle_row()` 按 kind 分列解析。修复 `/ws/app` 发送协程在客户端断开瞬间抛出未捕获 `WebSocketDisconnect` 的 ASGI 异常：新增 `try_send_text()` 吞掉正常断连。需求正文内容未变 |
| 2026-09-13 | 0.46 | 用户反馈：1) 项目统一展示时区改为美国东部 ET；2) `SPCX-USDT-SWAP` 等股票永续历史 1D K 线在拆股前区间价格达 3000+ 明显偏离当前约 150 的价格。已核实：OKX `history-candles`/`candles` 支持 `adjust=forward` 前复权参数（仅对股票永续合约生效），此前回填代码未传该参数；已改为固定传 `adjust=forward`，重新回填后 SPCX 历史 1D 价格已与当前一致。已核实 `history-mark-price-candles`/`mark-price-candles` 不支持 `adjust` 参数（文档未列出且实测无效），标记价格历史 K 线在公司行为发生前区间仍是未复权状态，记为 OKX 接口已知限制。前端新增 `time.ts`，K 线图与成交/Ticker 时间格式化统一改为 `America/New_York`（含 EST/EDT 自动切换），图表标题标注 ET；数据库/API/WS 原始时间戳仍为 UTC 毫秒，不受影响。需求正文更新为 0.40 |
| 2026-09-13 | 0.47 | 修复前端两处未捕获异常：`formatEt()` 在传入 `dateStyle`/`timeStyle` 时又默认附加 `timeZoneName`，触发 `Intl.DateTimeFormat` 的 `RangeError: Invalid option`；`/ws/app` 的 M02/M11 实时 candle 广播里 `ts` 是 OKX 原始字符串，而 `CandleItem.ts` 约定为 number，`marketDataStore.ts` 未转换导致 `new Date(string)` 解析失败、抛 `RangeError: Invalid time value`；两者均被 `AppErrorBoundary` 拦截显示为"界面加载失败"。已在 `time.ts`/`marketDataStore.ts` 修复并各自新增防御性校验。同时修复 `/ws/app` 的 `RuntimeError: WebSocket is not connected`：发送/接收协程各自独立调用 Starlette send/receive，客户端断开时若只有一方检测到并退出，另一方会在半死连接上再次调用而抛出非 `WebSocketDisconnect` 的 `RuntimeError`；改为 `run_socket_loops()` 用 `asyncio.wait(FIRST_COMPLETED)` 统一取消。**补齐已交付功能的正确性缺口**：此前 M01/M02/M03/M05/M11 完全没有滚动清理任务，MySQL 会无限增长；新增 `services/retention.py`，按 okx-requirements.md 的保留规则（80 根/10×24 小时/7 天）删除过期行，K 线 1D 按 `inst_id+kind` 分组用窗口函数保留最新 80 根，其余频道按业务时间戳滚动 7 天；`main.py` 的 lifespan 启动 `run_retention_cleanup_forever()`（每小时一轮，单轮失败不影响后续轮次）。已用真实数据库验证：执行后每个 `inst_id+kind` 的 `1D` K 线精确为 80 行，此前超额的 90 行被清理。新增 8 项 `test_retention.py` 单元测试（SQL 编译级 + 后台任务容错）。需求正文内容未变，仍为 0.40 |
| 2026-09-13 | 0.48 | 用户用 grilling 技能确认未实现功能清单与批次实现计划（Q1-Q5 全部"接受建议"）：批次 1 已在 0.47 完成（滚动清理）；本轮完成**批次 2：M10 标记价格、M12 资金费率、M13 持仓总量、M14 价格限制、M15 预估价格**，均仅对永续订阅（判定依据：`instId` 以 `-SWAP` 结尾，与需求文档"仅适用永续"一致），复用 M01 的 public WS 采集器模式，`market_collector.py` 新增 5 个 `_store_*` 方法（MySQL upsert + Redis 120s 缓存 + `/ws/app` 广播），`realtime/hub.py` 新增对应 `CHANNEL_KEYS`；这 5 张表此前在 0.47 的 retention.py 中已预先覆盖（`SIMPLE_RETENTION_TABLES`），本轮未再改动清理逻辑。前端新增 `SwapSnapshotCards.tsx`（5 个数值卡片组件），`ProductPanel.tsx` 按 `instId.endsWith('-SWAP')` 门控展示。已用真实 OKX 数据端到端验证：`BTC-USDT-SWAP`/`SPCX-USDT-SWAP` 五个频道均正确写入 MySQL（mark_px、funding_rate、oi/oiCcy/oiUsd、buy_lmt/sell_lmt 数值均合理），现货 `BTC-USDT` 确认未订阅这 5 个频道；M15 因当前无相关结算事件窗口暂无数据，符合"仅事件窗口推送"设计，非缺陷。新增 `test_collector_swap_channels.py`（3 项）及 `test_realtime_hub.py` 新增 1 项，全项目 ruff/mypy/pytest 42 passed，`npm run build` 通过。需求正文内容未变，仍为 0.40。下一步进入批次 3：M25（6 个独立统计接口 + 单位切换）。 |
| 2026-09-13 | 0.49 | 完成**批次 3：M25 S01/S04/S05/S09/S10/S11**。新增 `okx_client/rest.py` 六个 REST 方法（经 `okx-v5-api` Skill 逐一核验路径/参数/限速：S01/S04 各 5次/2s/IP+instId、S05/S10 各 10次/2s/IP+instId、S09 5次/2s/IP、S11 20次/2s/IP）；新增 `services/m25_stats.py` 实现历史回填（`backfill_array_metric`/`backfill_dict_metric`，按 cutoff/页大小停止分页）与启动后持续轮询（`start_m25_polling`，各周期结束后请求，S10/S11 每 5 分钟）；`main.py` lifespan 接入两者，退出时统一取消任务并关闭 REST client。新增 `api/m25_router.py`（`GET /api/market/{instId}/m25/{metric}` 查询历史、`GET/PUT .../m25/s04/unit` 读写 S04 单位偏好，复用初始 schema 已有的 `M25UnitPreference` 表，新建 `services/s04_unit_preference.py`）。真实联调中发现并修复三个问题（均有专门回归测试）：1) `asyncio.gather` 无节流导致并发首请求瞬间超过 OKX 最严 5次/2s 限速、实测触发 429，新增跨请求全局节流 `_throttle()`（`_GLOBAL_MIN_INTERVAL_SECONDS=0.5s`）；2) `backfill_m25` 原用不带 `return_exceptions=True` 的 `gather`，SPCX 无杠杆借贷市场（OKX 返回 `51012 Token does not exist`，已用 curl 核实）会让该产品/BTC 等其余全部指标一并失败，改为按 `(label, job)` 隔离并记录警告；3) MySQL 唯一索引对 NULL 不去重，`M25Stat.period`/`unit` 为 NULL 时（S01/S05/S09/S10/S11）每次轮询/回填都插入新行而非覆盖，实测复现约 3 万组重复行；改为 NOT NULL + 空字符串 `''` 语义，新增迁移 `6060da89549d`（含手写的历史数据去重 SQL），已在真实数据库上执行、验证 0 组重复后加回唯一约束。前端新增 `M25Panel.tsx`（S01/S05/S09 折线图+周期选择器、S04 主动买卖量+单位选择器与持久化、S10/S11 双栏历史表），接入 `ProductPanel.tsx`（仅永续展示，`ccy` 由 `instId` 首段推导）；`api.ts`/`types.ts` 新增 `M25StatItem`/`getM25Stat`/`getS04Unit`/`setS04Unit`。用真实浏览器登录验证时又发现并修复第四个问题：`m25_router.py` 响应组装 `{"ts": row.ts_ms, **row.raw_payload}` 展开顺序错误，`raw_payload` 自带的字符串 `ts` 覆盖了权威整数 `ts_ms`，导致前端 `new Date(字符串)` 解析失败抛 `RangeError: invalid timestamp for ET formatting`（复现于 M25Panel 首次接入后的第一次真实浏览器测试），已调整展开顺序并加 `test_m25_router_response.py` 回归测试。最终用真实浏览器分别验证 `BTC-USDT-SWAP`（S01～S11 全部有数据，S04 单位切换正常）与 `SPCX-USDT-SWAP`（S09 因无杠杆市场正确显示空图表、不崩溃）两个 Tab，无控制台错误、无"界面加载失败"。新增测试 `test_m25_stats.py`（11 项，含 429 节流与故障隔离两个专项回归）、`test_m25_router_response.py`（2 项），全项目 ruff/mypy/pytest 55 passed，`npm run build` 通过。需求正文内容未变，仍为 0.40。下一步进入批次 4：M22 + M23 + 前端全局侧边栏。 |
| 2026-09-13 | 0.50 | 完成**批次 4：M22 事件合约辅助市场 + M23 经济日历 + 前端全局侧边栏**（本轮涉及的功能均已在早期需求讨论中确认，需求正文内容不变，仍为 0.40；本条仅记录实现进度）。新增 `okx_client/auth.py`：OKX REST 私有签名（`OK-ACCESS-SIGN = Base64(HMAC-SHA256(SecretKey, ts+method+path+body))`）与 WS 登录签名（`sign(ts+'GET'+'/users/self/verify')`），6 项签名算法单元测试对照官方文档公式逐项核验；`OkxWsClient` 新增 `login_args_provider` 支持：每次（重）连接时调用该回调实时生成登录参数（时间戳必须是当次连接时刻），发送 `op=login` 并等待 `event=login` 响应（超时/失败会走既有重连退避，不会死等）。**M22**：`okx_client/rest.py` 新增系列/事件/市场三个 REST 方法；`services/event_contract_catalog.py` 实现全量目录刷新（`refresh_event_contract_catalog`：先系列→按系列取事件→按事件取市场，永久保存到已有的 `m22_series`/`m22_events`/`m22_markets` 三张表）与 WS 增量更新（`apply_event_contract_ws_update`：订阅 `event-contract-markets` 频道 `instType=EVENTS`，更新市场行并追加一条 `m22_revisions` 修订事件，`_payload_hash` 判定内容是否真正变化避免刷屏）；`main.py` 启动时**同步等待**首次全量刷新完成（M22 无 WS 快照，REST 是唯一初始状态来源）后再建立 WS 连接，并起一个每小时全量校正的后台任务兜底修正遗漏的 WS 更新。真实回填结果：23 个系列、1021 个事件、1748 个市场，全部为真实 OKX 全球站数据（如 `BTC-ABOVE-DAILY`、`XAU-HIT-MONTHLY` 等）。**M23**：`services/economic_calendar.py` 实现 `credentials_configured()`（读取 `config.py` 已有的 `okx_api_key`/`okx_api_secret`/`okx_api_passphrase` 三项）、`refresh_economic_calendar()`（未配置凭证时直接返回 0、不发起任何请求；已配置时按 `date` 分页拉取，鉴权失败/网络故障/非 VIP1 均捕获异常返回 0，不向上抛出、不暴露错误详情，保存到已有的 `m23_economic_calendar` 表）、`start_economic_calendar_ws()`（未配置凭证返回 `None`，调用方据此跳过启动 WS；已配置则返回带 `login_args_provider` 的 `OkxWsClient`，需要登录后才能订阅 `economic-calendar` 频道）与 30 分钟周期性 REST 校正任务；7 项单元测试覆盖凭证缺失/鉴权失败/网络故障三类空数据路径。真实验证：本机未配置 M23 凭证，`m23_economic_calendar` 表为 0 行，符合预期。**浏览器接口**：新增 `api/aux_router.py`（`GET /api/aux/event-contract-markets` 按 `expTime` 倒序、`GET /api/aux/economic-calendar` 按 `date` 倒序，均用条目自身排序字段值做不透明 `cursor` 分页，`hasMore`/`nextCursor` 语义已用真实分页验证：50→100 条、`hasMore=true`）；`bootstrap_router.py` 的 `auxSidebar` 字段接入两个真实查询函数替换此前的占位空数组。**前端**：新增 `components/AuxSidebar.tsx`（独立全局侧边栏，M22/M23 两个 Tab 切换、按时间倒序列表、"加载更早"按钮增量分页）；`App.tsx` 头部新增"市场/日历"按钮打开侧边栏；`types.ts` 新增 `EventContractMarketItem`/`EconomicCalendarItem`；`api.ts` 新增 `getEventContractMarkets`/`getEconomicCalendar`。已用真实浏览器登录验证：M22 Tab 正确展示 `live`（绿色）/`expired`（灰色）状态徽章、ET 格式化到期时间、行权价与结果；点击"加载更早"后条目从 50 增至 100，与后端分页游标一致；M23 Tab 因未配置凭证正确展示"暂无数据（未配置凭证/未达VIP1/鉴权或网络故障时为空）"提示，不崩溃、不暴露内部原因；关闭侧边栏后原有 Tab/K 线/M25 面板均无回归。全项目 ruff/mypy/pytest **71 passed**（新增 `test_okx_auth.py` 6 项、`test_event_contract_catalog.py` 4 项、`test_economic_calendar.py` 7 项），`npm run build` 通过。已知遗留（非缺陷）：M23 因本机未配置真实 OKX API 凭证，WS 登录路径（`op=login`→`event=login`）与 REST 鉴权路径均未在真实凭证下跑通，仅通过单元测试与代码走查确认逻辑正确；用户提供真实凭证后需要补一次真实联调。下一步进入批次 5（原计划外的收尾）：文档最终一致性检查，或用户指定的新方向；`/internal/v1/*` 按此前 Q4 约定仍推迟到有真实调用方时再做。 |
| 2026-09-13 | 0.51 | 完成**批次 5：M16 强平订单／ADL 预警**（需求正文内容不变，仍为 0.40；本条仅记录实现进度）。`services/subscriptions.py` 新增 `list_live_selected_full()` 返回 `(instId, instType, instFamily)` 三元组（原 `list_live_selected_with_type()` 保留、内部委托给新函数），因为 ADL 预警按 `instFamily` 而非 `instId` 推送，需要该字段在应用层归属到已选产品；`main.py`/`subscriptions_router.py` 的调用点同步改用三元组。`market_collector.py`：`apply_selected_products()` 签名改为接收三元组；已选任意永续产品时订阅 `liquidation-orders`/`adl-warning`（均为 `instType=SWAP` 全局订阅，协议本身不支持按 `instId`/`instFamily` 过滤，只需订阅一次，不随产品数量重复）；新增 `_store_liquidation_orders()`/`_store_adl_warning()`：前者按 `instId` 精确匹配已选集合、逐条 `details[]` 拆分为独立事件；后者按 `instFamily` 匹配、广播给该品种下所有已选产品；两者都归一化为统一的 `risk-events` 频道事件（前端展示为单一"按事件排列的列表"，而非两个独立面板），并调用已有的 `RiskEvent` 表 upsert（`inst_id+event_type+business_ts+payload_hash` 去重，模型在此前批次已建好，本轮未改表结构）；`realtime/hub.py` 的 `CHANNEL_KEYS` 新增 `risk-events` → `m16:latest:{inst_id}`（Redis 存最近 100 条数组，与 M03 trades 滚动列表模式一致）。新增 `api/market_router.py` 的 `GET /api/market/{instId}/risk-events`（按 `business_ts` 倒序、`before`/`limit` 不透明游标分页，响应字段合并顺序为 `{**raw_payload, eventType, ts}`，权威整数 `ts` 放最后，直接借鉴 0.49/0.50 已踩过的"字符串 ts 覆盖整数 ts_ms"教训，一次写对未再复现该 bug）。前端：`types.ts` 新增 `RiskEventData`；`marketDataStore.ts` 新增 `riskEvents` 状态字段与 `risk-events` 频道分发（snapshot 为数组直接替换，update 为单条事件前插并按 100 条截断）；新增 `components/RiskEventsPanel.tsx`（按事件类型着色：强平红色、ADL 预警橙色，`<details>` 展开原始字段）；`ProductPanel.tsx` 仅在 `isSwap` 时渲染。新增单元测试 `test_risk_events.py`（6 项：频道只订阅一次、非永续不订阅、未选 instId 的强平事件被丢弃、已选 instId 的强平事件正确落库并广播、ADL 预警按 instFamily 广播给该品种下所有已选产品、未选 instFamily 的预警被丢弃）与 `test_risk_events_router_response.py`（2 项，字段合并顺序回归）。**真实验证（非模拟）**：直接用真实 WS 连接 `wss://ws.okx.com:8443/ws/v5/public` 订阅 `liquidation-orders`，60 秒内收到真实强平事件（`SENT-USDT-SWAP`，非本项目已选产品，用于确认上游频道本身工作正常）；随后用真实捕获的 payload 走**真实（非 mock）** `_store_liquidation_orders()` 存储路径验证入库与 REST 查询字段顺序正确；最终在真实浏览器中，`BTC-USDT-SWAP` Tab 的 M16 面板在约 30 秒内自然收到 19 条真实强平事件（非人工注入），时间戳、`bkPx`、`side` 等字段与数据库记录完全一致，ET 格式化正常，事件计数随实时推送持续增长，与 M03 trades 面板行为一致。全项目 ruff/mypy/pytest **79 passed**（新增 8 项），`npm run build` 通过。已知遗留（非缺陷）：ADL 预警本身触发条件苛刻（仅在保证金余额进入 warning/adl 状态时推送），本轮真实验证窗口内未观测到真实 ADL 事件，该分支逻辑仅有单元测试覆盖，未见真实数据验证；用户如需完整验证需要长时间观察或等待市场出现极端行情。剩余未实现：内部策略消费者接口 `/internal/v1/*`（按 Q4 约定推迟）；M23 未在真实凭证下联调（同 0.50 记录的遗留）。 |
| 2026-09-13 | 0.53 | 用户要求"增加启动参数 env：ENV=localhost 时全部配置从 `.env.localhost` 读取，ENV=prod 时按当前 Nacos 方案读取"。经三轮确认：(1) 用环境变量 `ENV` 而非命令行参数；(2) `ENV` 未设置或非法值直接抛异常终止启动，不做静默默认；(3) `ENV=prod` 时除 MySQL/Redis 外的其余配置（OKX API 凭证、会话参数、`retention_days` 等）也必须全部来自 OS 环境变量，不允许任何 dotenv 文件兜底。实现：`config.py` 新增 `get_app_env()` 读取并校验 `ENV`；`get_settings()` 按 `ENV` 分支——`localhost` 走 `Settings()`（`model_config.env_file` 改为 `.env.localhost`，OS 环境变量优先级高于文件），`prod` 走 `Settings(_env_file=None)`（用 `python -c` 实测确认该写法完全跳过 dotenv 装载，只读 OS 环境变量与字段默认值）。`nacos_config.py` 的 `load_nacos_bootstrap()` 不再读取 `NACOS_ENABLED` 开关，改为 `enabled=get_app_env() == "prod"`（`ENV=prod` 强制启用 Nacos，`ENV=localhost` 强制禁用，避免"改了 ENV 却忘记同步 NACOS_ENABLED"的不一致状态）；`migrations/env.py` 因为委托同一套 `load_nacos_bootstrap()`/`get_settings()`，无需改动即自动遵循新规则。新增 `tests/conftest.py` 固定测试环境为 `ENV=localhost`（收集阶段早于各 router 模块顶层 `get_settings()` 调用生效）。新增 `tests/test_app_env.py`（8 项：未设置/非法值报错、合法值识别、prod 模式忽略当前目录 dotenv 文件只读 OS 环境变量、localhost 模式读取 dotenv 文件且 OS 环境变量可覆盖）；更新 `tests/test_nacos_config.py` 的两项既有测试改为按 `ENV` 而非 `NACOS_ENABLED` 断言。**真实验证**：`ENV=localhost uv run alembic current` 与 `ENV=localhost uv run uvicorn ...` 均正常启动、`/healthz` 返回 `{"ok":true}`；`env -u ENV uv run alembic current` 与 `env -u ENV uv run uvicorn ...` 均在启动瞬间抛出预期的 `RuntimeError` 并以退出码 1 终止，未静默降级。顺手把 `backend/.env` 迁移为 `backend/.env.localhost`（内容确认逐字节相同后删除旧文件）、`.env.example` 迁移为 `.env.localhost.example`（同步补上此前只在 `.env` 里存在、`.env.example` 遗漏的 M23 凭证三项占位与 Nacos 相关变量），`.gitignore` 补充 `.env.localhost`（原 `.env` 规则不会精确匹配这个新文件名），`backend/README.md` 新增「启动环境 ENV」小节并把所有 `NACOS_ENABLED`/`.env` 引用改为按新规则描述。全项目 ruff/mypy/pytest **87 passed**（新增 8 项，另有 2 项因语义变更被改写而非新增）。需求正文与 `okx-requirements.md` 均未改动（该文档未涉及具体部署/启动参数，属于此前"明确暂缓"的工程选型细节，本次只是应用户直接指令做的配置装载机制调整，不改变已确认的产品需求范围）。 |
| 2026-09-14 | 0.54 | 用户用 grilling 技能要求"将 `/Users/lazycatnewton/development-repo/skills/chan` 这个 Skill 在前端图表页面实现，即在前端图表中展示出中枢，除了 1s/1m 的周期外都要实现"。经两轮确认收敛：Q1 计算位置=前端计算；Q2 适用范围=M02 与 M11 都要（M02 排除 1s/1m，M11 排除 1m）；Q3 视觉范围=中枢矩形+笔连线+分型点+背驰点全部画，买卖点(1B/2B/3B等)留后续更大功能；Q4 数据不足时=暂时不显示（不伪造、不标注缺口）；另有 Q5 背离(DIV)与背驰(BC)两种强度都画、用样式区分，Q6 只用已闭合 K 线（`confirm=1`）参与计算避免结构随实时数据抖动，Q7 视觉样式细节全部"接受当前建议"。**实现**：新增 `frontend/src/chan.ts`（纯 TypeScript 移植，逐函数对应 Skill 的 `chan_core.py`：`mapKBars` 包含处理、`detectFractals` 分型、`detectStrokes` 笔、`detectZhongshu` 中枢、`calculateMacd`/`detectDivergences` 背离背驰；不含买卖点判定，按 Q3 明确排除）——**已用两组独立合成数据集（120 根、200 根 K 线）对照 Python 原始实现逐字段验证结果完全一致**（fractals/strokes/zhongshu/divergences 数量与数值均相同，用 esbuild 编译 TS 后在 Node 中运行对比）。新增 `frontend/src/chanPrimitives.ts`（`ChanZhongshuPrimitive`/`ChanStrokePrimitive`，基于 Lightweight Charts v5 的 `ISeriesPrimitive`/`attachPrimitive` 自定义画布层，绘制半透明中枢矩形与笔连线折线）与 `frontend/src/chanOverlay.ts`（适配层：`isChanEnabledForBar()` 按 Q2 规则判定周期是否启用、`computeChanOverlay()` 过滤 `confirm==='1'` 后调用 `analyzeChan()` 并转换为图元/`SeriesMarker[]`，分型用三角标记、背驰 BC-B/BC-S 用醒目橙红实心方块、背离 DIV-B/DIV-S 用同色系淡色方块区分强度）。**发现并补齐一个此前的功能缺口**：核实后发现前端此前完全没有渲染任何 M11（标记价格）K 线图表组件（虽然 M11 数据流已在 `marketDataStore.ts` 就绪），经用户确认后本轮一并新建；`components/CandleChart.tsx` 重构为 `GenericCandleChart` 通用组件（`kind: 'trade'\|'mark'` 参数化），导出 `CandleChart`（M02）与新增的 `MarkPriceChart`（M11，`ProductPanel.tsx` 按 `isSwap` 门控渲染，与其余仅永续面板一致）。**发现并修复一个真实的、非本次引入的既有渲染 bug**：原 `CandleChart.tsx` 用三元表达式在"加载中"时渲染 `<p>`、加载完成后才渲染带 `ref` 的图表容器 `<div>`，导致 React 在 `loading` 状态翻转时整个卸载/重新挂载该 DOM 节点，而创建图表实例的 `useEffect` 依赖仅为 `[bar]`（不含 `loading`），已绑定的 `containerRef.current` 指向的旧节点被卸载后图表初始化的 effect 不会重跑，实际观察到的现象是 K 线图区域完全空白、0 个 `<canvas>` 元素、且不产生任何控制台错误（因为 `createChart` 调用本身发生在初始渲染时机、指向的是当时仍存在的元素，只是该元素随后立刻被替换）；用 CDP MutationObserver 定位到该问题后，改为容器 `<div>` 始终挂载、仅用 `style.display` 控制加载态遮挡文案，不再整体卸载。**真实浏览器验证（非模拟数据）**：登录后在 `BTC-USDT`（现货，仅 M02）、`BTC-USDT-SWAP`（永续，M02+M11）两个 Tab 上验证：M02/M11 的 `5m`/`1D` 周期均正确显示黄色半透明中枢矩形（真实计算值如 ZG=77893.8/ZD=77599、ZG=76807.1/ZD=76750，与后端真实 300 根 K 线一致，已用相同数据集在 Python 原始实现与 TS 移植版上分别复算、结果逐字段相同）、灰色笔连线、灰色分型三角标记、多个橙色 BC-B/BC-S 背驰标记；切到 `1s`/`1m` 周期时中枢/笔/标记全部正确消失（M02/M11 独立验证均正确）；SPOT 产品（无 SWAP 后缀）正确不渲染 M11 图表。全项目 `tsc --noEmit`/`npm run build`/`oxlint` 均通过（无新增告警，2 处既有 `set-state-in-effect` 告警与本次改动无关）。需求正文新增"M02／M11 K 线的缠论结构叠加层"小节，更新为 0.41。 |
| 2026-09-14 | 0.55 | 用户直接指令"使默认环境为 localhost"，纠正 0.53 里"ENV 未设置必须报错"的设计（用户实测遇到 `RuntimeError: 环境变量 ENV 必须显式设置...`，判定该行为不便于日常本地开发，要求改为默认值）。**实现**：`config.py` 的 `get_app_env()` 改为——`ENV` 未设置（空字符串）时直接返回 `"localhost"` 默认值；`ENV` 有值但既不是 `localhost` 也不是 `prod` 时仍然抛 `RuntimeError` 终止启动（非法值拒绝的行为保留，只放开"未设置"这一种情况）。`nacos_config.py` 无需改动，因为它委托同一个 `get_app_env()`，未设置 `ENV` 时自动按 localhost 语义跳过 Nacos。同步更新 `tests/test_app_env.py`（原 `test_get_app_env_raises_when_unset` 改为 `test_get_app_env_defaults_to_localhost_when_unset`，断言返回值而非异常）、`backend/README.md`（"启动环境 ENV"小节改为"未设置时默认为 localhost"、启动/迁移命令示例去掉不再必需的 `ENV=localhost` 前缀，同时明确提示生产部署必须显式设置 `ENV=prod` 否则会按本地开发模式启动）、`config.py` 顶部模块 docstring。**真实验证**：`env -u ENV uv run uvicorn ...`（完全不设置 `ENV`）正常启动、`/healthz` 返回 200，日志显示按 localhost 语义连接本地 MySQL/Redis、跳过 Nacos、正常收到真实 OKX WS 数据；`ENV=garbage` 仍正确抛出 `RuntimeError: 环境变量 ENV 取值非法...` 拒绝启动；`ENV=prod`/`ENV=localhost` 显式设置的行为不变。全项目 ruff/mypy/pytest **87 passed**（1 项测试改写而非新增，用例总数不变）。需求正文与 `okx-requirements.md` 均未改动（该文档不涉及具体启动参数细节）。 |
| 2026-09-14 | 0.56 | 0.55 上线后用户实测遇到真实故障：`pymysql.err.OperationalError: (1045, "Access denied for user 'okx_app'@'localhost' (using password: NO)")`——排查发现根因不是密码本身，而是 `config.py` 里 `Settings.model_config.env_file=".env.localhost"` 用的是**相对路径**：pydantic-settings 按进程当前工作目录解析该路径，只要不是从 `backend/` 目录启动（例如从仓库根目录、或用 `--app-dir` 等方式启动），就会静默找不到 `.env.localhost` 文件、`mysql_password` 等字段全部退回代码默认值（空字符串），配置装载阶段不报任何错误，只有真正连接 MySQL 时才会看到 "Access denied ... (using password: NO)"，误导排查方向。**修复**：`config.py` 新增 `_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent`（从 `backend/src/okx_backend/config.py` 向上三级即 `backend/`）与 `_ENV_LOCALHOST_PATH = _BACKEND_ROOT / ".env.localhost"`，`Settings.model_config` 的 `env_file` 改用该绝对路径字符串，不再随 cwd 变化。同步更新 `tests/test_app_env.py`：原来依赖 `monkeypatch.chdir(tmp_path)` 的两项测试（`test_localhost_settings_read_from_dotenv_file`、`test_localhost_settings_os_env_overrides_dotenv_file`）改为显式传入 `Settings(_env_file=str(dotenv))`（因为路径固定后 chdir 不再能让 `Settings()` 读到临时目录里的文件，这是修复后的正确行为，不是回归）；新增专项回归测试 `test_settings_env_file_path_is_absolute_and_independent_of_cwd`（断言 `model_config["env_file"]` 是绝对路径、且切到空临时目录后 `Settings()` 仍能读到真实的 `backend/.env.localhost` 里的密码）。**真实验证**：分别从仓库根目录（`cd okx && uv --project backend run python -c ...`）与 `backend/` 目录执行同一段读取 `get_settings().mysql_password` 的代码，修复前前者返回空、后者非空（复现故障）；修复后两者一致非空。用**故意从仓库根目录、不设置 `ENV`、用 `--app-dir` 方式**启动的真实 uvicorn 进程验证：应用正常启动、`/healthz` 返回 200、日志显示 retention 清理任务成功对真实 MySQL 执行了查询（而非仅仅"没有崩溃"），证明是真实数据库连接成功而不是巧合。全项目 ruff/mypy/pytest **88 passed**（新增 1 项）。需求正文与 `okx-requirements.md` 均未改动（纯配置装载缺陷修复，不涉及产品需求范围）。 |
| 2026-09-14 | 0.57 | 用户提出两项图表优化：(1) 在每个中枢上区间和下区间分别标注价格；(2) 光标移动到某根 K 线时展示收盘、开盘、最高、最低价。实现：新增纯函数模块 `frontend/src/chartDisplay.ts` 与 Node 原生测试 `frontend/tests/chartDisplay.test.ts`，测试先因模块不存在失败（RED），实现后 2 项通过（GREEN）；`package.json` 新增 `npm test`。`ChanZhongshuPrimitive` 在每个中枢右端绘制 `ZG + 价格`、`ZD + 价格` 两个高对比标签；`CandleChart` 订阅 Lightweight Charts `subscribeCrosshairMove`，按光标时间从保留原始字符串的 K 线映射中读取 OHLC，标题下方按“收盘/开盘/最高/最低”展示，离开图表时恢复提示，不把十进制字符串转浮点再格式化。真实浏览器验证：将光标移动到 BTC-USDT 的真实 K 线上，页面显示收盘 `77736.6`、开盘 `77522.6`、最高 `77772.3`、最低 `77522.5`；中枢上下沿标签已在 Canvas 图层渲染。`npm test` 2 项、TypeScript 类型检查和生产构建通过。需求正文更新为 0.42。 |
| 2026-09-14 | 0.58 | 修复用户反馈“选择产品界面当前在图表之下，应始终处于图表最上层”。真实浏览器复现并检查 computed style：`.product-selector-overlay` 是 `position: fixed` 但 `z-index: auto`，Lightweight Charts 内部 Canvas 为 `z-index: 1`，导致 Canvas 绘制在选择器遮罩之上。先新增 `frontend/tests/productSelectorLayer.test.ts`，测试因遮罩没有显式层级而失败；随后在 `.product-selector-overlay` 增加 `z-index: 1000`（高于图表 Canvas 和 `z-index: 50` 的全局侧边栏）。回归测试转绿，前端 3 项测试和生产构建通过；真实浏览器验证 computed `z-index=1000`，视口中心最顶层元素属于 `.product-selector`，选择器及遮罩完整覆盖图表。需求正文未变（既有“选择产品”交互的显示缺陷修复）。 |
| 2026-09-14 | 0.59 | 修复用户反馈"新增的产品没有马上开始补足要求的数据"。**根因（3 处协同问题）**：(1) K 线历史回填（`backfill_candles`）、M25 历史回填（`backfill_m25`）与 M25 周期轮询（`start_m25_polling`）此前只在服务 `lifespan` 启动时基于当时已选产品快照运行一次；运行期通过"选择产品"新增产品时，`PUT /api/subscriptions/products` 只调用了 `collector.apply_selected_products()` 更新实时 WS 订阅，从未触发这三类历史任务，新产品只能从被选中那一刻起被动积累实时推送。(2) 日线（`1D`）回填固定用 300 条/页分页上限，先写入远超 80 根的历史再依赖每小时 retention 清理裁剪，新产品短暂窗口内会有超额行。**修复**：新增 `services/selection_data_runtime.py`（`SelectionDataRuntime`），按 `instId` 独立跟踪每个已选产品的回填/轮询任务集合，`apply_products()` 对比前后差异——新增产品立即 `asyncio.create_task` 启动对应任务（SPOT 只启动 K 线回填，SWAP 额外启动 M25 回填与轮询），移除产品立即取消并释放 REST client；单个产品的回填异常被捕获记警告，不影响其他产品（复用此前 M25 故障隔离的经验）。`api/subscriptions_router.py` 的 `update_selection` 现在同步调用 `get_selection_data_runtime().apply_products()`；`main.py` 启动逻辑改为委托给同一个 runtime 单例，消除了原先"启动时一套逻辑、运行期新增另一套逻辑"的不一致。`services/candle_backfill.py` 的 `_backfill_one` 对 `bar == "1D"` 固定按 80 条请求（其余周期不变）。新增测试：`test_selection_data_runtime.py`（3 项：新 SWAP 产品同时触发三类任务且幂等、移除产品取消对应任务并关闭 REST client、新 SPOT 产品只触发 K 线回填不触发 M25）、`test_subscriptions_router_runtime.py`（1 项：路由层正确委托 runtime）、`test_candle_backfill.py` 新增 1 项（日线精确请求 80 条并存储 80 条）。**真实端到端验证（非模拟）**：选中一个此前在数据库里完全没有任何记录的全新永续产品 `AAVE-USDT-SWAP`，1 秒内 K 线从 0 增长到 172 行（M02+M11 日线各精确 80 根 = 160，其余周期共 12 根）、M25 统计从 0 增长到 10 行；验证后清理测试产生的数据、恢复原选择。全项目 ruff/mypy/pytest **93 passed**（新增 5 项）。需求正文与 `okx-requirements.md` 均未改动（此前"已选且 live 的产品持续采集"的确认需求本就要求新增产品立即开始采集/回填，这是补齐实现缺口，不是需求变更）。 |
| 2026-09-14 | 0.60 | 修复用户反馈"光标悬停一段时间后图表会重新缩小（缩放/平移被重置）"。**根因**：`CandleChart.tsx` 的图表渲染 `useEffect` 依赖 `[bar, chartData]`，而 `chartData` 是 `items` 的派生值；`items` 在 WS 实时推送到达时会通过 `mergeCandle()` 更新（哪怕只是同一根未闭合 K 线的价格微调），导致该 effect 在每次实时推送后都重新执行 `series.setData()` + `chart.timeScale().fitContent()`——`setData()` 是全量替换、`fitContent()` 强制把可见范围重置为"最新一屏"，用户手动缩放/平移后的视图因此被每一次实时推送悄悄清空；用户感知为"悬停一段时间后图表缩小"，实际触发条件是时间流逝导致推送次数增多，与鼠标悬停本身无关（悬停只是让用户视线停留、更容易注意到范围突变）。**修复**：新增 `datasetVersion` 状态，仅在切换产品/`kind`/周期后的**全新数据集**首次到达时递增；`setData()+fitContent()` 的 effect 依赖改为 `[bar, datasetVersion]`（不再依赖 `chartData`），只在真正切换视图时整体重绘并恢复默认范围。新增一个独立 effect 依赖 `[live, bar, datasetVersion]`，对增量到达的单根实时 K 线改用 `series.update()`（Lightweight Charts 官方增量 API，只更新/追加最后一根，不改变当前可见范围），`update()` 因乱序/重连抛出的极少数异常被吞掉、留给下一次完整数据集重新对齐。**真实浏览器验证（非模拟）**：`BTC-USDT` 的 `1s` 图表在滚轮缩放到约 2 分钟窗口后，实测 M01/M03 面板确认真实行情持续变化（价格从 78499.50 变化到 78457.2、M03 出现新成交）的同时，图表可见范围与十字光标位置在 20～25 秒观察窗口内像素级不变；此前的问题在同一操作下必现。`npm test`（3 项）、`tsc --noEmit`、`npm run build` 均通过。需求正文与 `okx-requirements.md` 均未改动（"支持十字光标、缩放、平移"是既有确认需求，这是修复该交互被实时推送破坏的缺陷，不是新功能）。 |
| 2026-09-22 | 0.65 | 用户指令“矫正 S01 和 S05 的时间，该系统的所有时间都应该与 UTC-4，即纽约时间对齐”。核实后确认前端显示层无误，偏差在数据的日线分桶口径：OKX 的 `1D` 是 UTC+8 开盘价口径（`1Dutc` 为 UTC+0），库中 S01／S05／S04 的 `1D` 与 M02／M11 的 `1D` 时间戳全部落在 UTC 16:00 即纽约中午。用户选择“后端按纽约自然日重采样”并覆盖全系统所有 `1D`。实现：新增 `services/ny_day.py`／`services/ny_day_candles.py`，K 线与 M25 的日线一律改为请求官方 `1H` 后按 `America/New_York` 自然日重采样（K 线 OHLC 聚合、S01／S05／S09 取日界读数、S04 按日求和），WS 订阅由 `candle1D`／`mark-price-candle1D` 改为 `candle1H`／`mark-price-candle1H`，`1H` 作为不对外的派生源保留 80 个自然日，`1D` 轮询改为每小时回看 48 根，迁移 `a4c71e2f0b35` 清除旧 UTC+8 口径日线行。真实数据验证：重建后 640 行日线全部落在纽约 00:00、0 行错位。ruff／mypy／pytest 113 passed，前端 18 项测试与构建通过。需求正文更新为 0.45 |
| 2026-09-22 | 0.66 | 用户指令“去掉前后端关于 M12/M14/M15/S09/S10/S11 的实现”，属范围收缩。后端退订 `funding-rate`／`price-limit`／`estimated-price` 并删除对应落库方法、hub 频道、三个 REST 方法（loan-ratio／funding-rate-history／premium-history）、S09/S10/S11 的回填与轮询、`backfill_dict_metric`、`ccy_from_uly`／`_resolve_ccy_set`（M25 不再需要 `uly`→`ccy` 派生，全部指标改以永续 instId 查询）、保留清理条目与三个 ORM 模型；`M25Metric` 收窄为 S01/S04/S05。迁移 `c93b5ad10e77` 删除 S09/S10/S11 历史行、收窄 MySQL ENUM、drop `m12_funding_rates`／`m14_price_limits`／`m15_estimated_prices`。前端删除三个数据类型、三个 channel 状态、三张快照卡片、S09 图表与 S10/S11 表格及失效样式。测试删除专属用例，故障隔离回归改用 S05 失败场景，采集器与 hub 改为反向断言。真实数据库验证：三表已删、ENUM 实测收窄、21735 行被移除指标数据清除。ruff／mypy／pytest 110 passed，前端 18 项测试与构建通过。需求正文更新为 0.46，新增「已移除的能力」小节 |
| 2026-09-22 | 0.67 | 修复 K 线共用链路：独立回填重试与近期校对、历史和实时缓存隔离、闭合版本防回退、前端历史重新同步及报价精度、纽约日线完整性和 DST 重复时间去重。四个股票永续的成交价／标记价抽查窗口缺口与未闭合旧线均归零；后端 120、前端单元 22、浏览器 16 项通过（含各蜡烛周期像素高度核对）。需求仍为 0.46，补录局部验证；未登录真实用户浏览器、不伪造市场跳空。 |
| 2026-09-22 | 0.68 | 用户指令“去掉M11的前后端实现。将S04的展示位置上移，使与M01在同一行”。移除 M11（标记价格 K 线）：后端删除频道订阅／回填方法／`candle:mark:*` 实时频道，`candles.kind` 的 MySQL ENUM 收窄为仅 `trade`（新迁移 `ad4f1b5392f5`）；前端删除 `MarkPriceChart` 及相关 `kind='mark'` 分支。顺带补齐上一轮 M16 移除遗漏的删表迁移（`m16_risk_events` 曾是孤儿表，新迁移 `75fd54ac1bfe`）及需求正文中残留的“M16 在用”表述。S04 从 `M25Panel` 拆出为独立 `S04Chart`（自带周期选择器），移至 `product-panel-row` 与 `TickerCard`（M01）同一行；`M25Panel` 本体只剩 S01／S05。顺带修复 0.66 遗留的前端测试回归：`detailDisplay.test.ts` 断言的 M16 字段标签早被清空却未重新跑测试；核实 `DetailFields.tsx` 组件的唯一调用方是已删除的 `RiskEventsPanel.tsx`，一并删除该孤儿组件。ruff／mypy／pytest 110 passed，前端单元 22、浏览器 14 项通过，构建通过；未针对远程 MySQL 执行迁移、未登录真实浏览器验收（本环境无远程数据库／Redis／OKX 凭证）。需求正文更新为 0.47，「已移除的能力」新增 M11／M16 两行。 |
