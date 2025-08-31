# -*- coding: utf-8 -*-
"""
自动更新模块
提供基于GitHub Releases的版本检测和自动更新功能
"""

import os
import sys
import json
import time
import shutil
import zipfile
import tempfile
import threading
import subprocess
from typing import Optional, Dict, Any, Callable
from datetime import datetime, timedelta

import requests
from packaging import version

try:
	# 引入构建元信息，避免与packaging.version冲突
	import version as app_meta
except Exception:
	app_meta = None


def is_official_release_build() -> bool:
	"""检测是否为GitHub Actions发布版构建（且为打包运行）。"""
	try:
		channel = getattr(app_meta, "__build_channel__", "source") if app_meta else "source"
		if channel != "github-actions":
			return False
		# 仅在PyInstaller打包环境启用
		if not getattr(sys, "frozen", False):
			return False
		return True
	except Exception:
		return False


class UpdateChecker:
    """版本检测器"""
    
    def __init__(self, github_repo: str, current_version: str):
        """
        初始化更新检测器
        
        Args:
            github_repo: GitHub仓库地址，格式为 'owner/repo'
            current_version: 当前版本号
        """
        self.github_repo = github_repo
        self.current_version = current_version
        self.api_base = "https://api.github.com"
        self.check_interval = 3600  # 检查间隔（秒）
        self.last_check_time = None
        self.cached_release = None
        
    def get_latest_release(self, force_check: bool = False) -> Optional[Dict[str, Any]]:
        """
        获取最新版本信息
        
        Args:
            force_check: 是否强制检查（忽略缓存）
            
        Returns:
            最新版本信息字典，包含版本号、下载链接等
        """
        # 检查缓存
        if not force_check and self.cached_release and self.last_check_time:
            if time.time() - self.last_check_time < self.check_interval:
                return self.cached_release
        
        try:
            url = f"{self.api_base}/repos/{self.github_repo}/releases/latest"
            headers = {
                'Accept': 'application/vnd.github.v3+json',
                'User-Agent': 'Tomato-Novel-Downloader'
            }
            token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
            if token:
                headers['Authorization'] = f'Bearer {token}'
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            release_data = response.json()
            
            # 解析版本信息
            release_info = {
                'version': release_data['tag_name'].lstrip('v'),
                'name': release_data['name'],
                'body': release_data['body'],
                'published_at': release_data['published_at'],
                'html_url': release_data['html_url'],
                'assets': []
            }
            
            # 解析下载链接
            for asset in release_data.get('assets', []):
                asset_info = {
                    'name': asset['name'],
                    'size': asset['size'],
                    'download_url': asset['browser_download_url'],
                    'content_type': asset['content_type']
                }
                release_info['assets'].append(asset_info)
            
            # 更新缓存
            self.cached_release = release_info
            self.last_check_time = time.time()
            
            return release_info
            
        except requests.exceptions.RequestException as e:
            print(f"检查更新失败: {e}")
            return None
        except Exception as e:
            print(f"解析版本信息失败: {e}")
            return None
    
    def has_update(self, force_check: bool = False) -> bool:
        """
        检查是否有新版本
        
        Args:
            force_check: 是否强制检查
            
        Returns:
            是否有新版本
        """
        latest_release = self.get_latest_release(force_check)
        if not latest_release:
            return False
        
        try:
            latest_version = latest_release['version']
            current_version = self.current_version
            
            # 如果版本号包含日期格式（YYYY.MM.DD.HHMM+hash），使用字符串比较
            if self._is_timestamp_version(latest_version) or self._is_timestamp_version(current_version):
                return self._compare_timestamp_versions(latest_version, current_version)
            
            # 传统版本号使用packaging.version比较
            latest_ver = version.parse(latest_version)
            current_ver = version.parse(current_version)
            return latest_ver > current_ver
        except Exception as e:
            print(f"版本比较失败: {e}")
            return False
    
    def _is_timestamp_version(self, ver_str: str) -> bool:
        """检查是否为时间戳格式的版本号（YYYY.MM.DD.HHMM+hash）"""
        import re
        pattern = r'^\d{4}\.\d{2}\.\d{2}\.\d{4}\+[a-f0-9]{7}$'
        return bool(re.match(pattern, ver_str))
    
    def _compare_timestamp_versions(self, latest: str, current: str) -> bool:
        """
        比较时间戳格式的版本号
        格式: YYYY.MM.DD.HHMM+hash
        """
        try:
            # 首先检查完整版本号是否相同
            if latest.strip() == current.strip():
                return False
            
            # 提取时间戳部分进行比较
            latest_timestamp = latest.split('+')[0] if '+' in latest else latest
            current_timestamp = current.split('+')[0] if '+' in current else current
            
            # 如果是传统版本号，认为较旧
            if not self._is_timestamp_version(current):
                return True
            
            # 时间戳比较：较新的时间戳表示更新的版本
            if latest_timestamp == current_timestamp:
                # hash不同也认为是不同版本，但通常不需要更新
                return False
            
            return latest_timestamp > current_timestamp
        except Exception as e:
            print(f"版本比较异常: {e}")
            return False
    
    def get_update_info(self) -> Optional[Dict[str, Any]]:
        """
        获取更新信息（版本号、更新内容等）
        
        Returns:
            更新信息字典
        """
        if not self.has_update():
            return None
        
        return self.cached_release


