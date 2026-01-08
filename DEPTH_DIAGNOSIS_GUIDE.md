---
作成日時: 2026-01-08 10:04:37
最終更新: 2026-01-08 10:14:57
---

# Depth診断とメッシュ品質改善ガイド

## 🔴 最優先: Depthデータの確認

「波打ったカーテン状のメッシュ」が発生する場合、**最も可能性が高い原因はDepthデータの問題**です。

### Step 1: Depthデータの診断

```bash
# 仮想環境をアクティブ化
source venv/bin/activate

# 診断スクリプトを実行
python diagnose_depth.py <job_id>

# 結果をJSONファイルに保存
python diagnose_depth.py <job_id> --output diagnosis_result.json
```

### Step 2: 診断結果の解釈

#### A. Depthデータが存在しない場合

**症状:**
- `has_depth: false`
- `frames_with_depth: 0`

**対処法（優先順位）:**
1. **深度推定を有効化** (`config.yaml`)
   ```yaml
   depth_estimation:
     enable: true
     force_use: true  # DepthデータがあってもMiDaSで再推定
     model: "DPT_Large"
     device: "cuda"
   ```

2. **COLMAPパイプラインに切り替え**
   - ARCore Depthなしでも高品質なメッシュが生成可能
   - 処理時間は長い（数時間）

3. **NeRF / 3D Gaussian Splatting**
   - 最高品質だが、メッシュ抽出が必要

#### B. Depthデータが存在するが品質が悪い場合

**症状:**
- `avg_std_dev > 1.5m` (深度の標準偏差が大きい)
- `avg_valid_ratio < 0.7` (有効ピクセルが少ない)
- `depth_range_m[1] > 10.0m` (異常に大きな深度値)

**対処法（優先順位）:**

### 🔧 1. TSDFパラメータを「粗く」する（最も効果的）

`config.yaml`を編集:

```yaml
processing:
  tsdf:
    voxel_length: 0.03  # 0.01 → 0.03-0.06m に変更（ノイズを飲み込ませる）
    sdf_trunc: 0.24     # voxel_lengthの8倍程度（0.03 * 8 = 0.24）
  
  depth:
    trunc: 2.5          # 3.0 → 2.5-4.0m に短縮（遠距離Depthが一番荒い）
    # 深度前処理を有効化
    filter_noise: true
    bilateral_filter: true
    bilateral_d: 5
    bilateral_sigma_color: 50.0
    bilateral_sigma_space: 50.0
```

**効果:**
- 細かいノイズがボクセルサイズで吸収される
- 遠距離のノイズが除去される
- メモリ使用量も減少

### 🔧 2. Depth前処理を強化

現在の`config.yaml`には基本的なフィルタが含まれていますが、より強力な前処理を追加できます。

**推奨設定:**
```yaml
depth:
  filter_noise: true        # 統計的外れ値除去
  bilateral_filter: true    # エッジ保持平滑化
  bilateral_d: 5
  bilateral_sigma_color: 50.0
  bilateral_sigma_space: 50.0
  # 追加オプション（実装が必要）
  inpaint_holes: true       # 穴埋め
  flying_pixel_removal: true # 飛び値除去
  confidence_threshold: 0.5  # 信頼度しきい値（ARCore Depth Confidence使用時）
```

### 🔧 3. フレームの間引き（Frame Sampling）

ARCoreデータは通常30fpsで記録されますが、TSDF統合には全フレームは不要です。

**実装方法（`rgbd_integration_gpu.py`の`process_session`メソッド）:**
```python
# フレームを間引く（例: 2fpsに減らす）
frames = parser.get_frames_with_depth()
frame_interval = max(1, len(frames) // (target_fps * duration_seconds))
sampled_frames = frames[::frame_interval]
```

**推奨:**
- 動くスキャン: 1-2 fps
- 静止スキャン: 0.5-1 fps

**効果:**
- 似たフレームの重複を減らす
- 姿勢誤差の累積を減らす
- 処理時間の短縮

### 🔧 4. 姿勢（VIO）の最適化（上級）

ARCoreのVIOが少しズレていると、TSDF統合時に段差が積み上がります。

**対策:**
- Open3DのPose Graph Optimizationを使用
- RGBD Odometryで微調整

**実装の複雑度:** 高い（現時点では未実装）

### 🔧 5. メッシュ後処理（最後の手段）

根本原因（Depth/TSDF設定）が解決できない場合の対症療法:

```yaml
mesh:
  quality_improvement:
    enable: true
    subdivision:
      enable: false  # ノイズメッシュには細分化は逆効果
    smoothing:
      enable: true
      method: "laplacian"
      iterations: 3  # 5 → 3 に減らす（やりすぎ注意）
      lambda_filter: 0.3  # 0.5 → 0.3 に減らす
```

## 📊 優先順位まとめ

### 最優先（即座に実施）

1. **Depth診断スクリプトを実行**
   ```bash
   python diagnose_depth.py <job_id>
   ```

2. **Depthデータが無い場合**
   - `depth_estimation.force_use: true` を設定

3. **Depthデータがノイジーな場合**
   - `voxel_length: 0.01 → 0.03-0.06m`
   - `depth_trunc: 3.0 → 2.5-4.0m`
   - `depth.bilateral_filter: true` を確認

### 次に実施（Depthがノイジーな場合）

4. **フレーム間引きの実装**
   - 1-2 fpsに減らす

5. **Depth前処理の強化**
   - 穴埋め、飛び値除去

### 最後の手段

6. **メッシュ後処理の調整**
   - 平滑化パラメータの調整

7. **姿勢最適化（上級）**
   - Pose Graph Optimization

## 🔍 現在の設定確認

現在の`config.yaml`設定（推奨値適用済み）:

```yaml
processing:
  tsdf:
    voxel_length: 0.04  # ✓ ノイズを飲み込ませる設定
    sdf_trunc: 0.32     # ✓ 適切な値
  
  depth:
    trunc: 7.0          # ✓ 診断結果の99パーセンタイル値（無効値を除外）
    filter_noise: true  # ✓ 有効
    bilateral_filter: true  # ✓ 有効
```

**診断結果に基づく推奨値（有効深度ピクセル0.4%の場合）:**

```yaml
processing:
  tsdf:
    voxel_length: 0.04  # 0.01 → 0.04m (4cm) - ノイズを飲み込ませる
    sdf_trunc: 0.32     # 0.04 * 8 = 0.32
  
  depth:
    trunc: 7.0          # 3.0 → 7.0m（診断結果の99パーセンタイル値、無効値マーカー65m以上を除外）
    filter_noise: true
    bilateral_filter: true
    bilateral_d: 5
    bilateral_sigma_color: 50.0
    bilateral_sigma_space: 50.0
```

**注意:**
- 有効深度ピクセルが0.4%と非常に少ない場合、Androidアプリ側で深度解像度を上げることを強く推奨
- 現在の160x90解像度は非常に低い（推奨: 320x240以上）
- `ANDROID_DEPTH_RESOLUTION_GUIDE.md`を参照してAndroidアプリ側の設定を確認してください

## 📝 次のステップ

1. 診断スクリプトを実行してDepth品質を確認
2. 結果に基づいて上記の対処法を適用
3. メッシュを再生成: `python regenerate_mesh.py <job_id> existing`
4. 結果を確認: `python view_mesh.py data/results/<job_id>/mesh.ply`

## 🆘 それでも改善しない場合

- **COLMAPパイプライン**への移行を検討
- **NeRF / 3D Gaussian Splatting**の使用を検討
- ハードウェアのアップグレード（LiDAR搭載端末など）

最終更新: 2026-01-08 10:14:57
---

# Depth診断とメッシュ品質改善ガイド

## 🔴 最優先: Depthデータの確認

「波打ったカーテン状のメッシュ」が発生する場合、**最も可能性が高い原因はDepthデータの問題**です。

### Step 1: Depthデータの診断

```bash
# 仮想環境をアクティブ化
source venv/bin/activate

# 診断スクリプトを実行
python diagnose_depth.py <job_id>

# 結果をJSONファイルに保存
python diagnose_depth.py <job_id> --output diagnosis_result.json
```

### Step 2: 診断結果の解釈

#### A. Depthデータが存在しない場合

**症状:**
- `has_depth: false`
- `frames_with_depth: 0`

**対処法（優先順位）:**
1. **深度推定を有効化** (`config.yaml`)
   ```yaml
   depth_estimation:
     enable: true
     force_use: true  # DepthデータがあってもMiDaSで再推定
     model: "DPT_Large"
     device: "cuda"
   ```

2. **COLMAPパイプラインに切り替え**
   - ARCore Depthなしでも高品質なメッシュが生成可能
   - 処理時間は長い（数時間）

3. **NeRF / 3D Gaussian Splatting**
   - 最高品質だが、メッシュ抽出が必要

#### B. Depthデータが存在するが品質が悪い場合

**症状:**
- `avg_std_dev > 1.5m` (深度の標準偏差が大きい)
- `avg_valid_ratio < 0.7` (有効ピクセルが少ない)
- `depth_range_m[1] > 10.0m` (異常に大きな深度値)

**対処法（優先順位）:**

### 🔧 1. TSDFパラメータを「粗く」する（最も効果的）

`config.yaml`を編集:

```yaml
processing:
  tsdf:
    voxel_length: 0.03  # 0.01 → 0.03-0.06m に変更（ノイズを飲み込ませる）
    sdf_trunc: 0.24     # voxel_lengthの8倍程度（0.03 * 8 = 0.24）
  
  depth:
    trunc: 2.5          # 3.0 → 2.5-4.0m に短縮（遠距離Depthが一番荒い）
    # 深度前処理を有効化
    filter_noise: true
    bilateral_filter: true
    bilateral_d: 5
    bilateral_sigma_color: 50.0
    bilateral_sigma_space: 50.0
```

**効果:**
- 細かいノイズがボクセルサイズで吸収される
- 遠距離のノイズが除去される
- メモリ使用量も減少

### 🔧 2. Depth前処理を強化

現在の`config.yaml`には基本的なフィルタが含まれていますが、より強力な前処理を追加できます。

**推奨設定:**
```yaml
depth:
  filter_noise: true        # 統計的外れ値除去
  bilateral_filter: true    # エッジ保持平滑化
  bilateral_d: 5
  bilateral_sigma_color: 50.0
  bilateral_sigma_space: 50.0
  # 追加オプション（実装が必要）
  inpaint_holes: true       # 穴埋め
  flying_pixel_removal: true # 飛び値除去
  confidence_threshold: 0.5  # 信頼度しきい値（ARCore Depth Confidence使用時）
```

### 🔧 3. フレームの間引き（Frame Sampling）

ARCoreデータは通常30fpsで記録されますが、TSDF統合には全フレームは不要です。

**実装方法（`rgbd_integration_gpu.py`の`process_session`メソッド）:**
```python
# フレームを間引く（例: 2fpsに減らす）
frames = parser.get_frames_with_depth()
frame_interval = max(1, len(frames) // (target_fps * duration_seconds))
sampled_frames = frames[::frame_interval]
```

**推奨:**
- 動くスキャン: 1-2 fps
- 静止スキャン: 0.5-1 fps

**効果:**
- 似たフレームの重複を減らす
- 姿勢誤差の累積を減らす
- 処理時間の短縮

### 🔧 4. 姿勢（VIO）の最適化（上級）

ARCoreのVIOが少しズレていると、TSDF統合時に段差が積み上がります。

**対策:**
- Open3DのPose Graph Optimizationを使用
- RGBD Odometryで微調整

**実装の複雑度:** 高い（現時点では未実装）

### 🔧 5. メッシュ後処理（最後の手段）

根本原因（Depth/TSDF設定）が解決できない場合の対症療法:

```yaml
mesh:
  quality_improvement:
    enable: true
    subdivision:
      enable: false  # ノイズメッシュには細分化は逆効果
    smoothing:
      enable: true
      method: "laplacian"
      iterations: 3  # 5 → 3 に減らす（やりすぎ注意）
      lambda_filter: 0.3  # 0.5 → 0.3 に減らす
```

## 📊 優先順位まとめ

### 最優先（即座に実施）

1. **Depth診断スクリプトを実行**
   ```bash
   python diagnose_depth.py <job_id>
   ```

2. **Depthデータが無い場合**
   - `depth_estimation.force_use: true` を設定

3. **Depthデータがノイジーな場合**
   - `voxel_length: 0.01 → 0.03-0.06m`
   - `depth_trunc: 3.0 → 2.5-4.0m`
   - `depth.bilateral_filter: true` を確認

### 次に実施（Depthがノイジーな場合）

4. **フレーム間引きの実装**
   - 1-2 fpsに減らす

5. **Depth前処理の強化**
   - 穴埋め、飛び値除去

### 最後の手段

6. **メッシュ後処理の調整**
   - 平滑化パラメータの調整

7. **姿勢最適化（上級）**
   - Pose Graph Optimization

## 🔍 現在の設定確認

現在の`config.yaml`設定（推奨値適用済み）:

```yaml
processing:
  tsdf:
    voxel_length: 0.04  # ✓ ノイズを飲み込ませる設定
    sdf_trunc: 0.32     # ✓ 適切な値
  
  depth:
    trunc: 7.0          # ✓ 診断結果の99パーセンタイル値（無効値を除外）
    filter_noise: true  # ✓ 有効
    bilateral_filter: true  # ✓ 有効
```

**診断結果に基づく推奨値（有効深度ピクセル0.4%の場合）:**

```yaml
processing:
  tsdf:
    voxel_length: 0.04  # 0.01 → 0.04m (4cm) - ノイズを飲み込ませる
    sdf_trunc: 0.32     # 0.04 * 8 = 0.32
  
  depth:
    trunc: 7.0          # 3.0 → 7.0m（診断結果の99パーセンタイル値、無効値マーカー65m以上を除外）
    filter_noise: true
    bilateral_filter: true
    bilateral_d: 5
    bilateral_sigma_color: 50.0
    bilateral_sigma_space: 50.0
```

**注意:**
- 有効深度ピクセルが0.4%と非常に少ない場合、Androidアプリ側で深度解像度を上げることを強く推奨
- 現在の160x90解像度は非常に低い（推奨: 320x240以上）
- `ANDROID_DEPTH_RESOLUTION_GUIDE.md`を参照してAndroidアプリ側の設定を確認してください

## 📝 次のステップ

1. 診断スクリプトを実行してDepth品質を確認
2. 結果に基づいて上記の対処法を適用
3. メッシュを再生成: `python regenerate_mesh.py <job_id> existing`
4. 結果を確認: `python view_mesh.py data/results/<job_id>/mesh.ply`

## 🆘 それでも改善しない場合

