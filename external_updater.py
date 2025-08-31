#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
外部更新脚本 - 独立处理所有更新操作
当主程序退出后，由这个脚本接管所有更新流程
"""

import sys
import os
import time
import tempfile
import requests
import json
import platform
import subprocess
import shutil
from pathlib import Path

# 添加项目路径以导入内部模块
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

try:
    from updater import AutoUpdater
    from version import __github_repo__, __version__
    from config import CONFIG
except ImportError as e:
    print(f"[Updater] 导入失败: {e}")
    sys.exit(1)


def log_message(message, level="INFO"):
    """记录日志消息"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")


def get_current_exe_path():
    """获取当前可执行文件路径"""
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包的程序
        return sys.executable
    else:
        # 源码运行
        return sys.argv[0]


def backup_current_exe():
    """备份当前可执行文件"""
    current_exe = get_current_exe_path()
    backup_path = current_exe + ".backup"

    if os.path.exists(current_exe):
        log_message(f"创建备份: {backup_path}")
        shutil.copy2(current_exe, backup_path)
        return backup_path
    return None


def restore_backup(backup_path):
    """从备份恢复文件"""
    if backup_path and os.path.exists(backup_path):
        current_exe = get_current_exe_path()
        log_message(f"从备份恢复: {backup_path}")
        shutil.copy2(backup_path, current_exe)
        return True
    return False


def cleanup_backup(backup_path):
    """清理备份文件"""
    if backup_path and os.path.exists(backup_path):
        try:
            os.remove(backup_path)
            log_message(f"清理备份文件: {backup_path}")
        except Exception as e:
            log_message(f"清理备份文件失败: {e}", "WARNING")


def download_update_file(update_info):
    """下载更新文件"""
    try:
        log_message("开始下载更新文件...")

        # 创建更新器实例
        updater = AutoUpdater(__github_repo__, __version__)

        # 选择合适的下载资源
        asset = updater._get_platform_asset(update_info['assets'])
        if not asset:
            log_message("没有找到适合当前平台的更新文件", "ERROR")
            return None

        log_message(f"选择下载文件: {asset['name']}")

        # 创建临时文件
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, asset['name'])

        # 下载文件
        headers = {
            'User-Agent': 'Tomato-Novel-Downloader',
            'Accept': 'application/octet-stream'
        }
        token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
        if token:
            headers['Authorization'] = f'Bearer {token}'
        response = requests.get(asset['download_url'], headers=headers, stream=True, timeout=60)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        downloaded_size = 0

        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded_size += len(chunk)

                    # 显示下载进度
                    if total_size > 0:
                        percent = int(downloaded_size * 100 / total_size)
                        print(f"\r下载进度: {percent}% ({downloaded_size // 1024}KB / {total_size // 1024}KB)", end='', flush=True)

        print()  # 换行
        log_message(f"下载完成: {file_path}")
        return file_path

    except Exception as e:
        log_message(f"下载失败: {e}", "ERROR")
        return None


def install_update_windows(update_file):
    """Windows 平台安装更新"""
    try:
        current_exe = get_current_exe_path()
        log_message("开始安装更新 (Windows)...")

        # 备份当前文件
        backup_path = backup_current_exe()
        if not backup_path:
            log_message("创建备份失败", "ERROR")
            return False

        # 替换文件
        log_message(f"替换文件: {current_exe}")
        shutil.copy2(update_file, current_exe)

        log_message("更新安装成功")
        return True

    except Exception as e:
        log_message(f"安装失败: {e}", "ERROR")
        # 尝试恢复备份
        if 'backup_path' in locals() and backup_path:
            restore_backup(backup_path)
        return False


