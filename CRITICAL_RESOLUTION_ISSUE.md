---
作成日時: 2026-01-08 10:50:00
最終更新: 2026-01-08 10:50:00
---

# 🔴 重要な解像度問題: 部屋認識不能の主因

## 診断結果サマリー

### 現在の解像度状況

**画像解像度:**
- **480x640** (307,200ピクセル) ⚠️ 低い（HD未満）
- Full HD (1920x1080) の約 **25%**

**深度解像度:**
- **160x90** (14,400ピクセル) ❌ **非常に低い**
- 推奨 (320x240 = 76,800ピクセル) の約 **19%**
- 部屋認識ができない**主な原因**

**深度/画像比:**
- **4.7%** ❌ **非常に低い**
- 理想: 20-50%
- 現在は理想の約 **10-24%**

---

## 問題の影響

### 1. 部屋が認識できない

**原因:**
- 深度解像度が低すぎる（160x90 = 14,400ピクセル）
- 有効深度ピクセルが少ない（0.4%）
- 深度情報が不足している

**影響:**
- 部屋の構造が不明確
- 壁、床、天井が認識できない
- メッシュが粗く、フラグメント化

### 2. 画像解像度も低い

**原因:**
- 480x640（HD未満）
- Full HD (1920x1080) の約25%

**影響:**
- テクスチャ品質が低い
- 詳細が失われる

---

## 🔴 最優先対策（Androidアプリ側）

### Step 1: 深度解像度を320x240以上に向上（最重要）

**現在: 160x90 (14,400ピクセル)**
**目標: 320x240 (76,800ピクセル) 以上**

**実装方法:**

#### A. Raw Depth APIを使用している場合

```kotlin
// 現在の実装を確認
val rawDepthImage = frame.acquireRawDepthImage()
Log.d(TAG, "Raw depth: ${rawDepthImage.width}x${rawDepthImage.height}")

// 解像度が低い場合、カメラ設定を変更
val configFilter = ArCameraConfigFilter(session)
configFilter.setDepthSensorUsage(ArCameraConfig.DepthSensorUsage.REQUIRE_AND_USE)
val configList = session.getSupportedCameraConfigs(configFilter)

// 最大解像度の設定を選択
var bestConfig: ArCameraConfig? = null
var maxResolution = 0
for (config in configList) {
    val size = config.imageSize
    val res = size.width * size.height
    if (res > maxResolution) {
        maxResolution = res
        bestConfig = config
    }
}
if (bestConfig != null) {
    session.setCameraConfig(bestConfig)
    Log.d(TAG, "Camera config updated: ${bestConfig.imageSize}")
}
```

#### B. Depth API（通常）を使用している場合

```kotlin
// Depth APIでも解像度を確認
val depthImage = frame.acquireDepthImage()
Log.d(TAG, "Depth: ${depthImage.width}x${depthImage.height}")

// 解像度が低い場合、同じくカメラ設定を変更
```

**期待される改善:**
- 深度解像度: 160x90 → 320x240 (**5.3倍の向上**)
- 有効ピクセル: 0.4% → 20%以上 (**50倍の向上**)
- **部屋認識が大幅に改善** (80-90%改善)

### Step 2: 画像解像度をFull HD以上に向上

**現在: 480x640 (307,200ピクセル)**
**目標: Full HD 1920x1080 (2,073,600ピクセル) 以上**

**実装方法:**

```kotlin
// カメラ設定でFull HD以上を選択
val configList = session.getSupportedCameraConfigs(ArCameraConfigFilter(session))

for (config in configList) {
    val size = config.imageSize
    // Full HD以上を探す
    if (size.width >= 1920 && size.height >= 1080) {
        session.setCameraConfig(config)
        Log.d(TAG, "Camera config: ${size.width}x${size.height}")
        break
    }
    // または、最も近い解像度を選択
    if (size.width >= 1280) {
        session.setCameraConfig(config)
        Log.d(TAG, "Camera config: ${size.width}x${size.height}")
        break
    }
}
```

**期待される改善:**
- 画像解像度: 480x640 → 1920x1080 (**6.75倍の向上**)
- より高品質なテクスチャ
- より詳細な色情報

---

