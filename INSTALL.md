# インストール手順

## 推奨方法: 元の仮想環境を再利用

このGPU対応版は、元の`arcore-open3d`フォルダの仮想環境を再利用します。

### 1. 元の仮想環境の確認

```bash
# 元の仮想環境が存在することを確認
ls /opt/arcore-open3d/venv/bin/python
/opt/arcore-open3d/venv/bin/python --version
```

### 2. 起動スクリプトを使用（推奨）

```bash
cd /opt/arcore-open3d-gpu
./run.sh
```

このスクリプトは自動的に元の仮想環境をアクティベートしてからサーバーを起動します。

### 3. 手動で仮想環境をアクティベート

```bash
# 元の仮想環境をアクティベート
source /opt/arcore-open3d/venv/bin/activate

# サーバーを起動
cd /opt/arcore-open3d-gpu
python main.py
```

## 元の仮想環境にパッケージを追加する場合

### CUDA対応のPyTorchをインストール

元の仮想環境にCUDA対応のPyTorchがインストールされていない場合：

```bash
# 元の仮想環境をアクティベート
source /opt/arcore-open3d/venv/bin/activate

# CUDA 12.1版（最新）
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# または、CUDA 11.8版
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

### インストール済みパッケージの確認

```bash
/opt/arcore-open3d/venv/bin/pip list | grep -E "(open3d|torch|numpy|fastapi)"
```

## 新しい仮想環境を作成する場合

元の仮想環境が利用できない場合のみ、新しい仮想環境を作成してください：

```bash
# Python 3.12の仮想環境を作成（推奨）
python3.12 -m venv venv

# 仮想環境をアクティベート
source venv/bin/activate

# 依存関係をインストール
pip install -r server_open3d/requirements.txt
```

**注意**: Open3DはPython 3.8-3.12をサポートしています。Python 3.13はまだサポートされていません。

