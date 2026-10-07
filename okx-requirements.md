# OKX 项目需求文档

版本：0.54 · 更新日期：2026-10-07

本文记录已确认要实现的功能及对应接口依据。讨论进度、待定事项、下一步和未确认设计统一记录在 [HANDOFF.md](HANDOFF.md)。当前是已确认需求的阶段性结果，尚非完整实施规格；后续确认的结果持续补入本文。

## 1. 接口依据

使用全局 **`okx-v5-api`**：[Skill 入口](/Users/lazycatnewton/.codex/skills/okx-v5-api/SKILL.md)。本文中的文档路径相对该 Skill 安装目录。

当前引用快照：版本 `0.2.0`，生成时间 `2026-08-27T11:03:09+00:00`，核验日期 `2026-09-10`，站点 `okex`，语言 `zh`。接口事实依据 Skill 正文，需求中的 M／S 编号用于项目内标识。

<a id="req-001"></a>
## 2. REQ-001：行情连接服务

建立行情连接服务，向前端展示和后台策略／分析两类消费者提供行情数据。

| 项目 | 已确认要求 |
| --- | --- |
| 账户地区 | 全球站 `okex` |
| 行情环境 | 实盘；不需要模拟盘 |
| 产品范围 | 现货、永续合约；产品自动发现后由用户选择订阅 |
| 消费者 | 前端展示与后台策略／分析，两者均支持 |
| 历史保存 | 保存 7 天 |
| 辅助市场 | 接入 M22 事件合约市场数据、共享 M23 经济日历 |
| 前端载体 | Web（桌面与手机浏览器响应式兼容，2026-09-25 起）；单人自用 |
| 系统组成 | 后端服务（Python）、持久化数据库（MySQL 8.0+，远程非本机）、Redis 缓存 |

当前功能范围：

- 现货独立行情：M01、M02、M03、M05。
- 永续独立行情：M01、M02、M03、M05、M10、M13、M25。M11、M12、M14、M15、M16 已由用户指令移除（见第 2 节「已移除的能力」）。
- 共享辅助数据：M22 事件合约市场数据、M23 经济日历，供两类消费者使用，不扩展现货／永续交易产品范围。
- M06 暂时移出本期；本期不接入高阶深度。

### 产品发现与订阅选择

服务分别调用 `GET /api/v5/public/instruments?instType=SPOT` 与 `GET /api/v5/public/instruments?instType=SWAP` 自动发现全球站实盘可返回的现货和永续产品。接口按 `IP + Instrument Type` 限速为 20 次／2 秒。

发现结果用于向用户展示可选产品：现货至少展示 `instId`、`baseCcy`、`quoteCcy`、`state`；永续至少展示 `instId`、`instFamily`、`settleCcy`、`ctType`、`state`。只有用户选中的 `instId` 才进入本期 M01～M16 与 M25 的适用订阅／查询集合；自动发现本身不建立行情订阅，也不自动扩大产品范围。产品状态及可选范围以该次接口返回为准。

产品选择器可按 `instId` 搜索，并按产品类型和 `state` 筛选。所有接口返回状态均可见；只有 `state=live` 的产品可选择，其余状态显示为不可选择。已选择产品变为非 `live` 时，永久选择配置保留、对应 Tab 自动关闭；其后恢复为 `live` 时，Tab 自动恢复。

产品发现的接口依据：`docs/okex/zh/api/rest/public/instruments.md`，全球站 REST 基地址为 `https://www.okx.com`。接口参数、返回字段和限速以该正文为准。

### 前端形态与使用范围

#### 产品导航侧边栏（替代顶部横向产品导航）

- 主面板使用浏览器窗口全宽，取消固定宽度、居中留白及两侧边框；顶部保留紧凑标题／账户／市场日历工具栏，主面板占剩余高度并纵向滚动，保留适度内边距及全部数据面板，不进入浏览器全屏模式。
- 已选产品放入左侧覆盖式抽屉，默认收起；入口改为视口最左侧垂直居中的“›”箭头，展开后随抽屉移动到右边缘并变为“‹”，点击收起。移除头部“☰ 产品”按钮，保留抽屉内部关闭按钮。不挤压图表宽度，可与右侧市场／日历栏同时展开，产品选择弹窗位于两栏及箭头上方。
- 产品列表独立纵向滚动；底部固定圆角“+”按钮，不随列表滚动，打开现有产品选择窗口，保留搜索、类型切换、多选与保存操作。
- 点击产品名称切换当前图表，侧边栏保持展开。每行产品名称左侧提供“×”取消选择按钮，操作前使用原生确认框。
- 确认取消选择后永久更新选择配置，停止该产品订阅与采集／回填任务，不关闭其他产品共享的 WebSocket；重新打开页面不再显示该产品。取消操作不删除历史数据，原有滚动保留规则继续有效。
- 删除当前产品时，按原列表顺序优先激活下一项，无下一项则激活上一项，全部删除后显示空白提示；删除非当前产品不切换图表。
- 删除失败时保留原列表与当前图表，并显示失败原因；提交期间阻止重复删除及新增选择操作，避免覆盖选择配置。

本期前端为 Web 界面，桌面浏览器为主要形态；**用户于 2026-09-25 指令「开始做移动端兼容」**，撤回原“不适配移动页面”，改为同一套页面在手机浏览器上响应式可用（不做原生 App），规则见下方「移动端兼容」。前端技术栈固定为 React、TypeScript 与 Vite。服务面向单一使用者，不包含多用户账户、用户间的数据隔离、共享订阅配置或角色权限管理。**用户已于 2026-09-22 指令「去掉登录系统的前后端实现」**：不再有登录认证，浏览器直接访问本产品后端的全部 HTTP／WebSocket 接口；访问控制（若需要）留给部署层（网络边界、反向代理等），不在本产品应用层实现，详见「已移除的能力」。

产品选择与订阅配置属于单例永久全局配置：关闭浏览器、刷新页面均不改变配置；用户主动修改时更新当前有效配置并永久保留版本记录。前端具体页面、展示布局、历史数据查看方式和状态呈现也将在后续确认后补充。

### 移动端兼容

同一套 React 页面，以 640px 为手机断点响应式适配，不另做移动专用页面或原生 App。已验收设备宽度 320／360／390px（iPhone SE、Galaxy S8、iPhone 13 模拟），要求：

