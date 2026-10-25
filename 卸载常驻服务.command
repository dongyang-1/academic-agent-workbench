#!/bin/bash
# 卸载常驻服务：停掉后台进程并移除开机自启。

set -u
LABEL="cn.abstruct.aca-web"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
PORT=8088

echo "== 卸载常驻服务 =="
launchctl bootout "gui/$(id -u)/${LABEL}" 2>/dev/null
lsof -ti tcp:"$PORT" | xargs -r kill 2>/dev/null
rm -f "$PLIST"

if [ -f "$PLIST" ]; then
  echo "❌ plist 未能删除，可能需要手动：rm \"$PLIST\""
else
  echo "✅ 已卸载：不再开机自启，端口 $PORT 已释放。"
  echo "   需要临时启动时，双击 启动工作台.command。"
fi
