---
作成日時: 2026-01-08 10:23:00
最終更新: 2026-01-08 10:23:00
---

# Depth API比較チェックリスト

## 目的

Raw Depth APIとDepth API（通常）の実際の性能を比較し、どちらが3Dメッシュ生成に適しているかを判断する。

---

## ステップ1: Depth API（通常）で新しいジョブを作成

### Androidアプリ側での変更

**変更前（Raw Depth API）:**
```kotlin
val rawDepthImage = frame.acquireRawDepthImage()
```

**変更後（Depth API）:**
```kotlin
val depthImage = frame.acquireDepthImage()
```

### データアップロード

1. Androidアプリで同じシーンをスキャン
2. サーバーにアップロード
3. ジョブIDを記録（例: `depth_api_job_id`）

---

## ステップ2: 診断スクリプトで比較

### Raw Depth APIの結果（既存）

```bash
python diagnose_depth.py 0a89490c
```

**結果:**
- 解像度: 160x90
- 有効ピクセル: 0.4%
- 99th percentile: 6.99m

### Depth API（通常）の結果

```bash
python diagnose_depth.py <depth_api_job_id>
```

**確認項目:**
- [ ] 解像度（width x height）
- [ ] 有効ピクセル率（valid_ratio %）
- [ ] 無効値マーカー率（invalid_ratio %）
- [ ] 深度範囲（min - max m）
- [ ] 99th percentile（m）
- [ ] 標準偏差（std dev m）

---

## ステップ3: 比較表を作成

| 項目 | Raw Depth API | Depth API（通常） | 良い方 |
|------|---------------|-------------------|--------|
| **解像度** | 160x90 | ?x? | ? |
| **有効ピクセル率** | 0.4% | ?% | ? |
| **無効値マーカー率** | 99.6% | ?% | ? |
| **深度範囲（min）** | 2.00m | ?m | - |
| **深度範囲（max）** | 16.00m | ?m | - |
| **99th percentile** | 6.99m | ?m | - |
| **標準偏差** | 0.804m | ?m | Depth API |
| **推奨depth_trunc** | 7.0m | ?m | - |

---

## ステップ4: メッシュ品質を比較

### 両方のジョブでメッシュを生成

```bash
# Raw Depth APIのメッシュ（既存）
python regenerate_mesh.py 0a89490c existing

# Depth API（通常）のメッシュ
python regenerate_mesh.py <depth_api_job_id> existing
```

### 比較項目

- [ ] **メッシュの三角形数**
  - Raw Depth API: ?
  - Depth API: ?
  
- [ ] **メッシュの頂点数**
  - Raw Depth API: ?
  - Depth API: ?

- [ ] **視覚的な品質**
  - 波打ちの有無
  - ノイズの量
  - 詳細の保持
  - 滑らかさ

- [ ] **ファイルサイズ**
  - Raw Depth API: ?MB
  - Depth API: ?MB

---

## ステップ5: 判断基準

### Depth API（通常）を選択する場合

✅ **条件:**
- 解像度がRaw Depth APIと同じか高い（320x240以上）
- 有効ピクセルが10%以上
- 標準偏差が低い（ノイズが少ない、< 1.0m）
- メッシュ品質が良い（波打ちが少ない、詳細が保持されている）

**理由:**
- ARCoreのフィルタリングが有効
- サーバー側の前処理が不要（または軽減）
- より安定した品質

### Raw Depth APIを選択する場合

✅ **条件:**
- 解像度がDepth APIより高い（320x240以上）
- 有効ピクセルが10%以上（サーバー側フィルタリング後）
- サーバー側で適切にフィルタリング可能
- メッシュ品質が良い（より詳細、より滑らか）

**理由:**
- より高解像度
- より多くの情報
- サーバー側で柔軟に処理可能

---

## ステップ6: 設定の最適化

### Depth API（通常）を選択した場合

**推奨設定変更:**
```yaml
processing:
  depth:
    # Depth APIは既にフィルタリング済みのため、前処理を軽減
    filter_noise: false  # ARCoreが既に実施済み
    bilateral_filter: false  # ARCoreが既に実施済み
    # または、より軽いフィルタリング
    bilateral_sigma_color: 30.0  # デフォルトより軽く
    bilateral_sigma_space: 30.0
```

### Raw Depth APIを選択した場合

**推奨設定（現在の設定を維持）:**
```yaml
processing:
  depth:
    trunc: 7.0  # 診断結果に基づく
    filter_noise: true  # 必要
    bilateral_filter: true  # 必要
```

---

## ステップ7: 結果の記録

比較結果を記録して、今後の参考にする：

```
## Depth API比較結果 (YYYY-MM-DD)

### Raw Depth API
- ジョブID: 0a89490c
- 解像度: 160x90
- 有効ピクセル: 0.4%
- メッシュ品質: [評価]

### Depth API（通常）
- ジョブID: <depth_api_job_id>
- 解像度: ?x?
- 有効ピクセル: ?%
- メッシュ品質: [評価]

### 結論
[どちらを選択したか、理由]

```

---

## 参考: 期待される結果

### 理想的なDepth API（通常）の結果

- 解像度: 320x240以上
- 有効ピクセル: 10-30%以上
- 標準偏差: < 1.0m
- ノイズが少ない、安定した品質

### 理想的なRaw Depth APIの結果

- 解像度: 320x240〜640x480
- 有効ピクセル: 20-40%以上（フィルタリング前）、10-20%以上（フィルタリング後）
- 標準偏差: サーバー側フィルタリング後 < 1.5m
- より高解像度、より詳細

---

## 次のステップ

1. ✅ Depth API（通常）で新しいジョブを作成
2. ✅ 診断スクリプトで比較
3. ✅ メッシュ品質を比較
4. ✅ 判断基準に基づいて選択
5. ✅ 設定を最適化

最終更新: 2026-01-08 10:23:00
---

# Depth API比較チェックリスト

## 目的

Raw Depth APIとDepth API（通常）の実際の性能を比較し、どちらが3Dメッシュ生成に適しているかを判断する。

---

## ステップ1: Depth API（通常）で新しいジョブを作成

### Androidアプリ側での変更

**変更前（Raw Depth API）:**
```kotlin
val rawDepthImage = frame.acquireRawDepthImage()
```

**変更後（Depth API）:**
```kotlin
val depthImage = frame.acquireDepthImage()
```

### データアップロード

1. Androidアプリで同じシーンをスキャン
2. サーバーにアップロード
3. ジョブIDを記録（例: `depth_api_job_id`）

---

## ステップ2: 診断スクリプトで比較

### Raw Depth APIの結果（既存）

```bash
python diagnose_depth.py 0a89490c
```

**結果:**
- 解像度: 160x90
- 有効ピクセル: 0.4%
- 99th percentile: 6.99m

### Depth API（通常）の結果

```bash
python diagnose_depth.py <depth_api_job_id>
```

**確認項目:**
- [ ] 解像度（width x height）
- [ ] 有効ピクセル率（valid_ratio %）
- [ ] 無効値マーカー率（invalid_ratio %）
- [ ] 深度範囲（min - max m）
- [ ] 99th percentile（m）
- [ ] 標準偏差（std dev m）

---

## ステップ3: 比較表を作成

| 項目 | Raw Depth API | Depth API（通常） | 良い方 |
|------|---------------|-------------------|--------|
| **解像度** | 160x90 | ?x? | ? |
| **有効ピクセル率** | 0.4% | ?% | ? |
| **無効値マーカー率** | 99.6% | ?% | ? |
| **深度範囲（min）** | 2.00m | ?m | - |
| **深度範囲（max）** | 16.00m | ?m | - |
| **99th percentile** | 6.99m | ?m | - |
| **標準偏差** | 0.804m | ?m | Depth API |
| **推奨depth_trunc** | 7.0m | ?m | - |

---

## ステップ4: メッシュ品質を比較

### 両方のジョブでメッシュを生成

```bash
# Raw Depth APIのメッシュ（既存）
python regenerate_mesh.py 0a89490c existing

# Depth API（通常）のメッシュ
python regenerate_mesh.py <depth_api_job_id> existing
```

### 比較項目

- [ ] **メッシュの三角形数**
  - Raw Depth API: ?
  - Depth API: ?
  
- [ ] **メッシュの頂点数**
  - Raw Depth API: ?
  - Depth API: ?

- [ ] **視覚的な品質**
  - 波打ちの有無
  - ノイズの量
  - 詳細の保持
  - 滑らかさ

- [ ] **ファイルサイズ**
  - Raw Depth API: ?MB
  - Depth API: ?MB

---

## ステップ5: 判断基準

### Depth API（通常）を選択する場合

✅ **条件:**
- 解像度がRaw Depth APIと同じか高い（320x240以上）
- 有効ピクセルが10%以上
- 標準偏差が低い（ノイズが少ない、< 1.0m）
- メッシュ品質が良い（波打ちが少ない、詳細が保持されている）

**理由:**
- ARCoreのフィルタリングが有効
- サーバー側の前処理が不要（または軽減）
- より安定した品質

### Raw Depth APIを選択する場合

✅ **条件:**
- 解像度がDepth APIより高い（320x240以上）
- 有効ピクセルが10%以上（サーバー側フィルタリング後）
- サーバー側で適切にフィルタリング可能
- メッシュ品質が良い（より詳細、より滑らか）

**理由:**
- より高解像度
- より多くの情報
- サーバー側で柔軟に処理可能

---

## ステップ6: 設定の最適化

### Depth API（通常）を選択した場合

**推奨設定変更:**
```yaml
processing:
  depth:
    # Depth APIは既にフィルタリング済みのため、前処理を軽減
    filter_noise: false  # ARCoreが既に実施済み
    bilateral_filter: false  # ARCoreが既に実施済み
    # または、より軽いフィルタリング
    bilateral_sigma_color: 30.0  # デフォルトより軽く
    bilateral_sigma_space: 30.0
```

### Raw Depth APIを選択した場合

**推奨設定（現在の設定を維持）:**
```yaml
processing:
  depth:
    trunc: 7.0  # 診断結果に基づく
    filter_noise: true  # 必要
    bilateral_filter: true  # 必要
```

---

## ステップ7: 結果の記録

比較結果を記録して、今後の参考にする：

```
## Depth API比較結果 (YYYY-MM-DD)

### Raw Depth API
- ジョブID: 0a89490c
- 解像度: 160x90
- 有効ピクセル: 0.4%
- メッシュ品質: [評価]

### Depth API（通常）
- ジョブID: <depth_api_job_id>
- 解像度: ?x?
- 有効ピクセル: ?%
- メッシュ品質: [評価]

### 結論
[どちらを選択したか、理由]

```

---

## 参考: 期待される結果

### 理想的なDepth API（通常）の結果

- 解像度: 320x240以上
- 有効ピクセル: 10-30%以上
- 標準偏差: < 1.0m
- ノイズが少ない、安定した品質

### 理想的なRaw Depth APIの結果

- 解像度: 320x240〜640x480
- 有効ピクセル: 20-40%以上（フィルタリング前）、10-20%以上（フィルタリング後）
- 標準偏差: サーバー側フィルタリング後 < 1.5m
- より高解像度、より詳細

---

## 次のステップ

1. ✅ Depth API（通常）で新しいジョブを作成
2. ✅ 診断スクリプトで比較
3. ✅ メッシュ品質を比較
4. ✅ 判断基準に基づいて選択
5. ✅ 設定を最適化