- 页面不出现横向滚动；所有产品面板在手机上单列堆叠，面板内容（成交列表、缠论背驰点等行）不折行错位。
- 页面高度按手机浏览器可见视口计算（`100dvh`），底部内容不被地址栏遮挡。
- 已选产品抽屉：入口“›”箭头在手机上缩小并移到左下角，不压住 K 线图；抽屉宽度不超过屏宽 80%，展开时显示半透明遮罩，点击遮罩收起。桌面行为不变。
- 市场／日历侧边栏宽度不超过屏宽，并位于产品抽屉入口箭头之上。
- 图表触控：手指在 K 线图、M25 图上纵向滑动时滚动页面，横向拖动仍平移图表；K 线提示文案在触屏设备显示“触摸图表查看 OHLC”，有鼠标的设备仍为“移动光标查看 OHLC”。
- 输入框与下拉框在手机上字号为 16px，避免 iOS 聚焦时自动放大页面。

### 数据视图与产品面板

桌面 Web 中每一个 Tab 对应一个由用户选择的 OKX 产品。一个产品 Tab 内同时展示该产品的 K 线视图及其对应的其他数据面板；K 线不是独立 Tab。现货和永续的面板只能展示当前 Tab 对应产品的数据，不得混合不同产品。

第一版中，每个产品 Tab 展示该产品适用的**全部已选数据面板**：现货展示其适用的 M01、M02、M05；永续展示其适用的 M01、M02、M05、M10、M13、M25。第一版不对这些面板做取舍或隐藏；面板清单、布局和交互的修改留待第一版完成后迭代。M25 面板内按 S01、S04、S05 的顺序排列，三者共用面板的周期选择；S04 以买入量、卖出量两条折线展示，紧接在 S01 之后（用户指令 2026-10-07，取代此前“S04 与 M01 同一行”的位置）。三项图表均加载所选周期的全部已保存数据。

M22 预测市场和 M23 经济日历不归属任何单一产品 Tab，而是在桌面 Web 中以一个独立的全局侧边栏展示，供所有产品 Tab 共享。

产品选择发生后立即创建对应产品 Tab；取消选择产品后立即关闭对应 Tab。首次打开且尚未选择任何产品时，主区域显示空白视图。产品选择与 Tab 的创建、关闭同步更新单例永久全局订阅配置。后续打开按保存的选择顺序恢复全部当前 `live` 产品 Tab，并激活上次活动 Tab；不存在上次活动记录时激活首个已选产品。

产品 Tab 采用组合展示：M01、M10、M13 使用行情概览数值卡片；M02 和 M25 使用图表配合明细数据；M03 使用按时间倒序追加的最新成交（time & sales）列表；M05 使用五档盘口表格。每个面板先展示用于判断的核心字段，并提供结构化详情展开；不直接展示原始 JSON。K 线默认打开 `5m` 周期，并默认显示最近 2 小时；`1s`、`1m`、`5m`、`15m`、`30m` 均默认最近 2 小时，`1D` 默认最近 7 天。`1s` 以折线图展示，其余交易价格 K 线使用蜡烛图。图表采用 TradingView Lightweight Charts（HTML5 Canvas），支持十字光标、缩放、平移、价格与时间刻度；不实现画线工具、技术指标、多副图或 TradingView 账户功能。用户可在同一产品 Tab 中切换该产品已选的全部 K 线周期。M25 各统计指标独立选择其已确认周期，默认选择可用的 `5m`。具体视觉布局在第一版完成后迭代。

M22 与 M23 侧边栏中的数据均按时间倒序展示：M22 按 `expTime` 倒序，M23 按 `date` 倒序。初始加载最新一页，用户点击“加载更多”后再取得更早一页；第一版不提供侧边栏搜索或筛选。各条目可展开结构化详情。数据缺口、断线窗口和首次启动前缺失数据不在前端标注；服务端仍不得伪造或填补缺失数据。

#### M02 K 线的缠论（缠中说禅）结构叠加层

M02（成交价）K 线图叠加缠论结构分析：中枢矩形、笔连线、分型点、背离／背驰点标记。分型／笔／中枢／背离算法移植自全局 Skill `/Users/lazycatnewton/development-repo/skills/chan`（`scripts/chan_core.py`）；本期不移植该 Skill 的买卖点（1B/2B/3B 等）判定，留待后续更大的技术分析功能一并规划。

- 计算位置：前端浏览器内计算（TypeScript 移植版，`frontend/src/chan.ts`），不新增后端接口或持久化；K 线数据已在客户端、数据量小，无需网络往返。已用相同数据集对照 Python 原始实现验证 TS 移植结果逐字段一致（分型、笔、中枢、背离全部相同）。
- 适用周期：M02 排除 `1s`、`1m`，即 `5m`／`15m`／`30m`／`1D` 均启用。
- 参与计算的数据：只使用已闭合 K 线（`confirm=1`）；最新未闭合的一根仅在蜡烛图/折线图上正常显示，不参与分型/笔/中枢计算，避免结构随实时推送抖动、事后撤销重画。
- 视觉元素：中枢矩形（半透明色块，覆盖中枢起止时间、上下沿为 ZG/ZD；上沿标注 `ZG + 价格`、下沿标注 `ZD + 价格`）、笔连线（连接各分型点的折线，中性色，不与蜡烛图涨跌色冲突）、分型点（顶/底分型三角标记）、背离/背驰点（背驰 BC-B/BC-S 用醒目色实心标记，背离 DIV-B/DIV-S 用同色系较淡样式区分强度）。
- 光标数据：光标移动到某一根 K 线时，在图表标题下方展示该根 K 线的收盘价、开盘价、最高价和最低价；沿用后端返回的原始十进制字符串，不经浮点格式化丢失精度。
- 数据不足时（已闭合 K 线太少、无法形成满足"至少 3 笔重叠"的中枢）：不显示任何中枢/笔，前端提示"当前数据暂不足以形成缠论中枢（数据事实，非缺陷）"，不为凑出结果而扩大拉取范围或做特殊处理。

#### A1:CHAN 缠论结构面板

用户于 2026-09-25 确认：在 M02 K 线图下方新增文字面板 **A1:CHAN**，把当前所选周期的缠论结果按时间倒序展示。面板与 K 线图共用同一份已闭合 K 线数据和周期状态，用户点击 K 线周期按钮时面板即时切换，不单独请求后端、不新增持久化；计算口径与上方叠加层完全一致（只用 `confirm=1` 的 K 线，`1s`／`1m` 不计算并给出提示）。

