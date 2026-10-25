#!/usr/bin/env bash
# 保活：端口没在监听就拉起服务。由 cron 每分钟调用，不开浏览器、不重复启动。
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
cd "$ROOT" || exit 1
PORT="${ACA_PORT:-8088}"
HOST="${ACA_HOST:-127.0.0.1}"
LOG="$ROOT/logs/server.log"
mkdir -p "$ROOT/logs"

if curl -s --noproxy '*' -m 3 -o /dev/null "http://127.0.0.1:$PORT/api/health"; then
  exit 0   # 正常，什么都不做
fi

if [ -x "$ROOT/.venv/bin/python" ]; then
  PY="$ROOT/.venv/bin/python"
else
  PY="/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"
  [ -x "$PY" ] || PY="$(command -v python3)"
fi

echo "[$(date '+%F %T')] 检测到服务未运行，正在拉起…" >> "$LOG"
ACA_HOST="$HOST" ACA_PORT="$PORT" "$PY" "$ROOT/detach_start.py"
exit 0
