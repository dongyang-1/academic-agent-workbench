#!/usr/bin/env bash
# 学术全流程智能体 · 一键跑通（macOS / Linux 通用）
# 用法：bash start.sh
# 可选环境变量：
#   ACA_PORT=8088        端口
#   ACA_HOST=127.0.0.1   监听地址（部署到服务器时用 0.0.0.0）
#   ACA_BASIC_USER / ACA_BASIC_PASS   开启 Basic Auth 口令

set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
cd "$ROOT" || exit 1

PORT="${ACA_PORT:-8088}"
HOST="${ACA_HOST:-127.0.0.1}"
LOG_DIR="$ROOT/logs"
LOG="$LOG_DIR/server.log"
mkdir -p "$LOG_DIR"

# ---------- 1. 选一个 Python（优先项目内 .venv，其次系统 Python） ----------
pick_python() {
  local p
  for p in "$ROOT/.venv/bin/python" "$ROOT/venv/bin/python" \
           /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 \
           /usr/local/bin/python3 /usr/bin/python3 "$(command -v python3 2>/dev/null)"; do
    if [ -n "$p" ] && [ -x "$p" ]; then echo "$p"; return 0; fi
  done
  return 1
}
PY="$(pick_python)" || { echo "❌ 找不到 python3，请先安装 Python 3.10+"; exit 1; }

VER="$("$PY" -c 'import sys;print("%d.%d"%sys.version_info[:2])')"
echo "Python: $PY ($VER)"

# ---------- 2. 依赖自检，缺什么装什么（只在缺失时才联网） ----------
NEED="fastapi uvicorn pydantic numpy pandas scipy matplotlib openpyxl yaml docx requests networkx"
MISSING="$("$PY" - "$NEED" <<'EOF' 2>/dev/null
import importlib.util, sys
need = sys.argv[1].split()
miss = []
for m in need:
    try:
        if importlib.util.find_spec(m) is None:
            miss.append(m)
    except Exception:
        miss.append(m)
print(" ".join(miss))
EOF
)"
if [ -n "${MISSING// /}" ]; then
  echo "缺少依赖：$MISSING → 正在安装…"
  "$PY" -m pip install --quiet --disable-pip-version-check -r "$ROOT/requirements.txt" \
    || "$PY" -m pip install --quiet --disable-pip-version-check --user -r "$ROOT/requirements.txt" \
    || { echo "❌ 依赖安装失败，请手动执行： $PY -m pip install -r requirements.txt"; exit 1; }
fi

# ---------- 3. 端口占用检测：已在跑就直接开浏览器 ----------
health_ok() { curl -s --noproxy '*' -m 3 -o /dev/null "http://127.0.0.1:$PORT/api/health" 2>/dev/null; }

if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1 || health_ok; then
  echo "端口 $PORT 已在监听，复用现有服务。"
else
  echo "正在启动服务 → http://${HOST}:${PORT} （日志：${LOG}）"
  # detach_start.py：double-fork + setsid，服务脱离终端、由 launchd 收养，
  # 关掉终端窗口或当前会话被回收都不会把它带走
  ACA_HOST="$HOST" ACA_PORT="$PORT" "$PY" "$ROOT/detach_start.py"
  for i in $(seq 1 40); do
    sleep 1
    health_ok && break
  done
fi

# ---------- 4. 结果 ----------
if health_ok; then
  echo ""
  echo "✅ 已就绪 → http://127.0.0.1:$PORT"
  if [ "$HOST" != "127.0.0.1" ] && [ "$HOST" != "localhost" ]; then
    echo "   给别人访问的地址（务必先设 Basic Auth）："
    case "$(uname -s)" in
      Darwin)
        for iface in en0 en1 en2; do
          ip="$(ipconfig getifaddr "$iface" 2>/dev/null)"
          [ -n "$ip" ] && echo "     局域网   http://${ip}:${PORT}"
        done ;;
      Linux)
        for ip in $(hostname -I 2>/dev/null); do echo "     局域网   http://${ip}:${PORT}"; done ;;
    esac
    if command -v tailscale >/dev/null 2>&1; then
      tsip="$(tailscale ip -4 2>/dev/null)"
      [ -n "$tsip" ] && echo "     Tailscale http://${tsip}:${PORT}"
    fi
  fi
  case "$(uname -s)" in
    Darwin) open "http://127.0.0.1:$PORT" 2>/dev/null ;;
    Linux)  xdg-open "http://127.0.0.1:$PORT" 2>/dev/null || true ;;
  esac
else
  echo "❌ 启动失败，日志尾部："
  tail -30 "$LOG" 2>/dev/null
  exit 1
fi
