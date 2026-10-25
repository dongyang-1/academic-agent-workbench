#!/bin/bash
# 把学术全流程智能体工作台装成 macOS 常驻服务：开机自启 + 崩溃自动拉起。
# 双击运行即可（会申请一次权限，允许就行）。装好后 8088 永不掉线。

set -u
LABEL="cn.abstruct.aca-web"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
PORT=8088

echo "== 安装常驻服务 =="

# 1) 先清掉可能存在的旧实例，避免端口冲突
lsof -ti tcp:"$PORT" | xargs -r kill 2>/dev/null
launchctl bootout "gui/$(id -u)/${LABEL}" 2>/dev/null
sleep 1

# 2) 装载
launchctl bootstrap "gui/$(id -u)" "$PLIST"
sleep 1
launchctl kickstart -k "gui/$(id -u)/${LABEL}"

# 3) 等健康检查
echo -n "等待服务就绪"
for i in $(seq 1 30); do
  sleep 1
  echo -n "."
  if curl -s --noproxy '*' -m 2 -o /dev/null "http://127.0.0.1:${PORT}/api/health"; then break; fi
done
echo ""

# 4) 装不上就回退为普通后台启动，保证服务可用（哪怕不是常驻）
if ! curl -s --noproxy '*' -m 3 -o /dev/null "http://127.0.0.1:${PORT}/api/health"; then
  echo ""
  echo "常驻未生效，回退为普通后台启动…"
  cd "$(dirname "$0")" || exit 1
  PY="/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"
  nohup "$PY" -m uvicorn web_platform.app:app --host 127.0.0.1 --port "$PORT" \
    --log-level warning > /tmp/aca_8088.log 2>&1 &
  for i in $(seq 1 30); do
    sleep 1
    curl -s --noproxy '*' -m 2 -o /dev/null "http://127.0.0.1:${PORT}/api/health" && break
  done
fi

if curl -s --noproxy '*' -m 3 -o /dev/null "http://127.0.0.1:${PORT}/api/health"; then
  echo ""
  echo "✅ 服务已就绪 → http://127.0.0.1:${PORT}（常驻是否生效见上方提示）"
  open "http://127.0.0.1:${PORT}"
else
  echo ""
  echo "❌ 仍未就绪。请查看日志 /tmp/aca_8088.err.log"
  tail -15 /tmp/aca_8088.err.log 2>/dev/null
fi

echo ""
echo "—— 以后想停掉/卸载，双击 卸载常驻服务.command ——"