- **COLMAPパイプライン**への移行を検討
- **NeRF / 3D Gaussian Splatting**の使用を検討
- ハードウェアのアップグレード（LiDAR搭載端末など）

最終更新: 2026-01-08 10:14:57
---

# Depth診断とメッシュ品質改善ガイド

## 🔴 最優先: Depthデータの確認

「波打ったカーテン状のメッシュ」が発生する場合、**最も可能性が高い原因はDepthデータの問題**です。

### Step 1: Depthデータの診断

```bash
# 仮想環境をアクティブ化
source venv/bin/activate

# 診断スクリプトを実行
python diagnose_depth.py <job_id>

# 結果をJSONファイルに保存
python diagnose_depth.py <job_id> --output diagnosis_result.json
```

### Step 2: 診断結果の解釈

#### A. Depthデータが存在しない場合

**症状:**
- `has_depth: false`
- `frames_with_depth: 0`

**対処法（優先順位）:**
1. **深度推定を有効化** (`config.yaml`)
   ```yaml
   depth_estimation:
     enable: true
     force_use: true  # DepthデータがあってもMiDaSで再推定
     model: "DPT_Large"
     device: "cuda"
   ```

2. **COLMAPパイプラインに切り替え**
   - ARCore Depthなしでも高品質なメッシュが生成可能
   - 処理時間は長い（数時間）

3. **NeRF / 3D Gaussian Splatting**
   - 最高品質だが、メッシュ抽出が必要

#### B. Depthデータが存在するが品質が悪い場合

**症状:**
- `avg_std_dev > 1.5m` (深度の標準偏差が大きい)
- `avg_valid_ratio < 0.7` (有効ピクセルが少ない)
- `depth_range_m[1] > 10.0m` (異常に大きな深度値)

**対処法（優先順位）:**

### 🔧 1. TSDFパラメータを「粗く」する（最も効果的）

`config.yaml`を編集:

```yaml
processing:
  tsdf:
    voxel_length: 0.03  # 0.01 → 0.03-0.06m に変更（ノイズを飲み込ませる）
    sdf_trunc: 0.24     # voxel_lengthの8倍程度（0.03 * 8 = 0.24）
  
  depth:
    trunc: 2.5          # 3.0 → 2.5-4.0m に短縮（遠距離Depthが一番荒い）
    # 深度前処理を有効化
    filter_noise: true
    bilateral_filter: true
    bilateral_d: 5
    bilateral_sigma_color: 50.0
    bilateral_sigma_space: 50.0
```

**効果:**
- 細かいノイズがボクセルサイズで吸収される
- 遠距離のノイズが除去される
- メモリ使用量も減少

### 🔧 2. Depth前処理を強化

現在の`config.yaml`には基本的なフィルタが含まれていますが、より強力な前処理を追加できます。

**推奨設定:**
```yaml
depth:
  filter_noise: true        # 統計的外れ値除去
  bilateral_filter: true    # エッジ保持平滑化
  bilateral_d: 5
  bilateral_sigma_color: 50.0
  bilateral_sigma_space: 50.0
  # 追加オプション（実装が必要）
  inpaint_holes: true       # 穴埋め
  flying_pixel_removal: true # 飛び値除去
  confidence_threshold: 0.5  # 信頼度しきい値（ARCore Depth Confidence使用時）
```

### 🔧 3. フレームの間引き（Frame Sampling）

ARCoreデータは通常30fpsで記録されますが、TSDF統合には全フレームは不要です。

**実装方法（`rgbd_integration_gpu.py`の`process_session`メソッド）:**
```python
# フレームを間引く（例: 2fpsに減らす）
frames = parser.get_frames_with_depth()
frame_interval = max(1, len(frames) // (target_fps * duration_seconds))
sampled_frames = frames[::frame_interval]
```

**推奨:**
- 動くスキャン: 1-2 fps
- 静止スキャン: 0.5-1 fps

**効果:**
- 似たフレームの重複を減らす
- 姿勢誤差の累積を減らす
- 処理時間の短縮

### 🔧 4. 姿勢（VIO）の最適化（上級）

ARCoreのVIOが少しズレていると、TSDF統合時に段差が積み上がります。

**対策:**
- Open3DのPose Graph Optimizationを使用
- RGBD Odometryで微調整

**実装の複雑度:** 高い（現時点では未実装）

### 🔧 5. メッシュ後処理（最後の手段）

根本原因（Depth/TSDF設定）が解決できない場合の対症療法:

```yaml
mesh:
  quality_improvement:
    enable: true
    subdivision:
      enable: false  # ノイズメッシュには細分化は逆効果
    smoothing:
      enable: true
      method: "laplacian"
      iterations: 3  # 5 → 3 に減らす（やりすぎ注意）
      lambda_filter: 0.3  # 0.5 → 0.3 に減らす
```

## 📊 優先順位まとめ

### 最優先（即座に実施）

1. **Depth診断スクリプトを実行**
   ```bash
   python diagnose_depth.py <job_id>
   ```

2. **Depthデータが無い場合**
   - `depth_estimation.force_use: true` を設定

3. **Depthデータがノイジーな場合**
   - `voxel_length: 0.01 → 0.03-0.06m`
   - `depth_trunc: 3.0 → 2.5-4.0m`
   - `depth.bilateral_filter: true` を確認

### 次に実施（Depthがノイジーな場合）

4. **フレーム間引きの実装**
   - 1-2 fpsに減らす

5. **Depth前処理の強化**
   - 穴埋め、飛び値除去

### 最後の手段

6. **メッシュ後処理の調整**
   - 平滑化パラメータの調整

7. **姿勢最適化（上級）**
   - Pose Graph Optimization

## 🔍 現在の設定確認

現在の`config.yaml`設定（推奨値適用済み）:

```yaml
processing:
  tsdf:
    voxel_length: 0.04  # ✓ ノイズを飲み込ませる設定
    sdf_trunc: 0.32     # ✓ 適切な値
  
  depth:
    trunc: 7.0          # ✓ 診断結果の99パーセンタイル値（無効値を除外）
    filter_noise: true  # ✓ 有効
    bilateral_filter: true  # ✓ 有効
```

**診断結果に基づく推奨値（有効深度ピクセル0.4%の場合）:**

```yaml
processing:
  tsdf:
    voxel_length: 0.04  # 0.01 → 0.04m (4cm) - ノイズを飲み込ませる
    sdf_trunc: 0.32     # 0.04 * 8 = 0.32
  
  depth:
    trunc: 7.0          # 3.0 → 7.0m（診断結果の99パーセンタイル値、無効値マーカー65m以上を除外）
    filter_noise: true
    bilateral_filter: true
    bilateral_d: 5
    bilateral_sigma_color: 50.0
    bilateral_sigma_space: 50.0
```

**注意:**
- 有効深度ピクセルが0.4%と非常に少ない場合、Androidアプリ側で深度解像度を上げることを強く推奨
- 現在の160x90解像度は非常に低い（推奨: 320x240以上）
- `ANDROID_DEPTH_RESOLUTION_GUIDE.md`を参照してAndroidアプリ側の設定を確認してください

## 📝 次のステップ

1. 診断スクリプトを実行してDepth品質を確認
2. 結果に基づいて上記の対処法を適用
3. メッシュを再生成: `python regenerate_mesh.py <job_id> existing`
4. 結果を確認: `python view_mesh.py data/results/<job_id>/mesh.ply`

## 🆘 それでも改善しない場合

- **COLMAPパイプライン**への移行を検討
- **NeRF / 3D Gaussian Splatting**の使用を検討
- ハードウェアのアップグレード（LiDAR搭載端末など）

最終更新: 2026-01-08 10:14:57
---

# Depth診断とメッシュ品質改善ガイド

## 🔴 最優先: Depthデータの確認

「波打ったカーテン状のメッシュ」が発生する場合、**最も可能性が高い原因はDepthデータの問題**です。

### Step 1: Depthデータの診断

```bash
# 仮想環境をアクティブ化
source venv/bin/activate

# 診断スクリプトを実行
python diagnose_depth.py <job_id>

# 結果をJSONファイルに保存
python diagnose_depth.py <job_id> --output diagnosis_result.json
```

### Step 2: 診断結果の解釈

#### A. Depthデータが存在しない場合

**症状:**
- `has_depth: false`
- `frames_with_depth: 0`

**対処法（優先順位）:**
1. **深度推定を有効化** (`config.yaml`)
   ```yaml
   depth_estimation:
     enable: true
     force_use: true  # DepthデータがあってもMiDaSで再推定
     model: "DPT_Large"
     device: "cuda"
   ```

2. **COLMAPパイプラインに切り替え**
   - ARCore Depthなしでも高品質なメッシュが生成可能
   - 処理時間は長い（数時間）

3. **NeRF / 3D Gaussian Splatting**
   - 最高品質だが、メッシュ抽出が必要

#### B. Depthデータが存在するが品質が悪い場合

**症状:**
- `avg_std_dev > 1.5m` (深度の標準偏差が大きい)
- `avg_valid_ratio < 0.7` (有効ピクセルが少ない)
- `depth_range_m[1] > 10.0m` (異常に大きな深度値)

**対処法（優先順位）:**

### 🔧 1. TSDFパラメータを「粗く」する（最も効果的）

`config.yaml`を編集:

```yaml
processing:
  tsdf:
    voxel_length: 0.03  # 0.01 → 0.03-0.06m に変更（ノイズを飲み込ませる）
    sdf_trunc: 0.24     # voxel_lengthの8倍程度（0.03 * 8 = 0.24）
  
  depth:
    trunc: 2.5          # 3.0 → 2.5-4.0m に短縮（遠距離Depthが一番荒い）
    # 深度前処理を有効化
    filter_noise: true
    bilateral_filter: true
    bilateral_d: 5
    bilateral_sigma_color: 50.0
    bilateral_sigma_space: 50.0
```

**効果:**
- 細かいノイズがボクセルサイズで吸収される
- 遠距離のノイズが除去される
- メモリ使用量も減少

### 🔧 2. Depth前処理を強化

現在の`config.yaml`には基本的なフィルタが含まれていますが、より強力な前処理を追加できます。

**推奨設定:**
```yaml
depth:
  filter_noise: true        # 統計的外れ値除去
  bilateral_filter: true    # エッジ保持平滑化
  bilateral_d: 5
  bilateral_sigma_color: 50.0
  bilateral_sigma_space: 50.0
  # 追加オプション（実装が必要）
  inpaint_holes: true       # 穴埋め
  flying_pixel_removal: true # 飛び値除去
  confidence_threshold: 0.5  # 信頼度しきい値（ARCore Depth Confidence使用時）
```

### 🔧 3. フレームの間引き（Frame Sampling）

ARCoreデータは通常30fpsで記録されますが、TSDF統合には全フレームは不要です。

**実装方法（`rgbd_integration_gpu.py`の`process_session`メソッド）:**
```python
# フレームを間引く（例: 2fpsに減らす）
frames = parser.get_frames_with_depth()
frame_interval = max(1, len(frames) // (target_fps * duration_seconds))
sampled_frames = frames[::frame_interval]
```

**推奨:**
- 動くスキャン: 1-2 fps
- 静止スキャン: 0.5-1 fps

**効果:**
- 似たフレームの重複を減らす
- 姿勢誤差の累積を減らす
- 処理時間の短縮

### 🔧 4. 姿勢（VIO）の最適化（上級）

ARCoreのVIOが少しズレていると、TSDF統合時に段差が積み上がります。

**対策:**
- Open3DのPose Graph Optimizationを使用
- RGBD Odometryで微調整

**実装の複雑度:** 高い（現時点では未実装）

### 🔧 5. メッシュ後処理（最後の手段）

根本原因（Depth/TSDF設定）が解決できない場合の対症療法:

```yaml
mesh:
  quality_improvement:
    enable: true
    subdivision:
      enable: false  # ノイズメッシュには細分化は逆効果
    smoothing:
      enable: true
      method: "laplacian"
      iterations: 3  # 5 → 3 に減らす（やりすぎ注意）
      lambda_filter: 0.3  # 0.5 → 0.3 に減らす
```

## 📊 優先順位まとめ

### 最優先（即座に実施）

1. **Depth診断スクリプトを実行**
   ```bash
   python diagnose_depth.py <job_id>
   ```

2. **Depthデータが無い場合**
   - `depth_estimation.force_use: true` を設定

3. **Depthデータがノイジーな場合**
   - `voxel_length: 0.01 → 0.03-0.06m`
   - `depth_trunc: 3.0 → 2.5-4.0m`
   - `depth.bilateral_filter: true` を確認

### 次に実施（Depthがノイジーな場合）

4. **フレーム間引きの実装**
   - 1-2 fpsに減らす

5. **Depth前処理の強化**
   - 穴埋め、飛び値除去

### 最後の手段

6. **メッシュ後処理の調整**
   - 平滑化パラメータの調整

7. **姿勢最適化（上級）**
   - Pose Graph Optimization

## 🔍 現在の設定確認

現在の`config.yaml`設定（推奨値適用済み）:

```yaml
processing:
  tsdf:
    voxel_length: 0.04  # ✓ ノイズを飲み込ませる設定
    sdf_trunc: 0.32     # ✓ 適切な値
  
  depth:
    trunc: 7.0          # ✓ 診断結果の99パーセンタイル値（無効値を除外）
    filter_noise: true  # ✓ 有効
    bilateral_filter: true  # ✓ 有効
```

**診断結果に基づく推奨値（有効深度ピクセル0.4%の場合）:**

```yaml
processing:
  tsdf:
    voxel_length: 0.04  # 0.01 → 0.04m (4cm) - ノイズを飲み込ませる
    sdf_trunc: 0.32     # 0.04 * 8 = 0.32
  
  depth:
    trunc: 7.0          # 3.0 → 7.0m（診断結果の99パーセンタイル値、無効値マーカー65m以上を除外）
    filter_noise: true
    bilateral_filter: true
    bilateral_d: 5
    bilateral_sigma_color: 50.0
    bilateral_sigma_space: 50.0
```

**注意:**
- 有効深度ピクセルが0.4%と非常に少ない場合、Androidアプリ側で深度解像度を上げることを強く推奨
- 現在の160x90解像度は非常に低い（推奨: 320x240以上）
- `ANDROID_DEPTH_RESOLUTION_GUIDE.md`を参照してAndroidアプリ側の設定を確認してください

## 📝 次のステップ

1. 診断スクリプトを実行してDepth品質を確認
2. 結果に基づいて上記の対処法を適用
3. メッシュを再生成: `python regenerate_mesh.py <job_id> existing`
4. 結果を確認: `python view_mesh.py data/results/<job_id>/mesh.ply`

## 🆘 それでも改善しない場合

