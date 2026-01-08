---
作成日時: 2026-01-08 11:55:00
最終更新: 2026-01-08 11:55:00
---

# COLMAP CUDA対応版ビルド状況

## ビルド開始

COLMAP CUDA対応版のビルドを開始しました。

**開始時刻:** 2026-01-08 11:54:00

---

## 環境情報

### CUDA環境
- **NVIDIA Driver:** 580.95.05 (Driver Version: 561.09)
- **CUDA Version:** 12.6 (nvcc 12.0.140)
- **GPU:** NVIDIA GeForce GTX 1660 Ti
- **CUDA Architecture:** sm_75 (Turing)

### ビルド設定
- **COLMAP Source:** `/opt/arcore-open3d-gpu/colmap_build/src`
- **Build Directory:** `/opt/arcore-open3d-gpu/colmap_build/build`
- **CUDA Enabled:** ✓
- **GUI Disabled:** ✓ (サーバー環境のため)

---

## 進捗状況

### 依存関係のインストール
- ✓ すべての依存関係がインストール済み
- ✓ OpenImageIOもインストール済み

### CMake設定
- ✓ CMake設定が正常に完了
- ✓ CUDAサポートが有効化
- ✓ すべての依存関係が検出された

### ビルド
- **進捗:** 約33%（開始後約1分）
- **ステータス:** バックグラウンドで実行中
- **ログファイル:** `/tmp/colmap_build_final.log`

**ビルド中のファイル例:**
- CUDA関連: `cudacc.cc.o` → `libcolmap_util_cuda.a` ✓
- その他: faiss, PoseLib, VLFeatなど

---

## ビルド完了の確認方法

```bash
# 進捗を確認
tail -f /tmp/colmap_build_final.log

# ビルドプロセスを確認
ps aux | grep -E "cmake|make.*colmap" | grep -v grep

# インストール完了を確認
colmap help | head -3
```

---

## 予想される完了時間

- **通常:** 30-60分（12コアCPU、並列ビルド）
- **遅い場合:** 1-2時間

---

## 次のステップ

ビルド完了後:
1. COLMAPのインストール確認
2. CUDAサポートの確認
3. MVSパイプラインでのテスト実行

---

## トラブルシューティング

### ビルドが停止した場合

```bash
# ログを確認
tail -100 /tmp/colmap_build_final.log

# エラーを確認
grep -i error /tmp/colmap_build_final.log | tail -10
```

### 再ビルドが必要な場合

```bash
cd /opt/arcore-open3d-gpu/colmap_build/build
rm -rf *
cd /opt/arcore-open3d-gpu
./build_colmap_cuda.sh
```

---

## 注意事項

- ビルド中はCPUとメモリを大量に使用します
- ディスク容量が必要です（数GB）
- ビルドが完了するまで待機してください

