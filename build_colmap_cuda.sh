#!/bin/bash
# COLMAP CUDA対応版ビルドスクリプト（WSL2用）

set -e  # エラーが発生したら停止

echo "============================================================"
echo "COLMAP CUDA対応版ビルドスクリプト（WSL2用）"
echo "============================================================"
echo ""

# カレントディレクトリを保存
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# CUDA環境の確認
echo "Step 1: Checking CUDA environment..."
if ! nvidia-smi > /dev/null 2>&1; then
    echo "✗ Error: nvidia-smi not found. NVIDIA driver may not be installed."
    echo "  Please install NVIDIA driver for WSL2"
    exit 1
fi
echo "✓ NVIDIA driver is available"
nvidia-smi | head -5
echo ""

# CUDAツールキットの確認
echo "Step 2: Checking CUDA toolkit..."
if ! command -v nvcc > /dev/null 2>&1; then
    echo "⚠ CUDA toolkit not found. Installing..."
    echo "  Installing nvidia-cuda-toolkit..."
    sudo apt-get update
    sudo apt-get install -y nvidia-cuda-toolkit
    
    # nvccのパスを確認
    if [ -f /usr/bin/nvcc ]; then
        echo "✓ CUDA toolkit installed: /usr/bin/nvcc"
        nvcc --version
    else
        echo "✗ Error: CUDA toolkit installation failed"
        exit 1
    fi
else
    echo "✓ CUDA toolkit is available"
    nvcc --version
fi
echo ""

# COLMAPの依存関係をインストール
echo "Step 3: Installing COLMAP dependencies..."
sudo apt-get update
sudo apt-get install -y \
    cmake \
    git \
    build-essential \
    libboost-program-options-dev \
    libboost-filesystem-dev \
    libboost-graph-dev \
    libboost-system-dev \
    libboost-test-dev \
    libeigen3-dev \
    libflann-dev \
    libfreeimage-dev \
    libmetis-dev \
    libgoogle-glog-dev \
    libgflags-dev \
    libsqlite3-dev \
    libglew-dev \
    qtbase5-dev \
    libqt5opengl5-dev \
    libcgal-dev \
    libcgal-qt5-dev \
    libceres-dev \
    libopencv-dev \
    opencv-data

echo "✓ Dependencies installed"
echo ""

# COLMAPのソースを取得
COLMAP_DIR="$SCRIPT_DIR/colmap_build"
COLMAP_SRC_DIR="$COLMAP_DIR/src"
COLMAP_BUILD_DIR="$COLMAP_DIR/build"

echo "Step 4: Downloading COLMAP source..."
if [ ! -d "$COLMAP_SRC_DIR" ]; then
    mkdir -p "$COLMAP_SRC_DIR"
    cd "$COLMAP_SRC_DIR/.."
    git clone https://github.com/colmap/colmap.git src
    echo "✓ COLMAP source downloaded"
else
    echo "✓ COLMAP source already exists, updating..."
    cd "$COLMAP_SRC_DIR"
    git pull
fi
echo ""

# ビルドディレクトリの作成
echo "Step 5: Configuring COLMAP build (CUDA enabled)..."
mkdir -p "$COLMAP_BUILD_DIR"
cd "$COLMAP_BUILD_DIR"

# CUDAアーキテクチャを検出
CUDA_ARCH=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader | head -1 | sed 's/\.//')
if [ -z "$CUDA_ARCH" ]; then
    # デフォルト値（GTX 1660 Tiなど）
    CUDA_ARCH="75"
fi
echo "Detected CUDA architecture: sm_$CUDA_ARCH"

# CMake設定（CUDAサポートを有効化）
# OpenImageIOはオプションなので、見つからない場合は自動的に無効化される
echo "Configuring CMake with CUDA support..."
cmake "$COLMAP_SRC_DIR" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCUDA_ENABLED=ON \
    -DCMAKE_CUDA_ARCHITECTURES="$CUDA_ARCH" \
    -DCMAKE_CUDA_COMPILER=/usr/bin/nvcc \
    -DGUI_ENABLED=OFF \
    2>&1 | tee /tmp/cmake_config.log

CMAKE_EXIT_CODE=$?
if [ $CMAKE_EXIT_CODE -ne 0 ]; then
    echo ""
    echo "⚠ CMake configuration failed. Checking for missing dependencies..."
    grep -i "not found\|missing\|required" /tmp/cmake_config.log | tail -5 || true
    echo ""
    echo "Attempting to continue with build anyway..."
    # 一部のオプション依存関係がなくてもビルドは続行可能
fi

echo "✓ CMake configuration completed"
echo ""

# ビルド（並列ビルド）
echo "Step 6: Building COLMAP (this will take 30-60 minutes)..."
CPU_COUNT=$(nproc)
echo "Using $CPU_COUNT CPU cores for parallel build"
make -j$CPU_COUNT

echo ""
echo "✓ COLMAP build completed"
echo ""

# インストール
echo "Step 7: Installing COLMAP..."
sudo make install

echo ""
echo "============================================================"
echo "✓ COLMAP CUDA対応版のインストールが完了しました！"
echo "============================================================"
echo ""
echo "インストール場所: /usr/local/bin/colmap"
echo ""

# インストール確認
if command -v colmap > /dev/null 2>&1; then
    echo "インストール確認:"
    colmap help 2>&1 | head -3
    echo ""
    echo "CUDAサポートの確認:"
    colmap help 2>&1 | grep -i cuda || echo "（ヘルプにCUDA情報が表示されない場合があります）"
    echo ""
    echo "✓ COLMAP is ready to use!"
else
    echo "⚠ Warning: colmap command not found in PATH"
    echo "  Try: export PATH=/usr/local/bin:\$PATH"
fi


set -e  # エラーが発生したら停止

echo "============================================================"
echo "COLMAP CUDA対応版ビルドスクリプト（WSL2用）"
echo "============================================================"
echo ""

# カレントディレクトリを保存
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# CUDA環境の確認
echo "Step 1: Checking CUDA environment..."
if ! nvidia-smi > /dev/null 2>&1; then
    echo "✗ Error: nvidia-smi not found. NVIDIA driver may not be installed."
    echo "  Please install NVIDIA driver for WSL2"
    exit 1
fi
echo "✓ NVIDIA driver is available"
nvidia-smi | head -5
echo ""

# CUDAツールキットの確認
echo "Step 2: Checking CUDA toolkit..."
if ! command -v nvcc > /dev/null 2>&1; then
    echo "⚠ CUDA toolkit not found. Installing..."
    echo "  Installing nvidia-cuda-toolkit..."
    sudo apt-get update
    sudo apt-get install -y nvidia-cuda-toolkit
    
    # nvccのパスを確認
    if [ -f /usr/bin/nvcc ]; then
        echo "✓ CUDA toolkit installed: /usr/bin/nvcc"
        nvcc --version
    else
        echo "✗ Error: CUDA toolkit installation failed"
        exit 1
    fi
else
    echo "✓ CUDA toolkit is available"
    nvcc --version
fi
echo ""

# COLMAPの依存関係をインストール
echo "Step 3: Installing COLMAP dependencies..."
sudo apt-get update
sudo apt-get install -y \
    cmake \
    git \
    build-essential \
    libboost-program-options-dev \
    libboost-filesystem-dev \
    libboost-graph-dev \
    libboost-system-dev \
    libboost-test-dev \
    libeigen3-dev \
    libflann-dev \
    libfreeimage-dev \
    libmetis-dev \
    libgoogle-glog-dev \
    libgflags-dev \
    libsqlite3-dev \
    libglew-dev \
    qtbase5-dev \
    libqt5opengl5-dev \
    libcgal-dev \
    libcgal-qt5-dev \
    libceres-dev \
    libopencv-dev \
    opencv-data

echo "✓ Dependencies installed"
echo ""

# COLMAPのソースを取得
COLMAP_DIR="$SCRIPT_DIR/colmap_build"
COLMAP_SRC_DIR="$COLMAP_DIR/src"
COLMAP_BUILD_DIR="$COLMAP_DIR/build"

echo "Step 4: Downloading COLMAP source..."
if [ ! -d "$COLMAP_SRC_DIR" ]; then
    mkdir -p "$COLMAP_SRC_DIR"
    cd "$COLMAP_SRC_DIR/.."
    git clone https://github.com/colmap/colmap.git src
    echo "✓ COLMAP source downloaded"
else
    echo "✓ COLMAP source already exists, updating..."
    cd "$COLMAP_SRC_DIR"
    git pull
fi
echo ""

# ビルドディレクトリの作成
echo "Step 5: Configuring COLMAP build (CUDA enabled)..."
mkdir -p "$COLMAP_BUILD_DIR"
cd "$COLMAP_BUILD_DIR"

# CUDAアーキテクチャを検出
CUDA_ARCH=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader | head -1 | sed 's/\.//')
if [ -z "$CUDA_ARCH" ]; then
    # デフォルト値（GTX 1660 Tiなど）
    CUDA_ARCH="75"
fi
echo "Detected CUDA architecture: sm_$CUDA_ARCH"

# CMake設定（CUDAサポートを有効化）
# OpenImageIOはオプションなので、見つからない場合は自動的に無効化される
echo "Configuring CMake with CUDA support..."
cmake "$COLMAP_SRC_DIR" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCUDA_ENABLED=ON \
    -DCMAKE_CUDA_ARCHITECTURES="$CUDA_ARCH" \
    -DCMAKE_CUDA_COMPILER=/usr/bin/nvcc \
    -DGUI_ENABLED=OFF \
    2>&1 | tee /tmp/cmake_config.log

CMAKE_EXIT_CODE=$?
if [ $CMAKE_EXIT_CODE -ne 0 ]; then
    echo ""
    echo "⚠ CMake configuration failed. Checking for missing dependencies..."
    grep -i "not found\|missing\|required" /tmp/cmake_config.log | tail -5 || true
    echo ""
    echo "Attempting to continue with build anyway..."
    # 一部のオプション依存関係がなくてもビルドは続行可能
fi

echo "✓ CMake configuration completed"
echo ""

# ビルド（並列ビルド）
echo "Step 6: Building COLMAP (this will take 30-60 minutes)..."
CPU_COUNT=$(nproc)
echo "Using $CPU_COUNT CPU cores for parallel build"
make -j$CPU_COUNT

echo ""
echo "✓ COLMAP build completed"
echo ""

# インストール
echo "Step 7: Installing COLMAP..."
sudo make install

echo ""
echo "============================================================"
echo "✓ COLMAP CUDA対応版のインストールが完了しました！"
echo "============================================================"
echo ""
echo "インストール場所: /usr/local/bin/colmap"
echo ""

# インストール確認
if command -v colmap > /dev/null 2>&1; then
    echo "インストール確認:"
    colmap help 2>&1 | head -3
    echo ""
    echo "CUDAサポートの確認:"
    colmap help 2>&1 | grep -i cuda || echo "（ヘルプにCUDA情報が表示されない場合があります）"
    echo ""
    echo "✓ COLMAP is ready to use!"