- **COLMAPパイプライン**への移行を検討
- **NeRF / 3D Gaussian Splatting**の使用を検討
- ハードウェアのアップグレード（LiDAR搭載端末など）
最終更新: 2026-01-08 10:14:57
---

# Depth診断とメッシュ品質改善ガイド

## 🔴 最優先: Depthデータの確認

「波打ったカーテン状のメッシュ」が発生する場合、**最も可能性が高い原因はDepthデータの問題**です。

### Step 1: Depthデータの診断

```bash
# 仮想環境をアクティブ化
source venv/bin/activate

# 診断スクリプトを実行
python diagnose_depth.py <job_id>

# 結果をJSONファイルに保存
python diagnose_depth.py <job_id> --output diagnosis_result.json
```

### Step 2: 診断結果の解釈

#### A. Depthデータが存在しない場合

**症状:**
- `has_depth: false`
- `frames_with_depth: 0`

**対処法（優先順位）:**
1. **深度推定を有効化** (`config.yaml`)
   ```yaml
   depth_estimation:
     enable: true
     force_use: true  # DepthデータがあってもMiDaSで再推定
     model: "DPT_Large"
     device: "cuda"
   ```

2. **COLMAPパイプラインに切り替え**
   - ARCore Depthなしでも高品質なメッシュが生成可能
   - 処理時間は長い（数時間）

3. **NeRF / 3D Gaussian Splatting**
   - 最高品質だが、メッシュ抽出が必要

#### B. Depthデータが存在するが品質が悪い場合

**症状:**
- `avg_std_dev > 1.5m` (深度の標準偏差が大きい)
- `avg_valid_ratio < 0.7` (有効ピクセルが少ない)
- `depth_range_m[1] > 10.0m` (異常に大きな深度値)

**対処法（優先順位）:**

### 🔧 1. TSDFパラメータを「粗く」する（最も効果的）

`config.yaml`を編集:

```yaml
processing:
  tsdf:
    voxel_length: 0.03  # 0.01 → 0.03-0.06m に変更（ノイズを飲み込ませる）
    sdf_trunc: 0.24     # voxel_lengthの8倍程度（0.03 * 8 = 0.24）
  
  depth:
    trunc: 2.5          # 3.0 → 2.5-4.0m に短縮（遠距離Depthが一番荒い）
    # 深度前処理を有効化
    filter_noise: true
    bilateral_filter: true
    bilateral_d: 5
    bilateral_sigma_color: 50.0
    bilateral_sigma_space: 50.0
```

**効果:**
- 細かいノイズがボクセルサイズで吸収される
- 遠距離のノイズが除去される
- メモリ使用量も減少

### 🔧 2. Depth前処理を強化

現在の`config.yaml`には基本的なフィルタが含まれていますが、より強力な前処理を追加できます。

**推奨設定:**
```yaml
depth:
  filter_noise: true        # 統計的外れ値除去
  bilateral_filter: true    # エッジ保持平滑化
  bilateral_d: 5
  bilateral_sigma_color: 50.0
  bilateral_sigma_space: 50.0
  # 追加オプション（実装が必要）
  inpaint_holes: true       # 穴埋め
  flying_pixel_removal: true # 飛び値除去
  confidence_threshold: 0.5  # 信頼度しきい値（ARCore Depth Confidence使用時）
```

### 🔧 3. フレームの間引き（Frame Sampling）

ARCoreデータは通常30fpsで記録されますが、TSDF統合には全フレームは不要です。

**実装方法（`rgbd_integration_gpu.py`の`process_session`メソッド）:**
```python
# フレームを間引く（例: 2fpsに減らす）
frames = parser.get_frames_with_depth()
frame_interval = max(1, len(frames) // (target_fps * duration_seconds))
sampled_frames = frames[::frame_interval]
```

**推奨:**
- 動くスキャン: 1-2 fps
- 静止スキャン: 0.5-1 fps

**効果:**
- 似たフレームの重複を減らす
- 姿勢誤差の累積を減らす
- 処理時間の短縮

### 🔧 4. 姿勢（VIO）の最適化（上級）

ARCoreのVIOが少しズレていると、TSDF統合時に段差が積み上がります。

**対策:**
- Open3DのPose Graph Optimizationを使用
- RGBD Odometryで微調整

**実装の複雑度:** 高い（現時点では未実装）

### 🔧 5. メッシュ後処理（最後の手段）

根本原因（Depth/TSDF設定）が解決できない場合の対症療法:

```yaml
mesh:
  quality_improvement:
    enable: true
    subdivision:
      enable: false  # ノイズメッシュには細分化は逆効果
    smoothing:
      enable: true
      method: "laplacian"
      iterations: 3  # 5 → 3 に減らす（やりすぎ注意）
      lambda_filter: 0.3  # 0.5 → 0.3 に減らす
```

## 📊 優先順位まとめ

### 最優先（即座に実施）

1. **Depth診断スクリプトを実行**
   ```bash
   python diagnose_depth.py <job_id>
   ```

2. **Depthデータが無い場合**
   - `depth_estimation.force_use: true` を設定

3. **Depthデータがノイジーな場合**
   - `voxel_length: 0.01 → 0.03-0.06m`
   - `depth_trunc: 3.0 → 2.5-4.0m`
   - `depth.bilateral_filter: true` を確認

### 次に実施（Depthがノイジーな場合）

4. **フレーム間引きの実装**
   - 1-2 fpsに減らす

5. **Depth前処理の強化**
   - 穴埋め、飛び値除去

### 最後の手段

6. **メッシュ後処理の調整**
   - 平滑化パラメータの調整

7. **姿勢最適化（上級）**
   - Pose Graph Optimization

## 🔍 現在の設定確認

現在の`config.yaml`設定（推奨値適用済み）:

```yaml
processing:
  tsdf:
    voxel_length: 0.04  # ✓ ノイズを飲み込ませる設定
    sdf_trunc: 0.32     # ✓ 適切な値
  
  depth:
    trunc: 7.0          # ✓ 診断結果の99パーセンタイル値（無効値を除外）
    filter_noise: true  # ✓ 有効
    bilateral_filter: true  # ✓ 有効
```

**診断結果に基づく推奨値（有効深度ピクセル0.4%の場合）:**

```yaml
processing:
  tsdf:
    voxel_length: 0.04  # 0.01 → 0.04m (4cm) - ノイズを飲み込ませる
    sdf_trunc: 0.32     # 0.04 * 8 = 0.32
  
  depth:
    trunc: 7.0          # 3.0 → 7.0m（診断結果の99パーセンタイル値、無効値マーカー65m以上を除外）
    filter_noise: true
    bilateral_filter: true
    bilateral_d: 5
    bilateral_sigma_color: 50.0
    bilateral_sigma_space: 50.0
```

**注意:**
- 有効深度ピクセルが0.4%と非常に少ない場合、Androidアプリ側で深度解像度を上げることを強く推奨
- 現在の160x90解像度は非常に低い（推奨: 320x240以上）
- `ANDROID_DEPTH_RESOLUTION_GUIDE.md`を参照してAndroidアプリ側の設定を確認してください

## 📝 次のステップ

1. 診断スクリプトを実行してDepth品質を確認
2. 結果に基づいて上記の対処法を適用
3. メッシュを再生成: `python regenerate_mesh.py <job_id> existing`
4. 結果を確認: `python view_mesh.py data/results/<job_id>/mesh.ply`

## 🆘 それでも改善しない場合

- **COLMAPパイプライン**への移行を検討
- **NeRF / 3D Gaussian Splatting**の使用を検討
- ハードウェアのアップグレード（LiDAR搭載端末など）

最終更新: 2026-01-08 10:14:57
---

# Depth診断とメッシュ品質改善ガイド

## 🔴 最優先: Depthデータの確認

「波打ったカーテン状のメッシュ」が発生する場合、**最も可能性が高い原因はDepthデータの問題**です。

### Step 1: Depthデータの診断

```bash
# 仮想環境をアクティブ化
source venv/bin/activate

# 診断スクリプトを実行
python diagnose_depth.py <job_id>

# 結果をJSONファイルに保存
python diagnose_depth.py <job_id> --output diagnosis_result.json
```

### Step 2: 診断結果の解釈

#### A. Depthデータが存在しない場合

**症状:**
- `has_depth: false`
- `frames_with_depth: 0`

**対処法（優先順位）:**
1. **深度推定を有効化** (`config.yaml`)
   ```yaml
   depth_estimation:
     enable: true
     force_use: true  # DepthデータがあってもMiDaSで再推定
     model: "DPT_Large"
     device: "cuda"
   ```

2. **COLMAPパイプラインに切り替え**
   - ARCore Depthなしでも高品質なメッシュが生成可能
   - 処理時間は長い（数時間）

3. **NeRF / 3D Gaussian Splatting**
   - 最高品質だが、メッシュ抽出が必要

#### B. Depthデータが存在するが品質が悪い場合

**症状:**
- `avg_std_dev > 1.5m` (深度の標準偏差が大きい)
- `avg_valid_ratio < 0.7` (有効ピクセルが少ない)
- `depth_range_m[1] > 10.0m` (異常に大きな深度値)

**対処法（優先順位）:**

### 🔧 1. TSDFパラメータを「粗く」する（最も効果的）

`config.yaml`を編集:

```yaml
processing:
  tsdf:
    voxel_length: 0.03  # 0.01 → 0.03-0.06m に変更（ノイズを飲み込ませる）
    sdf_trunc: 0.24     # voxel_lengthの8倍程度（0.03 * 8 = 0.24）
  
  depth:
    trunc: 2.5          # 3.0 → 2.5-4.0m に短縮（遠距離Depthが一番荒い）
    # 深度前処理を有効化
    filter_noise: true
    bilateral_filter: true
    bilateral_d: 5
    bilateral_sigma_color: 50.0
    bilateral_sigma_space: 50.0
```

**効果:**
- 細かいノイズがボクセルサイズで吸収される
- 遠距離のノイズが除去される
- メモリ使用量も減少

### 🔧 2. Depth前処理を強化

現在の`config.yaml`には基本的なフィルタが含まれていますが、より強力な前処理を追加できます。

**推奨設定:**
```yaml
depth:
  filter_noise: true        # 統計的外れ値除去
  bilateral_filter: true    # エッジ保持平滑化
  bilateral_d: 5
  bilateral_sigma_color: 50.0
  bilateral_sigma_space: 50.0
  # 追加オプション（実装が必要）
  inpaint_holes: true       # 穴埋め
  flying_pixel_removal: true # 飛び値除去
  confidence_threshold: 0.5  # 信頼度しきい値（ARCore Depth Confidence使用時）
```

### 🔧 3. フレームの間引き（Frame Sampling）

ARCoreデータは通常30fpsで記録されますが、TSDF統合には全フレームは不要です。

**実装方法（`rgbd_integration_gpu.py`の`process_session`メソッド）:**
```python
# フレームを間引く（例: 2fpsに減らす）
frames = parser.get_frames_with_depth()
frame_interval = max(1, len(frames) // (target_fps * duration_seconds))
sampled_frames = frames[::frame_interval]
```

**推奨:**
- 動くスキャン: 1-2 fps
- 静止スキャン: 0.5-1 fps

**効果:**
- 似たフレームの重複を減らす
- 姿勢誤差の累積を減らす
- 処理時間の短縮

### 🔧 4. 姿勢（VIO）の最適化（上級）

ARCoreのVIOが少しズレていると、TSDF統合時に段差が積み上がります。

**対策:**
- Open3DのPose Graph Optimizationを使用
- RGBD Odometryで微調整

**実装の複雑度:** 高い（現時点では未実装）

### 🔧 5. メッシュ後処理（最後の手段）

根本原因（Depth/TSDF設定）が解決できない場合の対症療法:

```yaml
mesh:
  quality_improvement:
    enable: true
    subdivision:
      enable: false  # ノイズメッシュには細分化は逆効果
    smoothing:
      enable: true
      method: "laplacian"
      iterations: 3  # 5 → 3 に減らす（やりすぎ注意）
      lambda_filter: 0.3  # 0.5 → 0.3 に減らす
```

## 📊 優先順位まとめ

### 最優先（即座に実施）

1. **Depth診断スクリプトを実行**
   ```bash
   python diagnose_depth.py <job_id>
   ```

2. **Depthデータが無い場合**
   - `depth_estimation.force_use: true` を設定

3. **Depthデータがノイジーな場合**
   - `voxel_length: 0.01 → 0.03-0.06m`
   - `depth_trunc: 3.0 → 2.5-4.0m`
   - `depth.bilateral_filter: true` を確認

### 次に実施（Depthがノイジーな場合）

4. **フレーム間引きの実装**
   - 1-2 fpsに減らす

5. **Depth前処理の強化**
   - 穴埋め、飛び値除去

### 最後の手段

6. **メッシュ後処理の調整**
   - 平滑化パラメータの調整

7. **姿勢最適化（上級）**
   - Pose Graph Optimization

## 🔍 現在の設定確認

現在の`config.yaml`設定（推奨値適用済み）:

```yaml
processing:
  tsdf:
    voxel_length: 0.04  # ✓ ノイズを飲み込ませる設定
    sdf_trunc: 0.32     # ✓ 適切な値
  
  depth:
    trunc: 7.0          # ✓ 診断結果の99パーセンタイル値（無効値を除外）
    filter_noise: true  # ✓ 有効
    bilateral_filter: true  # ✓ 有効
```

**診断結果に基づく推奨値（有効深度ピクセル0.4%の場合）:**

```yaml
processing:
  tsdf:
    voxel_length: 0.04  # 0.01 → 0.04m (4cm) - ノイズを飲み込ませる
    sdf_trunc: 0.32     # 0.04 * 8 = 0.32
  
  depth:
    trunc: 7.0          # 3.0 → 7.0m（診断結果の99パーセンタイル値、無効値マーカー65m以上を除外）
    filter_noise: true
    bilateral_filter: true
    bilateral_d: 5
    bilateral_sigma_color: 50.0
    bilateral_sigma_space: 50.0
```

**注意:**
- 有効深度ピクセルが0.4%と非常に少ない場合、Androidアプリ側で深度解像度を上げることを強く推奨
- 現在の160x90解像度は非常に低い（推奨: 320x240以上）
- `ANDROID_DEPTH_RESOLUTION_GUIDE.md`を参照してAndroidアプリ側の設定を確認してください

## 📝 次のステップ

1. 診断スクリプトを実行してDepth品質を確認
2. 結果に基づいて上記の対処法を適用
3. メッシュを再生成: `python regenerate_mesh.py <job_id> existing`
4. 結果を確認: `python view_mesh.py data/results/<job_id>/mesh.ply`

## 🆘 それでも改善しない場合

- **COLMAPパイプライン**への移行を検討
- **NeRF / 3D Gaussian Splatting**の使用を検討
- ハードウェアのアップグレード（LiDAR搭載端末など）