最終更新: 2026-01-08 10:23:00
---

# Depth API比較チェックリスト

## 目的

Raw Depth APIとDepth API（通常）の実際の性能を比較し、どちらが3Dメッシュ生成に適しているかを判断する。

---

## ステップ1: Depth API（通常）で新しいジョブを作成

### Androidアプリ側での変更

**変更前（Raw Depth API）:**
```kotlin
val rawDepthImage = frame.acquireRawDepthImage()
```

**変更後（Depth API）:**
```kotlin
val depthImage = frame.acquireDepthImage()
```

### データアップロード

1. Androidアプリで同じシーンをスキャン
2. サーバーにアップロード
3. ジョブIDを記録（例: `depth_api_job_id`）

---

## ステップ2: 診断スクリプトで比較

### Raw Depth APIの結果（既存）

```bash
python diagnose_depth.py 0a89490c
```

**結果:**
- 解像度: 160x90
- 有効ピクセル: 0.4%
- 99th percentile: 6.99m

### Depth API（通常）の結果

```bash
python diagnose_depth.py <depth_api_job_id>
```

**確認項目:**
- [ ] 解像度（width x height）
- [ ] 有効ピクセル率（valid_ratio %）
- [ ] 無効値マーカー率（invalid_ratio %）
- [ ] 深度範囲（min - max m）
- [ ] 99th percentile（m）
- [ ] 標準偏差（std dev m）

---

## ステップ3: 比較表を作成

| 項目 | Raw Depth API | Depth API（通常） | 良い方 |
|------|---------------|-------------------|--------|
| **解像度** | 160x90 | ?x? | ? |
| **有効ピクセル率** | 0.4% | ?% | ? |
| **無効値マーカー率** | 99.6% | ?% | ? |
| **深度範囲（min）** | 2.00m | ?m | - |
| **深度範囲（max）** | 16.00m | ?m | - |
| **99th percentile** | 6.99m | ?m | - |
| **標準偏差** | 0.804m | ?m | Depth API |
| **推奨depth_trunc** | 7.0m | ?m | - |

---

## ステップ4: メッシュ品質を比較

### 両方のジョブでメッシュを生成

```bash
# Raw Depth APIのメッシュ（既存）
python regenerate_mesh.py 0a89490c existing

# Depth API（通常）のメッシュ
python regenerate_mesh.py <depth_api_job_id> existing
```

### 比較項目

- [ ] **メッシュの三角形数**
  - Raw Depth API: ?
  - Depth API: ?
  
- [ ] **メッシュの頂点数**
  - Raw Depth API: ?
  - Depth API: ?

- [ ] **視覚的な品質**
  - 波打ちの有無
  - ノイズの量
  - 詳細の保持
  - 滑らかさ

- [ ] **ファイルサイズ**
  - Raw Depth API: ?MB
  - Depth API: ?MB

---

## ステップ5: 判断基準

### Depth API（通常）を選択する場合

✅ **条件:**
- 解像度がRaw Depth APIと同じか高い（320x240以上）
- 有効ピクセルが10%以上
- 標準偏差が低い（ノイズが少ない、< 1.0m）
- メッシュ品質が良い（波打ちが少ない、詳細が保持されている）

**理由:**
- ARCoreのフィルタリングが有効
- サーバー側の前処理が不要（または軽減）
- より安定した品質

### Raw Depth APIを選択する場合

✅ **条件:**
- 解像度がDepth APIより高い（320x240以上）
- 有効ピクセルが10%以上（サーバー側フィルタリング後）
- サーバー側で適切にフィルタリング可能
- メッシュ品質が良い（より詳細、より滑らか）

**理由:**
- より高解像度
- より多くの情報
- サーバー側で柔軟に処理可能

---

## ステップ6: 設定の最適化

### Depth API（通常）を選択した場合

**推奨設定変更:**
```yaml
processing:
  depth:
    # Depth APIは既にフィルタリング済みのため、前処理を軽減
    filter_noise: false  # ARCoreが既に実施済み
    bilateral_filter: false  # ARCoreが既に実施済み
    # または、より軽いフィルタリング
    bilateral_sigma_color: 30.0  # デフォルトより軽く
    bilateral_sigma_space: 30.0
```

### Raw Depth APIを選択した場合

**推奨設定（現在の設定を維持）:**
```yaml
processing:
  depth:
    trunc: 7.0  # 診断結果に基づく
    filter_noise: true  # 必要
    bilateral_filter: true  # 必要
```

---

## ステップ7: 結果の記録

比較結果を記録して、今後の参考にする：

```
## Depth API比較結果 (YYYY-MM-DD)

### Raw Depth API
- ジョブID: 0a89490c
- 解像度: 160x90
- 有効ピクセル: 0.4%
- メッシュ品質: [評価]

### Depth API（通常）
- ジョブID: <depth_api_job_id>
- 解像度: ?x?
- 有効ピクセル: ?%
- メッシュ品質: [評価]

### 結論
[どちらを選択したか、理由]

```

---

## 参考: 期待される結果

### 理想的なDepth API（通常）の結果

- 解像度: 320x240以上
- 有効ピクセル: 10-30%以上
- 標準偏差: < 1.0m
- ノイズが少ない、安定した品質

### 理想的なRaw Depth APIの結果

- 解像度: 320x240〜640x480
- 有効ピクセル: 20-40%以上（フィルタリング前）、10-20%以上（フィルタリング後）
- 標準偏差: サーバー側フィルタリング後 < 1.5m
- より高解像度、より詳細

---

## 次のステップ

1. ✅ Depth API（通常）で新しいジョブを作成
2. ✅ 診断スクリプトで比較
3. ✅ メッシュ品質を比較
4. ✅ 判断基準に基づいて選択
5. ✅ 設定を最適化

最終更新: 2026-01-08 10:23:00
---

# Depth API比較チェックリスト

## 目的

Raw Depth APIとDepth API（通常）の実際の性能を比較し、どちらが3Dメッシュ生成に適しているかを判断する。

---

## ステップ1: Depth API（通常）で新しいジョブを作成

### Androidアプリ側での変更

**変更前（Raw Depth API）:**
```kotlin
val rawDepthImage = frame.acquireRawDepthImage()
```

**変更後（Depth API）:**
```kotlin
val depthImage = frame.acquireDepthImage()
```

### データアップロード

1. Androidアプリで同じシーンをスキャン
2. サーバーにアップロード
3. ジョブIDを記録（例: `depth_api_job_id`）

---

## ステップ2: 診断スクリプトで比較

### Raw Depth APIの結果（既存）

```bash
python diagnose_depth.py 0a89490c
```

**結果:**
- 解像度: 160x90
- 有効ピクセル: 0.4%
- 99th percentile: 6.99m

### Depth API（通常）の結果

```bash
python diagnose_depth.py <depth_api_job_id>
```

**確認項目:**
- [ ] 解像度（width x height）
- [ ] 有効ピクセル率（valid_ratio %）
- [ ] 無効値マーカー率（invalid_ratio %）
- [ ] 深度範囲（min - max m）
- [ ] 99th percentile（m）
- [ ] 標準偏差（std dev m）

---

## ステップ3: 比較表を作成

| 項目 | Raw Depth API | Depth API（通常） | 良い方 |
|------|---------------|-------------------|--------|
| **解像度** | 160x90 | ?x? | ? |
| **有効ピクセル率** | 0.4% | ?% | ? |
| **無効値マーカー率** | 99.6% | ?% | ? |
| **深度範囲（min）** | 2.00m | ?m | - |
| **深度範囲（max）** | 16.00m | ?m | - |
| **99th percentile** | 6.99m | ?m | - |
| **標準偏差** | 0.804m | ?m | Depth API |
| **推奨depth_trunc** | 7.0m | ?m | - |

---

## ステップ4: メッシュ品質を比較

### 両方のジョブでメッシュを生成

```bash
# Raw Depth APIのメッシュ（既存）
python regenerate_mesh.py 0a89490c existing

# Depth API（通常）のメッシュ
python regenerate_mesh.py <depth_api_job_id> existing
```

### 比較項目

- [ ] **メッシュの三角形数**
  - Raw Depth API: ?
  - Depth API: ?
  
- [ ] **メッシュの頂点数**
  - Raw Depth API: ?
  - Depth API: ?

- [ ] **視覚的な品質**
  - 波打ちの有無
  - ノイズの量
  - 詳細の保持
  - 滑らかさ

- [ ] **ファイルサイズ**
  - Raw Depth API: ?MB
  - Depth API: ?MB

---

## ステップ5: 判断基準

### Depth API（通常）を選択する場合

✅ **条件:**
- 解像度がRaw Depth APIと同じか高い（320x240以上）
- 有効ピクセルが10%以上
- 標準偏差が低い（ノイズが少ない、< 1.0m）
- メッシュ品質が良い（波打ちが少ない、詳細が保持されている）

**理由:**
- ARCoreのフィルタリングが有効
- サーバー側の前処理が不要（または軽減）
- より安定した品質

### Raw Depth APIを選択する場合

✅ **条件:**
- 解像度がDepth APIより高い（320x240以上）
- 有効ピクセルが10%以上（サーバー側フィルタリング後）
- サーバー側で適切にフィルタリング可能
- メッシュ品質が良い（より詳細、より滑らか）

**理由:**
- より高解像度
- より多くの情報
- サーバー側で柔軟に処理可能

---

## ステップ6: 設定の最適化

### Depth API（通常）を選択した場合

**推奨設定変更:**
```yaml
processing:
  depth:
    # Depth APIは既にフィルタリング済みのため、前処理を軽減
    filter_noise: false  # ARCoreが既に実施済み
    bilateral_filter: false  # ARCoreが既に実施済み
    # または、より軽いフィルタリング
    bilateral_sigma_color: 30.0  # デフォルトより軽く
    bilateral_sigma_space: 30.0
```

### Raw Depth APIを選択した場合

**推奨設定（現在の設定を維持）:**
```yaml
processing:
  depth:
    trunc: 7.0  # 診断結果に基づく
    filter_noise: true  # 必要
    bilateral_filter: true  # 必要
```

---

## ステップ7: 結果の記録

比較結果を記録して、今後の参考にする：

```
## Depth API比較結果 (YYYY-MM-DD)

### Raw Depth API
- ジョブID: 0a89490c
- 解像度: 160x90
- 有効ピクセル: 0.4%
- メッシュ品質: [評価]

### Depth API（通常）
- ジョブID: <depth_api_job_id>
- 解像度: ?x?
- 有効ピクセル: ?%
- メッシュ品質: [評価]

### 結論
[どちらを選択したか、理由]

```

---

## 参考: 期待される結果

### 理想的なDepth API（通常）の結果

- 解像度: 320x240以上
- 有効ピクセル: 10-30%以上
- 標準偏差: < 1.0m
- ノイズが少ない、安定した品質

### 理想的なRaw Depth APIの結果

- 解像度: 320x240〜640x480
- 有効ピクセル: 20-40%以上（フィルタリング前）、10-20%以上（フィルタリング後）
- 標準偏差: サーバー側フィルタリング後 < 1.5m
- より高解像度、より詳細

---

## 次のステップ

1. ✅ Depth API（通常）で新しいジョブを作成
2. ✅ 診断スクリプトで比較
3. ✅ メッシュ品質を比較
4. ✅ 判断基準に基づいて選択
5. ✅ 設定を最適化

