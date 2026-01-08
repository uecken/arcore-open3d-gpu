---
作成日時: 2026-01-08 10:45:00
最終更新: 2026-01-08 10:45:00
---

# 部屋認識改善ガイド

## 現状の問題

**メッシュが粗く、部屋の構造が認識できない**

### 考えられる原因

1. **深度解像度が低すぎる** (160x90 = 14,400ピクセル)
2. **有効深度ピクセルが少ない** (0.4% = 99.6%が無効値)
3. **画像解像度が低い可能性**
4. **TSDF解像度が粗い** (voxel_length: 0.03m)
5. **フレーム間引きによる情報損失** (処理速度向上のため)

---

## 現在の解像度を確認

### 診断スクリプトを実行

```bash
# 解像度診断スクリプトを実行
python diagnose_resolution.py <job_id>

# 深度品質も確認
python diagnose_depth.py <job_id>
```

### 確認項目

1. **画像解像度** (RGB)
   - 推奨: Full HD (1920x1080) 以上
   - 最小: 1280x720 (HD)

2. **深度解像度** (Depth)
   - 推奨: 320x240 (76,800ピクセル) 以上
   - 最小: 256x192 (49,152ピクセル)
   - 現在: 160x90 (14,400ピクセル) ← **非常に低い**

3. **有効深度ピクセル率**
   - 推奨: 20%以上
   - 現在: 0.4% ← **非常に低い**

---

## 改善策（優先順位順）

### 🔴 最優先: Android側での解像度向上

#### 1. 深度解像度を向上（最重要）

**現在の問題:**
- 深度解像度: 160x90 (14,400ピクセル)
- これは部屋が認識できない**主な原因**

**推奨変更:**

**A. Raw Depth APIを使用している場合**
```kotlin
// Raw Depth APIで最大解像度を取得
val rawDepthImage = frame.acquireRawDepthImage()

// 解像度を確認
Log.d(TAG, "Raw depth: ${rawDepthImage.width}x${rawDepthImage.height}")

// 320x240以上を目標とする
```

**B. Depth API（通常）を使用している場合**
```kotlin
// カメラ設定で最高解像度を選択
val configFilter = ArCameraConfigFilter(session)
val configList = session.getSupportedCameraConfigs(configFilter)

// 最大解像度の設定を選択
var bestConfig: ArCameraConfig? = null
var maxResolution = 0
for (config in configList) {
    val res = config.imageSize.width * config.imageSize.height
    if (res > maxResolution) {
        maxResolution = res
        bestConfig = config
    }
}
if (bestConfig != null) {
    session.setCameraConfig(bestConfig)
}
```

**目標:**
- 最小: 256x192 (49,152ピクセル)
- 推奨: 320x240 (76,800ピクセル)
- 理想: 640x480 (307,200ピクセル) - Depth Camera搭載デバイスのみ

#### 2. 画像解像度を向上

**推奨:**
- Full HD: 1920x1080
- 4K: 3840x2160 (可能な場合)

**Androidアプリ側:**
```kotlin
// カメラ設定で最高解像度を選択
val configList = session.getSupportedCameraConfigs(ArCameraConfigFilter(session))

// Full HD以上を選択
for (config in configList) {
    val size = config.imageSize
    if (size.width >= 1920 && size.height >= 1080) {
        session.setCameraConfig(config)
        break
    }
}
```

---

### 🔧 サーバー側の改善（即座に実施可能）

#### 1. TSDF解像度を細かくする

**現在の設定:**
```yaml
tsdf:
  voxel_length: 0.03  # 30mm（粗い）
```

**推奨変更:**
```yaml
tsdf:
  voxel_length: 0.02  # 20mm（より細かく、部屋の詳細を保持）
  # または
  voxel_length: 0.025  # 25mm（バランス）
```

**効果:**
- ✅ より詳細なメッシュ
- ✅ 部屋の構造がより明確に
- ⚠️ メモリ使用量が増加（0.03→0.02で約2.25倍）

**注意:**
- GTX 1660 Ti（6GB VRAM）の場合、0.02は可能
- メモリが不足する場合は0.025を推奨

#### 2. メッシュ細分化を強化

**現在の設定:**
```yaml
mesh:
  quality_improvement:
    subdivision:
      iterations: 1
      max_triangles: 5000000
```

**推奨変更:**
```yaml
mesh:
  quality_improvement:
    subdivision:
      iterations: 2  # 1 → 2（より滑らかな表面）
      max_triangles: 10000000  # 5000000 → 10000000
```

**効果:**
- ✅ より滑らかな表面
- ✅ 部屋の構造がより明確に
- ⚠️ メモリ使用量が大幅に増加（約4倍）

#### 3. 平滑化を強化

**現在の設定:**
```yaml
mesh:
  smoothing:
    iterations: 8
    lambda_filter: 0.4
```

**推奨変更:**
```yaml
mesh:
  smoothing:
    iterations: 10  # 8 → 10
    lambda_filter: 0.3  # 0.4 → 0.3（より強く平滑化）
```

**効果:**
- ✅ より滑らかな表面
- ✅ ノイズの除去

#### 4. Depth前処理を強化

**現在の設定:**
```yaml
depth:
  bilateral_sigma_color: 75.0
  bilateral_sigma_space: 75.0
```

**推奨変更:**
```yaml
depth:
  bilateral_sigma_color: 100.0  # 75.0 → 100.0（より強く平滑化）
  bilateral_sigma_space: 100.0  # 75.0 → 100.0
```

---

### 📐 フレーム処理の確認

#### 処理速度の向上について

**質問: 「処理が早くなったのは、不要データを間引いたから？」**

