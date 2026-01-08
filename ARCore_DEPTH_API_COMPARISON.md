# ARCore Depth API比較: Raw Depth API vs Depth API

## 概要

ARCoreには2つのDepth APIがあります：
1. **Depth API**（通常のDepth API）
2. **Raw Depth API**（生の深度データ）

3Dメッシュ生成に最適なAPIを選択するための比較です。

---

## Depth API（通常のDepth API）

### 特徴

- **平滑化済み・フィルタリング済み**の深度データ
- ARCoreが内部でノイズ除去と平滑化を実施
- **解像度が制限される可能性**がある
- 信頼度が高い深度値のみが含まれる

### 取得方法

```kotlin
// Depth API（通常）
val depthImage = frame.acquireDepthImage()

// 深度データの特徴
- 解像度: デバイス依存（通常160x90〜320x240）
- データ品質: フィルタリング済み、平滑化済み
- 無効値: 少ない（信頼度の低い箇所は除外）
```

### メリット

✅ **ノイズが少ない**（ARCoreが既にフィルタリング済み）
✅ **使いやすい**（追加の前処理が不要）
✅ **安定した品質**

### デメリット

❌ **解像度が低い可能性**（160x90など）
❌ **有効ピクセルが少ない**（信頼度の低い箇所を除外）
❌ **詳細が失われる可能性**（平滑化で細かい情報が消える）

---

## Raw Depth API（生の深度データ）

### 特徴

- **生の深度データ**（フィルタリング・平滑化なし）
- **より高解像度**の可能性がある
- **すべての深度値**が含まれる（信頼度が低いものも含む）
- **サーバー側でカスタムフィルタリング**が可能

### 取得方法

```kotlin
// Raw Depth API（生データ）
val rawDepthImage = frame.acquireRawDepthImage()

// 深度データの特徴
- 解像度: デバイス依存（通常320x240〜640x480、Depth Camera搭載デバイスではより高解像度）
- データ品質: 生データ、ノイズが多い
- 無効値: 多い（信頼度の低い箇所も含まれる）
```

### メリット

✅ **より高解像度**（320x240〜640x480など）
✅ **より多くの有効ピクセル**（信頼度の低い箇所も含まれる）
✅ **サーバー側でカスタムフィルタリング可能**（要件に合わせて調整）
✅ **詳細情報が保持される**（平滑化で失われない）

### デメリット

❌ **ノイズが多い**（サーバー側でフィルタリングが必要）
❌ **無効値が多い**（サーバー側で処理が必要）
❌ **前処理が必要**（bilateral filter、inpaintingなど）

---

## 3Dメッシュ生成への影響

### 現在の状況

診断結果：
- **深度解像度: 160x90** (14,400ピクセル)
- **有効ピクセル: 0.4%** (99.6%が無効値)
- **非常に低い解像度と有効ピクセル率**

### Depth API（通常）を使用している場合

**問題:**
- 解像度が低い（160x90）
- 有効ピクセルが少ない（0.4%）
- ARCoreのフィルタリングが厳しすぎる可能性

**対処法:**
- ARCoreのフィルタリング設定を緩和（可能な場合）
- Depth APIの解像度設定を確認

### Raw Depth APIを使用している場合

**利点:**
- より高解像度の可能性（320x240〜640x480）
- より多くの有効ピクセル（信頼度の低い箇所も含まれる）
- サーバー側で適切にフィルタリング可能

**必要な処理:**
- Bilateral filter（エッジ保持平滑化）
- 無効値の除去（65m以上のマーカー）
- 穴埋め（inpainting）

---

## 推奨: Raw Depth APIを使用

### 理由

1. **より高解像度**
   - Depth API: 160x90程度
   - Raw Depth API: 320x240〜640x480程度
   - **4倍〜16倍の解像度向上**

2. **より多くの有効ピクセル**
   - Depth API: ARCoreが厳しくフィルタリング（有効ピクセル0.4%）
   - Raw Depth API: より多くのピクセルが利用可能（適切なフィルタリングで10-30%以上）

3. **サーバー側での柔軟な処理**
   - サーバー側で要件に合わせてフィルタリング
   - 既存の`bilateral_filter`、`filter_noise`設定が活用可能
   - 診断結果に基づいて最適化可能

