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

show_usage() {
    cat <<EOF
Usage: $0 [options]

Options:
  -v, --version <tag>   Image tag to build and run (default: ${DEFAULT_VERSION})
  -h, --help            Show this help message

Examples:
  $0
  $0 -v 1.0.0
  $0 --version v2.1.3
EOF
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

parse_args() {
    IMAGE_VERSION="${DEFAULT_VERSION}"

    while [[ $# -gt 0 ]]; do
        case "$1" in
            -v|--version)
                if [[ $# -lt 2 || -z "${2:-}" ]]; then
                    log_error "Missing image version"
                    show_usage
                    exit 1
                fi
                IMAGE_VERSION="$2"
                shift 2
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_usage
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

remove_existing_container() {
    local existing_container_id
    existing_container_id="$(docker ps -aq -f "name=^/${CONTAINER_NAME}$" || true)"

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

main() {
    parse_args "$@"

    local script_dir project_dir compose_dir old_image_id new_image_id
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    project_dir="$(cd "${script_dir}/.." && pwd)"
    compose_dir="${project_dir}/deploy/backend/cloud"
    COMPOSE_FILE="${compose_dir}/docker-compose.yml"

    log_info "Project directory: ${project_dir}"
    log_info "Compose file: ${COMPOSE_FILE}"
    log_info "Image version: ${IMAGE_VERSION}"

    check_command docker
    detect_compose_cmd
    check_file "${COMPOSE_FILE}"
    check_file "${project_dir}/Dockerfile"

    old_image_id="$(docker inspect -f '{{.Image}}' "${CONTAINER_NAME}" 2>/dev/null || docker image inspect -f '{{.Id}}' "${IMAGE_NAME}:latest" 2>/dev/null || true)"

    log_info "Step 1/5: Stop and remove current container"
    remove_existing_container

    log_info "Step 2/5: Build new image"
    cd "${project_dir}"
    DOCKER_BUILDKIT=1 docker build \
        -f "${project_dir}/Dockerfile" \
        -t "${IMAGE_NAME}:${IMAGE_VERSION}" \
        -t "${IMAGE_NAME}:latest" \
        "${project_dir}"
    log_success "Built image ${IMAGE_NAME}:${IMAGE_VERSION}"

    log_info "Step 3/5: Start new container"
    cd "${compose_dir}"
    env IMAGE_VERSION="${IMAGE_VERSION}" "${COMPOSE_CMD[@]}" -f "${COMPOSE_FILE}" up -d "${SERVICE_NAME}"

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

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
