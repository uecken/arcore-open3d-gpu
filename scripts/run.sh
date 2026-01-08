#!/bin/bash
# GPU対応版ARCore + Open3Dサーバーの起動スクリプト
# 元のarcore-open3dフォルダの仮想環境を使用

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="/opt/arcore-open3d/venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "エラー: 仮想環境が見つかりません: $VENV_DIR"
    echo "元のarcore-open3dフォルダの仮想環境が必要です。"
    exit 1
fi

# 仮想環境をアクティベート
source "$VENV_DIR/bin/activate"

# 現在のディレクトリで実行
cd "$SCRIPT_DIR"

# サーバーを起動
echo "GPU対応版ARCore + Open3Dサーバーを起動します..."
echo "仮想環境: $VENV_DIR"
echo "作業ディレクトリ: $SCRIPT_DIR"
echo ""

python main.py "$@"

