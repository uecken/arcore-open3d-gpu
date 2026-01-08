---
作成日時: 2026-01-08 10:14:57
最終更新: 2026-01-08 10:14:57
---

# Android側でのDepth解像度向上ガイド

## 現状の問題

診断結果から以下の問題が判明：
- **深度解像度: 160x90** (14,400ピクセル) - 非常に低い
- **有効深度ピクセル: 0.4%** (99.6%が無効値マーカー)
- これはARCore Depth APIの**デフォルト解像度**で、明示的に解像度を指定していない可能性が高い

## ARCore Depth APIの解像度設定

### ARCore Depth APIの解像度オプション

ARCore Depth APIでは、`ArCameraConfig`または`ArSession`で深度解像度を設定できます。

#### 1. カメラ設定での解像度指定（推奨）

```java
// ARCore Depth APIの解像度を設定
ArSession session = new ArSession(context);

// カメラ設定を取得
ArCameraConfigFilter filter = new ArCameraConfigFilter(session);
ArCameraConfigList configList = session.getSupportedCameraConfigs(filter);

// 深度解像度が高い設定を選択
ArCameraConfig bestConfig = null;
int maxDepthSize = 0;
for (ArCameraConfig config : configList) {
    ArCameraConfig.DepthSensorUsage usage = config.getDepthSensorUsage();
    
    // 深度解像度を確認（直接取得できない場合、ターミナル解像度から推測）
    // より高い解像度の設定を選択
    int depthWidth = config.getImageSize().getWidth();  // 深度は通常カメラ解像度より低い
    if (depthWidth > maxDepthSize) {
        maxDepthSize = depthWidth;
        bestConfig = config;
    }
}

if (bestConfig != null) {
    session.setCameraConfig(bestConfig);
}
```

#### 2. ARCore Sessionの深度設定（直接指定）

```java
// ARCore 1.30以降では、深度解像度をより直接的に制御可能
ArConfig config = new ArConfig(session);
config.setDepthMode(ArConfig.DepthMode.AUTOMATIC);  // または DEPTH_MODE_RAW_DEPTH_ONLY

// 深度解像度の優先順位を設定（利用可能な場合）
// 注意: ARCoreのバージョンによってAPIが異なる可能性があります
```

#### 3. Depth APIでの最大解像度取得

```java
// 利用可能な深度解像度を取得
ArDepthPointCloud depthPointCloud = frame.acquireDepthPointCloud();

// 深度画像の解像度を確認
int depthWidth = depthPointCloud.getWidth();
int depthHeight = depthPointCloud.getHeight();

// より高い解像度が必要な場合、カメラ設定を調整
```

### 実装例（Kotlin/Java）

#### Androidアプリ側での設定

```kotlin
// ARCore Session初期化時に深度解像度を最大にする
fun initializeArCore(context: Context): ArSession? {
    val session = ArSession(context)
    
    try {
        // デフォルト設定を取得
        val defaultConfig = ArConfig(session)
        defaultConfig.depthMode = ArConfig.DepthMode.AUTOMATIC
        
        // サポートされているカメラ設定を確認
        val configFilter = ArCameraConfigFilter(session)
        val configList = session.getSupportedCameraConfigs(configFilter)
        
        // 最大解像度の設定を選択
        var bestConfig: ArCameraConfig? = null
        var maxResolution = 0
        
        for (i in 0 until configList.size) {
            val config = configList[i]
            val imageSize = config.imageSize
            
            // 画像解像度から深度解像度を推測（深度は通常1/4〜1/2）
            val estimatedDepthResolution = imageSize.width * imageSize.height
            
            if (estimatedDepthResolution > maxResolution) {
                maxResolution = estimatedDepthResolution
                bestConfig = config
            }
        }
        
        // 最適な設定を適用
        if (bestConfig != null) {
            session.setCameraConfig(bestConfig)
            Log.d(TAG, "Depth resolution optimized: ${bestConfig.imageSize}")
        }
        
        session.configure(defaultConfig)
        return session
        
    } catch (e: Exception) {
        Log.e(TAG, "ARCore initialization failed", e)
        return null
    }
}
```

#### 深度データ取得時の解像度確認

```kotlin
// フレームごとに深度データを取得
fun processFrame(frame: ArFrame) {
    val depthImage = frame.acquireDepthImage()
    
    if (depthImage != null) {
        val width = depthImage.width
        val height = depthImage.height
        
        Log.d(TAG, "Depth resolution: ${width}x${height}")
        
        // 期待される解像度より低い場合は警告
        if (width < 320 || height < 240) {
            Log.w(TAG, "Low depth resolution detected: ${width}x${height}")
            Log.w(TAG, "Consider adjusting camera config for higher depth resolution")
        }
        
        // 深度データを保存
        saveDepthImage(depthImage, frame.timestamp)
        
        depthImage.close()
    }
}
```

## ARCore Depth解像度の制約

### デバイスによる制約

1. **Depth Camera搭載デバイス** (iPhone 15 Proなど)
   - より高解像度の深度データが取得可能
   - 通常: 256x192, 320x240, 640x480など

2. **推定Depth（Motion Stereo + ML）** (Pixel 7 Proなど)
   - 解像度が制限される（160x90, 256x192など）
   - デバイスの性能とARCoreのバージョンに依存

3. **Depth APIのバージョン**
   - ARCore 1.20以降: より高解像度をサポート
   - 古いバージョン: 解像度が制限される

### 推奨される解像度

- **最小: 256x192** (49,152ピクセル)
- **推奨: 320x240** (76,800ピクセル)
- **理想: 640x480** (307,200ピクセル) - Depth Camera搭載デバイスのみ

現在の160x90 (14,400ピクセル)は**非常に低い**ため、可能な限り向上させる必要があります。

## 実装チェックリスト

### Androidアプリ側での確認事項

1. **ARCore Sessionの設定を確認**
   ```kotlin
   // 現在のカメラ設定を確認
   val currentConfig = session.cameraConfig
   Log.d(TAG, "Current camera config: ${currentConfig.imageSize}")
   ```

2. **利用可能な深度解像度を確認**
   ```kotlin
   // サポートされている設定を確認
   val configList = session.getSupportedCameraConfigs(ArCameraConfigFilter(session))
   for (config in configList) {
       Log.d(TAG, "Available config: ${config.imageSize}")
   }
   ```

3. **深度画像の解像度をログ出力**
   ```kotlin
   val depthImage = frame.acquireDepthImage()
   Log.d(TAG, "Depth image size: ${depthImage.width}x${depthImage.height}")
   ```

### サーバー側での確認

診断スクリプトで確認：
```bash
python diagnose_depth.py <job_id>
```

期待される結果：
- Depth resolution: 320x240以上
- Valid pixels: 10%以上

## 対処法

### 即座に実施可能（サーバー側）

1. **深度前処理の強化**
   - 穴埋め（inpainting）を実装
   - 無効値の補間

2. **TSDFパラメータの調整**
   - `voxel_length`を大きく（0.04m以上）
   - `depth_trunc`を適切に設定（診断結果の99パーセンタイル値）

### 根本的解決（Androidアプリ側）

1. **ARCore Session設定の見直し**
   - カメラ設定で最高解像度を選択
   - Depth APIのバージョンを確認

2. **ARCoreのバージョン更新**
   - 最新バージョンでより高解像度をサポート

3. **Depth Camera搭載デバイスの使用**
   - iPhone 15 Pro / iPad Pro
   - Intel RealSense
   - Azure Kinect

## 参考資料