class AutoUpdater:
    """自动更新器"""
    
    def __init__(self, github_repo: str, current_version: str):
        """
        初始化自动更新器
        
        Args:
            github_repo: GitHub仓库地址
            current_version: 当前版本号
        """
        self.github_repo = github_repo
        self.current_version = current_version
        self.checker = UpdateChecker(github_repo, current_version)
        self.download_progress = 0
        self.download_total = 0
        self.is_downloading = False
        self.update_callbacks = []
        self.official_build_only = True
        
    def register_callback(self, callback: Callable):
        """注册更新回调函数"""
        self.update_callbacks.append(callback)

    def _notify_callbacks(self, event: str, data: Any = None):
        """通知所有回调函数"""
        for callback in self.update_callbacks:
            try:
                callback(event, data)
            except Exception as e:
                print(f"回调函数执行失败: {e}")

    def _create_update_log(self, message: str, level: str = "INFO"):
        """创建更新日志"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] [{level}] {message}"

        # 写入日志文件
        log_file = os.path.join(tempfile.gettempdir(), 'update.log')
        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(log_message + '\n')
        except Exception:
            pass  # 忽略日志写入失败

        # 同时输出到控制台
        print(log_message)
    
    def check_for_updates(self, force: bool = False) -> Optional[Dict[str, Any]]:
        """
        检查更新
        
        Args:
            force: 是否强制检查
            
        Returns:
            更新信息
        """
        return self.checker.get_update_info() if self.checker.has_update(force) else None
    
    def _get_platform_asset(self, assets: list) -> Optional[Dict[str, Any]]:
        """
        根据平台选择合适的下载文件
        
        Args:
            assets: 资源列表
            
        Returns:
            合适的资源信息
        """
        platform = sys.platform.lower()

        # 根据平台定义优先级检查函数
        if platform == 'win32':
            predicates = [
                lambda n: n.endswith('.exe') and ('win' in n or 'windows' in n),
                lambda n: ('win' in n or 'windows' in n) and n.endswith('.zip'),
                lambda n: n.endswith('.zip')
            ]
        elif platform.startswith('linux'):
            predicates = [
                lambda n: n.endswith(('.appimage', '.appimage')),  # AppImage优先
                lambda n: ('linux' in n) and (n.endswith('.tar.gz') or n.endswith('.tgz')),
                lambda n: ('linux' in n) and n.endswith('.zip'),
                lambda n: (n.endswith('.tar.gz') or n.endswith('.tgz')),
                lambda n: n.endswith('.zip')
            ]
        elif platform == 'darwin':
            predicates = [
                lambda n: n.endswith('.dmg'),
                lambda n: ('mac' in n or 'darwin' in n) and n.endswith('.zip'),
                lambda n: n.endswith('.zip')
            ]
        else:
            predicates = [lambda n: n.endswith('.zip')]

        assets_by_name = [(asset, asset['name'].lower()) for asset in assets]
        for pred in predicates:
            for asset, lower_name in assets_by_name:
                try:
                    if pred(lower_name):
                        return asset
                except Exception:
                    continue

        return None
    
    def download_update(self, update_info: Dict[str, Any], 
                       progress_callback: Optional[Callable] = None) -> Optional[str]:
        """
        下载更新
        
        Args:
            update_info: 更新信息
            progress_callback: 进度回调函数
            
        Returns:
            下载的文件路径
        """
        # 仅允许官方发布版自动更新
        if self.official_build_only and not is_official_release_build():
            self._notify_callbacks('download_error', '当前为源码或非官方构建，已禁用自动更新')
            return None
        if self.is_downloading:
            return None
        
        self.is_downloading = True
        self._notify_callbacks('download_start', update_info)
        
        try:
            # 选择合适的下载文件
            asset = self._get_platform_asset(update_info['assets'])
            if not asset:
                raise Exception("没有找到适合当前平台的更新文件")
            
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
            
            self.download_total = int(response.headers.get('content-length', 0))
            self.download_progress = 0
            
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        self.download_progress += len(chunk)
                        
                        if progress_callback:
                            progress_callback(self.download_progress, self.download_total)
                        
                        self._notify_callbacks('download_progress', {
                            'current': self.download_progress,
                            'total': self.download_total,
                            'percent': (self.download_progress / self.download_total * 100) 
                                      if self.download_total > 0 else 0
                        })
            
            # 简单完整性校验（如有Content-Length）
            if self.download_total > 0 and os.path.getsize(file_path) != self.download_total:
                raise Exception("下载文件大小与预期不一致")

            self._notify_callbacks('download_complete', file_path)
            return file_path
            
        except Exception as e:
            self._notify_callbacks('download_error', str(e))
            print(f"下载更新失败: {e}")
            return None
        finally:
            self.is_downloading = False
    
    def install_update(self, update_file: str, restart: bool = True) -> bool:
        """
        安装更新

        Args:
            update_file: 更新文件路径
            restart: 是否重启应用

        Returns:
            是否安装成功
        """
        # 仅允许官方发布版自动更新
        if self.official_build_only and not is_official_release_build():
            self._notify_callbacks('install_error', '当前为源码或非官方构建，已禁用自动更新')
            return False
        try:
            self._notify_callbacks('install_start', update_file)
            self._create_update_log(f"开始安装更新: {update_file}")

            # 预检查：确保更新文件存在且可读
            if not os.path.exists(update_file):
                raise Exception(f"更新文件不存在: {update_file}")

            if not os.access(update_file, os.R_OK):
                raise Exception(f"无法读取更新文件: {update_file}")

            self._create_update_log(f"更新文件验证通过: {update_file}")

            # 预检查：确保当前程序目录可写
            current_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            if not os.access(current_dir, os.W_OK):
                raise Exception(f"程序目录无写入权限: {current_dir}")

            self._create_update_log(f"程序目录权限检查通过: {current_dir}")

            # 根据文件类型处理
            if update_file.endswith('.exe'):
                # Windows可执行文件
                self._create_update_log("使用Windows EXE更新模式")
                self._install_windows_exe(update_file, restart)
            elif update_file.endswith('.zip'):
                # ZIP压缩包
                self._create_update_log("使用ZIP压缩包更新模式")
                self._install_from_zip(update_file, restart)
            elif update_file.endswith('.tar.gz') or update_file.endswith('.tgz'):
                # tarball 压缩包（常见于Linux）
                self._create_update_log("使用TAR.GZ压缩包更新模式")
                self._install_from_tarball(update_file, restart)
            elif update_file.lower().endswith(('.appimage',)):
                # AppImage 单文件
                self._create_update_log("使用AppImage更新模式")
                self._install_unix_single_file(update_file, restart)
            else:
                raise Exception(f"不支持的更新文件类型: {update_file}")

            self._notify_callbacks('install_complete', None)
            return True

        except Exception as e:
            error_msg = f"安装更新失败: {e}"
            self._create_update_log(error_msg, "ERROR")
            self._notify_callbacks('install_error', str(e))
            print(error_msg)
            return False
    
    def _install_windows_exe(self, exe_path: str, restart: bool):
        """安装Windows可执行文件（调用外部批处理脚本接管更新）"""
        current_pid = os.getpid()
        current_exe = sys.executable

        helper_name = 'update_helper.bat'
        helper_path = os.path.join(tempfile.gettempdir(), helper_name)

        helper_script = f"""
