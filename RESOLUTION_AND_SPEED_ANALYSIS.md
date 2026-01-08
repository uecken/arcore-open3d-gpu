---
作成日時: 2026-01-08 10:45:00
最終更新: 2026-01-08 10:45:00
---

# 解像度と処理速度の分析

## 現在の解像度状況

### 確認方法

```bash
# 解像度診断スクリプトを実行
python diagnose_resolution.py 3b0cd1d9
```

### 期待される結果

**深度解像度:**
- 現在: 160x90 (14,400ピクセル) ← **非常に低い**
- 推奨: 320x240 (76,800ピクセル) 以上
- 理想: 640x480 (307,200ピクセル)

**画像解像度:**
- 現在: ? (確認必要)
- 推奨: Full HD (1920x1080) 以上
- 理想: 4K (3840x2160)

---

## 処理速度の向上要因

### 質問: 「処理が早くなったのは、不要データを間引いたから？」

**回答: いいえ、フレーム間引きは実装されていません。**

### 実際の要因

ログを確認すると：
```
Integrated 183/183 frames
```

**全フレームを処理しています**（183フレーム全て）。

### 処理速度向上の実際の要因

1. **TSDF解像度を粗くした**
   - `voxel_length: 0.01 → 0.04 → 0.03m`
   - 粗いほど処理が速い（処理量が減少）
   - ボクセル数: 約27倍減少 (0.01³ → 0.03³)

2. **GPU使用**
   - CUDA accelerationで処理が高速化
   - 一部の処理がGPU上で実行

3. **メッシュ簡略化（viewer用）**
   - 元のメッシュ: 857,501 triangles
   - 簡略化後: 500,000 triangles
   - ファイルサイズが減少（表示用のみ）

4. **処理対象データの減少**
   - 有効深度ピクセルが0.4%と非常に少ない
   - 処理する深度データが少ない → 処理時間が短い
   - ただし、これは**品質低下の原因**でもある

---

## 解像度の改善案

### 🔴 最優先: 深度解像度の向上（Androidアプリ側）

**現在:**
- 深度解像度: 160x90 (14,400ピクセル)
- 有効ピクセル: 0.4%

**目標:**
- 深度解像度: 320x240 (76,800ピクセル) 以上
- 有効ピクセル: 20%以上

**実装方法:**
- `ANDROID_DEPTH_RESOLUTION_GUIDE.md`を参照
- ARCore Session設定で最高解像度を選択
- Raw Depth APIを使用（より高解像度の可能性）

### 🟡 次に優先: 画像解像度の向上（Androidアプリ側）

**現在:**
- 画像解像度: ? (確認必要)

**目標:**
- Full HD: 1920x1080
- 4K: 3840x2160 (可能な場合)

**実装方法:**
- カメラ設定で最高解像度を選択
- `ArCameraConfig`で設定

### 🔧 サーバー側の調整（即座に効果）

**TSDF解像度を細かくする:**
```yaml
tsdf:
  voxel_length: 0.025  # 0.03 → 0.025（部屋の詳細を保持）
```

**メッシュ品質を向上:**
```yaml
mesh:
  quality_improvement:
    subdivision:
      iterations: 2  # 1 → 2（より滑らかに）
  
  smoothing:
    iterations: 10  # 8 → 10（より滑らかに）
```

---

## 部屋認識の改善

### 問題の原因

1. **深度解像度が非常に低い** (160x90)
2. **有効深度ピクセルが非常に少ない** (0.4%)
3. **TSDF解像度が粗い** (0.03m)

### 改善策

#### Step 1: 解像度診断を実行

```bash
python diagnose_resolution.py 3b0cd1d9
```

#### Step 2: Androidアプリ側で解像度を向上

- 深度解像度: 160x90 → 320x240以上
- 画像解像度: Full HD以上

#### Step 3: サーバー側の設定を調整

```yaml
processing:
  tsdf:
    voxel_length: 0.025  # 0.03 → 0.025
```

#### Step 4: メッシュを再生成

```bash
python regenerate_mesh.py 3b0cd1d9 existing
```

---

## 処理速度と品質のバランス

### 現在の設定（処理速度優先）

```yaml
tsdf:
  voxel_length: 0.03  # 粗い（処理が速い、品質が低い）
```

### 推奨設定（品質優先）

```yaml
tsdf:
  voxel_length: 0.025  # 細かい（処理が遅い、品質が高い）
```

### バランス設定（推奨）

```yaml
tsdf:
  voxel_length: 0.025  # バランス重視（0.02と0.03の中間）
```

**処理時間の目安:**
- 0.03: 基準時間 × 1.0
- 0.025: 基準時間 × 1.7 (約1.7倍)
- 0.02: 基準時間 × 3.4 (約3.4倍)

---

## フレーム間引きについて

### 現在の実装

**フレーム間引きは実装されていません。**
- ログ: "Integrated 183/183 frames"
- 全フレームを処理

### フレーム間引きを実装する場合

**推奨:**
- 部屋認識を優先: **フレーム間引きはしない**
- 処理速度を優先: **最小限の間引き** (30fps → 10-15fps)

**実装例:**
```python
# pipeline/rgbd_integration_gpu.py の process_session メソッド内
frames = parser.get_frames_with_depth()

# フレーム間引き（オプション）
frame_sampling_config = self.config.get('frame_sampling', {})
if frame_sampling_config.get('enable', False):
    target_fps = frame_sampling_config.get('target_fps', 10)
    if len(frames) > 0:
        duration_seconds = (frames[-1].timestamp - frames[0].timestamp) / 1e9
        frame_interval = max(1, len(frames) // (target_fps * duration_seconds))
        sampled_frames = frames[::frame_interval]
        print(f"Frame sampling: {len(frames)} -> {len(sampled_frames)} frames ({frame_interval} interval)")
        frames = sampled_frames
```

**config.yamlに追加:**
```yaml
processing:
  frame_sampling:
    enable: false  # 部屋認識を優先する場合はfalse
    target_fps: 10  # 間引きする場合の目標fps
```

---

## まとめ

### 現在の状況

1. **深度解像度: 160x90** ← 非常に低い（部屋認識不能の主因）
2. **有効深度ピクセル: 0.4%** ← 非常に少ない
3. **画像解像度: ?** ← 確認必要
4. **フレーム間引き: なし** ← 全フレーム処理

### 処理速度向上の要因

1. ✅ **TSDF解像度を粗くした** (0.01 → 0.03、約27倍の処理量減少)
2. ✅ **GPU使用** (CUDA acceleration)
3. ✅ **有効データが少ない** (0.4%の有効ピクセル → 処理量が少ない、ただし品質低下)

### 改善優先順位

1. **🔴 最優先: Androidアプリ側で深度解像度を320x240以上に**
2. **🟡 次に優先: Androidアプリ側で画像解像度をFull HD以上に**
3. **🔧 サーバー側: TSDF解像度を0.025に調整**