最終更新: 2026-01-08 10:23:00
---

# Depth API比較チェックリスト

## 目的

Raw Depth APIとDepth API（通常）の実際の性能を比較し、どちらが3Dメッシュ生成に適しているかを判断する。

---

## ステップ1: Depth API（通常）で新しいジョブを作成

### Androidアプリ側での変更

**変更前（Raw Depth API）:**
```kotlin
val rawDepthImage = frame.acquireRawDepthImage()
```

**変更後（Depth API）:**
```kotlin
val depthImage = frame.acquireDepthImage()
```

### データアップロード

1. Androidアプリで同じシーンをスキャン
2. サーバーにアップロード
3. ジョブIDを記録（例: `depth_api_job_id`）

---

## ステップ2: 診断スクリプトで比較

### Raw Depth APIの結果（既存）

```bash
python diagnose_depth.py 0a89490c
```

**結果:**
- 解像度: 160x90
- 有効ピクセル: 0.4%
- 99th percentile: 6.99m

### Depth API（通常）の結果

```bash
python diagnose_depth.py <depth_api_job_id>
```

**確認項目:**
- [ ] 解像度（width x height）
- [ ] 有効ピクセル率（valid_ratio %）
- [ ] 無効値マーカー率（invalid_ratio %）
- [ ] 深度範囲（min - max m）
- [ ] 99th percentile（m）
- [ ] 標準偏差（std dev m）

---

## ステップ3: 比較表を作成

| 項目 | Raw Depth API | Depth API（通常） | 良い方 |
|------|---------------|-------------------|--------|
| **解像度** | 160x90 | ?x? | ? |
| **有効ピクセル率** | 0.4% | ?% | ? |
| **無効値マーカー率** | 99.6% | ?% | ? |
| **深度範囲（min）** | 2.00m | ?m | - |
| **深度範囲（max）** | 16.00m | ?m | - |
| **99th percentile** | 6.99m | ?m | - |
| **標準偏差** | 0.804m | ?m | Depth API |
| **推奨depth_trunc** | 7.0m | ?m | - |

---

## ステップ4: メッシュ品質を比較

### 両方のジョブでメッシュを生成

```bash
# Raw Depth APIのメッシュ（既存）
python regenerate_mesh.py 0a89490c existing

# Depth API（通常）のメッシュ
python regenerate_mesh.py <depth_api_job_id> existing
```

### 比較項目

- [ ] **メッシュの三角形数**
  - Raw Depth API: ?
  - Depth API: ?
  
- [ ] **メッシュの頂点数**
  - Raw Depth API: ?
  - Depth API: ?

- [ ] **視覚的な品質**
  - 波打ちの有無
  - ノイズの量
  - 詳細の保持
  - 滑らかさ

- [ ] **ファイルサイズ**
  - Raw Depth API: ?MB
  - Depth API: ?MB

---

## ステップ5: 判断基準

### Depth API（通常）を選択する場合

✅ **条件:**
- 解像度がRaw Depth APIと同じか高い（320x240以上）
- 有効ピクセルが10%以上
- 標準偏差が低い（ノイズが少ない、< 1.0m）
- メッシュ品質が良い（波打ちが少ない、詳細が保持されている）

**理由:**
- ARCoreのフィルタリングが有効
- サーバー側の前処理が不要（または軽減）
- より安定した品質

### Raw Depth APIを選択する場合

✅ **条件:**
- 解像度がDepth APIより高い（320x240以上）
- 有効ピクセルが10%以上（サーバー側フィルタリング後）
- サーバー側で適切にフィルタリング可能
- メッシュ品質が良い（より詳細、より滑らか）

**理由:**
- より高解像度
- より多くの情報
- サーバー側で柔軟に処理可能

---

## ステップ6: 設定の最適化

### Depth API（通常）を選択した場合

**推奨設定変更:**
```yaml
processing:
  depth:
    # Depth APIは既にフィルタリング済みのため、前処理を軽減
    filter_noise: false  # ARCoreが既に実施済み
    bilateral_filter: false  # ARCoreが既に実施済み
    # または、より軽いフィルタリング
    bilateral_sigma_color: 30.0  # デフォルトより軽く
    bilateral_sigma_space: 30.0
```

### Raw Depth APIを選択した場合

**推奨設定（現在の設定を維持）:**
```yaml
processing:
  depth:
    trunc: 7.0  # 診断結果に基づく
    filter_noise: true  # 必要
    bilateral_filter: true  # 必要
```

---

## ステップ7: 結果の記録

比較結果を記録して、今後の参考にする：

```
## Depth API比較結果 (YYYY-MM-DD)

### Raw Depth API
- ジョブID: 0a89490c
- 解像度: 160x90
- 有効ピクセル: 0.4%
- メッシュ品質: [評価]

### Depth API（通常）
- ジョブID: <depth_api_job_id>
- 解像度: ?x?
- 有効ピクセル: ?%
- メッシュ品質: [評価]

### 結論
[どちらを選択したか、理由]

```

---

## 参考: 期待される結果

### 理想的なDepth API（通常）の結果

- 解像度: 320x240以上
- 有効ピクセル: 10-30%以上
- 標準偏差: < 1.0m
- ノイズが少ない、安定した品質

### 理想的なRaw Depth APIの結果

- 解像度: 320x240〜640x480
- 有効ピクセル: 20-40%以上（フィルタリング前）、10-20%以上（フィルタリング後）
- 標準偏差: サーバー側フィルタリング後 < 1.5m
- より高解像度、より詳細

---

## 次のステップ

1. ✅ Depth API（通常）で新しいジョブを作成
2. ✅ 診断スクリプトで比較
3. ✅ メッシュ品質を比較
4. ✅ 判断基準に基づいて選択
5. ✅ 設定を最適化

最終更新: 2026-01-08 10:23:00
---

# Depth API比較チェックリスト

## 目的

Raw Depth APIとDepth API（通常）の実際の性能を比較し、どちらが3Dメッシュ生成に適しているかを判断する。

---

## ステップ1: Depth API（通常）で新しいジョブを作成

### Androidアプリ側での変更

**変更前（Raw Depth API）:**
```kotlin
val rawDepthImage = frame.acquireRawDepthImage()
```

**変更後（Depth API）:**
```kotlin
val depthImage = frame.acquireDepthImage()
```

### データアップロード

1. Androidアプリで同じシーンをスキャン
2. サーバーにアップロード
3. ジョブIDを記録（例: `depth_api_job_id`）

---

## ステップ2: 診断スクリプトで比較

### Raw Depth APIの結果（既存）

```bash
python diagnose_depth.py 0a89490c
```

**結果:**
- 解像度: 160x90
- 有効ピクセル: 0.4%
- 99th percentile: 6.99m

### Depth API（通常）の結果

```bash
python diagnose_depth.py <depth_api_job_id>
```

**確認項目:**
- [ ] 解像度（width x height）
- [ ] 有効ピクセル率（valid_ratio %）
- [ ] 無効値マーカー率（invalid_ratio %）
- [ ] 深度範囲（min - max m）
- [ ] 99th percentile（m）
- [ ] 標準偏差（std dev m）

---

## ステップ3: 比較表を作成

| 項目 | Raw Depth API | Depth API（通常） | 良い方 |
|------|---------------|-------------------|--------|
| **解像度** | 160x90 | ?x? | ? |
| **有効ピクセル率** | 0.4% | ?% | ? |
| **無効値マーカー率** | 99.6% | ?% | ? |
| **深度範囲（min）** | 2.00m | ?m | - |
| **深度範囲（max）** | 16.00m | ?m | - |
| **99th percentile** | 6.99m | ?m | - |
| **標準偏差** | 0.804m | ?m | Depth API |
| **推奨depth_trunc** | 7.0m | ?m | - |

---

## ステップ4: メッシュ品質を比較

### 両方のジョブでメッシュを生成

```bash
# Raw Depth APIのメッシュ（既存）
python regenerate_mesh.py 0a89490c existing

# Depth API（通常）のメッシュ
python regenerate_mesh.py <depth_api_job_id> existing
```

### 比較項目

- [ ] **メッシュの三角形数**
  - Raw Depth API: ?
  - Depth API: ?
  
- [ ] **メッシュの頂点数**
  - Raw Depth API: ?
  - Depth API: ?

- [ ] **視覚的な品質**
  - 波打ちの有無
  - ノイズの量
  - 詳細の保持
  - 滑らかさ

- [ ] **ファイルサイズ**
  - Raw Depth API: ?MB
  - Depth API: ?MB

---

## ステップ5: 判断基準

### Depth API（通常）を選択する場合

✅ **条件:**
- 解像度がRaw Depth APIと同じか高い（320x240以上）
- 有効ピクセルが10%以上
- 標準偏差が低い（ノイズが少ない、< 1.0m）
- メッシュ品質が良い（波打ちが少ない、詳細が保持されている）

**理由:**
- ARCoreのフィルタリングが有効
- サーバー側の前処理が不要（または軽減）
- より安定した品質

### Raw Depth APIを選択する場合

✅ **条件:**
- 解像度がDepth APIより高い（320x240以上）
- 有効ピクセルが10%以上（サーバー側フィルタリング後）
- サーバー側で適切にフィルタリング可能
- メッシュ品質が良い（より詳細、より滑らか）

**理由:**
- より高解像度
- より多くの情報
- サーバー側で柔軟に処理可能

---

## ステップ6: 設定の最適化

### Depth API（通常）を選択した場合

**推奨設定変更:**
```yaml
processing:
  depth:
    # Depth APIは既にフィルタリング済みのため、前処理を軽減
    filter_noise: false  # ARCoreが既に実施済み
    bilateral_filter: false  # ARCoreが既に実施済み
    # または、より軽いフィルタリング
    bilateral_sigma_color: 30.0  # デフォルトより軽く
    bilateral_sigma_space: 30.0
```

### Raw Depth APIを選択した場合

**推奨設定（現在の設定を維持）:**
```yaml
processing:
  depth:
    trunc: 7.0  # 診断結果に基づく
    filter_noise: true  # 必要
    bilateral_filter: true  # 必要
```

---

## ステップ7: 結果の記録

比較結果を記録して、今後の参考にする：

```
## Depth API比較結果 (YYYY-MM-DD)

### Raw Depth API
- ジョブID: 0a89490c
- 解像度: 160x90
- 有効ピクセル: 0.4%
- メッシュ品質: [評価]

### Depth API（通常）
- ジョブID: <depth_api_job_id>
- 解像度: ?x?
- 有効ピクセル: ?%
- メッシュ品質: [評価]

### 結論
[どちらを選択したか、理由]

```

---

## 参考: 期待される結果

### 理想的なDepth API（通常）の結果

- 解像度: 320x240以上
- 有効ピクセル: 10-30%以上
- 標準偏差: < 1.0m
- ノイズが少ない、安定した品質

### 理想的なRaw Depth APIの結果

- 解像度: 320x240〜640x480
- 有効ピクセル: 20-40%以上（フィルタリング前）、10-20%以上（フィルタリング後）
- 標準偏差: サーバー側フィルタリング後 < 1.5m
- より高解像度、より詳細

---

## 次のステップ

1. ✅ Depth API（通常）で新しいジョブを作成
2. ✅ 診断スクリプトで比較
3. ✅ メッシュ品質を比較
4. ✅ 判断基準に基づいて選択
5. ✅ 設定を最適化