def install_update_unix(update_file):
    """Unix 平台安装更新"""
    try:
        current_exe = get_current_exe_path()
        current_dir = os.path.dirname(current_exe)
        log_message("开始安装更新 (Unix)...")

        # 如果是压缩包，解压到临时目录
        if update_file.endswith('.zip'):
            import zipfile
            temp_extract_dir = os.path.join(tempfile.gettempdir(), 'update_extract')
            os.makedirs(temp_extract_dir, exist_ok=True)

            log_message("解压更新文件...")
            with zipfile.ZipFile(update_file, 'r') as zip_ref:
                zip_ref.extractall(temp_extract_dir)
        elif update_file.endswith('.tar.gz') or update_file.endswith('.tgz'):
            import tarfile
            temp_extract_dir = os.path.join(tempfile.gettempdir(), 'update_extract')
            os.makedirs(temp_extract_dir, exist_ok=True)
            log_message("解压tarball更新文件...")
            with tarfile.open(update_file, 'r:gz') as tar:
                tar.extractall(temp_extract_dir)
        elif update_file.lower().endswith('.appimage'):
            # AppImage 单文件直接覆盖
            temp_extract_dir = None
        else:
            temp_extract_dir = None

        update_exe = update_file
        if temp_extract_dir:
            # 查找主要可执行文件（使用当前可执行文件名匹配）
            exe_name = os.path.basename(current_exe)
            candidates = []
            for root, dirs, files in os.walk(temp_extract_dir):
                for file in files:
                    if file == exe_name or exe_name in file:
                        candidates.append(os.path.join(root, file))
            if not candidates:
                log_message("未找到匹配的可执行文件", "ERROR")
                return False
            update_exe = candidates[0]

        # 备份当前文件
        backup_path = backup_current_exe()
        if not backup_path:
            log_message("创建备份失败", "ERROR")
            return False

        # 替换文件
        log_message(f"替换文件: {current_exe}")
        shutil.copy2(update_exe, current_exe)

        # 设置可执行权限
        os.chmod(current_exe, 0o755)

        log_message("更新安装成功")
        return True

    except Exception as e:
        log_message(f"安装失败: {e}", "ERROR")
        # 尝试恢复备份
        if 'backup_path' in locals() and backup_path:
            restore_backup(backup_path)
        return False


def restart_application():
    """重启应用程序"""
    try:
        current_exe = get_current_exe_path()
        log_message("重启应用程序...")

        if platform.system() == 'Windows':
            subprocess.Popen([current_exe], creationflags=subprocess.DETACHED_PROCESS)
        else:
            subprocess.Popen([current_exe], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        log_message("应用程序已重启")
        return True

    except Exception as e:
        log_message(f"重启失败: {e}", "ERROR")
        return False


def main():
    """主函数"""
    log_message("=== 外部更新脚本启动 ===")

    # 检查命令行参数
    if len(sys.argv) < 2:
        log_message("错误：缺少更新信息参数", "ERROR")
        sys.exit(1)

    try:
        # 解析更新信息
        update_info_json = sys.argv[1]
        update_info = json.loads(update_info_json)

        log_message(f"准备更新到版本: {update_info.get('version', 'unknown')}")

        # 步骤1: 下载更新文件
        update_file = download_update_file(update_info)
        if not update_file:
            log_message("下载失败，退出更新", "ERROR")
            sys.exit(1)

        # 步骤2: 安装更新
        if platform.system() == 'Windows':
            success = install_update_windows(update_file)
        else:
            success = install_update_unix(update_file)

        if not success:
            log_message("安装失败，退出更新", "ERROR")
            sys.exit(1)

        # 步骤3: 清理临时文件
        try:
            os.remove(update_file)
            log_message("清理临时文件完成")
        except Exception as e:
            log_message(f"清理临时文件失败: {e}", "WARNING")

        # 步骤4: 重启应用程序
        log_message("更新完成，准备重启应用程序...")
        time.sleep(1)  # 短暂延迟

        if not restart_application():
            log_message("重启失败，请手动重启应用程序", "WARNING")

        log_message("=== 更新脚本执行完成 ===")

    except json.JSONDecodeError as e:
        log_message(f"解析更新信息失败: {e}", "ERROR")
        sys.exit(1)
    except Exception as e:
        log_message(f"更新过程中发生错误: {e}", "ERROR")
        sys.exit(1)


if __name__ == "__main__":
    main()
