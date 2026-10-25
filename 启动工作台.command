#!/bin/bash
# 学术全流程智能体 · 双击启动（macOS）
# 实际逻辑在 start.sh 里，方便以后原样搬到 Linux 服务器上跑。
cd "$(dirname "$0")" || exit 1
exec bash ./start.sh