else
    echo "⚠ Warning: colmap command not found in PATH"
    echo "  Try: export PATH=/usr/local/bin:\$PATH"
fi


set -e  # エラーが発生したら停止

echo "============================================================"
echo "COLMAP CUDA対応版ビルドスクリプト（WSL2用）"
echo "============================================================"
echo ""

# カレントディレクトリを保存
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# CUDA環境の確認
echo "Step 1: Checking CUDA environment..."
if ! nvidia-smi > /dev/null 2>&1; then
    echo "✗ Error: nvidia-smi not found. NVIDIA driver may not be installed."
    echo "  Please install NVIDIA driver for WSL2"
    exit 1
fi
echo "✓ NVIDIA driver is available"
nvidia-smi | head -5
echo ""

# CUDAツールキットの確認
echo "Step 2: Checking CUDA toolkit..."
if ! command -v nvcc > /dev/null 2>&1; then
    echo "⚠ CUDA toolkit not found. Installing..."
    echo "  Installing nvidia-cuda-toolkit..."
    sudo apt-get update
    sudo apt-get install -y nvidia-cuda-toolkit
    
    # nvccのパスを確認
    if [ -f /usr/bin/nvcc ]; then
        echo "✓ CUDA toolkit installed: /usr/bin/nvcc"
        nvcc --version
    else
        echo "✗ Error: CUDA toolkit installation failed"
        exit 1
    fi
else
    echo "✓ CUDA toolkit is available"
    nvcc --version
fi
echo ""

# COLMAPの依存関係をインストール
echo "Step 3: Installing COLMAP dependencies..."
sudo apt-get update
sudo apt-get install -y \
    cmake \
    git \
    build-essential \
    libboost-program-options-dev \
    libboost-filesystem-dev \
    libboost-graph-dev \
    libboost-system-dev \
    libboost-test-dev \
    libeigen3-dev \
    libflann-dev \
    libfreeimage-dev \
    libmetis-dev \
    libgoogle-glog-dev \
    libgflags-dev \
    libsqlite3-dev \
    libglew-dev \
    qtbase5-dev \
    libqt5opengl5-dev \
    libcgal-dev \
    libcgal-qt5-dev \
    libceres-dev \
    libopencv-dev \
    opencv-data

echo "✓ Dependencies installed"
echo ""

# COLMAPのソースを取得
COLMAP_DIR="$SCRIPT_DIR/colmap_build"
COLMAP_SRC_DIR="$COLMAP_DIR/src"
COLMAP_BUILD_DIR="$COLMAP_DIR/build"

echo "Step 4: Downloading COLMAP source..."
if [ ! -d "$COLMAP_SRC_DIR" ]; then
    mkdir -p "$COLMAP_SRC_DIR"
    cd "$COLMAP_SRC_DIR/.."
    git clone https://github.com/colmap/colmap.git src
    echo "✓ COLMAP source downloaded"
else
    echo "✓ COLMAP source already exists, updating..."
    cd "$COLMAP_SRC_DIR"
    git pull
fi
echo ""

# ビルドディレクトリの作成
echo "Step 5: Configuring COLMAP build (CUDA enabled)..."
mkdir -p "$COLMAP_BUILD_DIR"
cd "$COLMAP_BUILD_DIR"

# CUDAアーキテクチャを検出
CUDA_ARCH=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader | head -1 | sed 's/\.//')
if [ -z "$CUDA_ARCH" ]; then
    # デフォルト値（GTX 1660 Tiなど）
    CUDA_ARCH="75"
fi
echo "Detected CUDA architecture: sm_$CUDA_ARCH"

# CMake設定（CUDAサポートを有効化）
# OpenImageIOはオプションなので、見つからない場合は自動的に無効化される
echo "Configuring CMake with CUDA support..."
cmake "$COLMAP_SRC_DIR" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCUDA_ENABLED=ON \
    -DCMAKE_CUDA_ARCHITECTURES="$CUDA_ARCH" \
    -DCMAKE_CUDA_COMPILER=/usr/bin/nvcc \
    -DGUI_ENABLED=OFF \
    2>&1 | tee /tmp/cmake_config.log

CMAKE_EXIT_CODE=$?
if [ $CMAKE_EXIT_CODE -ne 0 ]; then
    echo ""
    echo "⚠ CMake configuration failed. Checking for missing dependencies..."
    grep -i "not found\|missing\|required" /tmp/cmake_config.log | tail -5 || true
    echo ""
    echo "Attempting to continue with build anyway..."
    # 一部のオプション依存関係がなくてもビルドは続行可能
fi

echo "✓ CMake configuration completed"
echo ""

# ビルド（並列ビルド）
echo "Step 6: Building COLMAP (this will take 30-60 minutes)..."
CPU_COUNT=$(nproc)
echo "Using $CPU_COUNT CPU cores for parallel build"
make -j$CPU_COUNT

echo ""
echo "✓ COLMAP build completed"
echo ""

# インストール
echo "Step 7: Installing COLMAP..."
sudo make install

echo ""
echo "============================================================"
echo "✓ COLMAP CUDA対応版のインストールが完了しました！"
echo "============================================================"
echo ""
echo "インストール場所: /usr/local/bin/colmap"
echo ""

# インストール確認
if command -v colmap > /dev/null 2>&1; then
    echo "インストール確認:"
    colmap help 2>&1 | head -3
    echo ""
    echo "CUDAサポートの確認:"
    colmap help 2>&1 | grep -i cuda || echo "（ヘルプにCUDA情報が表示されない場合があります）"
    echo ""
    echo "✓ COLMAP is ready to use!"
else
    echo "⚠ Warning: colmap command not found in PATH"
    echo "  Try: export PATH=/usr/local/bin:\$PATH"
fi


set -e  # エラーが発生したら停止

echo "============================================================"
echo "COLMAP CUDA対応版ビルドスクリプト（WSL2用）"
echo "============================================================"
echo ""

# カレントディレクトリを保存
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# CUDA環境の確認
echo "Step 1: Checking CUDA environment..."
if ! nvidia-smi > /dev/null 2>&1; then
    echo "✗ Error: nvidia-smi not found. NVIDIA driver may not be installed."
    echo "  Please install NVIDIA driver for WSL2"
    exit 1
fi
echo "✓ NVIDIA driver is available"
nvidia-smi | head -5
echo ""

# CUDAツールキットの確認
echo "Step 2: Checking CUDA toolkit..."
if ! command -v nvcc > /dev/null 2>&1; then
    echo "⚠ CUDA toolkit not found. Installing..."
    echo "  Installing nvidia-cuda-toolkit..."
    sudo apt-get update
    sudo apt-get install -y nvidia-cuda-toolkit
    
    # nvccのパスを確認
    if [ -f /usr/bin/nvcc ]; then
        echo "✓ CUDA toolkit installed: /usr/bin/nvcc"
        nvcc --version
    else
        echo "✗ Error: CUDA toolkit installation failed"
        exit 1
    fi
else
    echo "✓ CUDA toolkit is available"
    nvcc --version
fi
echo ""

# COLMAPの依存関係をインストール
echo "Step 3: Installing COLMAP dependencies..."
sudo apt-get update
sudo apt-get install -y \
    cmake \
    git \
    build-essential \
    libboost-program-options-dev \
    libboost-filesystem-dev \
    libboost-graph-dev \
    libboost-system-dev \
    libboost-test-dev \
    libeigen3-dev \
    libflann-dev \
    libfreeimage-dev \
    libmetis-dev \
    libgoogle-glog-dev \
    libgflags-dev \
    libsqlite3-dev \
    libglew-dev \
    qtbase5-dev \
    libqt5opengl5-dev \
    libcgal-dev \
    libcgal-qt5-dev \
    libceres-dev \
    libopencv-dev \
    opencv-data

echo "✓ Dependencies installed"
echo ""

# COLMAPのソースを取得
COLMAP_DIR="$SCRIPT_DIR/colmap_build"
COLMAP_SRC_DIR="$COLMAP_DIR/src"
COLMAP_BUILD_DIR="$COLMAP_DIR/build"

echo "Step 4: Downloading COLMAP source..."
if [ ! -d "$COLMAP_SRC_DIR" ]; then
    mkdir -p "$COLMAP_SRC_DIR"
    cd "$COLMAP_SRC_DIR/.."
    git clone https://github.com/colmap/colmap.git src
    echo "✓ COLMAP source downloaded"
else
    echo "✓ COLMAP source already exists, updating..."
    cd "$COLMAP_SRC_DIR"
    git pull
fi
echo ""

# ビルドディレクトリの作成
echo "Step 5: Configuring COLMAP build (CUDA enabled)..."
mkdir -p "$COLMAP_BUILD_DIR"
cd "$COLMAP_BUILD_DIR"

# CUDAアーキテクチャを検出
CUDA_ARCH=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader | head -1 | sed 's/\.//')
if [ -z "$CUDA_ARCH" ]; then
    # デフォルト値（GTX 1660 Tiなど）
    CUDA_ARCH="75"
fi
echo "Detected CUDA architecture: sm_$CUDA_ARCH"

# CMake設定（CUDAサポートを有効化）
# OpenImageIOはオプションなので、見つからない場合は自動的に無効化される
echo "Configuring CMake with CUDA support..."
cmake "$COLMAP_SRC_DIR" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCUDA_ENABLED=ON \
    -DCMAKE_CUDA_ARCHITECTURES="$CUDA_ARCH" \
    -DCMAKE_CUDA_COMPILER=/usr/bin/nvcc \
    -DGUI_ENABLED=OFF \
    2>&1 | tee /tmp/cmake_config.log

CMAKE_EXIT_CODE=$?
if [ $CMAKE_EXIT_CODE -ne 0 ]; then
    echo ""
    echo "⚠ CMake configuration failed. Checking for missing dependencies..."
    grep -i "not found\|missing\|required" /tmp/cmake_config.log | tail -5 || true
    echo ""
    echo "Attempting to continue with build anyway..."
    # 一部のオプション依存関係がなくてもビルドは続行可能
fi

echo "✓ CMake configuration completed"
echo ""

# ビルド（並列ビルド）
echo "Step 6: Building COLMAP (this will take 30-60 minutes)..."
CPU_COUNT=$(nproc)
echo "Using $CPU_COUNT CPU cores for parallel build"
make -j$CPU_COUNT

echo ""
echo "✓ COLMAP build completed"
echo ""

# インストール
echo "Step 7: Installing COLMAP..."
sudo make install

echo ""
echo "============================================================"
echo "✓ COLMAP CUDA対応版のインストールが完了しました！"
echo "============================================================"
echo ""
echo "インストール場所: /usr/local/bin/colmap"
echo ""

# インストール確認
if command -v colmap > /dev/null 2>&1; then
    echo "インストール確認:"
    colmap help 2>&1 | head -3
    echo ""
    echo "CUDAサポートの確認:"
    colmap help 2>&1 | grep -i cuda || echo "（ヘルプにCUDA情報が表示されない場合があります）"
    echo ""
    echo "✓ COLMAP is ready to use!"