最終更新: 2026-01-08 10:14:57
---

# Depth診断とメッシュ品質改善ガイド

## 🔴 最優先: Depthデータの確認

「波打ったカーテン状のメッシュ」が発生する場合、**最も可能性が高い原因はDepthデータの問題**です。

### Step 1: Depthデータの診断

```bash
# 仮想環境をアクティブ化
source venv/bin/activate

# 診断スクリプトを実行
python diagnose_depth.py <job_id>

# 結果をJSONファイルに保存
python diagnose_depth.py <job_id> --output diagnosis_result.json
```

### Step 2: 診断結果の解釈

#### A. Depthデータが存在しない場合

**症状:**
- `has_depth: false`
- `frames_with_depth: 0`

**対処法（優先順位）:**
1. **深度推定を有効化** (`config.yaml`)
   ```yaml
   depth_estimation:
     enable: true
     force_use: true  # DepthデータがあってもMiDaSで再推定
     model: "DPT_Large"
     device: "cuda"
   ```

2. **COLMAPパイプラインに切り替え**
   - ARCore Depthなしでも高品質なメッシュが生成可能
   - 処理時間は長い（数時間）

3. **NeRF / 3D Gaussian Splatting**
   - 最高品質だが、メッシュ抽出が必要

#### B. Depthデータが存在するが品質が悪い場合

**症状:**
- `avg_std_dev > 1.5m` (深度の標準偏差が大きい)
- `avg_valid_ratio < 0.7` (有効ピクセルが少ない)
- `depth_range_m[1] > 10.0m` (異常に大きな深度値)

**対処法（優先順位）:**

### 🔧 1. TSDFパラメータを「粗く」する（最も効果的）

`config.yaml`を編集:

```yaml
processing:
  tsdf:
    voxel_length: 0.03  # 0.01 → 0.03-0.06m に変更（ノイズを飲み込ませる）
    sdf_trunc: 0.24     # voxel_lengthの8倍程度（0.03 * 8 = 0.24）
  
  depth:
    trunc: 2.5          # 3.0 → 2.5-4.0m に短縮（遠距離Depthが一番荒い）
    # 深度前処理を有効化
    filter_noise: true
    bilateral_filter: true
    bilateral_d: 5
    bilateral_sigma_color: 50.0
    bilateral_sigma_space: 50.0
```

**効果:**
- 細かいノイズがボクセルサイズで吸収される
- 遠距離のノイズが除去される
- メモリ使用量も減少

### 🔧 2. Depth前処理を強化

現在の`config.yaml`には基本的なフィルタが含まれていますが、より強力な前処理を追加できます。

**推奨設定:**
```yaml
depth:
  filter_noise: true        # 統計的外れ値除去
  bilateral_filter: true    # エッジ保持平滑化
  bilateral_d: 5
  bilateral_sigma_color: 50.0
  bilateral_sigma_space: 50.0
  # 追加オプション（実装が必要）
  inpaint_holes: true       # 穴埋め
  flying_pixel_removal: true # 飛び値除去
  confidence_threshold: 0.5  # 信頼度しきい値（ARCore Depth Confidence使用時）
```

### 🔧 3. フレームの間引き（Frame Sampling）

ARCoreデータは通常30fpsで記録されますが、TSDF統合には全フレームは不要です。

**実装方法（`rgbd_integration_gpu.py`の`process_session`メソッド）:**
```python
# フレームを間引く（例: 2fpsに減らす）
frames = parser.get_frames_with_depth()
frame_interval = max(1, len(frames) // (target_fps * duration_seconds))
sampled_frames = frames[::frame_interval]
```

**推奨:**
- 動くスキャン: 1-2 fps
- 静止スキャン: 0.5-1 fps

**効果:**
- 似たフレームの重複を減らす
- 姿勢誤差の累積を減らす
- 処理時間の短縮

### 🔧 4. 姿勢（VIO）の最適化（上級）

ARCoreのVIOが少しズレていると、TSDF統合時に段差が積み上がります。

**対策:**
- Open3DのPose Graph Optimizationを使用
- RGBD Odometryで微調整

**実装の複雑度:** 高い（現時点では未実装）

### 🔧 5. メッシュ後処理（最後の手段）

根本原因（Depth/TSDF設定）が解決できない場合の対症療法:

```yaml
mesh:
  quality_improvement:
    enable: true
    subdivision:
      enable: false  # ノイズメッシュには細分化は逆効果
    smoothing:
      enable: true
      method: "laplacian"
      iterations: 3  # 5 → 3 に減らす（やりすぎ注意）
      lambda_filter: 0.3  # 0.5 → 0.3 に減らす
```

## 📊 優先順位まとめ

### 最優先（即座に実施）

1. **Depth診断スクリプトを実行**
   ```bash
   python diagnose_depth.py <job_id>
   ```

2. **Depthデータが無い場合**
   - `depth_estimation.force_use: true` を設定

3. **Depthデータがノイジーな場合**
   - `voxel_length: 0.01 → 0.03-0.06m`
   - `depth_trunc: 3.0 → 2.5-4.0m`
   - `depth.bilateral_filter: true` を確認

### 次に実施（Depthがノイジーな場合）

4. **フレーム間引きの実装**
   - 1-2 fpsに減らす

5. **Depth前処理の強化**
   - 穴埋め、飛び値除去

### 最後の手段

6. **メッシュ後処理の調整**
   - 平滑化パラメータの調整

7. **姿勢最適化（上級）**
   - Pose Graph Optimization

## 🔍 現在の設定確認

現在の`config.yaml`設定（推奨値適用済み）:

```yaml
processing:
  tsdf:
    voxel_length: 0.04  # ✓ ノイズを飲み込ませる設定
    sdf_trunc: 0.32     # ✓ 適切な値
  
  depth:
    trunc: 7.0          # ✓ 診断結果の99パーセンタイル値（無効値を除外）
    filter_noise: true  # ✓ 有効
    bilateral_filter: true  # ✓ 有効
```

**診断結果に基づく推奨値（有効深度ピクセル0.4%の場合）:**

```yaml
processing:
  tsdf:
    voxel_length: 0.04  # 0.01 → 0.04m (4cm) - ノイズを飲み込ませる
    sdf_trunc: 0.32     # 0.04 * 8 = 0.32
  
  depth:
    trunc: 7.0          # 3.0 → 7.0m（診断結果の99パーセンタイル値、無効値マーカー65m以上を除外）
    filter_noise: true
    bilateral_filter: true
    bilateral_d: 5
    bilateral_sigma_color: 50.0
    bilateral_sigma_space: 50.0
```

**注意:**
- 有効深度ピクセルが0.4%と非常に少ない場合、Androidアプリ側で深度解像度を上げることを強く推奨
- 現在の160x90解像度は非常に低い（推奨: 320x240以上）
- `ANDROID_DEPTH_RESOLUTION_GUIDE.md`を参照してAndroidアプリ側の設定を確認してください

## 📝 次のステップ

1. 診断スクリプトを実行してDepth品質を確認
2. 結果に基づいて上記の対処法を適用
3. メッシュを再生成: `python regenerate_mesh.py <job_id> existing`
4. 結果を確認: `python view_mesh.py data/results/<job_id>/mesh.ply`

## 🆘 それでも改善しない場合

- **COLMAPパイプライン**への移行を検討
- **NeRF / 3D Gaussian Splatting**の使用を検討
- ハードウェアのアップグレード（LiDAR搭載端末など）

最終更新: 2026-01-08 10:14:57
---

# Depth診断とメッシュ品質改善ガイド

## 🔴 最優先: Depthデータの確認

「波打ったカーテン状のメッシュ」が発生する場合、**最も可能性が高い原因はDepthデータの問題**です。

### Step 1: Depthデータの診断

```bash
# 仮想環境をアクティブ化
source venv/bin/activate

# 診断スクリプトを実行
python diagnose_depth.py <job_id>

# 結果をJSONファイルに保存
python diagnose_depth.py <job_id> --output diagnosis_result.json
```

### Step 2: 診断結果の解釈

#### A. Depthデータが存在しない場合

**症状:**
- `has_depth: false`
- `frames_with_depth: 0`

**対処法（優先順位）:**
1. **深度推定を有効化** (`config.yaml`)
   ```yaml
   depth_estimation:
     enable: true
     force_use: true  # DepthデータがあってもMiDaSで再推定
     model: "DPT_Large"
     device: "cuda"
   ```

2. **COLMAPパイプラインに切り替え**
   - ARCore Depthなしでも高品質なメッシュが生成可能
   - 処理時間は長い（数時間）

3. **NeRF / 3D Gaussian Splatting**
   - 最高品質だが、メッシュ抽出が必要

#### B. Depthデータが存在するが品質が悪い場合

**症状:**
- `avg_std_dev > 1.5m` (深度の標準偏差が大きい)
- `avg_valid_ratio < 0.7` (有効ピクセルが少ない)
- `depth_range_m[1] > 10.0m` (異常に大きな深度値)

**対処法（優先順位）:**

### 🔧 1. TSDFパラメータを「粗く」する（最も効果的）

`config.yaml`を編集:

```yaml
processing:
  tsdf:
    voxel_length: 0.03  # 0.01 → 0.03-0.06m に変更（ノイズを飲み込ませる）
    sdf_trunc: 0.24     # voxel_lengthの8倍程度（0.03 * 8 = 0.24）
  
  depth:
    trunc: 2.5          # 3.0 → 2.5-4.0m に短縮（遠距離Depthが一番荒い）
    # 深度前処理を有効化
    filter_noise: true
    bilateral_filter: true
    bilateral_d: 5
    bilateral_sigma_color: 50.0
    bilateral_sigma_space: 50.0
```

**効果:**
- 細かいノイズがボクセルサイズで吸収される
- 遠距離のノイズが除去される
- メモリ使用量も減少

### 🔧 2. Depth前処理を強化

現在の`config.yaml`には基本的なフィルタが含まれていますが、より強力な前処理を追加できます。

**推奨設定:**
```yaml
depth:
  filter_noise: true        # 統計的外れ値除去
  bilateral_filter: true    # エッジ保持平滑化
  bilateral_d: 5
  bilateral_sigma_color: 50.0
  bilateral_sigma_space: 50.0
  # 追加オプション（実装が必要）
  inpaint_holes: true       # 穴埋め
  flying_pixel_removal: true # 飛び値除去
  confidence_threshold: 0.5  # 信頼度しきい値（ARCore Depth Confidence使用時）
```

### 🔧 3. フレームの間引き（Frame Sampling）

ARCoreデータは通常30fpsで記録されますが、TSDF統合には全フレームは不要です。

**実装方法（`rgbd_integration_gpu.py`の`process_session`メソッド）:**
```python
# フレームを間引く（例: 2fpsに減らす）
frames = parser.get_frames_with_depth()
frame_interval = max(1, len(frames) // (target_fps * duration_seconds))
sampled_frames = frames[::frame_interval]
```

**推奨:**
- 動くスキャン: 1-2 fps
- 静止スキャン: 0.5-1 fps

**効果:**
- 似たフレームの重複を減らす
- 姿勢誤差の累積を減らす
- 処理時間の短縮

### 🔧 4. 姿勢（VIO）の最適化（上級）

ARCoreのVIOが少しズレていると、TSDF統合時に段差が積み上がります。

**対策:**
- Open3DのPose Graph Optimizationを使用
- RGBD Odometryで微調整

**実装の複雑度:** 高い（現時点では未実装）

### 🔧 5. メッシュ後処理（最後の手段）

根本原因（Depth/TSDF設定）が解決できない場合の対症療法:

```yaml
mesh:
  quality_improvement:
    enable: true
    subdivision:
      enable: false  # ノイズメッシュには細分化は逆効果
    smoothing:
      enable: true
      method: "laplacian"
      iterations: 3  # 5 → 3 に減らす（やりすぎ注意）
      lambda_filter: 0.3  # 0.5 → 0.3 に減らす
```

## 📊 優先順位まとめ

### 最優先（即座に実施）

1. **Depth診断スクリプトを実行**
   ```bash
   python diagnose_depth.py <job_id>
   ```

2. **Depthデータが無い場合**
   - `depth_estimation.force_use: true` を設定

3. **Depthデータがノイジーな場合**
   - `voxel_length: 0.01 → 0.03-0.06m`
   - `depth_trunc: 3.0 → 2.5-4.0m`
   - `depth.bilateral_filter: true` を確認

### 次に実施（Depthがノイジーな場合）

4. **フレーム間引きの実装**
   - 1-2 fpsに減らす

5. **Depth前処理の強化**
   - 穴埋め、飛び値除去

### 最後の手段

6. **メッシュ後処理の調整**
   - 平滑化パラメータの調整

7. **姿勢最適化（上級）**
   - Pose Graph Optimization

## 🔍 現在の設定確認

現在の`config.yaml`設定（推奨値適用済み）:

```yaml
processing:
  tsdf:
    voxel_length: 0.04  # ✓ ノイズを飲み込ませる設定
    sdf_trunc: 0.32     # ✓ 適切な値
  
  depth:
    trunc: 7.0          # ✓ 診断結果の99パーセンタイル値（無効値を除外）
    filter_noise: true  # ✓ 有効
    bilateral_filter: true  # ✓ 有効
```

**診断結果に基づく推奨値（有効深度ピクセル0.4%の場合）:**

```yaml
processing:
  tsdf:
    voxel_length: 0.04  # 0.01 → 0.04m (4cm) - ノイズを飲み込ませる
    sdf_trunc: 0.32     # 0.04 * 8 = 0.32
  
  depth:
    trunc: 7.0          # 3.0 → 7.0m（診断結果の99パーセンタイル値、無効値マーカー65m以上を除外）
    filter_noise: true
    bilateral_filter: true
    bilateral_d: 5
    bilateral_sigma_color: 50.0
    bilateral_sigma_space: 50.0
```

**注意:**
- 有効深度ピクセルが0.4%と非常に少ない場合、Androidアプリ側で深度解像度を上げることを強く推奨
- 現在の160x90解像度は非常に低い（推奨: 320x240以上）
- `ANDROID_DEPTH_RESOLUTION_GUIDE.md`を参照してAndroidアプリ側の設定を確認してください

## 📝 次のステップ

1. 診断スクリプトを実行してDepth品質を確認
2. 結果に基づいて上記の対処法を適用
3. メッシュを再生成: `python regenerate_mesh.py <job_id> existing`
4. 結果を確認: `python view_mesh.py data/results/<job_id>/mesh.ply`

## 🆘 それでも改善しない場合