@echo off
setlocal enabledelayedexpansion

REM 参数：当前PID、当前EXE路径、下载的更新文件路径、是否重启(True/False)
set target_pid={current_pid}
set current_exe="{current_exe}"
set update_file="{exe_path}"
set do_restart={str(restart)}

echo [Updater] 准备关闭进程 !target_pid! 并执行文件替换
taskkill /PID !target_pid! /F >nul 2>&1
timeout /t 2 /nobreak > nul

REM 等待退出，最多15次
set /a count=0
:wait_exit
tasklist /FI "PID eq !target_pid!" 2>nul | find "!target_pid!" >nul
if errorlevel 1 goto do_update
set /a count+=1
if !count! geq 15 (
    echo [Updater] 进程未退出，继续强制更新
    goto do_update
)
timeout /t 1 /nobreak > nul
goto wait_exit

:do_update
echo [Updater] 开始更新文件
REM 备份旧文件
if exist !current_exe! (
    copy /y !current_exe! !current_exe!.backup >nul 2>&1
)

REM 替换新文件（带重试）
set /a retry=0
:replace_retry
move /y !update_file! !current_exe! >nul 2>&1
if errorlevel 1 (
    set /a retry+=1
    if !retry! lss 5 (
        echo [Updater] 替换失败，重试 !retry!/5
        timeout /t 1 /nobreak > nul
        goto replace_retry
    ) else (
        echo [Updater] 替换失败，尝试恢复备份
        if exist !current_exe!.backup (
            move /y !current_exe!.backup !current_exe! >nul 2>&1
        )
        goto end
    )
)

