# -*- coding: utf-8 -*-
"""
自动更新检查模块 - 从GitHub检查新版本
"""

import requests
import re
from packaging import version as pkg_version
from typing import Optional, Dict, Tuple
from locales import t

def parse_version(ver_str: str) -> Optional[pkg_version.Version]:
    """解析版本号字符串"""
    try:
        # 移除前导的 'v' 字符
        ver_str = ver_str.lstrip('v')
        # 尝试解析为标准版本号
        return pkg_version.parse(ver_str)
    except Exception:
        return None

def get_latest_release(repo: str, timeout: int = 10) -> Optional[Dict]:
    """
    获取GitHub仓库的最新发布版本
    
    Args:
        repo: GitHub仓库名，格式: owner/repo
        timeout: 请求超时时间(秒)
    
    Returns:
        包含版本信息的字典，如果失败返回None
    """
    try:
        url = f'https://api.github.com/repos/{repo}/releases/latest'
        headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'Mozilla/5.0'
        }
        
        response = requests.get(url, headers=headers, timeout=timeout)
        
        if response.status_code == 200:
            data = response.json()
            return {
                'tag_name': data.get('tag_name', ''),
                'name': data.get('name', ''),
                'body': data.get('body', ''),
                'html_url': data.get('html_url', ''),
                'published_at': data.get('published_at', ''),
                'assets': data.get('assets', [])
            }
        return None
    except Exception:
        return None

def check_update(current_version: str, repo: str) -> Optional[Tuple[bool, Dict]]:
    """
    检查是否有新版本可用
    
    Args:
        current_version: 当前版本号
        repo: GitHub仓库名
    
    Returns:
        (是否有新版本, 最新版本信息) 或 None(检查失败)
    """
    try:
        latest = get_latest_release(repo)
        if not latest:
            return None
        
        latest_version_str = latest.get('tag_name', '')
        if not latest_version_str:
            return None
        
        # 解析版本号
        current_ver = parse_version(current_version)
        latest_ver = parse_version(latest_version_str)
        
        if not current_ver or not latest_ver:
            return None
        
        # 比较版本号
        has_update = latest_ver > current_ver
        
        return (has_update, latest)
    
    except Exception:
        return None

def parse_release_assets(latest_info: Dict, platform: str = 'windows') -> list:
    """
    解析 release 中的 assets,分类并返回适合当前平台的版本
    
    Args:
        latest_info: 最新版本信息
        platform: 目标平台 ('windows', 'linux', 'macos')
    
    Returns:
        分类后的 assets 列表,每项包含:
        - name: 文件名
        - type: 版本类型 ('standard', 'standalone', 'debug')
        - size: 文件大小(字节)
        - size_mb: 文件大小(MB,格式化)
        - download_url: 下载链接
        - description: 版本描述
        - recommended: 是否推荐
    """
    assets = latest_info.get('assets', [])
    parsed_assets = []
    
    print(f'[DEBUG] parse_release_assets: platform={platform}, total_assets={len(assets)}')
    
    for asset in assets:
        name = asset.get('name', '')
        size = asset.get('size', 0)
        download_url = asset.get('browser_download_url', '')
        
        print(f'[DEBUG] Checking asset: name={name}, size={size}')
        
        # 只处理指定平台的文件
        if platform == 'windows':
            if not name.endswith('.exe'):
                print(f'[DEBUG]   -> Skipped: not .exe')
                continue
            
            # 分类 Windows 版本
            if 'Standalone' in name:
                asset_type = 'standalone'
                description = t("up_desc_standalone")
                recommended = True
                print(f'[DEBUG]   -> Matched: standalone')
            elif 'debug' in name.lower():
                asset_type = 'debug'
                description = t("up_desc_debug")
                recommended = False
                print(f'[DEBUG]   -> Matched: debug')
            else:
                asset_type = 'standard'
                description = t("up_desc_standard")
                recommended = False
                print(f'[DEBUG]   -> Matched: standard')
        
        elif platform == 'linux':
            if not ('linux' in name.lower() and not name.endswith('.exe')):
                continue
            asset_type = 'debug' if 'debug' in name.lower() else 'release'
            description = t("up_desc_linux_debug") if asset_type == 'debug' else t("up_desc_linux_release")
            recommended = asset_type == 'release'
        
        elif platform == 'macos':
            if not ('macos' in name.lower() and not name.endswith('.exe')):
                continue
            asset_type = 'debug' if 'debug' in name.lower() else 'release'
            description = t("up_desc_linux_debug") if asset_type == 'debug' else t("up_desc_linux_release")
            recommended = asset_type == 'release'
        
        else:
            continue
        
        parsed_assets.append({
            'name': name,
            'type': asset_type,
            'size': size,
            'size_mb': f'{size / 1024 / 1024:.1f}',
            'download_url': download_url,
            'description': description,
            'recommended': recommended
        })
    
    # 排序: 推荐的排在前面,然后按类型排序
    parsed_assets.sort(key=lambda x: (not x['recommended'], x['type']))
    
    print(f'[DEBUG] Final parsed_assets count: {len(parsed_assets)}')
    for i, a in enumerate(parsed_assets):
        print(f'[DEBUG]   [{i}] {a["name"]} -> type={a["type"]}, recommended={a["recommended"]}')
    
    return parsed_assets

