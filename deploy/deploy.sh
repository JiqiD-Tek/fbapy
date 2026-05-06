#!/bin/bash

set -euo pipefail

DEFAULT_VERSION="latest"
SERVICE_NAME="fba_server"
CONTAINER_NAME="fba_server"
IMAGE_NAME="fba_server"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

show_main_usage() {
    cat <<EOF
Usage: $0 <command> [options]

Commands:
  build                 Build image only, keep current container running
  switch                Stop current container and start an existing image tag
  rebuild               Build image, switch container, then clean old images
  help                  Show this help message

Options:
  -v, --version <tag>   Image tag to use (default: ${DEFAULT_VERSION})
  -h, --help            Show command help

Examples:
  $0 build
  $0 build -v 1.0.0
  $0 switch -v 1.0.0
  $0 rebuild -v 1.0.0
EOF
}

show_command_usage() {
    local command="$1"

    case "${command}" in
        build)
            cat <<EOF
Usage: $0 build [options]

Build image only, without stopping or removing the current container.

Options:
  -v, --version <tag>   Image tag to build (default: ${DEFAULT_VERSION})
  -h, --help            Show this help message
EOF
            ;;
        switch)
            cat <<EOF
Usage: $0 switch [options]

Stop the current container and start the specified existing image tag.

Options:
  -v, --version <tag>   Image tag to run (default: ${DEFAULT_VERSION})
  -h, --help            Show this help message
EOF
            ;;
        rebuild)
            cat <<EOF
Usage: $0 rebuild [options]

Build the image, switch the container, then clean old images.

Options:
  -v, --version <tag>   Image tag to build and run (default: ${DEFAULT_VERSION})
  -h, --help            Show this help message
EOF
            ;;
        *)
            show_main_usage
            ;;
    esac
}

check_command() {
    command -v "$1" >/dev/null 2>&1 || {
        log_error "Command not found: $1"
        exit 1
    }
}

check_file() {
    [ -f "$1" ] || {
        log_error "File not found: $1"
        exit 1
    }
}

setup_paths() {
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
    COMPOSE_DIR="${PROJECT_DIR}/deploy/backend/cloud"
    COMPOSE_FILE="${COMPOSE_DIR}/docker-compose.yml"
}

