# Funding Radar — 设计文档

日期：2026-07-06
状态：已批准（用户委托决策，要求最少参与）

## 1. 目标与商业模型

一套**永续 DEX 资金费率聚合引擎**，喂三个零边际成本变现渠道：

1. **Telegram**：免费频道推送资金费率套利警报（引流资产）；付费群（提前/高频警报，$10-30/月）为 Phase 2。
2. **Apify actor**：按请求付费（pay-per-event），挂在 Apify Store 被动接单。
3. **SEO 静态站**：每币种/每交易所程序化生成页面，GitHub Pages 免费托管，吃英文长尾搜索，导流到前两个渠道。

**目标市场**：海外英文用户（delta-neutral 资金费率套利者、量化开发者）。
**成本约束**：零服务器。GitHub Actions（公开仓库免费无限分钟）+ GitHub Pages + Telegram Bot API 全免费。可选支出：域名 ~$10/年。
**预期管理**：前 1-3 个月收入≈0，靠 SEO 与频道积累。低维护是硬约束，高于功能丰富度。

### 为什么选这个（调研结论，2026-07-06）

- CEX 资金费率 API：Apify 同类 actor（FundingPulse）仅 4 月活用户，需求已被 Coinalyze 免费层压死。且 Binance/Bybit/OKX 封美国 IP，GitHub Actions/Apify 出口在美国。
- 预测市场数据：Polymarket 已收购 Dome，Prediction Hunt / FinFeedAPI / Oddpool 已卡位。
- 中文平台爬虫（RedNote 等）：需求真实但 Apify 已有 8+ 竞品，且反爬猫鼠游戏 = 高维护，违反核心约束。
- **永续 DEX**：API 全开放（无地理封锁、无反爬、无 key）= 维护接近零。网页端有免费竞品（loris.tools、fundingview.app），但 Telegram 警报 + Apify API + SEO 组合变现口没人做全。竞争差异点 = 覆盖新兴 venue 长尾 + 扣费净收益计算 + 警报形态。

## 2. 总体架构

```
GitHub Actions cron (每 30 分钟, 公开仓库)
  └─ python -m radar.run
       ├─ collector: 并发拉取 12-15 家 perp DEX 公开 API
       ├─ normalize: 统一 schema (FundingSnapshot)
       ├─ store: 快照写入 data/ (JSON, git commit 到 data 分支)
       ├─ arb: 扣费净收益套利机会计算
       ├─ alert: 新机会推 Telegram 频道 (去重, 阈值)
       └─ sitegen: Jinja2 渲染静态站 → 部署 GitHub Pages

Apify actor (独立入口, 同一核心库)
  └─ 按需实时调 collector + arb, 返回 JSON, pay-per-event 计费
```

单一 Python 包 `radar/`，三个入口（cron run / apify actor / CLI）共享全部核心逻辑。

## 3. 组件

### 3.1 collector — venue 适配器框架

- `radar/venues/base.py`：`VenueAdapter` 抽象基类。契约：`fetch() -> list[FundingSnapshot]`，内部自带 httpx 超时（10s）与 2 次指数退避重试。
- 每个 venue 一个文件 `radar/venues/<name>.py`，注册进 `REGISTRY`。
- **适配器互相隔离**：单 venue 失败只记 warning + 标记该 venue stale，不影响整轮运行。全部失败才算运行失败。
- 首批 venue（Phase 0，按流动性优先）：Hyperliquid、Lighter、Aster、Paradex。
- 后续 venue（Phase 1）：edgeX、dYdX v4、Drift、Extended、Vest、Bluefin、Hibachi、Pacifica。
- **实现每个适配器前必须先用真实请求验证端点可达且字段符合预期**，把真实响应样本存为测试 fixture。

### 3.2 数据模型

```python
@dataclass(frozen=True)
class FundingSnapshot:
    venue: str            # "hyperliquid"
    symbol: str           # 归一化币名 "BTC"（去 venue 前后缀/编号）
    rate: float           # 单期费率（小数，非百分比）
    interval_hours: float # 结算周期：1/4/8
    apr: float            # 年化 = rate * (8760 / interval_hours)
    mark_price: float | None
    open_interest_usd: float | None
    next_funding_ts: int | None
    fetched_at: int       # unix 秒
```

归一化规则集中在 `radar/normalize.py`（symbol 映射表 + 周期换算），是正确性核心，测试最重。

### 3.3 store — 历史存储

- 无数据库。快照写 `data/latest.json`（全量最新）+ `data/history/<YYYY-MM-DD>/<HH>.json`（小时粒度归档）。
- 由 Actions 提交到独立 `data` 分支，避免污染 main 提交历史。
- 保留策略：history 保留 90 天（cron 内清理），latest 永远存在。站点与 API 只依赖 latest + 近 30 天。

### 3.4 arb — 套利机会引擎

- 对每个 symbol：所有 venue 两两配对。费率为正时多头付空头，因此**做空高费率 venue（收费率），做多低/负费率 venue（付得少或反收）**：`spread_apr = apr_short_venue - apr_long_venue`，其中 `apr_short_venue ≥ apr_long_venue`。
- **净收益**：`net_apr = spread_apr - annualized_cost(taker_fee_open + taker_fee_close, holding_days 假设 7 天)`。各 venue taker 费率维护在 `radar/fees.py` 静态表（低频人工更新，Sonnet 任务）。
- 过滤：两腿 open_interest_usd 均 ≥ $500k（可配置）；数据 stale 的 venue 剔除。
- 输出 `ArbOpportunity` 列表，按 net_apr 降序。

