# 每日行业资讯 · Daily Industry Digest

每天自动抓取多个行业板块的公开信息源，聚合去重后生成一份中文日报，
提交到本仓库（GitHub Actions 为主、本地计划任务兜底），并镜像到
Gitee / AtomGit / 极狐 GitLab。

<!-- INDEX:BEGIN -->
## 📅 最近 7 天

| 日期 | 🤖 AI / 科技 | 💰 财经 / 商业 | 🔒 网络安全 | 🛠 开源 / 开发者 |
| --- | --- | --- | --- | --- |
| [2026-10-28](digests/2026-10-28.md) | 35 | 99 | 30 | 42 |
| [2026-10-27](digests/2026-10-27.md) | 35 | 102 | 25 | 42 |
| [2026-10-26](digests/2026-10-26.md) | 24 | 82 | 4 | 33 |
| [2026-10-25](digests/2026-10-25.md) | 29 | 96 | 9 | 35 |
| [2026-10-24](digests/2026-10-24.md) | 39 | 102 | 27 | 43 |
| [2026-10-23](digests/2026-10-23.md) | 39 | 100 | 32 | 42 |
| [2026-10-22](digests/2026-10-22.md) | 36 | 100 | 36 | 38 |

## 📌 今日概览

206 条精选（各板块：35 / 99 / 30 / 42）

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