parse_version_args() {
    local command="$1"
    shift

    IMAGE_VERSION="${DEFAULT_VERSION}"

    while [[ $# -gt 0 ]]; do
        case "$1" in
            -v|--version)
                if [[ $# -lt 2 || -z "${2:-}" ]]; then
                    log_error "Missing image version"
                    show_command_usage "${command}"
                    exit 1
                fi
                IMAGE_VERSION="$2"
                shift 2
                ;;
            -h|--help)
                show_command_usage "${command}"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_command_usage "${command}"
                exit 1
                ;;
        esac
    done
}

detect_compose_cmd() {
    if docker compose version >/dev/null 2>&1; then
        COMPOSE_CMD=("docker" "compose")
        return
    fi

    if command -v docker-compose >/dev/null 2>&1; then
        COMPOSE_CMD=("docker-compose")
        return
    fi

    log_error "Neither 'docker compose' nor 'docker-compose' is available"
    exit 1
}

compose() {
    "${COMPOSE_CMD[@]}" "$@"
}

ensure_common_requirements() {
    check_command docker
    check_file "${PROJECT_DIR}/Dockerfile"
}

ensure_compose_requirements() {
    detect_compose_cmd
    check_file "${COMPOSE_FILE}"
}

ensure_image_exists() {
    if docker image inspect "${IMAGE_NAME}:${IMAGE_VERSION}" >/dev/null 2>&1; then
        return
    fi

    log_error "Image not found: ${IMAGE_NAME}:${IMAGE_VERSION}"
    log_info "Build it first: ./deploy/deploy.sh build -v ${IMAGE_VERSION}"
    exit 1
}

get_existing_container_id() {
    docker ps -aq -f "name=^/${CONTAINER_NAME}$" || true
}

get_current_image_id() {
    docker inspect -f '{{.Image}}' "${CONTAINER_NAME}" 2>/dev/null || docker image inspect -f '{{.Id}}' "${IMAGE_NAME}:latest" 2>/dev/null || true
}

build_image() {
    cd "${PROJECT_DIR}"
    DOCKER_BUILDKIT=1 docker build \
        -f "${PROJECT_DIR}/Dockerfile" \
        -t "${IMAGE_NAME}:${IMAGE_VERSION}" \
        -t "${IMAGE_NAME}:latest" \
        "${PROJECT_DIR}"
}

remove_existing_container() {
    local existing_container_id
    existing_container_id="$(get_existing_container_id)"

    if [[ -z "${existing_container_id}" ]]; then
        log_info "No existing container found"
        return
    fi

    local state
    state="$(docker inspect -f '{{.State.Status}}' "${CONTAINER_NAME}" 2>/dev/null || true)"
    if [[ -n "${state}" ]]; then
        log_info "Stopping container ${CONTAINER_NAME} (${state})..."
        docker stop "${CONTAINER_NAME}" >/dev/null 2>&1 || true
    fi

    log_info "Removing container ${CONTAINER_NAME}..."
    docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
}

wait_for_container() {
    local max_attempts=30
    local attempt=1

    while [[ ${attempt} -le ${max_attempts} ]]; do
        if [[ "$(docker inspect -f '{{.State.Running}}' "${CONTAINER_NAME}" 2>/dev/null || true)" == "true" ]]; then
            log_success "Container ${CONTAINER_NAME} is running"
            return 0
        fi

        if [[ ${attempt} -eq ${max_attempts} ]]; then
            log_error "Container ${CONTAINER_NAME} failed to start"
            compose -f "${COMPOSE_FILE}" ps "${SERVICE_NAME}" || true
            compose -f "${COMPOSE_FILE}" logs --tail=50 "${SERVICE_NAME}" || true
            return 1
        fi

        log_info "Waiting for container startup... (${attempt}/${max_attempts})"
        sleep 2
        attempt=$((attempt + 1))
    done
}

start_container() {
    cd "${COMPOSE_DIR}"
    env IMAGE_VERSION="${IMAGE_VERSION}" "${COMPOSE_CMD[@]}" -f "${COMPOSE_FILE}" up -d "${SERVICE_NAME}"
}

remove_old_image() {
    local old_image_id="$1"
    local new_image_id="$2"

    if [[ -z "${old_image_id}" ]]; then
        log_info "No previous image to remove"
        return
    fi

    if [[ "${old_image_id}" == "${new_image_id}" ]]; then
        log_info "Image ID unchanged, skipping old image removal"
        return
    fi

    if [[ -n "$(docker ps -aq --filter "ancestor=${old_image_id}" 2>/dev/null || true)" ]]; then
        log_warning "Old image is still referenced by another container, skipping removal"
        return
    fi

    log_info "Removing previous image ${old_image_id}..."
    docker rmi "${old_image_id}" >/dev/null 2>&1 || log_warning "Failed to remove previous image ${old_image_id}"
}

cleanup_dangling_images() {
    local dangling_images
    dangling_images="$(docker images -f "dangling=true" -q || true)"

    if [[ -z "${dangling_images}" ]]; then
        log_info "No dangling images found"
        return
    fi

    log_info "Removing dangling images..."
    echo "${dangling_images}" | xargs -r docker rmi >/dev/null 2>&1 || log_warning "Failed to remove some dangling images"
}

run_build() {
    parse_version_args build "$@"
    setup_paths
    ensure_common_requirements

    local running_container_id
    running_container_id="$(get_existing_container_id)"

    log_info "Project directory: ${PROJECT_DIR}"
    log_info "Image version: ${IMAGE_VERSION}"

    if [[ -n "${running_container_id}" ]]; then
        log_info "Existing container ${CONTAINER_NAME} detected and will be left untouched"
    else
        log_info "No existing container named ${CONTAINER_NAME} was found"
    fi

    log_info "Step 1/2: Build new image"
    build_image
    log_success "Built image ${IMAGE_NAME}:${IMAGE_VERSION}"

    log_info "Step 2/2: Keep existing containers and images unchanged"
    log_info "Current container ${CONTAINER_NAME} was not stopped or removed"
    log_info "Previously built images were not removed"

    log_success "Build completed"
    log_info "Built tags:"
    log_info "  - ${IMAGE_NAME}:${IMAGE_VERSION}"
    log_info "  - ${IMAGE_NAME}:latest"
    log_info "To switch later, run: ./deploy/deploy.sh switch -v ${IMAGE_VERSION}"
}

run_switch() {
    parse_version_args switch "$@"
    setup_paths
    ensure_common_requirements
    ensure_compose_requirements
    ensure_image_exists

    local running_image_id
    running_image_id="$(docker inspect -f '{{.Image}}' "${CONTAINER_NAME}" 2>/dev/null || true)"

    log_info "Project directory: ${PROJECT_DIR}"
    log_info "Compose file: ${COMPOSE_FILE}"
    log_info "Target image version: ${IMAGE_VERSION}"

    if [[ -n "${running_image_id}" ]]; then
        log_info "Current container image ID: ${running_image_id}"
    fi

    log_info "Step 1/3: Stop and remove current container"
    remove_existing_container

    log_info "Step 2/3: Start container from ${IMAGE_NAME}:${IMAGE_VERSION}"
    start_container

    log_info "Step 3/3: Verify container status"
    wait_for_container

    log_info "Container status:"
    compose -f "${COMPOSE_FILE}" ps "${SERVICE_NAME}"

    log_success "Switch completed"
    log_info "Running image: ${IMAGE_NAME}:${IMAGE_VERSION}"
    log_info "Logs: ${COMPOSE_CMD[*]} -f ${COMPOSE_FILE} logs -f ${SERVICE_NAME}"
}

run_rebuild() {
    parse_version_args rebuild "$@"
    setup_paths
    ensure_common_requirements
    ensure_compose_requirements

    local old_image_id new_image_id
    old_image_id="$(get_current_image_id)"

    log_info "Project directory: ${PROJECT_DIR}"
    log_info "Compose file: ${COMPOSE_FILE}"
    log_info "Image version: ${IMAGE_VERSION}"

    log_info "Step 1/5: Build new image"
    build_image
    log_success "Built image ${IMAGE_NAME}:${IMAGE_VERSION}"

    log_info "Step 2/5: Stop and remove current container"
    remove_existing_container

    log_info "Step 3/5: Start new container"
    start_container

    log_info "Step 4/5: Verify container status"
    wait_for_container
    new_image_id="$(docker inspect -f '{{.Image}}' "${CONTAINER_NAME}")"

    log_info "Step 5/5: Remove previous image"
    remove_old_image "${old_image_id}" "${new_image_id}"
    cleanup_dangling_images

    log_info "Container status:"
    compose -f "${COMPOSE_FILE}" ps "${SERVICE_NAME}"

    log_success "Rebuild completed"
    log_info "Running image: ${IMAGE_NAME}:${IMAGE_VERSION}"
    log_info "Logs: ${COMPOSE_CMD[*]} -f ${COMPOSE_FILE} logs -f ${SERVICE_NAME}"
}

main() {
    local command="${1:-help}"

    case "${command}" in
        build)
            shift
            run_build "$@"
            ;;
        switch)
            shift
            run_switch "$@"
            ;;
        rebuild)
            shift
            run_rebuild "$@"
            ;;
        help|-h|--help)
            show_main_usage
            ;;
        *)
            log_error "Unknown command: ${command}"
            show_main_usage
            exit 1
            ;;
    esac
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
