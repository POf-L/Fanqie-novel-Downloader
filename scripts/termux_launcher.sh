#!/bin/bash
# -*- coding: utf-8 -*-
# TomatoNovelDownloader Termux 启动脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
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

# 检查 Termux 环境
check_termux() {
    if [ ! -d "/data/data/com.termux" ]; then
        print_error "此脚本只能在 Termux 环境中运行"
        exit 1
    fi
    print_success "Termux 环境检查通过"
}

# 检查架构
check_architecture() {
    ARCH=$(uname -m)
    case $ARCH in
        aarch64)
            print_success "ARM64 架构检查通过"
            ;;
        armv7l|arm)
            print_warning "检测到 ARM32 架构，可能需要 ARM32 版本"
            ;;
        *)
            print_error "不支持的架构: $ARCH"
            exit 1
            ;;
    esac
}

# 检查可执行文件
check_executable() {
    local exe_name="$1"
    
    if [ ! -f "$exe_name" ]; then
        print_error "找不到可执行文件: $exe_name"
        print_info "请确保 $exe_name 在当前目录中"
        exit 1
    fi
    
    # 检查文件权限
    if [ ! -x "$exe_name" ]; then
        print_warning "可执行文件缺少执行权限，正在修复..."
        chmod +x "$exe_name"
        if [ $? -eq 0 ]; then
            print_success "执行权限修复成功"
        else
            print_error "执行权限修复失败"
            exit 1
        fi
    fi
    
    # 检查文件格式
    FILE_TYPE=$(file "$exe_name")
    if echo "$FILE_TYPE" | grep -q "ELF 64-bit.*ARM"; then
        print_success "ARM64 可执行文件格式正确"
    elif echo "$FILE_TYPE" | grep -q "ELF 32-bit.*ARM"; then
        print_success "ARM32 可执行文件格式正确"
    else
        print_error "无效的可执行文件格式: $FILE_TYPE"
        exit 1
    fi
}

# 检查动态链接依赖
check_dependencies() {
    local exe_name="$1"
    
    print_info "检查动态链接依赖..."
    
    # 尝试使用 ldd 检查依赖
    if command -v ldd >/dev/null 2>&1; then
        DEPS=$(ldd "$exe_name" 2>/dev/null || echo "ldd failed")
        if echo "$DEPS" | grep -q "not found"; then
            print_warning "发现缺失的动态链接库:"
            echo "$DEPS" | grep "not found" | sed 's/^/  /'
            print_info "尝试安装缺失的依赖..."
            
            # 尝试安装常见依赖
            pkg update -y
            pkg install -y libffi openssl libjpeg-turbo libwebp libxml2 libxslt
            
            # 再次检查
            DEPS=$(ldd "$exe_name" 2>/dev/null || echo "ldd failed")
            if echo "$DEPS" | grep -q "not found"; then
                print_warning "仍有缺失的依赖，但程序可能仍能运行"
            else
                print_success "所有依赖已满足"
            fi
        else
            print_success "动态链接依赖检查通过"
        fi
    else
        print_warning "ldd 命令不可用，跳过依赖检查"
    fi
}

# 运行程序
run_program() {
    local exe_name="$1"
    shift
    local args="$@"
    
    print_info "启动 TomatoNovelDownloader..."
    print_info "执行命令: ./$exe_name $args"
    echo ""
    
    # 设置 LD_LIBRARY_PATH 以确保能找到库文件
    export LD_LIBRARY_PATH="/data/data/com.termux/files/usr/lib:$LD_LIBRARY_PATH"
    
    # 运行程序
    "./$exe_name" "$args"
}

# 显示帮助信息
show_help() {
    echo "TomatoNovelDownloader Termux 启动脚本"
    echo ""
    echo "用法: $0 [可执行文件名] [选项]"
    echo ""
    echo "可执行文件名:"
    echo "  TomatoNovelDownloader-termux-arm64    (默认)"
    echo ""
    echo "选项:"
    echo "  --help, -h     显示此帮助信息"
    echo "  --version      显示版本信息"
    echo "  --check-only   仅检查环境，不运行程序"
    echo ""
    echo "示例:"
    echo "  $0                                    # 使用默认文件名运行"
    echo "  $0 --help                            # 显示帮助"
    echo "  $0 --version                         # 显示版本"
    echo "  $0 --check-only                      # 仅检查环境"
    echo "  $0 TomatoNovelDownloader-termux --help # 运行程序并显示帮助"
}

# 主函数
main() {
    local exe_name="TomatoNovelDownloader-termux-arm64"
    local check_only=false
    local show_version=false
    
    # 解析命令行参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            --help|-h)
                show_help
                exit 0
                ;;
            --version)
                show_version=true
                shift
                ;;
            --check-only)
                check_only=true
                shift
                ;;
            *.termux*)
                exe_name="$1"
                shift
                ;;
            *)
                # 其他参数传递给程序
                break
                ;;
        esac
    done
    
    print_info "TomatoNovelDownloader Termux 启动脚本"
    print_info "版本: 1.0.0"
    echo ""
    
    # 环境检查
    check_termux
    check_architecture
    check_executable "$exe_name"
    check_dependencies "$exe_name"
    
    if [ "$check_only" = true ]; then
        print_success "环境检查完成，所有检查通过"
        exit 0
    fi
    
    if [ "$show_version" = true ]; then
        print_info "正在显示程序版本..."
        run_program "$exe_name" --version
        exit 0
    fi
    
    # 运行程序
    run_program "$exe_name" "$@"
}

# 运行主函数
main "$@"