REM 清理备份
if exist !current_exe!.backup (
    del /f /q !current_exe!.backup >nul 2>&1
)

if "!do_restart!"=="True" (
    echo [Updater] 重启程序
    start "" !current_exe!
)

:end
exit /b 0
"""

        with open(helper_path, 'w', encoding='gbk') as f:
            f.write(helper_script)

        DETACHED_PROCESS = 0x00000008
        CREATE_NO_WINDOW = 0x08000000
        creationflags = DETACHED_PROCESS | CREATE_NO_WINDOW

        subprocess.Popen(['cmd', '/c', helper_path], creationflags=creationflags)

        self._notify_callbacks('install_progress', '外部更新程序已启动，应用将退出以完成更新...')
        time.sleep(0.5)
        sys.exit(0)
    
    def _install_from_zip(self, zip_path: str, restart: bool):
        """从ZIP文件安装更新"""
        # 解压到临时目录
        temp_extract_dir = os.path.join(tempfile.gettempdir(), 'update_extract')
        os.makedirs(temp_extract_dir, exist_ok=True)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_extract_dir)
        
        # 规范化解压出的可执行文件名称，确保覆盖当前正在运行的可执行文件名
        try:
            current_basename = os.path.basename(sys.executable)
            self._normalize_extracted_binary_name(temp_extract_dir, current_basename)
        except Exception as e:
            print(f"规范化解压文件名失败: {e}")
        
        # 获取当前程序目录
        app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        
        # 创建更新脚本
        if sys.platform == 'win32':
            self._create_windows_update_script(temp_extract_dir, app_dir, restart)
        else:
            self._create_unix_update_script(temp_extract_dir, app_dir, restart)

    def _normalize_extracted_binary_name(self, source_dir: str, target_basename: str) -> None:
        """在解压目录中查找主要可执行文件并重命名为当前可执行文件名。
        解决Release产物文件名包含版本号而导致无法覆盖原可执行文件的问题。
        """
        # macOS .app 包场景不处理此重命名
        for item in os.listdir(source_dir):
            if item.lower().endswith('.app') and os.path.isdir(os.path.join(source_dir, item)):
                return
        
        candidates = []
        for root, dirs, files in os.walk(source_dir):
            for name in files:
                try:
                    path = os.path.join(root, name)
                    lower_name = name.lower()
                    # 以可执行权限、后缀或关键字作为候选
                    if (
                        lower_name.endswith('.exe') or
                        'tomatonoveldownloader' in lower_name or
                        os.access(path, os.X_OK)
                    ):
                        candidates.append(path)
                except Exception:
                    continue
        if not candidates:
            return
        
        # 选择最大的候选文件，通常为实际可执行文件
        candidates.sort(key=lambda p: os.path.getsize(p) if os.path.exists(p) else 0, reverse=True)
        src_path = candidates[0]
        src_dir = os.path.dirname(src_path)
        # 目标名直接使用当前正在运行的可执行文件名
        target_path = os.path.join(src_dir, target_basename)
        
        # 已经同名则无需处理
        if os.path.basename(src_path) == target_basename:
            # 确保可执行权限
            try:
                if sys.platform != 'win32':
                    os.chmod(src_path, 0o755)
            except Exception:
                pass
            return
        
        # 重命名为目标名，覆盖已存在的文件
        try:
            if os.path.exists(target_path):
                try:
                    os.remove(target_path)
                except Exception:
                    pass
            os.replace(src_path, target_path)
            if sys.platform != 'win32':
                try:
                    os.chmod(target_path, 0o755)
                except Exception:
                    pass
        except Exception as e:
            # 失败则忽略，让后续脚本复制两个并保留旧名（虽然不会生效，但不影响当前运行）
            print(f"重命名解压文件失败: {e}")
    
    def _create_windows_update_script(self, source_dir: str, target_dir: str, restart: bool):
        """创建Windows更新脚本"""
        current_pid = os.getpid()
        exe_name = os.path.basename(sys.executable)

        script = f"""
