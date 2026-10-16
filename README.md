# 每日行业资讯 · Daily Industry Digest

每天自动抓取多个行业板块的公开信息源，聚合去重后生成一份中文日报，
提交到本仓库（GitHub Actions 为主、本地计划任务兜底），并镜像到
Gitee / AtomGit / 极狐 GitLab。

<!-- INDEX:BEGIN -->
## 📅 最近 7 天

| 日期 | 🤖 AI / 科技 | 💰 财经 / 商业 | 🔒 网络安全 | 🛠 开源 / 开发者 |
| --- | --- | --- | --- | --- |
| [2026-10-16](digests/2026-10-16.md) | 37 | 101 | 32 | 43 |
| [2026-10-15](digests/2026-10-15.md) | 40 | 101 | 36 | 44 |
| [2026-10-14](digests/2026-10-14.md) | 42 | 99 | 34 | 43 |
| [2026-10-13](digests/2026-10-13.md) | 30 | 99 | 17 | 38 |
| [2026-10-12](digests/2026-10-12.md) | 33 | 85 | 2 | 37 |
| [2026-10-11](digests/2026-10-11.md) | 28 | 90 | 8 | 43 |
| [2026-10-10](digests/2026-10-10.md) | 43 | 102 | 31 | 46 |

## 📌 今日概览

213 条精选（各板块：37 / 101 / 32 / 43）

<!-- INDEX:END -->

## 🗂 板块与来源

| 板块 | 来源 |
| --- | --- |
| 🤖 AI / 科技 | Hacker News · Simon Willison · MIT 科技评论 · The Verge |
| 💰 财经 / 商业 | Yahoo 财经 · FT · CNBC · MarketWatch · 新浪 7x24 |
| 🔒 网络安全 | The Hacker News · Krebs on Security · BleepingComputer · The Record |
| 🛠 开源 / 开发者 | GitHub 热门(搜索 API) · Lobsters · Product Hunt |

## ⚙️ 机制

- 每天 06:30（北京时间）由 GitHub Actions 自动生成并提交；若云端未产出，
  本地计划任务 07:20 补跑并推送。
- 纯 Python 标准库，零依赖零密钥；GitHub 热门板块走搜索 API（无需额外 key）。
- 板块、源、关键词权重都改 `config.json`，改完 push 当天生效。

## 🧰 本地补跑

```bash
python scripts/daily_digest.py            # 生成本日日报
python scripts/ensure_daily.py            # 检查远端→缺则补跑+提交+推送+镜像
```
