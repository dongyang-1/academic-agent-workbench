#!/usr/bin/env bash
# 停止工作台服务
set -u
PORT="${ACA_PORT:-8088}"
PID_FILE="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)/logs/server.pid"

if [ -f "$PID_FILE" ]; then
  PID="$(cat "$PID_FILE" 2>/dev/null)"
  [ -n "${PID:-}" ] && kill "$PID" 2>/dev/null && echo "已发送停止信号给 PID $PID"
  rm -f "$PID_FILE"
fi

if command -v lsof >/dev/null 2>&1; then
  PIDS="$(lsof -ti tcp:"$PORT" 2>/dev/null)"
  if [ -n "${PIDS// /}" ]; then
    echo "$PIDS" | xargs kill 2>/dev/null && echo "已停止端口 $PORT 上的进程"
  else
    echo "端口 $PORT 无进程。"
  fi
else
  pkill -f "uvicorn web_platform.app:app" 2>/dev/null && echo "已停止 uvicorn 进程"
fi
