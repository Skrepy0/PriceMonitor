#!/bin/bash
# ============================================
# Price Monitor 项目部署脚本
# 用法：./deploy.sh
# 功能：强制同步远程代码、更新依赖、重启服务
# ============================================
if [ ! -x "$0" ]; then
    chmod +x "$0"
    echo "已恢复脚本执行权限，请下次直接 ./deploy.sh 运行"
fi
set -e

# ---------- 颜色输出 ----------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info() { echo -e "${GREEN}✅${NC} $1"; }
warn() { echo -e "${YELLOW}⚠️${NC} $1"; }
error() { echo -e "${RED}❌${NC} $1"; }
step() { echo -e "${BLUE}➜${NC} $1"; }

# ---------- 获取脚本所在目录 ----------
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"
info "项目目录: $PROJECT_DIR"

# ---------- 检查 Git 仓库 ----------
if [ ! -d ".git" ]; then
    error "当前目录不是 Git 仓库，请确保项目通过 Git 管理。"
    exit 1
fi

# ---------- 备份 .env ----------
if [ -f ".env" ]; then
    cp .env .env.backup
    info "已备份 .env 文件到 .env.backup"
fi

# ---------- 强制同步代码 ----------
step "强制同步远程代码（丢弃所有本地更改）..."
git fetch --all
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" = "main" ] || [ "$CURRENT_BRANCH" = "master" ]; then
    git reset --hard "origin/$CURRENT_BRANCH"
else
    warn "当前不在 main/master 分支，切换到 main..."
    git checkout main || git checkout master
    git reset --hard "origin/$(git branch --show-current)"
fi
step "清理未跟踪的文件（保留 .env）..."
git clean -fd -e .env
info "代码已完全同步到远程最新版本"

# ---------- 恢复 .env（如果新仓库没有） ----------
if [ -f ".env.backup" ] && [ ! -f ".env" ]; then
    mv .env.backup .env
    info "已从备份恢复 .env"
else
    rm -f .env.backup
fi

# ---------- 更新依赖 ----------
step "更新 Python 依赖..."
if command -v uv &> /dev/null; then
    info "使用 uv 同步依赖..."
    uv sync --no-dev
    info "安装项目为可编辑包..."
    uv pip install -e .
else
    # 仅当 uv 不可用时才回退到 pip
    warn "未检测到 uv，使用 pip..."
    if [ -f ".venv/bin/activate" ]; then
        source .venv/bin/activate
        # 注意：这里使用 pip 需要确保虚拟环境包含 pip
        # 如果是在 uv 环境下，可能仍需显式安装 pip
        pip install --upgrade pip
        pip install -r requirements.txt
        pip install -e .
    else
        warn "未检测到虚拟环境，跳过依赖更新。"
    fi
fi

# ---------- 重启 systemd 服务 ----------
step "重启 systemd 服务..."
SERVICE_NAME="price-monitor"

if ! systemctl list-unit-files | grep -q "^$SERVICE_NAME.service"; then
    error "服务 $SERVICE_NAME 未注册，请先创建 systemd 服务单元。"
    exit 1
fi

if systemctl is-active --quiet "$SERVICE_NAME"; then
    systemctl restart "$SERVICE_NAME"
    info "服务 $SERVICE_NAME 已重启"
else
    warn "服务 $SERVICE_NAME 未运行，尝试启动..."
    systemctl start "$SERVICE_NAME"
fi

sleep 2

step "检查服务状态..."
if systemctl is-active --quiet "$SERVICE_NAME"; then
    info "✅ 服务 $SERVICE_NAME 运行正常"
else
    error "❌ 服务 $SERVICE_NAME 启动失败，请检查日志："
    systemctl status "$SERVICE_NAME" --no-pager
    exit 1
fi

step "最近日志（最后 10 行）："
journalctl -u "$SERVICE_NAME" -n 10 --no-pager

info "🎉 部署完成！"