- 概览：样本起止时间与已闭合 K 线数；中枢数、笔数、顶／底分型数、背驰（BC）数、背离（DIV）数。
- 当前状态：最新一笔的方向、起止价格、涨跌幅与结束时间；最新收盘价相对最新中枢的位置（ZG 上方／中枢内部／ZD 下方）。
- 中枢列表（最新在前）：编号、起止时间、持续时长、K 线数与所含笔数、ZD–ZG 区间与振幅、DD／GG 极值、本段背驰与背离个数，以及本段内每一个具体背驰／背离点（时间倒序，含发生时间、代码 BC-S／BC-B／DIV-S／DIV-B、中文类型与价格）。“本段”指该中枢起点到下一中枢起点之前（最新中枢则到最后一根已闭合 K 线），即中枢本身加离开段。首个中枢形成之前出现的背驰／背离点不属于任何中枢段，单独列在最后的“首个中枢之前”条目中，保证每个点都被展示且与概览计数一致。
- 用户于 2026-09-25 撤回了独立的“背驰／背离时间线”和“笔列表”两块，背驰／背离点改为归入各自中枢展示；概览中的笔数与“最新一笔”状态行保留。
- 时间按美东 ET 显示，`1D` 只显示日期；价格按该周期 K 线原始报价精度显示。历史尚未加载完成时显示“加载中”，不因先到的单根实时 K 线误报数据不足。

浏览器仅调用本产品后端：HTTP 用于产品选择、目录和历史数据，后端 WebSocket 用于实时快照与更新；浏览器不得直接连接 OKX、数据库或 Redis。浏览器打开实时连接后，以 `activate-product`／`deactivate-product` 消息声明当前需要实时展示的产品；产品选择、取消选择仍通过 HTTP 持久化。实时连接断开重连后，后端先发送当前有效快照，再继续推送更新。普通行情暂时不可用时，后端优先下发 Redis 中最后一份有效快照；没有缓存则返回空面板，且前端不标注缺口。

已选择且仍为 `live` 的产品必须持续采集其全部已选行情，即使 Tab 未激活、浏览器关闭或用户退出。`activate-product`／`deactivate-product` 只决定当前浏览器接收哪些产品的实时分发，不能改变 OKX 上游订阅、后台 M25 采集或 7 天保存范围。

### 已确定的系统组成

本产品包含 Python 后端服务、持久化数据库和 Redis 缓存。持久化数据库确定为 **MySQL 8.0 及以上**，且不部署在本机开发环境（远程实例）；具体主机、拓扑、单／多实例仍待后续确定。永久目录、用户账户、订阅配置、7 天历史数据及版本记录由持久化数据库保存；Redis 仅作为可重建的缓存，用于当前连接状态、最新行情／五档盘口和其他需要快速读取的最新状态。Redis 不作为永久配置或 7 天历史数据的唯一来源。服务启动及用户打开产品选择器时刷新现货／永续产品目录；M22 目录在服务启动时通过 REST 初始化，并持续消费 WS 更新。

行情后端允许使用第三方 SDK `python-okx`（PyPI: https://pypi.org/project/python-okx，源码 https://github.com/okxapi/python-okx）承担部分 OKX REST／WebSocket 调用的传输、签名与重连封装；SDK 是否覆盖某个接口、频道或参数以其当前版本实际支持为准，不能假定其自动满足本文档确认的频道选择、参数、限速、去重存储、7 天保留或首次启动回填等要求——这些要求仍需在业务代码中显式实现和核验，接口事实依据仍以 `okx-v5-api` Skill 正文为准，SDK 文档不替代该核验。

后台策略／分析通过仅在同一后端部署环境内开放的内部 HTTP 与内部 WebSocket 消费数据，不向浏览器或外部网络暴露。策略组件显式声明所需 `instId`、频道和指标；声明只改变内部数据分发，不改变已选产品的持续采集集合。内部 HTTP 用于目录和 7 天历史，内部 WebSocket 用于实时快照和更新。

未来策略／研究组件可独立进程运行，只作为上述内部消费者，通过内部 HTTP／WebSocket 接口获取数据，不直接连接 OKX 上游；Python 行情后端仍是唯一负责 OKX 连接、采集、缓存、持久化和对浏览器分发的服务。

| 项目 | 已确认规则及接口映射 |
| --- | --- |
| M01 | 现货／永续分别订阅 `tickers` |
| M02 | 现货／永续均选择 `1s`、`1m`、`5m`、`15m`、`30m`、`1D`；`1s`～`30m` 对应 `candle1s`、`candle1m`、`candle5m`、`candle15m`、`candle30m`，使用 business WS。`1D` **不订阅 OKX 的 `candle1D`**（它是 UTC+8 开盘价口径），改为订阅 `candle1H` 并在后端按纽约自然日聚合，见下方「日线口径」 |
| M03 | 现货／永续分别订阅 `trades`，使用 public WS；有成交即接收并向活动产品 Tab 实时转发。每条上游推送可能聚合多笔同价、同来源成交，按 `instId + tradeId` 去重。 |
| M05 | 已确认五档，现货与永续分别订阅 `books5`，使用 public WS；收到快照后覆盖对应产品的五档盘口 |
| M06 | 暂时移除，不订阅高阶深度 |
| M10、M13 | 按永续适用正文接入 |
| M11、M12、M14、M15、M16 | 已由用户指令移除，不订阅 `mark-price-candle{bar}`、`funding-rate`、`price-limit`、`estimated-price`、`liquidation-orders`、`adl-warning` |
| M22 | 确认接入独立辅助市场数据 `event-contract-markets`；按该频道自己的市场标识过滤，不传入普通现货或永续产品冒充事件合约 |
| M23 | 确认共享一份经济日历；需要 business WS 登录。未配置凭证、鉴权失败、网络故障或账户不满足 VIP1 时，应用均返回空数据集；不影响其他行情连接 |
| M25 | 继续保留统计与历史查询；其中 K 线历史按所选成交／标记 K 线周期分别映射。多空比、持仓量等统计不是 K 线，必须逐接口核验 period 或查询窗口；已选 S01、S04、S05（S09、S10、S11 已由用户指令移除）；统计周期已按下方配置确认，与 K 线周期分别管理 |

M23 的空数据是本应用的统一前端输出行为：未配置凭证、鉴权失败、网络故障或账户不满足 VIP1 时均返回空数据集，不暴露错误详情。M23 所需 OKX API 凭证仅可由服务端安全配置提供，第一版不提供 Web 管理入口。经济日历在现货与永续消费者之间共享；该规则只适用于 M23，不改变其他行情频道的状态或错误行为。

M02 维护周期配置。日线对外仍使用 `1D` 标识。

### 已移除的能力

用户于 2026-09-22 指令「去掉前后端关于 M12/M14/M15/S09/S10/S11 的实现」。这些能力此前已确认并交付，现整体退出本期范围：前后端代码、WS 订阅、REST 调用、轮询、保留清理与数据表全部移除，编号本身按编号稳定原则保留、不回收也不复用。

