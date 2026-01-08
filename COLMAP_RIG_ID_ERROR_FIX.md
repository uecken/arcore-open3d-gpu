# COLMAP Rig ID エラーの解決策

**作成日時**: 2026-01-08 13:00  
**更新日時**: 2026-01-08 13:00

## 問題

COLMAPの`point_triangulator`で以下のエラーが発生：

```
E20260108 12:59:22.214187 26464 reconstruction.cc:339] Check failed: existing_frame.RigId() == frame.RigId()
```

## 原因

COLMAPの`point_triangulator`は、入力のCOLMAPモデル（sparse reconstruction）に含まれる画像のRig情報が一貫していることを期待しています。しかし、我々が作成したCOLMAPモデルには、Rig情報が含まれていないか、または一貫していない可能性があります。

## 解決策

### オプション1: Rig情報を明示的に設定しない（推奨）

COLMAPモデルを作成する際に、すべての画像をrig_id=0（デフォルト）として設定します。

### オプション2: COLMAPのmapperを使用する代わりに、point_triangulatorをスキップ

`point_triangulator`は必須ではありません。特徴点マッチングとARCoreポーズがあれば、直接`image_undistorter`と`patch_match_stereo`を実行できます。

ただし、sparse reconstructionに点が少ない場合、Patch Match Stereoの一貫性グラフが構築できない可能性があります。

### オプション3: COLMAPのmapperを実行する（完全なSfM）

ARCoreポーズを初期値として使用せず、COLMAPのmapperを実行してsparse reconstructionを構築します。

## 推奨アプローチ

**オプション2を推奨**します。理由：

1. **point_triangulatorは必須ではない**: ARCoreポーズがあれば、`image_undistorter`と`patch_match_stereo`を直接実行可能
2. **一貫性グラフ**: Patch Match Stereoは、sparse reconstructionの画像間の対応関係から一貫性グラフを構築しますが、必ずしも3D点が必要ではありません
3. **処理時間**: `point_triangulator`をスキップすることで、処理時間を短縮

ただし、sparse reconstructionに点が少ない場合、Patch Match Stereoの一貫性グラフが正しく構築されない可能性があります。

その場合は、**COLMAPのmapperを実行**して、完全なSfMを行うか、または**近接フレーム間で手動一貫性グラフを構築**する必要があります。