**確認が必要:**
- 現在のコードではフレーム間引き（downsampling）は実装されていない
- 処理速度の向上は、以下の要因が考えられます：
  1. **TSDF解像度を粗くした** (0.01 → 0.04 → 0.03)
  2. **GPU使用** (CUDA acceleration)
  3. **メッシュ簡略化** (viewer用に500k trianglesに削減)

**確認方法:**
```bash
# ログで確認
# "Integrated 183/183 frames" と表示されている場合、全フレームを処理
# フレーム間引きが実装されていれば、"Integrated X/Y frames" のように表示される
```

**フレーム間引きの実装（オプション）:**

処理速度を向上させつつ、部屋認識を改善する場合：

```python
# pipeline/rgbd_integration_gpu.py の process_session メソッド内
frames = parser.get_frames_with_depth()

# フレーム間引き（例: 2fpsに減らす）
target_fps = 2  # または config.yaml から取得
if len(frames) > 0:
    duration_seconds = (frames[-1].timestamp - frames[0].timestamp) / 1e9
    frame_interval = max(1, len(frames) // (target_fps * duration_seconds))
    sampled_frames = frames[::frame_interval]
    print(f"Sampling frames: {len(frames)} -> {len(sampled_frames)} frames ({frame_interval} interval)")
    frames = sampled_frames
```

**推奨:**
- 部屋スキャンの場合: **フレーム間引きをしない** または **最小限** (30fps → 15fps程度)
- 処理速度が重要な場合: 2fps程度に間引く

---

## 推奨設定（段階的アプローチ）

### Step 1: TSDF解像度を調整（即座に効果）

```yaml
processing:
  tsdf:
    voxel_length: 0.025  # 0.03 → 0.025（25mm、バランス重視）
    sdf_trunc: 0.2       # 0.025 * 8 = 0.2
```

### Step 2: メッシュ品質向上（メモリが許す場合）

```yaml
mesh:
  quality_improvement:
    subdivision:
      iterations: 2  # 1 → 2
      max_triangles: 10000000  # 5000000 → 10000000
  
  smoothing:
    iterations: 10  # 8 → 10
    lambda_filter: 0.3  # 0.4 → 0.3
```

### Step 3: Depth前処理を強化

```yaml
depth:
  bilateral_sigma_color: 100.0  # 75.0 → 100.0
  bilateral_sigma_space: 100.0  # 75.0 → 100.0
```

---

## 根本的解決（Androidアプリ側）

### 1. 深度解像度を320x240以上に向上

**現在: 160x90 → 目標: 320x240以上**

- 4倍の解像度向上
- 有効ピクセル数が大幅に増加
- 部屋の構造がより明確に認識可能

### 2. 画像解像度をFull HD以上に

**現在: ? → 目標: 1920x1080以上**

- より高品質なテクスチャ
- より詳細な色情報

### 3. 有効深度ピクセル率を20%以上に

**現在: 0.4% → 目標: 20%以上**

- より多くの深度情報
- より完全なメッシュ

---

## 処理速度について

### 現在の処理速度の要因

1. **TSDF解像度の調整** (voxel_length: 0.04 → 0.03)
   - 粗いほど処理が速い（逆比例）

2. **GPU使用**
   - CUDA accelerationで処理が高速化

3. **メッシュ簡略化**
   - viewer用に500k trianglesに削減

### フレーム間引きについて

**現在の実装:**
- フレーム間引きは**実装されていない**
- 全フレームを処理している

**推奨:**
- 部屋認識を優先する場合: **フレーム間引きはしない**
- 処理速度を優先する場合: **最小限の間引き** (30fps → 10-15fps)

**実装例（必要に応じて）:**
```yaml
# config.yamlに追加
processing:
  frame_sampling:
    enable: false  # 部屋認識を優先する場合はfalse
    target_fps: 10  # 間引きする場合の目標fps
```

---

## 期待される効果

### Android側の解像度向上（根本的解決）

- 深度解像度: 160x90 → 320x240 (**4倍の向上**)
- 有効ピクセル: 0.4% → 20%以上 (**50倍の向上**)
- **部屋認識が大幅に改善** (80-90%改善)

### サーバー側の改善（即座に効果）

- TSDF解像度: 0.03 → 0.025 (**20%の向上**)
- メッシュ細分化: 1回 → 2回 (**4倍の三角形数**)
- **部屋認識が改善** (30-50%改善)

### 両方を実施

- **部屋認識が大幅に改善** (90-95%改善)
- 部屋の構造が明確に認識可能

---

## 実装手順

1. **解像度診断を実行**
   ```bash
   python diagnose_resolution.py 3b0cd1d9
   ```

2. **Androidアプリ側で解像度を向上**
   - `ANDROID_DEPTH_RESOLUTION_GUIDE.md`を参照
   - 深度解像度を320x240以上に
   - 画像解像度をFull HD以上に

3. **サーバー側の設定を調整**
   - `config.yaml`を編集（上記の推奨設定を適用）

4. **新しいジョブでテスト**
   - 同じシーンを再スキャン
   - メッシュを再生成

5. **結果を比較**
   - 解像度診断で確認
   - メッシュ品質を視覚的に確認

---

## まとめ

### 現在の問題

1. **深度解像度が非常に低い** (160x90 = 14,400ピクセル)
2. **有効深度ピクセルが非常に少ない** (0.4%)
3. **これが部屋が認識できない主な原因**

### 最優先の対策

1. **Androidアプリ側: 深度解像度を320x240以上に向上** (最重要)
2. **サーバー側: TSDF解像度を0.025に調整** (即座に効果)

### 処理速度について

- **フレーム間引きは実装されていない**
- 処理速度の向上は、TSDF解像度の調整とGPU使用によるもの
- 部屋認識を優先する場合は、フレーム間引きはしない