@echo off
setlocal enabledelayedexpansion
echo 等待程序退出...

REM 强制结束当前进程
taskkill /PID {current_pid} /F >nul 2>&1
timeout /t 2 /nobreak > nul

REM 等待进程完全退出，最多等待10秒
set /a count=0
:wait_loop
tasklist /FI "PID eq {current_pid}" 2>nul | find "{current_pid}" >nul
if errorlevel 1 goto process_ended
set /a count+=1
if %count% geq 10 (
    echo 警告：程序未在预期时间内退出，强制终止进程
    taskkill /PID {current_pid} /F >nul 2>&1
    timeout /t 1 /nobreak > nul
    goto process_ended
)
timeout /t 1 /nobreak > nul
goto wait_loop

:process_ended
echo 开始更新程序文件...

REM 创建备份目录
if not exist "{target_dir}\\backup" mkdir "{target_dir}\\backup" 2>nul
if errorlevel 1 (
    echo 警告：无法创建备份目录，尝试继续更新
)

REM 备份重要文件
if exist "{target_dir}\\{exe_name}" (
    echo 创建备份...
    copy "{target_dir}\\{exe_name}" "{target_dir}\\backup\\{exe_name}.backup" >nul 2>&1
    if errorlevel 1 (
        echo 警告：无法创建备份文件，尝试继续更新
    ) else (
        echo 备份文件已创建
    )
)

