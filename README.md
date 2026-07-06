# Funding Radar

跨交易所**永续合约资金费率聚合 + 费率套利扫描器**，覆盖去中心化永续 DEX。一条管线喂三个变现渠道：

- **Telegram 警报** —— 实时资金费率套利机会推送到免费频道
- **SEO 静态站** —— 按币种、按交易所、按交易所对自动生成页面（GitHub Pages）
- **Apify API** —— 同一份数据可编程查询（P2）

零服务器。整套跑在 GitHub Actions 定时任务上（每 30 分钟一次），git 分支就是唯一存储。

## 工作原理

```
GitHub Actions (*/30) → 采集 8 家永续 DEX → 归一化 → 套利扫描（扣手续费）
   → 写 latest.json + 小时级历史（data 分支）
   → Telegram 警报（去重）
   → 生成静态站 → GitHub Pages
```

套利逻辑：每个币种，做空费率最高的交易所、做多费率最低的。净年化 = 费率价差 - 年化的双腿往返 taker 手续费（按持仓 7 天摊算）。

## 已覆盖交易所（8 家）

hyperliquid · aster · paradex · lighter · binance（经 lighter）· dydx · extended · pacifica

数据源说明和被跳过的交易所（drift、vest、bluefin、edgex、hibachi）及原因见 [docs/venue-notes.md](docs/venue-notes.md)。

## 本地开发

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q                                              # 全套测试
python -m radar.run --dry-run --data-dir /tmp/fr       # 离线管线冒烟（用 fixture）
python -m radar.run --skip-telegram --site-out _site   # 实时数据、建站、不发警报
```

## 上线清单（一次性，约 1 小时）

以下都需要你的账号，代码已就绪。

1. **建一个公开 GitHub 仓库**，把本仓库推上去。
   （公开仓库 = 免费无限 Actions 分钟 + 免费 Pages。）
2. **建 Telegram bot + 频道：**
   - 给 [@BotFather](https://t.me/BotFather) 发 `/newbot` → 复制 token。
   - 建一个公开频道；把 bot 加为管理员。
   - 拿到频道 id（如 `@yourchannel` 可直接用）。
   - 失败私聊用：先给你的 bot 发条消息，记下你自己的数字 chat id。
3. **加仓库 Secrets**（Settings → Secrets and variables → Actions → Secrets）：
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHANNEL_ID`（如 `@yourchannel`）
   - `TELEGRAM_ADMIN_CHAT_ID`（你的数字 id，用于失败告警）
4. **加仓库 Variables**（同页 → Variables）：
   - `SITE_URL`（如 `https://<user>.github.io/<repo>`）
   - `TELEGRAM_URL`（如 `https://t.me/yourchannel`）
   - `APIFY_URL`（P2 上线 Apify actor 前先留默认值）
5. **开启 Pages：** Settings → Pages → Source 选 "GitHub Actions"。
6. **在定时任务跑起来前先手动测：** Actions → `cron` → "Run workflow"。
   确认：运行绿灯、`data` 分支已创建、Pages URL 可访问。想强制触发第一条
   警报，临时调低阈值（见下），跑一次，再改回来。

上线后把实际 URL 记在这里：

- 站点：_待填_
- Telegram 频道：_待填_
- Apify actor：_待填（P2）_

## 参数调节

警报阈值和套利过滤条件都在代码里：

- 警报阈值：`radar/run.py` 里 `select_alerts(..., threshold_apr=0.15)`
- 最小持仓量 / 持仓天数：`radar/arb.py` 里 `find_opportunities(...)` 默认值
- 各交易所 taker 手续费：`radar/fees.py`

## 免责声明

非投资建议。资金费率套利存在执行、爆仓、对手方风险。数据可能滞后或错误。