def format_update_message(latest_info: Dict) -> str:
    """
    格式化更新提示消息
    
    Args:
        latest_info: 最新版本信息
    
    Returns:
        格式化的消息字符串
    """
    version = latest_info.get('tag_name', '未知版本')
    name = latest_info.get('name', '')
    body = latest_info.get('body', '')
    url = latest_info.get('html_url', '')
    
    # 提取body中的关键信息(前300字符)
    if body:
        # 移除markdown格式
        body = re.sub(r'[#*`]', '', body)
        body = body.strip()[:300]
        if len(latest_info.get('body', '')) > 300:
            body += '...'
    
    message = t("up_auto_update_msg", version, name, body if body else '(无更新说明)', url)
    
    return message

def check_and_notify(current_version: str, repo: str, silent: bool = False) -> Optional[Dict]:
    """
    检查更新并返回结果(用于程序调用)
    
    Args:
        current_version: 当前版本号
        repo: GitHub仓库名
        silent: 是否静默模式(不打印)
    
    Returns:
        更新信息字典或None
    """
    result = check_update(current_version, repo)
    
    if result is None:
        if not silent:
            print(t("up_check_fail"))
        return None
    
    has_update, latest_info = result
    
    if has_update:
        message = format_update_message(latest_info)
        if not silent:
            print('\n' + '=' * 60)
            print(message)
            print('=' * 60 + '\n')
        
        return {
            'has_update': True,
            'current_version': current_version,
            'latest_version': latest_info.get('tag_name', ''),
            'message': message,
            'url': latest_info.get('html_url', ''),
            'release_info': latest_info
        }
    else:
        if not silent:
            print(t("up_latest", current_version))
        return {
            'has_update': False,
            'current_version': current_version,
            'latest_version': latest_info.get('tag_name', ''),
            'message': '',
            'url': '',
            'release_info': latest_info
        }