REM 复制新文件
echo 复制更新文件...
xcopy /s /e /y /h /r "{source_dir}\\*" "{target_dir}\\" >nul 2>&1
if %errorlevel% == 0 (
    echo 更新成功完成
    REM 清理临时文件
    if exist "{source_dir}" (
        rmdir /s /q "{source_dir}" 2>nul
    )

    REM 删除备份（更新成功后，带重试机制）
    if exist "{target_dir}\\backup\\{exe_name}.backup" (
        echo 清理备份文件...
        set /a retry=0
        :cleanup_backup_retry
        del "{target_dir}\\backup\\{exe_name}.backup" 2>nul
        if exist "{target_dir}\\backup\\{exe_name}.backup" (
            set /a retry+=1
            if !retry! lss 3 (
                echo 重试删除备份文件 (!retry!/3)...
                timeout /t 1 /nobreak > nul
                goto cleanup_backup_retry
            ) else (
                echo 警告：无法删除备份文件，将在下次启动时清理
            )
        ) else (
            echo 备份文件已清理
        )
    )

    REM 清理空的备份目录
    if exist "{target_dir}\\backup" (
        dir /b "{target_dir}\\backup" 2>nul | findstr "." >nul
        if errorlevel 1 (
            rmdir "{target_dir}\\backup" 2>nul
        )
    )

    if "{restart}" == "True" (
        echo 重启程序...
        cd /d "{target_dir}"
        start "" "{exe_name}"
        goto end_script
    )
) else (
    echo 错误：文件复制失败，尝试恢复备份
    if exist "{target_dir}\\backup\\{exe_name}.backup" (
        copy "{target_dir}\\backup\\{exe_name}.backup" "{target_dir}\\{exe_name}" >nul 2>&1
        if errorlevel 1 (
            echo 错误：无法恢复备份文件
        ) else (
            echo 已恢复原程序文件
        )
    )
    goto cleanup
)

:cleanup
echo 更新失败，清理临时文件...

:end_script
REM 确保脚本文件存在后再删除
if exist "%~f0" (
    timeout /t 1 /nobreak > nul
    del "%~f0" 2>nul
)
"""
        script_file = os.path.join(tempfile.gettempdir(), 'update.bat')
        with open(script_file, 'w', encoding='gbk') as f:  # 使用gbk编码避免中文乱码
            f.write(script)

        # 通知用户程序即将退出
        self._notify_callbacks('install_progress', '程序即将退出以完成更新...')
        time.sleep(0.5)  # 给UI一点时间显示消息

        subprocess.Popen(script_file, shell=True)
        sys.exit(0)
    
    def _create_unix_update_script(self, source_dir: str, target_dir: str, restart: bool):
        """创建Unix更新脚本"""
        current_pid = os.getpid()
        exe_name = os.path.basename(sys.executable)

        script = f"""#!/bin/bash
echo "等待程序退出..."

# 等待当前进程退出，最多等待30秒
count=0
while [ $count -lt 30 ]; do
    if ! kill -0 {current_pid} 2>/dev/null; then
        break
    fi
    count=$((count + 1))
    sleep 1
done

if kill -0 {current_pid} 2>/dev/null; then
    echo "警告：程序未在预期时间内退出，强制继续更新"
fi

echo "开始更新程序文件..."

# 创建备份目录
mkdir -p "{target_dir}/backup"

# 备份重要文件
if [ -f "{target_dir}/{exe_name}" ]; then
    cp "{target_dir}/{exe_name}" "{target_dir}/backup/{exe_name}.backup" 2>/dev/null
fi