最終更新: 2026-01-08 10:23:00
---

# Depth API比較チェックリスト

## 目的

Raw Depth APIとDepth API（通常）の実際の性能を比較し、どちらが3Dメッシュ生成に適しているかを判断する。

---

## ステップ1: Depth API（通常）で新しいジョブを作成

### Androidアプリ側での変更

**変更前（Raw Depth API）:**
```kotlin
val rawDepthImage = frame.acquireRawDepthImage()
```

**変更後（Depth API）:**
```kotlin
val depthImage = frame.acquireDepthImage()
```

### データアップロード

1. Androidアプリで同じシーンをスキャン
2. サーバーにアップロード
3. ジョブIDを記録（例: `depth_api_job_id`）

---

## ステップ2: 診断スクリプトで比較

### Raw Depth APIの結果（既存）

```bash
python diagnose_depth.py 0a89490c
```

**結果:**
- 解像度: 160x90
- 有効ピクセル: 0.4%
- 99th percentile: 6.99m

### Depth API（通常）の結果

```bash
python diagnose_depth.py <depth_api_job_id>
```

**確認項目:**
- [ ] 解像度（width x height）
- [ ] 有効ピクセル率（valid_ratio %）
- [ ] 無効値マーカー率（invalid_ratio %）
- [ ] 深度範囲（min - max m）
- [ ] 99th percentile（m）
- [ ] 標準偏差（std dev m）

---

## ステップ3: 比較表を作成

| 項目 | Raw Depth API | Depth API（通常） | 良い方 |
|------|---------------|-------------------|--------|
| **解像度** | 160x90 | ?x? | ? |
| **有効ピクセル率** | 0.4% | ?% | ? |
| **無効値マーカー率** | 99.6% | ?% | ? |
| **深度範囲（min）** | 2.00m | ?m | - |
| **深度範囲（max）** | 16.00m | ?m | - |
| **99th percentile** | 6.99m | ?m | - |
| **標準偏差** | 0.804m | ?m | Depth API |
| **推奨depth_trunc** | 7.0m | ?m | - |

---

## ステップ4: メッシュ品質を比較

### 両方のジョブでメッシュを生成

```bash
# Raw Depth APIのメッシュ（既存）
python regenerate_mesh.py 0a89490c existing

# Depth API（通常）のメッシュ
python regenerate_mesh.py <depth_api_job_id> existing
```

### 比較項目

- [ ] **メッシュの三角形数**
  - Raw Depth API: ?
  - Depth API: ?
  
- [ ] **メッシュの頂点数**
  - Raw Depth API: ?
  - Depth API: ?

- [ ] **視覚的な品質**
  - 波打ちの有無
  - ノイズの量
  - 詳細の保持
  - 滑らかさ

- [ ] **ファイルサイズ**
  - Raw Depth API: ?MB
  - Depth API: ?MB

---

## ステップ5: 判断基準

### Depth API（通常）を選択する場合

✅ **条件:**
- 解像度がRaw Depth APIと同じか高い（320x240以上）
- 有効ピクセルが10%以上
- 標準偏差が低い（ノイズが少ない、< 1.0m）
- メッシュ品質が良い（波打ちが少ない、詳細が保持されている）

**理由:**
- ARCoreのフィルタリングが有効
- サーバー側の前処理が不要（または軽減）
- より安定した品質

### Raw Depth APIを選択する場合

✅ **条件:**
- 解像度がDepth APIより高い（320x240以上）
- 有効ピクセルが10%以上（サーバー側フィルタリング後）
- サーバー側で適切にフィルタリング可能
- メッシュ品質が良い（より詳細、より滑らか）

**理由:**
- より高解像度
- より多くの情報
- サーバー側で柔軟に処理可能

---

## ステップ6: 設定の最適化

### Depth API（通常）を選択した場合

**推奨設定変更:**
```yaml
processing:
  depth:
    # Depth APIは既にフィルタリング済みのため、前処理を軽減
    filter_noise: false  # ARCoreが既に実施済み
    bilateral_filter: false  # ARCoreが既に実施済み
    # または、より軽いフィルタリング
    bilateral_sigma_color: 30.0  # デフォルトより軽く
    bilateral_sigma_space: 30.0
```

### Raw Depth APIを選択した場合

**推奨設定（現在の設定を維持）:**
```yaml
processing:
  depth:
    trunc: 7.0  # 診断結果に基づく
    filter_noise: true  # 必要
    bilateral_filter: true  # 必要
```

---

## ステップ7: 結果の記録

比較結果を記録して、今後の参考にする：

```
## Depth API比較結果 (YYYY-MM-DD)

### Raw Depth API
- ジョブID: 0a89490c
- 解像度: 160x90
- 有効ピクセル: 0.4%
- メッシュ品質: [評価]

### Depth API（通常）
- ジョブID: <depth_api_job_id>
- 解像度: ?x?
- 有効ピクセル: ?%
- メッシュ品質: [評価]

### 結論
[どちらを選択したか、理由]

```

---

## 参考: 期待される結果

### 理想的なDepth API（通常）の結果

- 解像度: 320x240以上
- 有効ピクセル: 10-30%以上
- 標準偏差: < 1.0m
- ノイズが少ない、安定した品質

### 理想的なRaw Depth APIの結果

- 解像度: 320x240〜640x480
- 有効ピクセル: 20-40%以上（フィルタリング前）、10-20%以上（フィルタリング後）
- 標準偏差: サーバー側フィルタリング後 < 1.5m
- より高解像度、より詳細

---

## 次のステップ

1. ✅ Depth API（通常）で新しいジョブを作成
2. ✅ 診断スクリプトで比較
3. ✅ メッシュ品質を比較
4. ✅ 判断基準に基づいて選択
5. ✅ 設定を最適化

最終更新: 2026-01-08 10:23:00
---

# Depth API比較チェックリスト

## 目的

Raw Depth APIとDepth API（通常）の実際の性能を比較し、どちらが3Dメッシュ生成に適しているかを判断する。

---

## ステップ1: Depth API（通常）で新しいジョブを作成

### Androidアプリ側での変更

**変更前（Raw Depth API）:**
```kotlin
val rawDepthImage = frame.acquireRawDepthImage()
```

**変更後（Depth API）:**
```kotlin
val depthImage = frame.acquireDepthImage()
```

### データアップロード

1. Androidアプリで同じシーンをスキャン
2. サーバーにアップロード
3. ジョブIDを記録（例: `depth_api_job_id`）

---

## ステップ2: 診断スクリプトで比較

### Raw Depth APIの結果（既存）

```bash
python diagnose_depth.py 0a89490c
```

**結果:**
- 解像度: 160x90
- 有効ピクセル: 0.4%
- 99th percentile: 6.99m

### Depth API（通常）の結果

```bash
python diagnose_depth.py <depth_api_job_id>
```

**確認項目:**
- [ ] 解像度（width x height）
- [ ] 有効ピクセル率（valid_ratio %）
- [ ] 無効値マーカー率（invalid_ratio %）
- [ ] 深度範囲（min - max m）
- [ ] 99th percentile（m）
- [ ] 標準偏差（std dev m）

---

## ステップ3: 比較表を作成

| 項目 | Raw Depth API | Depth API（通常） | 良い方 |
|------|---------------|-------------------|--------|
| **解像度** | 160x90 | ?x? | ? |
| **有効ピクセル率** | 0.4% | ?% | ? |
| **無効値マーカー率** | 99.6% | ?% | ? |
| **深度範囲（min）** | 2.00m | ?m | - |
| **深度範囲（max）** | 16.00m | ?m | - |
| **99th percentile** | 6.99m | ?m | - |
| **標準偏差** | 0.804m | ?m | Depth API |
| **推奨depth_trunc** | 7.0m | ?m | - |

---

## ステップ4: メッシュ品質を比較

### 両方のジョブでメッシュを生成

```bash
# Raw Depth APIのメッシュ（既存）
python regenerate_mesh.py 0a89490c existing

# Depth API（通常）のメッシュ
python regenerate_mesh.py <depth_api_job_id> existing
```

### 比較項目

- [ ] **メッシュの三角形数**
  - Raw Depth API: ?
  - Depth API: ?
  
- [ ] **メッシュの頂点数**
  - Raw Depth API: ?
  - Depth API: ?

- [ ] **視覚的な品質**
  - 波打ちの有無
  - ノイズの量
  - 詳細の保持
  - 滑らかさ

- [ ] **ファイルサイズ**
  - Raw Depth API: ?MB
  - Depth API: ?MB

---

## ステップ5: 判断基準

### Depth API（通常）を選択する場合

✅ **条件:**
- 解像度がRaw Depth APIと同じか高い（320x240以上）
- 有効ピクセルが10%以上
- 標準偏差が低い（ノイズが少ない、< 1.0m）
- メッシュ品質が良い（波打ちが少ない、詳細が保持されている）

**理由:**
- ARCoreのフィルタリングが有効
- サーバー側の前処理が不要（または軽減）
- より安定した品質

### Raw Depth APIを選択する場合

✅ **条件:**
- 解像度がDepth APIより高い（320x240以上）
- 有効ピクセルが10%以上（サーバー側フィルタリング後）
- サーバー側で適切にフィルタリング可能
- メッシュ品質が良い（より詳細、より滑らか）

**理由:**
- より高解像度
- より多くの情報
- サーバー側で柔軟に処理可能

---

## ステップ6: 設定の最適化

### Depth API（通常）を選択した場合

**推奨設定変更:**
```yaml
processing:
  depth:
    # Depth APIは既にフィルタリング済みのため、前処理を軽減
    filter_noise: false  # ARCoreが既に実施済み
    bilateral_filter: false  # ARCoreが既に実施済み
    # または、より軽いフィルタリング
    bilateral_sigma_color: 30.0  # デフォルトより軽く
    bilateral_sigma_space: 30.0
```

### Raw Depth APIを選択した場合

**推奨設定（現在の設定を維持）:**
```yaml
processing:
  depth:
    trunc: 7.0  # 診断結果に基づく
    filter_noise: true  # 必要
    bilateral_filter: true  # 必要
```

---

## ステップ7: 結果の記録

比較結果を記録して、今後の参考にする：

```
## Depth API比較結果 (YYYY-MM-DD)

### Raw Depth API
- ジョブID: 0a89490c
- 解像度: 160x90
- 有効ピクセル: 0.4%
- メッシュ品質: [評価]

### Depth API（通常）
- ジョブID: <depth_api_job_id>
- 解像度: ?x?
- 有効ピクセル: ?%
- メッシュ品質: [評価]

### 結論
[どちらを選択したか、理由]

```

---

## 参考: 期待される結果

### 理想的なDepth API（通常）の結果

- 解像度: 320x240以上
- 有効ピクセル: 10-30%以上
- 標準偏差: < 1.0m
- ノイズが少ない、安定した品質

### 理想的なRaw Depth APIの結果

- 解像度: 320x240〜640x480
- 有効ピクセル: 20-40%以上（フィルタリング前）、10-20%以上（フィルタリング後）
- 標準偏差: サーバー側フィルタリング後 < 1.5m
- より高解像度、より詳細

---

## 次のステップ

1. ✅ Depth API（通常）で新しいジョブを作成
2. ✅ 診断スクリプトで比較
3. ✅ メッシュ品質を比較
4. ✅ 判断基準に基づいて選択
5. ✅ 設定を最適化
最終更新: 2026-01-08 10:23:00
---