| 编号 | 原能力 | 原接入方式 | 移除范围 |
| --- | --- | --- | --- |
| M12 | 资金费率 | public WS `funding-rate` | 频道订阅、`m12_funding_rates` 表、前端资金费率卡片 |
| M14 | 价格限制 | public WS `price-limit` | 频道订阅、`m14_price_limits` 表、前端价格限制卡片 |
| M15 | 预估价格 | public WS `estimated-price` | 频道订阅、`m15_estimated_prices` 表、前端预估价格卡片 |
| S09 | 杠杆多空比 | `GET /api/v5/rubik/stat/margin/loan-ratio` | REST 方法、回填与轮询、`uly`→`ccy` 派生、前端 S09 图表与周期选择 |
| S10 | 历史资金费率 | `GET /api/v5/public/funding-rate-history` | REST 方法、回填与 5 分钟轮询、前端历史表格 |
| S11 | 溢价指数历史 | `GET /api/v5/public/premium-history` | REST 方法、回填与 5 分钟轮询、前端历史表格 |

`m25_stats.metric` 的取值范围同步收窄为 `S01/S04/S05`，S09／S10／S11 的历史行随迁移删除。随之失效的派生规则一并移除：M25 不再需要由永续 `uly` 推导关联币种 `ccy`（那是 S09 独有的查询维度），M25 全部指标现在都以永续 `instId` 为查询维度。

用户于 2026-09-22 另指令「去掉M16的前后端相关功能」「去掉M11的前后端实现」。移除范围与上述同类：

| 编号 | 原能力 | 原接入方式 | 移除范围 |
| --- | --- | --- | --- |
| M16 | 强平订单／ADL 预警 | public WS `liquidation-orders`、`adl-warning` | 频道订阅、`RiskEvent` 模型／`m16_risk_events` 表、`GET /api/market/{instId}/risk-events`、`risk-events` 实时频道、前端 `RiskEventsPanel` 及其展开详情组件 `DetailFields` |
| M11 | 标记价格 K 线 | business WS `mark-price-candle{bar}` | 频道订阅、`candles.kind='mark'`（ENUM 收窄为仅 `trade`）、`GET /api/v5/market/history-mark-price-candles` 回填方法、`candle:mark:*` 实时频道、前端标记价格图表组件 |

`candles.kind` 的 MySQL ENUM 同步从 `('trade','mark')` 收窄为 `('trade')`，`kind='mark'` 的历史行随迁移删除。`m16_risk_events` 表随迁移一并删除（该表在此前一轮 M16 应用代码移除时遗漏，本次补齐）。

用户于 2026-09-22 另指令「去掉登录系统的前后端实现」。这不是某个编号能力，而是 REQ-001「前端形态与使用范围」原先确认的用户名密码登录、会话 Cookie、登录失败冻结整体退出：前端登录页、后端登录/会话/密码哈希代码、`users` 表全部移除；浏览器与所有 HTTP／WebSocket 接口之间不再有鉴权层。产品选择与偏好（原按 `user_id` 归属唯一用户）收窄为单例全局配置，不再有“用户”概念；`M25UnitPreference`（S04 单位偏好）此前已是按 `instId` 的全局配置，不受影响。移除范围：

| 项目 | 原实现 | 移除范围 |
| --- | --- | --- |
| 登录/会话 | `POST /api/session/login`、`DELETE /api/session`，Redis 存会话状态，`argon2` 密码哈希 | `auth_router.py`、`auth/session.py`、`security.py`、`api/deps.py`（`get_current_session` 依赖）、前端 `LoginScreen.tsx`、`api.ts` 的 `login()`/`logout()`、所有路由的会话依赖注入 |
| 账户数据 | `users` 表（唯一使用者账户，含密码哈希） | 整表删除（该表从未有过真正的账户创建入口，控制台创建流程本就在本期范围外） |
| 用户归属数据 | `user_preferences`／`subscription_config_versions` 按 `user_id` 归属 | `user_preferences` 重构为单例 `app_preferences`（固定单行）；`subscription_config_versions` 删除 `user_id` 列，收窄为单例全局配置 |

### 日线口径：纽约自然日

本产品所有时间统一与纽约时间（IANA `America/New_York`，自动应用 EST／EDT）对齐，日粒度也必须按纽约自然日划分。OKX 只提供两种日粒度口径：`1D` 是 **UTC+8 开盘价 K 线**、`1Dutc` 是 **UTC+0 开盘价 K 线**（见 `docs/okex/zh/api/rest/market/historyCandles.md`、`docs/okex/zh/api/rest/tradingData/longShortAccountRatioContract.md`、`openInestVolumeHistory.md`、`contractTakerVolume.md` 的 `bar`／`period` 参数说明），两者都不是纽约自然日——OKX 的 `1D` 日界落在纽约时间中午。

因此所有日粒度序列一律改为：向 OKX 请求官方 `1H` 粒度，由后端按纽约自然日重采样为 `1D`。纽约 00:00 在 EDT／EST 下分别对应 UTC 04:00／05:00，都落在整点上，`1H` 足以精确对齐日界；夏令时切换当天的自然日分别为 23 小时和 25 小时，由时区库处理，不使用固定偏移。

| 序列 | 纽约自然日取值规则 |
| --- | --- |
| M02 K 线 | `o` 取当日首根 1H 开盘，`h`／`l` 取当日极值，`c` 取当日末根 1H 收盘，`vol`／`volCcy`／`volCcyQuote` 按日求和；当日未结束时 `confirm=0` |
| M25 S01、S05 | 比值／持仓量属于时点快照，不可求和，取纽约当日 00:00 那一根 1H 的官方读数 |
| M25 S04 | 主动买入／卖出量是区间累计量，按纽约自然日求和；当日未结束时为截至当前的累计值，随后续采集覆盖 |

派生出的 `1D` 行在 M25 的 payload 中附带 `srcPeriod`（固定 `1H`）与 `srcTs`／`srcHours`，标注其官方来源，保持可追溯。若某个纽约自然日的源数据未覆盖到日界那一根，该日不写入残缺值，等覆盖完整后再写。`1H` 源数据本身作为派生源保存，保留窗口覆盖需要展示的 80 个纽约自然日，不作为对外可选周期。

### 面板字段与展示映射

下表定义第一版的核心字段和可展开详情。除特别说明外，核心字段来自对应 WS 最新消息；详情使用同一条已保存消息或历史序列，不额外暴露原始 JSON。时间字段以 OKX 毫秒时间戳保存和传递；产品界面统一按美国东部时间 ET（IANA `America/New_York`，自动应用 EST／EDT 夏令时切换）格式化显示，图表时间轴标识 `ET`。数据库、API 与 WebSocket 的原始业务时间戳仍保持 UTC 毫秒值，不因展示时区改变。