- **COLMAPパイプライン**への移行を検討
- **NeRF / 3D Gaussian Splatting**の使用を検討
- ハードウェアのアップグレード（LiDAR搭載端末など）
最終更新: 2026-01-08 10:14:57
---

# Depth診断とメッシュ品質改善ガイド

## 🔴 最優先: Depthデータの確認

「波打ったカーテン状のメッシュ」が発生する場合、**最も可能性が高い原因はDepthデータの問題**です。

### Step 1: Depthデータの診断

```bash
# 仮想環境をアクティブ化
source venv/bin/activate

# 診断スクリプトを実行
python diagnose_depth.py <job_id>

# 結果をJSONファイルに保存
python diagnose_depth.py <job_id> --output diagnosis_result.json
```

### Step 2: 診断結果の解釈

#### A. Depthデータが存在しない場合

**症状:**
- `has_depth: false`
- `frames_with_depth: 0`

**対処法（優先順位）:**
1. **深度推定を有効化** (`config.yaml`)
   ```yaml
   depth_estimation:
     enable: true
     force_use: true  # DepthデータがあってもMiDaSで再推定
     model: "DPT_Large"
     device: "cuda"
   ```

2. **COLMAPパイプラインに切り替え**
   - ARCore Depthなしでも高品質なメッシュが生成可能
   - 処理時間は長い（数時間）

3. **NeRF / 3D Gaussian Splatting**
   - 最高品質だが、メッシュ抽出が必要

#### B. Depthデータが存在するが品質が悪い場合

**症状:**
- `avg_std_dev > 1.5m` (深度の標準偏差が大きい)
- `avg_valid_ratio < 0.7` (有効ピクセルが少ない)
- `depth_range_m[1] > 10.0m` (異常に大きな深度値)

**対処法（優先順位）:**

### 🔧 1. TSDFパラメータを「粗く」する（最も効果的）

`config.yaml`を編集:

```yaml
processing:
  tsdf:
    voxel_length: 0.03  # 0.01 → 0.03-0.06m に変更（ノイズを飲み込ませる）
    sdf_trunc: 0.24     # voxel_lengthの8倍程度（0.03 * 8 = 0.24）
  
  depth:
    trunc: 2.5          # 3.0 → 2.5-4.0m に短縮（遠距離Depthが一番荒い）
    # 深度前処理を有効化
    filter_noise: true
    bilateral_filter: true
    bilateral_d: 5
    bilateral_sigma_color: 50.0
    bilateral_sigma_space: 50.0
```

**効果:**
- 細かいノイズがボクセルサイズで吸収される
- 遠距離のノイズが除去される
- メモリ使用量も減少

### 🔧 2. Depth前処理を強化

現在の`config.yaml`には基本的なフィルタが含まれていますが、より強力な前処理を追加できます。

**推奨設定:**
```yaml
depth:
  filter_noise: true        # 統計的外れ値除去
  bilateral_filter: true    # エッジ保持平滑化
  bilateral_d: 5
  bilateral_sigma_color: 50.0
  bilateral_sigma_space: 50.0
  # 追加オプション（実装が必要）
  inpaint_holes: true       # 穴埋め
  flying_pixel_removal: true # 飛び値除去
  confidence_threshold: 0.5  # 信頼度しきい値（ARCore Depth Confidence使用時）
```

### 🔧 3. フレームの間引き（Frame Sampling）

ARCoreデータは通常30fpsで記録されますが、TSDF統合には全フレームは不要です。

**実装方法（`rgbd_integration_gpu.py`の`process_session`メソッド）:**
```python
# フレームを間引く（例: 2fpsに減らす）
frames = parser.get_frames_with_depth()
frame_interval = max(1, len(frames) // (target_fps * duration_seconds))
sampled_frames = frames[::frame_interval]
```

**推奨:**
- 動くスキャン: 1-2 fps
- 静止スキャン: 0.5-1 fps

**効果:**
- 似たフレームの重複を減らす
- 姿勢誤差の累積を減らす
- 処理時間の短縮

### 🔧 4. 姿勢（VIO）の最適化（上級）

ARCoreのVIOが少しズレていると、TSDF統合時に段差が積み上がります。

**対策:**
- Open3DのPose Graph Optimizationを使用
- RGBD Odometryで微調整

**実装の複雑度:** 高い（現時点では未実装）

### 🔧 5. メッシュ後処理（最後の手段）

根本原因（Depth/TSDF設定）が解決できない場合の対症療法:

```yaml
mesh:
  quality_improvement:
    enable: true
    subdivision:
      enable: false  # ノイズメッシュには細分化は逆効果
    smoothing:
      enable: true
      method: "laplacian"
      iterations: 3  # 5 → 3 に減らす（やりすぎ注意）
      lambda_filter: 0.3  # 0.5 → 0.3 に減らす
```

## 📊 優先順位まとめ

### 最優先（即座に実施）

1. **Depth診断スクリプトを実行**
   ```bash
   python diagnose_depth.py <job_id>
   ```

2. **Depthデータが無い場合**
   - `depth_estimation.force_use: true` を設定

3. **Depthデータがノイジーな場合**
   - `voxel_length: 0.01 → 0.03-0.06m`
   - `depth_trunc: 3.0 → 2.5-4.0m`
   - `depth.bilateral_filter: true` を確認

### 次に実施（Depthがノイジーな場合）

4. **フレーム間引きの実装**
   - 1-2 fpsに減らす

5. **Depth前処理の強化**
   - 穴埋め、飛び値除去

### 最後の手段

6. **メッシュ後処理の調整**
   - 平滑化パラメータの調整

7. **姿勢最適化（上級）**
   - Pose Graph Optimization

## 🔍 現在の設定確認

現在の`config.yaml`設定（推奨値適用済み）:

```yaml
processing:
  tsdf:
    voxel_length: 0.04  # ✓ ノイズを飲み込ませる設定
    sdf_trunc: 0.32     # ✓ 適切な値
  
  depth:
    trunc: 7.0          # ✓ 診断結果の99パーセンタイル値（無効値を除外）
    filter_noise: true  # ✓ 有効
    bilateral_filter: true  # ✓ 有効
```

**診断結果に基づく推奨値（有効深度ピクセル0.4%の場合）:**

```yaml
processing:
  tsdf:
    voxel_length: 0.04  # 0.01 → 0.04m (4cm) - ノイズを飲み込ませる
    sdf_trunc: 0.32     # 0.04 * 8 = 0.32
  
  depth:
    trunc: 7.0          # 3.0 → 7.0m（診断結果の99パーセンタイル値、無効値マーカー65m以上を除外）
    filter_noise: true
    bilateral_filter: true
    bilateral_d: 5
    bilateral_sigma_color: 50.0
    bilateral_sigma_space: 50.0
```

**注意:**
- 有効深度ピクセルが0.4%と非常に少ない場合、Androidアプリ側で深度解像度を上げることを強く推奨
- 現在の160x90解像度は非常に低い（推奨: 320x240以上）
- `ANDROID_DEPTH_RESOLUTION_GUIDE.md`を参照してAndroidアプリ側の設定を確認してください

## 📝 次のステップ

1. 診断スクリプトを実行してDepth品質を確認
2. 結果に基づいて上記の対処法を適用
3. メッシュを再生成: `python regenerate_mesh.py <job_id> existing`
4. 結果を確認: `python view_mesh.py data/results/<job_id>/mesh.ply`

## 🆘 それでも改善しない場合

- **COLMAPパイプライン**への移行を検討
- **NeRF / 3D Gaussian Splatting**の使用を検討
- ハードウェアのアップグレード（LiDAR搭載端末など）

最終更新: 2026-01-08 10:14:57
---

# Depth診断とメッシュ品質改善ガイド

## 🔴 最優先: Depthデータの確認

「波打ったカーテン状のメッシュ」が発生する場合、**最も可能性が高い原因はDepthデータの問題**です。

### Step 1: Depthデータの診断

```bash
# 仮想環境をアクティブ化
source venv/bin/activate

# 診断スクリプトを実行
python diagnose_depth.py <job_id>

# 結果をJSONファイルに保存
python diagnose_depth.py <job_id> --output diagnosis_result.json
```

### Step 2: 診断結果の解釈

#### A. Depthデータが存在しない場合

**症状:**
- `has_depth: false`
- `frames_with_depth: 0`

**対処法（優先順位）:**
1. **深度推定を有効化** (`config.yaml`)
   ```yaml
   depth_estimation:
     enable: true
     force_use: true  # DepthデータがあってもMiDaSで再推定
     model: "DPT_Large"
     device: "cuda"
   ```

2. **COLMAPパイプラインに切り替え**
   - ARCore Depthなしでも高品質なメッシュが生成可能
   - 処理時間は長い（数時間）

3. **NeRF / 3D Gaussian Splatting**
   - 最高品質だが、メッシュ抽出が必要

#### B. Depthデータが存在するが品質が悪い場合

**症状:**
- `avg_std_dev > 1.5m` (深度の標準偏差が大きい)
- `avg_valid_ratio < 0.7` (有効ピクセルが少ない)
- `depth_range_m[1] > 10.0m` (異常に大きな深度値)

**対処法（優先順位）:**

### 🔧 1. TSDFパラメータを「粗く」する（最も効果的）

`config.yaml`を編集:

```yaml
processing:
  tsdf:
    voxel_length: 0.03  # 0.01 → 0.03-0.06m に変更（ノイズを飲み込ませる）
    sdf_trunc: 0.24     # voxel_lengthの8倍程度（0.03 * 8 = 0.24）
  
  depth:
    trunc: 2.5          # 3.0 → 2.5-4.0m に短縮（遠距離Depthが一番荒い）
    # 深度前処理を有効化
    filter_noise: true
    bilateral_filter: true
    bilateral_d: 5
    bilateral_sigma_color: 50.0
    bilateral_sigma_space: 50.0
```

**効果:**
- 細かいノイズがボクセルサイズで吸収される
- 遠距離のノイズが除去される
- メモリ使用量も減少

### 🔧 2. Depth前処理を強化

現在の`config.yaml`には基本的なフィルタが含まれていますが、より強力な前処理を追加できます。

**推奨設定:**
```yaml
depth:
  filter_noise: true        # 統計的外れ値除去
  bilateral_filter: true    # エッジ保持平滑化
  bilateral_d: 5
  bilateral_sigma_color: 50.0
  bilateral_sigma_space: 50.0
  # 追加オプション（実装が必要）
  inpaint_holes: true       # 穴埋め
  flying_pixel_removal: true # 飛び値除去
  confidence_threshold: 0.5  # 信頼度しきい値（ARCore Depth Confidence使用時）
```

### 🔧 3. フレームの間引き（Frame Sampling）

ARCoreデータは通常30fpsで記録されますが、TSDF統合には全フレームは不要です。

**実装方法（`rgbd_integration_gpu.py`の`process_session`メソッド）:**
```python
# フレームを間引く（例: 2fpsに減らす）
frames = parser.get_frames_with_depth()
frame_interval = max(1, len(frames) // (target_fps * duration_seconds))
sampled_frames = frames[::frame_interval]
```

**推奨:**
- 動くスキャン: 1-2 fps
- 静止スキャン: 0.5-1 fps

**効果:**
- 似たフレームの重複を減らす
- 姿勢誤差の累積を減らす
- 処理時間の短縮

### 🔧 4. 姿勢（VIO）の最適化（上級）

ARCoreのVIOが少しズレていると、TSDF統合時に段差が積み上がります。

**対策:**
- Open3DのPose Graph Optimizationを使用
- RGBD Odometryで微調整

**実装の複雑度:** 高い（現時点では未実装）

### 🔧 5. メッシュ後処理（最後の手段）

根本原因（Depth/TSDF設定）が解決できない場合の対症療法:

```yaml
mesh:
  quality_improvement:
    enable: true
    subdivision:
      enable: false  # ノイズメッシュには細分化は逆効果
    smoothing:
      enable: true
      method: "laplacian"
      iterations: 3  # 5 → 3 に減らす（やりすぎ注意）
      lambda_filter: 0.3  # 0.5 → 0.3 に減らす
```

## 📊 優先順位まとめ

### 最優先（即座に実施）

1. **Depth診断スクリプトを実行**
   ```bash
   python diagnose_depth.py <job_id>
   ```

2. **Depthデータが無い場合**
   - `depth_estimation.force_use: true` を設定

3. **Depthデータがノイジーな場合**
   - `voxel_length: 0.01 → 0.03-0.06m`
   - `depth_trunc: 3.0 → 2.5-4.0m`
   - `depth.bilateral_filter: true` を確認

### 次に実施（Depthがノイジーな場合）

4. **フレーム間引きの実装**
   - 1-2 fpsに減らす

5. **Depth前処理の強化**
   - 穴埋め、飛び値除去

### 最後の手段

6. **メッシュ後処理の調整**
   - 平滑化パラメータの調整

7. **姿勢最適化（上級）**
   - Pose Graph Optimization

## 🔍 現在の設定確認

現在の`config.yaml`設定（推奨値適用済み）:

```yaml
processing:
  tsdf:
    voxel_length: 0.04  # ✓ ノイズを飲み込ませる設定
    sdf_trunc: 0.32     # ✓ 適切な値
  
  depth:
    trunc: 7.0          # ✓ 診断結果の99パーセンタイル値（無効値を除外）
    filter_noise: true  # ✓ 有効
    bilateral_filter: true  # ✓ 有効
```

**診断結果に基づく推奨値（有効深度ピクセル0.4%の場合）:**

```yaml
processing:
  tsdf:
    voxel_length: 0.04  # 0.01 → 0.04m (4cm) - ノイズを飲み込ませる
    sdf_trunc: 0.32     # 0.04 * 8 = 0.32
  
  depth:
    trunc: 7.0          # 3.0 → 7.0m（診断結果の99パーセンタイル値、無効値マーカー65m以上を除外）
    filter_noise: true
    bilateral_filter: true
    bilateral_d: 5
    bilateral_sigma_color: 50.0
    bilateral_sigma_space: 50.0
```

**注意:**
- 有効深度ピクセルが0.4%と非常に少ない場合、Androidアプリ側で深度解像度を上げることを強く推奨
- 現在の160x90解像度は非常に低い（推奨: 320x240以上）
- `ANDROID_DEPTH_RESOLUTION_GUIDE.md`を参照してAndroidアプリ側の設定を確認してください

## 📝 次のステップ

1. 診断スクリプトを実行してDepth品質を確認
2. 結果に基づいて上記の対処法を適用
3. メッシュを再生成: `python regenerate_mesh.py <job_id> existing`
4. 結果を確認: `python view_mesh.py data/results/<job_id>/mesh.ply`

## 🆘 それでも改善しない場合

- **COLMAPパイプライン**への移行を検討
- **NeRF / 3D Gaussian Splatting**の使用を検討
- ハードウェアのアップグレード（LiDAR搭載端末など）