def apply_windows_update(new_exe_path: str, current_exe_path: str = None) -> bool:
    """
    在 Windows 上应用更新：创建批处理脚本来替换当前程序并重启
    
    Args:
        new_exe_path: 新版本 exe 文件路径
        current_exe_path: 当前程序路径，如果为 None 则自动检测
    
    Returns:
        是否成功启动更新过程
    """
    import sys
    import os
    import subprocess
    import tempfile
    
    print(f'[DEBUG] apply_windows_update called')
    print(f'[DEBUG]   new_exe_path: {new_exe_path}')
    print(f'[DEBUG]   current_exe_path: {current_exe_path}')
    print(f'[DEBUG]   sys.frozen: {getattr(sys, "frozen", False)}')
    print(f'[DEBUG]   sys.executable: {sys.executable}')
    
    # 检查是否为打包后的 exe
    if not getattr(sys, 'frozen', False):
        print('[DEBUG] Not a frozen executable, cannot auto-update')
        print(t("up_not_frozen"))
        return False
    
    # 获取当前程序路径
    if current_exe_path is None:
        current_exe_path = sys.executable
    print(f'[DEBUG] Final current_exe_path: {current_exe_path}')
    
    # 检查新版本文件是否存在
    if not os.path.exists(new_exe_path):
        print(f'[DEBUG] New file does not exist!')
        print(t("up_new_missing", new_exe_path))
        return False
    
    print(f'[DEBUG] New file size: {os.path.getsize(new_exe_path)} bytes')
    
    # 获取当前进程 PID
    pid = os.getpid()
    
    # 获取可执行文件名
    exe_name = os.path.basename(current_exe_path)

    # 获取当前程序所在目录
    exe_dir = os.path.dirname(current_exe_path)
    
    # 创建更新批处理脚本（直接嵌入 PID 避免参数传递问题）
    # 注意：使用 chcp 65001 解决路径编码问题
    bat_content = f'''@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ====================================
echo Fanqie Novel Downloader - Auto Update
echo ====================================
echo.
echo Waiting for application to exit (PID: {pid})...

:: Wait for main process to exit (check every second, max 30 seconds)
set /a count=0
:waitloop
tasklist /FI "PID eq {pid}" 2>nul | find "{pid}" >nul
if errorlevel 1 goto :process_exited
set /a count+=1
if !count! geq 30 goto :force_kill
ping -n 2 127.0.0.1 >nul
goto :waitloop

:force_kill
echo Process did not exit gracefully, forcing termination...
taskkill /F /PID {pid} >nul 2>&1
ping -n 2 127.0.0.1 >nul

:process_exited
echo Application exited.
echo.

:: Also kill any remaining instances by name
taskkill /F /IM "{exe_name}" >nul 2>&1

:: Wait for file handles to be released
echo Waiting for file locks to release...
ping -n 3 127.0.0.1 >nul

echo Starting update process...
echo.

:: Strategy: Move-and-Replace with retry
:: Windows allows renaming running/locked executables, but not overwriting them.

set /a retry=0
:move_retry
echo Attempt to backup old version...
del /F /Q "{current_exe_path}.old" >nul 2>&1
if exist "{current_exe_path}" (
    move /Y "{current_exe_path}" "{current_exe_path}.old"
    if errorlevel 1 (
        set /a retry+=1
        if !retry! lss 5 (
            echo Retry !retry!/5 - file still locked, waiting...
            taskkill /F /IM "{exe_name}" >nul 2>&1
            ping -n 3 127.0.0.1 >nul
            goto :move_retry
        )
        echo ERROR: Cannot backup old version after 5 attempts.
        echo Please close all instances and try again.
        pause
        exit /b 1
    )
)
echo Old version backed up successfully.

:: Copy new exe to original location
echo Installing new version...
copy /Y "{new_exe_path}" "{current_exe_path}"
if errorlevel 1 (
    echo ERROR: Copy failed! Restoring old version...
    if exist "{current_exe_path}.old" (
        move /Y "{current_exe_path}.old" "{current_exe_path}"
    )
    pause
    exit /b 1
)
echo New version installed successfully.

:: Cleanup
echo Cleaning up temporary files...
del /F /Q "{new_exe_path}" >nul 2>&1
del /F /Q "{current_exe_path}.old" >nul 2>&1

echo.
echo ====================================
echo Update completed successfully!
echo ====================================
echo.
echo Starting new version in 3 seconds...
ping -n 4 127.0.0.1 >nul

echo Starting application...
echo Target: "{current_exe_path}"

:: Directly start the exe. Quotes are important.
start "" "{current_exe_path}"

echo New version launch attempt complete.
ping -n 2 127.0.0.1 >nul

:: Delete self (delayed)
(goto) 2>nul & del /F /Q "%~f0"
exit /b 0
'''
    
    # 写入批处理文件
    try:
        bat_path = os.path.join(tempfile.gettempdir(), 'fanqie_update.bat')
        print(f'[DEBUG] Writing update script to: {bat_path}')
        
        # 使用 utf-8 编码写入，配合 chcp 65001
        with open(bat_path, 'w', encoding='utf-8') as f:
            f.write(bat_content)
        
        print(f'[DEBUG] Update script written successfully')
        
        # 启动批处理脚本（使用新的控制台窗口）
        # 使用 CREATE_NEW_CONSOLE 标志确保脚本在独立窗口运行
        # 不使用 shell=True 和嵌套的 start 命令，更可靠
        CREATE_NEW_CONSOLE = 0x00000010
        DETACHED_PROCESS = 0x00000008
        
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 1  # SW_SHOWNORMAL
        
        process = subprocess.Popen(
            ['cmd.exe', '/c', bat_path],
            creationflags=CREATE_NEW_CONSOLE,
            startupinfo=startupinfo,
            cwd=tempfile.gettempdir(),
            close_fds=True
        )
        
        print(f'[DEBUG] Update script started with PID: {process.pid}')
        print(t("up_script_started"))
        return True
        
    except Exception as e:
        import traceback
        print(f'[DEBUG] Failed to create/start update script:')
        traceback.print_exc()
        print(t("up_create_script_fail", e))
        return False