- [ARCore Depth API Documentation](https://developers.google.com/ar/develop/java/depth)
- [ARCore Camera Configuration](https://developers.google.com/ar/reference/java/com/google/ar/core/ArCameraConfig)

最終更新: 2026-01-08 10:14:57
---

# Android側でのDepth解像度向上ガイド

## 現状の問題

診断結果から以下の問題が判明：
- **深度解像度: 160x90** (14,400ピクセル) - 非常に低い
- **有効深度ピクセル: 0.4%** (99.6%が無効値マーカー)
- これはARCore Depth APIの**デフォルト解像度**で、明示的に解像度を指定していない可能性が高い

## ARCore Depth APIの解像度設定

### ARCore Depth APIの解像度オプション

ARCore Depth APIでは、`ArCameraConfig`または`ArSession`で深度解像度を設定できます。

#### 1. カメラ設定での解像度指定（推奨）

```java
// ARCore Depth APIの解像度を設定
ArSession session = new ArSession(context);

// カメラ設定を取得
ArCameraConfigFilter filter = new ArCameraConfigFilter(session);
ArCameraConfigList configList = session.getSupportedCameraConfigs(filter);

// 深度解像度が高い設定を選択
ArCameraConfig bestConfig = null;
int maxDepthSize = 0;
for (ArCameraConfig config : configList) {
    ArCameraConfig.DepthSensorUsage usage = config.getDepthSensorUsage();
    
    // 深度解像度を確認（直接取得できない場合、ターミナル解像度から推測）
    // より高い解像度の設定を選択
    int depthWidth = config.getImageSize().getWidth();  // 深度は通常カメラ解像度より低い
    if (depthWidth > maxDepthSize) {
        maxDepthSize = depthWidth;
        bestConfig = config;
    }
}

if (bestConfig != null) {
    session.setCameraConfig(bestConfig);
}
```

#### 2. ARCore Sessionの深度設定（直接指定）

```java
// ARCore 1.30以降では、深度解像度をより直接的に制御可能
ArConfig config = new ArConfig(session);
config.setDepthMode(ArConfig.DepthMode.AUTOMATIC);  // または DEPTH_MODE_RAW_DEPTH_ONLY

// 深度解像度の優先順位を設定（利用可能な場合）
// 注意: ARCoreのバージョンによってAPIが異なる可能性があります
```

#### 3. Depth APIでの最大解像度取得

```java
// 利用可能な深度解像度を取得
ArDepthPointCloud depthPointCloud = frame.acquireDepthPointCloud();

// 深度画像の解像度を確認
int depthWidth = depthPointCloud.getWidth();
int depthHeight = depthPointCloud.getHeight();

// より高い解像度が必要な場合、カメラ設定を調整
```

### 実装例（Kotlin/Java）

#### Androidアプリ側での設定

```kotlin
// ARCore Session初期化時に深度解像度を最大にする
fun initializeArCore(context: Context): ArSession? {
    val session = ArSession(context)
    
    try {
        // デフォルト設定を取得
        val defaultConfig = ArConfig(session)
        defaultConfig.depthMode = ArConfig.DepthMode.AUTOMATIC
        
        // サポートされているカメラ設定を確認
        val configFilter = ArCameraConfigFilter(session)
        val configList = session.getSupportedCameraConfigs(configFilter)
        
        // 最大解像度の設定を選択
        var bestConfig: ArCameraConfig? = null
        var maxResolution = 0
        
        for (i in 0 until configList.size) {
            val config = configList[i]
            val imageSize = config.imageSize
            
            // 画像解像度から深度解像度を推測（深度は通常1/4〜1/2）
            val estimatedDepthResolution = imageSize.width * imageSize.height
            
            if (estimatedDepthResolution > maxResolution) {
                maxResolution = estimatedDepthResolution
                bestConfig = config
            }
        }
        
        // 最適な設定を適用
        if (bestConfig != null) {
            session.setCameraConfig(bestConfig)
            Log.d(TAG, "Depth resolution optimized: ${bestConfig.imageSize}")
        }
        
        session.configure(defaultConfig)
        return session
        
    } catch (e: Exception) {
        Log.e(TAG, "ARCore initialization failed", e)
        return null
    }
}
```

#### 深度データ取得時の解像度確認

```kotlin
// フレームごとに深度データを取得
fun processFrame(frame: ArFrame) {
    val depthImage = frame.acquireDepthImage()
    
    if (depthImage != null) {
        val width = depthImage.width
        val height = depthImage.height
        
        Log.d(TAG, "Depth resolution: ${width}x${height}")
        
        // 期待される解像度より低い場合は警告
        if (width < 320 || height < 240) {
            Log.w(TAG, "Low depth resolution detected: ${width}x${height}")
            Log.w(TAG, "Consider adjusting camera config for higher depth resolution")
        }
        
        // 深度データを保存
        saveDepthImage(depthImage, frame.timestamp)
        
        depthImage.close()
    }
}
```

## ARCore Depth解像度の制約

### デバイスによる制約

1. **Depth Camera搭載デバイス** (iPhone 15 Proなど)
   - より高解像度の深度データが取得可能
   - 通常: 256x192, 320x240, 640x480など

2. **推定Depth（Motion Stereo + ML）** (Pixel 7 Proなど)
   - 解像度が制限される（160x90, 256x192など）
   - デバイスの性能とARCoreのバージョンに依存

3. **Depth APIのバージョン**
   - ARCore 1.20以降: より高解像度をサポート
   - 古いバージョン: 解像度が制限される

### 推奨される解像度

- **最小: 256x192** (49,152ピクセル)
- **推奨: 320x240** (76,800ピクセル)
- **理想: 640x480** (307,200ピクセル) - Depth Camera搭載デバイスのみ

現在の160x90 (14,400ピクセル)は**非常に低い**ため、可能な限り向上させる必要があります。

## 実装チェックリスト

### Androidアプリ側での確認事項

1. **ARCore Sessionの設定を確認**
   ```kotlin
   // 現在のカメラ設定を確認
   val currentConfig = session.cameraConfig
   Log.d(TAG, "Current camera config: ${currentConfig.imageSize}")
   ```

2. **利用可能な深度解像度を確認**
   ```kotlin
   // サポートされている設定を確認
   val configList = session.getSupportedCameraConfigs(ArCameraConfigFilter(session))
   for (config in configList) {
       Log.d(TAG, "Available config: ${config.imageSize}")
   }
   ```

3. **深度画像の解像度をログ出力**
   ```kotlin
   val depthImage = frame.acquireDepthImage()
   Log.d(TAG, "Depth image size: ${depthImage.width}x${depthImage.height}")
   ```

### サーバー側での確認

診断スクリプトで確認：
```bash
python diagnose_depth.py <job_id>
```

期待される結果：
- Depth resolution: 320x240以上
- Valid pixels: 10%以上

## 対処法

### 即座に実施可能（サーバー側）

1. **深度前処理の強化**
   - 穴埋め（inpainting）を実装
   - 無効値の補間

2. **TSDFパラメータの調整**
   - `voxel_length`を大きく（0.04m以上）
   - `depth_trunc`を適切に設定（診断結果の99パーセンタイル値）

### 根本的解決（Androidアプリ側）

1. **ARCore Session設定の見直し**
   - カメラ設定で最高解像度を選択
   - Depth APIのバージョンを確認

2. **ARCoreのバージョン更新**
   - 最新バージョンでより高解像度をサポート

3. **Depth Camera搭載デバイスの使用**
   - iPhone 15 Pro / iPad Pro
   - Intel RealSense
   - Azure Kinect

## 参考資料

- [ARCore Depth API Documentation](https://developers.google.com/ar/develop/java/depth)
- [ARCore Camera Configuration](https://developers.google.com/ar/reference/java/com/google/ar/core/ArCameraConfig)

最終更新: 2026-01-08 10:14:57
---

# Android側でのDepth解像度向上ガイド

## 現状の問題

診断結果から以下の問題が判明：
- **深度解像度: 160x90** (14,400ピクセル) - 非常に低い
- **有効深度ピクセル: 0.4%** (99.6%が無効値マーカー)
- これはARCore Depth APIの**デフォルト解像度**で、明示的に解像度を指定していない可能性が高い

## ARCore Depth APIの解像度設定

### ARCore Depth APIの解像度オプション

ARCore Depth APIでは、`ArCameraConfig`または`ArSession`で深度解像度を設定できます。

#### 1. カメラ設定での解像度指定（推奨）

```java
// ARCore Depth APIの解像度を設定
ArSession session = new ArSession(context);

// カメラ設定を取得
ArCameraConfigFilter filter = new ArCameraConfigFilter(session);
ArCameraConfigList configList = session.getSupportedCameraConfigs(filter);

// 深度解像度が高い設定を選択
ArCameraConfig bestConfig = null;
int maxDepthSize = 0;
for (ArCameraConfig config : configList) {
    ArCameraConfig.DepthSensorUsage usage = config.getDepthSensorUsage();
    
    // 深度解像度を確認（直接取得できない場合、ターミナル解像度から推測）
    // より高い解像度の設定を選択
    int depthWidth = config.getImageSize().getWidth();  // 深度は通常カメラ解像度より低い
    if (depthWidth > maxDepthSize) {
        maxDepthSize = depthWidth;
        bestConfig = config;
    }
}

if (bestConfig != null) {
    session.setCameraConfig(bestConfig);
}
```

#### 2. ARCore Sessionの深度設定（直接指定）

```java
// ARCore 1.30以降では、深度解像度をより直接的に制御可能
ArConfig config = new ArConfig(session);
config.setDepthMode(ArConfig.DepthMode.AUTOMATIC);  // または DEPTH_MODE_RAW_DEPTH_ONLY

// 深度解像度の優先順位を設定（利用可能な場合）
// 注意: ARCoreのバージョンによってAPIが異なる可能性があります
```

#### 3. Depth APIでの最大解像度取得

```java
// 利用可能な深度解像度を取得
ArDepthPointCloud depthPointCloud = frame.acquireDepthPointCloud();

// 深度画像の解像度を確認
int depthWidth = depthPointCloud.getWidth();
int depthHeight = depthPointCloud.getHeight();

// より高い解像度が必要な場合、カメラ設定を調整
```

### 実装例（Kotlin/Java）

#### Androidアプリ側での設定

```kotlin
// ARCore Session初期化時に深度解像度を最大にする
fun initializeArCore(context: Context): ArSession? {
    val session = ArSession(context)
    
    try {
        // デフォルト設定を取得
        val defaultConfig = ArConfig(session)
        defaultConfig.depthMode = ArConfig.DepthMode.AUTOMATIC
        
        // サポートされているカメラ設定を確認
        val configFilter = ArCameraConfigFilter(session)
        val configList = session.getSupportedCameraConfigs(configFilter)
        
        // 最大解像度の設定を選択
        var bestConfig: ArCameraConfig? = null
        var maxResolution = 0
        
        for (i in 0 until configList.size) {
            val config = configList[i]
            val imageSize = config.imageSize
            
            // 画像解像度から深度解像度を推測（深度は通常1/4〜1/2）
            val estimatedDepthResolution = imageSize.width * imageSize.height
            
            if (estimatedDepthResolution > maxResolution) {
                maxResolution = estimatedDepthResolution
                bestConfig = config
            }
        }
        
        // 最適な設定を適用
        if (bestConfig != null) {
            session.setCameraConfig(bestConfig)
            Log.d(TAG, "Depth resolution optimized: ${bestConfig.imageSize}")
        }
        
        session.configure(defaultConfig)
        return session
        
    } catch (e: Exception) {
        Log.e(TAG, "ARCore initialization failed", e)
        return null
    }
}
```

#### 深度データ取得時の解像度確認

```kotlin
// フレームごとに深度データを取得
fun processFrame(frame: ArFrame) {
    val depthImage = frame.acquireDepthImage()
    
    if (depthImage != null) {
        val width = depthImage.width
        val height = depthImage.height
        
        Log.d(TAG, "Depth resolution: ${width}x${height}")
        
        // 期待される解像度より低い場合は警告
        if (width < 320 || height < 240) {
            Log.w(TAG, "Low depth resolution detected: ${width}x${height}")
            Log.w(TAG, "Consider adjusting camera config for higher depth resolution")
        }
        
        // 深度データを保存
        saveDepthImage(depthImage, frame.timestamp)
        
        depthImage.close()
    }
}
```

## ARCore Depth解像度の制約

### デバイスによる制約

1. **Depth Camera搭載デバイス** (iPhone 15 Proなど)
   - より高解像度の深度データが取得可能
   - 通常: 256x192, 320x240, 640x480など

2. **推定Depth（Motion Stereo + ML）** (Pixel 7 Proなど)
   - 解像度が制限される（160x90, 256x192など）
   - デバイスの性能とARCoreのバージョンに依存

3. **Depth APIのバージョン**
   - ARCore 1.20以降: より高解像度をサポート
   - 古いバージョン: 解像度が制限される

### 推奨される解像度

- **最小: 256x192** (49,152ピクセル)
- **推奨: 320x240** (76,800ピクセル)
- **理想: 640x480** (307,200ピクセル) - Depth Camera搭載デバイスのみ

現在の160x90 (14,400ピクセル)は**非常に低い**ため、可能な限り向上させる必要があります。

## 実装チェックリスト

### Androidアプリ側での確認事項

1. **ARCore Sessionの設定を確認**
   ```kotlin
   // 現在のカメラ設定を確認
   val currentConfig = session.cameraConfig
   Log.d(TAG, "Current camera config: ${currentConfig.imageSize}")
   ```

2. **利用可能な深度解像度を確認**
   ```kotlin
   // サポートされている設定を確認
   val configList = session.getSupportedCameraConfigs(ArCameraConfigFilter(session))
   for (config in configList) {
       Log.d(TAG, "Available config: ${config.imageSize}")
   }
   ```

3. **深度画像の解像度をログ出力**
   ```kotlin
   val depthImage = frame.acquireDepthImage()
   Log.d(TAG, "Depth image size: ${depthImage.width}x${depthImage.height}")
   ```

### サーバー側での確認

診断スクリプトで確認：
```bash
python diagnose_depth.py <job_id>
```

期待される結果：
- Depth resolution: 320x240以上
- Valid pixels: 10%以上

## 対処法

### 即座に実施可能（サーバー側）

1. **深度前処理の強化**
   - 穴埋め（inpainting）を実装
   - 無効値の補間

2. **TSDFパラメータの調整**
   - `voxel_length`を大きく（0.04m以上）
   - `depth_trunc`を適切に設定（診断結果の99パーセンタイル値）

### 根本的解決（Androidアプリ側）

1. **ARCore Session設定の見直し**
   - カメラ設定で最高解像度を選択
   - Depth APIのバージョンを確認

2. **ARCoreのバージョン更新**
   - 最新バージョンでより高解像度をサポート

3. **Depth Camera搭載デバイスの使用**
   - iPhone 15 Pro / iPad Pro
   - Intel RealSense
   - Azure Kinect

## 参考資料

- [ARCore Depth API Documentation](https://developers.google.com/ar/develop/java/depth)
- [ARCore Camera Configuration](https://developers.google.com/ar/reference/java/com/google/ar/core/ArCameraConfig)

最終更新: 2026-01-08 10:14:57
---

# Android側でのDepth解像度向上ガイド

## 現状の問題

診断結果から以下の問題が判明：
- **深度解像度: 160x90** (14,400ピクセル) - 非常に低い
- **有効深度ピクセル: 0.4%** (99.6%が無効値マーカー)
- これはARCore Depth APIの**デフォルト解像度**で、明示的に解像度を指定していない可能性が高い

## ARCore Depth APIの解像度設定

### ARCore Depth APIの解像度オプション

ARCore Depth APIでは、`ArCameraConfig`または`ArSession`で深度解像度を設定できます。

#### 1. カメラ設定での解像度指定（推奨）

```java
// ARCore Depth APIの解像度を設定
ArSession session = new ArSession(context);

// カメラ設定を取得
ArCameraConfigFilter filter = new ArCameraConfigFilter(session);
ArCameraConfigList configList = session.getSupportedCameraConfigs(filter);

// 深度解像度が高い設定を選択
ArCameraConfig bestConfig = null;
int maxDepthSize = 0;
for (ArCameraConfig config : configList) {
    ArCameraConfig.DepthSensorUsage usage = config.getDepthSensorUsage();
    
    // 深度解像度を確認（直接取得できない場合、ターミナル解像度から推測）
    // より高い解像度の設定を選択
    int depthWidth = config.getImageSize().getWidth();  // 深度は通常カメラ解像度より低い
    if (depthWidth > maxDepthSize) {
        maxDepthSize = depthWidth;
        bestConfig = config;
    }
}

if (bestConfig != null) {
    session.setCameraConfig(bestConfig);
}
```

#### 2. ARCore Sessionの深度設定（直接指定）

```java
// ARCore 1.30以降では、深度解像度をより直接的に制御可能
ArConfig config = new ArConfig(session);
config.setDepthMode(ArConfig.DepthMode.AUTOMATIC);  // または DEPTH_MODE_RAW_DEPTH_ONLY

// 深度解像度の優先順位を設定（利用可能な場合）
// 注意: ARCoreのバージョンによってAPIが異なる可能性があります
```

#### 3. Depth APIでの最大解像度取得

```java
// 利用可能な深度解像度を取得
ArDepthPointCloud depthPointCloud = frame.acquireDepthPointCloud();

// 深度画像の解像度を確認
int depthWidth = depthPointCloud.getWidth();
int depthHeight = depthPointCloud.getHeight();

// より高い解像度が必要な場合、カメラ設定を調整
```

### 実装例（Kotlin/Java）

#### Androidアプリ側での設定

```kotlin
// ARCore Session初期化時に深度解像度を最大にする
fun initializeArCore(context: Context): ArSession? {
    val session = ArSession(context)
    
    try {
        // デフォルト設定を取得
        val defaultConfig = ArConfig(session)
        defaultConfig.depthMode = ArConfig.DepthMode.AUTOMATIC
        
        // サポートされているカメラ設定を確認
        val configFilter = ArCameraConfigFilter(session)
        val configList = session.getSupportedCameraConfigs(configFilter)
        
        // 最大解像度の設定を選択
        var bestConfig: ArCameraConfig? = null
        var maxResolution = 0
        
        for (i in 0 until configList.size) {
            val config = configList[i]
            val imageSize = config.imageSize
            
            // 画像解像度から深度解像度を推測（深度は通常1/4〜1/2）
            val estimatedDepthResolution = imageSize.width * imageSize.height
            
            if (estimatedDepthResolution > maxResolution) {
                maxResolution = estimatedDepthResolution
                bestConfig = config
            }
        }
        
        // 最適な設定を適用
        if (bestConfig != null) {
            session.setCameraConfig(bestConfig)
            Log.d(TAG, "Depth resolution optimized: ${bestConfig.imageSize}")
        }
        
        session.configure(defaultConfig)
        return session
        
    } catch (e: Exception) {
        Log.e(TAG, "ARCore initialization failed", e)
        return null
    }
}
```

#### 深度データ取得時の解像度確認

```kotlin
// フレームごとに深度データを取得
fun processFrame(frame: ArFrame) {
    val depthImage = frame.acquireDepthImage()
    
    if (depthImage != null) {
        val width = depthImage.width
        val height = depthImage.height
        
        Log.d(TAG, "Depth resolution: ${width}x${height}")
        
        // 期待される解像度より低い場合は警告
        if (width < 320 || height < 240) {
            Log.w(TAG, "Low depth resolution detected: ${width}x${height}")
            Log.w(TAG, "Consider adjusting camera config for higher depth resolution")
        }
        
        // 深度データを保存
        saveDepthImage(depthImage, frame.timestamp)
        
        depthImage.close()
    }
}
```

## ARCore Depth解像度の制約

### デバイスによる制約

1. **Depth Camera搭載デバイス** (iPhone 15 Proなど)
   - より高解像度の深度データが取得可能
   - 通常: 256x192, 320x240, 640x480など

2. **推定Depth（Motion Stereo + ML）** (Pixel 7 Proなど)
   - 解像度が制限される（160x90, 256x192など）
   - デバイスの性能とARCoreのバージョンに依存

3. **Depth APIのバージョン**
   - ARCore 1.20以降: より高解像度をサポート
   - 古いバージョン: 解像度が制限される

### 推奨される解像度

- **最小: 256x192** (49,152ピクセル)
- **推奨: 320x240** (76,800ピクセル)
- **理想: 640x480** (307,200ピクセル) - Depth Camera搭載デバイスのみ

現在の160x90 (14,400ピクセル)は**非常に低い**ため、可能な限り向上させる必要があります。

## 実装チェックリスト

### Androidアプリ側での確認事項

1. **ARCore Sessionの設定を確認**
   ```kotlin
   // 現在のカメラ設定を確認
   val currentConfig = session.cameraConfig
   Log.d(TAG, "Current camera config: ${currentConfig.imageSize}")
   ```

2. **利用可能な深度解像度を確認**
   ```kotlin
   // サポートされている設定を確認
   val configList = session.getSupportedCameraConfigs(ArCameraConfigFilter(session))
   for (config in configList) {
       Log.d(TAG, "Available config: ${config.imageSize}")
   }
   ```

3. **深度画像の解像度をログ出力**
   ```kotlin
   val depthImage = frame.acquireDepthImage()
   Log.d(TAG, "Depth image size: ${depthImage.width}x${depthImage.height}")
   ```

### サーバー側での確認

診断スクリプトで確認：
```bash
python diagnose_depth.py <job_id>
```

期待される結果：
- Depth resolution: 320x240以上
- Valid pixels: 10%以上

## 対処法

### 即座に実施可能（サーバー側）

1. **深度前処理の強化**
   - 穴埋め（inpainting）を実装
   - 無効値の補間

2. **TSDFパラメータの調整**
   - `voxel_length`を大きく（0.04m以上）
   - `depth_trunc`を適切に設定（診断結果の99パーセンタイル値）

### 根本的解決（Androidアプリ側）

1. **ARCore Session設定の見直し**
   - カメラ設定で最高解像度を選択
   - Depth APIのバージョンを確認

2. **ARCoreのバージョン更新**
   - 最新バージョンでより高解像度をサポート

3. **Depth Camera搭載デバイスの使用**
   - iPhone 15 Pro / iPad Pro
   - Intel RealSense
   - Azure Kinect

## 参考資料

- [ARCore Depth API Documentation](https://developers.google.com/ar/develop/java/depth)
- [ARCore Camera Configuration](https://developers.google.com/ar/reference/java/com/google/ar/core/ArCameraConfig)

最終更新: 2026-01-08 10:14:57
---

# Android側でのDepth解像度向上ガイド

## 現状の問題

診断結果から以下の問題が判明：
- **深度解像度: 160x90** (14,400ピクセル) - 非常に低い
- **有効深度ピクセル: 0.4%** (99.6%が無効値マーカー)
- これはARCore Depth APIの**デフォルト解像度**で、明示的に解像度を指定していない可能性が高い

## ARCore Depth APIの解像度設定

### ARCore Depth APIの解像度オプション

ARCore Depth APIでは、`ArCameraConfig`または`ArSession`で深度解像度を設定できます。

#### 1. カメラ設定での解像度指定（推奨）

```java
// ARCore Depth APIの解像度を設定
ArSession session = new ArSession(context);

// カメラ設定を取得
ArCameraConfigFilter filter = new ArCameraConfigFilter(session);
ArCameraConfigList configList = session.getSupportedCameraConfigs(filter);

// 深度解像度が高い設定を選択
ArCameraConfig bestConfig = null;
int maxDepthSize = 0;
for (ArCameraConfig config : configList) {
    ArCameraConfig.DepthSensorUsage usage = config.getDepthSensorUsage();
    
    // 深度解像度を確認（直接取得できない場合、ターミナル解像度から推測）
    // より高い解像度の設定を選択
    int depthWidth = config.getImageSize().getWidth();  // 深度は通常カメラ解像度より低い
    if (depthWidth > maxDepthSize) {
        maxDepthSize = depthWidth;
        bestConfig = config;
    }
}

if (bestConfig != null) {
    session.setCameraConfig(bestConfig);
}
```

#### 2. ARCore Sessionの深度設定（直接指定）

```java
// ARCore 1.30以降では、深度解像度をより直接的に制御可能
ArConfig config = new ArConfig(session);
config.setDepthMode(ArConfig.DepthMode.AUTOMATIC);  // または DEPTH_MODE_RAW_DEPTH_ONLY

// 深度解像度の優先順位を設定（利用可能な場合）
// 注意: ARCoreのバージョンによってAPIが異なる可能性があります
```

#### 3. Depth APIでの最大解像度取得

```java
// 利用可能な深度解像度を取得
ArDepthPointCloud depthPointCloud = frame.acquireDepthPointCloud();

// 深度画像の解像度を確認
int depthWidth = depthPointCloud.getWidth();
int depthHeight = depthPointCloud.getHeight();

// より高い解像度が必要な場合、カメラ設定を調整
```

### 実装例（Kotlin/Java）

#### Androidアプリ側での設定

```kotlin
// ARCore Session初期化時に深度解像度を最大にする
fun initializeArCore(context: Context): ArSession? {
    val session = ArSession(context)
    
    try {
        // デフォルト設定を取得
        val defaultConfig = ArConfig(session)
        defaultConfig.depthMode = ArConfig.DepthMode.AUTOMATIC
        
        // サポートされているカメラ設定を確認
        val configFilter = ArCameraConfigFilter(session)
        val configList = session.getSupportedCameraConfigs(configFilter)
        
        // 最大解像度の設定を選択
        var bestConfig: ArCameraConfig? = null
        var maxResolution = 0
        
        for (i in 0 until configList.size) {
            val config = configList[i]
            val imageSize = config.imageSize
            
            // 画像解像度から深度解像度を推測（深度は通常1/4〜1/2）
            val estimatedDepthResolution = imageSize.width * imageSize.height
            
            if (estimatedDepthResolution > maxResolution) {
                maxResolution = estimatedDepthResolution
                bestConfig = config
            }
        }
        
        // 最適な設定を適用
        if (bestConfig != null) {
            session.setCameraConfig(bestConfig)
            Log.d(TAG, "Depth resolution optimized: ${bestConfig.imageSize}")
        }
        
        session.configure(defaultConfig)
        return session
        
    } catch (e: Exception) {
        Log.e(TAG, "ARCore initialization failed", e)
        return null
    }
}
```

#### 深度データ取得時の解像度確認

```kotlin
// フレームごとに深度データを取得
fun processFrame(frame: ArFrame) {
    val depthImage = frame.acquireDepthImage()
    
    if (depthImage != null) {
        val width = depthImage.width
        val height = depthImage.height
        
        Log.d(TAG, "Depth resolution: ${width}x${height}")
        
        // 期待される解像度より低い場合は警告
        if (width < 320 || height < 240) {
            Log.w(TAG, "Low depth resolution detected: ${width}x${height}")
            Log.w(TAG, "Consider adjusting camera config for higher depth resolution")
        }
        
        // 深度データを保存
        saveDepthImage(depthImage, frame.timestamp)
        
        depthImage.close()
    }
}
```

## ARCore Depth解像度の制約

### デバイスによる制約

1. **Depth Camera搭載デバイス** (iPhone 15 Proなど)
   - より高解像度の深度データが取得可能
   - 通常: 256x192, 320x240, 640x480など

2. **推定Depth（Motion Stereo + ML）** (Pixel 7 Proなど)
   - 解像度が制限される（160x90, 256x192など）
   - デバイスの性能とARCoreのバージョンに依存

3. **Depth APIのバージョン**
   - ARCore 1.20以降: より高解像度をサポート
   - 古いバージョン: 解像度が制限される

### 推奨される解像度

- **最小: 256x192** (49,152ピクセル)
- **推奨: 320x240** (76,800ピクセル)
- **理想: 640x480** (307,200ピクセル) - Depth Camera搭載デバイスのみ

現在の160x90 (14,400ピクセル)は**非常に低い**ため、可能な限り向上させる必要があります。

## 実装チェックリスト

### Androidアプリ側での確認事項

1. **ARCore Sessionの設定を確認**
   ```kotlin
   // 現在のカメラ設定を確認
   val currentConfig = session.cameraConfig
   Log.d(TAG, "Current camera config: ${currentConfig.imageSize}")
   ```

2. **利用可能な深度解像度を確認**
   ```kotlin
   // サポートされている設定を確認
   val configList = session.getSupportedCameraConfigs(ArCameraConfigFilter(session))
   for (config in configList) {
       Log.d(TAG, "Available config: ${config.imageSize}")
   }
   ```

3. **深度画像の解像度をログ出力**
   ```kotlin
   val depthImage = frame.acquireDepthImage()
   Log.d(TAG, "Depth image size: ${depthImage.width}x${depthImage.height}")
   ```

### サーバー側での確認

診断スクリプトで確認：
```bash
python diagnose_depth.py <job_id>
```

期待される結果：
- Depth resolution: 320x240以上
- Valid pixels: 10%以上

## 対処法

### 即座に実施可能（サーバー側）

1. **深度前処理の強化**
   - 穴埋め（inpainting）を実装
   - 無効値の補間

2. **TSDFパラメータの調整**
   - `voxel_length`を大きく（0.04m以上）
   - `depth_trunc`を適切に設定（診断結果の99パーセンタイル値）

### 根本的解決（Androidアプリ側）

1. **ARCore Session設定の見直し**
   - カメラ設定で最高解像度を選択
   - Depth APIのバージョンを確認

2. **ARCoreのバージョン更新**
   - 最新バージョンでより高解像度をサポート

3. **Depth Camera搭載デバイスの使用**
   - iPhone 15 Pro / iPad Pro
   - Intel RealSense
   - Azure Kinect

## 参考資料

- [ARCore Depth API Documentation](https://developers.google.com/ar/develop/java/depth)
- [ARCore Camera Configuration](https://developers.google.com/ar/reference/java/com/google/ar/core/ArCameraConfig)

最終更新: 2026-01-08 10:14:57
---

# Android側でのDepth解像度向上ガイド

## 現状の問題

診断結果から以下の問題が判明：
- **深度解像度: 160x90** (14,400ピクセル) - 非常に低い
- **有効深度ピクセル: 0.4%** (99.6%が無効値マーカー)
- これはARCore Depth APIの**デフォルト解像度**で、明示的に解像度を指定していない可能性が高い

## ARCore Depth APIの解像度設定

### ARCore Depth APIの解像度オプション

ARCore Depth APIでは、`ArCameraConfig`または`ArSession`で深度解像度を設定できます。

#### 1. カメラ設定での解像度指定（推奨）

```java
// ARCore Depth APIの解像度を設定
ArSession session = new ArSession(context);

// カメラ設定を取得
ArCameraConfigFilter filter = new ArCameraConfigFilter(session);
ArCameraConfigList configList = session.getSupportedCameraConfigs(filter);

// 深度解像度が高い設定を選択
ArCameraConfig bestConfig = null;
int maxDepthSize = 0;
for (ArCameraConfig config : configList) {
    ArCameraConfig.DepthSensorUsage usage = config.getDepthSensorUsage();
    
    // 深度解像度を確認（直接取得できない場合、ターミナル解像度から推測）
    // より高い解像度の設定を選択
    int depthWidth = config.getImageSize().getWidth();  // 深度は通常カメラ解像度より低い
    if (depthWidth > maxDepthSize) {
        maxDepthSize = depthWidth;
        bestConfig = config;
    }
}

if (bestConfig != null) {
    session.setCameraConfig(bestConfig);
}
```

#### 2. ARCore Sessionの深度設定（直接指定）

```java
// ARCore 1.30以降では、深度解像度をより直接的に制御可能
ArConfig config = new ArConfig(session);
config.setDepthMode(ArConfig.DepthMode.AUTOMATIC);  // または DEPTH_MODE_RAW_DEPTH_ONLY

// 深度解像度の優先順位を設定（利用可能な場合）
// 注意: ARCoreのバージョンによってAPIが異なる可能性があります
```

#### 3. Depth APIでの最大解像度取得

```java
// 利用可能な深度解像度を取得
ArDepthPointCloud depthPointCloud = frame.acquireDepthPointCloud();

// 深度画像の解像度を確認
int depthWidth = depthPointCloud.getWidth();
int depthHeight = depthPointCloud.getHeight();

// より高い解像度が必要な場合、カメラ設定を調整
```

### 実装例（Kotlin/Java）

#### Androidアプリ側での設定

```kotlin
// ARCore Session初期化時に深度解像度を最大にする
fun initializeArCore(context: Context): ArSession? {
    val session = ArSession(context)
    
    try {
        // デフォルト設定を取得
        val defaultConfig = ArConfig(session)
        defaultConfig.depthMode = ArConfig.DepthMode.AUTOMATIC
        
        // サポートされているカメラ設定を確認
        val configFilter = ArCameraConfigFilter(session)
        val configList = session.getSupportedCameraConfigs(configFilter)
        
        // 最大解像度の設定を選択
        var bestConfig: ArCameraConfig? = null
        var maxResolution = 0
        
        for (i in 0 until configList.size) {
            val config = configList[i]
            val imageSize = config.imageSize
            
            // 画像解像度から深度解像度を推測（深度は通常1/4〜1/2）
            val estimatedDepthResolution = imageSize.width * imageSize.height
            
            if (estimatedDepthResolution > maxResolution) {
                maxResolution = estimatedDepthResolution
                bestConfig = config
            }
        }
        
        // 最適な設定を適用
        if (bestConfig != null) {
            session.setCameraConfig(bestConfig)
            Log.d(TAG, "Depth resolution optimized: ${bestConfig.imageSize}")
        }
        
        session.configure(defaultConfig)
        return session
        
    } catch (e: Exception) {
        Log.e(TAG, "ARCore initialization failed", e)
        return null
    }
}
```

#### 深度データ取得時の解像度確認

```kotlin
// フレームごとに深度データを取得
fun processFrame(frame: ArFrame) {
    val depthImage = frame.acquireDepthImage()
    
    if (depthImage != null) {
        val width = depthImage.width
        val height = depthImage.height
        
        Log.d(TAG, "Depth resolution: ${width}x${height}")
        
        // 期待される解像度より低い場合は警告
        if (width < 320 || height < 240) {
            Log.w(TAG, "Low depth resolution detected: ${width}x${height}")
            Log.w(TAG, "Consider adjusting camera config for higher depth resolution")
        }
        
        // 深度データを保存
        saveDepthImage(depthImage, frame.timestamp)
        
        depthImage.close()
    }
}
```

## ARCore Depth解像度の制約

### デバイスによる制約

1. **Depth Camera搭載デバイス** (iPhone 15 Proなど)
   - より高解像度の深度データが取得可能
   - 通常: 256x192, 320x240, 640x480など

2. **推定Depth（Motion Stereo + ML）** (Pixel 7 Proなど)
   - 解像度が制限される（160x90, 256x192など）
   - デバイスの性能とARCoreのバージョンに依存

3. **Depth APIのバージョン**
   - ARCore 1.20以降: より高解像度をサポート
   - 古いバージョン: 解像度が制限される

### 推奨される解像度

- **最小: 256x192** (49,152ピクセル)
- **推奨: 320x240** (76,800ピクセル)
- **理想: 640x480** (307,200ピクセル) - Depth Camera搭載デバイスのみ

現在の160x90 (14,400ピクセル)は**非常に低い**ため、可能な限り向上させる必要があります。

## 実装チェックリスト

### Androidアプリ側での確認事項

1. **ARCore Sessionの設定を確認**
   ```kotlin
   // 現在のカメラ設定を確認
   val currentConfig = session.cameraConfig
   Log.d(TAG, "Current camera config: ${currentConfig.imageSize}")
   ```

2. **利用可能な深度解像度を確認**
   ```kotlin
   // サポートされている設定を確認
   val configList = session.getSupportedCameraConfigs(ArCameraConfigFilter(session))
   for (config in configList) {
       Log.d(TAG, "Available config: ${config.imageSize}")
   }
   ```

3. **深度画像の解像度をログ出力**
   ```kotlin
   val depthImage = frame.acquireDepthImage()
   Log.d(TAG, "Depth image size: ${depthImage.width}x${depthImage.height}")
   ```

### サーバー側での確認

診断スクリプトで確認：
```bash
python diagnose_depth.py <job_id>
```

期待される結果：
- Depth resolution: 320x240以上
- Valid pixels: 10%以上

## 対処法

### 即座に実施可能（サーバー側）

1. **深度前処理の強化**
   - 穴埋め（inpainting）を実装
   - 無効値の補間

2. **TSDFパラメータの調整**
   - `voxel_length`を大きく（0.04m以上）
   - `depth_trunc`を適切に設定（診断結果の99パーセンタイル値）

### 根本的解決（Androidアプリ側）

1. **ARCore Session設定の見直し**
   - カメラ設定で最高解像度を選択
   - Depth APIのバージョンを確認

2. **ARCoreのバージョン更新**
   - 最新バージョンでより高解像度をサポート

3. **Depth Camera搭載デバイスの使用**
   - iPhone 15 Pro / iPad Pro
   - Intel RealSense
   - Azure Kinect

## 参考資料

- [ARCore Depth API Documentation](https://developers.google.com/ar/develop/java/depth)
- [ARCore Camera Configuration](https://developers.google.com/ar/reference/java/com/google/ar/core/ArCameraConfig)

最終更新: 2026-01-08 10:14:57
---

# Android側でのDepth解像度向上ガイド

## 現状の問題

診断結果から以下の問題が判明：
- **深度解像度: 160x90** (14,400ピクセル) - 非常に低い
- **有効深度ピクセル: 0.4%** (99.6%が無効値マーカー)
- これはARCore Depth APIの**デフォルト解像度**で、明示的に解像度を指定していない可能性が高い

## ARCore Depth APIの解像度設定

### ARCore Depth APIの解像度オプション

ARCore Depth APIでは、`ArCameraConfig`または`ArSession`で深度解像度を設定できます。

#### 1. カメラ設定での解像度指定（推奨）

```java
// ARCore Depth APIの解像度を設定
ArSession session = new ArSession(context);

// カメラ設定を取得
ArCameraConfigFilter filter = new ArCameraConfigFilter(session);
ArCameraConfigList configList = session.getSupportedCameraConfigs(filter);

// 深度解像度が高い設定を選択
ArCameraConfig bestConfig = null;
int maxDepthSize = 0;
for (ArCameraConfig config : configList) {
    ArCameraConfig.DepthSensorUsage usage = config.getDepthSensorUsage();
    
    // 深度解像度を確認（直接取得できない場合、ターミナル解像度から推測）
    // より高い解像度の設定を選択
    int depthWidth = config.getImageSize().getWidth();  // 深度は通常カメラ解像度より低い
    if (depthWidth > maxDepthSize) {
        maxDepthSize = depthWidth;
        bestConfig = config;
    }
}

if (bestConfig != null) {
    session.setCameraConfig(bestConfig);
}
```

#### 2. ARCore Sessionの深度設定（直接指定）

```java
// ARCore 1.30以降では、深度解像度をより直接的に制御可能
ArConfig config = new ArConfig(session);
config.setDepthMode(ArConfig.DepthMode.AUTOMATIC);  // または DEPTH_MODE_RAW_DEPTH_ONLY

// 深度解像度の優先順位を設定（利用可能な場合）
// 注意: ARCoreのバージョンによってAPIが異なる可能性があります
```

#### 3. Depth APIでの最大解像度取得

```java
// 利用可能な深度解像度を取得
ArDepthPointCloud depthPointCloud = frame.acquireDepthPointCloud();

// 深度画像の解像度を確認
int depthWidth = depthPointCloud.getWidth();
int depthHeight = depthPointCloud.getHeight();

// より高い解像度が必要な場合、カメラ設定を調整
```

### 実装例（Kotlin/Java）

#### Androidアプリ側での設定

```kotlin
// ARCore Session初期化時に深度解像度を最大にする
fun initializeArCore(context: Context): ArSession? {
    val session = ArSession(context)
    
    try {
        // デフォルト設定を取得
        val defaultConfig = ArConfig(session)
        defaultConfig.depthMode = ArConfig.DepthMode.AUTOMATIC
        
        // サポートされているカメラ設定を確認
        val configFilter = ArCameraConfigFilter(session)
        val configList = session.getSupportedCameraConfigs(configFilter)
        
        // 最大解像度の設定を選択
        var bestConfig: ArCameraConfig? = null
        var maxResolution = 0
        
        for (i in 0 until configList.size) {
            val config = configList[i]
            val imageSize = config.imageSize
            
            // 画像解像度から深度解像度を推測（深度は通常1/4〜1/2）
            val estimatedDepthResolution = imageSize.width * imageSize.height
            
            if (estimatedDepthResolution > maxResolution) {
                maxResolution = estimatedDepthResolution
                bestConfig = config
            }
        }
        
        // 最適な設定を適用
        if (bestConfig != null) {
            session.setCameraConfig(bestConfig)
            Log.d(TAG, "Depth resolution optimized: ${bestConfig.imageSize}")
        }
        
        session.configure(defaultConfig)
        return session
        
    } catch (e: Exception) {
        Log.e(TAG, "ARCore initialization failed", e)
        return null
    }
}
```

#### 深度データ取得時の解像度確認

```kotlin
// フレームごとに深度データを取得
fun processFrame(frame: ArFrame) {
    val depthImage = frame.acquireDepthImage()
    
    if (depthImage != null) {
        val width = depthImage.width
        val height = depthImage.height
        
        Log.d(TAG, "Depth resolution: ${width}x${height}")
        
        // 期待される解像度より低い場合は警告
        if (width < 320 || height < 240) {
            Log.w(TAG, "Low depth resolution detected: ${width}x${height}")
            Log.w(TAG, "Consider adjusting camera config for higher depth resolution")
        }
        
        // 深度データを保存
        saveDepthImage(depthImage, frame.timestamp)
        
        depthImage.close()
    }
}
```

## ARCore Depth解像度の制約

### デバイスによる制約

1. **Depth Camera搭載デバイス** (iPhone 15 Proなど)
   - より高解像度の深度データが取得可能
   - 通常: 256x192, 320x240, 640x480など

2. **推定Depth（Motion Stereo + ML）** (Pixel 7 Proなど)
   - 解像度が制限される（160x90, 256x192など）
   - デバイスの性能とARCoreのバージョンに依存

3. **Depth APIのバージョン**
   - ARCore 1.20以降: より高解像度をサポート
   - 古いバージョン: 解像度が制限される

### 推奨される解像度

- **最小: 256x192** (49,152ピクセル)
- **推奨: 320x240** (76,800ピクセル)
- **理想: 640x480** (307,200ピクセル) - Depth Camera搭載デバイスのみ

現在の160x90 (14,400ピクセル)は**非常に低い**ため、可能な限り向上させる必要があります。

## 実装チェックリスト

### Androidアプリ側での確認事項

1. **ARCore Sessionの設定を確認**
   ```kotlin
   // 現在のカメラ設定を確認
   val currentConfig = session.cameraConfig
   Log.d(TAG, "Current camera config: ${currentConfig.imageSize}")
   ```

2. **利用可能な深度解像度を確認**
   ```kotlin
   // サポートされている設定を確認
   val configList = session.getSupportedCameraConfigs(ArCameraConfigFilter(session))
   for (config in configList) {
       Log.d(TAG, "Available config: ${config.imageSize}")
   }
   ```

3. **深度画像の解像度をログ出力**
   ```kotlin
   val depthImage = frame.acquireDepthImage()
   Log.d(TAG, "Depth image size: ${depthImage.width}x${depthImage.height}")
   ```

### サーバー側での確認

診断スクリプトで確認：
```bash
python diagnose_depth.py <job_id>
```

期待される結果：
- Depth resolution: 320x240以上
- Valid pixels: 10%以上

## 対処法

### 即座に実施可能（サーバー側）

1. **深度前処理の強化**
   - 穴埋め（inpainting）を実装
   - 無効値の補間

2. **TSDFパラメータの調整**
   - `voxel_length`を大きく（0.04m以上）
   - `depth_trunc`を適切に設定（診断結果の99パーセンタイル値）

### 根本的解決（Androidアプリ側）

1. **ARCore Session設定の見直し**
   - カメラ設定で最高解像度を選択
   - Depth APIのバージョンを確認

2. **ARCoreのバージョン更新**
   - 最新バージョンでより高解像度をサポート

3. **Depth Camera搭載デバイスの使用**
   - iPhone 15 Pro / iPad Pro
   - Intel RealSense
   - Azure Kinect

## 参考資料

- [ARCore Depth API Documentation](https://developers.google.com/ar/develop/java/depth)
- [ARCore Camera Configuration](https://developers.google.com/ar/reference/java/com/google/ar/core/ArCameraConfig)

最終更新: 2026-01-08 10:14:57
---

# Android側でのDepth解像度向上ガイド

## 現状の問題

診断結果から以下の問題が判明：
- **深度解像度: 160x90** (14,400ピクセル) - 非常に低い
- **有効深度ピクセル: 0.4%** (99.6%が無効値マーカー)
- これはARCore Depth APIの**デフォルト解像度**で、明示的に解像度を指定していない可能性が高い

## ARCore Depth APIの解像度設定

### ARCore Depth APIの解像度オプション

ARCore Depth APIでは、`ArCameraConfig`または`ArSession`で深度解像度を設定できます。

#### 1. カメラ設定での解像度指定（推奨）

```java
// ARCore Depth APIの解像度を設定
ArSession session = new ArSession(context);

// カメラ設定を取得
ArCameraConfigFilter filter = new ArCameraConfigFilter(session);
ArCameraConfigList configList = session.getSupportedCameraConfigs(filter);

// 深度解像度が高い設定を選択
ArCameraConfig bestConfig = null;
int maxDepthSize = 0;
for (ArCameraConfig config : configList) {
    ArCameraConfig.DepthSensorUsage usage = config.getDepthSensorUsage();
    
    // 深度解像度を確認（直接取得できない場合、ターミナル解像度から推測）
    // より高い解像度の設定を選択
    int depthWidth = config.getImageSize().getWidth();  // 深度は通常カメラ解像度より低い
    if (depthWidth > maxDepthSize) {
        maxDepthSize = depthWidth;
        bestConfig = config;
    }
}

if (bestConfig != null) {
    session.setCameraConfig(bestConfig);
}
```

#### 2. ARCore Sessionの深度設定（直接指定）

```java
// ARCore 1.30以降では、深度解像度をより直接的に制御可能
ArConfig config = new ArConfig(session);
config.setDepthMode(ArConfig.DepthMode.AUTOMATIC);  // または DEPTH_MODE_RAW_DEPTH_ONLY

// 深度解像度の優先順位を設定（利用可能な場合）
// 注意: ARCoreのバージョンによってAPIが異なる可能性があります
```

#### 3. Depth APIでの最大解像度取得

```java
// 利用可能な深度解像度を取得
ArDepthPointCloud depthPointCloud = frame.acquireDepthPointCloud();

// 深度画像の解像度を確認
int depthWidth = depthPointCloud.getWidth();
int depthHeight = depthPointCloud.getHeight();

// より高い解像度が必要な場合、カメラ設定を調整
```

### 実装例（Kotlin/Java）

#### Androidアプリ側での設定

```kotlin
// ARCore Session初期化時に深度解像度を最大にする
fun initializeArCore(context: Context): ArSession? {
    val session = ArSession(context)
    
    try {
        // デフォルト設定を取得
        val defaultConfig = ArConfig(session)
        defaultConfig.depthMode = ArConfig.DepthMode.AUTOMATIC
        
        // サポートされているカメラ設定を確認
        val configFilter = ArCameraConfigFilter(session)
        val configList = session.getSupportedCameraConfigs(configFilter)
        
        // 最大解像度の設定を選択
        var bestConfig: ArCameraConfig? = null
        var maxResolution = 0
        
        for (i in 0 until configList.size) {
            val config = configList[i]
            val imageSize = config.imageSize
            
            // 画像解像度から深度解像度を推測（深度は通常1/4〜1/2）
            val estimatedDepthResolution = imageSize.width * imageSize.height
            
            if (estimatedDepthResolution > maxResolution) {
                maxResolution = estimatedDepthResolution
                bestConfig = config
            }
        }
        
        // 最適な設定を適用
        if (bestConfig != null) {
            session.setCameraConfig(bestConfig)
            Log.d(TAG, "Depth resolution optimized: ${bestConfig.imageSize}")
        }
        
        session.configure(defaultConfig)
        return session
        
    } catch (e: Exception) {
        Log.e(TAG, "ARCore initialization failed", e)
        return null
    }
}
```

#### 深度データ取得時の解像度確認

```kotlin
// フレームごとに深度データを取得
fun processFrame(frame: ArFrame) {
    val depthImage = frame.acquireDepthImage()
    
    if (depthImage != null) {
        val width = depthImage.width
        val height = depthImage.height
        
        Log.d(TAG, "Depth resolution: ${width}x${height}")
        
        // 期待される解像度より低い場合は警告
        if (width < 320 || height < 240) {
            Log.w(TAG, "Low depth resolution detected: ${width}x${height}")
            Log.w(TAG, "Consider adjusting camera config for higher depth resolution")
        }
        
        // 深度データを保存
        saveDepthImage(depthImage, frame.timestamp)
        
        depthImage.close()
    }
}
```

## ARCore Depth解像度の制約

### デバイスによる制約

1. **Depth Camera搭載デバイス** (iPhone 15 Proなど)
   - より高解像度の深度データが取得可能
   - 通常: 256x192, 320x240, 640x480など

2. **推定Depth（Motion Stereo + ML）** (Pixel 7 Proなど)
   - 解像度が制限される（160x90, 256x192など）
   - デバイスの性能とARCoreのバージョンに依存

3. **Depth APIのバージョン**
   - ARCore 1.20以降: より高解像度をサポート
   - 古いバージョン: 解像度が制限される

### 推奨される解像度

- **最小: 256x192** (49,152ピクセル)
- **推奨: 320x240** (76,800ピクセル)
- **理想: 640x480** (307,200ピクセル) - Depth Camera搭載デバイスのみ

現在の160x90 (14,400ピクセル)は**非常に低い**ため、可能な限り向上させる必要があります。

## 実装チェックリスト

### Androidアプリ側での確認事項

1. **ARCore Sessionの設定を確認**
   ```kotlin
   // 現在のカメラ設定を確認
   val currentConfig = session.cameraConfig
   Log.d(TAG, "Current camera config: ${currentConfig.imageSize}")
   ```

2. **利用可能な深度解像度を確認**
   ```kotlin
   // サポートされている設定を確認
   val configList = session.getSupportedCameraConfigs(ArCameraConfigFilter(session))
   for (config in configList) {
       Log.d(TAG, "Available config: ${config.imageSize}")
   }
   ```

3. **深度画像の解像度をログ出力**
   ```kotlin
   val depthImage = frame.acquireDepthImage()
   Log.d(TAG, "Depth image size: ${depthImage.width}x${depthImage.height}")
   ```

### サーバー側での確認

診断スクリプトで確認：
```bash
python diagnose_depth.py <job_id>
```

期待される結果：
- Depth resolution: 320x240以上
- Valid pixels: 10%以上

## 対処法

### 即座に実施可能（サーバー側）

1. **深度前処理の強化**
   - 穴埋め（inpainting）を実装
   - 無効値の補間

2. **TSDFパラメータの調整**
   - `voxel_length`を大きく（0.04m以上）
   - `depth_trunc`を適切に設定（診断結果の99パーセンタイル値）

### 根本的解決（Androidアプリ側）

1. **ARCore Session設定の見直し**
   - カメラ設定で最高解像度を選択
   - Depth APIのバージョンを確認

2. **ARCoreのバージョン更新**
   - 最新バージョンでより高解像度をサポート

3. **Depth Camera搭載デバイスの使用**
   - iPhone 15 Pro / iPad Pro
   - Intel RealSense
   - Azure Kinect

## 参考資料

- [ARCore Depth API Documentation](https://developers.google.com/ar/develop/java/depth)
- [ARCore Camera Configuration](https://developers.google.com/ar/reference/java/com/google/ar/core/ArCameraConfig)
最終更新: 2026-01-08 10:14:57
---

# Android側でのDepth解像度向上ガイド

## 現状の問題

診断結果から以下の問題が判明：
- **深度解像度: 160x90** (14,400ピクセル) - 非常に低い
- **有効深度ピクセル: 0.4%** (99.6%が無効値マーカー)
- これはARCore Depth APIの**デフォルト解像度**で、明示的に解像度を指定していない可能性が高い

## ARCore Depth APIの解像度設定

### ARCore Depth APIの解像度オプション

ARCore Depth APIでは、`ArCameraConfig`または`ArSession`で深度解像度を設定できます。

#### 1. カメラ設定での解像度指定（推奨）

```java
// ARCore Depth APIの解像度を設定
ArSession session = new ArSession(context);

// カメラ設定を取得
ArCameraConfigFilter filter = new ArCameraConfigFilter(session);
ArCameraConfigList configList = session.getSupportedCameraConfigs(filter);

// 深度解像度が高い設定を選択
ArCameraConfig bestConfig = null;
int maxDepthSize = 0;
for (ArCameraConfig config : configList) {
    ArCameraConfig.DepthSensorUsage usage = config.getDepthSensorUsage();
    
    // 深度解像度を確認（直接取得できない場合、ターミナル解像度から推測）
    // より高い解像度の設定を選択
    int depthWidth = config.getImageSize().getWidth();  // 深度は通常カメラ解像度より低い
    if (depthWidth > maxDepthSize) {
        maxDepthSize = depthWidth;
        bestConfig = config;
    }
}

if (bestConfig != null) {
    session.setCameraConfig(bestConfig);
}
```

#### 2. ARCore Sessionの深度設定（直接指定）

```java
// ARCore 1.30以降では、深度解像度をより直接的に制御可能
ArConfig config = new ArConfig(session);
config.setDepthMode(ArConfig.DepthMode.AUTOMATIC);  // または DEPTH_MODE_RAW_DEPTH_ONLY

// 深度解像度の優先順位を設定（利用可能な場合）
// 注意: ARCoreのバージョンによってAPIが異なる可能性があります
```

#### 3. Depth APIでの最大解像度取得

```java
// 利用可能な深度解像度を取得
ArDepthPointCloud depthPointCloud = frame.acquireDepthPointCloud();

// 深度画像の解像度を確認
int depthWidth = depthPointCloud.getWidth();
int depthHeight = depthPointCloud.getHeight();

// より高い解像度が必要な場合、カメラ設定を調整
```

### 実装例（Kotlin/Java）

#### Androidアプリ側での設定

```kotlin
// ARCore Session初期化時に深度解像度を最大にする
fun initializeArCore(context: Context): ArSession? {
    val session = ArSession(context)
    
    try {
        // デフォルト設定を取得
        val defaultConfig = ArConfig(session)
        defaultConfig.depthMode = ArConfig.DepthMode.AUTOMATIC
        
        // サポートされているカメラ設定を確認
        val configFilter = ArCameraConfigFilter(session)
        val configList = session.getSupportedCameraConfigs(configFilter)
        
        // 最大解像度の設定を選択
        var bestConfig: ArCameraConfig? = null
        var maxResolution = 0
        
        for (i in 0 until configList.size) {
            val config = configList[i]
            val imageSize = config.imageSize
            
            // 画像解像度から深度解像度を推測（深度は通常1/4〜1/2）
            val estimatedDepthResolution = imageSize.width * imageSize.height
            
            if (estimatedDepthResolution > maxResolution) {
                maxResolution = estimatedDepthResolution
                bestConfig = config
            }
        }
        
        // 最適な設定を適用
        if (bestConfig != null) {
            session.setCameraConfig(bestConfig)
            Log.d(TAG, "Depth resolution optimized: ${bestConfig.imageSize}")
        }
        
        session.configure(defaultConfig)
        return session
        
    } catch (e: Exception) {
        Log.e(TAG, "ARCore initialization failed", e)
        return null
    }
}
```

#### 深度データ取得時の解像度確認

```kotlin
// フレームごとに深度データを取得
fun processFrame(frame: ArFrame) {
    val depthImage = frame.acquireDepthImage()
    
    if (depthImage != null) {
        val width = depthImage.width
        val height = depthImage.height
        
        Log.d(TAG, "Depth resolution: ${width}x${height}")
        
        // 期待される解像度より低い場合は警告
        if (width < 320 || height < 240) {
            Log.w(TAG, "Low depth resolution detected: ${width}x${height}")
            Log.w(TAG, "Consider adjusting camera config for higher depth resolution")
        }
        
        // 深度データを保存
        saveDepthImage(depthImage, frame.timestamp)
        
        depthImage.close()
    }
}
```

## ARCore Depth解像度の制約

### デバイスによる制約

1. **Depth Camera搭載デバイス** (iPhone 15 Proなど)
   - より高解像度の深度データが取得可能
   - 通常: 256x192, 320x240, 640x480など

2. **推定Depth（Motion Stereo + ML）** (Pixel 7 Proなど)
   - 解像度が制限される（160x90, 256x192など）
   - デバイスの性能とARCoreのバージョンに依存

3. **Depth APIのバージョン**
   - ARCore 1.20以降: より高解像度をサポート
   - 古いバージョン: 解像度が制限される

### 推奨される解像度

- **最小: 256x192** (49,152ピクセル)
- **推奨: 320x240** (76,800ピクセル)
- **理想: 640x480** (307,200ピクセル) - Depth Camera搭載デバイスのみ

現在の160x90 (14,400ピクセル)は**非常に低い**ため、可能な限り向上させる必要があります。

## 実装チェックリスト

### Androidアプリ側での確認事項

1. **ARCore Sessionの設定を確認**
   ```kotlin
   // 現在のカメラ設定を確認
   val currentConfig = session.cameraConfig
   Log.d(TAG, "Current camera config: ${currentConfig.imageSize}")
   ```

2. **利用可能な深度解像度を確認**
   ```kotlin
   // サポートされている設定を確認
   val configList = session.getSupportedCameraConfigs(ArCameraConfigFilter(session))
   for (config in configList) {
       Log.d(TAG, "Available config: ${config.imageSize}")
   }
   ```

3. **深度画像の解像度をログ出力**
   ```kotlin
   val depthImage = frame.acquireDepthImage()
   Log.d(TAG, "Depth image size: ${depthImage.width}x${depthImage.height}")
   ```

### サーバー側での確認

診断スクリプトで確認：
```bash
python diagnose_depth.py <job_id>
```

期待される結果：
- Depth resolution: 320x240以上
- Valid pixels: 10%以上

## 対処法

### 即座に実施可能（サーバー側）

1. **深度前処理の強化**
   - 穴埋め（inpainting）を実装
   - 無効値の補間

2. **TSDFパラメータの調整**
   - `voxel_length`を大きく（0.04m以上）
   - `depth_trunc`を適切に設定（診断結果の99パーセンタイル値）

### 根本的解決（Androidアプリ側）

1. **ARCore Session設定の見直し**
   - カメラ設定で最高解像度を選択
   - Depth APIのバージョンを確認

2. **ARCoreのバージョン更新**
   - 最新バージョンでより高解像度をサポート

3. **Depth Camera搭載デバイスの使用**
   - iPhone 15 Pro / iPad Pro
   - Intel RealSense
   - Azure Kinect

## 参考資料

- [ARCore Depth API Documentation](https://developers.google.com/ar/develop/java/depth)
- [ARCore Camera Configuration](https://developers.google.com/ar/reference/java/com/google/ar/core/ArCameraConfig)

最終更新: 2026-01-08 10:14:57
---

# Android側でのDepth解像度向上ガイド

## 現状の問題

診断結果から以下の問題が判明：
- **深度解像度: 160x90** (14,400ピクセル) - 非常に低い
- **有効深度ピクセル: 0.4%** (99.6%が無効値マーカー)
- これはARCore Depth APIの**デフォルト解像度**で、明示的に解像度を指定していない可能性が高い

## ARCore Depth APIの解像度設定

### ARCore Depth APIの解像度オプション

ARCore Depth APIでは、`ArCameraConfig`または`ArSession`で深度解像度を設定できます。

#### 1. カメラ設定での解像度指定（推奨）

```java
// ARCore Depth APIの解像度を設定
ArSession session = new ArSession(context);

// カメラ設定を取得
ArCameraConfigFilter filter = new ArCameraConfigFilter(session);
ArCameraConfigList configList = session.getSupportedCameraConfigs(filter);

// 深度解像度が高い設定を選択
ArCameraConfig bestConfig = null;
int maxDepthSize = 0;
for (ArCameraConfig config : configList) {
    ArCameraConfig.DepthSensorUsage usage = config.getDepthSensorUsage();
    
    // 深度解像度を確認（直接取得できない場合、ターミナル解像度から推測）
    // より高い解像度の設定を選択
    int depthWidth = config.getImageSize().getWidth();  // 深度は通常カメラ解像度より低い
    if (depthWidth > maxDepthSize) {
        maxDepthSize = depthWidth;
        bestConfig = config;
    }
}

if (bestConfig != null) {
    session.setCameraConfig(bestConfig);
}
```

#### 2. ARCore Sessionの深度設定（直接指定）

```java
// ARCore 1.30以降では、深度解像度をより直接的に制御可能
ArConfig config = new ArConfig(session);
config.setDepthMode(ArConfig.DepthMode.AUTOMATIC);  // または DEPTH_MODE_RAW_DEPTH_ONLY

// 深度解像度の優先順位を設定（利用可能な場合）
// 注意: ARCoreのバージョンによってAPIが異なる可能性があります
```

#### 3. Depth APIでの最大解像度取得

```java
// 利用可能な深度解像度を取得
ArDepthPointCloud depthPointCloud = frame.acquireDepthPointCloud();

// 深度画像の解像度を確認
int depthWidth = depthPointCloud.getWidth();
int depthHeight = depthPointCloud.getHeight();

// より高い解像度が必要な場合、カメラ設定を調整
```

### 実装例（Kotlin/Java）

#### Androidアプリ側での設定

```kotlin
// ARCore Session初期化時に深度解像度を最大にする
fun initializeArCore(context: Context): ArSession? {
    val session = ArSession(context)
    
    try {
        // デフォルト設定を取得
        val defaultConfig = ArConfig(session)
        defaultConfig.depthMode = ArConfig.DepthMode.AUTOMATIC
        
        // サポートされているカメラ設定を確認
        val configFilter = ArCameraConfigFilter(session)
        val configList = session.getSupportedCameraConfigs(configFilter)
        
        // 最大解像度の設定を選択
        var bestConfig: ArCameraConfig? = null
        var maxResolution = 0
        
        for (i in 0 until configList.size) {
            val config = configList[i]
            val imageSize = config.imageSize
            
            // 画像解像度から深度解像度を推測（深度は通常1/4〜1/2）
            val estimatedDepthResolution = imageSize.width * imageSize.height
            
            if (estimatedDepthResolution > maxResolution) {
                maxResolution = estimatedDepthResolution
                bestConfig = config
            }
        }
        
        // 最適な設定を適用
        if (bestConfig != null) {
            session.setCameraConfig(bestConfig)
            Log.d(TAG, "Depth resolution optimized: ${bestConfig.imageSize}")
        }
        
        session.configure(defaultConfig)
        return session
        
    } catch (e: Exception) {
        Log.e(TAG, "ARCore initialization failed", e)
        return null
    }
}
```

#### 深度データ取得時の解像度確認

```kotlin
// フレームごとに深度データを取得
fun processFrame(frame: ArFrame) {
    val depthImage = frame.acquireDepthImage()
    
    if (depthImage != null) {
        val width = depthImage.width
        val height = depthImage.height
        
        Log.d(TAG, "Depth resolution: ${width}x${height}")
        
        // 期待される解像度より低い場合は警告
        if (width < 320 || height < 240) {
            Log.w(TAG, "Low depth resolution detected: ${width}x${height}")
            Log.w(TAG, "Consider adjusting camera config for higher depth resolution")
        }
        
        // 深度データを保存
        saveDepthImage(depthImage, frame.timestamp)
        
        depthImage.close()
    }
}
```

## ARCore Depth解像度の制約

### デバイスによる制約

1. **Depth Camera搭載デバイス** (iPhone 15 Proなど)
   - より高解像度の深度データが取得可能
   - 通常: 256x192, 320x240, 640x480など

2. **推定Depth（Motion Stereo + ML）** (Pixel 7 Proなど)
   - 解像度が制限される（160x90, 256x192など）
   - デバイスの性能とARCoreのバージョンに依存

3. **Depth APIのバージョン**
   - ARCore 1.20以降: より高解像度をサポート
   - 古いバージョン: 解像度が制限される

### 推奨される解像度

- **最小: 256x192** (49,152ピクセル)
- **推奨: 320x240** (76,800ピクセル)
- **理想: 640x480** (307,200ピクセル) - Depth Camera搭載デバイスのみ

現在の160x90 (14,400ピクセル)は**非常に低い**ため、可能な限り向上させる必要があります。

## 実装チェックリスト

### Androidアプリ側での確認事項

1. **ARCore Sessionの設定を確認**
   ```kotlin
   // 現在のカメラ設定を確認
   val currentConfig = session.cameraConfig
   Log.d(TAG, "Current camera config: ${currentConfig.imageSize}")
   ```

2. **利用可能な深度解像度を確認**
   ```kotlin
   // サポートされている設定を確認
   val configList = session.getSupportedCameraConfigs(ArCameraConfigFilter(session))
   for (config in configList) {
       Log.d(TAG, "Available config: ${config.imageSize}")
   }
   ```

3. **深度画像の解像度をログ出力**
   ```kotlin
   val depthImage = frame.acquireDepthImage()
   Log.d(TAG, "Depth image size: ${depthImage.width}x${depthImage.height}")
   ```

### サーバー側での確認

診断スクリプトで確認：
```bash
python diagnose_depth.py <job_id>
```

期待される結果：
- Depth resolution: 320x240以上
- Valid pixels: 10%以上

## 対処法

### 即座に実施可能（サーバー側）

1. **深度前処理の強化**
   - 穴埋め（inpainting）を実装
   - 無効値の補間

2. **TSDFパラメータの調整**
   - `voxel_length`を大きく（0.04m以上）
   - `depth_trunc`を適切に設定（診断結果の99パーセンタイル値）

### 根本的解決（Androidアプリ側）

1. **ARCore Session設定の見直し**
   - カメラ設定で最高解像度を選択
   - Depth APIのバージョンを確認

2. **ARCoreのバージョン更新**
   - 最新バージョンでより高解像度をサポート

3. **Depth Camera搭載デバイスの使用**
   - iPhone 15 Pro / iPad Pro
   - Intel RealSense
   - Azure Kinect

## 参考資料

- [ARCore Depth API Documentation](https://developers.google.com/ar/develop/java/depth)
- [ARCore Camera Configuration](https://developers.google.com/ar/reference/java/com/google/ar/core/ArCameraConfig)

最終更新: 2026-01-08 10:14:57
---

# Android側でのDepth解像度向上ガイド

## 現状の問題

診断結果から以下の問題が判明：
- **深度解像度: 160x90** (14,400ピクセル) - 非常に低い
- **有効深度ピクセル: 0.4%** (99.6%が無効値マーカー)
- これはARCore Depth APIの**デフォルト解像度**で、明示的に解像度を指定していない可能性が高い

## ARCore Depth APIの解像度設定

### ARCore Depth APIの解像度オプション

ARCore Depth APIでは、`ArCameraConfig`または`ArSession`で深度解像度を設定できます。

#### 1. カメラ設定での解像度指定（推奨）

```java
// ARCore Depth APIの解像度を設定
ArSession session = new ArSession(context);

// カメラ設定を取得
ArCameraConfigFilter filter = new ArCameraConfigFilter(session);
ArCameraConfigList configList = session.getSupportedCameraConfigs(filter);

// 深度解像度が高い設定を選択
ArCameraConfig bestConfig = null;
int maxDepthSize = 0;
for (ArCameraConfig config : configList) {
    ArCameraConfig.DepthSensorUsage usage = config.getDepthSensorUsage();
    
    // 深度解像度を確認（直接取得できない場合、ターミナル解像度から推測）
    // より高い解像度の設定を選択
    int depthWidth = config.getImageSize().getWidth();  // 深度は通常カメラ解像度より低い
    if (depthWidth > maxDepthSize) {
        maxDepthSize = depthWidth;
        bestConfig = config;
    }
}

if (bestConfig != null) {
    session.setCameraConfig(bestConfig);
}
```

#### 2. ARCore Sessionの深度設定（直接指定）

```java
// ARCore 1.30以降では、深度解像度をより直接的に制御可能
ArConfig config = new ArConfig(session);
config.setDepthMode(ArConfig.DepthMode.AUTOMATIC);  // または DEPTH_MODE_RAW_DEPTH_ONLY

// 深度解像度の優先順位を設定（利用可能な場合）
// 注意: ARCoreのバージョンによってAPIが異なる可能性があります
```

#### 3. Depth APIでの最大解像度取得

```java
// 利用可能な深度解像度を取得
ArDepthPointCloud depthPointCloud = frame.acquireDepthPointCloud();

// 深度画像の解像度を確認
int depthWidth = depthPointCloud.getWidth();
int depthHeight = depthPointCloud.getHeight();

// より高い解像度が必要な場合、カメラ設定を調整
```

### 実装例（Kotlin/Java）

#### Androidアプリ側での設定

```kotlin
// ARCore Session初期化時に深度解像度を最大にする
fun initializeArCore(context: Context): ArSession? {
    val session = ArSession(context)
    
    try {
        // デフォルト設定を取得
        val defaultConfig = ArConfig(session)
        defaultConfig.depthMode = ArConfig.DepthMode.AUTOMATIC
        
        // サポートされているカメラ設定を確認
        val configFilter = ArCameraConfigFilter(session)
        val configList = session.getSupportedCameraConfigs(configFilter)
        
        // 最大解像度の設定を選択
        var bestConfig: ArCameraConfig? = null
        var maxResolution = 0
        
        for (i in 0 until configList.size) {
            val config = configList[i]
            val imageSize = config.imageSize
            
            // 画像解像度から深度解像度を推測（深度は通常1/4〜1/2）
            val estimatedDepthResolution = imageSize.width * imageSize.height
            
            if (estimatedDepthResolution > maxResolution) {
                maxResolution = estimatedDepthResolution
                bestConfig = config
            }
        }
        
        // 最適な設定を適用
        if (bestConfig != null) {
            session.setCameraConfig(bestConfig)
            Log.d(TAG, "Depth resolution optimized: ${bestConfig.imageSize}")
        }
        
        session.configure(defaultConfig)
        return session
        
    } catch (e: Exception) {
        Log.e(TAG, "ARCore initialization failed", e)
        return null
    }
}
```

#### 深度データ取得時の解像度確認

```kotlin
// フレームごとに深度データを取得
fun processFrame(frame: ArFrame) {
    val depthImage = frame.acquireDepthImage()
    
    if (depthImage != null) {
        val width = depthImage.width
        val height = depthImage.height
        
        Log.d(TAG, "Depth resolution: ${width}x${height}")
        
        // 期待される解像度より低い場合は警告
        if (width < 320 || height < 240) {
            Log.w(TAG, "Low depth resolution detected: ${width}x${height}")
            Log.w(TAG, "Consider adjusting camera config for higher depth resolution")
        }
        
        // 深度データを保存
        saveDepthImage(depthImage, frame.timestamp)
        
        depthImage.close()
    }
}
```

## ARCore Depth解像度の制約

### デバイスによる制約

1. **Depth Camera搭載デバイス** (iPhone 15 Proなど)
   - より高解像度の深度データが取得可能
   - 通常: 256x192, 320x240, 640x480など

2. **推定Depth（Motion Stereo + ML）** (Pixel 7 Proなど)
   - 解像度が制限される（160x90, 256x192など）
   - デバイスの性能とARCoreのバージョンに依存

3. **Depth APIのバージョン**
   - ARCore 1.20以降: より高解像度をサポート
   - 古いバージョン: 解像度が制限される

### 推奨される解像度

- **最小: 256x192** (49,152ピクセル)
- **推奨: 320x240** (76,800ピクセル)
- **理想: 640x480** (307,200ピクセル) - Depth Camera搭載デバイスのみ

現在の160x90 (14,400ピクセル)は**非常に低い**ため、可能な限り向上させる必要があります。

## 実装チェックリスト

### Androidアプリ側での確認事項

1. **ARCore Sessionの設定を確認**
   ```kotlin
   // 現在のカメラ設定を確認
   val currentConfig = session.cameraConfig
   Log.d(TAG, "Current camera config: ${currentConfig.imageSize}")
   ```

2. **利用可能な深度解像度を確認**
   ```kotlin
   // サポートされている設定を確認
   val configList = session.getSupportedCameraConfigs(ArCameraConfigFilter(session))
   for (config in configList) {
       Log.d(TAG, "Available config: ${config.imageSize}")
   }
   ```

3. **深度画像の解像度をログ出力**
   ```kotlin
   val depthImage = frame.acquireDepthImage()
   Log.d(TAG, "Depth image size: ${depthImage.width}x${depthImage.height}")
   ```

### サーバー側での確認

診断スクリプトで確認：
```bash
python diagnose_depth.py <job_id>
```

期待される結果：
- Depth resolution: 320x240以上
- Valid pixels: 10%以上

## 対処法

### 即座に実施可能（サーバー側）

1. **深度前処理の強化**
   - 穴埋め（inpainting）を実装
   - 無効値の補間

2. **TSDFパラメータの調整**
   - `voxel_length`を大きく（0.04m以上）
   - `depth_trunc`を適切に設定（診断結果の99パーセンタイル値）

### 根本的解決（Androidアプリ側）

1. **ARCore Session設定の見直し**
   - カメラ設定で最高解像度を選択
   - Depth APIのバージョンを確認

2. **ARCoreのバージョン更新**
   - 最新バージョンでより高解像度をサポート

3. **Depth Camera搭載デバイスの使用**
   - iPhone 15 Pro / iPad Pro
   - Intel RealSense
   - Azure Kinect

## 参考資料

- [ARCore Depth API Documentation](https://developers.google.com/ar/develop/java/depth)
- [ARCore Camera Configuration](https://developers.google.com/ar/reference/java/com/google/ar/core/ArCameraConfig)

最終更新: 2026-01-08 10:14:57
---

# Android側でのDepth解像度向上ガイド

## 現状の問題

診断結果から以下の問題が判明：
- **深度解像度: 160x90** (14,400ピクセル) - 非常に低い
- **有効深度ピクセル: 0.4%** (99.6%が無効値マーカー)
- これはARCore Depth APIの**デフォルト解像度**で、明示的に解像度を指定していない可能性が高い

## ARCore Depth APIの解像度設定

### ARCore Depth APIの解像度オプション

ARCore Depth APIでは、`ArCameraConfig`または`ArSession`で深度解像度を設定できます。

#### 1. カメラ設定での解像度指定（推奨）

```java
// ARCore Depth APIの解像度を設定
ArSession session = new ArSession(context);

// カメラ設定を取得
ArCameraConfigFilter filter = new ArCameraConfigFilter(session);
ArCameraConfigList configList = session.getSupportedCameraConfigs(filter);

// 深度解像度が高い設定を選択
ArCameraConfig bestConfig = null;
int maxDepthSize = 0;
for (ArCameraConfig config : configList) {
    ArCameraConfig.DepthSensorUsage usage = config.getDepthSensorUsage();
    
    // 深度解像度を確認（直接取得できない場合、ターミナル解像度から推測）
    // より高い解像度の設定を選択
    int depthWidth = config.getImageSize().getWidth();  // 深度は通常カメラ解像度より低い
    if (depthWidth > maxDepthSize) {
        maxDepthSize = depthWidth;
        bestConfig = config;
    }
}

if (bestConfig != null) {
    session.setCameraConfig(bestConfig);
}
```

#### 2. ARCore Sessionの深度設定（直接指定）

```java
// ARCore 1.30以降では、深度解像度をより直接的に制御可能
ArConfig config = new ArConfig(session);
config.setDepthMode(ArConfig.DepthMode.AUTOMATIC);  // または DEPTH_MODE_RAW_DEPTH_ONLY

// 深度解像度の優先順位を設定（利用可能な場合）
// 注意: ARCoreのバージョンによってAPIが異なる可能性があります
```

#### 3. Depth APIでの最大解像度取得

```java
// 利用可能な深度解像度を取得
ArDepthPointCloud depthPointCloud = frame.acquireDepthPointCloud();

// 深度画像の解像度を確認
int depthWidth = depthPointCloud.getWidth();
int depthHeight = depthPointCloud.getHeight();

// より高い解像度が必要な場合、カメラ設定を調整
```

### 実装例（Kotlin/Java）

#### Androidアプリ側での設定

```kotlin
// ARCore Session初期化時に深度解像度を最大にする
fun initializeArCore(context: Context): ArSession? {
    val session = ArSession(context)
    
    try {
        // デフォルト設定を取得
        val defaultConfig = ArConfig(session)
        defaultConfig.depthMode = ArConfig.DepthMode.AUTOMATIC
        
        // サポートされているカメラ設定を確認
        val configFilter = ArCameraConfigFilter(session)
        val configList = session.getSupportedCameraConfigs(configFilter)
        
        // 最大解像度の設定を選択
        var bestConfig: ArCameraConfig? = null
        var maxResolution = 0
        
        for (i in 0 until configList.size) {
            val config = configList[i]
            val imageSize = config.imageSize
            
            // 画像解像度から深度解像度を推測（深度は通常1/4〜1/2）
            val estimatedDepthResolution = imageSize.width * imageSize.height
            
            if (estimatedDepthResolution > maxResolution) {
                maxResolution = estimatedDepthResolution
                bestConfig = config
            }
        }
        
        // 最適な設定を適用
        if (bestConfig != null) {
            session.setCameraConfig(bestConfig)
            Log.d(TAG, "Depth resolution optimized: ${bestConfig.imageSize}")
        }
        
        session.configure(defaultConfig)
        return session
        
    } catch (e: Exception) {
        Log.e(TAG, "ARCore initialization failed", e)
        return null
    }
}
```

#### 深度データ取得時の解像度確認

```kotlin
// フレームごとに深度データを取得
fun processFrame(frame: ArFrame) {
    val depthImage = frame.acquireDepthImage()
    
    if (depthImage != null) {
        val width = depthImage.width
        val height = depthImage.height
        
        Log.d(TAG, "Depth resolution: ${width}x${height}")
        
        // 期待される解像度より低い場合は警告
        if (width < 320 || height < 240) {
            Log.w(TAG, "Low depth resolution detected: ${width}x${height}")
            Log.w(TAG, "Consider adjusting camera config for higher depth resolution")
        }
        
        // 深度データを保存
        saveDepthImage(depthImage, frame.timestamp)
        
        depthImage.close()
    }
}
```

## ARCore Depth解像度の制約

### デバイスによる制約

1. **Depth Camera搭載デバイス** (iPhone 15 Proなど)
   - より高解像度の深度データが取得可能
   - 通常: 256x192, 320x240, 640x480など

2. **推定Depth（Motion Stereo + ML）** (Pixel 7 Proなど)
   - 解像度が制限される（160x90, 256x192など）
   - デバイスの性能とARCoreのバージョンに依存

3. **Depth APIのバージョン**
   - ARCore 1.20以降: より高解像度をサポート
   - 古いバージョン: 解像度が制限される

### 推奨される解像度

- **最小: 256x192** (49,152ピクセル)
- **推奨: 320x240** (76,800ピクセル)
- **理想: 640x480** (307,200ピクセル) - Depth Camera搭載デバイスのみ

現在の160x90 (14,400ピクセル)は**非常に低い**ため、可能な限り向上させる必要があります。

## 実装チェックリスト

### Androidアプリ側での確認事項

1. **ARCore Sessionの設定を確認**
   ```kotlin
   // 現在のカメラ設定を確認
   val currentConfig = session.cameraConfig
   Log.d(TAG, "Current camera config: ${currentConfig.imageSize}")
   ```

2. **利用可能な深度解像度を確認**
   ```kotlin
   // サポートされている設定を確認
   val configList = session.getSupportedCameraConfigs(ArCameraConfigFilter(session))
   for (config in configList) {
       Log.d(TAG, "Available config: ${config.imageSize}")
   }
   ```

3. **深度画像の解像度をログ出力**
   ```kotlin
   val depthImage = frame.acquireDepthImage()
   Log.d(TAG, "Depth image size: ${depthImage.width}x${depthImage.height}")
   ```

### サーバー側での確認

診断スクリプトで確認：
```bash
python diagnose_depth.py <job_id>
```

期待される結果：
- Depth resolution: 320x240以上
- Valid pixels: 10%以上

## 対処法

### 即座に実施可能（サーバー側）

1. **深度前処理の強化**
   - 穴埋め（inpainting）を実装
   - 無効値の補間

2. **TSDFパラメータの調整**
   - `voxel_length`を大きく（0.04m以上）
   - `depth_trunc`を適切に設定（診断結果の99パーセンタイル値）

### 根本的解決（Androidアプリ側）

1. **ARCore Session設定の見直し**
   - カメラ設定で最高解像度を選択
   - Depth APIのバージョンを確認

2. **ARCoreのバージョン更新**
   - 最新バージョンでより高解像度をサポート

3. **Depth Camera搭載デバイスの使用**
   - iPhone 15 Pro / iPad Pro
   - Intel RealSense
   - Azure Kinect

## 参考資料

- [ARCore Depth API Documentation](https://developers.google.com/ar/develop/java/depth)
- [ARCore Camera Configuration](https://developers.google.com/ar/reference/java/com/google/ar/core/ArCameraConfig)

最終更新: 2026-01-08 10:14:57
---

# Android側でのDepth解像度向上ガイド

## 現状の問題

診断結果から以下の問題が判明：
- **深度解像度: 160x90** (14,400ピクセル) - 非常に低い
- **有効深度ピクセル: 0.4%** (99.6%が無効値マーカー)
- これはARCore Depth APIの**デフォルト解像度**で、明示的に解像度を指定していない可能性が高い

## ARCore Depth APIの解像度設定

### ARCore Depth APIの解像度オプション

ARCore Depth APIでは、`ArCameraConfig`または`ArSession`で深度解像度を設定できます。

#### 1. カメラ設定での解像度指定（推奨）

```java
// ARCore Depth APIの解像度を設定
ArSession session = new ArSession(context);

// カメラ設定を取得
ArCameraConfigFilter filter = new ArCameraConfigFilter(session);
ArCameraConfigList configList = session.getSupportedCameraConfigs(filter);

// 深度解像度が高い設定を選択
ArCameraConfig bestConfig = null;
int maxDepthSize = 0;
for (ArCameraConfig config : configList) {
    ArCameraConfig.DepthSensorUsage usage = config.getDepthSensorUsage();
    
    // 深度解像度を確認（直接取得できない場合、ターミナル解像度から推測）
    // より高い解像度の設定を選択
    int depthWidth = config.getImageSize().getWidth();  // 深度は通常カメラ解像度より低い
    if (depthWidth > maxDepthSize) {
        maxDepthSize = depthWidth;
        bestConfig = config;
    }
}

if (bestConfig != null) {
    session.setCameraConfig(bestConfig);
}
```

#### 2. ARCore Sessionの深度設定（直接指定）

```java
// ARCore 1.30以降では、深度解像度をより直接的に制御可能
ArConfig config = new ArConfig(session);
config.setDepthMode(ArConfig.DepthMode.AUTOMATIC);  // または DEPTH_MODE_RAW_DEPTH_ONLY

// 深度解像度の優先順位を設定（利用可能な場合）
// 注意: ARCoreのバージョンによってAPIが異なる可能性があります
```

#### 3. Depth APIでの最大解像度取得

```java
// 利用可能な深度解像度を取得
ArDepthPointCloud depthPointCloud = frame.acquireDepthPointCloud();

// 深度画像の解像度を確認
int depthWidth = depthPointCloud.getWidth();
int depthHeight = depthPointCloud.getHeight();

// より高い解像度が必要な場合、カメラ設定を調整
```

### 実装例（Kotlin/Java）

#### Androidアプリ側での設定

```kotlin
// ARCore Session初期化時に深度解像度を最大にする
fun initializeArCore(context: Context): ArSession? {
    val session = ArSession(context)
    
    try {
        // デフォルト設定を取得
        val defaultConfig = ArConfig(session)
        defaultConfig.depthMode = ArConfig.DepthMode.AUTOMATIC
        
        // サポートされているカメラ設定を確認
        val configFilter = ArCameraConfigFilter(session)
        val configList = session.getSupportedCameraConfigs(configFilter)
        
        // 最大解像度の設定を選択
        var bestConfig: ArCameraConfig? = null
        var maxResolution = 0
        
        for (i in 0 until configList.size) {
            val config = configList[i]
            val imageSize = config.imageSize
            
            // 画像解像度から深度解像度を推測（深度は通常1/4〜1/2）
            val estimatedDepthResolution = imageSize.width * imageSize.height
            
            if (estimatedDepthResolution > maxResolution) {
                maxResolution = estimatedDepthResolution
                bestConfig = config
            }
        }
        
        // 最適な設定を適用
        if (bestConfig != null) {
            session.setCameraConfig(bestConfig)
            Log.d(TAG, "Depth resolution optimized: ${bestConfig.imageSize}")
        }
        
        session.configure(defaultConfig)
        return session
        
    } catch (e: Exception) {
        Log.e(TAG, "ARCore initialization failed", e)
        return null
    }
}
```

#### 深度データ取得時の解像度確認

```kotlin
// フレームごとに深度データを取得
fun processFrame(frame: ArFrame) {
    val depthImage = frame.acquireDepthImage()
    
    if (depthImage != null) {
        val width = depthImage.width
        val height = depthImage.height
        
        Log.d(TAG, "Depth resolution: ${width}x${height}")
        
        // 期待される解像度より低い場合は警告
        if (width < 320 || height < 240) {
            Log.w(TAG, "Low depth resolution detected: ${width}x${height}")
            Log.w(TAG, "Consider adjusting camera config for higher depth resolution")
        }
        
        // 深度データを保存
        saveDepthImage(depthImage, frame.timestamp)
        
        depthImage.close()
    }
}
```

## ARCore Depth解像度の制約

### デバイスによる制約

1. **Depth Camera搭載デバイス** (iPhone 15 Proなど)
   - より高解像度の深度データが取得可能
   - 通常: 256x192, 320x240, 640x480など

2. **推定Depth（Motion Stereo + ML）** (Pixel 7 Proなど)
   - 解像度が制限される（160x90, 256x192など）
   - デバイスの性能とARCoreのバージョンに依存

3. **Depth APIのバージョン**
   - ARCore 1.20以降: より高解像度をサポート
   - 古いバージョン: 解像度が制限される

### 推奨される解像度

- **最小: 256x192** (49,152ピクセル)
- **推奨: 320x240** (76,800ピクセル)
- **理想: 640x480** (307,200ピクセル) - Depth Camera搭載デバイスのみ

現在の160x90 (14,400ピクセル)は**非常に低い**ため、可能な限り向上させる必要があります。

## 実装チェックリスト

### Androidアプリ側での確認事項

1. **ARCore Sessionの設定を確認**
   ```kotlin
   // 現在のカメラ設定を確認
   val currentConfig = session.cameraConfig
   Log.d(TAG, "Current camera config: ${currentConfig.imageSize}")
   ```

2. **利用可能な深度解像度を確認**
   ```kotlin
   // サポートされている設定を確認
   val configList = session.getSupportedCameraConfigs(ArCameraConfigFilter(session))
   for (config in configList) {
       Log.d(TAG, "Available config: ${config.imageSize}")
   }
   ```

3. **深度画像の解像度をログ出力**
   ```kotlin
   val depthImage = frame.acquireDepthImage()
   Log.d(TAG, "Depth image size: ${depthImage.width}x${depthImage.height}")
   ```

### サーバー側での確認

診断スクリプトで確認：
```bash
python diagnose_depth.py <job_id>
```

期待される結果：
- Depth resolution: 320x240以上
- Valid pixels: 10%以上

## 対処法

### 即座に実施可能（サーバー側）

1. **深度前処理の強化**
   - 穴埋め（inpainting）を実装
   - 無効値の補間

2. **TSDFパラメータの調整**
   - `voxel_length`を大きく（0.04m以上）
   - `depth_trunc`を適切に設定（診断結果の99パーセンタイル値）

### 根本的解決（Androidアプリ側）

1. **ARCore Session設定の見直し**
   - カメラ設定で最高解像度を選択
   - Depth APIのバージョンを確認

2. **ARCoreのバージョン更新**
   - 最新バージョンでより高解像度をサポート

3. **Depth Camera搭載デバイスの使用**
   - iPhone 15 Pro / iPad Pro
   - Intel RealSense
   - Azure Kinect

## 参考資料

- [ARCore Depth API Documentation](https://developers.google.com/ar/develop/java/depth)
- [ARCore Camera Configuration](https://developers.google.com/ar/reference/java/com/google/ar/core/ArCameraConfig)

最終更新: 2026-01-08 10:14:57
---

# Android側でのDepth解像度向上ガイド

## 現状の問題

診断結果から以下の問題が判明：
- **深度解像度: 160x90** (14,400ピクセル) - 非常に低い
- **有効深度ピクセル: 0.4%** (99.6%が無効値マーカー)
- これはARCore Depth APIの**デフォルト解像度**で、明示的に解像度を指定していない可能性が高い

## ARCore Depth APIの解像度設定

### ARCore Depth APIの解像度オプション

ARCore Depth APIでは、`ArCameraConfig`または`ArSession`で深度解像度を設定できます。

#### 1. カメラ設定での解像度指定（推奨）

```java
// ARCore Depth APIの解像度を設定
ArSession session = new ArSession(context);

// カメラ設定を取得
ArCameraConfigFilter filter = new ArCameraConfigFilter(session);
ArCameraConfigList configList = session.getSupportedCameraConfigs(filter);

// 深度解像度が高い設定を選択
ArCameraConfig bestConfig = null;
int maxDepthSize = 0;
for (ArCameraConfig config : configList) {
    ArCameraConfig.DepthSensorUsage usage = config.getDepthSensorUsage();
    
    // 深度解像度を確認（直接取得できない場合、ターミナル解像度から推測）
    // より高い解像度の設定を選択
    int depthWidth = config.getImageSize().getWidth();  // 深度は通常カメラ解像度より低い
    if (depthWidth > maxDepthSize) {
        maxDepthSize = depthWidth;
        bestConfig = config;
    }
}

if (bestConfig != null) {
    session.setCameraConfig(bestConfig);
}
```

#### 2. ARCore Sessionの深度設定（直接指定）

```java
// ARCore 1.30以降では、深度解像度をより直接的に制御可能
ArConfig config = new ArConfig(session);
config.setDepthMode(ArConfig.DepthMode.AUTOMATIC);  // または DEPTH_MODE_RAW_DEPTH_ONLY

// 深度解像度の優先順位を設定（利用可能な場合）
// 注意: ARCoreのバージョンによってAPIが異なる可能性があります
```

#### 3. Depth APIでの最大解像度取得

```java
// 利用可能な深度解像度を取得
ArDepthPointCloud depthPointCloud = frame.acquireDepthPointCloud();

// 深度画像の解像度を確認
int depthWidth = depthPointCloud.getWidth();
int depthHeight = depthPointCloud.getHeight();

// より高い解像度が必要な場合、カメラ設定を調整
```

### 実装例（Kotlin/Java）

#### Androidアプリ側での設定

```kotlin
// ARCore Session初期化時に深度解像度を最大にする
fun initializeArCore(context: Context): ArSession? {
    val session = ArSession(context)
    
    try {
        // デフォルト設定を取得
        val defaultConfig = ArConfig(session)
        defaultConfig.depthMode = ArConfig.DepthMode.AUTOMATIC
        
        // サポートされているカメラ設定を確認
        val configFilter = ArCameraConfigFilter(session)
        val configList = session.getSupportedCameraConfigs(configFilter)
        
        // 最大解像度の設定を選択
        var bestConfig: ArCameraConfig? = null
        var maxResolution = 0
        
        for (i in 0 until configList.size) {
            val config = configList[i]
            val imageSize = config.imageSize
            
            // 画像解像度から深度解像度を推測（深度は通常1/4〜1/2）
            val estimatedDepthResolution = imageSize.width * imageSize.height
            
            if (estimatedDepthResolution > maxResolution) {
                maxResolution = estimatedDepthResolution
                bestConfig = config
            }
        }
        
        // 最適な設定を適用
        if (bestConfig != null) {
            session.setCameraConfig(bestConfig)
            Log.d(TAG, "Depth resolution optimized: ${bestConfig.imageSize}")
        }
        
        session.configure(defaultConfig)
        return session
        
    } catch (e: Exception) {
        Log.e(TAG, "ARCore initialization failed", e)
        return null
    }
}
```

#### 深度データ取得時の解像度確認

```kotlin
// フレームごとに深度データを取得
fun processFrame(frame: ArFrame) {
    val depthImage = frame.acquireDepthImage()
    
    if (depthImage != null) {
        val width = depthImage.width
        val height = depthImage.height
        
        Log.d(TAG, "Depth resolution: ${width}x${height}")
        
        // 期待される解像度より低い場合は警告
        if (width < 320 || height < 240) {
            Log.w(TAG, "Low depth resolution detected: ${width}x${height}")
            Log.w(TAG, "Consider adjusting camera config for higher depth resolution")
        }
        
        // 深度データを保存
        saveDepthImage(depthImage, frame.timestamp)
        
        depthImage.close()
    }
}
```

## ARCore Depth解像度の制約

### デバイスによる制約

1. **Depth Camera搭載デバイス** (iPhone 15 Proなど)
   - より高解像度の深度データが取得可能
   - 通常: 256x192, 320x240, 640x480など

2. **推定Depth（Motion Stereo + ML）** (Pixel 7 Proなど)
   - 解像度が制限される（160x90, 256x192など）
   - デバイスの性能とARCoreのバージョンに依存

3. **Depth APIのバージョン**
   - ARCore 1.20以降: より高解像度をサポート
   - 古いバージョン: 解像度が制限される

### 推奨される解像度

- **最小: 256x192** (49,152ピクセル)
- **推奨: 320x240** (76,800ピクセル)
- **理想: 640x480** (307,200ピクセル) - Depth Camera搭載デバイスのみ

現在の160x90 (14,400ピクセル)は**非常に低い**ため、可能な限り向上させる必要があります。

## 実装チェックリスト

### Androidアプリ側での確認事項

1. **ARCore Sessionの設定を確認**
   ```kotlin
   // 現在のカメラ設定を確認
   val currentConfig = session.cameraConfig
   Log.d(TAG, "Current camera config: ${currentConfig.imageSize}")
   ```

2. **利用可能な深度解像度を確認**
   ```kotlin
   // サポートされている設定を確認
   val configList = session.getSupportedCameraConfigs(ArCameraConfigFilter(session))
   for (config in configList) {
       Log.d(TAG, "Available config: ${config.imageSize}")
   }
   ```

3. **深度画像の解像度をログ出力**
   ```kotlin
   val depthImage = frame.acquireDepthImage()
   Log.d(TAG, "Depth image size: ${depthImage.width}x${depthImage.height}")
   ```

### サーバー側での確認

診断スクリプトで確認：
```bash
python diagnose_depth.py <job_id>
```

期待される結果：
- Depth resolution: 320x240以上
- Valid pixels: 10%以上

## 対処法

### 即座に実施可能（サーバー側）

1. **深度前処理の強化**
   - 穴埋め（inpainting）を実装
   - 無効値の補間

2. **TSDFパラメータの調整**
   - `voxel_length`を大きく（0.04m以上）
   - `depth_trunc`を適切に設定（診断結果の99パーセンタイル値）

### 根本的解決（Androidアプリ側）

1. **ARCore Session設定の見直し**
   - カメラ設定で最高解像度を選択
   - Depth APIのバージョンを確認

2. **ARCoreのバージョン更新**
   - 最新バージョンでより高解像度をサポート

3. **Depth Camera搭載デバイスの使用**
   - iPhone 15 Pro / iPad Pro
   - Intel RealSense
   - Azure Kinect

## 参考資料

- [ARCore Depth API Documentation](https://developers.google.com/ar/develop/java/depth)
- [ARCore Camera Configuration](https://developers.google.com/ar/reference/java/com/google/ar/core/ArCameraConfig)

最終更新: 2026-01-08 10:14:57
---

# Android側でのDepth解像度向上ガイド

## 現状の問題

診断結果から以下の問題が判明：
- **深度解像度: 160x90** (14,400ピクセル) - 非常に低い
- **有効深度ピクセル: 0.4%** (99.6%が無効値マーカー)
- これはARCore Depth APIの**デフォルト解像度**で、明示的に解像度を指定していない可能性が高い

## ARCore Depth APIの解像度設定

### ARCore Depth APIの解像度オプション

ARCore Depth APIでは、`ArCameraConfig`または`ArSession`で深度解像度を設定できます。

#### 1. カメラ設定での解像度指定（推奨）

```java
// ARCore Depth APIの解像度を設定
ArSession session = new ArSession(context);

// カメラ設定を取得
ArCameraConfigFilter filter = new ArCameraConfigFilter(session);
ArCameraConfigList configList = session.getSupportedCameraConfigs(filter);

// 深度解像度が高い設定を選択
ArCameraConfig bestConfig = null;
int maxDepthSize = 0;
for (ArCameraConfig config : configList) {
    ArCameraConfig.DepthSensorUsage usage = config.getDepthSensorUsage();
    
    // 深度解像度を確認（直接取得できない場合、ターミナル解像度から推測）
    // より高い解像度の設定を選択
    int depthWidth = config.getImageSize().getWidth();  // 深度は通常カメラ解像度より低い
    if (depthWidth > maxDepthSize) {
        maxDepthSize = depthWidth;
        bestConfig = config;
    }
}

if (bestConfig != null) {
    session.setCameraConfig(bestConfig);
}
```

#### 2. ARCore Sessionの深度設定（直接指定）

```java
// ARCore 1.30以降では、深度解像度をより直接的に制御可能
ArConfig config = new ArConfig(session);
config.setDepthMode(ArConfig.DepthMode.AUTOMATIC);  // または DEPTH_MODE_RAW_DEPTH_ONLY

// 深度解像度の優先順位を設定（利用可能な場合）
// 注意: ARCoreのバージョンによってAPIが異なる可能性があります
```

#### 3. Depth APIでの最大解像度取得

```java
// 利用可能な深度解像度を取得
ArDepthPointCloud depthPointCloud = frame.acquireDepthPointCloud();

// 深度画像の解像度を確認
int depthWidth = depthPointCloud.getWidth();
int depthHeight = depthPointCloud.getHeight();

// より高い解像度が必要な場合、カメラ設定を調整
```

### 実装例（Kotlin/Java）

#### Androidアプリ側での設定

```kotlin
// ARCore Session初期化時に深度解像度を最大にする
fun initializeArCore(context: Context): ArSession? {
    val session = ArSession(context)
    
    try {
        // デフォルト設定を取得
        val defaultConfig = ArConfig(session)
        defaultConfig.depthMode = ArConfig.DepthMode.AUTOMATIC
        
        // サポートされているカメラ設定を確認
        val configFilter = ArCameraConfigFilter(session)
        val configList = session.getSupportedCameraConfigs(configFilter)
        
        // 最大解像度の設定を選択
        var bestConfig: ArCameraConfig? = null
        var maxResolution = 0
        
        for (i in 0 until configList.size) {
            val config = configList[i]
            val imageSize = config.imageSize
            
            // 画像解像度から深度解像度を推測（深度は通常1/4〜1/2）
            val estimatedDepthResolution = imageSize.width * imageSize.height
            
            if (estimatedDepthResolution > maxResolution) {
                maxResolution = estimatedDepthResolution
                bestConfig = config
            }
        }
        
        // 最適な設定を適用
        if (bestConfig != null) {
            session.setCameraConfig(bestConfig)
            Log.d(TAG, "Depth resolution optimized: ${bestConfig.imageSize}")
        }
        
        session.configure(defaultConfig)
        return session
        
    } catch (e: Exception) {
        Log.e(TAG, "ARCore initialization failed", e)
        return null
    }
}
```

#### 深度データ取得時の解像度確認

```kotlin
// フレームごとに深度データを取得
fun processFrame(frame: ArFrame) {
    val depthImage = frame.acquireDepthImage()
    
    if (depthImage != null) {
        val width = depthImage.width
        val height = depthImage.height
        
        Log.d(TAG, "Depth resolution: ${width}x${height}")
        
        // 期待される解像度より低い場合は警告
        if (width < 320 || height < 240) {
            Log.w(TAG, "Low depth resolution detected: ${width}x${height}")
            Log.w(TAG, "Consider adjusting camera config for higher depth resolution")
        }
        
        // 深度データを保存
        saveDepthImage(depthImage, frame.timestamp)
        
        depthImage.close()
    }
}
```

## ARCore Depth解像度の制約

### デバイスによる制約

1. **Depth Camera搭載デバイス** (iPhone 15 Proなど)
   - より高解像度の深度データが取得可能
   - 通常: 256x192, 320x240, 640x480など

2. **推定Depth（Motion Stereo + ML）** (Pixel 7 Proなど)
   - 解像度が制限される（160x90, 256x192など）
   - デバイスの性能とARCoreのバージョンに依存

3. **Depth APIのバージョン**
   - ARCore 1.20以降: より高解像度をサポート
   - 古いバージョン: 解像度が制限される

### 推奨される解像度

- **最小: 256x192** (49,152ピクセル)
- **推奨: 320x240** (76,800ピクセル)
- **理想: 640x480** (307,200ピクセル) - Depth Camera搭載デバイスのみ

現在の160x90 (14,400ピクセル)は**非常に低い**ため、可能な限り向上させる必要があります。

## 実装チェックリスト

### Androidアプリ側での確認事項

1. **ARCore Sessionの設定を確認**
   ```kotlin
   // 現在のカメラ設定を確認
   val currentConfig = session.cameraConfig
   Log.d(TAG, "Current camera config: ${currentConfig.imageSize}")
   ```

2. **利用可能な深度解像度を確認**
   ```kotlin
   // サポートされている設定を確認
   val configList = session.getSupportedCameraConfigs(ArCameraConfigFilter(session))
   for (config in configList) {
       Log.d(TAG, "Available config: ${config.imageSize}")
   }
   ```

3. **深度画像の解像度をログ出力**
   ```kotlin
   val depthImage = frame.acquireDepthImage()
   Log.d(TAG, "Depth image size: ${depthImage.width}x${depthImage.height}")
   ```

### サーバー側での確認

診断スクリプトで確認：
```bash
python diagnose_depth.py <job_id>
```

期待される結果：
- Depth resolution: 320x240以上
- Valid pixels: 10%以上

## 対処法

### 即座に実施可能（サーバー側）

1. **深度前処理の強化**
   - 穴埋め（inpainting）を実装
   - 無効値の補間

2. **TSDFパラメータの調整**
   - `voxel_length`を大きく（0.04m以上）
   - `depth_trunc`を適切に設定（診断結果の99パーセンタイル値）

### 根本的解決（Androidアプリ側）

1. **ARCore Session設定の見直し**
   - カメラ設定で最高解像度を選択
   - Depth APIのバージョンを確認

2. **ARCoreのバージョン更新**
   - 最新バージョンでより高解像度をサポート

3. **Depth Camera搭載デバイスの使用**
   - iPhone 15 Pro / iPad Pro
   - Intel RealSense
   - Azure Kinect

## 参考資料

- [ARCore Depth API Documentation](https://developers.google.com/ar/develop/java/depth)
- [ARCore Camera Configuration](https://developers.google.com/ar/reference/java/com/google/ar/core/ArCameraConfig)

最終更新: 2026-01-08 10:14:57
---

# Android側でのDepth解像度向上ガイド

## 現状の問題

診断結果から以下の問題が判明：
- **深度解像度: 160x90** (14,400ピクセル) - 非常に低い
- **有効深度ピクセル: 0.4%** (99.6%が無効値マーカー)
- これはARCore Depth APIの**デフォルト解像度**で、明示的に解像度を指定していない可能性が高い

## ARCore Depth APIの解像度設定

### ARCore Depth APIの解像度オプション

ARCore Depth APIでは、`ArCameraConfig`または`ArSession`で深度解像度を設定できます。

#### 1. カメラ設定での解像度指定（推奨）

```java
// ARCore Depth APIの解像度を設定
ArSession session = new ArSession(context);

// カメラ設定を取得
ArCameraConfigFilter filter = new ArCameraConfigFilter(session);
ArCameraConfigList configList = session.getSupportedCameraConfigs(filter);

// 深度解像度が高い設定を選択
ArCameraConfig bestConfig = null;
int maxDepthSize = 0;
for (ArCameraConfig config : configList) {
    ArCameraConfig.DepthSensorUsage usage = config.getDepthSensorUsage();
    
    // 深度解像度を確認（直接取得できない場合、ターミナル解像度から推測）
    // より高い解像度の設定を選択
    int depthWidth = config.getImageSize().getWidth();  // 深度は通常カメラ解像度より低い
    if (depthWidth > maxDepthSize) {
        maxDepthSize = depthWidth;
        bestConfig = config;
    }
}

if (bestConfig != null) {
    session.setCameraConfig(bestConfig);
}
```

#### 2. ARCore Sessionの深度設定（直接指定）

```java
// ARCore 1.30以降では、深度解像度をより直接的に制御可能
ArConfig config = new ArConfig(session);
config.setDepthMode(ArConfig.DepthMode.AUTOMATIC);  // または DEPTH_MODE_RAW_DEPTH_ONLY

// 深度解像度の優先順位を設定（利用可能な場合）
// 注意: ARCoreのバージョンによってAPIが異なる可能性があります
```

#### 3. Depth APIでの最大解像度取得

```java
// 利用可能な深度解像度を取得
ArDepthPointCloud depthPointCloud = frame.acquireDepthPointCloud();

// 深度画像の解像度を確認
int depthWidth = depthPointCloud.getWidth();
int depthHeight = depthPointCloud.getHeight();

// より高い解像度が必要な場合、カメラ設定を調整
```

### 実装例（Kotlin/Java）

#### Androidアプリ側での設定

```kotlin
// ARCore Session初期化時に深度解像度を最大にする
fun initializeArCore(context: Context): ArSession? {
    val session = ArSession(context)
    
    try {
        // デフォルト設定を取得
        val defaultConfig = ArConfig(session)
        defaultConfig.depthMode = ArConfig.DepthMode.AUTOMATIC
        
        // サポートされているカメラ設定を確認
        val configFilter = ArCameraConfigFilter(session)
        val configList = session.getSupportedCameraConfigs(configFilter)
        
        // 最大解像度の設定を選択
        var bestConfig: ArCameraConfig? = null
        var maxResolution = 0
        
        for (i in 0 until configList.size) {
            val config = configList[i]
            val imageSize = config.imageSize
            
            // 画像解像度から深度解像度を推測（深度は通常1/4〜1/2）
            val estimatedDepthResolution = imageSize.width * imageSize.height
            
            if (estimatedDepthResolution > maxResolution) {
                maxResolution = estimatedDepthResolution
                bestConfig = config
            }
        }
        
        // 最適な設定を適用
        if (bestConfig != null) {
            session.setCameraConfig(bestConfig)
            Log.d(TAG, "Depth resolution optimized: ${bestConfig.imageSize}")
        }
        
        session.configure(defaultConfig)
        return session
        
    } catch (e: Exception) {
        Log.e(TAG, "ARCore initialization failed", e)
        return null
    }
}
```

#### 深度データ取得時の解像度確認

```kotlin
// フレームごとに深度データを取得
fun processFrame(frame: ArFrame) {
    val depthImage = frame.acquireDepthImage()
    
    if (depthImage != null) {
        val width = depthImage.width
        val height = depthImage.height
        
        Log.d(TAG, "Depth resolution: ${width}x${height}")
        
        // 期待される解像度より低い場合は警告
        if (width < 320 || height < 240) {
            Log.w(TAG, "Low depth resolution detected: ${width}x${height}")
            Log.w(TAG, "Consider adjusting camera config for higher depth resolution")
        }
        
        // 深度データを保存
        saveDepthImage(depthImage, frame.timestamp)
        
        depthImage.close()
    }
}
```

## ARCore Depth解像度の制約

### デバイスによる制約

1. **Depth Camera搭載デバイス** (iPhone 15 Proなど)
   - より高解像度の深度データが取得可能
   - 通常: 256x192, 320x240, 640x480など

2. **推定Depth（Motion Stereo + ML）** (Pixel 7 Proなど)
   - 解像度が制限される（160x90, 256x192など）
   - デバイスの性能とARCoreのバージョンに依存

3. **Depth APIのバージョン**
   - ARCore 1.20以降: より高解像度をサポート
   - 古いバージョン: 解像度が制限される

### 推奨される解像度

- **最小: 256x192** (49,152ピクセル)
- **推奨: 320x240** (76,800ピクセル)
- **理想: 640x480** (307,200ピクセル) - Depth Camera搭載デバイスのみ

現在の160x90 (14,400ピクセル)は**非常に低い**ため、可能な限り向上させる必要があります。

## 実装チェックリスト

### Androidアプリ側での確認事項

1. **ARCore Sessionの設定を確認**
   ```kotlin
   // 現在のカメラ設定を確認
   val currentConfig = session.cameraConfig
   Log.d(TAG, "Current camera config: ${currentConfig.imageSize}")
   ```

2. **利用可能な深度解像度を確認**
   ```kotlin
   // サポートされている設定を確認
   val configList = session.getSupportedCameraConfigs(ArCameraConfigFilter(session))
   for (config in configList) {
       Log.d(TAG, "Available config: ${config.imageSize}")
   }
   ```

3. **深度画像の解像度をログ出力**
   ```kotlin
   val depthImage = frame.acquireDepthImage()
   Log.d(TAG, "Depth image size: ${depthImage.width}x${depthImage.height}")
   ```

### サーバー側での確認

診断スクリプトで確認：
```bash
python diagnose_depth.py <job_id>
```

期待される結果：
- Depth resolution: 320x240以上
- Valid pixels: 10%以上

## 対処法

### 即座に実施可能（サーバー側）

1. **深度前処理の強化**
   - 穴埋め（inpainting）を実装
   - 無効値の補間

2. **TSDFパラメータの調整**
   - `voxel_length`を大きく（0.04m以上）
   - `depth_trunc`を適切に設定（診断結果の99パーセンタイル値）

### 根本的解決（Androidアプリ側）

1. **ARCore Session設定の見直し**
   - カメラ設定で最高解像度を選択
   - Depth APIのバージョンを確認

2. **ARCoreのバージョン更新**
   - 最新バージョンでより高解像度をサポート

3. **Depth Camera搭載デバイスの使用**
   - iPhone 15 Pro / iPad Pro
   - Intel RealSense
   - Azure Kinect

## 参考資料

- [ARCore Depth API Documentation](https://developers.google.com/ar/develop/java/depth)
- [ARCore Camera Configuration](https://developers.google.com/ar/reference/java/com/google/ar/core/ArCameraConfig)
最終更新: 2026-01-08 10:14:57
---

# Android側でのDepth解像度向上ガイド

## 現状の問題

診断結果から以下の問題が判明：
- **深度解像度: 160x90** (14,400ピクセル) - 非常に低い
- **有効深度ピクセル: 0.4%** (99.6%が無効値マーカー)
- これはARCore Depth APIの**デフォルト解像度**で、明示的に解像度を指定していない可能性が高い

## ARCore Depth APIの解像度設定

### ARCore Depth APIの解像度オプション

ARCore Depth APIでは、`ArCameraConfig`または`ArSession`で深度解像度を設定できます。

#### 1. カメラ設定での解像度指定（推奨）

```java
// ARCore Depth APIの解像度を設定
ArSession session = new ArSession(context);

// カメラ設定を取得
ArCameraConfigFilter filter = new ArCameraConfigFilter(session);
ArCameraConfigList configList = session.getSupportedCameraConfigs(filter);

// 深度解像度が高い設定を選択
ArCameraConfig bestConfig = null;
int maxDepthSize = 0;
for (ArCameraConfig config : configList) {
    ArCameraConfig.DepthSensorUsage usage = config.getDepthSensorUsage();
    
    // 深度解像度を確認（直接取得できない場合、ターミナル解像度から推測）
    // より高い解像度の設定を選択
    int depthWidth = config.getImageSize().getWidth();  // 深度は通常カメラ解像度より低い
    if (depthWidth > maxDepthSize) {
        maxDepthSize = depthWidth;
        bestConfig = config;
    }
}

if (bestConfig != null) {
    session.setCameraConfig(bestConfig);
}
```

#### 2. ARCore Sessionの深度設定（直接指定）

```java
// ARCore 1.30以降では、深度解像度をより直接的に制御可能
ArConfig config = new ArConfig(session);
config.setDepthMode(ArConfig.DepthMode.AUTOMATIC);  // または DEPTH_MODE_RAW_DEPTH_ONLY

// 深度解像度の優先順位を設定（利用可能な場合）
// 注意: ARCoreのバージョンによってAPIが異なる可能性があります
```

#### 3. Depth APIでの最大解像度取得

```java
// 利用可能な深度解像度を取得
ArDepthPointCloud depthPointCloud = frame.acquireDepthPointCloud();

// 深度画像の解像度を確認
int depthWidth = depthPointCloud.getWidth();
int depthHeight = depthPointCloud.getHeight();

// より高い解像度が必要な場合、カメラ設定を調整
```

### 実装例（Kotlin/Java）

#### Androidアプリ側での設定

```kotlin
// ARCore Session初期化時に深度解像度を最大にする
fun initializeArCore(context: Context): ArSession? {
    val session = ArSession(context)
    
    try {
        // デフォルト設定を取得
        val defaultConfig = ArConfig(session)
        defaultConfig.depthMode = ArConfig.DepthMode.AUTOMATIC
        
        // サポートされているカメラ設定を確認
        val configFilter = ArCameraConfigFilter(session)
        val configList = session.getSupportedCameraConfigs(configFilter)
        
        // 最大解像度の設定を選択
        var bestConfig: ArCameraConfig? = null
        var maxResolution = 0
        
        for (i in 0 until configList.size) {
            val config = configList[i]
            val imageSize = config.imageSize
            
            // 画像解像度から深度解像度を推測（深度は通常1/4〜1/2）
            val estimatedDepthResolution = imageSize.width * imageSize.height
            
            if (estimatedDepthResolution > maxResolution) {
                maxResolution = estimatedDepthResolution
                bestConfig = config
            }
        }
        
        // 最適な設定を適用
        if (bestConfig != null) {
            session.setCameraConfig(bestConfig)
            Log.d(TAG, "Depth resolution optimized: ${bestConfig.imageSize}")
        }
        
        session.configure(defaultConfig)
        return session
        
    } catch (e: Exception) {
        Log.e(TAG, "ARCore initialization failed", e)
        return null
    }
}
```

#### 深度データ取得時の解像度確認

```kotlin
// フレームごとに深度データを取得
fun processFrame(frame: ArFrame) {
    val depthImage = frame.acquireDepthImage()
    
    if (depthImage != null) {
        val width = depthImage.width
        val height = depthImage.height
        
        Log.d(TAG, "Depth resolution: ${width}x${height}")
        
        // 期待される解像度より低い場合は警告
        if (width < 320 || height < 240) {
            Log.w(TAG, "Low depth resolution detected: ${width}x${height}")
            Log.w(TAG, "Consider adjusting camera config for higher depth resolution")
        }
        
        // 深度データを保存
        saveDepthImage(depthImage, frame.timestamp)
        
        depthImage.close()
    }
}
```

## ARCore Depth解像度の制約

### デバイスによる制約

1. **Depth Camera搭載デバイス** (iPhone 15 Proなど)
   - より高解像度の深度データが取得可能
   - 通常: 256x192, 320x240, 640x480など

2. **推定Depth（Motion Stereo + ML）** (Pixel 7 Proなど)
   - 解像度が制限される（160x90, 256x192など）
   - デバイスの性能とARCoreのバージョンに依存

3. **Depth APIのバージョン**
   - ARCore 1.20以降: より高解像度をサポート
   - 古いバージョン: 解像度が制限される

### 推奨される解像度

- **最小: 256x192** (49,152ピクセル)
- **推奨: 320x240** (76,800ピクセル)
- **理想: 640x480** (307,200ピクセル) - Depth Camera搭載デバイスのみ

現在の160x90 (14,400ピクセル)は**非常に低い**ため、可能な限り向上させる必要があります。

## 実装チェックリスト

### Androidアプリ側での確認事項

1. **ARCore Sessionの設定を確認**
   ```kotlin
   // 現在のカメラ設定を確認
   val currentConfig = session.cameraConfig
   Log.d(TAG, "Current camera config: ${currentConfig.imageSize}")
   ```

2. **利用可能な深度解像度を確認**
   ```kotlin
   // サポートされている設定を確認
   val configList = session.getSupportedCameraConfigs(ArCameraConfigFilter(session))
   for (config in configList) {
       Log.d(TAG, "Available config: ${config.imageSize}")
   }
   ```

3. **深度画像の解像度をログ出力**
   ```kotlin
   val depthImage = frame.acquireDepthImage()
   Log.d(TAG, "Depth image size: ${depthImage.width}x${depthImage.height}")
   ```

### サーバー側での確認

診断スクリプトで確認：
```bash
python diagnose_depth.py <job_id>
```

期待される結果：
- Depth resolution: 320x240以上
- Valid pixels: 10%以上

## 対処法

### 即座に実施可能（サーバー側）

1. **深度前処理の強化**
   - 穴埋め（inpainting）を実装
   - 無効値の補間

2. **TSDFパラメータの調整**
   - `voxel_length`を大きく（0.04m以上）
   - `depth_trunc`を適切に設定（診断結果の99パーセンタイル値）

### 根本的解決（Androidアプリ側）

1. **ARCore Session設定の見直し**
   - カメラ設定で最高解像度を選択
   - Depth APIのバージョンを確認

2. **ARCoreのバージョン更新**
   - 最新バージョンでより高解像度をサポート

3. **Depth Camera搭載デバイスの使用**
   - iPhone 15 Pro / iPad Pro
   - Intel RealSense
   - Azure Kinect

## 参考資料

- [ARCore Depth API Documentation](https://developers.google.com/ar/develop/java/depth)
- [ARCore Camera Configuration](https://developers.google.com/ar/reference/java/com/google/ar/core/ArCameraConfig)

最終更新: 2026-01-08 10:14:57
---

# Android側でのDepth解像度向上ガイド

## 現状の問題

診断結果から以下の問題が判明：
- **深度解像度: 160x90** (14,400ピクセル) - 非常に低い
- **有効深度ピクセル: 0.4%** (99.6%が無効値マーカー)
- これはARCore Depth APIの**デフォルト解像度**で、明示的に解像度を指定していない可能性が高い

## ARCore Depth APIの解像度設定

### ARCore Depth APIの解像度オプション

ARCore Depth APIでは、`ArCameraConfig`または`ArSession`で深度解像度を設定できます。

#### 1. カメラ設定での解像度指定（推奨）

```java
// ARCore Depth APIの解像度を設定
ArSession session = new ArSession(context);

// カメラ設定を取得
ArCameraConfigFilter filter = new ArCameraConfigFilter(session);
ArCameraConfigList configList = session.getSupportedCameraConfigs(filter);

// 深度解像度が高い設定を選択
ArCameraConfig bestConfig = null;
int maxDepthSize = 0;
for (ArCameraConfig config : configList) {
    ArCameraConfig.DepthSensorUsage usage = config.getDepthSensorUsage();
    
    // 深度解像度を確認（直接取得できない場合、ターミナル解像度から推測）
    // より高い解像度の設定を選択
    int depthWidth = config.getImageSize().getWidth();  // 深度は通常カメラ解像度より低い
    if (depthWidth > maxDepthSize) {
        maxDepthSize = depthWidth;
        bestConfig = config;
    }
}

if (bestConfig != null) {
    session.setCameraConfig(bestConfig);
}
```

#### 2. ARCore Sessionの深度設定（直接指定）

```java
// ARCore 1.30以降では、深度解像度をより直接的に制御可能
ArConfig config = new ArConfig(session);
config.setDepthMode(ArConfig.DepthMode.AUTOMATIC);  // または DEPTH_MODE_RAW_DEPTH_ONLY

// 深度解像度の優先順位を設定（利用可能な場合）
// 注意: ARCoreのバージョンによってAPIが異なる可能性があります
```

#### 3. Depth APIでの最大解像度取得

```java
// 利用可能な深度解像度を取得
ArDepthPointCloud depthPointCloud = frame.acquireDepthPointCloud();

// 深度画像の解像度を確認
int depthWidth = depthPointCloud.getWidth();
int depthHeight = depthPointCloud.getHeight();

// より高い解像度が必要な場合、カメラ設定を調整
```

### 実装例（Kotlin/Java）

#### Androidアプリ側での設定

```kotlin
// ARCore Session初期化時に深度解像度を最大にする
fun initializeArCore(context: Context): ArSession? {
    val session = ArSession(context)
    
    try {
        // デフォルト設定を取得
        val defaultConfig = ArConfig(session)
        defaultConfig.depthMode = ArConfig.DepthMode.AUTOMATIC
        
        // サポートされているカメラ設定を確認
        val configFilter = ArCameraConfigFilter(session)
        val configList = session.getSupportedCameraConfigs(configFilter)
        
        // 最大解像度の設定を選択
        var bestConfig: ArCameraConfig? = null
        var maxResolution = 0
        
        for (i in 0 until configList.size) {
            val config = configList[i]
            val imageSize = config.imageSize
            
            // 画像解像度から深度解像度を推測（深度は通常1/4〜1/2）
            val estimatedDepthResolution = imageSize.width * imageSize.height
            
            if (estimatedDepthResolution > maxResolution) {
                maxResolution = estimatedDepthResolution
                bestConfig = config
            }
        }
        
        // 最適な設定を適用
        if (bestConfig != null) {
            session.setCameraConfig(bestConfig)
            Log.d(TAG, "Depth resolution optimized: ${bestConfig.imageSize}")
        }
        
        session.configure(defaultConfig)
        return session
        
    } catch (e: Exception) {
        Log.e(TAG, "ARCore initialization failed", e)
        return null
    }
}
```

#### 深度データ取得時の解像度確認

```kotlin
// フレームごとに深度データを取得
fun processFrame(frame: ArFrame) {
    val depthImage = frame.acquireDepthImage()
    
    if (depthImage != null) {
        val width = depthImage.width
        val height = depthImage.height
        
        Log.d(TAG, "Depth resolution: ${width}x${height}")
        
        // 期待される解像度より低い場合は警告
        if (width < 320 || height < 240) {
            Log.w(TAG, "Low depth resolution detected: ${width}x${height}")
            Log.w(TAG, "Consider adjusting camera config for higher depth resolution")
        }
        
        // 深度データを保存
        saveDepthImage(depthImage, frame.timestamp)
        
        depthImage.close()
    }
}
```

## ARCore Depth解像度の制約

### デバイスによる制約

1. **Depth Camera搭載デバイス** (iPhone 15 Proなど)
   - より高解像度の深度データが取得可能
   - 通常: 256x192, 320x240, 640x480など

2. **推定Depth（Motion Stereo + ML）** (Pixel 7 Proなど)
   - 解像度が制限される（160x90, 256x192など）
   - デバイスの性能とARCoreのバージョンに依存

3. **Depth APIのバージョン**
   - ARCore 1.20以降: より高解像度をサポート
   - 古いバージョン: 解像度が制限される

### 推奨される解像度

- **最小: 256x192** (49,152ピクセル)
- **推奨: 320x240** (76,800ピクセル)
- **理想: 640x480** (307,200ピクセル) - Depth Camera搭載デバイスのみ

現在の160x90 (14,400ピクセル)は**非常に低い**ため、可能な限り向上させる必要があります。

## 実装チェックリスト

### Androidアプリ側での確認事項

1. **ARCore Sessionの設定を確認**
   ```kotlin
   // 現在のカメラ設定を確認
   val currentConfig = session.cameraConfig
   Log.d(TAG, "Current camera config: ${currentConfig.imageSize}")
   ```

2. **利用可能な深度解像度を確認**
   ```kotlin
   // サポートされている設定を確認
   val configList = session.getSupportedCameraConfigs(ArCameraConfigFilter(session))
   for (config in configList) {
       Log.d(TAG, "Available config: ${config.imageSize}")
   }
   ```

3. **深度画像の解像度をログ出力**
   ```kotlin
   val depthImage = frame.acquireDepthImage()
   Log.d(TAG, "Depth image size: ${depthImage.width}x${depthImage.height}")
   ```

### サーバー側での確認

診断スクリプトで確認：
```bash
python diagnose_depth.py <job_id>
```

期待される結果：
- Depth resolution: 320x240以上
- Valid pixels: 10%以上

## 対処法

### 即座に実施可能（サーバー側）

1. **深度前処理の強化**
   - 穴埋め（inpainting）を実装
   - 無効値の補間

2. **TSDFパラメータの調整**
   - `voxel_length`を大きく（0.04m以上）
   - `depth_trunc`を適切に設定（診断結果の99パーセンタイル値）

### 根本的解決（Androidアプリ側）

1. **ARCore Session設定の見直し**
   - カメラ設定で最高解像度を選択
   - Depth APIのバージョンを確認

2. **ARCoreのバージョン更新**
   - 最新バージョンでより高解像度をサポート

3. **Depth Camera搭載デバイスの使用**
   - iPhone 15 Pro / iPad Pro
   - Intel RealSense
   - Azure Kinect

## 参考資料

- [ARCore Depth API Documentation](https://developers.google.com/ar/develop/java/depth)
- [ARCore Camera Configuration](https://developers.google.com/ar/reference/java/com/google/ar/core/ArCameraConfig)

最終更新: 2026-01-08 10:14:57
---

# Android側でのDepth解像度向上ガイド

## 現状の問題

診断結果から以下の問題が判明：
- **深度解像度: 160x90** (14,400ピクセル) - 非常に低い
- **有効深度ピクセル: 0.4%** (99.6%が無効値マーカー)
- これはARCore Depth APIの**デフォルト解像度**で、明示的に解像度を指定していない可能性が高い

## ARCore Depth APIの解像度設定

### ARCore Depth APIの解像度オプション

ARCore Depth APIでは、`ArCameraConfig`または`ArSession`で深度解像度を設定できます。

#### 1. カメラ設定での解像度指定（推奨）

```java
// ARCore Depth APIの解像度を設定
ArSession session = new ArSession(context);

// カメラ設定を取得
ArCameraConfigFilter filter = new ArCameraConfigFilter(session);
ArCameraConfigList configList = session.getSupportedCameraConfigs(filter);

// 深度解像度が高い設定を選択
ArCameraConfig bestConfig = null;
int maxDepthSize = 0;
for (ArCameraConfig config : configList) {
    ArCameraConfig.DepthSensorUsage usage = config.getDepthSensorUsage();
    
    // 深度解像度を確認（直接取得できない場合、ターミナル解像度から推測）
    // より高い解像度の設定を選択
    int depthWidth = config.getImageSize().getWidth();  // 深度は通常カメラ解像度より低い
    if (depthWidth > maxDepthSize) {
        maxDepthSize = depthWidth;
        bestConfig = config;
    }
}

if (bestConfig != null) {
    session.setCameraConfig(bestConfig);
}
```

#### 2. ARCore Sessionの深度設定（直接指定）

```java
// ARCore 1.30以降では、深度解像度をより直接的に制御可能
ArConfig config = new ArConfig(session);
config.setDepthMode(ArConfig.DepthMode.AUTOMATIC);  // または DEPTH_MODE_RAW_DEPTH_ONLY

// 深度解像度の優先順位を設定（利用可能な場合）
// 注意: ARCoreのバージョンによってAPIが異なる可能性があります
```

#### 3. Depth APIでの最大解像度取得

```java
// 利用可能な深度解像度を取得
ArDepthPointCloud depthPointCloud = frame.acquireDepthPointCloud();

// 深度画像の解像度を確認
int depthWidth = depthPointCloud.getWidth();
int depthHeight = depthPointCloud.getHeight();

// より高い解像度が必要な場合、カメラ設定を調整
```

### 実装例（Kotlin/Java）

#### Androidアプリ側での設定

```kotlin
// ARCore Session初期化時に深度解像度を最大にする
fun initializeArCore(context: Context): ArSession? {
    val session = ArSession(context)
    
    try {
        // デフォルト設定を取得
        val defaultConfig = ArConfig(session)
        defaultConfig.depthMode = ArConfig.DepthMode.AUTOMATIC
        
        // サポートされているカメラ設定を確認
        val configFilter = ArCameraConfigFilter(session)
        val configList = session.getSupportedCameraConfigs(configFilter)
        
        // 最大解像度の設定を選択
        var bestConfig: ArCameraConfig? = null
        var maxResolution = 0
        
        for (i in 0 until configList.size) {
            val config = configList[i]
            val imageSize = config.imageSize
            
            // 画像解像度から深度解像度を推測（深度は通常1/4〜1/2）
            val estimatedDepthResolution = imageSize.width * imageSize.height
            
            if (estimatedDepthResolution > maxResolution) {
                maxResolution = estimatedDepthResolution
                bestConfig = config
            }
        }
        
        // 最適な設定を適用
        if (bestConfig != null) {
            session.setCameraConfig(bestConfig)
            Log.d(TAG, "Depth resolution optimized: ${bestConfig.imageSize}")
        }
        
        session.configure(defaultConfig)
        return session
        
    } catch (e: Exception) {
        Log.e(TAG, "ARCore initialization failed", e)
        return null
    }
}
```

#### 深度データ取得時の解像度確認

```kotlin
// フレームごとに深度データを取得
fun processFrame(frame: ArFrame) {
    val depthImage = frame.acquireDepthImage()
    
    if (depthImage != null) {
        val width = depthImage.width
        val height = depthImage.height
        
        Log.d(TAG, "Depth resolution: ${width}x${height}")
        
        // 期待される解像度より低い場合は警告
        if (width < 320 || height < 240) {
            Log.w(TAG, "Low depth resolution detected: ${width}x${height}")
            Log.w(TAG, "Consider adjusting camera config for higher depth resolution")
        }
        
        // 深度データを保存
        saveDepthImage(depthImage, frame.timestamp)
        
        depthImage.close()
    }
}
```

## ARCore Depth解像度の制約

### デバイスによる制約

1. **Depth Camera搭載デバイス** (iPhone 15 Proなど)
   - より高解像度の深度データが取得可能
   - 通常: 256x192, 320x240, 640x480など

2. **推定Depth（Motion Stereo + ML）** (Pixel 7 Proなど)
   - 解像度が制限される（160x90, 256x192など）
   - デバイスの性能とARCoreのバージョンに依存

3. **Depth APIのバージョン**
   - ARCore 1.20以降: より高解像度をサポート
   - 古いバージョン: 解像度が制限される

### 推奨される解像度

- **最小: 256x192** (49,152ピクセル)
- **推奨: 320x240** (76,800ピクセル)
- **理想: 640x480** (307,200ピクセル) - Depth Camera搭載デバイスのみ

現在の160x90 (14,400ピクセル)は**非常に低い**ため、可能な限り向上させる必要があります。

## 実装チェックリスト

### Androidアプリ側での確認事項

1. **ARCore Sessionの設定を確認**
   ```kotlin
   // 現在のカメラ設定を確認
   val currentConfig = session.cameraConfig
   Log.d(TAG, "Current camera config: ${currentConfig.imageSize}")
   ```

2. **利用可能な深度解像度を確認**
   ```kotlin
   // サポートされている設定を確認
   val configList = session.getSupportedCameraConfigs(ArCameraConfigFilter(session))
   for (config in configList) {
       Log.d(TAG, "Available config: ${config.imageSize}")
   }
   ```

3. **深度画像の解像度をログ出力**
   ```kotlin
   val depthImage = frame.acquireDepthImage()
   Log.d(TAG, "Depth image size: ${depthImage.width}x${depthImage.height}")
   ```

### サーバー側での確認

診断スクリプトで確認：
```bash
python diagnose_depth.py <job_id>
```

期待される結果：
- Depth resolution: 320x240以上
- Valid pixels: 10%以上

## 対処法

### 即座に実施可能（サーバー側）

1. **深度前処理の強化**
   - 穴埋め（inpainting）を実装
   - 無効値の補間

2. **TSDFパラメータの調整**
   - `voxel_length`を大きく（0.04m以上）
   - `depth_trunc`を適切に設定（診断結果の99パーセンタイル値）

### 根本的解決（Androidアプリ側）

1. **ARCore Session設定の見直し**
   - カメラ設定で最高解像度を選択
   - Depth APIのバージョンを確認

2. **ARCoreのバージョン更新**
   - 最新バージョンでより高解像度をサポート

3. **Depth Camera搭載デバイスの使用**
   - iPhone 15 Pro / iPad Pro
   - Intel RealSense
   - Azure Kinect

## 参考資料

- [ARCore Depth API Documentation](https://developers.google.com/ar/develop/java/depth)
- [ARCore Camera Configuration](https://developers.google.com/ar/reference/java/com/google/ar/core/ArCameraConfig)

最終更新: 2026-01-08 10:14:57
---

# Android側でのDepth解像度向上ガイド

## 現状の問題

診断結果から以下の問題が判明：
- **深度解像度: 160x90** (14,400ピクセル) - 非常に低い
- **有効深度ピクセル: 0.4%** (99.6%が無効値マーカー)
- これはARCore Depth APIの**デフォルト解像度**で、明示的に解像度を指定していない可能性が高い

## ARCore Depth APIの解像度設定

### ARCore Depth APIの解像度オプション

ARCore Depth APIでは、`ArCameraConfig`または`ArSession`で深度解像度を設定できます。

#### 1. カメラ設定での解像度指定（推奨）

```java
// ARCore Depth APIの解像度を設定
ArSession session = new ArSession(context);

// カメラ設定を取得
ArCameraConfigFilter filter = new ArCameraConfigFilter(session);
ArCameraConfigList configList = session.getSupportedCameraConfigs(filter);

// 深度解像度が高い設定を選択
ArCameraConfig bestConfig = null;
int maxDepthSize = 0;
for (ArCameraConfig config : configList) {
    ArCameraConfig.DepthSensorUsage usage = config.getDepthSensorUsage();
    
    // 深度解像度を確認（直接取得できない場合、ターミナル解像度から推測）
    // より高い解像度の設定を選択
    int depthWidth = config.getImageSize().getWidth();  // 深度は通常カメラ解像度より低い
    if (depthWidth > maxDepthSize) {
        maxDepthSize = depthWidth;
        bestConfig = config;
    }
}

if (bestConfig != null) {
    session.setCameraConfig(bestConfig);
}
```

#### 2. ARCore Sessionの深度設定（直接指定）

```java
// ARCore 1.30以降では、深度解像度をより直接的に制御可能
ArConfig config = new ArConfig(session);
config.setDepthMode(ArConfig.DepthMode.AUTOMATIC);  // または DEPTH_MODE_RAW_DEPTH_ONLY

// 深度解像度の優先順位を設定（利用可能な場合）
// 注意: ARCoreのバージョンによってAPIが異なる可能性があります
```

#### 3. Depth APIでの最大解像度取得

```java
// 利用可能な深度解像度を取得
ArDepthPointCloud depthPointCloud = frame.acquireDepthPointCloud();

// 深度画像の解像度を確認
int depthWidth = depthPointCloud.getWidth();
int depthHeight = depthPointCloud.getHeight();

// より高い解像度が必要な場合、カメラ設定を調整
```

### 実装例（Kotlin/Java）

#### Androidアプリ側での設定

```kotlin
// ARCore Session初期化時に深度解像度を最大にする
fun initializeArCore(context: Context): ArSession? {
    val session = ArSession(context)
    
    try {
        // デフォルト設定を取得
        val defaultConfig = ArConfig(session)
        defaultConfig.depthMode = ArConfig.DepthMode.AUTOMATIC
        
        // サポートされているカメラ設定を確認
        val configFilter = ArCameraConfigFilter(session)
        val configList = session.getSupportedCameraConfigs(configFilter)
        
        // 最大解像度の設定を選択
        var bestConfig: ArCameraConfig? = null
        var maxResolution = 0
        
        for (i in 0 until configList.size) {
            val config = configList[i]
            val imageSize = config.imageSize
            
            // 画像解像度から深度解像度を推測（深度は通常1/4〜1/2）
            val estimatedDepthResolution = imageSize.width * imageSize.height
            
            if (estimatedDepthResolution > maxResolution) {
                maxResolution = estimatedDepthResolution
                bestConfig = config
            }
        }
        
        // 最適な設定を適用
        if (bestConfig != null) {
            session.setCameraConfig(bestConfig)
            Log.d(TAG, "Depth resolution optimized: ${bestConfig.imageSize}")
        }
        
        session.configure(defaultConfig)
        return session
        
    } catch (e: Exception) {
        Log.e(TAG, "ARCore initialization failed", e)
        return null
    }
}
```

#### 深度データ取得時の解像度確認

```kotlin
// フレームごとに深度データを取得
fun processFrame(frame: ArFrame) {
    val depthImage = frame.acquireDepthImage()
    
    if (depthImage != null) {
        val width = depthImage.width
        val height = depthImage.height
        
        Log.d(TAG, "Depth resolution: ${width}x${height}")
        
        // 期待される解像度より低い場合は警告
        if (width < 320 || height < 240) {
            Log.w(TAG, "Low depth resolution detected: ${width}x${height}")
            Log.w(TAG, "Consider adjusting camera config for higher depth resolution")
        }
        
        // 深度データを保存
        saveDepthImage(depthImage, frame.timestamp)
        
        depthImage.close()
    }
}
```

## ARCore Depth解像度の制約

### デバイスによる制約

1. **Depth Camera搭載デバイス** (iPhone 15 Proなど)
   - より高解像度の深度データが取得可能
   - 通常: 256x192, 320x240, 640x480など

2. **推定Depth（Motion Stereo + ML）** (Pixel 7 Proなど)
   - 解像度が制限される（160x90, 256x192など）
   - デバイスの性能とARCoreのバージョンに依存

3. **Depth APIのバージョン**
   - ARCore 1.20以降: より高解像度をサポート
   - 古いバージョン: 解像度が制限される

### 推奨される解像度

- **最小: 256x192** (49,152ピクセル)
- **推奨: 320x240** (76,800ピクセル)
- **理想: 640x480** (307,200ピクセル) - Depth Camera搭載デバイスのみ

現在の160x90 (14,400ピクセル)は**非常に低い**ため、可能な限り向上させる必要があります。

## 実装チェックリスト

### Androidアプリ側での確認事項

1. **ARCore Sessionの設定を確認**
   ```kotlin
   // 現在のカメラ設定を確認
   val currentConfig = session.cameraConfig
   Log.d(TAG, "Current camera config: ${currentConfig.imageSize}")
   ```

2. **利用可能な深度解像度を確認**
   ```kotlin
   // サポートされている設定を確認
   val configList = session.getSupportedCameraConfigs(ArCameraConfigFilter(session))
   for (config in configList) {
       Log.d(TAG, "Available config: ${config.imageSize}")
   }
   ```

3. **深度画像の解像度をログ出力**
   ```kotlin
   val depthImage = frame.acquireDepthImage()
   Log.d(TAG, "Depth image size: ${depthImage.width}x${depthImage.height}")
   ```

### サーバー側での確認

診断スクリプトで確認：
```bash
python diagnose_depth.py <job_id>
```

期待される結果：
- Depth resolution: 320x240以上
- Valid pixels: 10%以上

## 対処法

### 即座に実施可能（サーバー側）

1. **深度前処理の強化**
   - 穴埋め（inpainting）を実装
   - 無効値の補間

2. **TSDFパラメータの調整**
   - `voxel_length`を大きく（0.04m以上）
   - `depth_trunc`を適切に設定（診断結果の99パーセンタイル値）

### 根本的解決（Androidアプリ側）

1. **ARCore Session設定の見直し**
   - カメラ設定で最高解像度を選択
   - Depth APIのバージョンを確認

2. **ARCoreのバージョン更新**
   - 最新バージョンでより高解像度をサポート

3. **Depth Camera搭載デバイスの使用**
   - iPhone 15 Pro / iPad Pro
   - Intel RealSense
   - Azure Kinect

## 参考資料

- [ARCore Depth API Documentation](https://developers.google.com/ar/develop/java/depth)
- [ARCore Camera Configuration](https://developers.google.com/ar/reference/java/com/google/ar/core/ArCameraConfig)

最終更新: 2026-01-08 10:14:57
---

# Android側でのDepth解像度向上ガイド

## 現状の問題

診断結果から以下の問題が判明：
- **深度解像度: 160x90** (14,400ピクセル) - 非常に低い
- **有効深度ピクセル: 0.4%** (99.6%が無効値マーカー)
- これはARCore Depth APIの**デフォルト解像度**で、明示的に解像度を指定していない可能性が高い

## ARCore Depth APIの解像度設定

### ARCore Depth APIの解像度オプション

ARCore Depth APIでは、`ArCameraConfig`または`ArSession`で深度解像度を設定できます。

#### 1. カメラ設定での解像度指定（推奨）

```java
// ARCore Depth APIの解像度を設定
ArSession session = new ArSession(context);

// カメラ設定を取得
ArCameraConfigFilter filter = new ArCameraConfigFilter(session);
ArCameraConfigList configList = session.getSupportedCameraConfigs(filter);

// 深度解像度が高い設定を選択
ArCameraConfig bestConfig = null;
int maxDepthSize = 0;
for (ArCameraConfig config : configList) {
    ArCameraConfig.DepthSensorUsage usage = config.getDepthSensorUsage();
    
    // 深度解像度を確認（直接取得できない場合、ターミナル解像度から推測）
    // より高い解像度の設定を選択
    int depthWidth = config.getImageSize().getWidth();  // 深度は通常カメラ解像度より低い
    if (depthWidth > maxDepthSize) {
        maxDepthSize = depthWidth;
        bestConfig = config;
    }
}

if (bestConfig != null) {
    session.setCameraConfig(bestConfig);
}
```

#### 2. ARCore Sessionの深度設定（直接指定）

```java
// ARCore 1.30以降では、深度解像度をより直接的に制御可能
ArConfig config = new ArConfig(session);
config.setDepthMode(ArConfig.DepthMode.AUTOMATIC);  // または DEPTH_MODE_RAW_DEPTH_ONLY

// 深度解像度の優先順位を設定（利用可能な場合）
// 注意: ARCoreのバージョンによってAPIが異なる可能性があります
```

#### 3. Depth APIでの最大解像度取得

```java
// 利用可能な深度解像度を取得
ArDepthPointCloud depthPointCloud = frame.acquireDepthPointCloud();

// 深度画像の解像度を確認
int depthWidth = depthPointCloud.getWidth();
int depthHeight = depthPointCloud.getHeight();

// より高い解像度が必要な場合、カメラ設定を調整
```

### 実装例（Kotlin/Java）

#### Androidアプリ側での設定

```kotlin
// ARCore Session初期化時に深度解像度を最大にする
fun initializeArCore(context: Context): ArSession? {
    val session = ArSession(context)
    
    try {
        // デフォルト設定を取得
        val defaultConfig = ArConfig(session)
        defaultConfig.depthMode = ArConfig.DepthMode.AUTOMATIC
        
        // サポートされているカメラ設定を確認
        val configFilter = ArCameraConfigFilter(session)
        val configList = session.getSupportedCameraConfigs(configFilter)
        
        // 最大解像度の設定を選択
        var bestConfig: ArCameraConfig? = null
        var maxResolution = 0
        
        for (i in 0 until configList.size) {
            val config = configList[i]
            val imageSize = config.imageSize
            
            // 画像解像度から深度解像度を推測（深度は通常1/4〜1/2）
            val estimatedDepthResolution = imageSize.width * imageSize.height
            
            if (estimatedDepthResolution > maxResolution) {
                maxResolution = estimatedDepthResolution
                bestConfig = config
            }
        }
        
        // 最適な設定を適用
        if (bestConfig != null) {
            session.setCameraConfig(bestConfig)
            Log.d(TAG, "Depth resolution optimized: ${bestConfig.imageSize}")
        }
        
        session.configure(defaultConfig)
        return session
        
    } catch (e: Exception) {
        Log.e(TAG, "ARCore initialization failed", e)
        return null
    }
}
```

#### 深度データ取得時の解像度確認

```kotlin
// フレームごとに深度データを取得
fun processFrame(frame: ArFrame) {
    val depthImage = frame.acquireDepthImage()
    
    if (depthImage != null) {
        val width = depthImage.width
        val height = depthImage.height
        
        Log.d(TAG, "Depth resolution: ${width}x${height}")
        
        // 期待される解像度より低い場合は警告
        if (width < 320 || height < 240) {
            Log.w(TAG, "Low depth resolution detected: ${width}x${height}")
            Log.w(TAG, "Consider adjusting camera config for higher depth resolution")
        }
        
        // 深度データを保存
        saveDepthImage(depthImage, frame.timestamp)
        
        depthImage.close()
    }
}
```

## ARCore Depth解像度の制約

### デバイスによる制約

1. **Depth Camera搭載デバイス** (iPhone 15 Proなど)
   - より高解像度の深度データが取得可能
   - 通常: 256x192, 320x240, 640x480など

2. **推定Depth（Motion Stereo + ML）** (Pixel 7 Proなど)
   - 解像度が制限される（160x90, 256x192など）
   - デバイスの性能とARCoreのバージョンに依存

3. **Depth APIのバージョン**
   - ARCore 1.20以降: より高解像度をサポート
   - 古いバージョン: 解像度が制限される

### 推奨される解像度

- **最小: 256x192** (49,152ピクセル)
- **推奨: 320x240** (76,800ピクセル)
- **理想: 640x480** (307,200ピクセル) - Depth Camera搭載デバイスのみ

現在の160x90 (14,400ピクセル)は**非常に低い**ため、可能な限り向上させる必要があります。

## 実装チェックリスト

### Androidアプリ側での確認事項

1. **ARCore Sessionの設定を確認**
   ```kotlin
   // 現在のカメラ設定を確認
   val currentConfig = session.cameraConfig
   Log.d(TAG, "Current camera config: ${currentConfig.imageSize}")
   ```

2. **利用可能な深度解像度を確認**
   ```kotlin
   // サポートされている設定を確認
   val configList = session.getSupportedCameraConfigs(ArCameraConfigFilter(session))
   for (config in configList) {
       Log.d(TAG, "Available config: ${config.imageSize}")
   }
   ```

3. **深度画像の解像度をログ出力**
   ```kotlin
   val depthImage = frame.acquireDepthImage()
   Log.d(TAG, "Depth image size: ${depthImage.width}x${depthImage.height}")
   ```

### サーバー側での確認

診断スクリプトで確認：
```bash
python diagnose_depth.py <job_id>
```

期待される結果：
- Depth resolution: 320x240以上
- Valid pixels: 10%以上

## 対処法

### 即座に実施可能（サーバー側）

1. **深度前処理の強化**
   - 穴埋め（inpainting）を実装
   - 無効値の補間

2. **TSDFパラメータの調整**
   - `voxel_length`を大きく（0.04m以上）
   - `depth_trunc`を適切に設定（診断結果の99パーセンタイル値）

### 根本的解決（Androidアプリ側）

1. **ARCore Session設定の見直し**
   - カメラ設定で最高解像度を選択
   - Depth APIのバージョンを確認

2. **ARCoreのバージョン更新**
   - 最新バージョンでより高解像度をサポート

3. **Depth Camera搭載デバイスの使用**
   - iPhone 15 Pro / iPad Pro
   - Intel RealSense
   - Azure Kinect

## 参考資料

- [ARCore Depth API Documentation](https://developers.google.com/ar/develop/java/depth)
- [ARCore Camera Configuration](https://developers.google.com/ar/reference/java/com/google/ar/core/ArCameraConfig)

最終更新: 2026-01-08 10:14:57
---

# Android側でのDepth解像度向上ガイド

## 現状の問題

診断結果から以下の問題が判明：
- **深度解像度: 160x90** (14,400ピクセル) - 非常に低い
- **有効深度ピクセル: 0.4%** (99.6%が無効値マーカー)
- これはARCore Depth APIの**デフォルト解像度**で、明示的に解像度を指定していない可能性が高い

## ARCore Depth APIの解像度設定

### ARCore Depth APIの解像度オプション

ARCore Depth APIでは、`ArCameraConfig`または`ArSession`で深度解像度を設定できます。

#### 1. カメラ設定での解像度指定（推奨）

```java
// ARCore Depth APIの解像度を設定
ArSession session = new ArSession(context);

// カメラ設定を取得
ArCameraConfigFilter filter = new ArCameraConfigFilter(session);
ArCameraConfigList configList = session.getSupportedCameraConfigs(filter);

// 深度解像度が高い設定を選択
ArCameraConfig bestConfig = null;
int maxDepthSize = 0;
for (ArCameraConfig config : configList) {
    ArCameraConfig.DepthSensorUsage usage = config.getDepthSensorUsage();
    
    // 深度解像度を確認（直接取得できない場合、ターミナル解像度から推測）
    // より高い解像度の設定を選択
    int depthWidth = config.getImageSize().getWidth();  // 深度は通常カメラ解像度より低い
    if (depthWidth > maxDepthSize) {
        maxDepthSize = depthWidth;
        bestConfig = config;
    }
}

if (bestConfig != null) {
    session.setCameraConfig(bestConfig);
}
```

#### 2. ARCore Sessionの深度設定（直接指定）

```java
// ARCore 1.30以降では、深度解像度をより直接的に制御可能
ArConfig config = new ArConfig(session);
config.setDepthMode(ArConfig.DepthMode.AUTOMATIC);  // または DEPTH_MODE_RAW_DEPTH_ONLY

// 深度解像度の優先順位を設定（利用可能な場合）
// 注意: ARCoreのバージョンによってAPIが異なる可能性があります
```

#### 3. Depth APIでの最大解像度取得

```java
// 利用可能な深度解像度を取得
ArDepthPointCloud depthPointCloud = frame.acquireDepthPointCloud();

// 深度画像の解像度を確認
int depthWidth = depthPointCloud.getWidth();
int depthHeight = depthPointCloud.getHeight();

// より高い解像度が必要な場合、カメラ設定を調整
```

### 実装例（Kotlin/Java）

#### Androidアプリ側での設定

```kotlin
// ARCore Session初期化時に深度解像度を最大にする
fun initializeArCore(context: Context): ArSession? {
    val session = ArSession(context)
    
    try {
        // デフォルト設定を取得
        val defaultConfig = ArConfig(session)
        defaultConfig.depthMode = ArConfig.DepthMode.AUTOMATIC
        
        // サポートされているカメラ設定を確認
        val configFilter = ArCameraConfigFilter(session)
        val configList = session.getSupportedCameraConfigs(configFilter)
        
        // 最大解像度の設定を選択
        var bestConfig: ArCameraConfig? = null
        var maxResolution = 0
        
        for (i in 0 until configList.size) {
            val config = configList[i]
            val imageSize = config.imageSize
            
            // 画像解像度から深度解像度を推測（深度は通常1/4〜1/2）
            val estimatedDepthResolution = imageSize.width * imageSize.height
            
            if (estimatedDepthResolution > maxResolution) {
                maxResolution = estimatedDepthResolution
                bestConfig = config
            }
        }
        
        // 最適な設定を適用
        if (bestConfig != null) {
            session.setCameraConfig(bestConfig)
            Log.d(TAG, "Depth resolution optimized: ${bestConfig.imageSize}")
        }
        
        session.configure(defaultConfig)
        return session
        
    } catch (e: Exception) {
        Log.e(TAG, "ARCore initialization failed", e)
        return null
    }
}
```

#### 深度データ取得時の解像度確認

```kotlin
// フレームごとに深度データを取得
fun processFrame(frame: ArFrame) {
    val depthImage = frame.acquireDepthImage()
    
    if (depthImage != null) {
        val width = depthImage.width
        val height = depthImage.height
        
        Log.d(TAG, "Depth resolution: ${width}x${height}")
        
        // 期待される解像度より低い場合は警告
        if (width < 320 || height < 240) {
            Log.w(TAG, "Low depth resolution detected: ${width}x${height}")
            Log.w(TAG, "Consider adjusting camera config for higher depth resolution")
        }
        
        // 深度データを保存
        saveDepthImage(depthImage, frame.timestamp)
        
        depthImage.close()
    }
}
```

## ARCore Depth解像度の制約

### デバイスによる制約

1. **Depth Camera搭載デバイス** (iPhone 15 Proなど)
   - より高解像度の深度データが取得可能
   - 通常: 256x192, 320x240, 640x480など

2. **推定Depth（Motion Stereo + ML）** (Pixel 7 Proなど)
   - 解像度が制限される（160x90, 256x192など）
   - デバイスの性能とARCoreのバージョンに依存

3. **Depth APIのバージョン**
   - ARCore 1.20以降: より高解像度をサポート
   - 古いバージョン: 解像度が制限される

### 推奨される解像度

- **最小: 256x192** (49,152ピクセル)
- **推奨: 320x240** (76,800ピクセル)
- **理想: 640x480** (307,200ピクセル) - Depth Camera搭載デバイスのみ

現在の160x90 (14,400ピクセル)は**非常に低い**ため、可能な限り向上させる必要があります。

## 実装チェックリスト

### Androidアプリ側での確認事項

1. **ARCore Sessionの設定を確認**
   ```kotlin
   // 現在のカメラ設定を確認
   val currentConfig = session.cameraConfig
   Log.d(TAG, "Current camera config: ${currentConfig.imageSize}")
   ```

2. **利用可能な深度解像度を確認**
   ```kotlin
   // サポートされている設定を確認
   val configList = session.getSupportedCameraConfigs(ArCameraConfigFilter(session))
   for (config in configList) {
       Log.d(TAG, "Available config: ${config.imageSize}")
   }
   ```

3. **深度画像の解像度をログ出力**
   ```kotlin
   val depthImage = frame.acquireDepthImage()
   Log.d(TAG, "Depth image size: ${depthImage.width}x${depthImage.height}")
   ```

### サーバー側での確認

診断スクリプトで確認：
```bash
python diagnose_depth.py <job_id>
```

期待される結果：
- Depth resolution: 320x240以上
- Valid pixels: 10%以上

## 対処法

### 即座に実施可能（サーバー側）

1. **深度前処理の強化**
   - 穴埋め（inpainting）を実装
   - 無効値の補間

2. **TSDFパラメータの調整**
   - `voxel_length`を大きく（0.04m以上）
   - `depth_trunc`を適切に設定（診断結果の99パーセンタイル値）

### 根本的解決（Androidアプリ側）

1. **ARCore Session設定の見直し**
   - カメラ設定で最高解像度を選択
   - Depth APIのバージョンを確認

2. **ARCoreのバージョン更新**
   - 最新バージョンでより高解像度をサポート

3. **Depth Camera搭載デバイスの使用**
   - iPhone 15 Pro / iPad Pro
   - Intel RealSense
   - Azure Kinect

## 参考資料

- [ARCore Depth API Documentation](https://developers.google.com/ar/develop/java/depth)
- [ARCore Camera Configuration](https://developers.google.com/ar/reference/java/com/google/ar/core/ArCameraConfig)

最終更新: 2026-01-08 10:14:57
---

# Android側でのDepth解像度向上ガイド

## 現状の問題

診断結果から以下の問題が判明：
- **深度解像度: 160x90** (14,400ピクセル) - 非常に低い
- **有効深度ピクセル: 0.4%** (99.6%が無効値マーカー)
- これはARCore Depth APIの**デフォルト解像度**で、明示的に解像度を指定していない可能性が高い

## ARCore Depth APIの解像度設定

### ARCore Depth APIの解像度オプション

ARCore Depth APIでは、`ArCameraConfig`または`ArSession`で深度解像度を設定できます。

#### 1. カメラ設定での解像度指定（推奨）

```java
// ARCore Depth APIの解像度を設定
ArSession session = new ArSession(context);

// カメラ設定を取得
ArCameraConfigFilter filter = new ArCameraConfigFilter(session);
ArCameraConfigList configList = session.getSupportedCameraConfigs(filter);

// 深度解像度が高い設定を選択
ArCameraConfig bestConfig = null;
int maxDepthSize = 0;
for (ArCameraConfig config : configList) {
    ArCameraConfig.DepthSensorUsage usage = config.getDepthSensorUsage();
    
    // 深度解像度を確認（直接取得できない場合、ターミナル解像度から推測）
    // より高い解像度の設定を選択
    int depthWidth = config.getImageSize().getWidth();  // 深度は通常カメラ解像度より低い
    if (depthWidth > maxDepthSize) {
        maxDepthSize = depthWidth;
        bestConfig = config;
    }
}

if (bestConfig != null) {
    session.setCameraConfig(bestConfig);
}
```

#### 2. ARCore Sessionの深度設定（直接指定）

```java
// ARCore 1.30以降では、深度解像度をより直接的に制御可能
ArConfig config = new ArConfig(session);
config.setDepthMode(ArConfig.DepthMode.AUTOMATIC);  // または DEPTH_MODE_RAW_DEPTH_ONLY

// 深度解像度の優先順位を設定（利用可能な場合）
// 注意: ARCoreのバージョンによってAPIが異なる可能性があります
```

#### 3. Depth APIでの最大解像度取得

```java
// 利用可能な深度解像度を取得
ArDepthPointCloud depthPointCloud = frame.acquireDepthPointCloud();

// 深度画像の解像度を確認
int depthWidth = depthPointCloud.getWidth();
int depthHeight = depthPointCloud.getHeight();

// より高い解像度が必要な場合、カメラ設定を調整
```

### 実装例（Kotlin/Java）

#### Androidアプリ側での設定

```kotlin
// ARCore Session初期化時に深度解像度を最大にする
fun initializeArCore(context: Context): ArSession? {
    val session = ArSession(context)
    
    try {
        // デフォルト設定を取得
        val defaultConfig = ArConfig(session)
        defaultConfig.depthMode = ArConfig.DepthMode.AUTOMATIC
        
        // サポートされているカメラ設定を確認
        val configFilter = ArCameraConfigFilter(session)
        val configList = session.getSupportedCameraConfigs(configFilter)
        
        // 最大解像度の設定を選択
        var bestConfig: ArCameraConfig? = null
        var maxResolution = 0
        
        for (i in 0 until configList.size) {
            val config = configList[i]
            val imageSize = config.imageSize
            
            // 画像解像度から深度解像度を推測（深度は通常1/4〜1/2）
            val estimatedDepthResolution = imageSize.width * imageSize.height
            
            if (estimatedDepthResolution > maxResolution) {
                maxResolution = estimatedDepthResolution
                bestConfig = config
            }
        }
        
        // 最適な設定を適用
        if (bestConfig != null) {
            session.setCameraConfig(bestConfig)
            Log.d(TAG, "Depth resolution optimized: ${bestConfig.imageSize}")
        }
        
        session.configure(defaultConfig)
        return session
        
    } catch (e: Exception) {
        Log.e(TAG, "ARCore initialization failed", e)
        return null
    }
}
```

#### 深度データ取得時の解像度確認

```kotlin
// フレームごとに深度データを取得
fun processFrame(frame: ArFrame) {
    val depthImage = frame.acquireDepthImage()
    
    if (depthImage != null) {
        val width = depthImage.width
        val height = depthImage.height
        
        Log.d(TAG, "Depth resolution: ${width}x${height}")
        
        // 期待される解像度より低い場合は警告
        if (width < 320 || height < 240) {
            Log.w(TAG, "Low depth resolution detected: ${width}x${height}")
            Log.w(TAG, "Consider adjusting camera config for higher depth resolution")
        }
        
        // 深度データを保存
        saveDepthImage(depthImage, frame.timestamp)
        
        depthImage.close()
    }
}
```

## ARCore Depth解像度の制約

### デバイスによる制約

1. **Depth Camera搭載デバイス** (iPhone 15 Proなど)
   - より高解像度の深度データが取得可能
   - 通常: 256x192, 320x240, 640x480など

2. **推定Depth（Motion Stereo + ML）** (Pixel 7 Proなど)
   - 解像度が制限される（160x90, 256x192など）
   - デバイスの性能とARCoreのバージョンに依存

3. **Depth APIのバージョン**
   - ARCore 1.20以降: より高解像度をサポート
   - 古いバージョン: 解像度が制限される

### 推奨される解像度

- **最小: 256x192** (49,152ピクセル)
- **推奨: 320x240** (76,800ピクセル)
- **理想: 640x480** (307,200ピクセル) - Depth Camera搭載デバイスのみ

現在の160x90 (14,400ピクセル)は**非常に低い**ため、可能な限り向上させる必要があります。

## 実装チェックリスト

### Androidアプリ側での確認事項

1. **ARCore Sessionの設定を確認**
   ```kotlin
   // 現在のカメラ設定を確認
   val currentConfig = session.cameraConfig
   Log.d(TAG, "Current camera config: ${currentConfig.imageSize}")
   ```

2. **利用可能な深度解像度を確認**
   ```kotlin
   // サポートされている設定を確認
   val configList = session.getSupportedCameraConfigs(ArCameraConfigFilter(session))
   for (config in configList) {
       Log.d(TAG, "Available config: ${config.imageSize}")
   }
   ```

3. **深度画像の解像度をログ出力**
   ```kotlin
   val depthImage = frame.acquireDepthImage()
   Log.d(TAG, "Depth image size: ${depthImage.width}x${depthImage.height}")
   ```

### サーバー側での確認

診断スクリプトで確認：
```bash
python diagnose_depth.py <job_id>
```

期待される結果：
- Depth resolution: 320x240以上
- Valid pixels: 10%以上

## 対処法

### 即座に実施可能（サーバー側）

1. **深度前処理の強化**
   - 穴埋め（inpainting）を実装
   - 無効値の補間

2. **TSDFパラメータの調整**
   - `voxel_length`を大きく（0.04m以上）
   - `depth_trunc`を適切に設定（診断結果の99パーセンタイル値）

### 根本的解決（Androidアプリ側）

1. **ARCore Session設定の見直し**
   - カメラ設定で最高解像度を選択
   - Depth APIのバージョンを確認

2. **ARCoreのバージョン更新**
   - 最新バージョンでより高解像度をサポート

3. **Depth Camera搭載デバイスの使用**
   - iPhone 15 Pro / iPad Pro
   - Intel RealSense
   - Azure Kinect

## 参考資料

- [ARCore Depth API Documentation](https://developers.google.com/ar/develop/java/depth)
- [ARCore Camera Configuration](https://developers.google.com/ar/reference/java/com/google/ar/core/ArCameraConfig)

最終更新: 2026-01-08 10:14:57
---

# Android側でのDepth解像度向上ガイド

## 現状の問題

診断結果から以下の問題が判明：
- **深度解像度: 160x90** (14,400ピクセル) - 非常に低い
- **有効深度ピクセル: 0.4%** (99.6%が無効値マーカー)
- これはARCore Depth APIの**デフォルト解像度**で、明示的に解像度を指定していない可能性が高い

## ARCore Depth APIの解像度設定

### ARCore Depth APIの解像度オプション

ARCore Depth APIでは、`ArCameraConfig`または`ArSession`で深度解像度を設定できます。

#### 1. カメラ設定での解像度指定（推奨）

```java
// ARCore Depth APIの解像度を設定
ArSession session = new ArSession(context);

// カメラ設定を取得
ArCameraConfigFilter filter = new ArCameraConfigFilter(session);
ArCameraConfigList configList = session.getSupportedCameraConfigs(filter);

// 深度解像度が高い設定を選択
ArCameraConfig bestConfig = null;
int maxDepthSize = 0;
for (ArCameraConfig config : configList) {
    ArCameraConfig.DepthSensorUsage usage = config.getDepthSensorUsage();
    
    // 深度解像度を確認（直接取得できない場合、ターミナル解像度から推測）
    // より高い解像度の設定を選択
    int depthWidth = config.getImageSize().getWidth();  // 深度は通常カメラ解像度より低い
    if (depthWidth > maxDepthSize) {
        maxDepthSize = depthWidth;
        bestConfig = config;
    }
}

if (bestConfig != null) {
    session.setCameraConfig(bestConfig);
}
```

#### 2. ARCore Sessionの深度設定（直接指定）

```java
// ARCore 1.30以降では、深度解像度をより直接的に制御可能
ArConfig config = new ArConfig(session);
config.setDepthMode(ArConfig.DepthMode.AUTOMATIC);  // または DEPTH_MODE_RAW_DEPTH_ONLY

// 深度解像度の優先順位を設定（利用可能な場合）
// 注意: ARCoreのバージョンによってAPIが異なる可能性があります
```

#### 3. Depth APIでの最大解像度取得

```java
// 利用可能な深度解像度を取得
ArDepthPointCloud depthPointCloud = frame.acquireDepthPointCloud();

// 深度画像の解像度を確認
int depthWidth = depthPointCloud.getWidth();
int depthHeight = depthPointCloud.getHeight();

// より高い解像度が必要な場合、カメラ設定を調整
```

### 実装例（Kotlin/Java）

#### Androidアプリ側での設定

```kotlin
// ARCore Session初期化時に深度解像度を最大にする
fun initializeArCore(context: Context): ArSession? {
    val session = ArSession(context)
    
    try {
        // デフォルト設定を取得
        val defaultConfig = ArConfig(session)
        defaultConfig.depthMode = ArConfig.DepthMode.AUTOMATIC
        
        // サポートされているカメラ設定を確認
        val configFilter = ArCameraConfigFilter(session)
        val configList = session.getSupportedCameraConfigs(configFilter)
        
        // 最大解像度の設定を選択
        var bestConfig: ArCameraConfig? = null
        var maxResolution = 0
        
        for (i in 0 until configList.size) {
            val config = configList[i]
            val imageSize = config.imageSize
            
            // 画像解像度から深度解像度を推測（深度は通常1/4〜1/2）
            val estimatedDepthResolution = imageSize.width * imageSize.height
            
            if (estimatedDepthResolution > maxResolution) {
                maxResolution = estimatedDepthResolution
                bestConfig = config
            }
        }
        
        // 最適な設定を適用
        if (bestConfig != null) {
            session.setCameraConfig(bestConfig)
            Log.d(TAG, "Depth resolution optimized: ${bestConfig.imageSize}")
        }
        
        session.configure(defaultConfig)
        return session
        
    } catch (e: Exception) {
        Log.e(TAG, "ARCore initialization failed", e)
        return null
    }
}
```

#### 深度データ取得時の解像度確認

```kotlin
// フレームごとに深度データを取得
fun processFrame(frame: ArFrame) {
    val depthImage = frame.acquireDepthImage()
    
    if (depthImage != null) {
        val width = depthImage.width
        val height = depthImage.height
        
        Log.d(TAG, "Depth resolution: ${width}x${height}")
        
        // 期待される解像度より低い場合は警告
        if (width < 320 || height < 240) {
            Log.w(TAG, "Low depth resolution detected: ${width}x${height}")
            Log.w(TAG, "Consider adjusting camera config for higher depth resolution")
        }
        
        // 深度データを保存
        saveDepthImage(depthImage, frame.timestamp)
        
        depthImage.close()
    }
}
```

## ARCore Depth解像度の制約

### デバイスによる制約

1. **Depth Camera搭載デバイス** (iPhone 15 Proなど)
   - より高解像度の深度データが取得可能
   - 通常: 256x192, 320x240, 640x480など

2. **推定Depth（Motion Stereo + ML）** (Pixel 7 Proなど)
   - 解像度が制限される（160x90, 256x192など）
   - デバイスの性能とARCoreのバージョンに依存

3. **Depth APIのバージョン**
   - ARCore 1.20以降: より高解像度をサポート
   - 古いバージョン: 解像度が制限される

### 推奨される解像度

- **最小: 256x192** (49,152ピクセル)
- **推奨: 320x240** (76,800ピクセル)
- **理想: 640x480** (307,200ピクセル) - Depth Camera搭載デバイスのみ

現在の160x90 (14,400ピクセル)は**非常に低い**ため、可能な限り向上させる必要があります。

## 実装チェックリスト

### Androidアプリ側での確認事項

1. **ARCore Sessionの設定を確認**
   ```kotlin
   // 現在のカメラ設定を確認
   val currentConfig = session.cameraConfig
   Log.d(TAG, "Current camera config: ${currentConfig.imageSize}")
   ```

2. **利用可能な深度解像度を確認**
   ```kotlin
   // サポートされている設定を確認
   val configList = session.getSupportedCameraConfigs(ArCameraConfigFilter(session))
   for (config in configList) {
       Log.d(TAG, "Available config: ${config.imageSize}")
   }
   ```

3. **深度画像の解像度をログ出力**
   ```kotlin
   val depthImage = frame.acquireDepthImage()
   Log.d(TAG, "Depth image size: ${depthImage.width}x${depthImage.height}")
   ```

### サーバー側での確認

診断スクリプトで確認：
```bash
python diagnose_depth.py <job_id>
```

期待される結果：
- Depth resolution: 320x240以上
- Valid pixels: 10%以上

## 対処法

### 即座に実施可能（サーバー側）

1. **深度前処理の強化**
   - 穴埋め（inpainting）を実装
   - 無効値の補間

2. **TSDFパラメータの調整**
   - `voxel_length`を大きく（0.04m以上）
   - `depth_trunc`を適切に設定（診断結果の99パーセンタイル値）

### 根本的解決（Androidアプリ側）

1. **ARCore Session設定の見直し**
   - カメラ設定で最高解像度を選択
   - Depth APIのバージョンを確認

2. **ARCoreのバージョン更新**
   - 最新バージョンでより高解像度をサポート

3. **Depth Camera搭載デバイスの使用**
   - iPhone 15 Pro / iPad Pro
   - Intel RealSense
   - Azure Kinect

## 参考資料

- [ARCore Depth API Documentation](https://developers.google.com/ar/develop/java/depth)
- [ARCore Camera Configuration](https://developers.google.com/ar/reference/java/com/google/ar/core/ArCameraConfig)
最終更新: 2026-01-08 10:14:57
---

# Android側でのDepth解像度向上ガイド

## 現状の問題

診断結果から以下の問題が判明：
- **深度解像度: 160x90** (14,400ピクセル) - 非常に低い
- **有効深度ピクセル: 0.4%** (99.6%が無効値マーカー)
- これはARCore Depth APIの**デフォルト解像度**で、明示的に解像度を指定していない可能性が高い

## ARCore Depth APIの解像度設定

### ARCore Depth APIの解像度オプション

ARCore Depth APIでは、`ArCameraConfig`または`ArSession`で深度解像度を設定できます。

#### 1. カメラ設定での解像度指定（推奨）

```java
// ARCore Depth APIの解像度を設定
ArSession session = new ArSession(context);

// カメラ設定を取得
ArCameraConfigFilter filter = new ArCameraConfigFilter(session);
ArCameraConfigList configList = session.getSupportedCameraConfigs(filter);

// 深度解像度が高い設定を選択
ArCameraConfig bestConfig = null;
int maxDepthSize = 0;
for (ArCameraConfig config : configList) {
    ArCameraConfig.DepthSensorUsage usage = config.getDepthSensorUsage();
    
    // 深度解像度を確認（直接取得できない場合、ターミナル解像度から推測）
    // より高い解像度の設定を選択
    int depthWidth = config.getImageSize().getWidth();  // 深度は通常カメラ解像度より低い
    if (depthWidth > maxDepthSize) {
        maxDepthSize = depthWidth;
        bestConfig = config;
    }
}

if (bestConfig != null) {
    session.setCameraConfig(bestConfig);
}
```

#### 2. ARCore Sessionの深度設定（直接指定）

```java
// ARCore 1.30以降では、深度解像度をより直接的に制御可能
ArConfig config = new ArConfig(session);
config.setDepthMode(ArConfig.DepthMode.AUTOMATIC);  // または DEPTH_MODE_RAW_DEPTH_ONLY

// 深度解像度の優先順位を設定（利用可能な場合）
// 注意: ARCoreのバージョンによってAPIが異なる可能性があります
```

#### 3. Depth APIでの最大解像度取得

```java
// 利用可能な深度解像度を取得
ArDepthPointCloud depthPointCloud = frame.acquireDepthPointCloud();

// 深度画像の解像度を確認
int depthWidth = depthPointCloud.getWidth();
int depthHeight = depthPointCloud.getHeight();

// より高い解像度が必要な場合、カメラ設定を調整
```

### 実装例（Kotlin/Java）

#### Androidアプリ側での設定

```kotlin
// ARCore Session初期化時に深度解像度を最大にする
fun initializeArCore(context: Context): ArSession? {
    val session = ArSession(context)
    
    try {
        // デフォルト設定を取得
        val defaultConfig = ArConfig(session)
        defaultConfig.depthMode = ArConfig.DepthMode.AUTOMATIC
        
        // サポートされているカメラ設定を確認
        val configFilter = ArCameraConfigFilter(session)
        val configList = session.getSupportedCameraConfigs(configFilter)
        
        // 最大解像度の設定を選択
        var bestConfig: ArCameraConfig? = null
        var maxResolution = 0
        
        for (i in 0 until configList.size) {
            val config = configList[i]
            val imageSize = config.imageSize
            
            // 画像解像度から深度解像度を推測（深度は通常1/4〜1/2）
            val estimatedDepthResolution = imageSize.width * imageSize.height
            
            if (estimatedDepthResolution > maxResolution) {
                maxResolution = estimatedDepthResolution
                bestConfig = config
            }
        }
        
        // 最適な設定を適用
        if (bestConfig != null) {
            session.setCameraConfig(bestConfig)
            Log.d(TAG, "Depth resolution optimized: ${bestConfig.imageSize}")
        }
        
        session.configure(defaultConfig)
        return session
        
    } catch (e: Exception) {
        Log.e(TAG, "ARCore initialization failed", e)
        return null
    }
}
```

#### 深度データ取得時の解像度確認

```kotlin
// フレームごとに深度データを取得
fun processFrame(frame: ArFrame) {
    val depthImage = frame.acquireDepthImage()
    
    if (depthImage != null) {
        val width = depthImage.width
        val height = depthImage.height
        
        Log.d(TAG, "Depth resolution: ${width}x${height}")
        
        // 期待される解像度より低い場合は警告
        if (width < 320 || height < 240) {
            Log.w(TAG, "Low depth resolution detected: ${width}x${height}")
            Log.w(TAG, "Consider adjusting camera config for higher depth resolution")
        }
        
        // 深度データを保存
        saveDepthImage(depthImage, frame.timestamp)
        
        depthImage.close()
    }
}
```

## ARCore Depth解像度の制約

### デバイスによる制約

1. **Depth Camera搭載デバイス** (iPhone 15 Proなど)
   - より高解像度の深度データが取得可能
   - 通常: 256x192, 320x240, 640x480など

2. **推定Depth（Motion Stereo + ML）** (Pixel 7 Proなど)
   - 解像度が制限される（160x90, 256x192など）
   - デバイスの性能とARCoreのバージョンに依存

3. **Depth APIのバージョン**
   - ARCore 1.20以降: より高解像度をサポート
   - 古いバージョン: 解像度が制限される

### 推奨される解像度

- **最小: 256x192** (49,152ピクセル)
- **推奨: 320x240** (76,800ピクセル)
- **理想: 640x480** (307,200ピクセル) - Depth Camera搭載デバイスのみ

現在の160x90 (14,400ピクセル)は**非常に低い**ため、可能な限り向上させる必要があります。

## 実装チェックリスト

### Androidアプリ側での確認事項

1. **ARCore Sessionの設定を確認**
   ```kotlin
   // 現在のカメラ設定を確認
   val currentConfig = session.cameraConfig
   Log.d(TAG, "Current camera config: ${currentConfig.imageSize}")
   ```

2. **利用可能な深度解像度を確認**
   ```kotlin
   // サポートされている設定を確認
   val configList = session.getSupportedCameraConfigs(ArCameraConfigFilter(session))
   for (config in configList) {
       Log.d(TAG, "Available config: ${config.imageSize}")
   }
   ```

3. **深度画像の解像度をログ出力**
   ```kotlin
   val depthImage = frame.acquireDepthImage()
   Log.d(TAG, "Depth image size: ${depthImage.width}x${depthImage.height}")
   ```

### サーバー側での確認

診断スクリプトで確認：
```bash
python diagnose_depth.py <job_id>
```

期待される結果：
- Depth resolution: 320x240以上
- Valid pixels: 10%以上

## 対処法

### 即座に実施可能（サーバー側）

1. **深度前処理の強化**
   - 穴埋め（inpainting）を実装
   - 無効値の補間

2. **TSDFパラメータの調整**
   - `voxel_length`を大きく（0.04m以上）
   - `depth_trunc`を適切に設定（診断結果の99パーセンタイル値）

### 根本的解決（Androidアプリ側）

1. **ARCore Session設定の見直し**
   - カメラ設定で最高解像度を選択
   - Depth APIのバージョンを確認

2. **ARCoreのバージョン更新**
   - 最新バージョンでより高解像度をサポート

3. **Depth Camera搭載デバイスの使用**
   - iPhone 15 Pro / iPad Pro
   - Intel RealSense
   - Azure Kinect

## 参考資料

- [ARCore Depth API Documentation](https://developers.google.com/ar/develop/java/depth)
- [ARCore Camera Configuration](https://developers.google.com/ar/reference/java/com/google/ar/core/ArCameraConfig)

最終更新: 2026-01-08 10:14:57
---

# Android側でのDepth解像度向上ガイド

## 現状の問題

診断結果から以下の問題が判明：
- **深度解像度: 160x90** (14,400ピクセル) - 非常に低い
- **有効深度ピクセル: 0.4%** (99.6%が無効値マーカー)
- これはARCore Depth APIの**デフォルト解像度**で、明示的に解像度を指定していない可能性が高い

## ARCore Depth APIの解像度設定

### ARCore Depth APIの解像度オプション

ARCore Depth APIでは、`ArCameraConfig`または`ArSession`で深度解像度を設定できます。

#### 1. カメラ設定での解像度指定（推奨）

```java
// ARCore Depth APIの解像度を設定
ArSession session = new ArSession(context);

// カメラ設定を取得
ArCameraConfigFilter filter = new ArCameraConfigFilter(session);
ArCameraConfigList configList = session.getSupportedCameraConfigs(filter);

// 深度解像度が高い設定を選択
ArCameraConfig bestConfig = null;
int maxDepthSize = 0;
for (ArCameraConfig config : configList) {
    ArCameraConfig.DepthSensorUsage usage = config.getDepthSensorUsage();
    
    // 深度解像度を確認（直接取得できない場合、ターミナル解像度から推測）
    // より高い解像度の設定を選択
    int depthWidth = config.getImageSize().getWidth();  // 深度は通常カメラ解像度より低い
    if (depthWidth > maxDepthSize) {
        maxDepthSize = depthWidth;
        bestConfig = config;
    }
}

if (bestConfig != null) {
    session.setCameraConfig(bestConfig);
}
```

#### 2. ARCore Sessionの深度設定（直接指定）

```java
// ARCore 1.30以降では、深度解像度をより直接的に制御可能
ArConfig config = new ArConfig(session);
config.setDepthMode(ArConfig.DepthMode.AUTOMATIC);  // または DEPTH_MODE_RAW_DEPTH_ONLY

// 深度解像度の優先順位を設定（利用可能な場合）
// 注意: ARCoreのバージョンによってAPIが異なる可能性があります
```

#### 3. Depth APIでの最大解像度取得

```java
// 利用可能な深度解像度を取得
ArDepthPointCloud depthPointCloud = frame.acquireDepthPointCloud();

// 深度画像の解像度を確認
int depthWidth = depthPointCloud.getWidth();
int depthHeight = depthPointCloud.getHeight();

// より高い解像度が必要な場合、カメラ設定を調整
```

### 実装例（Kotlin/Java）

#### Androidアプリ側での設定

```kotlin
// ARCore Session初期化時に深度解像度を最大にする
fun initializeArCore(context: Context): ArSession? {
    val session = ArSession(context)
    
    try {
        // デフォルト設定を取得
        val defaultConfig = ArConfig(session)
        defaultConfig.depthMode = ArConfig.DepthMode.AUTOMATIC
        
        // サポートされているカメラ設定を確認
        val configFilter = ArCameraConfigFilter(session)
        val configList = session.getSupportedCameraConfigs(configFilter)
        
        // 最大解像度の設定を選択
        var bestConfig: ArCameraConfig? = null
        var maxResolution = 0
        
        for (i in 0 until configList.size) {
            val config = configList[i]
            val imageSize = config.imageSize
            
            // 画像解像度から深度解像度を推測（深度は通常1/4〜1/2）
            val estimatedDepthResolution = imageSize.width * imageSize.height
            
            if (estimatedDepthResolution > maxResolution) {
                maxResolution = estimatedDepthResolution
                bestConfig = config
            }
        }
        
        // 最適な設定を適用
        if (bestConfig != null) {
            session.setCameraConfig(bestConfig)
            Log.d(TAG, "Depth resolution optimized: ${bestConfig.imageSize}")
        }
        
        session.configure(defaultConfig)
        return session
        
    } catch (e: Exception) {
        Log.e(TAG, "ARCore initialization failed", e)
        return null
    }
}
```

#### 深度データ取得時の解像度確認

```kotlin
// フレームごとに深度データを取得
fun processFrame(frame: ArFrame) {
    val depthImage = frame.acquireDepthImage()
    
    if (depthImage != null) {
        val width = depthImage.width
        val height = depthImage.height
        
        Log.d(TAG, "Depth resolution: ${width}x${height}")
        
        // 期待される解像度より低い場合は警告
        if (width < 320 || height < 240) {
            Log.w(TAG, "Low depth resolution detected: ${width}x${height}")
            Log.w(TAG, "Consider adjusting camera config for higher depth resolution")
        }
        
        // 深度データを保存
        saveDepthImage(depthImage, frame.timestamp)
        
        depthImage.close()
    }
}
```

## ARCore Depth解像度の制約

### デバイスによる制約

1. **Depth Camera搭載デバイス** (iPhone 15 Proなど)
   - より高解像度の深度データが取得可能
   - 通常: 256x192, 320x240, 640x480など

2. **推定Depth（Motion Stereo + ML）** (Pixel 7 Proなど)
   - 解像度が制限される（160x90, 256x192など）
   - デバイスの性能とARCoreのバージョンに依存

3. **Depth APIのバージョン**
   - ARCore 1.20以降: より高解像度をサポート
   - 古いバージョン: 解像度が制限される

### 推奨される解像度

- **最小: 256x192** (49,152ピクセル)
- **推奨: 320x240** (76,800ピクセル)
- **理想: 640x480** (307,200ピクセル) - Depth Camera搭載デバイスのみ

現在の160x90 (14,400ピクセル)は**非常に低い**ため、可能な限り向上させる必要があります。

## 実装チェックリスト

### Androidアプリ側での確認事項

1. **ARCore Sessionの設定を確認**
   ```kotlin
   // 現在のカメラ設定を確認
   val currentConfig = session.cameraConfig
   Log.d(TAG, "Current camera config: ${currentConfig.imageSize}")
   ```

2. **利用可能な深度解像度を確認**
   ```kotlin
   // サポートされている設定を確認
   val configList = session.getSupportedCameraConfigs(ArCameraConfigFilter(session))
   for (config in configList) {
       Log.d(TAG, "Available config: ${config.imageSize}")
   }
   ```

3. **深度画像の解像度をログ出力**
   ```kotlin
   val depthImage = frame.acquireDepthImage()
   Log.d(TAG, "Depth image size: ${depthImage.width}x${depthImage.height}")
   ```

### サーバー側での確認

診断スクリプトで確認：
```bash
python diagnose_depth.py <job_id>
```

期待される結果：
- Depth resolution: 320x240以上
- Valid pixels: 10%以上

## 対処法

### 即座に実施可能（サーバー側）

1. **深度前処理の強化**
   - 穴埋め（inpainting）を実装
   - 無効値の補間

2. **TSDFパラメータの調整**
   - `voxel_length`を大きく（0.04m以上）
   - `depth_trunc`を適切に設定（診断結果の99パーセンタイル値）

### 根本的解決（Androidアプリ側）

1. **ARCore Session設定の見直し**
   - カメラ設定で最高解像度を選択
   - Depth APIのバージョンを確認

2. **ARCoreのバージョン更新**
   - 最新バージョンでより高解像度をサポート

3. **Depth Camera搭載デバイスの使用**
   - iPhone 15 Pro / iPad Pro
   - Intel RealSense
   - Azure Kinect

## 参考資料

- [ARCore Depth API Documentation](https://developers.google.com/ar/develop/java/depth)
- [ARCore Camera Configuration](https://developers.google.com/ar/reference/java/com/google/ar/core/ArCameraConfig)

最終更新: 2026-01-08 10:14:57
---

# Android側でのDepth解像度向上ガイド

## 現状の問題

診断結果から以下の問題が判明：
- **深度解像度: 160x90** (14,400ピクセル) - 非常に低い
- **有効深度ピクセル: 0.4%** (99.6%が無効値マーカー)
- これはARCore Depth APIの**デフォルト解像度**で、明示的に解像度を指定していない可能性が高い

## ARCore Depth APIの解像度設定

### ARCore Depth APIの解像度オプション

ARCore Depth APIでは、`ArCameraConfig`または`ArSession`で深度解像度を設定できます。

#### 1. カメラ設定での解像度指定（推奨）

```java
// ARCore Depth APIの解像度を設定
ArSession session = new ArSession(context);

// カメラ設定を取得
ArCameraConfigFilter filter = new ArCameraConfigFilter(session);
ArCameraConfigList configList = session.getSupportedCameraConfigs(filter);

// 深度解像度が高い設定を選択
ArCameraConfig bestConfig = null;
int maxDepthSize = 0;
for (ArCameraConfig config : configList) {
    ArCameraConfig.DepthSensorUsage usage = config.getDepthSensorUsage();
    
    // 深度解像度を確認（直接取得できない場合、ターミナル解像度から推測）
    // より高い解像度の設定を選択
    int depthWidth = config.getImageSize().getWidth();  // 深度は通常カメラ解像度より低い
    if (depthWidth > maxDepthSize) {
        maxDepthSize = depthWidth;
        bestConfig = config;
    }
}

if (bestConfig != null) {
    session.setCameraConfig(bestConfig);
}
```

#### 2. ARCore Sessionの深度設定（直接指定）

```java
// ARCore 1.30以降では、深度解像度をより直接的に制御可能
ArConfig config = new ArConfig(session);
config.setDepthMode(ArConfig.DepthMode.AUTOMATIC);  // または DEPTH_MODE_RAW_DEPTH_ONLY

// 深度解像度の優先順位を設定（利用可能な場合）
// 注意: ARCoreのバージョンによってAPIが異なる可能性があります
```

#### 3. Depth APIでの最大解像度取得

```java
// 利用可能な深度解像度を取得
ArDepthPointCloud depthPointCloud = frame.acquireDepthPointCloud();

// 深度画像の解像度を確認
int depthWidth = depthPointCloud.getWidth();
int depthHeight = depthPointCloud.getHeight();

// より高い解像度が必要な場合、カメラ設定を調整
```

### 実装例（Kotlin/Java）

#### Androidアプリ側での設定

```kotlin
// ARCore Session初期化時に深度解像度を最大にする
fun initializeArCore(context: Context): ArSession? {
    val session = ArSession(context)
    
    try {
        // デフォルト設定を取得
        val defaultConfig = ArConfig(session)
        defaultConfig.depthMode = ArConfig.DepthMode.AUTOMATIC
        
        // サポートされているカメラ設定を確認
        val configFilter = ArCameraConfigFilter(session)
        val configList = session.getSupportedCameraConfigs(configFilter)
        
        // 最大解像度の設定を選択
        var bestConfig: ArCameraConfig? = null
        var maxResolution = 0
        
        for (i in 0 until configList.size) {
            val config = configList[i]
            val imageSize = config.imageSize
            
            // 画像解像度から深度解像度を推測（深度は通常1/4〜1/2）
            val estimatedDepthResolution = imageSize.width * imageSize.height
            
            if (estimatedDepthResolution > maxResolution) {
                maxResolution = estimatedDepthResolution
                bestConfig = config
            }
        }
        
        // 最適な設定を適用
        if (bestConfig != null) {
            session.setCameraConfig(bestConfig)
            Log.d(TAG, "Depth resolution optimized: ${bestConfig.imageSize}")
        }
        
        session.configure(defaultConfig)
        return session
        
    } catch (e: Exception) {
        Log.e(TAG, "ARCore initialization failed", e)
        return null
    }
}
```

#### 深度データ取得時の解像度確認

```kotlin
// フレームごとに深度データを取得
fun processFrame(frame: ArFrame) {
    val depthImage = frame.acquireDepthImage()
    
    if (depthImage != null) {
        val width = depthImage.width
        val height = depthImage.height
        
        Log.d(TAG, "Depth resolution: ${width}x${height}")
        
        // 期待される解像度より低い場合は警告
        if (width < 320 || height < 240) {
            Log.w(TAG, "Low depth resolution detected: ${width}x${height}")
            Log.w(TAG, "Consider adjusting camera config for higher depth resolution")
        }
        
        // 深度データを保存
        saveDepthImage(depthImage, frame.timestamp)
        
        depthImage.close()
    }
}
```

## ARCore Depth解像度の制約

### デバイスによる制約

1. **Depth Camera搭載デバイス** (iPhone 15 Proなど)
   - より高解像度の深度データが取得可能
   - 通常: 256x192, 320x240, 640x480など

2. **推定Depth（Motion Stereo + ML）** (Pixel 7 Proなど)
   - 解像度が制限される（160x90, 256x192など）
   - デバイスの性能とARCoreのバージョンに依存

3. **Depth APIのバージョン**
   - ARCore 1.20以降: より高解像度をサポート
   - 古いバージョン: 解像度が制限される

### 推奨される解像度

- **最小: 256x192** (49,152ピクセル)
- **推奨: 320x240** (76,800ピクセル)
- **理想: 640x480** (307,200ピクセル) - Depth Camera搭載デバイスのみ

現在の160x90 (14,400ピクセル)は**非常に低い**ため、可能な限り向上させる必要があります。

## 実装チェックリスト

### Androidアプリ側での確認事項

1. **ARCore Sessionの設定を確認**
   ```kotlin
   // 現在のカメラ設定を確認
   val currentConfig = session.cameraConfig
   Log.d(TAG, "Current camera config: ${currentConfig.imageSize}")
   ```

2. **利用可能な深度解像度を確認**
   ```kotlin
   // サポートされている設定を確認
   val configList = session.getSupportedCameraConfigs(ArCameraConfigFilter(session))
   for (config in configList) {
       Log.d(TAG, "Available config: ${config.imageSize}")
   }
   ```

3. **深度画像の解像度をログ出力**
   ```kotlin
   val depthImage = frame.acquireDepthImage()
   Log.d(TAG, "Depth image size: ${depthImage.width}x${depthImage.height}")
   ```

### サーバー側での確認

診断スクリプトで確認：
```bash
python diagnose_depth.py <job_id>
```

期待される結果：
- Depth resolution: 320x240以上
- Valid pixels: 10%以上

## 対処法

### 即座に実施可能（サーバー側）

1. **深度前処理の強化**
   - 穴埋め（inpainting）を実装
   - 無効値の補間

2. **TSDFパラメータの調整**
   - `voxel_length`を大きく（0.04m以上）
   - `depth_trunc`を適切に設定（診断結果の99パーセンタイル値）

### 根本的解決（Androidアプリ側）

1. **ARCore Session設定の見直し**
   - カメラ設定で最高解像度を選択
   - Depth APIのバージョンを確認

2. **ARCoreのバージョン更新**
   - 最新バージョンでより高解像度をサポート

3. **Depth Camera搭載デバイスの使用**
   - iPhone 15 Pro / iPad Pro
   - Intel RealSense
   - Azure Kinect

## 参考資料

- [ARCore Depth API Documentation](https://developers.google.com/ar/develop/java/depth)
- [ARCore Camera Configuration](https://developers.google.com/ar/reference/java/com/google/ar/core/ArCameraConfig)

最終更新: 2026-01-08 10:14:57
---

# Android側でのDepth解像度向上ガイド

## 現状の問題

診断結果から以下の問題が判明：
- **深度解像度: 160x90** (14,400ピクセル) - 非常に低い
- **有効深度ピクセル: 0.4%** (99.6%が無効値マーカー)
- これはARCore Depth APIの**デフォルト解像度**で、明示的に解像度を指定していない可能性が高い

## ARCore Depth APIの解像度設定

### ARCore Depth APIの解像度オプション

ARCore Depth APIでは、`ArCameraConfig`または`ArSession`で深度解像度を設定できます。

#### 1. カメラ設定での解像度指定（推奨）

```java
// ARCore Depth APIの解像度を設定
ArSession session = new ArSession(context);

// カメラ設定を取得
ArCameraConfigFilter filter = new ArCameraConfigFilter(session);
ArCameraConfigList configList = session.getSupportedCameraConfigs(filter);

// 深度解像度が高い設定を選択
ArCameraConfig bestConfig = null;
int maxDepthSize = 0;
for (ArCameraConfig config : configList) {
    ArCameraConfig.DepthSensorUsage usage = config.getDepthSensorUsage();
    
    // 深度解像度を確認（直接取得できない場合、ターミナル解像度から推測）
    // より高い解像度の設定を選択
    int depthWidth = config.getImageSize().getWidth();  // 深度は通常カメラ解像度より低い
    if (depthWidth > maxDepthSize) {
        maxDepthSize = depthWidth;
        bestConfig = config;
    }
}

if (bestConfig != null) {
    session.setCameraConfig(bestConfig);
}
```

#### 2. ARCore Sessionの深度設定（直接指定）

```java
// ARCore 1.30以降では、深度解像度をより直接的に制御可能
ArConfig config = new ArConfig(session);
config.setDepthMode(ArConfig.DepthMode.AUTOMATIC);  // または DEPTH_MODE_RAW_DEPTH_ONLY

// 深度解像度の優先順位を設定（利用可能な場合）
// 注意: ARCoreのバージョンによってAPIが異なる可能性があります
```

#### 3. Depth APIでの最大解像度取得

```java
// 利用可能な深度解像度を取得
ArDepthPointCloud depthPointCloud = frame.acquireDepthPointCloud();

// 深度画像の解像度を確認
int depthWidth = depthPointCloud.getWidth();
int depthHeight = depthPointCloud.getHeight();

// より高い解像度が必要な場合、カメラ設定を調整
```

### 実装例（Kotlin/Java）

#### Androidアプリ側での設定

```kotlin
// ARCore Session初期化時に深度解像度を最大にする
fun initializeArCore(context: Context): ArSession? {
    val session = ArSession(context)
    
    try {
        // デフォルト設定を取得
        val defaultConfig = ArConfig(session)
        defaultConfig.depthMode = ArConfig.DepthMode.AUTOMATIC
        
        // サポートされているカメラ設定を確認
        val configFilter = ArCameraConfigFilter(session)
        val configList = session.getSupportedCameraConfigs(configFilter)
        
        // 最大解像度の設定を選択
        var bestConfig: ArCameraConfig? = null
        var maxResolution = 0
        
        for (i in 0 until configList.size) {
            val config = configList[i]
            val imageSize = config.imageSize
            
            // 画像解像度から深度解像度を推測（深度は通常1/4〜1/2）
            val estimatedDepthResolution = imageSize.width * imageSize.height
            
            if (estimatedDepthResolution > maxResolution) {
                maxResolution = estimatedDepthResolution
                bestConfig = config
            }
        }
        
        // 最適な設定を適用
        if (bestConfig != null) {
            session.setCameraConfig(bestConfig)
            Log.d(TAG, "Depth resolution optimized: ${bestConfig.imageSize}")
        }
        
        session.configure(defaultConfig)
        return session
        
    } catch (e: Exception) {
        Log.e(TAG, "ARCore initialization failed", e)
        return null
    }
}
```

#### 深度データ取得時の解像度確認

```kotlin
// フレームごとに深度データを取得
fun processFrame(frame: ArFrame) {
    val depthImage = frame.acquireDepthImage()
    
    if (depthImage != null) {
        val width = depthImage.width
        val height = depthImage.height
        
        Log.d(TAG, "Depth resolution: ${width}x${height}")
        
        // 期待される解像度より低い場合は警告
        if (width < 320 || height < 240) {
            Log.w(TAG, "Low depth resolution detected: ${width}x${height}")
            Log.w(TAG, "Consider adjusting camera config for higher depth resolution")
        }
        
        // 深度データを保存
        saveDepthImage(depthImage, frame.timestamp)
        
        depthImage.close()
    }
}
```

## ARCore Depth解像度の制約

### デバイスによる制約

1. **Depth Camera搭載デバイス** (iPhone 15 Proなど)
   - より高解像度の深度データが取得可能
   - 通常: 256x192, 320x240, 640x480など

2. **推定Depth（Motion Stereo + ML）** (Pixel 7 Proなど)
   - 解像度が制限される（160x90, 256x192など）
   - デバイスの性能とARCoreのバージョンに依存

3. **Depth APIのバージョン**
   - ARCore 1.20以降: より高解像度をサポート
   - 古いバージョン: 解像度が制限される

### 推奨される解像度

- **最小: 256x192** (49,152ピクセル)
- **推奨: 320x240** (76,800ピクセル)
- **理想: 640x480** (307,200ピクセル) - Depth Camera搭載デバイスのみ

現在の160x90 (14,400ピクセル)は**非常に低い**ため、可能な限り向上させる必要があります。

## 実装チェックリスト

### Androidアプリ側での確認事項

1. **ARCore Sessionの設定を確認**
   ```kotlin
   // 現在のカメラ設定を確認
   val currentConfig = session.cameraConfig
   Log.d(TAG, "Current camera config: ${currentConfig.imageSize}")
   ```

2. **利用可能な深度解像度を確認**
   ```kotlin
   // サポートされている設定を確認
   val configList = session.getSupportedCameraConfigs(ArCameraConfigFilter(session))
   for (config in configList) {
       Log.d(TAG, "Available config: ${config.imageSize}")
   }
   ```

3. **深度画像の解像度をログ出力**
   ```kotlin
   val depthImage = frame.acquireDepthImage()
   Log.d(TAG, "Depth image size: ${depthImage.width}x${depthImage.height}")
   ```

### サーバー側での確認

診断スクリプトで確認：
```bash
python diagnose_depth.py <job_id>
```

期待される結果：
- Depth resolution: 320x240以上
- Valid pixels: 10%以上

## 対処法

### 即座に実施可能（サーバー側）

1. **深度前処理の強化**
   - 穴埋め（inpainting）を実装
   - 無効値の補間

2. **TSDFパラメータの調整**
   - `voxel_length`を大きく（0.04m以上）
   - `depth_trunc`を適切に設定（診断結果の99パーセンタイル値）

### 根本的解決（Androidアプリ側）

1. **ARCore Session設定の見直し**
   - カメラ設定で最高解像度を選択
   - Depth APIのバージョンを確認

2. **ARCoreのバージョン更新**
   - 最新バージョンでより高解像度をサポート

3. **Depth Camera搭載デバイスの使用**
   - iPhone 15 Pro / iPad Pro
   - Intel RealSense
   - Azure Kinect

## 参考資料

- [ARCore Depth API Documentation](https://developers.google.com/ar/develop/java/depth)
- [ARCore Camera Configuration](https://developers.google.com/ar/reference/java/com/google/ar/core/ArCameraConfig)

最終更新: 2026-01-08 10:14:57
---

# Android側でのDepth解像度向上ガイド

## 現状の問題

診断結果から以下の問題が判明：
- **深度解像度: 160x90** (14,400ピクセル) - 非常に低い
- **有効深度ピクセル: 0.4%** (99.6%が無効値マーカー)
- これはARCore Depth APIの**デフォルト解像度**で、明示的に解像度を指定していない可能性が高い

## ARCore Depth APIの解像度設定

### ARCore Depth APIの解像度オプション

ARCore Depth APIでは、`ArCameraConfig`または`ArSession`で深度解像度を設定できます。

#### 1. カメラ設定での解像度指定（推奨）

```java
// ARCore Depth APIの解像度を設定
ArSession session = new ArSession(context);

// カメラ設定を取得
ArCameraConfigFilter filter = new ArCameraConfigFilter(session);
ArCameraConfigList configList = session.getSupportedCameraConfigs(filter);

// 深度解像度が高い設定を選択
ArCameraConfig bestConfig = null;
int maxDepthSize = 0;
for (ArCameraConfig config : configList) {
    ArCameraConfig.DepthSensorUsage usage = config.getDepthSensorUsage();
    
    // 深度解像度を確認（直接取得できない場合、ターミナル解像度から推測）
    // より高い解像度の設定を選択
    int depthWidth = config.getImageSize().getWidth();  // 深度は通常カメラ解像度より低い
    if (depthWidth > maxDepthSize) {
        maxDepthSize = depthWidth;
        bestConfig = config;
    }
}

if (bestConfig != null) {
    session.setCameraConfig(bestConfig);
}
```

#### 2. ARCore Sessionの深度設定（直接指定）

```java
// ARCore 1.30以降では、深度解像度をより直接的に制御可能
ArConfig config = new ArConfig(session);
config.setDepthMode(ArConfig.DepthMode.AUTOMATIC);  // または DEPTH_MODE_RAW_DEPTH_ONLY

// 深度解像度の優先順位を設定（利用可能な場合）
// 注意: ARCoreのバージョンによってAPIが異なる可能性があります
```

#### 3. Depth APIでの最大解像度取得

```java
// 利用可能な深度解像度を取得
ArDepthPointCloud depthPointCloud = frame.acquireDepthPointCloud();

// 深度画像の解像度を確認
int depthWidth = depthPointCloud.getWidth();
int depthHeight = depthPointCloud.getHeight();

// より高い解像度が必要な場合、カメラ設定を調整
```

### 実装例（Kotlin/Java）

#### Androidアプリ側での設定

```kotlin
// ARCore Session初期化時に深度解像度を最大にする
fun initializeArCore(context: Context): ArSession? {
    val session = ArSession(context)
    
    try {
        // デフォルト設定を取得
        val defaultConfig = ArConfig(session)
        defaultConfig.depthMode = ArConfig.DepthMode.AUTOMATIC
        
        // サポートされているカメラ設定を確認
        val configFilter = ArCameraConfigFilter(session)
        val configList = session.getSupportedCameraConfigs(configFilter)
        
        // 最大解像度の設定を選択
        var bestConfig: ArCameraConfig? = null
        var maxResolution = 0
        
        for (i in 0 until configList.size) {
            val config = configList[i]
            val imageSize = config.imageSize
            
            // 画像解像度から深度解像度を推測（深度は通常1/4〜1/2）
            val estimatedDepthResolution = imageSize.width * imageSize.height
            
            if (estimatedDepthResolution > maxResolution) {
                maxResolution = estimatedDepthResolution
                bestConfig = config
            }
        }
        
        // 最適な設定を適用
        if (bestConfig != null) {
            session.setCameraConfig(bestConfig)
            Log.d(TAG, "Depth resolution optimized: ${bestConfig.imageSize}")
        }
        
        session.configure(defaultConfig)
        return session
        
    } catch (e: Exception) {
        Log.e(TAG, "ARCore initialization failed", e)
        return null
    }
}
```

#### 深度データ取得時の解像度確認

```kotlin
// フレームごとに深度データを取得
fun processFrame(frame: ArFrame) {
    val depthImage = frame.acquireDepthImage()
    
    if (depthImage != null) {
        val width = depthImage.width
        val height = depthImage.height
        
        Log.d(TAG, "Depth resolution: ${width}x${height}")
        
        // 期待される解像度より低い場合は警告
        if (width < 320 || height < 240) {
            Log.w(TAG, "Low depth resolution detected: ${width}x${height}")
            Log.w(TAG, "Consider adjusting camera config for higher depth resolution")
        }
        
        // 深度データを保存
        saveDepthImage(depthImage, frame.timestamp)
        
        depthImage.close()
    }
}
```

## ARCore Depth解像度の制約

### デバイスによる制約

1. **Depth Camera搭載デバイス** (iPhone 15 Proなど)
   - より高解像度の深度データが取得可能
   - 通常: 256x192, 320x240, 640x480など

2. **推定Depth（Motion Stereo + ML）** (Pixel 7 Proなど)
   - 解像度が制限される（160x90, 256x192など）
   - デバイスの性能とARCoreのバージョンに依存

3. **Depth APIのバージョン**
   - ARCore 1.20以降: より高解像度をサポート
   - 古いバージョン: 解像度が制限される

### 推奨される解像度

- **最小: 256x192** (49,152ピクセル)
- **推奨: 320x240** (76,800ピクセル)
- **理想: 640x480** (307,200ピクセル) - Depth Camera搭載デバイスのみ

現在の160x90 (14,400ピクセル)は**非常に低い**ため、可能な限り向上させる必要があります。

## 実装チェックリスト

### Androidアプリ側での確認事項

1. **ARCore Sessionの設定を確認**
   ```kotlin
   // 現在のカメラ設定を確認
   val currentConfig = session.cameraConfig
   Log.d(TAG, "Current camera config: ${currentConfig.imageSize}")
   ```

2. **利用可能な深度解像度を確認**
   ```kotlin
   // サポートされている設定を確認
   val configList = session.getSupportedCameraConfigs(ArCameraConfigFilter(session))
   for (config in configList) {
       Log.d(TAG, "Available config: ${config.imageSize}")
   }
   ```

3. **深度画像の解像度をログ出力**
   ```kotlin
   val depthImage = frame.acquireDepthImage()
   Log.d(TAG, "Depth image size: ${depthImage.width}x${depthImage.height}")
   ```

### サーバー側での確認

診断スクリプトで確認：
```bash
python diagnose_depth.py <job_id>
```

期待される結果：
- Depth resolution: 320x240以上
- Valid pixels: 10%以上

## 対処法

### 即座に実施可能（サーバー側）

1. **深度前処理の強化**
   - 穴埋め（inpainting）を実装
   - 無効値の補間

2. **TSDFパラメータの調整**
   - `voxel_length`を大きく（0.04m以上）
   - `depth_trunc`を適切に設定（診断結果の99パーセンタイル値）

### 根本的解決（Androidアプリ側）

1. **ARCore Session設定の見直し**
   - カメラ設定で最高解像度を選択
   - Depth APIのバージョンを確認

2. **ARCoreのバージョン更新**
   - 最新バージョンでより高解像度をサポート

3. **Depth Camera搭載デバイスの使用**
   - iPhone 15 Pro / iPad Pro
   - Intel RealSense
   - Azure Kinect

## 参考資料

- [ARCore Depth API Documentation](https://developers.google.com/ar/develop/java/depth)
- [ARCore Camera Configuration](https://developers.google.com/ar/reference/java/com/google/ar/core/ArCameraConfig)

最終更新: 2026-01-08 10:14:57
---

# Android側でのDepth解像度向上ガイド

## 現状の問題

診断結果から以下の問題が判明：
- **深度解像度: 160x90** (14,400ピクセル) - 非常に低い
- **有効深度ピクセル: 0.4%** (99.6%が無効値マーカー)
- これはARCore Depth APIの**デフォルト解像度**で、明示的に解像度を指定していない可能性が高い

## ARCore Depth APIの解像度設定

### ARCore Depth APIの解像度オプション

ARCore Depth APIでは、`ArCameraConfig`または`ArSession`で深度解像度を設定できます。

#### 1. カメラ設定での解像度指定（推奨）

```java
// ARCore Depth APIの解像度を設定
ArSession session = new ArSession(context);

// カメラ設定を取得
ArCameraConfigFilter filter = new ArCameraConfigFilter(session);
ArCameraConfigList configList = session.getSupportedCameraConfigs(filter);

// 深度解像度が高い設定を選択
ArCameraConfig bestConfig = null;
int maxDepthSize = 0;
for (ArCameraConfig config : configList) {
    ArCameraConfig.DepthSensorUsage usage = config.getDepthSensorUsage();
    
    // 深度解像度を確認（直接取得できない場合、ターミナル解像度から推測）
    // より高い解像度の設定を選択
    int depthWidth = config.getImageSize().getWidth();  // 深度は通常カメラ解像度より低い
    if (depthWidth > maxDepthSize) {
        maxDepthSize = depthWidth;
        bestConfig = config;
    }
}

if (bestConfig != null) {
    session.setCameraConfig(bestConfig);
}
```

#### 2. ARCore Sessionの深度設定（直接指定）

```java
// ARCore 1.30以降では、深度解像度をより直接的に制御可能
ArConfig config = new ArConfig(session);
config.setDepthMode(ArConfig.DepthMode.AUTOMATIC);  // または DEPTH_MODE_RAW_DEPTH_ONLY

// 深度解像度の優先順位を設定（利用可能な場合）
// 注意: ARCoreのバージョンによってAPIが異なる可能性があります
```

#### 3. Depth APIでの最大解像度取得

```java
// 利用可能な深度解像度を取得
ArDepthPointCloud depthPointCloud = frame.acquireDepthPointCloud();

// 深度画像の解像度を確認
int depthWidth = depthPointCloud.getWidth();
int depthHeight = depthPointCloud.getHeight();

// より高い解像度が必要な場合、カメラ設定を調整
```

### 実装例（Kotlin/Java）

#### Androidアプリ側での設定

```kotlin
// ARCore Session初期化時に深度解像度を最大にする
fun initializeArCore(context: Context): ArSession? {
    val session = ArSession(context)
    
    try {
        // デフォルト設定を取得
        val defaultConfig = ArConfig(session)
        defaultConfig.depthMode = ArConfig.DepthMode.AUTOMATIC
        
        // サポートされているカメラ設定を確認
        val configFilter = ArCameraConfigFilter(session)
        val configList = session.getSupportedCameraConfigs(configFilter)
        
        // 最大解像度の設定を選択
        var bestConfig: ArCameraConfig? = null
        var maxResolution = 0
        
        for (i in 0 until configList.size) {
            val config = configList[i]
            val imageSize = config.imageSize
            
            // 画像解像度から深度解像度を推測（深度は通常1/4〜1/2）
            val estimatedDepthResolution = imageSize.width * imageSize.height
            
            if (estimatedDepthResolution > maxResolution) {
                maxResolution = estimatedDepthResolution
                bestConfig = config
            }
        }
        
        // 最適な設定を適用
        if (bestConfig != null) {
            session.setCameraConfig(bestConfig)
            Log.d(TAG, "Depth resolution optimized: ${bestConfig.imageSize}")
        }
        
        session.configure(defaultConfig)
        return session
        
    } catch (e: Exception) {
        Log.e(TAG, "ARCore initialization failed", e)
        return null
    }
}
```

#### 深度データ取得時の解像度確認

```kotlin
// フレームごとに深度データを取得
fun processFrame(frame: ArFrame) {
    val depthImage = frame.acquireDepthImage()
    
    if (depthImage != null) {
        val width = depthImage.width
        val height = depthImage.height
        
        Log.d(TAG, "Depth resolution: ${width}x${height}")
        
        // 期待される解像度より低い場合は警告
        if (width < 320 || height < 240) {
            Log.w(TAG, "Low depth resolution detected: ${width}x${height}")
            Log.w(TAG, "Consider adjusting camera config for higher depth resolution")
        }
        
        // 深度データを保存
        saveDepthImage(depthImage, frame.timestamp)
        
        depthImage.close()
    }
}
```

## ARCore Depth解像度の制約

### デバイスによる制約

1. **Depth Camera搭載デバイス** (iPhone 15 Proなど)
   - より高解像度の深度データが取得可能
   - 通常: 256x192, 320x240, 640x480など

2. **推定Depth（Motion Stereo + ML）** (Pixel 7 Proなど)
   - 解像度が制限される（160x90, 256x192など）
   - デバイスの性能とARCoreのバージョンに依存

3. **Depth APIのバージョン**
   - ARCore 1.20以降: より高解像度をサポート
   - 古いバージョン: 解像度が制限される

### 推奨される解像度

- **最小: 256x192** (49,152ピクセル)
- **推奨: 320x240** (76,800ピクセル)
- **理想: 640x480** (307,200ピクセル) - Depth Camera搭載デバイスのみ

現在の160x90 (14,400ピクセル)は**非常に低い**ため、可能な限り向上させる必要があります。

## 実装チェックリスト

### Androidアプリ側での確認事項

1. **ARCore Sessionの設定を確認**
   ```kotlin
   // 現在のカメラ設定を確認
   val currentConfig = session.cameraConfig
   Log.d(TAG, "Current camera config: ${currentConfig.imageSize}")
   ```

2. **利用可能な深度解像度を確認**
   ```kotlin
   // サポートされている設定を確認
   val configList = session.getSupportedCameraConfigs(ArCameraConfigFilter(session))
   for (config in configList) {
       Log.d(TAG, "Available config: ${config.imageSize}")
   }
   ```

3. **深度画像の解像度をログ出力**
   ```kotlin
   val depthImage = frame.acquireDepthImage()
   Log.d(TAG, "Depth image size: ${depthImage.width}x${depthImage.height}")
   ```

### サーバー側での確認

診断スクリプトで確認：
```bash
python diagnose_depth.py <job_id>
```

期待される結果：
- Depth resolution: 320x240以上
- Valid pixels: 10%以上

## 対処法

### 即座に実施可能（サーバー側）

1. **深度前処理の強化**
   - 穴埋め（inpainting）を実装
   - 無効値の補間

2. **TSDFパラメータの調整**
   - `voxel_length`を大きく（0.04m以上）
   - `depth_trunc`を適切に設定（診断結果の99パーセンタイル値）

### 根本的解決（Androidアプリ側）

1. **ARCore Session設定の見直し**
   - カメラ設定で最高解像度を選択
   - Depth APIのバージョンを確認

2. **ARCoreのバージョン更新**
   - 最新バージョンでより高解像度をサポート

3. **Depth Camera搭載デバイスの使用**
   - iPhone 15 Pro / iPad Pro
   - Intel RealSense
   - Azure Kinect

## 参考資料

- [ARCore Depth API Documentation](https://developers.google.com/ar/develop/java/depth)
- [ARCore Camera Configuration](https://developers.google.com/ar/reference/java/com/google/ar/core/ArCameraConfig)

最終更新: 2026-01-08 10:14:57
---

# Android側でのDepth解像度向上ガイド

## 現状の問題

診断結果から以下の問題が判明：
- **深度解像度: 160x90** (14,400ピクセル) - 非常に低い
- **有効深度ピクセル: 0.4%** (99.6%が無効値マーカー)
- これはARCore Depth APIの**デフォルト解像度**で、明示的に解像度を指定していない可能性が高い

## ARCore Depth APIの解像度設定

### ARCore Depth APIの解像度オプション

ARCore Depth APIでは、`ArCameraConfig`または`ArSession`で深度解像度を設定できます。

#### 1. カメラ設定での解像度指定（推奨）

```java
// ARCore Depth APIの解像度を設定
ArSession session = new ArSession(context);

// カメラ設定を取得
ArCameraConfigFilter filter = new ArCameraConfigFilter(session);
ArCameraConfigList configList = session.getSupportedCameraConfigs(filter);

// 深度解像度が高い設定を選択
ArCameraConfig bestConfig = null;
int maxDepthSize = 0;
for (ArCameraConfig config : configList) {
    ArCameraConfig.DepthSensorUsage usage = config.getDepthSensorUsage();
    
    // 深度解像度を確認（直接取得できない場合、ターミナル解像度から推測）
    // より高い解像度の設定を選択
    int depthWidth = config.getImageSize().getWidth();  // 深度は通常カメラ解像度より低い
    if (depthWidth > maxDepthSize) {
        maxDepthSize = depthWidth;
        bestConfig = config;
    }
}

if (bestConfig != null) {
    session.setCameraConfig(bestConfig);
}
```

#### 2. ARCore Sessionの深度設定（直接指定）

```java
// ARCore 1.30以降では、深度解像度をより直接的に制御可能
ArConfig config = new ArConfig(session);
config.setDepthMode(ArConfig.DepthMode.AUTOMATIC);  // または DEPTH_MODE_RAW_DEPTH_ONLY

// 深度解像度の優先順位を設定（利用可能な場合）
// 注意: ARCoreのバージョンによってAPIが異なる可能性があります
```

#### 3. Depth APIでの最大解像度取得

```java
// 利用可能な深度解像度を取得
ArDepthPointCloud depthPointCloud = frame.acquireDepthPointCloud();

// 深度画像の解像度を確認
int depthWidth = depthPointCloud.getWidth();
int depthHeight = depthPointCloud.getHeight();

// より高い解像度が必要な場合、カメラ設定を調整
```

### 実装例（Kotlin/Java）

#### Androidアプリ側での設定

```kotlin
// ARCore Session初期化時に深度解像度を最大にする
fun initializeArCore(context: Context): ArSession? {
    val session = ArSession(context)
    
    try {
        // デフォルト設定を取得
        val defaultConfig = ArConfig(session)
        defaultConfig.depthMode = ArConfig.DepthMode.AUTOMATIC
        
        // サポートされているカメラ設定を確認
        val configFilter = ArCameraConfigFilter(session)
        val configList = session.getSupportedCameraConfigs(configFilter)
        
        // 最大解像度の設定を選択
        var bestConfig: ArCameraConfig? = null
        var maxResolution = 0
        
        for (i in 0 until configList.size) {
            val config = configList[i]
            val imageSize = config.imageSize
            
            // 画像解像度から深度解像度を推測（深度は通常1/4〜1/2）
            val estimatedDepthResolution = imageSize.width * imageSize.height
            
            if (estimatedDepthResolution > maxResolution) {
                maxResolution = estimatedDepthResolution
                bestConfig = config
            }
        }
        
        // 最適な設定を適用
        if (bestConfig != null) {
            session.setCameraConfig(bestConfig)
            Log.d(TAG, "Depth resolution optimized: ${bestConfig.imageSize}")
        }
        
        session.configure(defaultConfig)
        return session
        
    } catch (e: Exception) {
        Log.e(TAG, "ARCore initialization failed", e)
        return null
    }
}
```

#### 深度データ取得時の解像度確認

```kotlin
// フレームごとに深度データを取得
fun processFrame(frame: ArFrame) {
    val depthImage = frame.acquireDepthImage()
    
    if (depthImage != null) {
        val width = depthImage.width
        val height = depthImage.height
        
        Log.d(TAG, "Depth resolution: ${width}x${height}")
        
        // 期待される解像度より低い場合は警告
        if (width < 320 || height < 240) {
            Log.w(TAG, "Low depth resolution detected: ${width}x${height}")
            Log.w(TAG, "Consider adjusting camera config for higher depth resolution")
        }
        
        // 深度データを保存
        saveDepthImage(depthImage, frame.timestamp)
        
        depthImage.close()
    }
}
```

## ARCore Depth解像度の制約

### デバイスによる制約

1. **Depth Camera搭載デバイス** (iPhone 15 Proなど)
   - より高解像度の深度データが取得可能
   - 通常: 256x192, 320x240, 640x480など

2. **推定Depth（Motion Stereo + ML）** (Pixel 7 Proなど)
   - 解像度が制限される（160x90, 256x192など）
   - デバイスの性能とARCoreのバージョンに依存

3. **Depth APIのバージョン**
   - ARCore 1.20以降: より高解像度をサポート
   - 古いバージョン: 解像度が制限される

### 推奨される解像度

- **最小: 256x192** (49,152ピクセル)
- **推奨: 320x240** (76,800ピクセル)
- **理想: 640x480** (307,200ピクセル) - Depth Camera搭載デバイスのみ

現在の160x90 (14,400ピクセル)は**非常に低い**ため、可能な限り向上させる必要があります。

## 実装チェックリスト

### Androidアプリ側での確認事項

1. **ARCore Sessionの設定を確認**
   ```kotlin
   // 現在のカメラ設定を確認
   val currentConfig = session.cameraConfig
   Log.d(TAG, "Current camera config: ${currentConfig.imageSize}")
   ```

2. **利用可能な深度解像度を確認**
   ```kotlin
   // サポートされている設定を確認
   val configList = session.getSupportedCameraConfigs(ArCameraConfigFilter(session))
   for (config in configList) {
       Log.d(TAG, "Available config: ${config.imageSize}")
   }
   ```

3. **深度画像の解像度をログ出力**
   ```kotlin
   val depthImage = frame.acquireDepthImage()
   Log.d(TAG, "Depth image size: ${depthImage.width}x${depthImage.height}")
   ```

### サーバー側での確認

診断スクリプトで確認：
```bash
python diagnose_depth.py <job_id>
```

期待される結果：
- Depth resolution: 320x240以上
- Valid pixels: 10%以上

## 対処法

### 即座に実施可能（サーバー側）

1. **深度前処理の強化**
   - 穴埋め（inpainting）を実装
   - 無効値の補間

2. **TSDFパラメータの調整**
   - `voxel_length`を大きく（0.04m以上）
   - `depth_trunc`を適切に設定（診断結果の99パーセンタイル値）

### 根本的解決（Androidアプリ側）

1. **ARCore Session設定の見直し**
   - カメラ設定で最高解像度を選択
   - Depth APIのバージョンを確認

2. **ARCoreのバージョン更新**
   - 最新バージョンでより高解像度をサポート

3. **Depth Camera搭載デバイスの使用**
   - iPhone 15 Pro / iPad Pro
   - Intel RealSense
   - Azure Kinect

## 参考資料

- [ARCore Depth API Documentation](https://developers.google.com/ar/develop/java/depth)
- [ARCore Camera Configuration](https://developers.google.com/ar/reference/java/com/google/ar/core/ArCameraConfig)

最終更新: 2026-01-08 10:14:57
---

# Android側でのDepth解像度向上ガイド

## 現状の問題

診断結果から以下の問題が判明：
- **深度解像度: 160x90** (14,400ピクセル) - 非常に低い
- **有効深度ピクセル: 0.4%** (99.6%が無効値マーカー)
- これはARCore Depth APIの**デフォルト解像度**で、明示的に解像度を指定していない可能性が高い

## ARCore Depth APIの解像度設定

### ARCore Depth APIの解像度オプション

ARCore Depth APIでは、`ArCameraConfig`または`ArSession`で深度解像度を設定できます。

#### 1. カメラ設定での解像度指定（推奨）

```java
// ARCore Depth APIの解像度を設定
ArSession session = new ArSession(context);

// カメラ設定を取得
ArCameraConfigFilter filter = new ArCameraConfigFilter(session);
ArCameraConfigList configList = session.getSupportedCameraConfigs(filter);

// 深度解像度が高い設定を選択
ArCameraConfig bestConfig = null;
int maxDepthSize = 0;
for (ArCameraConfig config : configList) {
    ArCameraConfig.DepthSensorUsage usage = config.getDepthSensorUsage();
    
    // 深度解像度を確認（直接取得できない場合、ターミナル解像度から推測）
    // より高い解像度の設定を選択
    int depthWidth = config.getImageSize().getWidth();  // 深度は通常カメラ解像度より低い
    if (depthWidth > maxDepthSize) {
        maxDepthSize = depthWidth;
        bestConfig = config;
    }
}

if (bestConfig != null) {
    session.setCameraConfig(bestConfig);
}
```

#### 2. ARCore Sessionの深度設定（直接指定）

```java
// ARCore 1.30以降では、深度解像度をより直接的に制御可能
ArConfig config = new ArConfig(session);
config.setDepthMode(ArConfig.DepthMode.AUTOMATIC);  // または DEPTH_MODE_RAW_DEPTH_ONLY

// 深度解像度の優先順位を設定（利用可能な場合）
// 注意: ARCoreのバージョンによってAPIが異なる可能性があります
```

#### 3. Depth APIでの最大解像度取得

```java
// 利用可能な深度解像度を取得
ArDepthPointCloud depthPointCloud = frame.acquireDepthPointCloud();

// 深度画像の解像度を確認
int depthWidth = depthPointCloud.getWidth();
int depthHeight = depthPointCloud.getHeight();

// より高い解像度が必要な場合、カメラ設定を調整
```

### 実装例（Kotlin/Java）

#### Androidアプリ側での設定

```kotlin
// ARCore Session初期化時に深度解像度を最大にする
fun initializeArCore(context: Context): ArSession? {
    val session = ArSession(context)
    
    try {
        // デフォルト設定を取得
        val defaultConfig = ArConfig(session)
        defaultConfig.depthMode = ArConfig.DepthMode.AUTOMATIC
        
        // サポートされているカメラ設定を確認
        val configFilter = ArCameraConfigFilter(session)
        val configList = session.getSupportedCameraConfigs(configFilter)
        
        // 最大解像度の設定を選択
        var bestConfig: ArCameraConfig? = null
        var maxResolution = 0
        
        for (i in 0 until configList.size) {
            val config = configList[i]
            val imageSize = config.imageSize
            
            // 画像解像度から深度解像度を推測（深度は通常1/4〜1/2）
            val estimatedDepthResolution = imageSize.width * imageSize.height
            
            if (estimatedDepthResolution > maxResolution) {
                maxResolution = estimatedDepthResolution
                bestConfig = config
            }
        }
        
        // 最適な設定を適用
        if (bestConfig != null) {
            session.setCameraConfig(bestConfig)
            Log.d(TAG, "Depth resolution optimized: ${bestConfig.imageSize}")
        }
        
        session.configure(defaultConfig)
        return session
        
    } catch (e: Exception) {
        Log.e(TAG, "ARCore initialization failed", e)
        return null
    }
}
```

#### 深度データ取得時の解像度確認

```kotlin
// フレームごとに深度データを取得
fun processFrame(frame: ArFrame) {
    val depthImage = frame.acquireDepthImage()
    
    if (depthImage != null) {
        val width = depthImage.width
        val height = depthImage.height
        
        Log.d(TAG, "Depth resolution: ${width}x${height}")
        
        // 期待される解像度より低い場合は警告
        if (width < 320 || height < 240) {
            Log.w(TAG, "Low depth resolution detected: ${width}x${height}")
            Log.w(TAG, "Consider adjusting camera config for higher depth resolution")
        }
        
        // 深度データを保存
        saveDepthImage(depthImage, frame.timestamp)
        
        depthImage.close()
    }
}
```

## ARCore Depth解像度の制約

### デバイスによる制約

1. **Depth Camera搭載デバイス** (iPhone 15 Proなど)
   - より高解像度の深度データが取得可能
   - 通常: 256x192, 320x240, 640x480など

2. **推定Depth（Motion Stereo + ML）** (Pixel 7 Proなど)
   - 解像度が制限される（160x90, 256x192など）
   - デバイスの性能とARCoreのバージョンに依存

3. **Depth APIのバージョン**
   - ARCore 1.20以降: より高解像度をサポート
   - 古いバージョン: 解像度が制限される

### 推奨される解像度

- **最小: 256x192** (49,152ピクセル)
- **推奨: 320x240** (76,800ピクセル)
- **理想: 640x480** (307,200ピクセル) - Depth Camera搭載デバイスのみ

現在の160x90 (14,400ピクセル)は**非常に低い**ため、可能な限り向上させる必要があります。

## 実装チェックリスト

### Androidアプリ側での確認事項

1. **ARCore Sessionの設定を確認**
   ```kotlin
   // 現在のカメラ設定を確認
   val currentConfig = session.cameraConfig
   Log.d(TAG, "Current camera config: ${currentConfig.imageSize}")
   ```

2. **利用可能な深度解像度を確認**
   ```kotlin
   // サポートされている設定を確認
   val configList = session.getSupportedCameraConfigs(ArCameraConfigFilter(session))
   for (config in configList) {
       Log.d(TAG, "Available config: ${config.imageSize}")
   }
   ```

3. **深度画像の解像度をログ出力**
   ```kotlin
   val depthImage = frame.acquireDepthImage()
   Log.d(TAG, "Depth image size: ${depthImage.width}x${depthImage.height}")
   ```

### サーバー側での確認

診断スクリプトで確認：
```bash
python diagnose_depth.py <job_id>
```

期待される結果：
- Depth resolution: 320x240以上
- Valid pixels: 10%以上

## 対処法

### 即座に実施可能（サーバー側）

1. **深度前処理の強化**
   - 穴埋め（inpainting）を実装
   - 無効値の補間

2. **TSDFパラメータの調整**
   - `voxel_length`を大きく（0.04m以上）
   - `depth_trunc`を適切に設定（診断結果の99パーセンタイル値）

### 根本的解決（Androidアプリ側）

1. **ARCore Session設定の見直し**
   - カメラ設定で最高解像度を選択
   - Depth APIのバージョンを確認

2. **ARCoreのバージョン更新**
   - 最新バージョンでより高解像度をサポート

3. **Depth Camera搭載デバイスの使用**
   - iPhone 15 Pro / iPad Pro
   - Intel RealSense
   - Azure Kinect

## 参考資料

- [ARCore Depth API Documentation](https://developers.google.com/ar/develop/java/depth)
- [ARCore Camera Configuration](https://developers.google.com/ar/reference/java/com/google/ar/core/ArCameraConfig)