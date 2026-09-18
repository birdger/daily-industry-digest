#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每日行业资讯雷达。

按 config.json 的板块配置，并发抓取各行业 RSS / JSON 源，按时间窗口过滤、
标题去重、关键词加成排序，生成中文 Markdown 日报到 digests/YYYY-MM-DD.md，
并刷新 README 的最近 7 天索引。

沿袭 daily-arxiv-digest 的三个设计：
  1) 只用 Python 标准库 —— GitHub Actions 上零安装，不会因依赖挂掉；
  2) 每个源独立失败、互不拖累 —— 单源挂了只在该板块少几条，不中断整体；
  3) 无论结果如何都写文件 —— 抓取失败也留痕，不会静默断更。

板块/源/关键词都在 config.json 里，改配置即改口味。
"""

import html
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TZ_CN = timezone(timedelta(hours=8))
UA = "daily-industry-digest/1.0 (daily multi-industry digest; contact: repo owner)"
NS = {"atom": "http://www.w3.org/2005/Atom"}


def log(msg):
    print("[digest] %s" % msg, flush=True)


def load_config():
    with open(ROOT / "config.json", encoding="utf-8") as f:
        cfg = json.load(f)
    cfg.pop("_comment", None)
    cfg.setdefault("window_hours", 30)
    cfg.setdefault("max_per_section", 8)
    cfg.setdefault("max_per_feed", 3)
    cfg.setdefault("keywords", {})
    cfg.setdefault("sections", {})
    cfg.setdefault("feeds", [])
    return cfg


def http_get(url, retries=2, timeout=40):
    last = None
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", "replace")
        except Exception as exc:  # noqa: BLE001
            last = exc
            if i < retries:
                time.sleep(3 * (i + 1))
    raise RuntimeError(str(last))


def gh_token():
    for k in ("GITHUB_TOKEN", "GH_TOKEN"):
        v = os.environ.get(k)
        if v:
            return v
    try:
        p = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=30)
        if p.returncode == 0 and p.stdout.strip():
            return p.stdout.strip()
    except Exception:  # noqa: BLE001
        pass
    return None


def fetch_gh_trending(feed, cutoff):
    """GitHub 搜索 API：最近 24h 内有推送且 star≥100 的仓库，按 star 排序 ≈ 今日热门。"""
    q = "pushed:>=%s stars:>=100" % cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")
    url = "https://api.github.com/search/repositories?%s" % urllib.parse.urlencode(
        {"q": q, "sort": "stars", "order": "desc", "per_page": 12}
    )
    token = gh_token()
    headers = {"User-Agent": UA, "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = "Bearer %s" % token
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=40) as resp:
        data = json.loads(resp.read().decode("utf-8", "replace"))
    out = []
    for it in data.get("items", []):
        pushed = it.get("pushed_at")
        pdt = _parse_iso(pushed)
        out.append(
            {
                "title": it.get("full_name", ""),
                "url": it.get("html_url", ""),
                "summary": "⭐ %s · %s" % (it.get("stargazers_count", 0),
                                          it.get("description") or it.get("language") or "—"),
                "published": pdt.astimezone(TZ_CN).strftime("%m-%d %H:%M") if pdt else "",
                "published_dt": pdt,
            }
        )
    return out


def _parse_iso(s):
    if not s:
        return None
    try:
        return datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    except Exception:  # noqa: BLE001
        return None


def fetch_sina_724(feed, cutoff):
    """新浪财经 7x24 快讯 JSON：{result:{data:[{title,url,ctime}]}}"""
    req = urllib.request.Request(feed["url"], headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as resp:
        data = json.loads(resp.read().decode("utf-8", "replace"))
    out = []
    for it in (data.get("result", {}) or {}).get("data", []) or []:
        ctime = it.get("ctime")
        pdt = _parse_sina(ctime)
        out.append(
            {
                "title": it.get("title", "").strip(),
                "url": it.get("url", ""),
                "summary": "",
                "published": pdt.astimezone(TZ_CN).strftime("%m-%d %H:%M") if pdt else "",
                "published_dt": pdt,
            }
        )
    return out


def _parse_sina(ctime):
    if not ctime:
        return None
    try:
        return datetime.fromtimestamp(int(ctime), tz=timezone.utc)
    except Exception:  # noqa: BLE001
        return None


def fetch_rss(feed, cutoff):
    text = http_get(feed["url"])
    root = ET.fromstring(text)
    out = []
    # Atom 与 RSS 2.0 统一处理：逐 item/entry 提取标题/链接/描述/时间
    for it in root.iter():
        tag = it.tag.split("}")[-1]
        if tag not in ("item", "entry"):
            continue
        title = link = desc = pub = ""
        for child in it.iter():
            ctag = child.tag.split("}")[-1]
            if ctag == "title" and not title:
                title = (child.text or "").strip()
            elif ctag == "link":
                rel = child.get("rel")
                if rel in (None, "alternate"):
                    href = child.get("href") or (child.text or "").strip()
                    if href and not link:
                        link = href
            elif ctag in ("description", "summary") and not desc:
                desc = (child.text or "").strip()
            elif ctag in ("pubDate", "published", "updated") and not pub:
                pub = (child.text or "").strip()
        title = title or link
        if not title:
            continue
        pdt = None
        try:
            if pub:
                pdt = parsedate_to_datetime(pub)
        except Exception:  # noqa: BLE001
            pdt = None
        if pdt is None and pub:
            try:  # Atom 常用 ISO 8601（含 T 分隔符），email.utils 解析不了就退回 fromisoformat
                pdt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            except Exception:  # noqa: BLE001
                pdt = None
        summary = one_liner(desc)
        if summary in ("Comments", "Comment"):  # HN 的 description 就一个词，无信息量
            summary = ""
        out.append(
            {
                "title": re.sub(r"\s+", " ", html.unescape(title)).strip(),
                "url": link,
                "summary": summary,
                "published": pdt.astimezone(TZ_CN).strftime("%m-%d %H:%M") if pdt else "",
                "published_dt": pdt,
            }
        )
    return out


def fetch_one(feed, cutoff):
    kind = feed.get("kind", "rss")
    if kind == "gh_trending":
        return fetch_gh_trending(feed, cutoff)
    if kind == "json_sina":
        return fetch_sina_724(feed, cutoff)
    return fetch_rss(feed, cutoff)


def one_liner(desc, limit=280):
    text = re.sub(r"<[^>]+>", " ", desc or "")
    text = re.sub(r"\s+", " ", html.unescape(text)).strip()
    if not text:
        return ""
    line = " ".join(re.split(r"(?<=[.!?。！？])\s+", text)[:2])
    return line[:limit] + ("…" if len(line) > limit else "")


def norm_key(title):
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", (title or "").lower())


def keyword_boost(title, keywords):
    t = (title or "").lower()
    total = 0
    for kw, w in keywords.items():
        if kw.lower() in t:
            total += int(w)
    return total


def collect(cfg):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=cfg["window_hours"])
    feeds = sorted(cfg["feeds"], key=lambda f: -f.get("prio", 1))
    results, errors = {}, []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = {pool.submit(fetch_one, f, cutoff): f for f in feeds}
        for fut in as_completed(futs):
            f = futs[fut]
            try:
                items = fut.result()
                results[f["name"]] = (f, items)
                log("OK   %-24s %s → %d 条" % (f["name"], f.get("kind", "rss"), len(items)))
            except Exception as exc:  # noqa: BLE001
                errors.append(f["name"])
                log("FAIL %-24s %s" % (f["name"], exc))
    # 组装：去重（按规范化标题），过滤时间窗口
    seen, sections = set(), {}
    for f, items in results.values():
        sec = sections.setdefault(f["section"], [])
        for it in items:
            key = norm_key(it["title"])
            if not key or key in seen:
                continue
            dt = it.get("published_dt")
            if dt and dt < cutoff:
                continue
            seen.add(key)
            it["source"] = f["name"]
            it["boost"] = keyword_boost(it["title"], cfg["keywords"])
            sec.append(it)
    return sections, sorted(errors), len(seen)


def esc(s):
    return (s or "").replace("|", "\\|").replace("[", "\\[").replace("]", "\\]")


def build_markdown(today_cn, cfg, sections, errors):
    L = []
    L.append("# 每日行业资讯 · %s" % today_cn)
    L.append("")
    total = sum(len(v) for v in sections.values())
    L.append("> 板块：%s ｜ 去重聚合 %d 条 ｜ 源：%s"
             % (" · ".join(s["name"] for s in cfg["sections"].values()),
                total, "，".join(f["name"] for f in cfg["feeds"])))
    L.append("")
    for key, sec in cfg["sections"].items():
        items = sections.get(key, [])
        L.append("## %s（%d 条）" % (sec["name"], len(items)))
        L.append("")
        if not items:
            L.append("_本板块今日无内容（源全部失败或超窗）_")
            L.append("")
            continue
        # 时间新在前（无时间的沉底），关键词命中次之；同一来源最多占 max_per_feed 条，避免霸榜
        items = sorted(
            items,
            key=lambda x: (
                -(x["published_dt"].timestamp() if x["published_dt"] else 0),
                -x.get("boost", 0),
            ),
        )
        per_feed = {}
        shown = 0
        for it in items:
            if shown >= cfg["max_per_section"]:
                break
            src_name = it["source"]
            if per_feed.get(src_name, 0) >= cfg.get("max_per_feed", 3):
                continue
            per_feed[src_name] = per_feed.get(src_name, 0) + 1
            shown += 1
            src = "%s · %s" % (src_name, it["published"]) if it["published"] else src_name
            L.append("%d. [%s](%s) — %s" % (shown, esc(it["title"]), it["url"], src))
            if it.get("summary"):
                L.append("   %s" % it["summary"])
        L.append("")
    L.append("---")
    L.append("_失败源：%s_ " % ("，".join(errors) if errors else "无"))
    L.append("_自动生成，仅供参考；数据来自各公开源，准确性以原站为准。_")
    return "\n".join(L)


def refresh_readme(today_cn, cfg, sections):
    """刷新 README 里 <!-- INDEX:BEGIN --> .. <!-- INDEX:END --> 之间的索引区。"""
    rows = []
    rows.append("## 📅 最近 7 天")
    rows.append("")
    rows.append("| 日期 | %s |" % " | ".join(s["name"] for s in cfg["sections"].values()))
    rows.append("| --- | %s |" % " | ".join("---" for _ in cfg["sections"]))
    days = [today_cn]
    for i in range(1, 7):
        d = (datetime.now(TZ_CN) - timedelta(days=i)).strftime("%Y-%m-%d")
        if (ROOT / "digests" / ("%s.md" % d)).exists():
            days.append(d)
    for d in days:
        f = ROOT / "digests" / ("%s.md" % d)
        if not f.exists():
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        cnts = []
        for key, sec in cfg["sections"].items():
            seg = re.search(r"## " + re.escape(sec["name"]) + r"（(\d+) 条）", text)
            cnts.append(seg.group(1) if seg else "—")
        rows.append("| [%s](digests/%s.md) | %s |" % (d, d, " | ".join(cnts)))
    today_cnt = " / ".join(str(len(sections.get(k, []))) for k in cfg["sections"])
    block = "\n".join(rows) + "\n\n## 📌 今日概览\n\n%s 条精选（各板块：%s）\n" % (sum(len(v) for v in sections.values()), today_cnt)
    readme = ROOT / "README.md"
    if readme.exists():
        text = readme.read_text(encoding="utf-8")
        pattern = re.compile(r"<!-- INDEX:BEGIN -->.*?<!-- INDEX:END -->", re.S)
        if pattern.search(text):
            text = pattern.sub("<!-- INDEX:BEGIN -->\n%s\n<!-- INDEX:END -->" % block, text, count=1)
        else:
            text += "\n<!-- INDEX:BEGIN -->\n%s\n<!-- INDEX:END -->\n" % block
    else:
        text = TEMPLATE_README % {"index": block}
    readme.write_text(text, encoding="utf-8")


TEMPLATE_README = """# 每日行业资讯 · Daily Industry Digest

每天自动抓取多个行业板块的公开信息源，聚合去重后生成一份中文日报，
提交到本仓库（GitHub Actions 为主、本地计划任务兜底），并镜像到
Gitee / AtomGit / 极狐 GitLab。

<!-- INDEX:BEGIN -->
%(index)s
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
"""


def main():
    cfg = load_config()
    today_cn = datetime.now(TZ_CN).strftime("%Y-%m-%d")
    sections, errors, total = collect(cfg)
    log("共抓到 %d 条（去重后），失败源 %d 个" % (total, len(errors)))
    md = build_markdown(today_cn, cfg, sections, errors)
    out = ROOT / "digests" / ("%s.md" % today_cn)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    refresh_readme(today_cn, cfg, sections)
    log("已写入 %s" % out)
    print("\n" + md[:600] + ("\n..." if len(md) > 600 else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
