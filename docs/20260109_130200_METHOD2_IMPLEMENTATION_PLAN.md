# 方式2: COLMAP pose_prior による実装

**作成日時:** 2026-01-09 13:02:00  
**更新日時:** 2026-01-09 15:15:00  
**ステータス:** ✅ 実装完了、検証済み

---

## 1. 概要

ARCoreのポーズ情報を`pose_priors`テーブルに挿入し、`pose_prior_mapper`を使用してSfMを実行する方式。

### 実装状態

| 項目 | 状態 |
|------|------|
| pose_priors挿入 | ✅ 完了 |
| pose_prior_mapper実行 | ✅ 完了 |
| 座標変換（COLMAP→ARCore） | ✅ 完了 |
| config.yaml設定 | ✅ 完了 |
| テスト実行 | ✅ 完了 |

### 設定方法

```yaml
# config.yaml
colmap:
  use_pose_priors: true  # 方式2を有効化
  pose_prior:
    position_std_x: 0.1  # ARCore位置の標準偏差（10cm）
    position_std_y: 0.1
    position_std_z: 0.1
    use_robust_loss: true
```

---

## 2. 検証結果（2026-01-09 15:10）

### テストジョブ: `6d24a96e_method2_20260109_135750`

| 項目 | 値 |
|------|-----|
| 挿入ポーズ数 | 294 |
| 登録画像数 | 262/294 (89%) |
| 点群 | 168,726点 |
| メッシュ頂点 | 428,850 |
| メッシュ三角形 | 854,449 |

### 座標変換パラメータ

| パラメータ | 値 |
|-----------|-----|
| スケール係数 | 0.118 |
| 平均誤差 | 0.55m |
| 中央値誤差 | 0.43m |
| スケール比（変換後） | 1.69x |

### ユーザー評価

> "見た目のメッシュは方式2のほうが少し綺麗です。軌跡もそこまでずれていない。"

---

## 3. 方式比較

| 方式 | メッシュ品質 | 軌跡精度 | 処理時間 | 設定 |
|------|------------|---------|---------|------|
| **方式2** | ✅ 綺麗 | 0.55m | 約6分 | `use_pose_priors: true` |
| 方式3改良 | 若干歪み | **0.14m** | 数秒 | `use_pose_priors: false` |

### 長所・短所

#### 方式2の長所 ✅
1. **メッシュが綺麗** - COLMAPがARCore拘束付きで最適化
2. **歪みなし** - セグメント補正による不連続がない
3. **一貫性** - 最初からARCore座標系に近い形で生成

#### 方式2の短所 ❌
1. **スケール精度** - 1.69xのずれが残る
2. **位置精度** - 0.55m（方式3の0.14mより劣る）
3. **回転情報なし** - pose_priorsに回転は格納不可

---

## 4. 技術詳細

### COLMAPの `pose_priors` テーブル

```sql
CREATE TABLE pose_priors (
    pose_prior_id INTEGER PRIMARY KEY,
    corr_data_id INTEGER,        -- frame_dataへの参照
    corr_sensor_id INTEGER,      -- センサーID
    corr_sensor_type INTEGER,    -- センサータイプ
    position BLOB,               -- 位置情報 (3x float64)
    position_covariance BLOB,    -- 共分散行列 (3x3 float64)
    gravity BLOB,                -- 重力方向 (3x float64)
    coordinate_system INTEGER    -- 座標系タイプ
);
```

### 実装コード（`pipeline/colmap_mvs.py`）

```python
def _insert_pose_priors(self, parser, database_path):
    """ARCoreのポーズをpose_priorsテーブルに挿入"""
    # ARCore座標系 → COLMAP座標系の変換
    # ARCore: Y軸上向き、Z軸後方
    # COLMAP: Y軸下向き、Z軸前方
    colmap_position = [
        float(position[0]),      # X: 同じ
        float(-position[1]),     # Y: 反転
        float(-position[2])      # Z: 反転
    ]
    # ... 挿入処理
```

### `pose_prior_mapper` コマンド

```bash
colmap pose_prior_mapper \
    --database_path colmap/database.db \
    --image_path images/ \
    --output_path colmap/sparse \
    --prior_position_std_x 0.1 \
    --prior_position_std_y 0.1 \
    --prior_position_std_z 0.1 \
    --use_robust_loss_on_prior_position 1 \
    --overwrite_priors_covariance 1
```

---

## 5. 使い分けの指針

| 優先事項 | 推奨方式 |
|---------|---------|
| **メッシュの見た目** | 方式2 |
| **RFIDタグ位置精度** | 方式3改良 |
| **処理速度** | 方式3改良 |
| **歪みのないメッシュ** | 方式2 |

### 推奨ワークフロー

1. **メッシュ可視化用**: 方式2（`use_pose_priors: true`）
2. **RFID位置測定用**: 方式3改良（`use_pose_priors: false` + `use_arcore_rotation: true`）

---

## 6. Viewerで確認

| Job ID | 方式 | URL |
|--------|------|-----|
| 6d24a96e_method2_* | 方式2 | http://localhost:8002/viewer?job=6d24a96e_method2_20260109_135750 |
| 6d24a96e_2sec_rot | 方式3改良 | http://localhost:8002/viewer?job=6d24a96e_2sec_rot |

---

## 7. 今後の改善案

1. **position_std の最適化** - より小さい値（0.05m）でテスト
2. **ハイブリッド方式** - 方式2でメッシュ生成 + 方式3で軌跡補正
3. **回転情報の別経路追加** - 軌跡JSONにARCore回転を追加（実装済み）