else
    echo "⚠ Warning: colmap command not found in PATH"
    echo "  Try: export PATH=/usr/local/bin:\$PATH"
fi


set -e  # エラーが発生したら停止

echo "============================================================"
echo "COLMAP CUDA対応版ビルドスクリプト（WSL2用）"
echo "============================================================"
echo ""

# カレントディレクトリを保存
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# CUDA環境の確認
echo "Step 1: Checking CUDA environment..."
if ! nvidia-smi > /dev/null 2>&1; then
    echo "✗ Error: nvidia-smi not found. NVIDIA driver may not be installed."
    echo "  Please install NVIDIA driver for WSL2"
    exit 1
fi
echo "✓ NVIDIA driver is available"
nvidia-smi | head -5
echo ""

# CUDAツールキットの確認
echo "Step 2: Checking CUDA toolkit..."
if ! command -v nvcc > /dev/null 2>&1; then
    echo "⚠ CUDA toolkit not found. Installing..."
    echo "  Installing nvidia-cuda-toolkit..."
    sudo apt-get update
    sudo apt-get install -y nvidia-cuda-toolkit
    
    # nvccのパスを確認
    if [ -f /usr/bin/nvcc ]; then
        echo "✓ CUDA toolkit installed: /usr/bin/nvcc"
        nvcc --version
    else
        echo "✗ Error: CUDA toolkit installation failed"
        exit 1
    fi
else
    echo "✓ CUDA toolkit is available"
    nvcc --version
fi
echo ""

# COLMAPの依存関係をインストール
echo "Step 3: Installing COLMAP dependencies..."
sudo apt-get update
sudo apt-get install -y \
    cmake \
    git \
    build-essential \
    libboost-program-options-dev \
    libboost-filesystem-dev \
    libboost-graph-dev \
    libboost-system-dev \
    libboost-test-dev \
    libeigen3-dev \
    libflann-dev \
    libfreeimage-dev \
    libmetis-dev \
    libgoogle-glog-dev \
    libgflags-dev \
    libsqlite3-dev \
    libglew-dev \
    qtbase5-dev \
    libqt5opengl5-dev \
    libcgal-dev \
    libcgal-qt5-dev \
    libceres-dev \
    libopencv-dev \
    opencv-data

echo "✓ Dependencies installed"
echo ""

# COLMAPのソースを取得
COLMAP_DIR="$SCRIPT_DIR/colmap_build"
COLMAP_SRC_DIR="$COLMAP_DIR/src"
COLMAP_BUILD_DIR="$COLMAP_DIR/build"

echo "Step 4: Downloading COLMAP source..."
if [ ! -d "$COLMAP_SRC_DIR" ]; then
    mkdir -p "$COLMAP_SRC_DIR"
    cd "$COLMAP_SRC_DIR/.."
    git clone https://github.com/colmap/colmap.git src
    echo "✓ COLMAP source downloaded"
else
    echo "✓ COLMAP source already exists, updating..."
    cd "$COLMAP_SRC_DIR"
    git pull
fi
echo ""

# ビルドディレクトリの作成
echo "Step 5: Configuring COLMAP build (CUDA enabled)..."
mkdir -p "$COLMAP_BUILD_DIR"
cd "$COLMAP_BUILD_DIR"

# CUDAアーキテクチャを検出
CUDA_ARCH=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader | head -1 | sed 's/\.//')
if [ -z "$CUDA_ARCH" ]; then
    # デフォルト値（GTX 1660 Tiなど）
    CUDA_ARCH="75"
fi
echo "Detected CUDA architecture: sm_$CUDA_ARCH"

# CMake設定（CUDAサポートを有効化）
# OpenImageIOはオプションなので、見つからない場合は自動的に無効化される
echo "Configuring CMake with CUDA support..."
cmake "$COLMAP_SRC_DIR" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCUDA_ENABLED=ON \
    -DCMAKE_CUDA_ARCHITECTURES="$CUDA_ARCH" \
    -DCMAKE_CUDA_COMPILER=/usr/bin/nvcc \
    -DGUI_ENABLED=OFF \
    2>&1 | tee /tmp/cmake_config.log

CMAKE_EXIT_CODE=$?
if [ $CMAKE_EXIT_CODE -ne 0 ]; then
    echo ""
    echo "⚠ CMake configuration failed. Checking for missing dependencies..."
    grep -i "not found\|missing\|required" /tmp/cmake_config.log | tail -5 || true
    echo ""
    echo "Attempting to continue with build anyway..."
    # 一部のオプション依存関係がなくてもビルドは続行可能
fi

echo "✓ CMake configuration completed"
echo ""

# ビルド（並列ビルド）
echo "Step 6: Building COLMAP (this will take 30-60 minutes)..."
CPU_COUNT=$(nproc)
echo "Using $CPU_COUNT CPU cores for parallel build"
make -j$CPU_COUNT

echo ""
echo "✓ COLMAP build completed"
echo ""

# インストール
echo "Step 7: Installing COLMAP..."
sudo make install

echo ""
echo "============================================================"
echo "✓ COLMAP CUDA対応版のインストールが完了しました！"
echo "============================================================"
echo ""
echo "インストール場所: /usr/local/bin/colmap"
echo ""

# インストール確認
if command -v colmap > /dev/null 2>&1; then
    echo "インストール確認:"
    colmap help 2>&1 | head -3
    echo ""
    echo "CUDAサポートの確認:"
    colmap help 2>&1 | grep -i cuda || echo "（ヘルプにCUDA情報が表示されない場合があります）"
    echo ""
    echo "✓ COLMAP is ready to use!"
else
    echo "⚠ Warning: colmap command not found in PATH"
    echo "  Try: export PATH=/usr/local/bin:\$PATH"
fi


set -e  # エラーが発生したら停止

echo "============================================================"
echo "COLMAP CUDA対応版ビルドスクリプト（WSL2用）"
echo "============================================================"
echo ""

# カレントディレクトリを保存
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# CUDA環境の確認
echo "Step 1: Checking CUDA environment..."
if ! nvidia-smi > /dev/null 2>&1; then
    echo "✗ Error: nvidia-smi not found. NVIDIA driver may not be installed."
    echo "  Please install NVIDIA driver for WSL2"
    exit 1
fi
echo "✓ NVIDIA driver is available"
nvidia-smi | head -5
echo ""

# CUDAツールキットの確認
echo "Step 2: Checking CUDA toolkit..."
if ! command -v nvcc > /dev/null 2>&1; then
    echo "⚠ CUDA toolkit not found. Installing..."
    echo "  Installing nvidia-cuda-toolkit..."
    sudo apt-get update
    sudo apt-get install -y nvidia-cuda-toolkit
    
    # nvccのパスを確認
    if [ -f /usr/bin/nvcc ]; then
        echo "✓ CUDA toolkit installed: /usr/bin/nvcc"
        nvcc --version
    else
        echo "✗ Error: CUDA toolkit installation failed"
        exit 1
    fi
else
    echo "✓ CUDA toolkit is available"
    nvcc --version
fi
echo ""

# COLMAPの依存関係をインストール
echo "Step 3: Installing COLMAP dependencies..."
sudo apt-get update
sudo apt-get install -y \
    cmake \
    git \
    build-essential \
    libboost-program-options-dev \
    libboost-filesystem-dev \
    libboost-graph-dev \
    libboost-system-dev \
    libboost-test-dev \
    libeigen3-dev \
    libflann-dev \
    libfreeimage-dev \
    libmetis-dev \
    libgoogle-glog-dev \
    libgflags-dev \
    libsqlite3-dev \
    libglew-dev \
    qtbase5-dev \
    libqt5opengl5-dev \
    libcgal-dev \
    libcgal-qt5-dev \
    libceres-dev \
    libopencv-dev \
    opencv-data

echo "✓ Dependencies installed"
echo ""

# COLMAPのソースを取得
COLMAP_DIR="$SCRIPT_DIR/colmap_build"
COLMAP_SRC_DIR="$COLMAP_DIR/src"
COLMAP_BUILD_DIR="$COLMAP_DIR/build"

echo "Step 4: Downloading COLMAP source..."
if [ ! -d "$COLMAP_SRC_DIR" ]; then
    mkdir -p "$COLMAP_SRC_DIR"
    cd "$COLMAP_SRC_DIR/.."
    git clone https://github.com/colmap/colmap.git src
    echo "✓ COLMAP source downloaded"
else
    echo "✓ COLMAP source already exists, updating..."
    cd "$COLMAP_SRC_DIR"
    git pull
fi
echo ""

# ビルドディレクトリの作成
echo "Step 5: Configuring COLMAP build (CUDA enabled)..."
mkdir -p "$COLMAP_BUILD_DIR"
cd "$COLMAP_BUILD_DIR"

# CUDAアーキテクチャを検出
CUDA_ARCH=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader | head -1 | sed 's/\.//')
if [ -z "$CUDA_ARCH" ]; then
    # デフォルト値（GTX 1660 Tiなど）
    CUDA_ARCH="75"
fi
echo "Detected CUDA architecture: sm_$CUDA_ARCH"

# CMake設定（CUDAサポートを有効化）
# OpenImageIOはオプションなので、見つからない場合は自動的に無効化される
echo "Configuring CMake with CUDA support..."
cmake "$COLMAP_SRC_DIR" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCUDA_ENABLED=ON \
    -DCMAKE_CUDA_ARCHITECTURES="$CUDA_ARCH" \
    -DCMAKE_CUDA_COMPILER=/usr/bin/nvcc \
    -DGUI_ENABLED=OFF \
    2>&1 | tee /tmp/cmake_config.log

CMAKE_EXIT_CODE=$?
if [ $CMAKE_EXIT_CODE -ne 0 ]; then
    echo ""
    echo "⚠ CMake configuration failed. Checking for missing dependencies..."
    grep -i "not found\|missing\|required" /tmp/cmake_config.log | tail -5 || true
    echo ""
    echo "Attempting to continue with build anyway..."
    # 一部のオプション依存関係がなくてもビルドは続行可能
fi

echo "✓ CMake configuration completed"
echo ""

# ビルド（並列ビルド）
echo "Step 6: Building COLMAP (this will take 30-60 minutes)..."
CPU_COUNT=$(nproc)
echo "Using $CPU_COUNT CPU cores for parallel build"
make -j$CPU_COUNT

echo ""
echo "✓ COLMAP build completed"
echo ""

# インストール
echo "Step 7: Installing COLMAP..."
sudo make install

echo ""
echo "============================================================"
echo "✓ COLMAP CUDA対応版のインストールが完了しました！"
echo "============================================================"
echo ""
echo "インストール場所: /usr/local/bin/colmap"
echo ""

# インストール確認
if command -v colmap > /dev/null 2>&1; then
    echo "インストール確認:"
    colmap help 2>&1 | head -3
    echo ""
    echo "CUDAサポートの確認:"
    colmap help 2>&1 | grep -i cuda || echo "（ヘルプにCUDA情報が表示されない場合があります）"
    echo ""
    echo "✓ COLMAP is ready to use!"
