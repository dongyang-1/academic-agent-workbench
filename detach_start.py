#!/usr/bin/env python3
"""以「完全脱离终端」的方式启动 uvicorn：double-fork + setsid。

这样服务不属于任何终端会话/进程组，关掉启动它的窗口、或当前会话被回收都不会带走它。
父进程立刻返回，服务由 launchd(pid 1) 收养。
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(ROOT, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG = os.path.join(LOG_DIR, "server.log")
HOST = os.environ.get("ACA_HOST", "127.0.0.1")
PORT = os.environ.get("ACA_PORT", "8088")
PY = sys.executable

# 第一次 fork：父进程立即退出
if os.fork() > 0:
    sys.exit(0)

os.setsid()  # 新会话、新进程组，脱离终端

# 第二次 fork：确保不再是会话首进程，无法再获得终端
if os.fork() > 0:
    sys.exit(0)

os.chdir(ROOT)
fd = os.open(LOG, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
os.dup2(fd, 1)
os.dup2(fd, 2)
os.dup2(os.open(os.devnull, os.O_RDONLY), 0)

os.execv(PY, [PY, "-m", "uvicorn", "web_platform.app:app",
              "--host", HOST, "--port", PORT, "--log-level", "info"])
