#!/bin/bash
# ============================================================
# ARCore + Open3D Server Setup for Ubuntu (WSL2)
# ============================================================
# 
# 使用方法:
#   chmod +x setup_ubuntu.sh
#   sudo ./setup_ubuntu.sh
#
# 必要な環境:
#   - Ubuntu 22.04+ (WSL2推奨)
#   - NVIDIA GPU + CUDA対応ドライバ
#   - 6GB+ VRAM推奨
#
# ============================================================

set -e

# 色付き出力
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ============================================================
# Configuration
# ============================================================
SERVICE_NAME="arcore-open3d"
SERVICE_USER="${SUDO_USER:-$USER}"
SERVICE_USER_HOME=$(getent passwd "$SERVICE_USER" | cut -d: -f6)

INSTALL_DIR="/opt/${SERVICE_NAME}"
DATA_DIR="${INSTALL_DIR}/data"
RESULTS_DIR="${INSTALL_DIR}/results"
LOG_DIR="/var/log/${SERVICE_NAME}"

VENV_DIR="${INSTALL_DIR}/venv"
PYTHON_VERSION="3.10"

# ============================================================
# Pre-flight checks
# ============================================================
log_info "Starting ARCore + Open3D Server Setup..."

if [ "$EUID" -ne 0 ]; then
    log_error "Please run as root (sudo)"
    exit 1
fi

# Check GPU
if command -v nvidia-smi &> /dev/null; then
    log_info "NVIDIA GPU detected:"
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
else
    log_warn "nvidia-smi not found. CUDA acceleration may not be available."
fi

# ============================================================
# System packages
# ============================================================
log_info "Installing system packages..."

apt-get update
apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    curl \
    wget \
    libgl1 \
    libglib2.0-0t64 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libegl1 \
    libgl1-mesa-dri \
    mesa-utils

log_success "System packages installed"

# ============================================================
# Create directories
# ============================================================
log_info "Creating directories..."

mkdir -p "${INSTALL_DIR}"
mkdir -p "${DATA_DIR}/sessions"
mkdir -p "${RESULTS_DIR}"
mkdir -p "${LOG_DIR}"

# Set ownership
chown -R "${SERVICE_USER}:${SERVICE_USER}" "${INSTALL_DIR}"
chown -R "${SERVICE_USER}:${SERVICE_USER}" "${DATA_DIR}"
chown -R "${SERVICE_USER}:${SERVICE_USER}" "${RESULTS_DIR}"
chown -R "${SERVICE_USER}:${SERVICE_USER}" "${LOG_DIR}"

log_success "Directories created"

# ============================================================
# Python virtual environment
# ============================================================
log_info "Creating Python virtual environment..."

sudo -u "${SERVICE_USER}" python3 -m venv "${VENV_DIR}"

log_success "Virtual environment created"

# ============================================================
# Install Python dependencies
# ============================================================
log_info "Installing Python dependencies..."

# Upgrade pip
sudo -u "${SERVICE_USER}" "${VENV_DIR}/bin/pip" install --upgrade pip

# Core dependencies
sudo -u "${SERVICE_USER}" "${VENV_DIR}/bin/pip" install \
    fastapi>=0.109.0 \
    uvicorn[standard]>=0.27.0 \
    python-multipart>=0.0.6 \
    aiofiles>=23.2.1 \
    pillow>=10.2.0 \
    opencv-python>=4.9.0 \
    numpy>=1.26.0 \
    scipy>=1.12.0 \
    pyyaml>=6.0.0 \
    httpx>=0.26.0 \
    pydantic>=2.5.0 \
    plyfile>=1.0.0 \
    trimesh>=4.1.0

# Open3D
log_info "Installing Open3D..."
sudo -u "${SERVICE_USER}" "${VENV_DIR}/bin/pip" install open3d>=0.18.0

# PyTorch (CUDA)
log_info "Installing PyTorch (CUDA)..."
sudo -u "${SERVICE_USER}" "${VENV_DIR}/bin/pip" install \
    torch>=2.1.0 \
    torchvision>=0.16.0 \
    --index-url https://download.pytorch.org/whl/cu121

# timm (MiDaS dependency) - 通常のPyPIからインストール
log_info "Installing timm (MiDaS dependency)..."
sudo -u "${SERVICE_USER}" "${VENV_DIR}/bin/pip" install timm>=0.9.0

log_success "Python dependencies installed"

