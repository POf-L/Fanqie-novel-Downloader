#!/usr/bin/env bash
# -*- coding: utf-8 -*-
# TomatoNovelDownloader Termux 启动入口（可直接作为发布资产执行）

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

APP_HOME="${HOME}/.fanqienoveldownloader"
LAUNCHER_PATH="${APP_HOME}/launcher.py"
REPO="${FANQIE_GITHUB_REPO:-POf-L/Fanqie-novel-Downloader}"
LAUNCHER_BRANCH="${FANQIE_LAUNCHER_BRANCH:-}"

CHECK_ONLY=false
FORCE_LAUNCHER_UPDATE=false
APP_ARGS=()

show_help() {
    echo "TomatoNovelDownloader Termux 启动脚本"
    echo ""
    echo "用法: $0 [选项] [CLI 参数]"
    echo ""
    echo "选项:"
    echo "  --help, -h             显示此帮助信息"
    echo "  --check-only           仅检查环境与依赖"
    echo "  --update-launcher      强制更新 launcher.py"
    echo ""
    echo "示例:"
    echo "  $0 --help"
    echo "  $0 --check-only"
    echo "  $0"
    echo "  $0 --update-launcher"
    echo ""
    echo "说明:"
    echo "  - 此文件是 Termux 的官方入口，不再依赖旧 ELF 可执行文件。"
    echo "  - 若你之前下载的是旧版二进制，出现 'cannot execute: required file not found'，"
    echo "    请重新下载当前版本的此脚本并执行。"
}

check_termux() {
    local prefix="${PREFIX:-}"
    if [[ "${prefix}" != *"com.termux"* ]] && [ ! -d "/data/data/com.termux" ]; then
        print_error "此脚本只能在 Termux 环境中运行"
        exit 1
    fi
    print_success "Termux 环境检查通过"
}

check_architecture() {
    local arch
    arch="$(uname -m)"
    case "${arch}" in
        aarch64)
            print_success "ARM64 架构检查通过"
            ;;
        arm*|armv7l)
            print_warning "检测到 ARM32 架构，推荐使用 ARM64 设备"
            ;;
        *)
            print_warning "当前架构为 ${arch}，脚本会继续尝试运行"
            ;;
    esac
}

ensure_python() {
    if ! command -v python >/dev/null 2>&1; then
        print_warning "未检测到 python，正在通过 pkg 安装..."
        pkg update -y
        pkg install -y python
    fi
}

ensure_requests() {
    if python -c "import requests" >/dev/null 2>&1; then
        print_success "Python requests 依赖检查通过"
        return
    fi

    print_warning "未检测到 requests，正在安装..."
    python -m pip install --upgrade pip
    python -m pip install requests
    print_success "requests 安装完成"
}

download_launcher() {
    mkdir -p "${APP_HOME}"

    if [ "${FORCE_LAUNCHER_UPDATE}" = true ] || [ ! -f "${LAUNCHER_PATH}" ]; then
        local urls=()
        if [ -n "${LAUNCHER_BRANCH}" ]; then
            urls+=("https://raw.githubusercontent.com/${REPO}/${LAUNCHER_BRANCH}/launcher.py")
        else
            urls+=(
                "https://raw.githubusercontent.com/${REPO}/main/launcher.py"
                "https://raw.githubusercontent.com/${REPO}/master/launcher.py"
            )
        fi

        local ok=0
        local url

        if ! command -v curl >/dev/null 2>&1 && ! command -v wget >/dev/null 2>&1; then
            print_warning "未检测到 curl/wget，正在安装 curl..."
            pkg update -y
            pkg install -y curl
        fi

        for url in "${urls[@]}"; do
            print_info "尝试下载 launcher.py: ${url}"
            if command -v curl >/dev/null 2>&1; then
                if curl -fsSL "${url}" -o "${LAUNCHER_PATH}"; then
                    ok=1
                    break
                fi
            elif command -v wget >/dev/null 2>&1; then
                if wget -qO "${LAUNCHER_PATH}" "${url}"; then
                    ok=1
                    break
                fi
            fi
        done

        if [ "${ok}" -ne 1 ]; then
            print_error "下载 launcher.py 失败，请检查网络或仓库设置"
            print_info "当前仓库: ${REPO}"
            if [ -n "${LAUNCHER_BRANCH}" ]; then
                print_info "当前分支: ${LAUNCHER_BRANCH}"
            fi
            exit 1
        fi
    fi

    if [ ! -s "${LAUNCHER_PATH}" ]; then
        print_error "launcher.py 下载失败或文件为空"
        exit 1
    fi

    print_success "launcher.py 已就绪: ${LAUNCHER_PATH}"
}

run_launcher() {
    print_info "启动 TomatoNovelDownloader..."
    export FANQIE_GITHUB_REPO="${REPO}"
    python "${LAUNCHER_PATH}" "${APP_ARGS[@]}"
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --help|-h)
                show_help
                exit 0
                ;;
            --check-only)
                CHECK_ONLY=true
                shift
                ;;
            --update-launcher)
                FORCE_LAUNCHER_UPDATE=true
                shift
                ;;
            *)
                APP_ARGS+=("$1")
                shift
                ;;
        esac
    done
}

main() {
    parse_args "$@"

    print_info "TomatoNovelDownloader Termux 启动脚本"
    print_info "版本: 2.0.0"
    echo ""

    check_termux
    check_architecture
    ensure_python
    ensure_requests
    download_launcher

    if [ "${CHECK_ONLY}" = true ]; then
        print_success "环境检查完成"
        exit 0
    fi

    run_launcher
}

main "$@"