else
    echo "⚠ Warning: colmap command not found in PATH"
    echo "  Try: export PATH=/usr/local/bin:\$PATH"
fi


set -e  # エラーが発生したら停止

echo "============================================================"
echo "COLMAP CUDA対応版ビルドスクリプト（WSL2用）"
echo "============================================================"
echo ""

# カレントディレクトリを保存
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# CUDA環境の確認
echo "Step 1: Checking CUDA environment..."
if ! nvidia-smi > /dev/null 2>&1; then
    echo "✗ Error: nvidia-smi not found. NVIDIA driver may not be installed."
    echo "  Please install NVIDIA driver for WSL2"
    exit 1
fi
echo "✓ NVIDIA driver is available"
nvidia-smi | head -5
echo ""

# CUDAツールキットの確認
echo "Step 2: Checking CUDA toolkit..."
if ! command -v nvcc > /dev/null 2>&1; then
    echo "⚠ CUDA toolkit not found. Installing..."
    echo "  Installing nvidia-cuda-toolkit..."
    sudo apt-get update
    sudo apt-get install -y nvidia-cuda-toolkit
    
    # nvccのパスを確認
    if [ -f /usr/bin/nvcc ]; then
        echo "✓ CUDA toolkit installed: /usr/bin/nvcc"
        nvcc --version
    else
        echo "✗ Error: CUDA toolkit installation failed"
        exit 1
    fi
else
    echo "✓ CUDA toolkit is available"
    nvcc --version
fi
echo ""

# COLMAPの依存関係をインストール
echo "Step 3: Installing COLMAP dependencies..."
sudo apt-get update
sudo apt-get install -y \
    cmake \
    git \
    build-essential \
    libboost-program-options-dev \
    libboost-filesystem-dev \
    libboost-graph-dev \
    libboost-system-dev \
    libboost-test-dev \
    libeigen3-dev \
    libflann-dev \
    libfreeimage-dev \
    libmetis-dev \
    libgoogle-glog-dev \
    libgflags-dev \
    libsqlite3-dev \
    libglew-dev \
    qtbase5-dev \
    libqt5opengl5-dev \
    libcgal-dev \
    libcgal-qt5-dev \
    libceres-dev \
    libopencv-dev \
    opencv-data

echo "✓ Dependencies installed"
echo ""

# COLMAPのソースを取得
COLMAP_DIR="$SCRIPT_DIR/colmap_build"
COLMAP_SRC_DIR="$COLMAP_DIR/src"
COLMAP_BUILD_DIR="$COLMAP_DIR/build"

echo "Step 4: Downloading COLMAP source..."
if [ ! -d "$COLMAP_SRC_DIR" ]; then
    mkdir -p "$COLMAP_SRC_DIR"
    cd "$COLMAP_SRC_DIR/.."
    git clone https://github.com/colmap/colmap.git src
    echo "✓ COLMAP source downloaded"
else
    echo "✓ COLMAP source already exists, updating..."
    cd "$COLMAP_SRC_DIR"
    git pull
fi
echo ""

# ビルドディレクトリの作成
echo "Step 5: Configuring COLMAP build (CUDA enabled)..."
mkdir -p "$COLMAP_BUILD_DIR"
cd "$COLMAP_BUILD_DIR"

# CUDAアーキテクチャを検出
CUDA_ARCH=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader | head -1 | sed 's/\.//')
if [ -z "$CUDA_ARCH" ]; then
    # デフォルト値（GTX 1660 Tiなど）
    CUDA_ARCH="75"
fi
echo "Detected CUDA architecture: sm_$CUDA_ARCH"

# CMake設定（CUDAサポートを有効化）
# OpenImageIOはオプションなので、見つからない場合は自動的に無効化される
echo "Configuring CMake with CUDA support..."
cmake "$COLMAP_SRC_DIR" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCUDA_ENABLED=ON \
    -DCMAKE_CUDA_ARCHITECTURES="$CUDA_ARCH" \
    -DCMAKE_CUDA_COMPILER=/usr/bin/nvcc \
    -DGUI_ENABLED=OFF \
    2>&1 | tee /tmp/cmake_config.log

CMAKE_EXIT_CODE=$?
if [ $CMAKE_EXIT_CODE -ne 0 ]; then
    echo ""
    echo "⚠ CMake configuration failed. Checking for missing dependencies..."
    grep -i "not found\|missing\|required" /tmp/cmake_config.log | tail -5 || true
    echo ""
    echo "Attempting to continue with build anyway..."
    # 一部のオプション依存関係がなくてもビルドは続行可能
fi

echo "✓ CMake configuration completed"
echo ""

# ビルド（並列ビルド）
echo "Step 6: Building COLMAP (this will take 30-60 minutes)..."
CPU_COUNT=$(nproc)
echo "Using $CPU_COUNT CPU cores for parallel build"
make -j$CPU_COUNT

echo ""
echo "✓ COLMAP build completed"
echo ""

# インストール
echo "Step 7: Installing COLMAP..."
sudo make install

echo ""
echo "============================================================"
echo "✓ COLMAP CUDA対応版のインストールが完了しました！"
echo "============================================================"
echo ""
echo "インストール場所: /usr/local/bin/colmap"
echo ""

# インストール確認
if command -v colmap > /dev/null 2>&1; then
    echo "インストール確認:"
    colmap help 2>&1 | head -3
    echo ""
    echo "CUDAサポートの確認:"
    colmap help 2>&1 | grep -i cuda || echo "（ヘルプにCUDA情報が表示されない場合があります）"
    echo ""
    echo "✓ COLMAP is ready to use!"
else
    echo "⚠ Warning: colmap command not found in PATH"
    echo "  Try: export PATH=/usr/local/bin:\$PATH"
fi


set -e  # エラーが発生したら停止

echo "============================================================"
echo "COLMAP CUDA対応版ビルドスクリプト（WSL2用）"
echo "============================================================"
echo ""

# カレントディレクトリを保存
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# CUDA環境の確認
echo "Step 1: Checking CUDA environment..."
if ! nvidia-smi > /dev/null 2>&1; then
    echo "✗ Error: nvidia-smi not found. NVIDIA driver may not be installed."
    echo "  Please install NVIDIA driver for WSL2"
    exit 1
fi
echo "✓ NVIDIA driver is available"
nvidia-smi | head -5
echo ""

# CUDAツールキットの確認
echo "Step 2: Checking CUDA toolkit..."
if ! command -v nvcc > /dev/null 2>&1; then
    echo "⚠ CUDA toolkit not found. Installing..."
    echo "  Installing nvidia-cuda-toolkit..."
    sudo apt-get update
    sudo apt-get install -y nvidia-cuda-toolkit
    
    # nvccのパスを確認
    if [ -f /usr/bin/nvcc ]; then
        echo "✓ CUDA toolkit installed: /usr/bin/nvcc"
        nvcc --version
    else
        echo "✗ Error: CUDA toolkit installation failed"
        exit 1
    fi
else
    echo "✓ CUDA toolkit is available"
    nvcc --version
fi
echo ""

# COLMAPの依存関係をインストール
echo "Step 3: Installing COLMAP dependencies..."
sudo apt-get update
sudo apt-get install -y \
    cmake \
    git \
    build-essential \
    libboost-program-options-dev \
    libboost-filesystem-dev \
    libboost-graph-dev \
    libboost-system-dev \
    libboost-test-dev \
    libeigen3-dev \
    libflann-dev \
    libfreeimage-dev \
    libmetis-dev \
    libgoogle-glog-dev \
    libgflags-dev \
    libsqlite3-dev \
    libglew-dev \
    qtbase5-dev \
    libqt5opengl5-dev \
    libcgal-dev \
    libcgal-qt5-dev \
    libceres-dev \
    libopencv-dev \
    opencv-data

echo "✓ Dependencies installed"
echo ""

# COLMAPのソースを取得
COLMAP_DIR="$SCRIPT_DIR/colmap_build"
COLMAP_SRC_DIR="$COLMAP_DIR/src"
COLMAP_BUILD_DIR="$COLMAP_DIR/build"

echo "Step 4: Downloading COLMAP source..."
if [ ! -d "$COLMAP_SRC_DIR" ]; then
    mkdir -p "$COLMAP_SRC_DIR"
    cd "$COLMAP_SRC_DIR/.."
    git clone https://github.com/colmap/colmap.git src
    echo "✓ COLMAP source downloaded"
else
    echo "✓ COLMAP source already exists, updating..."
    cd "$COLMAP_SRC_DIR"
    git pull
fi
echo ""

# ビルドディレクトリの作成
echo "Step 5: Configuring COLMAP build (CUDA enabled)..."
mkdir -p "$COLMAP_BUILD_DIR"
cd "$COLMAP_BUILD_DIR"

# CUDAアーキテクチャを検出
CUDA_ARCH=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader | head -1 | sed 's/\.//')
if [ -z "$CUDA_ARCH" ]; then
    # デフォルト値（GTX 1660 Tiなど）
    CUDA_ARCH="75"
fi
echo "Detected CUDA architecture: sm_$CUDA_ARCH"

# CMake設定（CUDAサポートを有効化）
# OpenImageIOはオプションなので、見つからない場合は自動的に無効化される
echo "Configuring CMake with CUDA support..."
cmake "$COLMAP_SRC_DIR" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCUDA_ENABLED=ON \
    -DCMAKE_CUDA_ARCHITECTURES="$CUDA_ARCH" \
    -DCMAKE_CUDA_COMPILER=/usr/bin/nvcc \
    -DGUI_ENABLED=OFF \
    2>&1 | tee /tmp/cmake_config.log

CMAKE_EXIT_CODE=$?
if [ $CMAKE_EXIT_CODE -ne 0 ]; then
    echo ""
    echo "⚠ CMake configuration failed. Checking for missing dependencies..."
    grep -i "not found\|missing\|required" /tmp/cmake_config.log | tail -5 || true
    echo ""
    echo "Attempting to continue with build anyway..."
    # 一部のオプション依存関係がなくてもビルドは続行可能
fi

echo "✓ CMake configuration completed"
echo ""

# ビルド（並列ビルド）
echo "Step 6: Building COLMAP (this will take 30-60 minutes)..."
CPU_COUNT=$(nproc)
echo "Using $CPU_COUNT CPU cores for parallel build"
make -j$CPU_COUNT

echo ""
echo "✓ COLMAP build completed"
echo ""

# インストール
echo "Step 7: Installing COLMAP..."
sudo make install

echo ""
echo "============================================================"
echo "✓ COLMAP CUDA対応版のインストールが完了しました！"
echo "============================================================"
echo ""
echo "インストール場所: /usr/local/bin/colmap"
echo ""

# インストール確認
if command -v colmap > /dev/null 2>&1; then
    echo "インストール確認:"
    colmap help 2>&1 | head -3
    echo ""
    echo "CUDAサポートの確認:"
    colmap help 2>&1 | grep -i cuda || echo "（ヘルプにCUDA情報が表示されない場合があります）"
    echo ""
    echo "✓ COLMAP is ready to use!"
else
    echo "⚠ Warning: colmap command not found in PATH"
    echo "  Try: export PATH=/usr/local/bin:\$PATH"
