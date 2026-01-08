---
作成日時: 2026-01-08 10:38:00
最終更新: 2026-01-08 10:38:00
---

# メッシュの粗さ改善ガイド

## 現状の問題

メッシュが粗く、フラグメント化している。

**考えられる原因:**
1. **TSDF voxel_lengthが粗すぎる** (0.04m = 40mm)
2. **有効深度ピクセルが非常に少ない** (0.4%)
3. **メッシュ細分化が不十分** (1回のみ)
4. **平滑化が不十分** (5回、lambda=0.5)

---

## 改善策（優先順位順）

### 🔧 1. TSDF解像度を少し細かくする（効果大）

**現在の設定:**
```yaml
tsdf:
  voxel_length: 0.04  # 40mm（粗い）
```

**推奨変更:**
```yaml
tsdf:
  voxel_length: 0.025  # 25mm（0.04 → 0.025、バランスを取る）
  # または
  voxel_length: 0.03   # 30mm（より保守的）
```

**効果:**
- ✅ より細かい解像度でメッシュ生成
- ✅ 詳細がより保持される
- ⚠️ メモリ使用量が増加（0.04→0.025で約2.5倍）

**注意:**
- 有効深度ピクセルが0.4%と非常に少ない場合、細かくしすぎるとノイズが増える可能性
- まず0.03に変更してテスト

### 🔧 2. メッシュ細分化を増やす（効果大）

**現在の設定:**
```yaml
mesh:
  quality_improvement:
    subdivision:
      iterations: 1  # 1回のみ
      max_triangles: 3000000
```

**推奨変更:**
```yaml
mesh:
  quality_improvement:
    subdivision:
      iterations: 2  # 1 → 2に増やす
      max_triangles: 5000000  # 3000000 → 5000000に増やす
```

**効果:**
- ✅ より滑らかな表面
- ✅ より詳細なメッシュ
- ⚠️ メモリ使用量が大幅に増加（約4倍）

**注意:**
- 現在のメッシュが857,501 trianglesの場合、2回の細分化で約6.8M trianglesになる可能性
- メモリが不足する場合は1回のまま

### 🔧 3. 平滑化を強化（効果中）

**現在の設定:**
```yaml
mesh:
  smoothing:
    iterations: 5
    lambda_filter: 0.5
```

**推奨変更:**
```yaml
mesh:
  smoothing:
    iterations: 8  # 5 → 8に増やす
    lambda_filter: 0.4  # 0.5 → 0.4に減らす（より強く平滑化）
    # または Taubin平滑化を試す
    method: "taubin"  # laplacian → taubin
```

**効果:**
- ✅ より滑らかな表面
- ✅ ノイズの除去
- ⚠️ 詳細が失われる可能性（やりすぎ注意）

### 🔧 4. Depth前処理を強化（根本的解決）

**現在の設定:**
```yaml
depth:
  filter_noise: true
  bilateral_filter: true
```

**推奨変更:**
```yaml
depth:
  filter_noise: true
  bilateral_filter: true
  bilateral_sigma_color: 75.0  # 50.0 → 75.0（より強く平滑化）
  bilateral_sigma_space: 75.0  # 50.0 → 75.0
```

**効果:**
- ✅ 深度ノイズの除去
- ✅ より滑らかな深度データ
- ✅ メッシュ品質の向上

### 🔧 5. メッシュ簡略化を無効化（表示用）

**現在の設定:**
```yaml
output:
  mesh:
    simplify_for_viewer: true
    max_triangles_for_viewer: 500000
```

**一時的な確認:**
```yaml
output:
  mesh:
    simplify_for_viewer: false  # 元のメッシュを確認
```

**効果:**
- ✅ 元のメッシュの品質を確認可能
- ⚠️ ファイルサイズが大きくなる

---

## 推奨設定変更（段階的アプローチ）

### Step 1: TSDF解像度を調整（即座に効果）

```yaml
processing:
  tsdf:
    voxel_length: 0.03  # 0.04 → 0.03（30mm）
    sdf_trunc: 0.24     # 0.03 * 8 = 0.24
```

### Step 2: メッシュ細分化を強化

```yaml
mesh:
  quality_improvement:
    subdivision:
      iterations: 2  # 1 → 2
      max_triangles: 5000000  # 3000000 → 5000000
```

### Step 3: 平滑化を強化

```yaml
mesh:
  smoothing:
    iterations: 8  # 5 → 8
    lambda_filter: 0.4  # 0.5 → 0.4
```

### Step 4: Depth前処理を強化

```yaml
depth:
  bilateral_sigma_color: 75.0  # 50.0 → 75.0
  bilateral_sigma_space: 75.0  # 50.0 → 75.0
```

---

## 実装手順

1. **config.yamlを変更**
   ```bash
   # Step 1: TSDF解像度を調整
   # voxel_length: 0.04 → 0.03
   ```

2. **メッシュを再生成**
   ```bash
   python regenerate_mesh.py 3b0cd1d9 existing
   ```

3. **結果を確認**
   ```bash
   python view_mesh.py data/results/3b0cd1d9/mesh.ply
   # またはブラウザで viewer を確認
   ```

4. **改善が不十分な場合は Step 2, 3, 4 を順次実施**

---

## メモリ制約の考慮

**GTX 1660 Ti（6GB VRAM）の場合:**
- `voxel_length: 0.03` → 安全
- `voxel_length: 0.025` → ややリスク（メモリ使用量増加）
- `subdivision iterations: 2` → リスクあり（メモリ使用量大幅増加）

**推奨:**
1. まず `voxel_length: 0.03` で試す
2. 改善が不十分な場合のみ `0.025` に変更
3. `subdivision` は1回のまま、平滑化で対処

---

## 期待される効果

### Step 1のみ（TSDF解像度調整）

- メッシュの粗さが**20-30%改善**することが期待できる

### Step 1 + Step 2（TSDF + 細分化）

- メッシュの粗さが**40-60%改善**することが期待できる
- より滑らかな表面

### Step 1-4（全対策）

- メッシュの粗さが**60-80%改善**することが期待できる
- より高品質なメッシュ

最終更新: 2026-01-08 10:38:00
---

# メッシュの粗さ改善ガイド

## 現状の問題

メッシュが粗く、フラグメント化している。

**考えられる原因:**
1. **TSDF voxel_lengthが粗すぎる** (0.04m = 40mm)
2. **有効深度ピクセルが非常に少ない** (0.4%)
3. **メッシュ細分化が不十分** (1回のみ)
4. **平滑化が不十分** (5回、lambda=0.5)

---

## 改善策（優先順位順）

### 🔧 1. TSDF解像度を少し細かくする（効果大）

**現在の設定:**
```yaml
tsdf:
  voxel_length: 0.04  # 40mm（粗い）
```

**推奨変更:**
```yaml
tsdf:
  voxel_length: 0.025  # 25mm（0.04 → 0.025、バランスを取る）
  # または
  voxel_length: 0.03   # 30mm（より保守的）
```

**効果:**
- ✅ より細かい解像度でメッシュ生成
- ✅ 詳細がより保持される
- ⚠️ メモリ使用量が増加（0.04→0.025で約2.5倍）

**注意:**
- 有効深度ピクセルが0.4%と非常に少ない場合、細かくしすぎるとノイズが増える可能性
- まず0.03に変更してテスト

### 🔧 2. メッシュ細分化を増やす（効果大）

**現在の設定:**
```yaml
mesh:
  quality_improvement:
    subdivision:
      iterations: 1  # 1回のみ
      max_triangles: 3000000
```

**推奨変更:**
```yaml
mesh:
  quality_improvement:
    subdivision:
      iterations: 2  # 1 → 2に増やす
      max_triangles: 5000000  # 3000000 → 5000000に増やす
```

**効果:**
- ✅ より滑らかな表面
- ✅ より詳細なメッシュ
- ⚠️ メモリ使用量が大幅に増加（約4倍）

**注意:**
- 現在のメッシュが857,501 trianglesの場合、2回の細分化で約6.8M trianglesになる可能性
- メモリが不足する場合は1回のまま