| 面板 | 核心字段 | 展开详情 | 数据来源 |
| --- | --- | --- | --- |
| M01 ticker | `last`、`bidPx`、`askPx`、`high24h`、`low24h`、`vol24h`、`ts` | `lastSz`、`bidSz`、`askSz`、`open24h`、`volCcy24h`、`sodUtc0`、`sodUtc8`、`instType`、`instId` | public WS `tickers`，订阅参数 `channel=tickers, instId` |
| M02 成交价 K 线 | `ts,o,h,l,c,vol,confirm` | `volCcy`、`volCcyQuote`、`bar`、`instId` | business WS `candle{bar}`；历史为 `GET /api/v5/market/history-candles?instId&bar&before|after&limit&adjust=forward` |
| M03 最新成交 | `ts`、`side`、`px`、`sz`、`count` | `tradeId`、`source`、`seqId`、`instId` | public WS `trades`，订阅参数 `channel=trades, instId` |
| M05 五档盘口 | 五档 `bids`、`asks` 中各档的价格和数量、`ts` | 每档订单数量（数组第 4 项）、`instId`、频道名 | public WS `books5`，订阅参数 `channel=books5, instId`；每条消息是完整五档快照 |
| M10 标记价格 | `markPx`、`ts` | `instId`、`instType` | public WS `mark-price`，订阅参数 `channel=mark-price, instId` |
| M13 持仓总量 | `oi`、`oiCcy`、`oiUsd`、`ts` | `instId`、`instType` | public WS `open-interest`，订阅参数 `channel=open-interest, instId` |
| M25 S01 | `ts`、`longShortAcctRatio` | `instId`、`period` | `GET /api/v5/rubik/stat/contracts/long-short-account-ratio-contract?instId&period&begin|end&limit` |
| M25 S04 | `ts`、`buyVol`、`sellVol` | `instId`、`period`、返回使用的 `unit` | `GET /api/v5/rubik/stat/taker-volume-contract?instId&period&unit&begin|end&limit` |
| M25 S05 | `ts`、`oi`、`oiCcy`、`oiUsd` | `instId`、`period` | `GET /api/v5/rubik/stat/contracts/open-interest-history?instId&period&begin|end&limit` |

M25 的 `begin`／`end` 使用各指标返回的 `ts`。每个 Tab 仅显示其 `instId` 对应的已选 M 能力与 S01／S04／S05。S04 在面板内提供单位选择器：`0`（币）、`1`（合约）、`2`（U）；首次打开默认 `1`（合约），并永久保存每个产品最近一次选择。单位是查询维度的一部分，切换后以新 `unit` 调用接口、独立保存和展示，不在前端对既有数据换算。后台对三个 `unit` 持续独立采集、保存并在首次启动时分别尽量回填官方可提供的全部历史（窗口见「保存、保留与首次启动回填」中的 M25 行）。

启动回填之后，S01／S04／S05 在各已选周期结束后请求对应周期；`1D` 因为请求的是官方 `1H`，改为每小时请求一次并回看最近 48 根 1H，持续修正当天尚未结束的日线。M25 短暂请求失败时保留最近有效数据，下一个计划周期重试，不伪造新记录。M22 持续以 WS 为实时来源，并每小时以 REST 完整校正目录；M23 持续以已登录 WS 为实时来源，并每 30 分钟以 REST 补充，且必须遵守每 IP 1 次／5 秒限速。上述 REST 请求失败时保留最近有效数据。

### 保存、保留与首次启动回填

产品目录和订阅目录永久保存，不受历史保留期清理。M01、M03、M05、M10、M13 暂不持久化（见下表）；除这些对象及 M02 K 线的下列特例外，其他数据采用滚动 7×24 小时保留：以 OKX 的业务时间戳作为过期依据；没有业务时间戳的记录以服务接收时间为准。到期后删除数据正文及原始载荷。所有存储记录额外保留 `site=okex`、`environment=production`、`receivedAt`；价格、数量、比率和成交量按原始十进制字符串保存，不转为浮点数。

| 保存对象 | 保存期限 | 具体形式 |
| --- | --- | --- |
| 产品目录（现货／永续） | 永久 | 按 `instType + instId` 保存当前基础信息；每次发现结果中同一产品的基础字段或 `state` 变化时追加永久版本记录，不物理删除已下线产品。 |
| 订阅目录 | 永久 | 按产品选择、频道、周期与适用范围保存用户配置；启用、停用或参数变更追加版本记录，当前有效配置单独标记，历史配置不删除。 |
| M01 ticker | 暂不持久化 | 用户指令（2026-10-07）暂停写入 MySQL；仅在 Redis 保留每个 `instId` 的最新一条 ticker，用于浏览器实时快照与更新。恢复持久化须由用户另行确认。 |
| M02 成交价 K 线 | `1D`（纽约自然日）最新 80 根；`1m`／`5m`／`15m`／`30m` 最近 10×24 小时；`1s` 7 天；`1H` 作为日线派生源保留最近 80 个纽约自然日 | 按 `instId + bar + ts` 去重的 OHLCV 时间序列；同一根未完结 K 线以较新的推送覆盖，`confirm=1` 后保留已闭合版本。 |
| M03 最新成交 | 暂不持久化 | 用户指令（2026-10-07）暂停写入 MySQL；仅在 Redis 保留每个 `instId` 按 `tradeId` 去重的最近 100 笔成交，用于浏览器实时快照与更新。恢复持久化须由用户另行确认。 |
| M05 五档盘口 | 暂不持久化 | 用户指令（2026-10-07）暂停写入 MySQL；仅在 Redis 保留每个 `instId` 的最新一份 `books5` 快照。恢复持久化须由用户另行确认。 |
| M10 标记价格 | 暂不持久化 | 用户指令（2026-10-07）暂停写入 MySQL；仅在 Redis 保留每个永续 `instId` 的最新标记价格。恢复持久化须由用户另行确认。 |
| M13 持仓总量 | 暂不持久化 | 用户指令（2026-10-07）暂停写入 MySQL；仅在 Redis 保留每个永续 `instId` 的最新 `oi`／`oiCcy`／`oiUsd`。恢复持久化须由用户另行确认。 |
| M22 预测市场目录与更新 | 目录永久；更新 7 天 | 系列、事件和市场的当前目录及字段版本永久保存；WS 市场状态／行权区间更新按 `instId + 业务时间 + payload 哈希` 追加为 7 天修订事件。 |
| M23 经济日历 | 7 天 | 追加式修订事件日志，保存 `calendarId`、`date`、`ts`、经济字段及原始 payload；按 `calendarId + ts` 去重，使同一经济事件的后续修正可保留。 |
| M25 S01／S04／S05 | 官方每个粒度最多可取的最近 1,440 条：`5m` 5 天、`15m` 15 天；`1D` 由 1,440 根 `1H` 派生，保留最近 58 个纽约自然日（含当天） | 按“指标编号 + 永续 `instId` + `period` + `unit`（仅 S04 适用）+ 官方时间戳”去重的时间序列，保存该指标的所有官方返回值及查询来源。 |

