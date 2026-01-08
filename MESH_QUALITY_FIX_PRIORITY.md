# 3Dメッシュ品質改善：優先順位ガイド

## 🔴 最優先: Depthデータの確認（Step 1）

**なぜ最優先か:**
- 「波打ったカーテン状の面」の**最も可能性が高い原因**はDepthデータの問題
- Viewerに「Depth source: Unknown」と表示されている場合、Depthが期待通りに入っていない可能性が高い
- Depthが無い/壊れている場合、TSDF統合では「きれいな部屋メッシュ」は基本できない

### 実施方法

```bash
# 1. 診断スクリプトを実行
python diagnose_depth.py <job_id>

# 2. 結果を確認
# - has_depth: false → Step 2-Aへ
# - has_depth: true かつ avg_std_dev > 1.5m → Step 2-Bへ
```

### 確認項目

1. **Depthフレームが本当に入っているか**
   - Android側ログにDepth画像が保存されているか
   - フレーム数がRGBと一致しているか

2. **Depthの値が有効か**
   - 0〜数mのレンジになっているか（全0、全255、NaNだらけはNG）
   - 有効ピクセル比が70%以上か
   - 標準偏差が1.5m以下か

---

## 📋 Step 2-A: Depthデータが無い場合

### 症状
- `diagnose_depth.py`で `has_depth: false`
- `frames_with_depth: 0`

### 対処法（優先順位順）

#### 1. 深度推定を有効化（最も簡単）

`config.yaml`を編集:
```yaml
depth_estimation:
  enable: true
  force_use: true  # DepthデータがあってもMiDaSで再推定
  model: "DPT_Large"
  device: "cuda"
```

**メリット:**
- 実装済み、すぐ使える
- GPUで高速処理可能

**デメリット:**
- 推定Depthは実際のDepthよりノイジー
- → Step 2-Bの対策も必要

#### 2. COLMAPパイプラインに切り替え

**メリット:**
- ARCore Depthなしでも高品質なメッシュが生成可能
- テクスチャマッピングも可能

**デメリット:**
- 処理時間が長い（数時間）
- 実装が必要

#### 3. NeRF / 3D Gaussian Splatting

**メリット:**
- 最高品質

**デメリット:**
- メッシュ抽出が必要
- 処理時間が非常に長い
- 実装が必要

---

## 📋 Step 2-B: Depthデータがノイジーな場合（Pixel 7 Proなど）

### 症状
- `has_depth: true`
- `avg_std_dev > 1.5m` (深度の標準偏差が大きい)
- ARCore推定Depth（Motion Stereo + ML）を使用している

### 対処法（優先順位順）

#### 🔧 1. TSDFパラメータを「粗く」する（最も効果的・即効性あり）

**現状の問題:**
- `voxel_length: 0.01m` → 細かすぎてノイズを彫刻している
- `depth_trunc: 3.0m` → 遠距離Depthが一番荒い

**推奨設定変更 (`config.yaml`):**
```yaml
processing:
  tsdf:
    voxel_length: 0.04  # 0.01 → 0.04m (4cm) - ノイズを飲み込ませる
    sdf_trunc: 0.32     # 0.04 * 8 = 0.32
  
  depth:
    trunc: 2.5          # 3.0 → 2.5m - 遠距離Depthを除外
```

**効果:**
- ✅ 細かいノイズがボクセルサイズで吸収される
- ✅ 遠距離のノイズが除去される
- ✅ メモリ使用量も減少
- ✅ 即座に効果が出る

**実装難易度:** ⭐ (既存設定を変更するだけ)

#### 🔧 2. Depth前処理の強化（効果大）

**現在の設定確認:**
```yaml
depth:
  filter_noise: true        # ✓ 有効
  bilateral_filter: true    # ✓ 有効
```

**追加推奨（実装が必要）:**
- 穴埋め（inpainting）
- Flying pixel除去
- Confidenceベースのフィルタリング

**実装難易度:** ⭐⭐ (基本的なフィルタは実装済み、追加実装が必要)

#### 🔧 3. フレーム間引き（Frame Sampling）（効果中）

**問題:**
- 30fpsで記録されたフレームを全て使用
- 似たフレームを大量に入れると、微妙な姿勢誤差が積み上がる