最終更新: 2026-01-08 10:14:57
---

# Depth診断とメッシュ品質改善ガイド

## 🔴 最優先: Depthデータの確認

「波打ったカーテン状のメッシュ」が発生する場合、**最も可能性が高い原因はDepthデータの問題**です。

### Step 1: Depthデータの診断

```bash
# 仮想環境をアクティブ化
source venv/bin/activate

# 診断スクリプトを実行
python diagnose_depth.py <job_id>

# 結果をJSONファイルに保存
python diagnose_depth.py <job_id> --output diagnosis_result.json
```

### Step 2: 診断結果の解釈

#### A. Depthデータが存在しない場合

**症状:**
- `has_depth: false`
- `frames_with_depth: 0`

**対処法（優先順位）:**
1. **深度推定を有効化** (`config.yaml`)
   ```yaml
   depth_estimation:
     enable: true
     force_use: true  # DepthデータがあってもMiDaSで再推定
     model: "DPT_Large"
     device: "cuda"
   ```

2. **COLMAPパイプラインに切り替え**
   - ARCore Depthなしでも高品質なメッシュが生成可能
   - 処理時間は長い（数時間）

3. **NeRF / 3D Gaussian Splatting**
   - 最高品質だが、メッシュ抽出が必要

#### B. Depthデータが存在するが品質が悪い場合

**症状:**
- `avg_std_dev > 1.5m` (深度の標準偏差が大きい)
- `avg_valid_ratio < 0.7` (有効ピクセルが少ない)
- `depth_range_m[1] > 10.0m` (異常に大きな深度値)

**対処法（優先順位）:**

### 🔧 1. TSDFパラメータを「粗く」する（最も効果的）

`config.yaml`を編集:

```yaml
processing:
  tsdf:
    voxel_length: 0.03  # 0.01 → 0.03-0.06m に変更（ノイズを飲み込ませる）
    sdf_trunc: 0.24     # voxel_lengthの8倍程度（0.03 * 8 = 0.24）
  
  depth:
    trunc: 2.5          # 3.0 → 2.5-4.0m に短縮（遠距離Depthが一番荒い）
    # 深度前処理を有効化
    filter_noise: true
    bilateral_filter: true
    bilateral_d: 5
    bilateral_sigma_color: 50.0
    bilateral_sigma_space: 50.0
```

**効果:**
- 細かいノイズがボクセルサイズで吸収される
- 遠距離のノイズが除去される
- メモリ使用量も減少

### 🔧 2. Depth前処理を強化

現在の`config.yaml`には基本的なフィルタが含まれていますが、より強力な前処理を追加できます。

**推奨設定:**
```yaml
depth:
  filter_noise: true        # 統計的外れ値除去
  bilateral_filter: true    # エッジ保持平滑化
  bilateral_d: 5
  bilateral_sigma_color: 50.0
  bilateral_sigma_space: 50.0
  # 追加オプション（実装が必要）
  inpaint_holes: true       # 穴埋め
  flying_pixel_removal: true # 飛び値除去
  confidence_threshold: 0.5  # 信頼度しきい値（ARCore Depth Confidence使用時）
```

### 🔧 3. フレームの間引き（Frame Sampling）

ARCoreデータは通常30fpsで記録されますが、TSDF統合には全フレームは不要です。

**実装方法（`rgbd_integration_gpu.py`の`process_session`メソッド）:**
```python
# フレームを間引く（例: 2fpsに減らす）
frames = parser.get_frames_with_depth()
frame_interval = max(1, len(frames) // (target_fps * duration_seconds))
sampled_frames = frames[::frame_interval]
```

**推奨:**
- 動くスキャン: 1-2 fps
- 静止スキャン: 0.5-1 fps

**効果:**
- 似たフレームの重複を減らす
- 姿勢誤差の累積を減らす
- 処理時間の短縮

### 🔧 4. 姿勢（VIO）の最適化（上級）

ARCoreのVIOが少しズレていると、TSDF統合時に段差が積み上がります。

**対策:**
- Open3DのPose Graph Optimizationを使用
- RGBD Odometryで微調整

**実装の複雑度:** 高い（現時点では未実装）

### 🔧 5. メッシュ後処理（最後の手段）

根本原因（Depth/TSDF設定）が解決できない場合の対症療法:

```yaml
mesh:
  quality_improvement:
    enable: true
    subdivision:
      enable: false  # ノイズメッシュには細分化は逆効果
    smoothing:
      enable: true
      method: "laplacian"
      iterations: 3  # 5 → 3 に減らす（やりすぎ注意）
      lambda_filter: 0.3  # 0.5 → 0.3 に減らす
```

## 📊 優先順位まとめ

### 最優先（即座に実施）

1. **Depth診断スクリプトを実行**
   ```bash
   python diagnose_depth.py <job_id>
   ```

2. **Depthデータが無い場合**
   - `depth_estimation.force_use: true` を設定

3. **Depthデータがノイジーな場合**
   - `voxel_length: 0.01 → 0.03-0.06m`
   - `depth_trunc: 3.0 → 2.5-4.0m`
   - `depth.bilateral_filter: true` を確認

### 次に実施（Depthがノイジーな場合）

4. **フレーム間引きの実装**
   - 1-2 fpsに減らす

5. **Depth前処理の強化**
   - 穴埋め、飛び値除去

### 最後の手段

6. **メッシュ後処理の調整**
   - 平滑化パラメータの調整

7. **姿勢最適化（上級）**
   - Pose Graph Optimization

## 🔍 現在の設定確認

現在の`config.yaml`設定（推奨値適用済み）:

```yaml
processing:
  tsdf:
    voxel_length: 0.04  # ✓ ノイズを飲み込ませる設定
    sdf_trunc: 0.32     # ✓ 適切な値
  
  depth:
    trunc: 7.0          # ✓ 診断結果の99パーセンタイル値（無効値を除外）
    filter_noise: true  # ✓ 有効
    bilateral_filter: true  # ✓ 有効
```

**診断結果に基づく推奨値（有効深度ピクセル0.4%の場合）:**

```yaml
processing:
  tsdf:
    voxel_length: 0.04  # 0.01 → 0.04m (4cm) - ノイズを飲み込ませる
    sdf_trunc: 0.32     # 0.04 * 8 = 0.32
  
  depth:
    trunc: 7.0          # 3.0 → 7.0m（診断結果の99パーセンタイル値、無効値マーカー65m以上を除外）
    filter_noise: true
    bilateral_filter: true
    bilateral_d: 5
    bilateral_sigma_color: 50.0
    bilateral_sigma_space: 50.0
```

**注意:**
- 有効深度ピクセルが0.4%と非常に少ない場合、Androidアプリ側で深度解像度を上げることを強く推奨
- 現在の160x90解像度は非常に低い（推奨: 320x240以上）
- `ANDROID_DEPTH_RESOLUTION_GUIDE.md`を参照してAndroidアプリ側の設定を確認してください

## 📝 次のステップ

1. 診断スクリプトを実行してDepth品質を確認
2. 結果に基づいて上記の対処法を適用
3. メッシュを再生成: `python regenerate_mesh.py <job_id> existing`
4. 結果を確認: `python view_mesh.py data/results/<job_id>/mesh.ply`

## 🆘 それでも改善しない場合

- **COLMAPパイプライン**への移行を検討
- **NeRF / 3D Gaussian Splatting**の使用を検討
- ハードウェアのアップグレード（LiDAR搭載端末など）

最終更新: 2026-01-08 10:14:57
---

# Depth診断とメッシュ品質改善ガイド

## 🔴 最優先: Depthデータの確認

「波打ったカーテン状のメッシュ」が発生する場合、**最も可能性が高い原因はDepthデータの問題**です。

### Step 1: Depthデータの診断

```bash
# 仮想環境をアクティブ化
source venv/bin/activate

# 診断スクリプトを実行
python diagnose_depth.py <job_id>

# 結果をJSONファイルに保存
python diagnose_depth.py <job_id> --output diagnosis_result.json
```

### Step 2: 診断結果の解釈

#### A. Depthデータが存在しない場合

**症状:**
- `has_depth: false`
- `frames_with_depth: 0`

**対処法（優先順位）:**
1. **深度推定を有効化** (`config.yaml`)
   ```yaml
   depth_estimation:
     enable: true
     force_use: true  # DepthデータがあってもMiDaSで再推定
     model: "DPT_Large"
     device: "cuda"
   ```

2. **COLMAPパイプラインに切り替え**
   - ARCore Depthなしでも高品質なメッシュが生成可能
   - 処理時間は長い（数時間）

3. **NeRF / 3D Gaussian Splatting**
   - 最高品質だが、メッシュ抽出が必要

#### B. Depthデータが存在するが品質が悪い場合

**症状:**
- `avg_std_dev > 1.5m` (深度の標準偏差が大きい)
- `avg_valid_ratio < 0.7` (有効ピクセルが少ない)
- `depth_range_m[1] > 10.0m` (異常に大きな深度値)

**対処法（優先順位）:**

### 🔧 1. TSDFパラメータを「粗く」する（最も効果的）

`config.yaml`を編集:

```yaml
processing:
  tsdf:
    voxel_length: 0.03  # 0.01 → 0.03-0.06m に変更（ノイズを飲み込ませる）
    sdf_trunc: 0.24     # voxel_lengthの8倍程度（0.03 * 8 = 0.24）
  
  depth:
    trunc: 2.5          # 3.0 → 2.5-4.0m に短縮（遠距離Depthが一番荒い）
    # 深度前処理を有効化
    filter_noise: true
    bilateral_filter: true
    bilateral_d: 5
    bilateral_sigma_color: 50.0
    bilateral_sigma_space: 50.0
```

**効果:**
- 細かいノイズがボクセルサイズで吸収される
- 遠距離のノイズが除去される
- メモリ使用量も減少

### 🔧 2. Depth前処理を強化

現在の`config.yaml`には基本的なフィルタが含まれていますが、より強力な前処理を追加できます。

**推奨設定:**
```yaml
depth:
  filter_noise: true        # 統計的外れ値除去
  bilateral_filter: true    # エッジ保持平滑化
  bilateral_d: 5
  bilateral_sigma_color: 50.0
  bilateral_sigma_space: 50.0
  # 追加オプション（実装が必要）
  inpaint_holes: true       # 穴埋め
  flying_pixel_removal: true # 飛び値除去
  confidence_threshold: 0.5  # 信頼度しきい値（ARCore Depth Confidence使用時）
```

### 🔧 3. フレームの間引き（Frame Sampling）

ARCoreデータは通常30fpsで記録されますが、TSDF統合には全フレームは不要です。

**実装方法（`rgbd_integration_gpu.py`の`process_session`メソッド）:**
```python
# フレームを間引く（例: 2fpsに減らす）
frames = parser.get_frames_with_depth()
frame_interval = max(1, len(frames) // (target_fps * duration_seconds))
sampled_frames = frames[::frame_interval]
```

**推奨:**
- 動くスキャン: 1-2 fps
- 静止スキャン: 0.5-1 fps

**効果:**
- 似たフレームの重複を減らす
- 姿勢誤差の累積を減らす
- 処理時間の短縮

### 🔧 4. 姿勢（VIO）の最適化（上級）

ARCoreのVIOが少しズレていると、TSDF統合時に段差が積み上がります。

**対策:**
- Open3DのPose Graph Optimizationを使用
- RGBD Odometryで微調整

**実装の複雑度:** 高い（現時点では未実装）

### 🔧 5. メッシュ後処理（最後の手段）

根本原因（Depth/TSDF設定）が解決できない場合の対症療法:

```yaml
mesh:
  quality_improvement:
    enable: true
    subdivision:
      enable: false  # ノイズメッシュには細分化は逆効果
    smoothing:
      enable: true
      method: "laplacian"
      iterations: 3  # 5 → 3 に減らす（やりすぎ注意）
      lambda_filter: 0.3  # 0.5 → 0.3 に減らす
```

## 📊 優先順位まとめ

### 最優先（即座に実施）

1. **Depth診断スクリプトを実行**
   ```bash
   python diagnose_depth.py <job_id>
   ```

2. **Depthデータが無い場合**
   - `depth_estimation.force_use: true` を設定

3. **Depthデータがノイジーな場合**
   - `voxel_length: 0.01 → 0.03-0.06m`
   - `depth_trunc: 3.0 → 2.5-4.0m`
   - `depth.bilateral_filter: true` を確認

### 次に実施（Depthがノイジーな場合）

4. **フレーム間引きの実装**
   - 1-2 fpsに減らす

5. **Depth前処理の強化**
   - 穴埋め、飛び値除去

### 最後の手段

6. **メッシュ後処理の調整**
   - 平滑化パラメータの調整

7. **姿勢最適化（上級）**
   - Pose Graph Optimization

## 🔍 現在の設定確認

現在の`config.yaml`設定（推奨値適用済み）:

```yaml
processing:
  tsdf:
    voxel_length: 0.04  # ✓ ノイズを飲み込ませる設定
    sdf_trunc: 0.32     # ✓ 適切な値
  
  depth:
    trunc: 7.0          # ✓ 診断結果の99パーセンタイル値（無効値を除外）
    filter_noise: true  # ✓ 有効
    bilateral_filter: true  # ✓ 有効
```

**診断結果に基づく推奨値（有効深度ピクセル0.4%の場合）:**

```yaml
processing:
  tsdf:
    voxel_length: 0.04  # 0.01 → 0.04m (4cm) - ノイズを飲み込ませる
    sdf_trunc: 0.32     # 0.04 * 8 = 0.32
  
  depth:
    trunc: 7.0          # 3.0 → 7.0m（診断結果の99パーセンタイル値、無効値マーカー65m以上を除外）
    filter_noise: true
    bilateral_filter: true
    bilateral_d: 5
    bilateral_sigma_color: 50.0
    bilateral_sigma_space: 50.0
```

**注意:**
- 有効深度ピクセルが0.4%と非常に少ない場合、Androidアプリ側で深度解像度を上げることを強く推奨
- 現在の160x90解像度は非常に低い（推奨: 320x240以上）
- `ANDROID_DEPTH_RESOLUTION_GUIDE.md`を参照してAndroidアプリ側の設定を確認してください

## 📝 次のステップ

1. 診断スクリプトを実行してDepth品質を確認
2. 結果に基づいて上記の対処法を適用
3. メッシュを再生成: `python regenerate_mesh.py <job_id> existing`
4. 結果を確認: `python view_mesh.py data/results/<job_id>/mesh.ply`

## 🆘 それでも改善しない場合

- **COLMAPパイプライン**への移行を検討
- **NeRF / 3D Gaussian Splatting**の使用を検討
- ハードウェアのアップグレード（LiDAR搭載端末など）
最終更新: 2026-01-08 10:14:57
---

