# メッシュ表示ツール使用方法

## 前提条件

仮想環境を有効化する必要があります。

```bash
# 仮想環境を有効化
source venv/bin/activate

# または、元のプロジェクトの仮想環境を使用
source /opt/arcore-open3d/venv/bin/activate
```

## 使用方法

### 1. ジョブIDを指定して表示

```bash
python view_mesh.py 6d7cd464
```

### 2. ファイルパスを直接指定

```bash
python view_mesh.py data/results/6d7cd464/mesh.ply
```

### 3. 元のメッシュ（簡略化前）を表示

```bash
python view_mesh.py 6d7cd464 --original
```

### 4. カスタム結果ディレクトリを指定

```bash
python view_mesh.py 6d7cd464 --results-dir /path/to/results
```

## 操作方法

- **マウス左ドラッグ**: 回転
- **マウス右ドラッグ**: 平行移動
- **マウスホイール**: ズーム
- **'Q' または 'Esc'**: 終了
- **'R'**: リセット
- **'W'**: ワイヤーフレーム表示切り替え
- **'L'**: ライティング切り替え
- **'P'**: 点群表示切り替え

## トラブルシューティング

### Open3Dがインストールされていない場合

```bash
# 仮想環境を有効化
source venv/bin/activate

# Open3Dをインストール（必要な場合）
pip install open3d
```

### 仮想環境が見つからない場合

元のプロジェクトの仮想環境を使用:

```bash
source /opt/arcore-open3d/venv/bin/activate
python view_mesh.py 6d7cd464
```


