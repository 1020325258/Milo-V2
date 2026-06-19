#!/bin/bash
# 快捷运行脚本
# 用法: ./run.sh [目录路径]
# 示例: ./run.sh /path/to/your/java/project

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="/Users/zqy/work/AI-Project/CodeWiki/.venv/bin/python"

if [ -z "$1" ]; then
    # 默认使用 personal 目录
    REPO_PATH="/Users/zqy/work/project/nrs-sales-project/utopia-nrs-sales-project-service/src/main/java/com/ke/utopia/nrs/salesproject/service/contract/v2/personal"
else
    REPO_PATH="$1"
fi

$PYTHON "$SCRIPT_DIR/main.py" "$REPO_PATH"