# 复制新文件
if cp -rf "{source_dir}"/* "{target_dir}/"; then
    echo "更新成功完成"
    rm -rf "{source_dir}" 2>/dev/null
    # 删除备份（更新成功后）
    rm -rf "{target_dir}/backup" 2>/dev/null

    if [ "{restart}" = "True" ]; then
        echo "重启程序..."
        cd "{target_dir}"
        nohup ./{exe_name} > /dev/null 2>&1 &
    fi
else
    echo "错误：更新失败，尝试恢复备份"
    if [ -f "{target_dir}/backup/{exe_name}.backup" ]; then
        cp "{target_dir}/backup/{exe_name}.backup" "{target_dir}/{exe_name}" 2>/dev/null
        echo "已恢复原程序文件"
    fi
    read -p "按回车键继续..."
fi

rm -f "$0"
"""

        script_file = os.path.join(tempfile.gettempdir(), 'update.sh')
        with open(script_file, 'w') as f:
            f.write(script)

        os.chmod(script_file, 0o755)

        # 通知用户程序即将退出
        self._notify_callbacks('install_progress', '程序即将退出以完成更新...')
        time.sleep(0.5)  # 给UI一点时间显示消息

        subprocess.Popen(['/bin/bash', script_file])
        sys.exit(0)

    def _install_from_tarball(self, tar_path: str, restart: bool):
        """从tar.gz或tgz安装更新（Unix平台）"""
        import tarfile
        # 解压到临时目录
        temp_extract_dir = os.path.join(tempfile.gettempdir(), 'update_extract')
        os.makedirs(temp_extract_dir, exist_ok=True)
        with tarfile.open(tar_path, 'r:gz') as tar:
            tar.extractall(temp_extract_dir)
        # 规范化可执行文件名称
        try:
            current_basename = os.path.basename(sys.executable)
            self._normalize_extracted_binary_name(temp_extract_dir, current_basename)
        except Exception as e:
            print(f"规范化解压文件名失败: {e}")
        # 生成脚本
        app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        self._create_unix_update_script(temp_extract_dir, app_dir, restart)

    def _install_unix_single_file(self, file_path: str, restart: bool):
        """安装单文件（如AppImage），通过统一脚本复制覆盖"""
        temp_extract_dir = os.path.join(tempfile.gettempdir(), 'update_extract')
        os.makedirs(temp_extract_dir, exist_ok=True)
        # 重命名为当前可执行文件名
        target_basename = os.path.basename(sys.executable)
        target_path = os.path.join(temp_extract_dir, target_basename)
        try:
            if os.path.exists(target_path):
                os.remove(target_path)
            shutil.copy2(file_path, target_path)
            if sys.platform != 'win32':
                os.chmod(target_path, 0o755)
        except Exception as e:
            raise Exception(f"准备单文件更新失败: {e}")
        # 生成脚本
        app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        self._create_unix_update_script(temp_extract_dir, app_dir, restart)

    @staticmethod
    def check_update_status() -> Dict[str, Any]:
        """
        检查上次更新的状态

        Returns:
            更新状态信息
        """
        log_file = os.path.join(tempfile.gettempdir(), 'update.log')
        status = {
            'last_update_time': None,
            'update_success': False,
            'error_message': None,
            'log_exists': False
        }

        if os.path.exists(log_file):
            status['log_exists'] = True
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

                # 分析最后几行日志
                for line in reversed(lines[-20:]):  # 只看最后20行
                    if '开始安装更新' in line:
                        # 提取时间戳
                        import re
                        match = re.search(r'\[(.*?)\]', line)
                        if match:
                            status['last_update_time'] = match.group(1)
                    elif '更新成功完成' in line:
                        status['update_success'] = True
                    elif '[ERROR]' in line:
                        status['error_message'] = line.split('] ', 2)[-1].strip()

            except Exception as e:
                status['error_message'] = f"读取更新日志失败: {e}"

        return status

    @staticmethod
    def clear_update_log():
        """清除更新日志"""
        log_file = os.path.join(tempfile.gettempdir(), 'update.log')
        try:
            if os.path.exists(log_file):
                os.remove(log_file)
        except Exception:
            pass


def get_current_version() -> str:
    """
    获取当前版本号
    
    Returns:
        版本号字符串
    """
    # 尝试从version.py文件读取
    version_file = os.path.join(os.path.dirname(__file__), 'version.py')
    if os.path.exists(version_file):
        try:
            with open(version_file, 'r', encoding='utf-8') as f:
                content = f.read()
                # 查找__version__定义
                for line in content.split('\n'):
                    if line.strip().startswith('__version__'):
                        # 提取版本号，支持单引号和双引号
                        version_str = line.split('=')[1].strip()
                        version_str = version_str.strip('"\'')
                        return version_str
        except Exception as e:
            print(f"读取版本文件失败: {e}")
    
    # 默认版本号
    return "1.0.0"


def check_and_notify_update(updater: AutoUpdater, callback: Optional[Callable] = None):
    """
    后台检查更新并通知
    
    Args:
        updater: 更新器实例
        callback: 通知回调函数
    """
    def check():
        update_info = updater.check_for_updates()
        if update_info and callback:
            callback(update_info)
    
    thread = threading.Thread(target=check, daemon=True)
    thread.start()


if __name__ == "__main__":
    # 测试代码
    updater = AutoUpdater("owner/repo", "1.0.0")
    update_info = updater.check_for_updates()
    if update_info:
        print(f"发现新版本: {update_info['version']}")
        print(f"更新内容: {update_info['body']}")