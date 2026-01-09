# 方式2: COLMAP pose_prior による実装計画

**作成日時:** 2026-01-09 13:02:00  
**ステータス:** 調査完了、未実装

---

## 1. 重要な発見

### COLMAPには `pose_priors` テーブルが存在

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

### `pose_prior_mapper` コマンド

```bash
colmap pose_prior_mapper \
    --database_path <db> \
    --image_path <images> \
    --input_path <sparse> \
    --output_path <output> \
    --prior_position_std_x 0.1 \  # 位置の標準偏差（メートル）
    --prior_position_std_y 0.1 \
    --prior_position_std_z 0.1
```

---

## 2. 実装手順（案）

### Step 1: ARCoreポーズをpose_priorsに挿入

```python
import sqlite3
import struct
import numpy as np

def add_pose_priors(db_path, arcore_poses):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 画像IDとframe_dataのマッピングを取得
    cursor.execute("""
        SELECT i.image_id, i.name, fd.data_id
        FROM images i
        JOIN frame_data fd ON fd.data_id = i.image_id
    """)
    image_mapping = {row[1]: (row[0], row[2]) for row in cursor.fetchall()}
    
    for image_name, pose in arcore_poses.items():
        if image_name not in image_mapping:
            continue
        
        image_id, data_id = image_mapping[image_name]
        position = pose['position']  # [x, y, z]
        
        # 位置をBLOB形式に変換
        position_blob = struct.pack('ddd', *position)
        
        # 共分散行列（単位行列 * 0.01 = 10cm標準偏差）
        cov = np.eye(3) * 0.01
        cov_blob = struct.pack('d'*9, *cov.flatten())
        
        # 重力方向（Y軸下向き）
        gravity = [0, -1, 0]
        gravity_blob = struct.pack('ddd', *gravity)
        
        cursor.execute("""
            INSERT INTO pose_priors 
            (corr_data_id, corr_sensor_id, corr_sensor_type, 
             position, position_covariance, gravity, coordinate_system)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (data_id, 1, 0, position_blob, cov_blob, gravity_blob, 0))
    
    conn.commit()
    conn.close()
```

### Step 2: pose_prior_mapper を実行

```bash
# 通常のmapperの代わりにpose_prior_mapperを使用
colmap pose_prior_mapper \
    --database_path colmap/database.db \
    --image_path images/ \
    --output_path colmap/sparse \
    --prior_position_std_x 0.1 \
    --prior_position_std_y 0.1 \
    --prior_position_std_z 0.1 \
    --Mapper.ba_refine_focal_length 0
```

### Step 3: 通常のMVSパイプライン

```bash
# Image Undistorter
colmap image_undistorter ...

# Patch Match Stereo
colmap patch_match_stereo ...

# Stereo Fusion
colmap stereo_fusion ...
```

---

## 3. 座標系変換

### ARCore → COLMAP 座標変換

| | ARCore | COLMAP |
|--|--------|--------|
| X軸 | 右 | 右 |
| Y軸 | **上** | **下** |
| Z軸 | 後ろ | 前 |
| 単位 | メートル | メートル（priorの場合） |

```python
def arcore_to_colmap_position(arcore_pos):
    """ARCore位置をCOLMAP座標系に変換"""
    x, y, z = arcore_pos
    return [x, -y, -z]  # Y軸とZ軸を反転
```

---

## 4. 期待される利点

1. **メッシュが歪まない** - 最初からARCore座標系で生成
2. **軌跡が一致** - ARCoreポーズを拘束条件として使用
3. **精度向上** - Bundle Adjustmentで最適化されつつARCoreに近い結果

---

## 5. 潜在的な問題

### 問題1: position_covariance の設定

ARCoreの位置精度に応じた共分散を設定する必要がある。

- **小さすぎる** → ARCoreの誤差を伝播、悪影響
- **大きすぎる** → priorが無視される

**推奨:** σ = 0.05〜0.1m（5〜10cm）

### 問題2: coordinate_system の値

COLMAPのソースコードを確認して正しい値を設定する必要がある。

```cpp
enum class CoordinateSystem {
    UNDEFINED = 0,
    WGS84 = 1,  // GPS用
    // ...
};
```

### 問題3: 回転情報

`pose_priors`テーブルには回転（向き）の列がない。
位置のみの拘束で十分か検証が必要。

---

## 6. 実装の優先度

| 項目 | 優先度 | 理由 |
|------|--------|------|
| pose_priors挿入 | 高 | コア機能 |
| 座標変換 | 高 | 必須 |
| 共分散設定 | 中 | チューニング |
| エラー処理 | 中 | 安定性 |
| 回転対応 | 低 | 位置のみで十分な可能性 |

---

## 7. 次のステップ

1. [ ] pose_priorsテーブルへの挿入コードを実装
2. [ ] 小規模データでテスト
3. [ ] pose_prior_mapperの動作確認
4. [ ] 6d24a96eデータで検証
5. [ ] 方式3との比較

---

## 8. 参考コマンド

```bash
# pose_prior_mapperのオプション確認
colmap pose_prior_mapper --help

# データベースの内容確認
sqlite3 database.db "SELECT * FROM pose_priors LIMIT 5"
```