# Depth API比較チェックリスト

## 目的

Raw Depth APIとDepth API（通常）の実際の性能を比較し、どちらが3Dメッシュ生成に適しているかを判断する。

---

## ステップ1: Depth API（通常）で新しいジョブを作成

### Androidアプリ側での変更

**変更前（Raw Depth API）:**
```kotlin
val rawDepthImage = frame.acquireRawDepthImage()
```

**変更後（Depth API）:**
```kotlin
val depthImage = frame.acquireDepthImage()
```

### データアップロード

1. Androidアプリで同じシーンをスキャン
2. サーバーにアップロード
3. ジョブIDを記録（例: `depth_api_job_id`）

---

## ステップ2: 診断スクリプトで比較

### Raw Depth APIの結果（既存）

```bash
python diagnose_depth.py 0a89490c
```

**結果:**
- 解像度: 160x90
- 有効ピクセル: 0.4%
- 99th percentile: 6.99m

### Depth API（通常）の結果

```bash
python diagnose_depth.py <depth_api_job_id>
```

**確認項目:**
- [ ] 解像度（width x height）
- [ ] 有効ピクセル率（valid_ratio %）
- [ ] 無効値マーカー率（invalid_ratio %）
- [ ] 深度範囲（min - max m）
- [ ] 99th percentile（m）
- [ ] 標準偏差（std dev m）

---

## ステップ3: 比較表を作成

| 項目 | Raw Depth API | Depth API（通常） | 良い方 |
|------|---------------|-------------------|--------|
| **解像度** | 160x90 | ?x? | ? |
| **有効ピクセル率** | 0.4% | ?% | ? |
| **無効値マーカー率** | 99.6% | ?% | ? |
| **深度範囲（min）** | 2.00m | ?m | - |
| **深度範囲（max）** | 16.00m | ?m | - |
| **99th percentile** | 6.99m | ?m | - |
| **標準偏差** | 0.804m | ?m | Depth API |
| **推奨depth_trunc** | 7.0m | ?m | - |

---

## ステップ4: メッシュ品質を比較

### 両方のジョブでメッシュを生成

```bash
# Raw Depth APIのメッシュ（既存）
python regenerate_mesh.py 0a89490c existing

# Depth API（通常）のメッシュ
python regenerate_mesh.py <depth_api_job_id> existing
```

### 比較項目

- [ ] **メッシュの三角形数**
  - Raw Depth API: ?
  - Depth API: ?
  
- [ ] **メッシュの頂点数**
  - Raw Depth API: ?
  - Depth API: ?

- [ ] **視覚的な品質**
  - 波打ちの有無
  - ノイズの量
  - 詳細の保持
  - 滑らかさ

- [ ] **ファイルサイズ**
  - Raw Depth API: ?MB
  - Depth API: ?MB

---

## ステップ5: 判断基準

### Depth API（通常）を選択する場合

✅ **条件:**
- 解像度がRaw Depth APIと同じか高い（320x240以上）
- 有効ピクセルが10%以上
- 標準偏差が低い（ノイズが少ない、< 1.0m）
- メッシュ品質が良い（波打ちが少ない、詳細が保持されている）

**理由:**
- ARCoreのフィルタリングが有効
- サーバー側の前処理が不要（または軽減）
- より安定した品質

### Raw Depth APIを選択する場合

✅ **条件:**
- 解像度がDepth APIより高い（320x240以上）
- 有効ピクセルが10%以上（サーバー側フィルタリング後）
- サーバー側で適切にフィルタリング可能
- メッシュ品質が良い（より詳細、より滑らか）

**理由:**
- より高解像度
- より多くの情報
- サーバー側で柔軟に処理可能

---

## ステップ6: 設定の最適化

### Depth API（通常）を選択した場合

**推奨設定変更:**
```yaml
processing:
  depth:
    # Depth APIは既にフィルタリング済みのため、前処理を軽減
    filter_noise: false  # ARCoreが既に実施済み
    bilateral_filter: false  # ARCoreが既に実施済み
    # または、より軽いフィルタリング
    bilateral_sigma_color: 30.0  # デフォルトより軽く
    bilateral_sigma_space: 30.0
```

### Raw Depth APIを選択した場合

**推奨設定（現在の設定を維持）:**
```yaml
processing:
  depth:
    trunc: 7.0  # 診断結果に基づく
    filter_noise: true  # 必要
    bilateral_filter: true  # 必要
```

---

## ステップ7: 結果の記録

比較結果を記録して、今後の参考にする：

```
## Depth API比較結果 (YYYY-MM-DD)

### Raw Depth API
- ジョブID: 0a89490c
- 解像度: 160x90
- 有効ピクセル: 0.4%
- メッシュ品質: [評価]

### Depth API（通常）
- ジョブID: <depth_api_job_id>
- 解像度: ?x?
- 有効ピクセル: ?%
- メッシュ品質: [評価]

### 結論
[どちらを選択したか、理由]

```

---

## 参考: 期待される結果

### 理想的なDepth API（通常）の結果

- 解像度: 320x240以上
- 有効ピクセル: 10-30%以上
- 標準偏差: < 1.0m
- ノイズが少ない、安定した品質

### 理想的なRaw Depth APIの結果

- 解像度: 320x240〜640x480
- 有効ピクセル: 20-40%以上（フィルタリング前）、10-20%以上（フィルタリング後）
- 標準偏差: サーバー側フィルタリング後 < 1.5m
- より高解像度、より詳細

---

## 次のステップ

1. ✅ Depth API（通常）で新しいジョブを作成
2. ✅ 診断スクリプトで比較
3. ✅ メッシュ品質を比較
4. ✅ 判断基準に基づいて選択
5. ✅ 設定を最適化

最終更新: 2026-01-08 10:23:00
---

# Depth API比較チェックリスト

## 目的

Raw Depth APIとDepth API（通常）の実際の性能を比較し、どちらが3Dメッシュ生成に適しているかを判断する。

---

## ステップ1: Depth API（通常）で新しいジョブを作成

### Androidアプリ側での変更

**変更前（Raw Depth API）:**
```kotlin
val rawDepthImage = frame.acquireRawDepthImage()
```

**変更後（Depth API）:**
```kotlin
val depthImage = frame.acquireDepthImage()
```

### データアップロード

1. Androidアプリで同じシーンをスキャン
2. サーバーにアップロード
3. ジョブIDを記録（例: `depth_api_job_id`）

---

## ステップ2: 診断スクリプトで比較

### Raw Depth APIの結果（既存）

```bash
python diagnose_depth.py 0a89490c
```

**結果:**
- 解像度: 160x90
- 有効ピクセル: 0.4%
- 99th percentile: 6.99m

### Depth API（通常）の結果

```bash
python diagnose_depth.py <depth_api_job_id>
```

**確認項目:**
- [ ] 解像度（width x height）
- [ ] 有効ピクセル率（valid_ratio %）
- [ ] 無効値マーカー率（invalid_ratio %）
- [ ] 深度範囲（min - max m）
- [ ] 99th percentile（m）
- [ ] 標準偏差（std dev m）

---

## ステップ3: 比較表を作成

| 項目 | Raw Depth API | Depth API（通常） | 良い方 |
|------|---------------|-------------------|--------|
| **解像度** | 160x90 | ?x? | ? |
| **有効ピクセル率** | 0.4% | ?% | ? |
| **無効値マーカー率** | 99.6% | ?% | ? |
| **深度範囲（min）** | 2.00m | ?m | - |
| **深度範囲（max）** | 16.00m | ?m | - |
| **99th percentile** | 6.99m | ?m | - |
| **標準偏差** | 0.804m | ?m | Depth API |
| **推奨depth_trunc** | 7.0m | ?m | - |

---

## ステップ4: メッシュ品質を比較

### 両方のジョブでメッシュを生成

```bash
# Raw Depth APIのメッシュ（既存）
python regenerate_mesh.py 0a89490c existing

# Depth API（通常）のメッシュ
python regenerate_mesh.py <depth_api_job_id> existing
```

### 比較項目

- [ ] **メッシュの三角形数**
  - Raw Depth API: ?
  - Depth API: ?
  
- [ ] **メッシュの頂点数**
  - Raw Depth API: ?
  - Depth API: ?

- [ ] **視覚的な品質**
  - 波打ちの有無
  - ノイズの量
  - 詳細の保持
  - 滑らかさ

- [ ] **ファイルサイズ**
  - Raw Depth API: ?MB
  - Depth API: ?MB

---

## ステップ5: 判断基準

### Depth API（通常）を選択する場合

✅ **条件:**
- 解像度がRaw Depth APIと同じか高い（320x240以上）
- 有効ピクセルが10%以上
- 標準偏差が低い（ノイズが少ない、< 1.0m）
- メッシュ品質が良い（波打ちが少ない、詳細が保持されている）

**理由:**
- ARCoreのフィルタリングが有効
- サーバー側の前処理が不要（または軽減）
- より安定した品質

### Raw Depth APIを選択する場合

✅ **条件:**
- 解像度がDepth APIより高い（320x240以上）
- 有効ピクセルが10%以上（サーバー側フィルタリング後）
- サーバー側で適切にフィルタリング可能
- メッシュ品質が良い（より詳細、より滑らか）

**理由:**
- より高解像度
- より多くの情報
- サーバー側で柔軟に処理可能

---

## ステップ6: 設定の最適化

### Depth API（通常）を選択した場合

**推奨設定変更:**
```yaml
processing:
  depth:
    # Depth APIは既にフィルタリング済みのため、前処理を軽減
    filter_noise: false  # ARCoreが既に実施済み
    bilateral_filter: false  # ARCoreが既に実施済み
    # または、より軽いフィルタリング
    bilateral_sigma_color: 30.0  # デフォルトより軽く
    bilateral_sigma_space: 30.0
```

### Raw Depth APIを選択した場合

**推奨設定（現在の設定を維持）:**
```yaml
processing:
  depth:
    trunc: 7.0  # 診断結果に基づく
    filter_noise: true  # 必要
    bilateral_filter: true  # 必要
```

---

## ステップ7: 結果の記録

比較結果を記録して、今後の参考にする：

```
## Depth API比較結果 (YYYY-MM-DD)

### Raw Depth API
- ジョブID: 0a89490c
- 解像度: 160x90
- 有効ピクセル: 0.4%
- メッシュ品質: [評価]

### Depth API（通常）
- ジョブID: <depth_api_job_id>
- 解像度: ?x?
- 有効ピクセル: ?%
- メッシュ品質: [評価]

### 結論
[どちらを選択したか、理由]

```

---

## 参考: 期待される結果

### 理想的なDepth API（通常）の結果

- 解像度: 320x240以上
- 有効ピクセル: 10-30%以上
- 標準偏差: < 1.0m
- ノイズが少ない、安定した品質

### 理想的なRaw Depth APIの結果

- 解像度: 320x240〜640x480
- 有効ピクセル: 20-40%以上（フィルタリング前）、10-20%以上（フィルタリング後）
- 標準偏差: サーバー側フィルタリング後 < 1.5m
- より高解像度、より詳細

---

## 次のステップ

1. ✅ Depth API（通常）で新しいジョブを作成
2. ✅ 診断スクリプトで比較
3. ✅ メッシュ品質を比較
4. ✅ 判断基準に基づいて選択
5. ✅ 設定を最適化

