---
作成日時: 2026-01-08 11:46:00
最終更新: 2026-01-08 11:46:00
---

# COLMAP CUDA要件について

## 問題

MVSパイプラインのテストを実行しましたが、COLMAPのPatch Match StereoがCUDAを要求しているため、現在インストールされているCOLMAP（CUDAなし版）では実行できません。

## エラーメッセージ

```
E20260108 11:45:42.694207  9806 mvs.cc:80] Dense stereo reconstruction requires CUDA, which is not available on your system.
```

## 状況

### 現在のCOLMAP

- **バージョン**: COLMAP 3.9.1
- **CUDAサポート**: なし（"without CUDA"）
- **インストール方法**: `sudo apt-get install colmap`
- **問題**: Patch Match Stereo（Dense MVS）がCUDA必須のため実行不可

### 成功したステップ

1. ✓ ARCore VIOポーズからCOLMAPモデル作成（成功）
2. ✓ 画像の歪み補正（成功）
3. ✗ Patch Match Stereo（失敗 - CUDA必須）

---

## 解決策

### オプション1: COLMAPをCUDA対応版で再インストール（推奨）

**COLMAPをCUDA対応版でビルド/インストール:**

```bash
# 依存関係のインストール
sudo apt-get update
sudo apt-get install -y \
    cmake \
    git \
    libboost-program-options-dev \
    libboost-filesystem-dev \
    libboost-graph-dev \
    libboost-system-dev \
    libeigen3-dev \
    libflann-dev \
    libfreeimage-dev \
    libmetis-dev \
    libgoogle-glog-dev \
    libgflags-dev \
    libsqlite3-dev \
    libglew-dev \
    qtbase5-dev \
    libqt5opengl5-dev \
    libcgal-dev \
    libceres-dev

# CUDAツールキットのインストール
sudo apt-get install -y nvidia-cuda-toolkit

# COLMAPをソースからビルド（CUDAサポートあり）
git clone https://github.com/colmap/colmap.git
cd colmap
mkdir build
cd build
cmake .. -DCMAKE_CUDA_ARCHITECTURES=native
make -j$(nproc)
sudo make install
```

**注意:**
- ビルドには時間がかかります（30分〜1時間）
- CUDAツールキットが必要です

---

### オプション2: 一時的にRGB-D統合（MiDaS）に戻す

MVSパイプラインを使用する前に、RGB-D統合（MiDaS深度推定）で処理を続けることができます。

**config.yaml:**
```yaml
processing:
  default_mode: "rgbd"  # MVSパイプラインを一時的に無効化
```

**使用方法:**
```bash
python reprocess_job.py 1611626e
```

---

## テスト結果の詳細

### 成功した部分

1. **COLMAPモデル作成**: ✓
   - ARCore VIOポーズからCOLMAPモデルファイル（`cameras.txt`, `images.txt`, `points3D.txt`）を正常に作成
   - 209フレームすべてのポーズを正しく変換

2. **画像の歪み補正**: ✓
   - `colmap image_undistorter`が正常に実行
   - 画像の歪み補正が完了

### 失敗した部分

1. **Patch Match Stereo**: ✗
   - CUDA必須エラー
   - COLMAPのDense MVS処理が実行不可

---

## 推奨される次のステップ

### 短期（今すぐ実行可能）

1. **RGB-D統合（MiDaS）に戻す**
   ```yaml
   processing:
     default_mode: "rgbd"
   ```
   ```bash
   python reprocess_job.py 1611626e
   ```

### 中期（COLMAP CUDA対応版をインストール後）

1. **COLMAPをCUDA対応版でインストール**
   - 上記の手順に従ってビルド/インストール

2. **MVSパイプラインで再処理**
   ```yaml
   processing:
     default_mode: "mvs"
   ```
   ```bash
   python reprocess_job_mvs.py 1611626e
   ```

---

## 参考情報

- COLMAP公式インストールガイド: https://colmap.github.io/install.html
- CUDA要件: Patch Match StereoとStereo FusionはCUDA必須

---

## まとめ

MVSパイプラインの実装は正常に動作していますが、COLMAPのPatch Match StereoがCUDAを要求するため、現在のCOLMAP（CUDAなし版）では実行できません。

**次のアクション:**
1. COLMAPをCUDA対応版で再インストール（推奨）
2. または、一時的にRGB-D統合（MiDaS）に戻す