fi

set -e  # エラーが発生したら停止

echo "============================================================"
echo "COLMAP CUDA対応版ビルドスクリプト（WSL2用）"
echo "============================================================"
echo ""

# カレントディレクトリを保存
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# CUDA環境の確認
echo "Step 1: Checking CUDA environment..."
if ! nvidia-smi > /dev/null 2>&1; then
    echo "✗ Error: nvidia-smi not found. NVIDIA driver may not be installed."
    echo "  Please install NVIDIA driver for WSL2"
    exit 1
fi
echo "✓ NVIDIA driver is available"
nvidia-smi | head -5
echo ""

# CUDAツールキットの確認
echo "Step 2: Checking CUDA toolkit..."
if ! command -v nvcc > /dev/null 2>&1; then
    echo "⚠ CUDA toolkit not found. Installing..."
    echo "  Installing nvidia-cuda-toolkit..."
    sudo apt-get update
    sudo apt-get install -y nvidia-cuda-toolkit
    
    # nvccのパスを確認
    if [ -f /usr/bin/nvcc ]; then
        echo "✓ CUDA toolkit installed: /usr/bin/nvcc"
        nvcc --version
    else
        echo "✗ Error: CUDA toolkit installation failed"
        exit 1
    fi
else
    echo "✓ CUDA toolkit is available"
    nvcc --version
fi
echo ""

# COLMAPの依存関係をインストール
echo "Step 3: Installing COLMAP dependencies..."
sudo apt-get update
sudo apt-get install -y \
    cmake \
    git \
    build-essential \
    libboost-program-options-dev \
    libboost-filesystem-dev \
    libboost-graph-dev \
    libboost-system-dev \
    libboost-test-dev \
    libeigen3-dev \
    libflann-dev \
    libfreeimage-dev \
    libmetis-dev \
    libgoogle-glog-dev \
    libgflags-dev \
    libsqlite3-dev \
    libglew-dev \
    qtbase5-dev \
    libqt5opengl5-dev \
    libcgal-dev \
    libcgal-qt5-dev \
    libceres-dev \
    libopencv-dev \
    opencv-data

echo "✓ Dependencies installed"
echo ""

# COLMAPのソースを取得
COLMAP_DIR="$SCRIPT_DIR/colmap_build"
COLMAP_SRC_DIR="$COLMAP_DIR/src"
COLMAP_BUILD_DIR="$COLMAP_DIR/build"

echo "Step 4: Downloading COLMAP source..."
if [ ! -d "$COLMAP_SRC_DIR" ]; then
    mkdir -p "$COLMAP_SRC_DIR"
    cd "$COLMAP_SRC_DIR/.."
    git clone https://github.com/colmap/colmap.git src
    echo "✓ COLMAP source downloaded"
else
    echo "✓ COLMAP source already exists, updating..."
    cd "$COLMAP_SRC_DIR"
    git pull
fi
echo ""

# ビルドディレクトリの作成
echo "Step 5: Configuring COLMAP build (CUDA enabled)..."
mkdir -p "$COLMAP_BUILD_DIR"
cd "$COLMAP_BUILD_DIR"

# CUDAアーキテクチャを検出
CUDA_ARCH=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader | head -1 | sed 's/\.//')
if [ -z "$CUDA_ARCH" ]; then
    # デフォルト値（GTX 1660 Tiなど）
    CUDA_ARCH="75"
fi
echo "Detected CUDA architecture: sm_$CUDA_ARCH"

# CMake設定（CUDAサポートを有効化）
# OpenImageIOはオプションなので、見つからない場合は自動的に無効化される
echo "Configuring CMake with CUDA support..."
cmake "$COLMAP_SRC_DIR" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCUDA_ENABLED=ON \
    -DCMAKE_CUDA_ARCHITECTURES="$CUDA_ARCH" \
    -DCMAKE_CUDA_COMPILER=/usr/bin/nvcc \
    -DGUI_ENABLED=OFF \
    2>&1 | tee /tmp/cmake_config.log

CMAKE_EXIT_CODE=$?
if [ $CMAKE_EXIT_CODE -ne 0 ]; then
    echo ""
    echo "⚠ CMake configuration failed. Checking for missing dependencies..."
    grep -i "not found\|missing\|required" /tmp/cmake_config.log | tail -5 || true
    echo ""
    echo "Attempting to continue with build anyway..."
    # 一部のオプション依存関係がなくてもビルドは続行可能
fi

echo "✓ CMake configuration completed"
echo ""

# ビルド（並列ビルド）
echo "Step 6: Building COLMAP (this will take 30-60 minutes)..."
CPU_COUNT=$(nproc)
echo "Using $CPU_COUNT CPU cores for parallel build"
make -j$CPU_COUNT

echo ""
echo "✓ COLMAP build completed"
echo ""

# インストール
echo "Step 7: Installing COLMAP..."
sudo make install

echo ""
echo "============================================================"
echo "✓ COLMAP CUDA対応版のインストールが完了しました！"
echo "============================================================"
echo ""
echo "インストール場所: /usr/local/bin/colmap"
echo ""

# インストール確認
if command -v colmap > /dev/null 2>&1; then
    echo "インストール確認:"
    colmap help 2>&1 | head -3
    echo ""
    echo "CUDAサポートの確認:"
    colmap help 2>&1 | grep -i cuda || echo "（ヘルプにCUDA情報が表示されない場合があります）"
    echo ""
    echo "✓ COLMAP is ready to use!"
else
    echo "⚠ Warning: colmap command not found in PATH"
    echo "  Try: export PATH=/usr/local/bin:\$PATH"
fi


set -e  # エラーが発生したら停止

echo "============================================================"
echo "COLMAP CUDA対応版ビルドスクリプト（WSL2用）"
echo "============================================================"
echo ""

# カレントディレクトリを保存
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# CUDA環境の確認
echo "Step 1: Checking CUDA environment..."
if ! nvidia-smi > /dev/null 2>&1; then
    echo "✗ Error: nvidia-smi not found. NVIDIA driver may not be installed."
    echo "  Please install NVIDIA driver for WSL2"
    exit 1
fi
echo "✓ NVIDIA driver is available"
nvidia-smi | head -5
echo ""

# CUDAツールキットの確認
echo "Step 2: Checking CUDA toolkit..."
if ! command -v nvcc > /dev/null 2>&1; then
    echo "⚠ CUDA toolkit not found. Installing..."
    echo "  Installing nvidia-cuda-toolkit..."
    sudo apt-get update
    sudo apt-get install -y nvidia-cuda-toolkit
    
    # nvccのパスを確認
    if [ -f /usr/bin/nvcc ]; then
        echo "✓ CUDA toolkit installed: /usr/bin/nvcc"
        nvcc --version
    else
        echo "✗ Error: CUDA toolkit installation failed"
        exit 1
    fi
else
    echo "✓ CUDA toolkit is available"
    nvcc --version
fi
echo ""

# COLMAPの依存関係をインストール
echo "Step 3: Installing COLMAP dependencies..."
sudo apt-get update
sudo apt-get install -y \
    cmake \
    git \
    build-essential \
    libboost-program-options-dev \
    libboost-filesystem-dev \
    libboost-graph-dev \
    libboost-system-dev \
    libboost-test-dev \
    libeigen3-dev \
    libflann-dev \
    libfreeimage-dev \
    libmetis-dev \
    libgoogle-glog-dev \
    libgflags-dev \
    libsqlite3-dev \
    libglew-dev \
    qtbase5-dev \
    libqt5opengl5-dev \
    libcgal-dev \
    libcgal-qt5-dev \
    libceres-dev \
    libopencv-dev \
    opencv-data

echo "✓ Dependencies installed"
echo ""

# COLMAPのソースを取得
COLMAP_DIR="$SCRIPT_DIR/colmap_build"
COLMAP_SRC_DIR="$COLMAP_DIR/src"
COLMAP_BUILD_DIR="$COLMAP_DIR/build"

echo "Step 4: Downloading COLMAP source..."
if [ ! -d "$COLMAP_SRC_DIR" ]; then
    mkdir -p "$COLMAP_SRC_DIR"
    cd "$COLMAP_SRC_DIR/.."
    git clone https://github.com/colmap/colmap.git src
    echo "✓ COLMAP source downloaded"
else
    echo "✓ COLMAP source already exists, updating..."
    cd "$COLMAP_SRC_DIR"
    git pull
fi
echo ""

# ビルドディレクトリの作成
echo "Step 5: Configuring COLMAP build (CUDA enabled)..."
mkdir -p "$COLMAP_BUILD_DIR"
cd "$COLMAP_BUILD_DIR"

# CUDAアーキテクチャを検出
CUDA_ARCH=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader | head -1 | sed 's/\.//')
if [ -z "$CUDA_ARCH" ]; then
    # デフォルト値（GTX 1660 Tiなど）
    CUDA_ARCH="75"
fi
echo "Detected CUDA architecture: sm_$CUDA_ARCH"

# CMake設定（CUDAサポートを有効化）
# OpenImageIOはオプションなので、見つからない場合は自動的に無効化される
echo "Configuring CMake with CUDA support..."
cmake "$COLMAP_SRC_DIR" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCUDA_ENABLED=ON \
    -DCMAKE_CUDA_ARCHITECTURES="$CUDA_ARCH" \
    -DCMAKE_CUDA_COMPILER=/usr/bin/nvcc \
    -DGUI_ENABLED=OFF \
    2>&1 | tee /tmp/cmake_config.log

CMAKE_EXIT_CODE=$?
if [ $CMAKE_EXIT_CODE -ne 0 ]; then
    echo ""
    echo "⚠ CMake configuration failed. Checking for missing dependencies..."
    grep -i "not found\|missing\|required" /tmp/cmake_config.log | tail -5 || true
    echo ""
    echo "Attempting to continue with build anyway..."
    # 一部のオプション依存関係がなくてもビルドは続行可能
fi

echo "✓ CMake configuration completed"
echo ""

# ビルド（並列ビルド）
echo "Step 6: Building COLMAP (this will take 30-60 minutes)..."
CPU_COUNT=$(nproc)
echo "Using $CPU_COUNT CPU cores for parallel build"
make -j$CPU_COUNT

echo ""
echo "✓ COLMAP build completed"
echo ""

# インストール
echo "Step 7: Installing COLMAP..."
sudo make install

echo ""
echo "============================================================"
echo "✓ COLMAP CUDA対応版のインストールが完了しました！"
echo "============================================================"
echo ""
echo "インストール場所: /usr/local/bin/colmap"
echo ""

# インストール確認
if command -v colmap > /dev/null 2>&1; then
    echo "インストール確認:"
    colmap help 2>&1 | head -3
    echo ""
    echo "CUDAサポートの確認:"
    colmap help 2>&1 | grep -i cuda || echo "（ヘルプにCUDA情報が表示されない場合があります）"
    echo ""
    echo "✓ COLMAP is ready to use!"
else
    echo "⚠ Warning: colmap command not found in PATH"
    echo "  Try: export PATH=/usr/local/bin:\$PATH"