def apply_unix_update(new_binary_path: str, current_binary_path: str = None) -> bool:
    """
    在 Linux/macOS 上应用更新：创建 shell 脚本来替换当前程序并重启
    
    Args:
        new_binary_path: 新版本二进制文件路径
        current_binary_path: 当前程序路径，如果为 None 则自动检测
    
    Returns:
        是否成功启动更新过程
    """
    import sys
    import os
    import subprocess
    import tempfile
    import stat
    
    # 检查是否为打包后的程序
    if not getattr(sys, 'frozen', False):
        print(t("up_not_frozen_linux"))
        return False
    
    # 获取当前程序路径
    if current_binary_path is None:
        current_binary_path = sys.executable
    
    # 检查新版本文件是否存在
    if not os.path.exists(new_binary_path):
        print(t("up_new_missing_linux", new_binary_path))
        return False
    
    # 获取当前进程 PID
    pid = os.getpid()
    
    # 创建更新 shell 脚本
    shell_content = f'''#!/bin/bash
echo "===================================="
echo "番茄小说下载器 - 自动更新"
echo "===================================="
echo ""
echo "正在等待程序退出..."

# 等待原进程退出
while kill -0 {pid} 2>/dev/null; do
    sleep 1
done

echo "程序已退出，开始更新..."
echo ""

# 备份旧版本
BACKUP_PATH="{current_binary_path}.backup"
if [ -f "{current_binary_path}" ]; then
    echo "备份旧版本..."
    cp "{current_binary_path}" "$BACKUP_PATH"
    if [ $? -ne 0 ]; then
        echo "备份失败，更新终止"
        read -p "按回车键退出..."
        exit 1
    fi
fi

# 替换新版本
echo "安装新版本..."
cp "{new_binary_path}" "{current_binary_path}"
if [ $? -ne 0 ]; then
    echo "更新失败，正在恢复旧版本..."
    cp "$BACKUP_PATH" "{current_binary_path}"
    read -p "按回车键退出..."
    exit 1
fi

# 设置执行权限
chmod +x "{current_binary_path}"

# 清理
echo "清理临时文件..."
rm -f "{new_binary_path}" 2>/dev/null
rm -f "$BACKUP_PATH" 2>/dev/null

echo ""
echo "✓ 更新完成！正在启动新版本..."
echo ""
sleep 2

# 启动新版本
nohup "{current_binary_path}" >/dev/null 2>&1 &

# 删除自身
rm -f "$0" 2>/dev/null
exit 0
'''
    
    # 写入 shell 脚本
    try:
        script_path = os.path.join(tempfile.gettempdir(), 'fanqie_update.sh')
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(shell_content)
        
        # 设置执行权限
        os.chmod(script_path, os.stat(script_path).st_mode | stat.S_IEXEC)
        
        # 启动脚本（在新终端中运行）
        if sys.platform == 'darwin':
            # macOS: 使用 osascript 打开终端
            subprocess.Popen([
                'osascript', '-e',
                f'tell application "Terminal" to do script "{script_path}"'
            ])
        else:
            # Linux: 尝试各种终端模拟器
            terminals = [
                ['gnome-terminal', '--', 'bash', script_path],
                ['konsole', '-e', 'bash', script_path],
                ['xfce4-terminal', '-e', f'bash {script_path}'],
                ['xterm', '-e', 'bash', script_path],
                ['termux-open', script_path],  # Termux
            ]
            
            launched = False
            for term_cmd in terminals:
                try:
                    subprocess.Popen(term_cmd, start_new_session=True)
                    launched = True
                    break
                except (FileNotFoundError, OSError):
                    continue
            
            if not launched:
                # 如果没有找到终端，直接后台运行
                subprocess.Popen(['bash', script_path], start_new_session=True)
        
        print(t("up_script_started"))
        return True
        
    except Exception as e:
        print(t("up_create_script_fail", e))
        return False


def apply_update(new_file_path: str, current_path: str = None) -> bool:
    """
    应用更新 - 自动检测平台并调用对应的更新函数
    
    Args:
        new_file_path: 新版本文件路径
        current_path: 当前程序路径，如果为 None 则自动检测
    
    Returns:
        是否成功启动更新过程
    """
    import sys
    
    if sys.platform == 'win32':
        return apply_windows_update(new_file_path, current_path)
    elif sys.platform in ('linux', 'darwin'):
        return apply_unix_update(new_file_path, current_path)
    else:
        print(t("up_platform_unsupported", sys.platform))
        return False


def get_update_exe_path(save_path: str, filename: str) -> str:
    """获取下载的更新文件完整路径"""
    import os
    return os.path.join(save_path, filename)


def can_auto_update() -> bool:
    """检查当前环境是否支持自动更新"""
    import sys
    # Windows、Linux、macOS 打包后的程序都支持自动更新
    supported_platforms = ('win32', 'linux', 'darwin')
    return sys.platform in supported_platforms and getattr(sys, 'frozen', False)


if __name__ == '__main__':
    # 测试代码
    from config import __version__, __github_repo__
    
    print(f'当前版本: {__version__}')
    print(f'检查仓库: {__github_repo__}')
    print(f'支持自动更新: {can_auto_update()}')
    print('-' * 60)
    
    check_and_notify(__version__, __github_repo__)