7 天数据按滚动截止时间清理；K 线按照本表的 80 根／10×24 小时／7 天例外清理；产品目录、订阅目录及 M22 当前目录／版本不参与此清理。服务必须能区分“历史数据不存在”与“历史已被保留规则清理”，不以空数据填补缺口。

首次启动采用混合回填：先恢复永久目录与订阅配置，再刷新现货／永续产品目录及 M22 全量系列、事件、市场目录；随后建立 WS 订阅并立即开始保存实时数据。历史回填在后台执行，不阻塞实时采集或前端可用性。对于可用的历史接口，以分页方式回填至已确认的最低保留量：M02 的 `1D` 通过回填官方 `1H` 至第 80 个纽约自然日 00:00、再重采样得到 80 根日线；`1m`／`5m`／`15m`／`30m` 回填最近 10×24 小时，`1s` 尽量回填最近 7 天。若官方可用历史不足目标，保存可获取的全部历史，不伪造、聚合或插值。

M02 的历史回填请求统一附带 `adjust=forward`：该参数仅对股票永续合约生效，返回前复权 OHLC（拆股等公司行为发生前的历史价格按当前股本尺度换算），成交量同比例调整、成交额不调整；对其余产品该参数无实际影响，因此可以统一附带而不需要按产品类型分支。实时逐笔成交（M03）、Ticker（M01）、五档盘口（M05）、标记价格快照（M10）均为当期状态，不涉及历史复权问题。

其他可回填对象仍以分页方式尽量回填最近 7 天：

- M02 使用 `GET /api/v5/market/history-candles`，按产品和已选 `bar` 分页回填；
- M25 逐项调用已选的 S01、S04、S05 历史／统计接口，按各接口的时间游标和页面限制回填；M25 的回填窗口不是 7 天，而是官方 1,440 条上限（见 M25 补充数据一节）。

无法从本期已选接口回填的实时快照、风险事件、M22 更新和 M23 数据，从首次成功接收对应 WS 数据起积累；不得用聚合、插值或复制数据补满。回填记录与实时记录使用相同去重键，较新 WS 数据不得被较旧 REST 回填覆盖。

回填接口依据：`docs/okex/zh/api/rest/market/historyCandles.md`，以及本节 M25 所列的接口正文。`history-candles` 的 `1s` 支持查询最近 3 个月；按 `after`／`before` 分页，单页最多 300 条，20 次／2 秒／IP。

### M22：事件合约辅助市场

保留全球站自动发现的**全部**预测市场，不按 `category`、`seriesId`、`eventId` 或 `state` 进行业务筛选。服务通过以下 REST 接口建立及刷新完整层级：

1. `GET /api/v5/public/event-contract/series` 获取所有系列；
2. 对每个系列调用 `GET /api/v5/public/event-contract/events?seriesId={seriesId}` 获取事件；
3. 对每个系列调用 `GET /api/v5/public/event-contract/markets?seriesId={seriesId}` 获取市场。

市场层级为系列 → 事件 → 市场。保留系列的 `seriesId`、`title`、`category`、`freq`、`settlement`，事件的 `eventId`、`expTime`、`state`，以及市场的 `instId`、`listTime`、`fixTime`、`expTime`、`state`、`outcome`、`floorStrike`、`capStrike`、`settleValue`、`disputed`、`hitDir`。

实时更新使用 public WS 的 `event-contract-markets` 频道，订阅参数固定为 `channel=event-contract-markets`、`instType=EVENTS`。该频道推送全部事件合约市场的状态变更和 `floorStrike` 生成，且不推送初始快照；REST 结果是初始状态的唯一来源。三个 REST 接口均为全球站可用、限速 10 次／2 秒／IP；频道与 REST 具体字段以以下来源为准：

- `docs/okex/zh/api/rest/public/series.md`
- `docs/okex/zh/api/rest/public/events.md`
- `docs/okex/zh/api/rest/public/markets.md`
- `docs/okex/zh/api/ws/public_channel/eventContractMarkets.md`

M22 侧边栏每项核心展示系列标题、`eventId`、`instId`、`expTime`、`state`、`floorStrike`、`outcome`；展开详情展示 `category`、`freq`、结算信息、`listTime`、`fixTime`、`capStrike`、`settleValue`、`disputed` 与 `hitDir`。本地目录查询按 `expTime` 倒序分页；初始 REST 建目录时，`events` 与 `markets` 以 `seriesId` 必填、单页最大 100、`before`／`after` 为 `expTime` 游标遍历，不传 `state` 过滤。

M23 侧边栏每项核心展示 `event`、`region`、`date`、`importance`、`actual`、`forecast`；展开详情展示 `category`、`previous`、`prevInitial`、`refDate`、`unit`、`ccy` 与修订时间。服务端在凭证可用时使用 `GET /api/v5/public/economic-calendar?before|after&limit` 建立或补充目录，按 `date` 倒序、最大 100 条分页；接口仅支持实盘、需要鉴权且限速为每 IP 1 次／5 秒。实时更新来自已登录的 business WS `economic-calendar`。不可用时依既有规则返回空数据集。

### 本产品接口契约

浏览器 HTTP 接口均无鉴权，直接访问。`GET /api/bootstrap` 返回永久产品选择、产品选择顺序、上次活动 Tab、可用产品目录版本和 M22／M23 侧边栏首屏。`GET /api/products` 支持 `instType`、`state` 和 `q`（`instId` 搜索）；返回所有发现状态及是否可选。

产品选择使用 `PUT /api/subscriptions/products`：请求体是有序 `instId` 列表，后端原子保存为永久全局配置；响应返回当前有效选择及被拒绝的非 `live` 项。`GET /api/market/{instId}/candles` 接受 `kind=trade`、`bar`、`before`、`limit`；返回本服务按 M02 对应保留规则保存的时间序列。`GET /api/aux/event-contract-markets` 使用不透明 `cursor` 分页并按 `expTime` 倒序；`GET /api/aux/economic-calendar` 使用不透明 `cursor` 分页并按 `date` 倒序。每页大小由后端限定，响应包含 `items`、`nextCursor` 和 `hasMore`；M23 不可用时返回空 `items`。

浏览器 WebSocket 固定为本产品 `/ws/app`。客户端消息为 `{ "type": "activate-product", "instId": "..." }` 或 `{ "type": "deactivate-product", "instId": "..." }`。服务端消息使用 `{ "type", "instId", "channel", "data", "sourceTs", "receivedAt" }` 信封：`snapshot` 为当前缓存状态，`update` 为新数据，`empty` 为当前无可用数据；`empty` 不表示历史缺口。M02 的 `channel` 为 `candle:trade:{bar}`，未完结的同一时间戳 K 线更新覆盖前端已有记录；M03 的 `channel` 为 `trades`，成交事件按 `tradeId` 追加。重连后，对全部当前活动产品先发送各频道 `snapshot`，再发送 `update`。

