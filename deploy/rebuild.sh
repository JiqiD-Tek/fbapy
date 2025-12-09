#!/bin/bash

# Fbapy 部署脚本
# Author: guhua@jiqid.com

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查命令是否存在
check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "命令 $1 未找到，请先安装"
        exit 1
    fi
}

# 检查文件是否存在
check_file() {
    if [ ! -f "$1" ]; then
        log_error "文件不存在: $1"
        exit 1
    fi
}

# 检查目录是否存在
check_dir() {
    if [ ! -d "$1" ]; then
        log_error "目录不存在: $1"
        exit 1
    fi
}

# 主函数
main() {
    echo "=== Fbapy 部署脚本 ==="

    # 初始化路径
    local PROJECT_DIR
    PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    local COMPOSE_DIR="$PROJECT_DIR/deploy/backend/docker-compose"

    log_info "项目目录: $PROJECT_DIR"
    log_info "Docker Compose 目录: $COMPOSE_DIR"

    # 检查必要的命令
    check_command docker
    check_command docker-compose

    # 检查必要的目录和文件
    check_dir "$COMPOSE_DIR"
    check_file "$COMPOSE_DIR/docker-compose.yml"
    check_file "$PROJECT_DIR/Dockerfile"

    # 1. 停止现有容器
    log_info "步骤 1: 停止现有容器..."
    cd "$COMPOSE_DIR"
    if docker-compose ps fbapy 2>/dev/null | grep -q "Up"; then
        log_info "正在停止 fbapy 容器..."
        docker-compose stop fbapy
        docker-compose rm -f fbapy || log_warning "删除 fbapy 容器时出现问题"
    else
        log_info "fbapy 容器未运行，无需停止"
    fi

    # 2. 构建新镜像
    log_info "步骤 2: 构建 Docker 镜像..."
    cd "$PROJECT_DIR"
    local IMAGE_NAME="fbapy"
    local TIMESTAMP
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)

    # 构建镜像，只打 latest 标签
    docker build -f Dockerfile -t "${IMAGE_NAME}:latest" .
    log_success "镜像构建完成: ${IMAGE_NAME}:latest"

    # 3. 清理悬空镜像
    log_info "步骤 3: 清理悬空镜像..."
    local DANGLING_IMAGES
    DANGLING_IMAGES=$(docker images -f "dangling=true" -q)
    if [ -n "$DANGLING_IMAGES" ]; then
        log_info "找到悬空镜像，正在清理..."
        echo "$DANGLING_IMAGES" | xargs -r docker rmi 2>/dev/null &&
            log_success "悬空镜像清理完成" ||
            log_warning "清理部分悬空镜像时失败"
    else
        log_info "未找到悬空镜像"
    fi

    # 4. 启动新容器
    log_info "步骤 4: 启动容器..."
    cd "$COMPOSE_DIR"
    docker-compose up fbapy -d

    # 5. 验证部署
    log_info "步骤 5: 验证部署..."
    local max_attempts=30
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if docker-compose ps fbapy | grep -q "Up"; then
            log_success "Fbapy 容器启动成功！"
            break
        fi

        if [ $attempt -eq $max_attempts ]; then
            log_error "Fbapy 容器启动失败，请检查日志"
            log_info "容器状态:"
            docker-compose ps fbapy
            log_info "最近日志:"
            docker-compose logs --tail=20 fbapy
            exit 1
        fi

        log_info "等待容器启动... ($attempt/$max_attempts)"
        sleep 2
        ((attempt++))
    done

    # 显示最终状态
    log_info "最终容器状态:"
    docker-compose ps fbapy

    log_success "=== 部署完成 ==="
    log_info "镜像版本: ${IMAGE_NAME}:${TIMESTAMP}"
    log_info "使用 'docker-compose logs -f fbapy' 查看实时日志"
}

# 脚本入口
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi