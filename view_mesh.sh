#!/bin/bash
# メッシュ表示ツールのラッパースクリプト
# 仮想環境を自動的に有効化してから実行

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="/opt/arcore-open3d/venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "❌ エラー: 仮想環境が見つかりません: $VENV_DIR"
    echo "元のarcore-open3dフォルダの仮想環境が必要です。"
    exit 1
fi

# 仮想環境をアクティベート
source "$VENV_DIR/bin/activate"

# メッシュ表示ツールを実行
cd "$SCRIPT_DIR"
python view_mesh.py "$@"