最終更新: 2026-01-08 10:23:00
---

# Depth API比較チェックリスト

## 目的

Raw Depth APIとDepth API（通常）の実際の性能を比較し、どちらが3Dメッシュ生成に適しているかを判断する。

---

## ステップ1: Depth API（通常）で新しいジョブを作成

### Androidアプリ側での変更

**変更前（Raw Depth API）:**
```kotlin
val rawDepthImage = frame.acquireRawDepthImage()
```

**変更後（Depth API）:**
```kotlin
val depthImage = frame.acquireDepthImage()
```

### データアップロード

1. Androidアプリで同じシーンをスキャン
2. サーバーにアップロード
3. ジョブIDを記録（例: `depth_api_job_id`）

---

## ステップ2: 診断スクリプトで比較

### Raw Depth APIの結果（既存）

```bash
python diagnose_depth.py 0a89490c
```

**結果:**
- 解像度: 160x90
- 有効ピクセル: 0.4%
- 99th percentile: 6.99m

### Depth API（通常）の結果

```bash
python diagnose_depth.py <depth_api_job_id>
```

**確認項目:**
- [ ] 解像度（width x height）
- [ ] 有効ピクセル率（valid_ratio %）
- [ ] 無効値マーカー率（invalid_ratio %）
- [ ] 深度範囲（min - max m）
- [ ] 99th percentile（m）
- [ ] 標準偏差（std dev m）

---

## ステップ3: 比較表を作成

| 項目 | Raw Depth API | Depth API（通常） | 良い方 |
|------|---------------|-------------------|--------|
| **解像度** | 160x90 | ?x? | ? |
| **有効ピクセル率** | 0.4% | ?% | ? |
| **無効値マーカー率** | 99.6% | ?% | ? |
| **深度範囲（min）** | 2.00m | ?m | - |
| **深度範囲（max）** | 16.00m | ?m | - |
| **99th percentile** | 6.99m | ?m | - |
| **標準偏差** | 0.804m | ?m | Depth API |
| **推奨depth_trunc** | 7.0m | ?m | - |

---

## ステップ4: メッシュ品質を比較

### 両方のジョブでメッシュを生成

```bash
# Raw Depth APIのメッシュ（既存）
python regenerate_mesh.py 0a89490c existing

# Depth API（通常）のメッシュ
python regenerate_mesh.py <depth_api_job_id> existing
```

### 比較項目

- [ ] **メッシュの三角形数**
  - Raw Depth API: ?
  - Depth API: ?
  
- [ ] **メッシュの頂点数**
  - Raw Depth API: ?
  - Depth API: ?

- [ ] **視覚的な品質**
  - 波打ちの有無
  - ノイズの量
  - 詳細の保持
  - 滑らかさ

- [ ] **ファイルサイズ**
  - Raw Depth API: ?MB
  - Depth API: ?MB

---

## ステップ5: 判断基準

### Depth API（通常）を選択する場合

✅ **条件:**
- 解像度がRaw Depth APIと同じか高い（320x240以上）
- 有効ピクセルが10%以上
- 標準偏差が低い（ノイズが少ない、< 1.0m）
- メッシュ品質が良い（波打ちが少ない、詳細が保持されている）

**理由:**
- ARCoreのフィルタリングが有効
- サーバー側の前処理が不要（または軽減）
- より安定した品質

### Raw Depth APIを選択する場合

✅ **条件:**
- 解像度がDepth APIより高い（320x240以上）
- 有効ピクセルが10%以上（サーバー側フィルタリング後）
- サーバー側で適切にフィルタリング可能
- メッシュ品質が良い（より詳細、より滑らか）

**理由:**
- より高解像度
- より多くの情報
- サーバー側で柔軟に処理可能

---

## ステップ6: 設定の最適化

### Depth API（通常）を選択した場合

**推奨設定変更:**
```yaml
processing:
  depth:
    # Depth APIは既にフィルタリング済みのため、前処理を軽減
    filter_noise: false  # ARCoreが既に実施済み
    bilateral_filter: false  # ARCoreが既に実施済み
    # または、より軽いフィルタリング
    bilateral_sigma_color: 30.0  # デフォルトより軽く
    bilateral_sigma_space: 30.0
```

### Raw Depth APIを選択した場合

**推奨設定（現在の設定を維持）:**
```yaml
processing:
  depth:
    trunc: 7.0  # 診断結果に基づく
    filter_noise: true  # 必要
    bilateral_filter: true  # 必要
```

---

## ステップ7: 結果の記録

比較結果を記録して、今後の参考にする：

```
## Depth API比較結果 (YYYY-MM-DD)

### Raw Depth API
- ジョブID: 0a89490c
- 解像度: 160x90
- 有効ピクセル: 0.4%
- メッシュ品質: [評価]

### Depth API（通常）
- ジョブID: <depth_api_job_id>
- 解像度: ?x?
- 有効ピクセル: ?%
- メッシュ品質: [評価]

### 結論
[どちらを選択したか、理由]

```

---

## 参考: 期待される結果

### 理想的なDepth API（通常）の結果

- 解像度: 320x240以上
- 有効ピクセル: 10-30%以上
- 標準偏差: < 1.0m
- ノイズが少ない、安定した品質

### 理想的なRaw Depth APIの結果

- 解像度: 320x240〜640x480
- 有効ピクセル: 20-40%以上（フィルタリング前）、10-20%以上（フィルタリング後）
- 標準偏差: サーバー側フィルタリング後 < 1.5m
- より高解像度、より詳細

---

## 次のステップ

1. ✅ Depth API（通常）で新しいジョブを作成
2. ✅ 診断スクリプトで比較
3. ✅ メッシュ品質を比較
4. ✅ 判断基準に基づいて選択
5. ✅ 設定を最適化

最終更新: 2026-01-08 10:23:00
---

# Depth API比較チェックリスト

## 目的

Raw Depth APIとDepth API（通常）の実際の性能を比較し、どちらが3Dメッシュ生成に適しているかを判断する。

---

## ステップ1: Depth API（通常）で新しいジョブを作成

### Androidアプリ側での変更

**変更前（Raw Depth API）:**
```kotlin
val rawDepthImage = frame.acquireRawDepthImage()
```

**変更後（Depth API）:**
```kotlin
val depthImage = frame.acquireDepthImage()
```

### データアップロード

1. Androidアプリで同じシーンをスキャン
2. サーバーにアップロード
3. ジョブIDを記録（例: `depth_api_job_id`）

---

## ステップ2: 診断スクリプトで比較

### Raw Depth APIの結果（既存）

```bash
python diagnose_depth.py 0a89490c
```

**結果:**
- 解像度: 160x90
- 有効ピクセル: 0.4%
- 99th percentile: 6.99m

### Depth API（通常）の結果

```bash
python diagnose_depth.py <depth_api_job_id>
```

**確認項目:**
- [ ] 解像度（width x height）
- [ ] 有効ピクセル率（valid_ratio %）
- [ ] 無効値マーカー率（invalid_ratio %）
- [ ] 深度範囲（min - max m）
- [ ] 99th percentile（m）
- [ ] 標準偏差（std dev m）

---

## ステップ3: 比較表を作成

| 項目 | Raw Depth API | Depth API（通常） | 良い方 |
|------|---------------|-------------------|--------|
| **解像度** | 160x90 | ?x? | ? |
| **有効ピクセル率** | 0.4% | ?% | ? |
| **無効値マーカー率** | 99.6% | ?% | ? |
| **深度範囲（min）** | 2.00m | ?m | - |
| **深度範囲（max）** | 16.00m | ?m | - |
| **99th percentile** | 6.99m | ?m | - |
| **標準偏差** | 0.804m | ?m | Depth API |
| **推奨depth_trunc** | 7.0m | ?m | - |

---

## ステップ4: メッシュ品質を比較

### 両方のジョブでメッシュを生成

```bash
# Raw Depth APIのメッシュ（既存）
python regenerate_mesh.py 0a89490c existing

# Depth API（通常）のメッシュ
python regenerate_mesh.py <depth_api_job_id> existing
```

### 比較項目

- [ ] **メッシュの三角形数**
  - Raw Depth API: ?
  - Depth API: ?
  
- [ ] **メッシュの頂点数**
  - Raw Depth API: ?
  - Depth API: ?

- [ ] **視覚的な品質**
  - 波打ちの有無
  - ノイズの量
  - 詳細の保持
  - 滑らかさ

- [ ] **ファイルサイズ**
  - Raw Depth API: ?MB
  - Depth API: ?MB

---

## ステップ5: 判断基準

### Depth API（通常）を選択する場合

✅ **条件:**
- 解像度がRaw Depth APIと同じか高い（320x240以上）
- 有効ピクセルが10%以上
- 標準偏差が低い（ノイズが少ない、< 1.0m）
- メッシュ品質が良い（波打ちが少ない、詳細が保持されている）

**理由:**
- ARCoreのフィルタリングが有効
- サーバー側の前処理が不要（または軽減）
- より安定した品質

### Raw Depth APIを選択する場合

✅ **条件:**
- 解像度がDepth APIより高い（320x240以上）
- 有効ピクセルが10%以上（サーバー側フィルタリング後）
- サーバー側で適切にフィルタリング可能
- メッシュ品質が良い（より詳細、より滑らか）

**理由:**
- より高解像度
- より多くの情報
- サーバー側で柔軟に処理可能

---

## ステップ6: 設定の最適化

### Depth API（通常）を選択した場合

**推奨設定変更:**
```yaml
processing:
  depth:
    # Depth APIは既にフィルタリング済みのため、前処理を軽減
    filter_noise: false  # ARCoreが既に実施済み
    bilateral_filter: false  # ARCoreが既に実施済み
    # または、より軽いフィルタリング
    bilateral_sigma_color: 30.0  # デフォルトより軽く
    bilateral_sigma_space: 30.0
```

### Raw Depth APIを選択した場合

**推奨設定（現在の設定を維持）:**
```yaml
processing:
  depth:
    trunc: 7.0  # 診断結果に基づく
    filter_noise: true  # 必要
    bilateral_filter: true  # 必要
```

---

## ステップ7: 結果の記録

比較結果を記録して、今後の参考にする：

```
## Depth API比較結果 (YYYY-MM-DD)

### Raw Depth API
- ジョブID: 0a89490c
- 解像度: 160x90
- 有効ピクセル: 0.4%
- メッシュ品質: [評価]

### Depth API（通常）
- ジョブID: <depth_api_job_id>
- 解像度: ?x?
- 有効ピクセル: ?%
- メッシュ品質: [評価]

### 結論
[どちらを選択したか、理由]

```

---

## 参考: 期待される結果

### 理想的なDepth API（通常）の結果

- 解像度: 320x240以上
- 有効ピクセル: 10-30%以上
- 標準偏差: < 1.0m
- ノイズが少ない、安定した品質

### 理想的なRaw Depth APIの結果

- 解像度: 320x240〜640x480
- 有効ピクセル: 20-40%以上（フィルタリング前）、10-20%以上（フィルタリング後）
- 標準偏差: サーバー側フィルタリング後 < 1.5m
- より高解像度、より詳細

---

## 次のステップ

1. ✅ Depth API（通常）で新しいジョブを作成
2. ✅ 診断スクリプトで比較
3. ✅ メッシュ品質を比較
4. ✅ 判断基準に基づいて選択
5. ✅ 設定を最適化