## 🔧 サーバー側の改善（即座に実施）

### 設定変更（config.yaml）

```yaml
processing:
  tsdf:
    # 診断結果に基づく設定（深度解像度が低いため、可能な限り細かく）
    voxel_length: 0.02         # 0.03 → 0.02（20mm、部屋の詳細を保持）
    sdf_trunc: 0.16            # 0.02 * 8 = 0.16
  
  depth:
    trunc: 7.0                 # 無効値マーカーを除外
    bilateral_sigma_color: 100.0  # 75.0 → 100.0（より強く平滑化）
    bilateral_sigma_space: 100.0  # 75.0 → 100.0

mesh:
  quality_improvement:
    subdivision:
      iterations: 2            # 1 → 2（より滑らかな表面）
      max_triangles: 10000000  # 5000000 → 10000000
  
  smoothing:
    iterations: 10             # 8 → 10（より滑らかに）
    lambda_filter: 0.3         # 0.4 → 0.3（より強く平滑化）
```

**注意:**
- `voxel_length: 0.02` はメモリ使用量が増加（約1.5倍）
- GTX 1660 Ti（6GB VRAM）では可能だが、メモリ不足の場合は0.025に調整

---

## 期待される改善効果

### Android側の解像度向上（根本的解決）

**深度解像度向上:**
- 現在: 160x90 = 14,400ピクセル
- 目標: 320x240 = 76,800ピクセル
- **5.3倍の向上**

**画像解像度向上:**
- 現在: 480x640 = 307,200ピクセル
- 目標: 1920x1080 = 2,073,600ピクセル
- **6.75倍の向上**

**部屋認識の改善:**
- **80-90%改善**が期待できる

### サーバー側の設定変更（即座に効果）

**TSDF解像度調整:**
- `voxel_length: 0.03 → 0.02` (約1.5倍細かく)
- **20-30%改善**が期待できる

**メッシュ品質向上:**
- 細分化: 1回 → 2回
- 平滑化: 8回 → 10回
- **10-20%改善**が期待できる

### 両方を実施

- **部屋認識が大幅に改善** (90-95%改善)
- 部屋の構造が明確に認識可能
- 壁、床、天井が明確に表示される

---

## 実装手順

### 即座に実施（サーバー側）

1. **config.yamlを変更**（上記の設定を適用）

2. **メッシュを再生成**
   ```bash
   python regenerate_mesh.py 3b0cd1d9 existing
   ```

3. **結果を確認**
   - viewerで確認
   - 改善が不十分な場合はAndroid側の対策が必要

### 根本的解決（Androidアプリ側）

1. **深度解像度を確認**
   ```kotlin
   val depthImage = frame.acquireDepthImage()
   Log.d(TAG, "Depth resolution: ${depthImage.width}x${depthImage.height}")
   ```

2. **カメラ設定で最高解像度を選択**
   - `ANDROID_DEPTH_RESOLUTION_GUIDE.md`を参照

3. **画像解像度も向上**
   - Full HD (1920x1080) 以上を選択

4. **新しいジョブでテスト**
   - 同じシーンを再スキャン
   - 解像度診断で確認
   - メッシュ品質を比較

---

## まとめ

### 現在の問題

1. **深度解像度が非常に低い** (160x90 = 14,400ピクセル)
   - 理想の19%
   - **部屋認識不能の主因**

2. **画像解像度が低い** (480x640 = 307,200ピクセル)
   - Full HDの約25%

3. **深度/画像比が非常に低い** (4.7%)
   - 理想は20-50%

### 最優先の対策

1. **🔴 Androidアプリ側: 深度解像度を320x240以上に** (最重要)
   - 5.3倍の向上
   - 部屋認識が大幅に改善

2. **🟡 Androidアプリ側: 画像解像度をFull HD以上に**
   - 6.75倍の向上
   - より高品質なテクスチャ

3. **🔧 サーバー側: TSDF解像度を0.02に調整** (即座に効果)
   - 20-30%改善
   - メモリが許す範囲で実施

### 期待される最終結果

- **部屋認識が大幅に改善** (90-95%改善)
- 部屋の構造が明確に認識可能
- 壁、床、天井が明確に表示される
- より高品質なメッシュ