# Depth診断とメッシュ品質改善ガイド

## 🔴 最優先: Depthデータの確認

「波打ったカーテン状のメッシュ」が発生する場合、**最も可能性が高い原因はDepthデータの問題**です。

### Step 1: Depthデータの診断

```bash
# 仮想環境をアクティブ化
source venv/bin/activate

# 診断スクリプトを実行
python diagnose_depth.py <job_id>

# 結果をJSONファイルに保存
python diagnose_depth.py <job_id> --output diagnosis_result.json
```

### Step 2: 診断結果の解釈

#### A. Depthデータが存在しない場合

**症状:**
- `has_depth: false`
- `frames_with_depth: 0`

**対処法（優先順位）:**
1. **深度推定を有効化** (`config.yaml`)
   ```yaml
   depth_estimation:
     enable: true
     force_use: true  # DepthデータがあってもMiDaSで再推定
     model: "DPT_Large"
     device: "cuda"
   ```

2. **COLMAPパイプラインに切り替え**
   - ARCore Depthなしでも高品質なメッシュが生成可能
   - 処理時間は長い（数時間）

3. **NeRF / 3D Gaussian Splatting**
   - 最高品質だが、メッシュ抽出が必要

#### B. Depthデータが存在するが品質が悪い場合

**症状:**
- `avg_std_dev > 1.5m` (深度の標準偏差が大きい)
- `avg_valid_ratio < 0.7` (有効ピクセルが少ない)
- `depth_range_m[1] > 10.0m` (異常に大きな深度値)

**対処法（優先順位）:**

### 🔧 1. TSDFパラメータを「粗く」する（最も効果的）

`config.yaml`を編集:

```yaml
processing:
  tsdf:
    voxel_length: 0.03  # 0.01 → 0.03-0.06m に変更（ノイズを飲み込ませる）
    sdf_trunc: 0.24     # voxel_lengthの8倍程度（0.03 * 8 = 0.24）
  
  depth:
    trunc: 2.5          # 3.0 → 2.5-4.0m に短縮（遠距離Depthが一番荒い）
    # 深度前処理を有効化
    filter_noise: true
    bilateral_filter: true
    bilateral_d: 5
    bilateral_sigma_color: 50.0
    bilateral_sigma_space: 50.0
```

**効果:**
- 細かいノイズがボクセルサイズで吸収される
- 遠距離のノイズが除去される
- メモリ使用量も減少

### 🔧 2. Depth前処理を強化

現在の`config.yaml`には基本的なフィルタが含まれていますが、より強力な前処理を追加できます。

**推奨設定:**
```yaml
depth:
  filter_noise: true        # 統計的外れ値除去
  bilateral_filter: true    # エッジ保持平滑化
  bilateral_d: 5
  bilateral_sigma_color: 50.0
  bilateral_sigma_space: 50.0
  # 追加オプション（実装が必要）
  inpaint_holes: true       # 穴埋め
  flying_pixel_removal: true # 飛び値除去
  confidence_threshold: 0.5  # 信頼度しきい値（ARCore Depth Confidence使用時）
```

### 🔧 3. フレームの間引き（Frame Sampling）

ARCoreデータは通常30fpsで記録されますが、TSDF統合には全フレームは不要です。

**実装方法（`rgbd_integration_gpu.py`の`process_session`メソッド）:**
```python
# フレームを間引く（例: 2fpsに減らす）
frames = parser.get_frames_with_depth()
frame_interval = max(1, len(frames) // (target_fps * duration_seconds))
sampled_frames = frames[::frame_interval]
```

**推奨:**
- 動くスキャン: 1-2 fps
- 静止スキャン: 0.5-1 fps

**効果:**
- 似たフレームの重複を減らす
- 姿勢誤差の累積を減らす
- 処理時間の短縮

### 🔧 4. 姿勢（VIO）の最適化（上級）

ARCoreのVIOが少しズレていると、TSDF統合時に段差が積み上がります。

**対策:**
- Open3DのPose Graph Optimizationを使用
- RGBD Odometryで微調整

**実装の複雑度:** 高い（現時点では未実装）

### 🔧 5. メッシュ後処理（最後の手段）

根本原因（Depth/TSDF設定）が解決できない場合の対症療法:

```yaml
mesh:
  quality_improvement:
    enable: true
    subdivision:
      enable: false  # ノイズメッシュには細分化は逆効果
    smoothing:
      enable: true
      method: "laplacian"
      iterations: 3  # 5 → 3 に減らす（やりすぎ注意）
      lambda_filter: 0.3  # 0.5 → 0.3 に減らす
```

## 📊 優先順位まとめ

### 最優先（即座に実施）

1. **Depth診断スクリプトを実行**
   ```bash
   python diagnose_depth.py <job_id>
   ```

2. **Depthデータが無い場合**
   - `depth_estimation.force_use: true` を設定

3. **Depthデータがノイジーな場合**
   - `voxel_length: 0.01 → 0.03-0.06m`
   - `depth_trunc: 3.0 → 2.5-4.0m`
   - `depth.bilateral_filter: true` を確認

### 次に実施（Depthがノイジーな場合）

4. **フレーム間引きの実装**
   - 1-2 fpsに減らす

5. **Depth前処理の強化**
   - 穴埋め、飛び値除去

### 最後の手段

6. **メッシュ後処理の調整**
   - 平滑化パラメータの調整

7. **姿勢最適化（上級）**
   - Pose Graph Optimization

## 🔍 現在の設定確認

現在の`config.yaml`設定（推奨値適用済み）:

```yaml
processing:
  tsdf:
    voxel_length: 0.04  # ✓ ノイズを飲み込ませる設定
    sdf_trunc: 0.32     # ✓ 適切な値
  
  depth:
    trunc: 7.0          # ✓ 診断結果の99パーセンタイル値（無効値を除外）
    filter_noise: true  # ✓ 有効
    bilateral_filter: true  # ✓ 有効
```

**診断結果に基づく推奨値（有効深度ピクセル0.4%の場合）:**

```yaml
processing:
  tsdf:
    voxel_length: 0.04  # 0.01 → 0.04m (4cm) - ノイズを飲み込ませる
    sdf_trunc: 0.32     # 0.04 * 8 = 0.32
  
  depth:
    trunc: 7.0          # 3.0 → 7.0m（診断結果の99パーセンタイル値、無効値マーカー65m以上を除外）
    filter_noise: true
    bilateral_filter: true
    bilateral_d: 5
    bilateral_sigma_color: 50.0
    bilateral_sigma_space: 50.0
```

**注意:**
- 有効深度ピクセルが0.4%と非常に少ない場合、Androidアプリ側で深度解像度を上げることを強く推奨
- 現在の160x90解像度は非常に低い（推奨: 320x240以上）
- `ANDROID_DEPTH_RESOLUTION_GUIDE.md`を参照してAndroidアプリ側の設定を確認してください

## 📝 次のステップ

1. 診断スクリプトを実行してDepth品質を確認
2. 結果に基づいて上記の対処法を適用
3. メッシュを再生成: `python regenerate_mesh.py <job_id> existing`
4. 結果を確認: `python view_mesh.py data/results/<job_id>/mesh.ply`

## 🆘 それでも改善しない場合

- **COLMAPパイプライン**への移行を検討
- **NeRF / 3D Gaussian Splatting**の使用を検討
- ハードウェアのアップグレード（LiDAR搭載端末など）

最終更新: 2026-01-08 10:14:57
---

# Depth診断とメッシュ品質改善ガイド

## 🔴 最優先: Depthデータの確認

「波打ったカーテン状のメッシュ」が発生する場合、**最も可能性が高い原因はDepthデータの問題**です。

### Step 1: Depthデータの診断

```bash
# 仮想環境をアクティブ化
source venv/bin/activate

# 診断スクリプトを実行
python diagnose_depth.py <job_id>

# 結果をJSONファイルに保存
python diagnose_depth.py <job_id> --output diagnosis_result.json
```

### Step 2: 診断結果の解釈

#### A. Depthデータが存在しない場合

**症状:**
- `has_depth: false`
- `frames_with_depth: 0`

**対処法（優先順位）:**
1. **深度推定を有効化** (`config.yaml`)
   ```yaml
   depth_estimation:
     enable: true
     force_use: true  # DepthデータがあってもMiDaSで再推定
     model: "DPT_Large"
     device: "cuda"
   ```

2. **COLMAPパイプラインに切り替え**
   - ARCore Depthなしでも高品質なメッシュが生成可能
   - 処理時間は長い（数時間）

3. **NeRF / 3D Gaussian Splatting**
   - 最高品質だが、メッシュ抽出が必要

#### B. Depthデータが存在するが品質が悪い場合

**症状:**
- `avg_std_dev > 1.5m` (深度の標準偏差が大きい)
- `avg_valid_ratio < 0.7` (有効ピクセルが少ない)
- `depth_range_m[1] > 10.0m` (異常に大きな深度値)

**対処法（優先順位）:**

### 🔧 1. TSDFパラメータを「粗く」する（最も効果的）

`config.yaml`を編集:

```yaml
processing:
  tsdf:
    voxel_length: 0.03  # 0.01 → 0.03-0.06m に変更（ノイズを飲み込ませる）
    sdf_trunc: 0.24     # voxel_lengthの8倍程度（0.03 * 8 = 0.24）
  
  depth:
    trunc: 2.5          # 3.0 → 2.5-4.0m に短縮（遠距離Depthが一番荒い）
    # 深度前処理を有効化
    filter_noise: true
    bilateral_filter: true
    bilateral_d: 5
    bilateral_sigma_color: 50.0
    bilateral_sigma_space: 50.0
```

**効果:**
- 細かいノイズがボクセルサイズで吸収される
- 遠距離のノイズが除去される
- メモリ使用量も減少

### 🔧 2. Depth前処理を強化

現在の`config.yaml`には基本的なフィルタが含まれていますが、より強力な前処理を追加できます。

**推奨設定:**
```yaml
depth:
  filter_noise: true        # 統計的外れ値除去
  bilateral_filter: true    # エッジ保持平滑化
  bilateral_d: 5
  bilateral_sigma_color: 50.0
  bilateral_sigma_space: 50.0
  # 追加オプション（実装が必要）
  inpaint_holes: true       # 穴埋め
  flying_pixel_removal: true # 飛び値除去
  confidence_threshold: 0.5  # 信頼度しきい値（ARCore Depth Confidence使用時）
```

### 🔧 3. フレームの間引き（Frame Sampling）

ARCoreデータは通常30fpsで記録されますが、TSDF統合には全フレームは不要です。

**実装方法（`rgbd_integration_gpu.py`の`process_session`メソッド）:**
```python
# フレームを間引く（例: 2fpsに減らす）
frames = parser.get_frames_with_depth()
frame_interval = max(1, len(frames) // (target_fps * duration_seconds))
sampled_frames = frames[::frame_interval]
```

**推奨:**
- 動くスキャン: 1-2 fps
- 静止スキャン: 0.5-1 fps

**効果:**
- 似たフレームの重複を減らす
- 姿勢誤差の累積を減らす
- 処理時間の短縮

### 🔧 4. 姿勢（VIO）の最適化（上級）

ARCoreのVIOが少しズレていると、TSDF統合時に段差が積み上がります。

**対策:**
- Open3DのPose Graph Optimizationを使用
- RGBD Odometryで微調整

**実装の複雑度:** 高い（現時点では未実装）

### 🔧 5. メッシュ後処理（最後の手段）

根本原因（Depth/TSDF設定）が解決できない場合の対症療法:

```yaml
mesh:
  quality_improvement:
    enable: true
    subdivision:
      enable: false  # ノイズメッシュには細分化は逆効果
    smoothing:
      enable: true
      method: "laplacian"
      iterations: 3  # 5 → 3 に減らす（やりすぎ注意）
      lambda_filter: 0.3  # 0.5 → 0.3 に減らす
```

## 📊 優先順位まとめ

### 最優先（即座に実施）

1. **Depth診断スクリプトを実行**
   ```bash
   python diagnose_depth.py <job_id>
   ```

2. **Depthデータが無い場合**
   - `depth_estimation.force_use: true` を設定

3. **Depthデータがノイジーな場合**
   - `voxel_length: 0.01 → 0.03-0.06m`
   - `depth_trunc: 3.0 → 2.5-4.0m`
   - `depth.bilateral_filter: true` を確認

### 次に実施（Depthがノイジーな場合）

4. **フレーム間引きの実装**
   - 1-2 fpsに減らす

5. **Depth前処理の強化**
   - 穴埋め、飛び値除去

### 最後の手段

6. **メッシュ後処理の調整**
   - 平滑化パラメータの調整

7. **姿勢最適化（上級）**
   - Pose Graph Optimization

## 🔍 現在の設定確認

現在の`config.yaml`設定（推奨値適用済み）:

```yaml
processing:
  tsdf:
    voxel_length: 0.04  # ✓ ノイズを飲み込ませる設定
    sdf_trunc: 0.32     # ✓ 適切な値
  
  depth:
    trunc: 7.0          # ✓ 診断結果の99パーセンタイル値（無効値を除外）
    filter_noise: true  # ✓ 有効
    bilateral_filter: true  # ✓ 有効
```

**診断結果に基づく推奨値（有効深度ピクセル0.4%の場合）:**

```yaml
processing:
  tsdf:
    voxel_length: 0.04  # 0.01 → 0.04m (4cm) - ノイズを飲み込ませる
    sdf_trunc: 0.32     # 0.04 * 8 = 0.32
  
  depth:
    trunc: 7.0          # 3.0 → 7.0m（診断結果の99パーセンタイル値、無効値マーカー65m以上を除外）
    filter_noise: true
    bilateral_filter: true
    bilateral_d: 5
    bilateral_sigma_color: 50.0
    bilateral_sigma_space: 50.0
```

**注意:**
- 有効深度ピクセルが0.4%と非常に少ない場合、Androidアプリ側で深度解像度を上げることを強く推奨
- 現在の160x90解像度は非常に低い（推奨: 320x240以上）
- `ANDROID_DEPTH_RESOLUTION_GUIDE.md`を参照してAndroidアプリ側の設定を確認してください

## 📝 次のステップ

1. 診断スクリプトを実行してDepth品質を確認
2. 結果に基づいて上記の対処法を適用
3. メッシュを再生成: `python regenerate_mesh.py <job_id> existing`
4. 結果を確認: `python view_mesh.py data/results/<job_id>/mesh.ply`

## 🆘 それでも改善しない場合

- **COLMAPパイプライン**への移行を検討
- **NeRF / 3D Gaussian Splatting**の使用を検討
- ハードウェアのアップグレード（LiDAR搭載端末など）