### 🔧 3. 平滑化を強化（効果中）

**現在の設定:**
```yaml
mesh:
  smoothing:
    iterations: 5
    lambda_filter: 0.5
```

**推奨変更:**
```yaml
mesh:
  smoothing:
    iterations: 8  # 5 → 8に増やす
    lambda_filter: 0.4  # 0.5 → 0.4に減らす（より強く平滑化）
    # または Taubin平滑化を試す
    method: "taubin"  # laplacian → taubin
```

**効果:**
- ✅ より滑らかな表面
- ✅ ノイズの除去
- ⚠️ 詳細が失われる可能性（やりすぎ注意）

### 🔧 4. Depth前処理を強化（根本的解決）

**現在の設定:**
```yaml
depth:
  filter_noise: true
  bilateral_filter: true
```

**推奨変更:**
```yaml
depth:
  filter_noise: true
  bilateral_filter: true
  bilateral_sigma_color: 75.0  # 50.0 → 75.0（より強く平滑化）
  bilateral_sigma_space: 75.0  # 50.0 → 75.0
```

**効果:**
- ✅ 深度ノイズの除去
- ✅ より滑らかな深度データ
- ✅ メッシュ品質の向上

### 🔧 5. メッシュ簡略化を無効化（表示用）

**現在の設定:**
```yaml
output:
  mesh:
    simplify_for_viewer: true
    max_triangles_for_viewer: 500000
```

**一時的な確認:**
```yaml
output:
  mesh:
    simplify_for_viewer: false  # 元のメッシュを確認
```

**効果:**
- ✅ 元のメッシュの品質を確認可能
- ⚠️ ファイルサイズが大きくなる

---

## 推奨設定変更（段階的アプローチ）

### Step 1: TSDF解像度を調整（即座に効果）

```yaml
processing:
  tsdf:
    voxel_length: 0.03  # 0.04 → 0.03（30mm）
    sdf_trunc: 0.24     # 0.03 * 8 = 0.24
```

### Step 2: メッシュ細分化を強化

```yaml
mesh:
  quality_improvement:
    subdivision:
      iterations: 2  # 1 → 2
      max_triangles: 5000000  # 3000000 → 5000000
```

### Step 3: 平滑化を強化

```yaml
mesh:
  smoothing:
    iterations: 8  # 5 → 8
    lambda_filter: 0.4  # 0.5 → 0.4
```

### Step 4: Depth前処理を強化

```yaml
depth:
  bilateral_sigma_color: 75.0  # 50.0 → 75.0
  bilateral_sigma_space: 75.0  # 50.0 → 75.0
```

---

## 実装手順

1. **config.yamlを変更**
   ```bash
   # Step 1: TSDF解像度を調整
   # voxel_length: 0.04 → 0.03
   ```

2. **メッシュを再生成**
   ```bash
   python regenerate_mesh.py 3b0cd1d9 existing
   ```

3. **結果を確認**
   ```bash
   python view_mesh.py data/results/3b0cd1d9/mesh.ply
   # またはブラウザで viewer を確認
   ```

4. **改善が不十分な場合は Step 2, 3, 4 を順次実施**

---

## メモリ制約の考慮

**GTX 1660 Ti（6GB VRAM）の場合:**
- `voxel_length: 0.03` → 安全
- `voxel_length: 0.025` → ややリスク（メモリ使用量増加）
- `subdivision iterations: 2` → リスクあり（メモリ使用量大幅増加）

**推奨:**
1. まず `voxel_length: 0.03` で試す
2. 改善が不十分な場合のみ `0.025` に変更
3. `subdivision` は1回のまま、平滑化で対処

---

## 期待される効果

### Step 1のみ（TSDF解像度調整）

- メッシュの粗さが**20-30%改善**することが期待できる

### Step 1 + Step 2（TSDF + 細分化）

- メッシュの粗さが**40-60%改善**することが期待できる
- より滑らかな表面

### Step 1-4（全対策）

- メッシュの粗さが**60-80%改善**することが期待できる
- より高品質なメッシュ