**対策:**
- 1-2 fpsに間引く（動くスキャンの場合）
- 0.5-1 fpsに間引く（静止スキャンの場合）

**実装難易度:** ⭐⭐ (`rgbd_integration_gpu.py`の`process_session`に追加)

**効果:**
- ✅ 姿勢誤差の累積を減らす
- ✅ 処理時間の短縮

#### 🔧 4. 姿勢（VIO）の最適化（上級・効果大だが実装が複雑）

**問題:**
- ARCore VIOが少しズレていると、TSDF統合時に段差が積み上がる

**対策:**
- Open3DのPose Graph Optimization
- RGBD Odometryで微調整

**実装難易度:** ⭐⭐⭐⭐ (実装が複雑、現時点では未実装)

#### 🔧 5. メッシュ後処理の調整（最後の手段）

**問題:**
- 根本原因（Depth/TSDF設定）が解決できない場合の対症療法

**設定変更:**
```yaml
mesh:
  smoothing:
    iterations: 3  # 5 → 3 に減らす（やりすぎ注意）
    lambda_filter: 0.3  # 0.5 → 0.3 に減らす
  subdivision:
    enable: false  # ノイズメッシュには細分化は逆効果
```

**実装難易度:** ⭐ (設定変更のみ)

**効果:**
- ⚠️ 限定的（根本原因が解決されないと限界がある）

---

## 📊 推奨実施順序（まとめ）

### 即座に実施（コスト: 無料、時間: 5分）

1. ✅ **Depth診断スクリプトを実行**
   ```bash
   python diagnose_depth.py <job_id>
   ```

2. ✅ **TSDFパラメータを粗くする** (`config.yaml`)
   - `voxel_length: 0.01 → 0.04`
   - `depth_trunc: 3.0 → 2.5`

3. ✅ **Depth前処理を確認** (`config.yaml`)
   - `bilateral_filter: true` を確認

### 次に実施（コスト: 無料、時間: 30分）

4. ⚙️ **フレーム間引きを実装**
   - 1-2 fpsに減らす

5. ⚙️ **Depth前処理の強化**
   - 穴埋め、飛び値除去

### 必要に応じて（コスト: 中〜高、時間: 数時間〜数日）

6. 🔄 **深度推定を有効化** (Depthデータが無い場合)
   - `depth_estimation.force_use: true`

7. 🔄 **COLMAPパイプライン** (Depthデータが無い場合、またはより高品質が必要な場合)

8. 🔄 **姿勢最適化** (上級者向け)

---

## 🎯 期待される効果

### Step 1のみ実施（TSDFパラメータ調整）

- 波打ちが**50-70%改善**することが期待できる
- メッシュがより滑らかに
- 処理時間とメモリ使用量が減少

### Step 1 + Step 2-B.2, 2-B.3実施（Depth前処理 + フレーム間引き）

- 波打ちが**70-85%改善**することが期待できる
- より詳細な改善

### Step 1 + 全対策実施

- 波打ちが**85-95%改善**することが期待できる
- 実用的な品質レベルに到達

---

## 🆘 それでも改善しない場合

以下の選択肢を検討:

1. **ハードウェアのアップグレード**
   - iPhone 15 Pro / iPad Pro (LiDAR)
   - Intel RealSense D455
   - Azure Kinect DK

2. **別のパイプラインに切り替え**
   - COLMAP
   - NeRF / 3D Gaussian Splatting

3. **メッシュ編集ソフトで後処理**
   - MeshLab
   - CloudCompare

---

## 📝 実装例

### TSDFパラメータの変更例（config.yaml）

**変更前（ノイジーDepthに不向き）:**
```yaml
processing:
  tsdf:
    voxel_length: 0.01  # 細かすぎる
    sdf_trunc: 0.08
  depth:
    trunc: 3.0          # 遠距離まで含む
```

**変更後（ノイジーDepth向け）:**
```yaml
processing:
  tsdf:
    voxel_length: 0.04  # ノイズを飲み込ませる
    sdf_trunc: 0.32
  depth:
    trunc: 2.5          # 遠距離Depthを除外
```

### メッシュ再生成

```bash
# 設定変更後、メッシュを再生成
python regenerate_mesh.py <job_id> existing

# 結果を確認
python view_mesh.py data/results/<job_id>/mesh.ply
```