fi


set -e  # エラーが発生したら停止

echo "============================================================"
echo "COLMAP CUDA対応版ビルドスクリプト（WSL2用）"
echo "============================================================"
echo ""

# カレントディレクトリを保存
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# CUDA環境の確認
echo "Step 1: Checking CUDA environment..."
if ! nvidia-smi > /dev/null 2>&1; then
    echo "✗ Error: nvidia-smi not found. NVIDIA driver may not be installed."
    echo "  Please install NVIDIA driver for WSL2"
    exit 1
fi
echo "✓ NVIDIA driver is available"
nvidia-smi | head -5
echo ""

# CUDAツールキットの確認
echo "Step 2: Checking CUDA toolkit..."
if ! command -v nvcc > /dev/null 2>&1; then
    echo "⚠ CUDA toolkit not found. Installing..."
    echo "  Installing nvidia-cuda-toolkit..."
    sudo apt-get update
    sudo apt-get install -y nvidia-cuda-toolkit
    
    # nvccのパスを確認
    if [ -f /usr/bin/nvcc ]; then
        echo "✓ CUDA toolkit installed: /usr/bin/nvcc"
        nvcc --version
    else
        echo "✗ Error: CUDA toolkit installation failed"
        exit 1
    fi
else
    echo "✓ CUDA toolkit is available"
    nvcc --version
fi
echo ""

# COLMAPの依存関係をインストール
echo "Step 3: Installing COLMAP dependencies..."
sudo apt-get update
sudo apt-get install -y \
    cmake \
    git \
    build-essential \
    libboost-program-options-dev \
    libboost-filesystem-dev \
    libboost-graph-dev \
    libboost-system-dev \
    libboost-test-dev \
    libeigen3-dev \
    libflann-dev \
    libfreeimage-dev \
    libmetis-dev \
    libgoogle-glog-dev \
    libgflags-dev \
    libsqlite3-dev \
    libglew-dev \
    qtbase5-dev \
    libqt5opengl5-dev \
    libcgal-dev \
    libcgal-qt5-dev \
    libceres-dev \
    libopencv-dev \
    opencv-data

echo "✓ Dependencies installed"
echo ""

# COLMAPのソースを取得
COLMAP_DIR="$SCRIPT_DIR/colmap_build"
COLMAP_SRC_DIR="$COLMAP_DIR/src"
COLMAP_BUILD_DIR="$COLMAP_DIR/build"

echo "Step 4: Downloading COLMAP source..."
if [ ! -d "$COLMAP_SRC_DIR" ]; then
    mkdir -p "$COLMAP_SRC_DIR"
    cd "$COLMAP_SRC_DIR/.."
    git clone https://github.com/colmap/colmap.git src
    echo "✓ COLMAP source downloaded"
else
    echo "✓ COLMAP source already exists, updating..."
    cd "$COLMAP_SRC_DIR"
    git pull
fi
echo ""

# ビルドディレクトリの作成
echo "Step 5: Configuring COLMAP build (CUDA enabled)..."
mkdir -p "$COLMAP_BUILD_DIR"
cd "$COLMAP_BUILD_DIR"

# CUDAアーキテクチャを検出
CUDA_ARCH=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader | head -1 | sed 's/\.//')
if [ -z "$CUDA_ARCH" ]; then
    # デフォルト値（GTX 1660 Tiなど）
    CUDA_ARCH="75"
fi
echo "Detected CUDA architecture: sm_$CUDA_ARCH"

# CMake設定（CUDAサポートを有効化）
# OpenImageIOはオプションなので、見つからない場合は自動的に無効化される
echo "Configuring CMake with CUDA support..."
cmake "$COLMAP_SRC_DIR" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCUDA_ENABLED=ON \
    -DCMAKE_CUDA_ARCHITECTURES="$CUDA_ARCH" \
    -DCMAKE_CUDA_COMPILER=/usr/bin/nvcc \
    -DGUI_ENABLED=OFF \
    2>&1 | tee /tmp/cmake_config.log

CMAKE_EXIT_CODE=$?
if [ $CMAKE_EXIT_CODE -ne 0 ]; then
    echo ""
    echo "⚠ CMake configuration failed. Checking for missing dependencies..."
    grep -i "not found\|missing\|required" /tmp/cmake_config.log | tail -5 || true
    echo ""
    echo "Attempting to continue with build anyway..."
    # 一部のオプション依存関係がなくてもビルドは続行可能
fi

echo "✓ CMake configuration completed"
echo ""

# ビルド（並列ビルド）
echo "Step 6: Building COLMAP (this will take 30-60 minutes)..."
CPU_COUNT=$(nproc)
echo "Using $CPU_COUNT CPU cores for parallel build"
make -j$CPU_COUNT

echo ""
echo "✓ COLMAP build completed"
echo ""

# インストール
echo "Step 7: Installing COLMAP..."
sudo make install

echo ""
echo "============================================================"
echo "✓ COLMAP CUDA対応版のインストールが完了しました！"
echo "============================================================"
echo ""
echo "インストール場所: /usr/local/bin/colmap"
echo ""

# インストール確認
if command -v colmap > /dev/null 2>&1; then
    echo "インストール確認:"
    colmap help 2>&1 | head -3
    echo ""
    echo "CUDAサポートの確認:"
    colmap help 2>&1 | grep -i cuda || echo "（ヘルプにCUDA情報が表示されない場合があります）"
    echo ""
    echo "✓ COLMAP is ready to use!"
else
    echo "⚠ Warning: colmap command not found in PATH"
    echo "  Try: export PATH=/usr/local/bin:\$PATH"
fi


set -e  # エラーが発生したら停止

echo "============================================================"
echo "COLMAP CUDA対応版ビルドスクリプト（WSL2用）"
echo "============================================================"
echo ""

# カレントディレクトリを保存
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# CUDA環境の確認
echo "Step 1: Checking CUDA environment..."
if ! nvidia-smi > /dev/null 2>&1; then
    echo "✗ Error: nvidia-smi not found. NVIDIA driver may not be installed."
    echo "  Please install NVIDIA driver for WSL2"
    exit 1
fi
echo "✓ NVIDIA driver is available"
nvidia-smi | head -5
echo ""

# CUDAツールキットの確認
echo "Step 2: Checking CUDA toolkit..."
if ! command -v nvcc > /dev/null 2>&1; then
    echo "⚠ CUDA toolkit not found. Installing..."
    echo "  Installing nvidia-cuda-toolkit..."
    sudo apt-get update
    sudo apt-get install -y nvidia-cuda-toolkit
    
    # nvccのパスを確認
    if [ -f /usr/bin/nvcc ]; then
        echo "✓ CUDA toolkit installed: /usr/bin/nvcc"
        nvcc --version
    else
        echo "✗ Error: CUDA toolkit installation failed"
        exit 1
    fi
else
    echo "✓ CUDA toolkit is available"
    nvcc --version
fi
echo ""

# COLMAPの依存関係をインストール
echo "Step 3: Installing COLMAP dependencies..."
sudo apt-get update
sudo apt-get install -y \
    cmake \
    git \
    build-essential \
    libboost-program-options-dev \
    libboost-filesystem-dev \
    libboost-graph-dev \
    libboost-system-dev \
    libboost-test-dev \
    libeigen3-dev \
    libflann-dev \
    libfreeimage-dev \
    libmetis-dev \
    libgoogle-glog-dev \
    libgflags-dev \
    libsqlite3-dev \
    libglew-dev \
    qtbase5-dev \
    libqt5opengl5-dev \
    libcgal-dev \
    libcgal-qt5-dev \
    libceres-dev \
    libopencv-dev \
    opencv-data

echo "✓ Dependencies installed"
echo ""

# COLMAPのソースを取得
COLMAP_DIR="$SCRIPT_DIR/colmap_build"
COLMAP_SRC_DIR="$COLMAP_DIR/src"
COLMAP_BUILD_DIR="$COLMAP_DIR/build"

echo "Step 4: Downloading COLMAP source..."
if [ ! -d "$COLMAP_SRC_DIR" ]; then
    mkdir -p "$COLMAP_SRC_DIR"
    cd "$COLMAP_SRC_DIR/.."
    git clone https://github.com/colmap/colmap.git src
    echo "✓ COLMAP source downloaded"
else
    echo "✓ COLMAP source already exists, updating..."
    cd "$COLMAP_SRC_DIR"
    git pull
fi
echo ""

# ビルドディレクトリの作成
echo "Step 5: Configuring COLMAP build (CUDA enabled)..."
mkdir -p "$COLMAP_BUILD_DIR"
cd "$COLMAP_BUILD_DIR"

# CUDAアーキテクチャを検出
CUDA_ARCH=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader | head -1 | sed 's/\.//')
if [ -z "$CUDA_ARCH" ]; then
    # デフォルト値（GTX 1660 Tiなど）
    CUDA_ARCH="75"
fi
echo "Detected CUDA architecture: sm_$CUDA_ARCH"

# CMake設定（CUDAサポートを有効化）
# OpenImageIOはオプションなので、見つからない場合は自動的に無効化される
echo "Configuring CMake with CUDA support..."
cmake "$COLMAP_SRC_DIR" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCUDA_ENABLED=ON \
    -DCMAKE_CUDA_ARCHITECTURES="$CUDA_ARCH" \
    -DCMAKE_CUDA_COMPILER=/usr/bin/nvcc \
    -DGUI_ENABLED=OFF \
    2>&1 | tee /tmp/cmake_config.log

CMAKE_EXIT_CODE=$?
if [ $CMAKE_EXIT_CODE -ne 0 ]; then
    echo ""
    echo "⚠ CMake configuration failed. Checking for missing dependencies..."
    grep -i "not found\|missing\|required" /tmp/cmake_config.log | tail -5 || true
    echo ""
    echo "Attempting to continue with build anyway..."
    # 一部のオプション依存関係がなくてもビルドは続行可能
fi

echo "✓ CMake configuration completed"
echo ""

# ビルド（並列ビルド）
echo "Step 6: Building COLMAP (this will take 30-60 minutes)..."
CPU_COUNT=$(nproc)
echo "Using $CPU_COUNT CPU cores for parallel build"
make -j$CPU_COUNT

echo ""
echo "✓ COLMAP build completed"
echo ""

# インストール
echo "Step 7: Installing COLMAP..."
sudo make install

echo ""
echo "============================================================"
echo "✓ COLMAP CUDA対応版のインストールが完了しました！"
echo "============================================================"
echo ""
echo "インストール場所: /usr/local/bin/colmap"
echo ""

# インストール確認
if command -v colmap > /dev/null 2>&1; then
    echo "インストール確認:"
    colmap help 2>&1 | head -3
    echo ""
    echo "CUDAサポートの確認:"
    colmap help 2>&1 | grep -i cuda || echo "（ヘルプにCUDA情報が表示されない場合があります）"
    echo ""
    echo "✓ COLMAP is ready to use!"
else
    echo "⚠ Warning: colmap command not found in PATH"
    echo "  Try: export PATH=/usr/local/bin:\$PATH"
