# -*- coding: utf-8 -*-

"""
自动更新应用模块 - 平台相关替换/重启逻辑

从 utils/updater.py 拆分，避免单文件过长
"""

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
        print("自动更新仅支持打包后的程序")
        return False
    
    # 获取当前程序路径
    if current_exe_path is None:
        current_exe_path = sys.executable
    print(f'[DEBUG] Final current_exe_path: {current_exe_path}')
    
    # 检查新版本文件是否存在
    if not os.path.exists(new_exe_path):
        print(f'[DEBUG] New file does not exist!')
        print(f"新版本文件不存在: {new_exe_path}")
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
echo Working directory: "{exe_dir}"

:: Change to the application directory first
cd /d "{exe_dir}"

:: Verify the new exe exists before starting
if not exist "{current_exe_path}" (
    echo ERROR: New executable not found at "{current_exe_path}"
    pause
    exit /b 1
)

:: Start the exe - use pushd/popd to handle paths with spaces
pushd "{exe_dir}"
echo Current directory: %CD%
echo Launching executable...

:: Method: Use explorer.exe to launch (most reliable for GUI apps)
explorer.exe "{current_exe_path}"

:: Wait a moment to let the process start
ping -n 4 127.0.0.1 >nul

:: Verify the process is running
tasklist /FI "IMAGENAME eq {exe_name}" 2>nul | find /I "{exe_name}" >nul
if errorlevel 1 (
    echo WARNING: Process may not have started via explorer. Trying cmd...
    cmd /c start "" "{current_exe_path}"
    ping -n 3 127.0.0.1 >nul
)

popd

echo.
echo New version launch attempt complete.
echo This window will close in 5 seconds...
ping -n 6 127.0.0.1 >nul

:: Delete self (delayed)
(goto) 2>nul & del /F /Q "%~f0"
exit /b 0
'''
    
    # 写入批处理文件
    try:
        cache_dir = _get_cache_dir()
        bat_path = os.path.join(cache_dir, 'fanqie_update.bat')
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
            cwd=cache_dir,
            close_fds=True
        )
        
        print(f'[DEBUG] Update script started with PID: {process.pid}')
        print("更新脚本已启动，程序即将退出...")
        return True
        
    except Exception as e:
        import traceback
        print(f'[DEBUG] Failed to create/start update script:')
        traceback.print_exc()
        print(f"创建更新脚本失败: {e}")
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
        print("自动更新仅支持打包后的程序")
        return False
    
    # 获取当前程序路径
    if current_binary_path is None:
        current_binary_path = sys.executable
    
    # 检查新版本文件是否存在
    if not os.path.exists(new_binary_path):
        print(f"新版本文件不存在: {new_binary_path}")
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
        cache_dir = _get_cache_dir()
        script_path = os.path.join(cache_dir, 'fanqie_update.sh')
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
        
        print("更新脚本已启动，程序即将退出...")
        return True
        
    except Exception as e:
        print(f"创建更新脚本失败: {e}")
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
        print(f"不支持的平台: {sys.platform}")
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