# ============================================================
# Copy server files
# ============================================================
log_info "Copying server files..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Copy all Python files
cp -r "${SCRIPT_DIR}/main.py" "${INSTALL_DIR}/"
cp -r "${SCRIPT_DIR}/config.yaml" "${INSTALL_DIR}/"
cp -r "${SCRIPT_DIR}/pipeline" "${INSTALL_DIR}/"
cp -r "${SCRIPT_DIR}/utils" "${INSTALL_DIR}/"
cp -r "${SCRIPT_DIR}/static" "${INSTALL_DIR}/"

# Set ownership
chown -R "${SERVICE_USER}:${SERVICE_USER}" "${INSTALL_DIR}"

log_success "Server files copied"

# ============================================================
# Update config.yaml paths
# ============================================================
log_info "Updating configuration..."

cat > "${INSTALL_DIR}/config.yaml" << EOF
# ARCore + Open3D Server Configuration

server:
  host: "0.0.0.0"
  port: 8001
  data_dir: "${DATA_DIR}"
  results_dir: "${RESULTS_DIR}"

processing:
  default_mode: "rgbd"
  
  tsdf:
    voxel_length: 0.005
    sdf_trunc: 0.04
    color_type: "RGB8"
  
  depth:
    scale: 1000.0
    trunc: 3.0
    min_depth: 0.1
  
  pointcloud:
    voxel_down_size: 0.01
    remove_outliers: true
    nb_neighbors: 20
    std_ratio: 2.0

mesh:
  method: "poisson"
  
  poisson:
    depth: 9
    width: 0
    scale: 1.1
    linear_fit: false

depth_estimation:
  enable: true
  model: "DPT_Large"
  device: "cuda"

gpu:
  enabled: true
  device_id: 0
  use_cuda: true

output:
  point_cloud:
    format: "ply"
    with_normals: true
    with_colors: true
  
  mesh:
    format: "ply"
    compute_normals: true
    simplify: false
    target_triangles: 100000

logging:
  level: "INFO"
  file: "${LOG_DIR}/server.log"
EOF

chown "${SERVICE_USER}:${SERVICE_USER}" "${INSTALL_DIR}/config.yaml"

log_success "Configuration updated"

# ============================================================
# Systemd service
# ============================================================
log_info "Creating systemd service..."

cat > "/etc/systemd/system/${SERVICE_NAME}.service" << EOF
[Unit]
Description=ARCore Open3D 3D Reconstruction Server
After=network.target

[Service]
Type=simple
User=${SERVICE_USER}
WorkingDirectory=${INSTALL_DIR}
Environment="PATH=${VENV_DIR}/bin:/usr/local/bin:/usr/bin"
Environment="PYTHONUNBUFFERED=1"
Environment="QT_QPA_PLATFORM=offscreen"
ExecStart=${VENV_DIR}/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8001
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"

log_success "Systemd service created"

# ============================================================
# Preload MiDaS model (optional)
# ============================================================
log_info "Pre-downloading MiDaS model (this may take a while)..."

sudo -u "${SERVICE_USER}" "${VENV_DIR}/bin/python" << 'PYEOF'
import torch
try:
    print("Loading MiDaS model...")
    model = torch.hub.load("intel-isl/MiDaS", "DPT_Large", trust_repo=True)
    print("MiDaS model pre-loaded successfully")
except Exception as e:
    print(f"Warning: Could not pre-load MiDaS: {e}")
PYEOF

# ============================================================
# Start service
# ============================================================
log_info "Starting service..."

systemctl start "${SERVICE_NAME}"
sleep 3

if systemctl is-active --quiet "${SERVICE_NAME}"; then
    log_success "Service started successfully!"
else
    log_error "Service failed to start. Check logs:"
    journalctl -u "${SERVICE_NAME}" --no-pager -n 30
fi

# ============================================================
# Summary
# ============================================================
echo ""
echo "============================================================"
log_success "ARCore + Open3D Server Setup Complete!"
echo "============================================================"
echo ""
echo "  Server URL:      http://localhost:8001"
echo "  Viewer:          http://localhost:8001/viewer"
echo "  Health:          http://localhost:8001/api/v1/health"
echo ""
echo "  Service name:    ${SERVICE_NAME}"
echo "  Install dir:     ${INSTALL_DIR}"
echo "  Data dir:        ${DATA_DIR}"
echo "  Log file:        ${LOG_DIR}/server.log"
echo ""
echo "  Commands:"
echo "    sudo systemctl status ${SERVICE_NAME}"
echo "    sudo systemctl restart ${SERVICE_NAME}"
echo "    sudo journalctl -u ${SERVICE_NAME} -f"
echo ""
echo "  Note: This server runs on port 8001 (different from COLMAP server)"
echo "============================================================"

