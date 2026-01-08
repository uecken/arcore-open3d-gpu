# COLMAP特徴点要件の問題と解決策

**作成日時**: 2026-01-08 12:40  
**更新日時**: 2026-01-08 12:40

## 問題の概要

COLMAPのPatch Match Stereoが空の深度マップを生成し、すべての画像が「no source images」として無視されています。

### エラーログ

```
W20260108 12:36:51.340641 24449 patch_match.cc:357] Ignoring reference image frame_..., because it has no source images.
I20260108 12:36:51.341162 24449 patch_match.cc:366] Configuration has 0 problems...
```

### 根本原因

COLMAPのPatch Match Stereoは、**sparse reconstruction（特徴点）から一貫性グラフ（consistency graph）を構築**します：

1. **一貫性グラフとは**: どの画像が他のどの画像と視覚的に重複しているかを示すグラフ
2. **構築方法**: 2D特徴点→3D点の対応関係から、画像間の視覚的重複を推論
3. **現在の問題**: `points3D.txt`が空（特徴点なし）のため、一貫性グラフが構築できない

## 現在の実装の問題

現在の実装では、ARCore VIOポーズから直接COLMAPモデルを作成していますが、**特徴点情報が欠如**しています：

```
- cameras.txt: ✅ カメラ内部パラメータ（正常）
- images.txt: ✅ カメラポーズと画像ファイル名（正常）
- points3D.txt: ❌ 空（特徴点なし = 一貫性グラフが構築できない）
```

## 解決策

### 解決策1: COLMAPの特徴点抽出とマッチングを実行（推奨）

ARCoreポーズを初期値として使用し、COLMAPで特徴点抽出→マッチング→バンドル調整を実行します。

**手順:**
1. **特徴点抽出**（feature_extractor）
   ```bash
   colmap feature_extractor \
     --database_path database.db \
     --image_path images/ \
     --ImageReader.camera_model PINHOLE \
     --ImageReader.camera_params fx,fy,cx,cy
   ```

2. **特徴点マッチング**（exhaustive_matcher または sequential_matcher）
   ```bash
   colmap exhaustive_matcher \
     --database_path database.db
   ```

3. **バンドル調整**（point_triangulator + bundle_adjuster）
   - ARCoreポーズを初期値として使用
   - 特徴点を3D点として三角測量

4. **Dense MVS**（image_undistorter → patch_match_stereo → stereo_fusion）

**メリット:**
- ✅ 一貫性グラフが正しく構築される
- ✅ ARCoreポーズを初期値として使用（精度向上）
- ✅ 特徴点の品質が向上

**デメリット:**
- ⚠️ 処理時間が増加（特徴点抽出＋マッチング＋バンドル調整）
- ⚠️ SfMと同等の処理が必要

### 解決策2: 近接フレーム間で手動一貫性グラフを構築

ARCoreポーズから、時間的に近接しているフレーム間で視覚的重複を推測し、手動で一貫性グラフを構築します。

**手順:**
1. フレーム間の距離と向きを計算
2. 近接フレーム（距離 < 0.5m、角度差 < 30度）を「source images」として設定
3. ダミーの特徴点を追加（実際の特徴点抽出は不要）

**メリット:**
- ✅ 処理が高速
- ✅ SfMを完全にスキップ可能

**デメリット:**
- ⚠️ 一貫性グラフの精度が低い
- ⚠️ 実際の視覚的重複と一致しない可能性

### 解決策3: RGBDパイプラインに戻る（暫定的）

MVSパイプラインの問題が解決するまで、RGBDパイプラインを使用します。

**メリット:**
- ✅ すぐに動作する
- ✅ ARCore Depth APIまたはMiDaS深度推定を使用可能

**デメリット:**
- ❌ MVSパイプラインの恩恵を受けられない
- ❌ テクスチャマッピングができない

## 推奨アプローチ

**解決策1を推奨**します。理由：

1. **品質が最も高い**: 一貫性グラフが正しく構築され、MVSパイプラインの真価を発揮できる
2. **ARCoreポーズの活用**: 初期値として使用することで、処理時間と精度のバランスが取れる
3. **将来の拡張性**: テクスチャマッピングなど、他のCOLMAP機能を活用できる

## 実装方法

### ステップ1: 特徴点抽出

```python
def run_feature_extractor(self, session_dir: Path, database_path: Path, intrinsics: CameraIntrinsics) -> bool:
    """COLMAPの特徴点抽出を実行"""
    images_dir = session_dir / "images"
    
    result = subprocess.run([
        self.colmap_path, "feature_extractor",
        "--database_path", str(database_path),
        "--image_path", str(images_dir),
        "--ImageReader.camera_model", "PINHOLE",
        "--ImageReader.camera_params", f"{intrinsics.fx},{intrinsics.fy},{intrinsics.cx},{intrinsics.cy}",
        "--SiftExtraction.use_gpu", "true" if self.use_gpu else "false"
    ], capture_output=True, text=True)
    
    return result.returncode == 0
```

### ステップ2: 特徴点マッチング

```python
def run_exhaustive_matcher(self, database_path: Path) -> bool:
    """COLMAPのexhaustive matcherを実行"""
    result = subprocess.run([
        self.colmap_path, "exhaustive_matcher",
        "--database_path", str(database_path),
        "--SiftMatching.use_gpu", "true" if self.use_gpu else "false"
    ], capture_output=True, text=True)
    
    return result.returncode == 0
```

### ステップ3: バンドル調整（ARCoreポーズを初期値として使用）

```python
def run_bundle_adjustment_with_arcore_poses(
    self, 
    colmap_dir: Path, 
    parser: ARCoreDataParser,
    database_path: Path
) -> bool:
    """ARCoreポーズを初期値としてバンドル調整を実行"""
    # 1. ARCoreポーズからCOLMAPモデルを作成（既存の実装）
    # 2. 特徴点マッチング結果を統合
    # 3. バンドル調整を実行
    
    result = subprocess.run([
        self.colmap_path, "bundle_adjuster",
        "--input_path", str(colmap_dir / "sparse" / "0"),
        "--output_path", str(colmap_dir / "sparse" / "0"),
        "--database_path", str(database_path)
    ], capture_output=True, text=True)
    
    return result.returncode == 0
```

## 次のステップ

1. **解決策1を実装**: 特徴点抽出→マッチング→バンドル調整のパイプラインを追加
2. **テスト**: 既存データで動作確認
3. **パフォーマンス測定**: 処理時間と品質を評価