4. **既存のインフラが活用可能**
   - 既に`config.yaml`で深度前処理が設定済み
   - 診断スクリプトで品質を確認可能

### 実装例（Kotlin）

```kotlin
// Raw Depth APIを使用
fun processFrame(frame: ArFrame) {
    // Raw Depth Imageを取得
    val rawDepthImage = frame.acquireRawDepthImage()
    
    if (rawDepthImage != null) {
        val width = rawDepthImage.width
        val height = rawDepthImage.height
        
        Log.d(TAG, "Raw depth resolution: ${width}x${height}")
        
        // 深度データを保存
        saveRawDepthImage(rawDepthImage, frame.timestamp)
        
        rawDepthImage.close()
    }
    
    // 比較のため、通常のDepth APIも取得してログ出力
    val depthImage = frame.acquireDepthImage()
    if (depthImage != null) {
        Log.d(TAG, "Regular depth resolution: ${depthImage.width}x${depthImage.height}")
        depthImage.close()
    }
}
```

### サーバー側での処理

既存の`config.yaml`設定が活用できます：

```yaml
processing:
  depth:
    trunc: 7.0          # 無効値マーカー（65m以上）を除外
    filter_noise: true  # 統計的外れ値除去
    bilateral_filter: true  # エッジ保持平滑化
```

---

## 実装チェックリスト

### Androidアプリ側

1. **Raw Depth APIに切り替え**
   ```kotlin
   // Depth API → Raw Depth API
   val rawDepthImage = frame.acquireRawDepthImage()
   ```

2. **解像度を確認**
   ```kotlin
   Log.d(TAG, "Raw depth: ${rawDepthImage.width}x${rawDepthImage.height}")
   ```

3. **データを保存**
   - 既存の`.raw`ファイル形式と同じ形式で保存
   - または、解像度情報を追加

### サーバー側

1. **設定を確認**
   ```yaml
   depth:
     trunc: 7.0  # 無効値マーカーを除外
     filter_noise: true
     bilateral_filter: true
   ```

2. **診断スクリプトで確認**
   ```bash
   python diagnose_depth.py <job_id>
   ```

3. **期待される改善**
   - 解像度: 160x90 → 320x240以上
   - 有効ピクセル: 0.4% → 10-30%以上

---

## 比較表

| 項目 | Depth API（通常） | Raw Depth API |
|------|------------------|---------------|
| **解像度** | 低い（160x90など） | 高い（320x240〜640x480） |
| **有効ピクセル** | 少ない（0.4%） | 多い（10-30%以上、フィルタリング後） |
| **ノイズ** | 少ない（ARCoreがフィルタリング済み） | 多い（サーバー側でフィルタリング必要） |
| **データ品質** | 平滑化済み | 生データ（詳細保持） |
| **前処理** | 不要 | 必要（bilateral filter等） |
| **柔軟性** | 低い | 高い（サーバー側でカスタマイズ可能） |
| **3Dメッシュ品質** | 限定的（解像度・有効ピクセルの制約） | 高い（解像度・有効ピクセルの利点） |

---

## 結論

### 推奨: **Raw Depth APIを使用**

**理由:**
1. ✅ **より高解像度**（4倍〜16倍の向上が期待できる）
2. ✅ **より多くの有効ピクセル**（10-30%以上が期待できる）
3. ✅ **サーバー側で適切にフィルタリング可能**（既存設定を活用）
4. ✅ **現在の低解像度・低有効ピクセル問題を解決可能**

**必要な対応:**
- Androidアプリ側: `acquireDepthImage()` → `acquireRawDepthImage()`に変更
- サーバー側: 既存の`config.yaml`設定で対応可能（`bilateral_filter`、`filter_noise`）

現在のDepth APIでは解像度160x90、有効ピクセル0.4%と非常に低いため、**Raw Depth APIに切り替えることで大幅な改善が期待できます**。

---

## 参考資料

- [ARCore Depth API Documentation](https://developers.google.com/ar/develop/java/depth)
- [ARCore Raw Depth API](https://developers.google.com/ar/develop/java/depth#raw-depth)
- [ARCore Depth API Best Practices](https://developers.google.com/ar/develop/java/depth#best-practices)