最終更新: 2026-01-08 10:23:00
---

# Depth API比較チェックリスト

## 目的

Raw Depth APIとDepth API（通常）の実際の性能を比較し、どちらが3Dメッシュ生成に適しているかを判断する。

---

## ステップ1: Depth API（通常）で新しいジョブを作成

### Androidアプリ側での変更

**変更前（Raw Depth API）:**
```kotlin
val rawDepthImage = frame.acquireRawDepthImage()
```

**変更後（Depth API）:**
```kotlin
val depthImage = frame.acquireDepthImage()
```

### データアップロード

1. Androidアプリで同じシーンをスキャン
2. サーバーにアップロード
3. ジョブIDを記録（例: `depth_api_job_id`）

---

## ステップ2: 診断スクリプトで比較

### Raw Depth APIの結果（既存）

```bash
python diagnose_depth.py 0a89490c
```

**結果:**
- 解像度: 160x90
- 有効ピクセル: 0.4%
- 99th percentile: 6.99m

### Depth API（通常）の結果

```bash
python diagnose_depth.py <depth_api_job_id>
```

**確認項目:**
- [ ] 解像度（width x height）
- [ ] 有効ピクセル率（valid_ratio %）
- [ ] 無効値マーカー率（invalid_ratio %）
- [ ] 深度範囲（min - max m）
- [ ] 99th percentile（m）
- [ ] 標準偏差（std dev m）

---

## ステップ3: 比較表を作成

| 項目 | Raw Depth API | Depth API（通常） | 良い方 |
|------|---------------|-------------------|--------|
| **解像度** | 160x90 | ?x? | ? |
| **有効ピクセル率** | 0.4% | ?% | ? |
| **無効値マーカー率** | 99.6% | ?% | ? |
| **深度範囲（min）** | 2.00m | ?m | - |
| **深度範囲（max）** | 16.00m | ?m | - |
| **99th percentile** | 6.99m | ?m | - |
| **標準偏差** | 0.804m | ?m | Depth API |
| **推奨depth_trunc** | 7.0m | ?m | - |

---

## ステップ4: メッシュ品質を比較

### 両方のジョブでメッシュを生成

```bash
# Raw Depth APIのメッシュ（既存）
python regenerate_mesh.py 0a89490c existing

# Depth API（通常）のメッシュ
python regenerate_mesh.py <depth_api_job_id> existing
```

### 比較項目

- [ ] **メッシュの三角形数**
  - Raw Depth API: ?
  - Depth API: ?
  
- [ ] **メッシュの頂点数**
  - Raw Depth API: ?
  - Depth API: ?

- [ ] **視覚的な品質**
  - 波打ちの有無
  - ノイズの量
  - 詳細の保持
  - 滑らかさ

- [ ] **ファイルサイズ**
  - Raw Depth API: ?MB
  - Depth API: ?MB

---

## ステップ5: 判断基準

### Depth API（通常）を選択する場合

✅ **条件:**
- 解像度がRaw Depth APIと同じか高い（320x240以上）
- 有効ピクセルが10%以上
- 標準偏差が低い（ノイズが少ない、< 1.0m）
- メッシュ品質が良い（波打ちが少ない、詳細が保持されている）

**理由:**
- ARCoreのフィルタリングが有効
- サーバー側の前処理が不要（または軽減）
- より安定した品質

### Raw Depth APIを選択する場合

✅ **条件:**
- 解像度がDepth APIより高い（320x240以上）
- 有効ピクセルが10%以上（サーバー側フィルタリング後）
- サーバー側で適切にフィルタリング可能
- メッシュ品質が良い（より詳細、より滑らか）

**理由:**
- より高解像度
- より多くの情報
- サーバー側で柔軟に処理可能

---

## ステップ6: 設定の最適化

### Depth API（通常）を選択した場合

**推奨設定変更:**
```yaml
processing:
  depth:
    # Depth APIは既にフィルタリング済みのため、前処理を軽減
    filter_noise: false  # ARCoreが既に実施済み
    bilateral_filter: false  # ARCoreが既に実施済み
    # または、より軽いフィルタリング
    bilateral_sigma_color: 30.0  # デフォルトより軽く
    bilateral_sigma_space: 30.0
```

### Raw Depth APIを選択した場合

**推奨設定（現在の設定を維持）:**
```yaml
processing:
  depth:
    trunc: 7.0  # 診断結果に基づく
    filter_noise: true  # 必要
    bilateral_filter: true  # 必要
```

---

## ステップ7: 結果の記録

比較結果を記録して、今後の参考にする：

```
## Depth API比較結果 (YYYY-MM-DD)

### Raw Depth API
- ジョブID: 0a89490c
- 解像度: 160x90
- 有効ピクセル: 0.4%
- メッシュ品質: [評価]

### Depth API（通常）
- ジョブID: <depth_api_job_id>
- 解像度: ?x?
- 有効ピクセル: ?%
- メッシュ品質: [評価]

### 結論
[どちらを選択したか、理由]

```

---

## 参考: 期待される結果

### 理想的なDepth API（通常）の結果

- 解像度: 320x240以上
- 有効ピクセル: 10-30%以上
- 標準偏差: < 1.0m
- ノイズが少ない、安定した品質

### 理想的なRaw Depth APIの結果

- 解像度: 320x240〜640x480
- 有効ピクセル: 20-40%以上（フィルタリング前）、10-20%以上（フィルタリング後）
- 標準偏差: サーバー側フィルタリング後 < 1.5m
- より高解像度、より詳細

---

## 次のステップ

1. ✅ Depth API（通常）で新しいジョブを作成
2. ✅ 診断スクリプトで比較
3. ✅ メッシュ品質を比較
4. ✅ 判断基準に基づいて選択
5. ✅ 設定を最適化

最終更新: 2026-01-08 10:23:00
---

# Depth API比較チェックリスト

## 目的

Raw Depth APIとDepth API（通常）の実際の性能を比較し、どちらが3Dメッシュ生成に適しているかを判断する。

---

## ステップ1: Depth API（通常）で新しいジョブを作成

### Androidアプリ側での変更

**変更前（Raw Depth API）:**
```kotlin
val rawDepthImage = frame.acquireRawDepthImage()
```

**変更後（Depth API）:**
```kotlin
val depthImage = frame.acquireDepthImage()
```

### データアップロード

1. Androidアプリで同じシーンをスキャン
2. サーバーにアップロード
3. ジョブIDを記録（例: `depth_api_job_id`）

---

## ステップ2: 診断スクリプトで比較

### Raw Depth APIの結果（既存）

```bash
python diagnose_depth.py 0a89490c
```

**結果:**
- 解像度: 160x90
- 有効ピクセル: 0.4%
- 99th percentile: 6.99m

### Depth API（通常）の結果

```bash
python diagnose_depth.py <depth_api_job_id>
```

**確認項目:**
- [ ] 解像度（width x height）
- [ ] 有効ピクセル率（valid_ratio %）
- [ ] 無効値マーカー率（invalid_ratio %）
- [ ] 深度範囲（min - max m）
- [ ] 99th percentile（m）
- [ ] 標準偏差（std dev m）

---

## ステップ3: 比較表を作成

| 項目 | Raw Depth API | Depth API（通常） | 良い方 |
|------|---------------|-------------------|--------|
| **解像度** | 160x90 | ?x? | ? |
| **有効ピクセル率** | 0.4% | ?% | ? |
| **無効値マーカー率** | 99.6% | ?% | ? |
| **深度範囲（min）** | 2.00m | ?m | - |
| **深度範囲（max）** | 16.00m | ?m | - |
| **99th percentile** | 6.99m | ?m | - |
| **標準偏差** | 0.804m | ?m | Depth API |
| **推奨depth_trunc** | 7.0m | ?m | - |

---

## ステップ4: メッシュ品質を比較

### 両方のジョブでメッシュを生成

```bash
# Raw Depth APIのメッシュ（既存）
python regenerate_mesh.py 0a89490c existing

# Depth API（通常）のメッシュ
python regenerate_mesh.py <depth_api_job_id> existing
```

### 比較項目

- [ ] **メッシュの三角形数**
  - Raw Depth API: ?
  - Depth API: ?
  
- [ ] **メッシュの頂点数**
  - Raw Depth API: ?
  - Depth API: ?

- [ ] **視覚的な品質**
  - 波打ちの有無
  - ノイズの量
  - 詳細の保持
  - 滑らかさ

- [ ] **ファイルサイズ**
  - Raw Depth API: ?MB
  - Depth API: ?MB

---

## ステップ5: 判断基準

### Depth API（通常）を選択する場合

✅ **条件:**
- 解像度がRaw Depth APIと同じか高い（320x240以上）
- 有効ピクセルが10%以上
- 標準偏差が低い（ノイズが少ない、< 1.0m）
- メッシュ品質が良い（波打ちが少ない、詳細が保持されている）

**理由:**
- ARCoreのフィルタリングが有効
- サーバー側の前処理が不要（または軽減）
- より安定した品質

### Raw Depth APIを選択する場合

✅ **条件:**
- 解像度がDepth APIより高い（320x240以上）
- 有効ピクセルが10%以上（サーバー側フィルタリング後）
- サーバー側で適切にフィルタリング可能
- メッシュ品質が良い（より詳細、より滑らか）

**理由:**
- より高解像度
- より多くの情報
- サーバー側で柔軟に処理可能

---

## ステップ6: 設定の最適化

### Depth API（通常）を選択した場合

**推奨設定変更:**
```yaml
processing:
  depth:
    # Depth APIは既にフィルタリング済みのため、前処理を軽減
    filter_noise: false  # ARCoreが既に実施済み
    bilateral_filter: false  # ARCoreが既に実施済み
    # または、より軽いフィルタリング
    bilateral_sigma_color: 30.0  # デフォルトより軽く
    bilateral_sigma_space: 30.0
```

### Raw Depth APIを選択した場合

**推奨設定（現在の設定を維持）:**
```yaml
processing:
  depth:
    trunc: 7.0  # 診断結果に基づく
    filter_noise: true  # 必要
    bilateral_filter: true  # 必要
```

---

## ステップ7: 結果の記録

比較結果を記録して、今後の参考にする：

```
## Depth API比較結果 (YYYY-MM-DD)

### Raw Depth API
- ジョブID: 0a89490c
- 解像度: 160x90
- 有効ピクセル: 0.4%
- メッシュ品質: [評価]

### Depth API（通常）
- ジョブID: <depth_api_job_id>
- 解像度: ?x?
- 有効ピクセル: ?%
- メッシュ品質: [評価]

### 結論
[どちらを選択したか、理由]

```

---

## 参考: 期待される結果

### 理想的なDepth API（通常）の結果

- 解像度: 320x240以上
- 有効ピクセル: 10-30%以上
- 標準偏差: < 1.0m
- ノイズが少ない、安定した品質

### 理想的なRaw Depth APIの結果

- 解像度: 320x240〜640x480
- 有効ピクセル: 20-40%以上（フィルタリング前）、10-20%以上（フィルタリング後）
- 標準偏差: サーバー側フィルタリング後 < 1.5m
- より高解像度、より詳細

---

## 次のステップ

1. ✅ Depth API（通常）で新しいジョブを作成
2. ✅ 診断スクリプトで比較
3. ✅ メッシュ品質を比較
4. ✅ 判断基準に基づいて選択
5. ✅ 設定を最適化

