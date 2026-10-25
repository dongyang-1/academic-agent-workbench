#!/usr/bin/env bash
# 常驻服务（launchd）入口：exec 方式启动 uvicorn，保证 launchd 能持续托管并自动拉起。
# 环境变量统一放在同目录的 .env.sh 里，改完执行：
#   launchctl kickstart -k "gui/$(id -u)/cn.abstruct.aca-web"
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
cd "$ROOT" || exit 1

if [ -f "$ROOT/.env.sh" ]; then
  . "$ROOT/.env.sh"
fi

PY="/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"
[ -x "$PY" ] || PY="$(command -v python3)"

exec "$PY" -m uvicorn web_platform.app:app \
  --host "${ACA_HOST:-127.0.0.1}" \
  --port "${ACA_PORT:-8088}" \
  --log-level "${ACA_LOG_LEVEL:-info}"