### 3.5 alert — Telegram 警报

- 阈值：net_apr ≥ 15%（可配置）视为机会。
- 去重：`data/alert_state.json` 记录已播报的 (symbol, venue_pair)；净收益回落 30% 以下后重置，避免刷屏。
- 免费频道消息格式：币种、两腿 venue+方向、各腿 APR、净 APR、OI，加站点链接（引流）。
- 发送 = 对 Telegram Bot API 一个 POST。secret：`TELEGRAM_BOT_TOKEN`、`TELEGRAM_CHANNEL_ID`。
- 付费群（Phase 2）：同逻辑更低阈值 + 提前推送；收款用 Telegram Stars 或 crypto，方案 Phase 2 再定。

### 3.6 sitegen — SEO 静态站

- Jinja2 模板 → 纯静态 HTML + 一份 CSS，无 JS 框架。页面：
  - `/`：实时套利机会排行榜（核心页）
  - `/funding-rates/<symbol>/`：单币种跨 venue 对比 + 7 天历史表
  - `/exchanges/<venue>/`：单 venue 全币种费率
  - `/compare/<venueA>-vs-<venueB>/`：venue 对比页（程序化长尾）
  - `sitemap.xml`、`robots.txt`、每页独立 title/meta description
- 页面含 Telegram 频道与 Apify actor 的 CTA。
- 部署：Actions 内 build 后推 `gh-pages`。域名后接（先用 `<user>.github.io`）。

### 3.7 Apify actor

- `apify/` 目录，Python actor，薄封装：输入（symbols/venues/mode=rates|arb）→ 调核心库实时抓取 → `Actor.push_data`。
- 计费 pay-per-event。上架文案（英文 README、定价、示例输出）= Sonnet 任务。

### 3.8 CI / 运维

- `.github/workflows/cron.yml`：`schedule: */30 * * * *` + `workflow_dispatch`。步骤：checkout → run → commit data 分支 → 部署 pages。
- `.github/workflows/test.yml`：PR/push 跑 pytest。
- 运行失败通知：Actions 失败时通过同一 Telegram bot 私聊用户（免费的运维监控）。

## 4. 错误处理原则

| 场景 | 处理 |
|------|------|
| 单 venue API 挂/改字段 | 隔离跳过，标 stale，Telegram 私聊通知；站点该 venue 显示 stale 徽章 |
| 全部 venue 失败 | 运行 fail，不覆盖 latest.json，Telegram 私聊告警 |
| symbol 无法归一化 | 丢弃并记 warning（宁缺勿错，防止套利假信号） |
| 数据异常（apr > 1000% 等） | 视为脏数据丢弃，防闪烁值触发假警报 |
| Telegram 发送失败 | 重试 2 次后放弃，不阻塞数据管线 |

## 5. 测试策略

- pytest。每个 venue 适配器配真实响应 fixture（JSON 文件），测解析与归一化。
- `normalize.py` 与 `arb.py` 是资金正确性核心：周期年化换算、方向判断（谁做多谁做空）、净费率计算，全部显式用例覆盖，含负费率、跨周期（1h vs 8h）配对等边界。
- alert 去重逻辑：状态机单测。
- sitegen：冒烟测试（渲染不抛错 + 关键字段出现在 HTML）。
- 集成冒烟：`radar.run --dry-run` 走通全管线（fixture 数据源）。

## 6. 分阶段与模型分工

| Phase | 内容 | 模型 |
|-------|------|------|
| **P0 核心引擎（本会话）** | 数据模型、normalize、arb 引擎、adapter 框架、Hyperliquid/Lighter/Aster/Paradex 四个适配器（含真实端点验证+fixture）、alert 逻辑、全部单测 | **Fable** |
| **P1 管线上线** | 剩余 8 家适配器（照模式抄）、store、cron workflow、Telegram 接线、sitegen 模板实现、Pages 部署 | **Opus** |
| **P2 变现口** | Apify actor 打包上架、premium 群逻辑、compare 长尾页扩展 | **Opus** |
| **持续维护** | fees.py 费率表更新、venue 增删、SEO 文案/README/上架文案、新币种 | **Sonnet** |

## 7. 用户仅需的动作（总计 ~1.5 小时，一次性）

1. GitHub 建公开仓库并推送（或给我 `gh` 授权）。
2. Telegram @BotFather 建 bot，拿 token；建频道，把 bot 设为管理员。token 存入 GitHub Secrets。
3. Apify 注册账号（P2 时）。
4. （可选）买域名。

## 8. 明确不做（YAGNI）

- 不做交易执行/下单，只做数据与信号。
- 不做用户系统/数据库/后端服务器。
- 不做 CEX（地理封锁 + 维护重），除非日后套 proxy 有明确收益。
- 不做实时 WebSocket（30 分钟粒度对费率套利足够）。
- P0/P1 不做付费墙。先有流量再收钱。
