#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每日行业日报 · 本地补跑脚本（Windows 计划任务 07:20 调用，云端的兜底）。

逻辑沿袭 daily-arxiv-digest 的 daily_job.py：
  1) 等本机代理(127.0.0.1:7892)就绪，等不到就退出（宁可今天不产出，不污染仓库）
  2) git pull --rebase
  3) 查 GitHub 远端今天是否已有 "digest: <今天> 行业日报" 提交
     - 有 → 什么都不做
     - 没有 → 本地跑生成器；若抓到 0 条则回滚不提交；否则提交并推送
  4) 调 mirror_push.py 把本仓镜像到 Gitee / AtomGit / 极狐

日志: G:\\code\\github\\workbench\\data\\logs\\industry_<date>.log
"""
import datetime
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
WORKBENCH = pathlib.Path("G:/code/github/workbench")
LOG_DIR = WORKBENCH / "data" / "logs"
PROXY = "http://127.0.0.1:7892"
PY = sys.executable
TZ = datetime.timezone(datetime.timedelta(hours=8))
TODAY = datetime.datetime.now(TZ).strftime("%Y-%m-%d")
_buf = []


def say(line=""):
    text = str(line)
    _buf.append(text)
    try:
        print(text, flush=True)
    except UnicodeEncodeError:
        print(str(text).encode("utf-8", "replace").decode("utf-8", "replace"), flush=True)


def run(cmd, cwd=None, timeout=420):
    env = os.environ.copy()
    env["HTTPS_PROXY"] = PROXY
    env["HTTP_PROXY"] = PROXY
    env["NO_PROXY"] = "gitee.com,gitcode.com,atomgit.com,jihulab.com,localhost,127.0.0.1"
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "never"
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as exc:  # noqa: BLE001
        return 1, "[异常] %s" % exc


def tail(text, n=6):
    lines = [l for l in (text or "").splitlines() if l.strip()]
    return "\n".join(lines[-n:])


def wait_proxy(seconds=240, step=15):
    import socket
    import time
    deadline = time.time() + seconds
    while True:
        try:
            with socket.create_connection(("127.0.0.1", 7892), timeout=3):
                return True
        except OSError:
            pass
        if time.time() >= deadline:
            return False
        time.sleep(step)


def gh():
    for c in ("G:/code/tools/gh/gh.exe", "gh"):
        p = subprocess.run([c, "--version"], capture_output=True, text=True)
        if p.returncode == 0:
            return c
    return "gh"


def main():
    say("===== 行业日报补跑 %s %s =====" % (TODAY, datetime.datetime.now(TZ).strftime("%H:%M")))
    if not wait_proxy():
        say("[中断] 代理未就绪，跳过（云端 Actions 会兜底）")
        return 0

    _, out = run(["git", "pull", "-q", "--rebase"], cwd=ROOT)
    say(tail(out, 2))

    # 上次"提交成功但推送失败"的补推
    _, out = run(["git", "rev-list", "--count", "origin/main..HEAD"], cwd=ROOT)
    ahead = (out.strip().splitlines() or ["0"])[-1].strip()
    if ahead.isdigit() and int(ahead) > 0:
        say("→ 本地领先远端 %s 个提交，先补推" % ahead)
        code, out = run(["git", "push", "-q"], cwd=ROOT)
        say("→ 补推%s" % ("成功" if code == 0 else "失败: " + tail(out, 2)))

    code, out = run([gh(), "api", "repos/birdger/daily-industry-digest/commits?per_page=30",
                     "--jq", ".[].commit.message"])
    has = len([l for l in out.splitlines() if l.startswith("digest: %s" % TODAY)])
    say("远端今天行业日报提交数: %d" % has)
    if has > 0:
        say("→ 云端已产出，无需补跑")
        return 0

    say("→ 云端今天没产出，本地补跑")
    code, out = run([PY, "scripts/daily_digest.py"], cwd=ROOT, timeout=480)
    say(tail(out, 8))
    if code != 0:
        say("[警告] 生成器失败，不提交")
        return 1

    dfile = ROOT / "digests" / ("%s.md" % TODAY)
    head = dfile.read_text(encoding="utf-8", errors="replace")[:600] if dfile.exists() else ""
    if "去重聚合 0 条" in head or "抓到 0 条" in head:
        run(["git", "checkout", "--", "."], cwd=ROOT)
        say("[警告] 抓取全部失败（0 条），不提交空日报，本地改动已回滚")
        return 0

    run(["git", "add", "-A"], cwd=ROOT)
    code, out = run(["git", "diff", "--cached", "--quiet"], cwd=ROOT)
    if code == 0:
        say("→ 与远端一致，无需提交")
    else:
        run(["git", "commit", "-q", "-m", "digest: %s 行业日报（本地补跑）" % TODAY], cwd=ROOT)
        code, out = run(["git", "push", "-q"], cwd=ROOT)
        say("→ 已推送 GitHub%s" % ("" if code == 0 else "（失败，下次自动补推）"))

    say("===== 镜像到 Gitee / AtomGit / 极狐 =====")
    _, out = run([PY, str(WORKBENCH / "mirror_push.py")], cwd=WORKBENCH, timeout=600)
    say(tail(out, 6))
    say("===== 结束 =====")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    finally:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_DIR / ("industry_%s.log" % TODAY), "a", encoding="utf-8") as f:
            f.write("\n".join(_buf) + "\n")
    sys.exit(code)