最終更新: 2026-01-08 10:14:57
---

# Depth診断とメッシュ品質改善ガイド

## 🔴 最優先: Depthデータの確認

「波打ったカーテン状のメッシュ」が発生する場合、**最も可能性が高い原因はDepthデータの問題**です。

### Step 1: Depthデータの診断

```bash
# 仮想環境をアクティブ化
source venv/bin/activate

# 診断スクリプトを実行
python diagnose_depth.py <job_id>

# 結果をJSONファイルに保存
python diagnose_depth.py <job_id> --output diagnosis_result.json
```

### Step 2: 診断結果の解釈

#### A. Depthデータが存在しない場合

**症状:**
- `has_depth: false`
- `frames_with_depth: 0`

**対処法（優先順位）:**
1. **深度推定を有効化** (`config.yaml`)
   ```yaml
   depth_estimation:
     enable: true
     force_use: true  # DepthデータがあってもMiDaSで再推定
     model: "DPT_Large"
     device: "cuda"
   ```

2. **COLMAPパイプラインに切り替え**
   - ARCore Depthなしでも高品質なメッシュが生成可能
   - 処理時間は長い（数時間）

3. **NeRF / 3D Gaussian Splatting**
   - 最高品質だが、メッシュ抽出が必要

#### B. Depthデータが存在するが品質が悪い場合

**症状:**
- `avg_std_dev > 1.5m` (深度の標準偏差が大きい)
- `avg_valid_ratio < 0.7` (有効ピクセルが少ない)
- `depth_range_m[1] > 10.0m` (異常に大きな深度値)

**対処法（優先順位）:**

### 🔧 1. TSDFパラメータを「粗く」する（最も効果的）

`config.yaml`を編集:

```yaml
processing:
  tsdf:
    voxel_length: 0.03  # 0.01 → 0.03-0.06m に変更（ノイズを飲み込ませる）
    sdf_trunc: 0.24     # voxel_lengthの8倍程度（0.03 * 8 = 0.24）
  
  depth:
    trunc: 2.5          # 3.0 → 2.5-4.0m に短縮（遠距離Depthが一番荒い）
    # 深度前処理を有効化
    filter_noise: true
    bilateral_filter: true
    bilateral_d: 5
    bilateral_sigma_color: 50.0
    bilateral_sigma_space: 50.0
```

**効果:**
- 細かいノイズがボクセルサイズで吸収される
- 遠距離のノイズが除去される
- メモリ使用量も減少

### 🔧 2. Depth前処理を強化

現在の`config.yaml`には基本的なフィルタが含まれていますが、より強力な前処理を追加できます。

**推奨設定:**
```yaml
depth:
  filter_noise: true        # 統計的外れ値除去
  bilateral_filter: true    # エッジ保持平滑化
  bilateral_d: 5
  bilateral_sigma_color: 50.0
  bilateral_sigma_space: 50.0
  # 追加オプション（実装が必要）
  inpaint_holes: true       # 穴埋め
  flying_pixel_removal: true # 飛び値除去
  confidence_threshold: 0.5  # 信頼度しきい値（ARCore Depth Confidence使用時）
```

### 🔧 3. フレームの間引き（Frame Sampling）

ARCoreデータは通常30fpsで記録されますが、TSDF統合には全フレームは不要です。

**実装方法（`rgbd_integration_gpu.py`の`process_session`メソッド）:**
```python
# フレームを間引く（例: 2fpsに減らす）
frames = parser.get_frames_with_depth()
frame_interval = max(1, len(frames) // (target_fps * duration_seconds))
sampled_frames = frames[::frame_interval]
```

**推奨:**
- 動くスキャン: 1-2 fps
- 静止スキャン: 0.5-1 fps

**効果:**
- 似たフレームの重複を減らす
- 姿勢誤差の累積を減らす
- 処理時間の短縮

### 🔧 4. 姿勢（VIO）の最適化（上級）

ARCoreのVIOが少しズレていると、TSDF統合時に段差が積み上がります。

**対策:**
- Open3DのPose Graph Optimizationを使用
- RGBD Odometryで微調整

**実装の複雑度:** 高い（現時点では未実装）

### 🔧 5. メッシュ後処理（最後の手段）

根本原因（Depth/TSDF設定）が解決できない場合の対症療法:

```yaml
mesh:
  quality_improvement:
    enable: true
    subdivision:
      enable: false  # ノイズメッシュには細分化は逆効果
    smoothing:
      enable: true
      method: "laplacian"
      iterations: 3  # 5 → 3 に減らす（やりすぎ注意）
      lambda_filter: 0.3  # 0.5 → 0.3 に減らす
```

## 📊 優先順位まとめ

### 最優先（即座に実施）

1. **Depth診断スクリプトを実行**
   ```bash
   python diagnose_depth.py <job_id>
   ```

2. **Depthデータが無い場合**
   - `depth_estimation.force_use: true` を設定

3. **Depthデータがノイジーな場合**
   - `voxel_length: 0.01 → 0.03-0.06m`
   - `depth_trunc: 3.0 → 2.5-4.0m`
   - `depth.bilateral_filter: true` を確認

### 次に実施（Depthがノイジーな場合）

4. **フレーム間引きの実装**
   - 1-2 fpsに減らす

5. **Depth前処理の強化**
   - 穴埋め、飛び値除去

### 最後の手段

6. **メッシュ後処理の調整**
   - 平滑化パラメータの調整

7. **姿勢最適化（上級）**
   - Pose Graph Optimization

## 🔍 現在の設定確認

現在の`config.yaml`設定（推奨値適用済み）:

```yaml
processing:
  tsdf:
    voxel_length: 0.04  # ✓ ノイズを飲み込ませる設定
    sdf_trunc: 0.32     # ✓ 適切な値
  
  depth:
    trunc: 7.0          # ✓ 診断結果の99パーセンタイル値（無効値を除外）
    filter_noise: true  # ✓ 有効
    bilateral_filter: true  # ✓ 有効
```

**診断結果に基づく推奨値（有効深度ピクセル0.4%の場合）:**

```yaml
processing:
  tsdf:
    voxel_length: 0.04  # 0.01 → 0.04m (4cm) - ノイズを飲み込ませる
    sdf_trunc: 0.32     # 0.04 * 8 = 0.32
  
  depth:
    trunc: 7.0          # 3.0 → 7.0m（診断結果の99パーセンタイル値、無効値マーカー65m以上を除外）
    filter_noise: true
    bilateral_filter: true
    bilateral_d: 5
    bilateral_sigma_color: 50.0
    bilateral_sigma_space: 50.0
```

**注意:**
- 有効深度ピクセルが0.4%と非常に少ない場合、Androidアプリ側で深度解像度を上げることを強く推奨
- 現在の160x90解像度は非常に低い（推奨: 320x240以上）
- `ANDROID_DEPTH_RESOLUTION_GUIDE.md`を参照してAndroidアプリ側の設定を確認してください

## 📝 次のステップ

1. 診断スクリプトを実行してDepth品質を確認
2. 結果に基づいて上記の対処法を適用
3. メッシュを再生成: `python regenerate_mesh.py <job_id> existing`
4. 結果を確認: `python view_mesh.py data/results/<job_id>/mesh.ply`

## 🆘 それでも改善しない場合

- **COLMAPパイプライン**への移行を検討
- **NeRF / 3D Gaussian Splatting**の使用を検討
- ハードウェアのアップグレード（LiDAR搭載端末など）

最終更新: 2026-01-08 10:14:57
---

# Depth診断とメッシュ品質改善ガイド

## 🔴 最優先: Depthデータの確認

「波打ったカーテン状のメッシュ」が発生する場合、**最も可能性が高い原因はDepthデータの問題**です。

### Step 1: Depthデータの診断

```bash
# 仮想環境をアクティブ化
source venv/bin/activate

# 診断スクリプトを実行
python diagnose_depth.py <job_id>

# 結果をJSONファイルに保存
python diagnose_depth.py <job_id> --output diagnosis_result.json
```

### Step 2: 診断結果の解釈

#### A. Depthデータが存在しない場合

**症状:**
- `has_depth: false`
- `frames_with_depth: 0`

**対処法（優先順位）:**
1. **深度推定を有効化** (`config.yaml`)
   ```yaml
   depth_estimation:
     enable: true
     force_use: true  # DepthデータがあってもMiDaSで再推定
     model: "DPT_Large"
     device: "cuda"
   ```

2. **COLMAPパイプラインに切り替え**
   - ARCore Depthなしでも高品質なメッシュが生成可能
   - 処理時間は長い（数時間）

3. **NeRF / 3D Gaussian Splatting**
   - 最高品質だが、メッシュ抽出が必要

#### B. Depthデータが存在するが品質が悪い場合

**症状:**
- `avg_std_dev > 1.5m` (深度の標準偏差が大きい)
- `avg_valid_ratio < 0.7` (有効ピクセルが少ない)
- `depth_range_m[1] > 10.0m` (異常に大きな深度値)

**対処法（優先順位）:**

### 🔧 1. TSDFパラメータを「粗く」する（最も効果的）

`config.yaml`を編集:

```yaml
processing:
  tsdf:
    voxel_length: 0.03  # 0.01 → 0.03-0.06m に変更（ノイズを飲み込ませる）
    sdf_trunc: 0.24     # voxel_lengthの8倍程度（0.03 * 8 = 0.24）
  
  depth:
    trunc: 2.5          # 3.0 → 2.5-4.0m に短縮（遠距離Depthが一番荒い）
    # 深度前処理を有効化
    filter_noise: true
    bilateral_filter: true
    bilateral_d: 5
    bilateral_sigma_color: 50.0
    bilateral_sigma_space: 50.0
```

**効果:**
- 細かいノイズがボクセルサイズで吸収される
- 遠距離のノイズが除去される
- メモリ使用量も減少

### 🔧 2. Depth前処理を強化

現在の`config.yaml`には基本的なフィルタが含まれていますが、より強力な前処理を追加できます。

**推奨設定:**
```yaml
depth:
  filter_noise: true        # 統計的外れ値除去
  bilateral_filter: true    # エッジ保持平滑化
  bilateral_d: 5
  bilateral_sigma_color: 50.0
  bilateral_sigma_space: 50.0
  # 追加オプション（実装が必要）
  inpaint_holes: true       # 穴埋め
  flying_pixel_removal: true # 飛び値除去
  confidence_threshold: 0.5  # 信頼度しきい値（ARCore Depth Confidence使用時）
```

### 🔧 3. フレームの間引き（Frame Sampling）

ARCoreデータは通常30fpsで記録されますが、TSDF統合には全フレームは不要です。

**実装方法（`rgbd_integration_gpu.py`の`process_session`メソッド）:**
```python
# フレームを間引く（例: 2fpsに減らす）
frames = parser.get_frames_with_depth()
frame_interval = max(1, len(frames) // (target_fps * duration_seconds))
sampled_frames = frames[::frame_interval]
```

**推奨:**
- 動くスキャン: 1-2 fps
- 静止スキャン: 0.5-1 fps

**効果:**
- 似たフレームの重複を減らす
- 姿勢誤差の累積を減らす
- 処理時間の短縮

### 🔧 4. 姿勢（VIO）の最適化（上級）

ARCoreのVIOが少しズレていると、TSDF統合時に段差が積み上がります。

**対策:**
- Open3DのPose Graph Optimizationを使用
- RGBD Odometryで微調整

**実装の複雑度:** 高い（現時点では未実装）

### 🔧 5. メッシュ後処理（最後の手段）

根本原因（Depth/TSDF設定）が解決できない場合の対症療法:

```yaml
mesh:
  quality_improvement:
    enable: true
    subdivision:
      enable: false  # ノイズメッシュには細分化は逆効果
    smoothing:
      enable: true
      method: "laplacian"
      iterations: 3  # 5 → 3 に減らす（やりすぎ注意）
      lambda_filter: 0.3  # 0.5 → 0.3 に減らす
```

## 📊 優先順位まとめ

### 最優先（即座に実施）

1. **Depth診断スクリプトを実行**
   ```bash
   python diagnose_depth.py <job_id>
   ```

2. **Depthデータが無い場合**
   - `depth_estimation.force_use: true` を設定

3. **Depthデータがノイジーな場合**
   - `voxel_length: 0.01 → 0.03-0.06m`
   - `depth_trunc: 3.0 → 2.5-4.0m`
   - `depth.bilateral_filter: true` を確認

### 次に実施（Depthがノイジーな場合）

4. **フレーム間引きの実装**
   - 1-2 fpsに減らす

5. **Depth前処理の強化**
   - 穴埋め、飛び値除去

### 最後の手段

6. **メッシュ後処理の調整**
   - 平滑化パラメータの調整

7. **姿勢最適化（上級）**
   - Pose Graph Optimization

## 🔍 現在の設定確認

現在の`config.yaml`設定（推奨値適用済み）:

```yaml
processing:
  tsdf:
    voxel_length: 0.04  # ✓ ノイズを飲み込ませる設定
    sdf_trunc: 0.32     # ✓ 適切な値
  
  depth:
    trunc: 7.0          # ✓ 診断結果の99パーセンタイル値（無効値を除外）
    filter_noise: true  # ✓ 有効
    bilateral_filter: true  # ✓ 有効
```

**診断結果に基づく推奨値（有効深度ピクセル0.4%の場合）:**

```yaml
processing:
  tsdf:
    voxel_length: 0.04  # 0.01 → 0.04m (4cm) - ノイズを飲み込ませる
    sdf_trunc: 0.32     # 0.04 * 8 = 0.32
  
  depth:
    trunc: 7.0          # 3.0 → 7.0m（診断結果の99パーセンタイル値、無効値マーカー65m以上を除外）
    filter_noise: true
    bilateral_filter: true
    bilateral_d: 5
    bilateral_sigma_color: 50.0
    bilateral_sigma_space: 50.0
```

**注意:**
- 有効深度ピクセルが0.4%と非常に少ない場合、Androidアプリ側で深度解像度を上げることを強く推奨
- 現在の160x90解像度は非常に低い（推奨: 320x240以上）
- `ANDROID_DEPTH_RESOLUTION_GUIDE.md`を参照してAndroidアプリ側の設定を確認してください

## 📝 次のステップ

1. 診断スクリプトを実行してDepth品質を確認
2. 結果に基づいて上記の対処法を適用
3. メッシュを再生成: `python regenerate_mesh.py <job_id> existing`
4. 結果を確認: `python view_mesh.py data/results/<job_id>/mesh.ply`

## 🆘 それでも改善しない場合

- **COLMAPパイプライン**への移行を検討
- **NeRF / 3D Gaussian Splatting**の使用を検討
- ハードウェアのアップグレード（LiDAR搭載端末など）