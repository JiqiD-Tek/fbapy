#!/bin/bash

# fba_server 部署脚本
# Author: guhua@jiqid.com

set -e  # 遇到错误立即退出

# 默认版本号
DEFAULT_VERSION="latest"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 显示用法
show_usage() {
    echo "用法: $0 [选项]"
    echo "选项:"
    echo "  -v, --version <版本号>    指定镜像版本号 (默认: $DEFAULT_VERSION)"
    echo "  -h, --help                显示帮助信息"
    echo ""
    echo "示例:"
    echo "  $0                        使用默认版本号 latest"
    echo "  $0 -v 1.0.0               使用指定版本号 1.0.0"
    echo "  $0 --version v2.1.3       使用指定版本号 v2.1.3"
}

# ==========================
# 检查命令/文件/目录
# ==========================
check_command() { command -v "$1" &>/dev/null || { log_error "命令 $1 未找到，请安装"; exit 1; } }
check_file()    { [ -f "$1" ] || { log_error "文件不存在: $1"; exit 1; } }
check_dir()     { [ -d "$1" ] || { log_error "目录不存在: $1"; exit 1; } }

# 解析命令行参数
parse_args() {
    IMAGE_VERSION="$DEFAULT_VERSION"

    while [[ $# -gt 0 ]]; do
        case "$1" in
            -v|--version)
                if [ -n "$2" ]; then
                    IMAGE_VERSION="$2"
                    shift 2
                else
                    log_error "错误: 需要指定版本号"
                    show_usage
                    exit 1
                fi
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            *)
                log_error "未知选项: $1"
                show_usage
                exit 1
                ;;
        esac
    done
}

# 主函数
main() {
    echo "=== fba_server 部署脚本 ==="

    # 解析参数
    parse_args "$@"
    log_info "镜像版本: $IMAGE_VERSION"

    # 初始化路径
    local PROJECT_DIR
    PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    local COMPOSE_DIR="$PROJECT_DIR/deploy/backend/cloud"

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
    if docker-compose ps fba_server 2>/dev/null | grep -q "Up"; then
        log_info "正在停止 fba_server 容器..."
        docker-compose stop fba_server
        docker-compose rm -f fba_server || log_warning "删除 fba_server 容器时出现问题"
    else
        log_info "fba_server 容器未运行，无需停止"
    fi

    # 2. 构建新镜像
    log_info "步骤 2: 构建 Docker 镜像..."
    cd "$PROJECT_DIR"
    local IMAGE_NAME="fba_server"
    DOCKER_BUILDKIT=1 docker build -f Dockerfile -t "${IMAGE_NAME}:${IMAGE_VERSION}" .
    log_success "镜像构建完成: ${IMAGE_NAME}:${IMAGE_VERSION}"

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
    docker-compose up fba_server -d

    # 5. 验证部署
    log_info "步骤 5: 验证部署..."
    local max_attempts=30
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if docker-compose ps fba_server | grep -q "Up"; then
            log_success "fba_server 容器启动成功！"
            break
        fi

        if [ $attempt -eq $max_attempts ]; then
            log_error "fba_server 容器启动失败，请检查日志"
            log_info "容器状态:"
            docker-compose ps fba_server
            log_info "最近日志:"
            docker-compose logs --tail=20 fba_server
            exit 1
        fi

        log_info "等待容器启动... ($attempt/$max_attempts)"
        sleep 2
        ((attempt++))
    done

    # 显示最终状态
    log_info "最终容器状态:"
    docker-compose ps fba_server

    log_success "=== 部署完成 ==="
    log_info "镜像版本: ${IMAGE_NAME}:${IMAGE_VERSION}"
    log_info "使用 'docker-compose logs -f fba_server' 查看实时日志"
}

# 脚本入口
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