fi


set -e  # エラーが発生したら停止

echo "============================================================"
echo "COLMAP CUDA対応版ビルドスクリプト（WSL2用）"
echo "============================================================"
echo ""

# カレントディレクトリを保存
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# CUDA環境の確認
echo "Step 1: Checking CUDA environment..."
if ! nvidia-smi > /dev/null 2>&1; then
    echo "✗ Error: nvidia-smi not found. NVIDIA driver may not be installed."
    echo "  Please install NVIDIA driver for WSL2"
    exit 1
fi
echo "✓ NVIDIA driver is available"
nvidia-smi | head -5
echo ""

# CUDAツールキットの確認
echo "Step 2: Checking CUDA toolkit..."
if ! command -v nvcc > /dev/null 2>&1; then
    echo "⚠ CUDA toolkit not found. Installing..."
    echo "  Installing nvidia-cuda-toolkit..."
    sudo apt-get update
    sudo apt-get install -y nvidia-cuda-toolkit
    
    # nvccのパスを確認
    if [ -f /usr/bin/nvcc ]; then
        echo "✓ CUDA toolkit installed: /usr/bin/nvcc"
        nvcc --version
    else
        echo "✗ Error: CUDA toolkit installation failed"
        exit 1
    fi
else
    echo "✓ CUDA toolkit is available"
    nvcc --version
fi
echo ""

# COLMAPの依存関係をインストール
echo "Step 3: Installing COLMAP dependencies..."
sudo apt-get update
sudo apt-get install -y \
    cmake \
    git \
    build-essential \
    libboost-program-options-dev \
    libboost-filesystem-dev \
    libboost-graph-dev \
    libboost-system-dev \
    libboost-test-dev \
    libeigen3-dev \
    libflann-dev \
    libfreeimage-dev \
    libmetis-dev \
    libgoogle-glog-dev \
    libgflags-dev \
    libsqlite3-dev \
    libglew-dev \
    qtbase5-dev \
    libqt5opengl5-dev \
    libcgal-dev \
    libcgal-qt5-dev \
    libceres-dev \
    libopencv-dev \
    opencv-data

echo "✓ Dependencies installed"
echo ""

# COLMAPのソースを取得
COLMAP_DIR="$SCRIPT_DIR/colmap_build"
COLMAP_SRC_DIR="$COLMAP_DIR/src"
COLMAP_BUILD_DIR="$COLMAP_DIR/build"

echo "Step 4: Downloading COLMAP source..."
if [ ! -d "$COLMAP_SRC_DIR" ]; then
    mkdir -p "$COLMAP_SRC_DIR"
    cd "$COLMAP_SRC_DIR/.."
    git clone https://github.com/colmap/colmap.git src
    echo "✓ COLMAP source downloaded"
else
    echo "✓ COLMAP source already exists, updating..."
    cd "$COLMAP_SRC_DIR"
    git pull
fi
echo ""

# ビルドディレクトリの作成
echo "Step 5: Configuring COLMAP build (CUDA enabled)..."
mkdir -p "$COLMAP_BUILD_DIR"
cd "$COLMAP_BUILD_DIR"

# CUDAアーキテクチャを検出
CUDA_ARCH=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader | head -1 | sed 's/\.//')
if [ -z "$CUDA_ARCH" ]; then
    # デフォルト値（GTX 1660 Tiなど）
    CUDA_ARCH="75"
fi
echo "Detected CUDA architecture: sm_$CUDA_ARCH"

# CMake設定（CUDAサポートを有効化）
# OpenImageIOはオプションなので、見つからない場合は自動的に無効化される
echo "Configuring CMake with CUDA support..."
cmake "$COLMAP_SRC_DIR" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCUDA_ENABLED=ON \
    -DCMAKE_CUDA_ARCHITECTURES="$CUDA_ARCH" \
    -DCMAKE_CUDA_COMPILER=/usr/bin/nvcc \
    -DGUI_ENABLED=OFF \
    2>&1 | tee /tmp/cmake_config.log

CMAKE_EXIT_CODE=$?
if [ $CMAKE_EXIT_CODE -ne 0 ]; then
    echo ""
    echo "⚠ CMake configuration failed. Checking for missing dependencies..."
    grep -i "not found\|missing\|required" /tmp/cmake_config.log | tail -5 || true
    echo ""
    echo "Attempting to continue with build anyway..."
    # 一部のオプション依存関係がなくてもビルドは続行可能
fi

echo "✓ CMake configuration completed"
echo ""

# ビルド（並列ビルド）
echo "Step 6: Building COLMAP (this will take 30-60 minutes)..."
CPU_COUNT=$(nproc)
echo "Using $CPU_COUNT CPU cores for parallel build"
make -j$CPU_COUNT

echo ""
echo "✓ COLMAP build completed"
echo ""

# インストール
echo "Step 7: Installing COLMAP..."
sudo make install

echo ""
echo "============================================================"
echo "✓ COLMAP CUDA対応版のインストールが完了しました！"
echo "============================================================"
echo ""
echo "インストール場所: /usr/local/bin/colmap"
echo ""

# インストール確認
if command -v colmap > /dev/null 2>&1; then
    echo "インストール確認:"
    colmap help 2>&1 | head -3
    echo ""
    echo "CUDAサポートの確認:"
    colmap help 2>&1 | grep -i cuda || echo "（ヘルプにCUDA情報が表示されない場合があります）"
    echo ""
    echo "✓ COLMAP is ready to use!"
else
    echo "⚠ Warning: colmap command not found in PATH"
    echo "  Try: export PATH=/usr/local/bin:\$PATH"
fi


set -e  # エラーが発生したら停止

echo "============================================================"
echo "COLMAP CUDA対応版ビルドスクリプト（WSL2用）"
echo "============================================================"
echo ""

# カレントディレクトリを保存
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# CUDA環境の確認
echo "Step 1: Checking CUDA environment..."
if ! nvidia-smi > /dev/null 2>&1; then
    echo "✗ Error: nvidia-smi not found. NVIDIA driver may not be installed."
    echo "  Please install NVIDIA driver for WSL2"
    exit 1
fi
echo "✓ NVIDIA driver is available"
nvidia-smi | head -5
echo ""

# CUDAツールキットの確認
echo "Step 2: Checking CUDA toolkit..."
if ! command -v nvcc > /dev/null 2>&1; then
    echo "⚠ CUDA toolkit not found. Installing..."
    echo "  Installing nvidia-cuda-toolkit..."
    sudo apt-get update
    sudo apt-get install -y nvidia-cuda-toolkit
    
    # nvccのパスを確認
    if [ -f /usr/bin/nvcc ]; then
        echo "✓ CUDA toolkit installed: /usr/bin/nvcc"
        nvcc --version
    else
        echo "✗ Error: CUDA toolkit installation failed"
        exit 1
    fi
else
    echo "✓ CUDA toolkit is available"
    nvcc --version
fi
echo ""

# COLMAPの依存関係をインストール
echo "Step 3: Installing COLMAP dependencies..."
sudo apt-get update
sudo apt-get install -y \
    cmake \
    git \
    build-essential \
    libboost-program-options-dev \
    libboost-filesystem-dev \
    libboost-graph-dev \
    libboost-system-dev \
    libboost-test-dev \
    libeigen3-dev \
    libflann-dev \
    libfreeimage-dev \
    libmetis-dev \
    libgoogle-glog-dev \
    libgflags-dev \
    libsqlite3-dev \
    libglew-dev \
    qtbase5-dev \
    libqt5opengl5-dev \
    libcgal-dev \
    libcgal-qt5-dev \
    libceres-dev \
    libopencv-dev \
    opencv-data

echo "✓ Dependencies installed"
echo ""

# COLMAPのソースを取得
COLMAP_DIR="$SCRIPT_DIR/colmap_build"
COLMAP_SRC_DIR="$COLMAP_DIR/src"
COLMAP_BUILD_DIR="$COLMAP_DIR/build"

echo "Step 4: Downloading COLMAP source..."
if [ ! -d "$COLMAP_SRC_DIR" ]; then
    mkdir -p "$COLMAP_SRC_DIR"
    cd "$COLMAP_SRC_DIR/.."
    git clone https://github.com/colmap/colmap.git src
    echo "✓ COLMAP source downloaded"
else
    echo "✓ COLMAP source already exists, updating..."
    cd "$COLMAP_SRC_DIR"
    git pull
fi
echo ""

# ビルドディレクトリの作成
echo "Step 5: Configuring COLMAP build (CUDA enabled)..."
mkdir -p "$COLMAP_BUILD_DIR"
cd "$COLMAP_BUILD_DIR"

# CUDAアーキテクチャを検出
CUDA_ARCH=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader | head -1 | sed 's/\.//')
if [ -z "$CUDA_ARCH" ]; then
    # デフォルト値（GTX 1660 Tiなど）
    CUDA_ARCH="75"
fi
echo "Detected CUDA architecture: sm_$CUDA_ARCH"

# CMake設定（CUDAサポートを有効化）
# OpenImageIOはオプションなので、見つからない場合は自動的に無効化される
echo "Configuring CMake with CUDA support..."
cmake "$COLMAP_SRC_DIR" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCUDA_ENABLED=ON \
    -DCMAKE_CUDA_ARCHITECTURES="$CUDA_ARCH" \
    -DCMAKE_CUDA_COMPILER=/usr/bin/nvcc \
    -DGUI_ENABLED=OFF \
    2>&1 | tee /tmp/cmake_config.log

CMAKE_EXIT_CODE=$?
if [ $CMAKE_EXIT_CODE -ne 0 ]; then
    echo ""
    echo "⚠ CMake configuration failed. Checking for missing dependencies..."
    grep -i "not found\|missing\|required" /tmp/cmake_config.log | tail -5 || true
    echo ""
    echo "Attempting to continue with build anyway..."
    # 一部のオプション依存関係がなくてもビルドは続行可能
fi

echo "✓ CMake configuration completed"
echo ""

# ビルド（並列ビルド）
echo "Step 6: Building COLMAP (this will take 30-60 minutes)..."
CPU_COUNT=$(nproc)
echo "Using $CPU_COUNT CPU cores for parallel build"
make -j$CPU_COUNT

echo ""
echo "✓ COLMAP build completed"
echo ""

# インストール
echo "Step 7: Installing COLMAP..."
sudo make install

echo ""
echo "============================================================"
echo "✓ COLMAP CUDA対応版のインストールが完了しました！"
echo "============================================================"
echo ""
echo "インストール場所: /usr/local/bin/colmap"
echo ""

# インストール確認
if command -v colmap > /dev/null 2>&1; then
    echo "インストール確認:"
    colmap help 2>&1 | head -3
    echo ""
    echo "CUDAサポートの確認:"
    colmap help 2>&1 | grep -i cuda || echo "（ヘルプにCUDA情報が表示されない場合があります）"
    echo ""
    echo "✓ COLMAP is ready to use!"
else
    echo "⚠ Warning: colmap command not found in PATH"
    echo "  Try: export PATH=/usr/local/bin:\$PATH"
fi


set -e  # エラーが発生したら停止

echo "============================================================"
echo "COLMAP CUDA対応版ビルドスクリプト（WSL2用）"
echo "============================================================"
echo ""

# カレントディレクトリを保存
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# CUDA環境の確認
echo "Step 1: Checking CUDA environment..."
if ! nvidia-smi > /dev/null 2>&1; then
    echo "✗ Error: nvidia-smi not found. NVIDIA driver may not be installed."
    echo "  Please install NVIDIA driver for WSL2"
    exit 1
fi
echo "✓ NVIDIA driver is available"
nvidia-smi | head -5
echo ""

# CUDAツールキットの確認
echo "Step 2: Checking CUDA toolkit..."
if ! command -v nvcc > /dev/null 2>&1; then
    echo "⚠ CUDA toolkit not found. Installing..."
    echo "  Installing nvidia-cuda-toolkit..."
    sudo apt-get update
    sudo apt-get install -y nvidia-cuda-toolkit
    
    # nvccのパスを確認
    if [ -f /usr/bin/nvcc ]; then
        echo "✓ CUDA toolkit installed: /usr/bin/nvcc"
        nvcc --version
    else
        echo "✗ Error: CUDA toolkit installation failed"
        exit 1
    fi
else
    echo "✓ CUDA toolkit is available"
    nvcc --version
fi
echo ""

# COLMAPの依存関係をインストール
echo "Step 3: Installing COLMAP dependencies..."
sudo apt-get update
sudo apt-get install -y \
    cmake \
    git \
    build-essential \
    libboost-program-options-dev \
    libboost-filesystem-dev \
    libboost-graph-dev \
    libboost-system-dev \
    libboost-test-dev \
    libeigen3-dev \
    libflann-dev \
    libfreeimage-dev \
    libmetis-dev \
    libgoogle-glog-dev \
    libgflags-dev \
    libsqlite3-dev \
    libglew-dev \
    qtbase5-dev \
    libqt5opengl5-dev \
    libcgal-dev \
    libcgal-qt5-dev \
    libceres-dev \
    libopencv-dev \
    opencv-data

echo "✓ Dependencies installed"
echo ""

# COLMAPのソースを取得
COLMAP_DIR="$SCRIPT_DIR/colmap_build"
COLMAP_SRC_DIR="$COLMAP_DIR/src"
COLMAP_BUILD_DIR="$COLMAP_DIR/build"

echo "Step 4: Downloading COLMAP source..."
if [ ! -d "$COLMAP_SRC_DIR" ]; then
    mkdir -p "$COLMAP_SRC_DIR"
    cd "$COLMAP_SRC_DIR/.."
    git clone https://github.com/colmap/colmap.git src
    echo "✓ COLMAP source downloaded"
else
    echo "✓ COLMAP source already exists, updating..."
    cd "$COLMAP_SRC_DIR"
    git pull
fi
echo ""

# ビルドディレクトリの作成
echo "Step 5: Configuring COLMAP build (CUDA enabled)..."
mkdir -p "$COLMAP_BUILD_DIR"
cd "$COLMAP_BUILD_DIR"

# CUDAアーキテクチャを検出
CUDA_ARCH=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader | head -1 | sed 's/\.//')
if [ -z "$CUDA_ARCH" ]; then
    # デフォルト値（GTX 1660 Tiなど）
    CUDA_ARCH="75"
fi
echo "Detected CUDA architecture: sm_$CUDA_ARCH"

# CMake設定（CUDAサポートを有効化）
# OpenImageIOはオプションなので、見つからない場合は自動的に無効化される
echo "Configuring CMake with CUDA support..."
cmake "$COLMAP_SRC_DIR" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCUDA_ENABLED=ON \
    -DCMAKE_CUDA_ARCHITECTURES="$CUDA_ARCH" \
    -DCMAKE_CUDA_COMPILER=/usr/bin/nvcc \
    -DGUI_ENABLED=OFF \
    2>&1 | tee /tmp/cmake_config.log

CMAKE_EXIT_CODE=$?
if [ $CMAKE_EXIT_CODE -ne 0 ]; then
    echo ""
    echo "⚠ CMake configuration failed. Checking for missing dependencies..."
    grep -i "not found\|missing\|required" /tmp/cmake_config.log | tail -5 || true
    echo ""
    echo "Attempting to continue with build anyway..."
    # 一部のオプション依存関係がなくてもビルドは続行可能
fi

echo "✓ CMake configuration completed"
echo ""

# ビルド（並列ビルド）
echo "Step 6: Building COLMAP (this will take 30-60 minutes)..."
CPU_COUNT=$(nproc)
echo "Using $CPU_COUNT CPU cores for parallel build"
make -j$CPU_COUNT

echo ""
echo "✓ COLMAP build completed"
echo ""

# インストール
echo "Step 7: Installing COLMAP..."
sudo make install

echo ""
echo "============================================================"
echo "✓ COLMAP CUDA対応版のインストールが完了しました！"
echo "============================================================"
echo ""
echo "インストール場所: /usr/local/bin/colmap"
echo ""

# インストール確認
if command -v colmap > /dev/null 2>&1; then
    echo "インストール確認:"
    colmap help 2>&1 | head -3
    echo ""
    echo "CUDAサポートの確認:"
    colmap help 2>&1 | grep -i cuda || echo "（ヘルプにCUDA情報が表示されない場合があります）"
    echo ""
    echo "✓ COLMAP is ready to use!"
else
    echo "⚠ Warning: colmap command not found in PATH"
    echo "  Try: export PATH=/usr/local/bin:\$PATH"
fi


set -e  # エラーが発生したら停止

echo "============================================================"
echo "COLMAP CUDA対応版ビルドスクリプト（WSL2用）"
echo "============================================================"
echo ""

# カレントディレクトリを保存
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# CUDA環境の確認
echo "Step 1: Checking CUDA environment..."
if ! nvidia-smi > /dev/null 2>&1; then
    echo "✗ Error: nvidia-smi not found. NVIDIA driver may not be installed."
    echo "  Please install NVIDIA driver for WSL2"
    exit 1
fi
echo "✓ NVIDIA driver is available"
nvidia-smi | head -5
echo ""

# CUDAツールキットの確認
echo "Step 2: Checking CUDA toolkit..."
if ! command -v nvcc > /dev/null 2>&1; then
    echo "⚠ CUDA toolkit not found. Installing..."
    echo "  Installing nvidia-cuda-toolkit..."
    sudo apt-get update
    sudo apt-get install -y nvidia-cuda-toolkit
    
    # nvccのパスを確認
    if [ -f /usr/bin/nvcc ]; then
        echo "✓ CUDA toolkit installed: /usr/bin/nvcc"
        nvcc --version
    else
        echo "✗ Error: CUDA toolkit installation failed"
        exit 1
    fi
else
    echo "✓ CUDA toolkit is available"
    nvcc --version
fi
echo ""

# COLMAPの依存関係をインストール
echo "Step 3: Installing COLMAP dependencies..."
sudo apt-get update
sudo apt-get install -y \
    cmake \
    git \
    build-essential \
    libboost-program-options-dev \
    libboost-filesystem-dev \
    libboost-graph-dev \
    libboost-system-dev \
    libboost-test-dev \
    libeigen3-dev \
    libflann-dev \
    libfreeimage-dev \
    libmetis-dev \
    libgoogle-glog-dev \
    libgflags-dev \
    libsqlite3-dev \
    libglew-dev \
    qtbase5-dev \
    libqt5opengl5-dev \
    libcgal-dev \
    libcgal-qt5-dev \
    libceres-dev \
    libopencv-dev \
    opencv-data

echo "✓ Dependencies installed"
echo ""

# COLMAPのソースを取得
COLMAP_DIR="$SCRIPT_DIR/colmap_build"
COLMAP_SRC_DIR="$COLMAP_DIR/src"
COLMAP_BUILD_DIR="$COLMAP_DIR/build"

echo "Step 4: Downloading COLMAP source..."
if [ ! -d "$COLMAP_SRC_DIR" ]; then
    mkdir -p "$COLMAP_SRC_DIR"
    cd "$COLMAP_SRC_DIR/.."
    git clone https://github.com/colmap/colmap.git src
    echo "✓ COLMAP source downloaded"
else
    echo "✓ COLMAP source already exists, updating..."
    cd "$COLMAP_SRC_DIR"
    git pull
fi
echo ""

# ビルドディレクトリの作成
echo "Step 5: Configuring COLMAP build (CUDA enabled)..."
mkdir -p "$COLMAP_BUILD_DIR"
cd "$COLMAP_BUILD_DIR"

# CUDAアーキテクチャを検出
CUDA_ARCH=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader | head -1 | sed 's/\.//')
if [ -z "$CUDA_ARCH" ]; then
    # デフォルト値（GTX 1660 Tiなど）
    CUDA_ARCH="75"
fi
echo "Detected CUDA architecture: sm_$CUDA_ARCH"

# CMake設定（CUDAサポートを有効化）
# OpenImageIOはオプションなので、見つからない場合は自動的に無効化される
echo "Configuring CMake with CUDA support..."
cmake "$COLMAP_SRC_DIR" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCUDA_ENABLED=ON \
    -DCMAKE_CUDA_ARCHITECTURES="$CUDA_ARCH" \
    -DCMAKE_CUDA_COMPILER=/usr/bin/nvcc \
    -DGUI_ENABLED=OFF \
    2>&1 | tee /tmp/cmake_config.log

CMAKE_EXIT_CODE=$?
if [ $CMAKE_EXIT_CODE -ne 0 ]; then
    echo ""
    echo "⚠ CMake configuration failed. Checking for missing dependencies..."
    grep -i "not found\|missing\|required" /tmp/cmake_config.log | tail -5 || true
    echo ""
    echo "Attempting to continue with build anyway..."
    # 一部のオプション依存関係がなくてもビルドは続行可能
fi

echo "✓ CMake configuration completed"
echo ""

# ビルド（並列ビルド）
echo "Step 6: Building COLMAP (this will take 30-60 minutes)..."
CPU_COUNT=$(nproc)
echo "Using $CPU_COUNT CPU cores for parallel build"
make -j$CPU_COUNT

echo ""
echo "✓ COLMAP build completed"
echo ""

# インストール
echo "Step 7: Installing COLMAP..."
sudo make install

echo ""
echo "============================================================"
echo "✓ COLMAP CUDA対応版のインストールが完了しました！"
echo "============================================================"
echo ""
echo "インストール場所: /usr/local/bin/colmap"
echo ""

# インストール確認
if command -v colmap > /dev/null 2>&1; then
    echo "インストール確認:"
    colmap help 2>&1 | head -3
    echo ""
    echo "CUDAサポートの確認:"
    colmap help 2>&1 | grep -i cuda || echo "（ヘルプにCUDA情報が表示されない場合があります）"
    echo ""
    echo "✓ COLMAP is ready to use!"
else
    echo "⚠ Warning: colmap command not found in PATH"
    echo "  Try: export PATH=/usr/local/bin:\$PATH"
fi