React 前端将 WebSocket 建连、重连、消息规范化和产品／频道状态维护封装为独立数据层；Tab、数值卡片、图表、盘口和侧边栏只读取该状态，不自行直连 OKX 或管理上游订阅。图表按已规范化的时间序列渲染，不在渲染组件内执行历史请求或行情计算。

内部策略 HTTP 为 `/internal/v1/catalog` 和 `/internal/v1/history`；内部 WebSocket 为 `/internal/v1/stream`。策略在 HTTP 参数或 WebSocket 订阅消息中显式给出 `instId`、频道、指标、周期和分页游标。它们仅接受同一部署环境的受信任调用方；具体进程边界和传输认证实现属于暂缓的部署设计。

### M25：统计与历史数据

已确认 S01、S04、S05；其他 S 指标不纳入本期。S09、S10、S11 曾一度确认并实现，已由用户指令移除（见「已移除的能力」）。

| 编号 | 指标 | 含义／范围 | 已确认周期／时间口径 | GET 接口路径 |
| --- | --- | --- | --- | --- |
| S01 | 合约多空持仓人数比 | 按产品比较多头与空头账户数量 | 5m／15m／1D | `/api/v5/rubik/stat/contracts/long-short-account-ratio-contract` |
| S04 | 合约主动买入／卖出量 | 按产品统计主动买入量、主动卖出量 | 5m／15m／1D | `/api/v5/rubik/stat/taker-volume-contract` |
| S05 | 合约持仓量历史 | 历史持仓量，含张数、币数、美元口径 | 5m／15m／1D | `/api/v5/rubik/stat/contracts/open-interest-history` |

S01／S04／S05 均采集 `5m、15m、1D`；其中 `1D` 一律按上文「日线口径：纽约自然日」由官方 `1H` 重采样，不直接请求 OKX 的 `1D`／`1Dutc`。保留与回填窗口统一为“官方每个粒度最多可获取的最近 1,440 条”（用户指令 2026-10-07「S01／S04／S05 都改为官方最多能拉的历史」）：`5m` 为 1,440 × 5 分钟 = 5 天，`15m` 为 1,440 × 15 分钟 = 15 天，按官方 `ts` 滚动清理；`1D` 由 1,440 根 `1H`（60 天）派生，扣除未结束的当天、窗口起点落在当天中途的最旧一天，并留一天余量应对官方最新一根的发布延迟，保留最近 58 个纽约自然日（含当天），按日界 `ts` 早于第 58 个纽约自然日 00:00 清理。窗口外的数据官方已无法提供，因此不长期保留。

回填在每次产品开始采集（服务启动或新选中）时执行：`5m`／`15m` 按 `end` 分页拉取至窗口下界（每组合最多约 15 页），按去重键覆盖写入；`1D`（用户指令「如果不存在则回填」）对每个“指标 + 产品 + `unit`”组合检查窗口内当天之前的 57 个纽约自然日是否都已落库，全部存在则不请求，存在缺失则以官方 `1H` 分页回看到最早缺失日的 00:00 并重采样补齐。当天日线由每小时轮询持续修正，不参与缺失判断。若官方历史不足窗口，保存可获取部分，不伪造。

对应 Skill 正文：

- S01：合约多空持仓人数比。
- S04：合约主动买入／卖出量。
- S05：合约持仓量历史。
- S01：`docs/okex/zh/api/rest/tradingData/longShortAccountRatioContract.md`。
- S04：`docs/okex/zh/api/rest/tradingData/contractTakerVolume.md`。
- S05：`docs/okex/zh/api/rest/tradingData/openInestVolumeHistory.md`。

上述 1,440 条上限依据同一 Skill（版本 `0.2.0`，生成时间 `2026-08-27T11:03:09+00:00`，站点 `okex`，语言 `zh`）三个正文的接口说明，核验日期 `2026-10-07`。

## 3. 接口映射与文档依据

#### 已核验的接口事实

本次使用 `okx-v5-api`，版本 `0.2.0`，生成时间 `2026-08-27T11:03:09+00:00`，核验日期 `2026-09-12`。已确认地区为全球站 `okex`，查询语言为 `zh`。

| 需求用途 | 接口／频道 | Skill 内相对路径 | 已核验条件 |
| --- | --- | --- | --- |
| 连接、登录、心跳 | WS 连接协议 | `docs/okex/zh/introduction.md` → WebSocket | 普通公共频道无需登录；按 IP 建连上限 3 次/秒；每连接登录／订阅／退订合计 480 次/小时 |
| 最新价、买卖一价、24 小时行情 | `tickers`，`/ws/v5/public` | `docs/okex/zh/api/ws/public_channel/tickers.md` | 无需 API Key；`instId` 必填；有事件时最快 100ms 推送 |
| K 线 | `candle1s`／`candle1m`／`candle5m`／`candle15m`／`candle30m`／`candle1H`，`/ws/v5/business`（`1H` 是纽约自然日日线的派生源，不订阅 `candle1D`） | `docs/okex/zh/api/ws/public_channel/candles.md` | 普通公开 K 线无需登录；`instId` 必填；最快 1 秒推送；`confirm=0` 为未完结、`confirm=1` 为完结 |
| 最新成交 | `trades`，`/ws/v5/public` | `docs/okex/zh/api/ws/public_channel/trades.md` | 普通公开频道无需登录；`instId` 必填；有成交即推送，每条推送可能聚合多笔成交 |
| 五档深度快照 | `books5`，`/ws/v5/public` | `docs/okex/zh/api/ws/public_channel/books.md` | 常规公开深度无需登录；变化时按约 100ms 周期推送快照 |
| 初始价格／查询回退 | `GET /api/v5/market/ticker` | `docs/okex/zh/api/rest/market/ticker.md` | `instId`；20 次/2 秒，按 IP |
| 初始 K 线 | `GET /api/v5/market/candles` | `docs/okex/zh/api/rest/market/candles.md` | `instId`、`bar`、分页；40 次/2 秒，按 IP；单页最大 300 |
| K 线断线补数 | `GET /api/v5/market/history-candles` | `docs/okex/zh/api/rest/market/historyCandles.md` | `instId`、`bar`、以 `ts` 分页；20 次/2 秒，按 IP；单页最大 300；历史跨度另按周期核验 |

全球站示例地址：`wss://ws.okx.com:8443/ws/v5/public` 和 `wss://ws.okx.com:8443/ws/v5/business`。本需求固定使用实盘环境，不使用 `ws_pap`，不设置模拟盘接入或验收要求。连接配置记录 `site` 与实盘环境标识。