最終更新: 2026-01-08 10:23:00
---

# Depth API比較チェックリスト

## 目的

Raw Depth APIとDepth API（通常）の実際の性能を比較し、どちらが3Dメッシュ生成に適しているかを判断する。

---

## ステップ1: Depth API（通常）で新しいジョブを作成

### Androidアプリ側での変更

**変更前（Raw Depth API）:**
```kotlin
val rawDepthImage = frame.acquireRawDepthImage()
```

**変更後（Depth API）:**
```kotlin
val depthImage = frame.acquireDepthImage()
```

### データアップロード

1. Androidアプリで同じシーンをスキャン
2. サーバーにアップロード
3. ジョブIDを記録（例: `depth_api_job_id`）

---

## ステップ2: 診断スクリプトで比較

### Raw Depth APIの結果（既存）

```bash
python diagnose_depth.py 0a89490c
```

**結果:**
- 解像度: 160x90
- 有効ピクセル: 0.4%
- 99th percentile: 6.99m

### Depth API（通常）の結果

```bash
python diagnose_depth.py <depth_api_job_id>
```

**確認項目:**
- [ ] 解像度（width x height）
- [ ] 有効ピクセル率（valid_ratio %）
- [ ] 無効値マーカー率（invalid_ratio %）
- [ ] 深度範囲（min - max m）
- [ ] 99th percentile（m）
- [ ] 標準偏差（std dev m）

---

## ステップ3: 比較表を作成

| 項目 | Raw Depth API | Depth API（通常） | 良い方 |
|------|---------------|-------------------|--------|
| **解像度** | 160x90 | ?x? | ? |
| **有効ピクセル率** | 0.4% | ?% | ? |
| **無効値マーカー率** | 99.6% | ?% | ? |
| **深度範囲（min）** | 2.00m | ?m | - |
| **深度範囲（max）** | 16.00m | ?m | - |
| **99th percentile** | 6.99m | ?m | - |
| **標準偏差** | 0.804m | ?m | Depth API |
| **推奨depth_trunc** | 7.0m | ?m | - |

---

## ステップ4: メッシュ品質を比較

### 両方のジョブでメッシュを生成

```bash
# Raw Depth APIのメッシュ（既存）
python regenerate_mesh.py 0a89490c existing

# Depth API（通常）のメッシュ
python regenerate_mesh.py <depth_api_job_id> existing
```

### 比較項目

- [ ] **メッシュの三角形数**
  - Raw Depth API: ?
  - Depth API: ?
  
- [ ] **メッシュの頂点数**
  - Raw Depth API: ?
  - Depth API: ?

- [ ] **視覚的な品質**
  - 波打ちの有無
  - ノイズの量
  - 詳細の保持
  - 滑らかさ

- [ ] **ファイルサイズ**
  - Raw Depth API: ?MB
  - Depth API: ?MB

---

## ステップ5: 判断基準

### Depth API（通常）を選択する場合

✅ **条件:**
- 解像度がRaw Depth APIと同じか高い（320x240以上）
- 有効ピクセルが10%以上
- 標準偏差が低い（ノイズが少ない、< 1.0m）
- メッシュ品質が良い（波打ちが少ない、詳細が保持されている）

**理由:**
- ARCoreのフィルタリングが有効
- サーバー側の前処理が不要（または軽減）
- より安定した品質

### Raw Depth APIを選択する場合

✅ **条件:**
- 解像度がDepth APIより高い（320x240以上）
- 有効ピクセルが10%以上（サーバー側フィルタリング後）
- サーバー側で適切にフィルタリング可能
- メッシュ品質が良い（より詳細、より滑らか）

**理由:**
- より高解像度
- より多くの情報
- サーバー側で柔軟に処理可能

---

## ステップ6: 設定の最適化

### Depth API（通常）を選択した場合

**推奨設定変更:**
```yaml
processing:
  depth:
    # Depth APIは既にフィルタリング済みのため、前処理を軽減
    filter_noise: false  # ARCoreが既に実施済み
    bilateral_filter: false  # ARCoreが既に実施済み
    # または、より軽いフィルタリング
    bilateral_sigma_color: 30.0  # デフォルトより軽く
    bilateral_sigma_space: 30.0
```

### Raw Depth APIを選択した場合

**推奨設定（現在の設定を維持）:**
```yaml
processing:
  depth:
    trunc: 7.0  # 診断結果に基づく
    filter_noise: true  # 必要
    bilateral_filter: true  # 必要
```

---

## ステップ7: 結果の記録

比較結果を記録して、今後の参考にする：

```
## Depth API比較結果 (YYYY-MM-DD)

### Raw Depth API
- ジョブID: 0a89490c
- 解像度: 160x90
- 有効ピクセル: 0.4%
- メッシュ品質: [評価]

### Depth API（通常）
- ジョブID: <depth_api_job_id>
- 解像度: ?x?
- 有効ピクセル: ?%
- メッシュ品質: [評価]

### 結論
[どちらを選択したか、理由]

```

---

## 参考: 期待される結果

### 理想的なDepth API（通常）の結果

- 解像度: 320x240以上
- 有効ピクセル: 10-30%以上
- 標準偏差: < 1.0m
- ノイズが少ない、安定した品質

### 理想的なRaw Depth APIの結果

- 解像度: 320x240〜640x480
- 有効ピクセル: 20-40%以上（フィルタリング前）、10-20%以上（フィルタリング後）
- 標準偏差: サーバー側フィルタリング後 < 1.5m
- より高解像度、より詳細

---

## 次のステップ

1. ✅ Depth API（通常）で新しいジョブを作成
2. ✅ 診断スクリプトで比較
3. ✅ メッシュ品質を比較
4. ✅ 判断基準に基づいて選択
5. ✅ 設定を最適化

最終更新: 2026-01-08 10:23:00
---

# Depth API比較チェックリスト

## 目的

Raw Depth APIとDepth API（通常）の実際の性能を比較し、どちらが3Dメッシュ生成に適しているかを判断する。

---

## ステップ1: Depth API（通常）で新しいジョブを作成

### Androidアプリ側での変更

**変更前（Raw Depth API）:**
```kotlin
val rawDepthImage = frame.acquireRawDepthImage()
```

**変更後（Depth API）:**
```kotlin
val depthImage = frame.acquireDepthImage()
```

### データアップロード

1. Androidアプリで同じシーンをスキャン
2. サーバーにアップロード
3. ジョブIDを記録（例: `depth_api_job_id`）

---

## ステップ2: 診断スクリプトで比較

### Raw Depth APIの結果（既存）

```bash
python diagnose_depth.py 0a89490c
```

**結果:**
- 解像度: 160x90
- 有効ピクセル: 0.4%
- 99th percentile: 6.99m

### Depth API（通常）の結果

```bash
python diagnose_depth.py <depth_api_job_id>
```

**確認項目:**
- [ ] 解像度（width x height）
- [ ] 有効ピクセル率（valid_ratio %）
- [ ] 無効値マーカー率（invalid_ratio %）
- [ ] 深度範囲（min - max m）
- [ ] 99th percentile（m）
- [ ] 標準偏差（std dev m）

---

## ステップ3: 比較表を作成

| 項目 | Raw Depth API | Depth API（通常） | 良い方 |
|------|---------------|-------------------|--------|
| **解像度** | 160x90 | ?x? | ? |
| **有効ピクセル率** | 0.4% | ?% | ? |
| **無効値マーカー率** | 99.6% | ?% | ? |
| **深度範囲（min）** | 2.00m | ?m | - |
| **深度範囲（max）** | 16.00m | ?m | - |
| **99th percentile** | 6.99m | ?m | - |
| **標準偏差** | 0.804m | ?m | Depth API |
| **推奨depth_trunc** | 7.0m | ?m | - |

---

## ステップ4: メッシュ品質を比較

### 両方のジョブでメッシュを生成

```bash
# Raw Depth APIのメッシュ（既存）
python regenerate_mesh.py 0a89490c existing

# Depth API（通常）のメッシュ
python regenerate_mesh.py <depth_api_job_id> existing
```

### 比較項目

- [ ] **メッシュの三角形数**
  - Raw Depth API: ?
  - Depth API: ?
  
- [ ] **メッシュの頂点数**
  - Raw Depth API: ?
  - Depth API: ?

- [ ] **視覚的な品質**
  - 波打ちの有無
  - ノイズの量
  - 詳細の保持
  - 滑らかさ

- [ ] **ファイルサイズ**
  - Raw Depth API: ?MB
  - Depth API: ?MB

---

## ステップ5: 判断基準

### Depth API（通常）を選択する場合

✅ **条件:**
- 解像度がRaw Depth APIと同じか高い（320x240以上）
- 有効ピクセルが10%以上
- 標準偏差が低い（ノイズが少ない、< 1.0m）
- メッシュ品質が良い（波打ちが少ない、詳細が保持されている）

**理由:**
- ARCoreのフィルタリングが有効
- サーバー側の前処理が不要（または軽減）
- より安定した品質

### Raw Depth APIを選択する場合

✅ **条件:**
- 解像度がDepth APIより高い（320x240以上）
- 有効ピクセルが10%以上（サーバー側フィルタリング後）
- サーバー側で適切にフィルタリング可能
- メッシュ品質が良い（より詳細、より滑らか）

**理由:**
- より高解像度
- より多くの情報
- サーバー側で柔軟に処理可能

---

## ステップ6: 設定の最適化

### Depth API（通常）を選択した場合

**推奨設定変更:**
```yaml
processing:
  depth:
    # Depth APIは既にフィルタリング済みのため、前処理を軽減
    filter_noise: false  # ARCoreが既に実施済み
    bilateral_filter: false  # ARCoreが既に実施済み
    # または、より軽いフィルタリング
    bilateral_sigma_color: 30.0  # デフォルトより軽く
    bilateral_sigma_space: 30.0
```

### Raw Depth APIを選択した場合

**推奨設定（現在の設定を維持）:**
```yaml
processing:
  depth:
    trunc: 7.0  # 診断結果に基づく
    filter_noise: true  # 必要
    bilateral_filter: true  # 必要
```

---

## ステップ7: 結果の記録

比較結果を記録して、今後の参考にする：

```
## Depth API比較結果 (YYYY-MM-DD)

### Raw Depth API
- ジョブID: 0a89490c
- 解像度: 160x90
- 有効ピクセル: 0.4%
- メッシュ品質: [評価]

### Depth API（通常）
- ジョブID: <depth_api_job_id>
- 解像度: ?x?
- 有効ピクセル: ?%
- メッシュ品質: [評価]

### 結論
[どちらを選択したか、理由]

```

---

## 参考: 期待される結果

### 理想的なDepth API（通常）の結果

- 解像度: 320x240以上
- 有効ピクセル: 10-30%以上
- 標準偏差: < 1.0m
- ノイズが少ない、安定した品質

### 理想的なRaw Depth APIの結果

- 解像度: 320x240〜640x480
- 有効ピクセル: 20-40%以上（フィルタリング前）、10-20%以上（フィルタリング後）
- 標準偏差: サーバー側フィルタリング後 < 1.5m
- より高解像度、より詳細

---

## 次のステップ

1. ✅ Depth API（通常）で新しいジョブを作成
2. ✅ 診断スクリプトで比較
3. ✅ メッシュ品質を比較
4. ✅ 判断基準に基づいて選択
5. ✅ 設定を最適化