**凭证边界：**普通行情连接没有“先申请 token、再建立 WS”的步骤。私有账户／订单频道使用 API Key、SecretKey、Passphrase；连接后发送 `op=login`，参数为 `apiKey`、`passphrase`、秒级 `timestamp` 和 `sign`。签名为 `Base64(HMAC-SHA256(SecretKey, timestamp + "GET" + "/users/self/verify"))`，SecretKey 本身不发送。本产品前端与后端之间无登录、无鉴权 token；服务端持有的 OKX API 凭证（M23 所需）仅在后端与 OKX 之间使用，不经过浏览器。

已选频道的补充来源均相对 `<skill_dir>/docs/okex/zh/`：

| 功能 | 文档路径 |
| --- | --- |
| M02 | `api/ws/public_channel/candles.md` |
| M03 | `api/ws/public_channel/trades.md` |
| M05 | `api/ws/public_channel/books.md` |
| M10 | `api/ws/public_channel/markPrice.md` |
| M13 | `api/ws/public_channel/openInterest.md` |
| M22 | `api/ws/public_channel/eventContractMarkets.md` |
| M23 | `api/ws/private_channel/economicCalendar.md` |

REST 初始化、补数与首次启动混合回填已确认为产品行为，具体保存形式与回填边界见“保存、保留与首次启动回填”。

#### 逐接口限速与分页依据

Global 站 REST 以 Skill 的站点表和端点正文为准，统一使用 `https://www.okx.com`；介绍页中出现的 `openapi.okx.com` 不覆盖站点表或端点正文。S01 与 S04 均为 `5 次／2 秒／IP + instId`、`limit≤100`；S05 为 `10 次／2 秒／IP + instId`、`limit≤100`。三者均使用 `instId`（适用 SWAP）、`period`、`begin`、`end` 和 `limit`。本期实际请求的 `period` 为 `5m`、`15m`、`1H`——对外的 `1D` 由 `1H` 按纽约自然日重采样，不请求 OKX 的 `1D`（UTC+8 口径）或 `1Dutc`（UTC+0 口径）。

M10、M13 都以 `channel` 与 `instId` 订阅。M22 的系列、事件和市场 REST 均为 `10 次／2 秒／IP`，事件和市场均用 `seriesId`、可选 `eventId`、`before`／`after` 与 `limit≤100` 分页，不传 `state`。M23 REST 为 `1 次／5 秒／IP`，按 `date` 使用 `before`／`after` 且 `limit≤100`。

## 4. 基于已确认需求的验收结果

- 前端与后台策略／分析均可消费其所需行情。
- 使用全球站实盘行情，现货和永续按已选集合提供数据。
- 成交价格 K 线提供 1s／1m／5m／15m／30m／1D，1s 以折线图展示。日线按纽约自然日划分（见「日线口径：纽约自然日」）。
- 成交价格日线保留最新 80 根；分钟级各保留最近 10×24 小时；首次启动时回填到目标或官方可获取最大量。
- M03 公共成交持续采集，并在活动产品 Tab 实时展示；暂不持久化，仅在 Redis 保留最近 100 笔。
- 普通深度为五档；本期不接入 M06 高阶深度。
- M22 作为独立辅助市场数据提供。
- M23 为共享数据；未配置凭证、鉴权失败、网络故障或账户不满足 VIP1 时均返回空。
- M25 仅包含已选三项（S01、S04、S05），并使用各自已确认的周期／时间口径。
- M01、M03、M05、M10、M13 暂不持久化；除此之外及 K 线的 80 根／10×24 小时／7 天例外外，历史数据以业务时间滚动保留 7 天；首次启动尽量回填至已确认下限，无法回填的数据从首次接收开始积累并保留缺口事实。
- 仅 `live` 产品可被选择；已选产品状态变化会关闭或恢复对应 Tab，且持久化选择不丢失。
- 浏览器到后端的数据边界和实时快照恢复遵循“前端形态与使用范围”及“数据视图与产品面板”的规定；无登录。
- 功能验收只检验可观察行为；性能、可靠性和部署数值门槛属于明确暂缓项。

### 功能验收案例

| 场景 | 通过标准 |
| --- | --- |
| 产品发现和选择 | 产品选择器显示 SPOT／SWAP 的所有返回状态，仅允许选择 `live`；保存选择后立即创建 Tab，取消后关闭。 |
| 持续采集 | 已选 live 产品在浏览器关闭、Tab 非活动后仍持续写入所选行情；活动 Tab 变化只影响浏览器实时消息。 |
| 实时浏览器数据 | 激活产品后收到各可用频道的 `snapshot` 与后续 `update`；K 线最快按上游每秒更新、同时间戳未完结 K 线覆盖；成交事件追加；重连先收到快照；无缓存的不可用普通行情显示空面板。 |
| 历史与回填 | K 线和 M25 按定义的键去重；K 线日线保留 80 根、分钟级保留 10×24 小时，首次启动回填至目标或可用最大量；不伪造无法回填的数据。 |
| M22／M23 | M22 建立完整目录并按 expTime 倒序分页；M23 在可用时按 date 倒序分页，在未配置凭证、鉴权失败、网络故障或非 VIP1 时返回空集。 |
| 策略消费者 | 受信任部署内策略可显式请求目录、历史或实时流，其请求不改变后台已选产品采集集合。 |

验收的具体操作样例与技术阈值在相关决定确认后补入；以下为已执行的局部验证，不代表全项目验收完成。

### 2026-09-22 K 线缺陷修复验证

本次不扩大功能范围，仍为 0.46。针对用户反馈的蜡烛高度与数值不符、相邻 K 线缺口，验证结果如下：

- 真实本地数据库只读复核：NVDA／SKHYNIX／SNDK／SPCX 四个 USDT 永续，成交价与标记价分别抽查最新 300 根 `1m`／`5m`／`15m` 和 80 根纽约日线；修复后样本内时间缺口、OHLC 越界、已过期但未闭合的旧线均为 0。该结论不外推到所有历史或所有产品。
- 实际浏览器图表回归：两类图表的 `1m`／`5m`／`15m`／`30m`／`1D` 实体和影线像素高度与 OHLC 坐标一致；小数报价不再被两位纵轴刻度抹平；后台补齐后当前视图能取得中间缺线与最终 OHLC，不重置用户平移。
- 纽约时区只参与标签格式化，图表以真实 UTC 时间排序、去重；秋季重复的 01 点保留两小时全部数据，标签区分 EDT／EST。日线仍由官方 `1H` 按纽约自然日派生，缺日界／缺小时的残缺日线不得被当作完整已闭合日线。
- 自动验证：后端 120 项、前端单元 22 项、浏览器 16 项通过，构建与静态检查通过（仅既有警告）。浏览器使用隔离数据回放，没有登录用户的真实浏览器会话；不通过修改 OHLC 或造线消除真实价格跳空。
