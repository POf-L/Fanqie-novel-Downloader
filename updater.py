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
import importlib
from typing import Optional, Dict, Any, Callable
from datetime import datetime, timedelta

# 延迟导入第三方依赖，避免模块导入失败
_requests = None
_packaging_version = None
_dependencies_available = None

def _check_dependencies():
    """检查并导入必要的依赖库"""
    global _requests, _packaging_version, _dependencies_available
    
    if _dependencies_available is not None:
        return _dependencies_available
    
    try:
        import requests as req
        from packaging import version as pkg_ver
        _requests = req
        _packaging_version = pkg_ver
        _dependencies_available = True
        return True
    except ImportError as e:
        _dependencies_available = False
        print(f"警告：更新模块依赖缺失: {e}")
        print("请安装依赖：pip install requests packaging")
        return False

def _get_requests():
    """获取 requests 模块"""
    if not _check_dependencies():
        raise ImportError("requests 模块未安装，请运行: pip install requests")
    return _requests

def _get_packaging_version():
    """获取 packaging.version 模块"""
    if not _check_dependencies():
        raise ImportError("packaging 模块未安装，请运行: pip install packaging")
    return _packaging_version

try:
    # 引入构建元信息，避免与packaging.version冲突
    import config as app_meta
except Exception:
    app_meta = None


def is_official_release_build() -> bool:
    """检测是否为GitHub Actions发布版构建（且为打包运行）。"""
    # 修改：允许所有打包版本进行更新
    try:
        # 只要是PyInstaller打包环境就允许更新
        if getattr(sys, "frozen", False):
            return True
        # 源码运行环境也允许更新（开发调试用）
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
            # 延迟导入 requests
            requests = _get_requests()
            
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
            
        except ImportError as e:
            print(f"检查更新失败: 缺少依赖库 - {e}")
            return None
        except Exception as e:
            # 捕获所有异常（包括 requests.exceptions.RequestException）
            print(f"检查更新失败: {e}")
            return None
    
    def has_update(self, force_check: bool = False, force: Optional[bool] = None) -> bool:
        """
        检查是否有新版本
        
        Args:
            force_check: 是否强制检查
            force: 兼容旧调用的别名参数（等价于 force_check）
            
        Returns:
            是否有新版本
        """
        # 兼容旧调用：允许使用 force 关键字作为别名
        if force is not None:
            force_check = force
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
            pkg_version = _get_packaging_version()
            latest_ver = pkg_version.parse(latest_version)
            current_ver = pkg_version.parse(current_version)
            return latest_ver > current_ver
        except ImportError as e:
            print(f"版本比较失败: 缺少依赖库 - {e}")
            return False
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
    
    def _terminate_current_process(self, exit_code: int = 0, delay: float = 0.5) -> None:
        """强制结束当前进程，尽可能释放文件锁。"""
        try:
            if delay > 0:
                time.sleep(delay)
        except Exception:
            pass

        # 刷新输出
        for stream in (getattr(sys, 'stdout', None), getattr(sys, 'stderr', None)):
            try:
                if stream:
                    stream.flush()
            except Exception:
                pass

        # 尝试退出Tk主循环，避免GUI阻塞
        try:
            import tkinter  # type: ignore
            root = getattr(tkinter, "_default_root", None)
            if root is not None:
                try:
                    root.quit()
                except Exception:
                    pass
        except Exception:
            pass

        os._exit(exit_code)
    
    def check_for_updates(self, force: bool = False) -> Optional[Dict[str, Any]]:
        """
        检查更新
        
        Args:
            force: 是否强制检查
            
        Returns:
            更新信息
        """
        return self.checker.get_update_info() if self.checker.has_update(force) else None
    
    def _get_platform_asset(self, assets: list, prefer_debug: bool = False) -> Optional[Dict[str, Any]]:
        """
        根据平台和版本类型选择合适的下载文件
        
        Args:
{{ ... }}
            assets: GitHub Release的资源列表
            prefer_debug: 是否优先选择debug版本
            
        Returns:
            匹配的资源字典,如果没有找到则返回None
        """
        if not assets:
            return None
        
        platform = sys.platform.lower()
        
        # 根据偏好过滤debug或release版本
        if prefer_debug:
            filtered_assets = [a for a in assets if 'debug' in a['name'].lower()]
        else:
            filtered_assets = [a for a in assets if 'debug' not in a['name'].lower()]
        
        # 如果过滤后没有资源,使用所有资源
        if not filtered_assets:
            filtered_assets = assets

        # 根据平台定义优先级检查函数
        if platform == 'win32':
            predicates = [
                lambda n: n.endswith('.exe') and any(k in n for k in ['win', 'windows', 'x64', 'amd64']),
                lambda n: n.endswith('.exe'),  # 任何exe作为备选
                lambda n: any(k in n for k in ['win', 'windows']) and n.endswith('.zip'),
                lambda n: n.endswith('.zip')
            ]
        elif platform.startswith('linux'):
            predicates = [
                lambda n: n.endswith(('.AppImage', '.appimage')),  # AppImage优先(支持大小写)
                lambda n: ('linux' in n) and (n.endswith('.tar.gz') or n.endswith('.tgz')),
                lambda n: ('linux' in n) and n.endswith('.zip'),
                lambda n: (n.endswith('.tar.gz') or n.endswith('.tgz')),
                lambda n: n.endswith('.zip')
            ]
        elif platform == 'darwin':
            predicates = [
                lambda n: n.lower().endswith('.dmg'),
                lambda n: ('mac' in n or 'darwin' in n) and n.lower().endswith('.zip'),
                lambda n: n.lower().endswith('.zip')
            ]
        else:
            predicates = [lambda n: n.endswith('.zip')]

        assets_by_name = [(asset, asset['name'].lower()) for asset in filtered_assets]
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
            # 延迟导入 requests
            requests = _get_requests()
            
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
            
        except ImportError as e:
            error_msg = f"下载更新失败: 缺少依赖库 - {e}"
            self._notify_callbacks('download_error', error_msg)
            print(error_msg)
            return None
        except Exception as e:
            self._notify_callbacks('download_error', str(e))
            print(f"下载更新失败: {e}")
            return None
        finally:
            self.is_downloading = False
    
    def install_update(self, update_file: str, restart: bool = True) -> bool:
        """
        安装更新 - 优先使用外部更新机制

        Args:
            update_file: 更新文件路径
            restart: 是否重启应用

        Returns:
            是否安装成功
        """
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
            
            # 优先使用外部更新器进行更新
            if sys.platform == 'win32' and update_file.endswith('.exe'):
                # Windows 可执行文件：使用外部更新器
                self._create_update_log("使用外部更新器进行 Windows EXE 更新")
                
                # 创建更新信息，模拟下载完成后的状态  
                update_info = {
                    'version': 'manual_update',
                    'name': 'Manual Update',
                    'assets': [{
                        'name': os.path.basename(update_file),
                        'download_url': 'file:///' + os.path.abspath(update_file).replace('\\', '/'),
                        'size': os.path.getsize(update_file),
                        'content_type': 'application/octet-stream'
                    }]
                }
                
                # 直接调用外部更新机制
                try:
                    # 创建一个已下载完成的外部更新脚本
                    self._launch_external_installer(update_file, restart)
                except Exception as e:
                    self._create_update_log(f"外部更新器启动失败，使用备用方案: {e}", "WARNING")
                    # 备用方案
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

            # 写入成功标记，供 GUI 判断更新成功
            try:
                self._create_update_log("更新成功完成")
            except Exception:
                pass

            self._notify_callbacks('install_complete', None)
            return True

        except Exception as e:
            error_msg = f"安装更新失败: {e}"
            self._create_update_log(error_msg, "ERROR")
            self._notify_callbacks('install_error', str(e))
            print(error_msg)
            return False
    
    def _launch_external_installer(self, update_file: str, restart: bool):
        """启动外部安装程序（已下载完成的文件）"""
        current_exe = sys.executable
        current_pid = os.getpid()
        
        # 创建Windows批处理脚本，直接处理已下载的文件
        batch_script = os.path.join(tempfile.gettempdir(), 'install_update.bat')
        batch_content = f'''@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1

echo [更新器] 准备安装更新...

REM 等待主程序退出
taskkill /PID {current_pid} /F >nul 2>&1
timeout /t 3 /nobreak >nul

REM 备份当前文件
if exist "{current_exe}" (
    echo [更新器] 创建备份...
    copy /y "{current_exe}" "{current_exe}.backup" >nul 2>&1
)

REM 替换文件（多种策略）
echo [更新器] 正在更新程序...
set /a retry=0
:retry_replace
if !retry! geq 10 goto failed

REM 尝试直接移动
move /y "{update_file}" "{current_exe}" >nul 2>&1
if not errorlevel 1 goto success

REM 尝试删除后复制
del /f /q "{current_exe}" >nul 2>&1
timeout /t 1 /nobreak >nul
copy /y "{update_file}" "{current_exe}" >nul 2>&1
if not errorlevel 1 (
    del /f /q "{update_file}" >nul 2>&1
    goto success
)

set /a retry+=1
timeout /t 1 /nobreak >nul
goto retry_replace

:failed
echo [更新器] 更新失败，恢复备份...
if exist "{current_exe}.backup" (
    copy /y "{current_exe}.backup" "{current_exe}" >nul 2>&1
)
exit /b 1

:success
echo [更新器] 更新成功！
REM 清理备份
if exist "{current_exe}.backup" del /f /q "{current_exe}.backup" >nul 2>&1

if "{str(restart)}"=="True" (
    echo [更新器] 重启程序...
    start "" "{current_exe}"
)

exit /b 0
'''
        
        with open(batch_script, 'w', encoding='gbk') as f:
            f.write(batch_content)
        
        # 启动批处理脚本
        # 不使用CREATE_NO_WINDOW，让用户能看到更新过程
        DETACHED_PROCESS = 0x00000008
        creationflags = DETACHED_PROCESS
        subprocess.Popen(['cmd', '/c', batch_script], creationflags=creationflags)
        
        # 通知并退出
        self._notify_callbacks('install_progress', '外部安装程序已启动，应用将退出以完成更新...')
        self._terminate_current_process(delay=0.5)
    
    def _start_force_update(self, update_info: Dict[str, Any]) -> None:
        """启动强制更新流程：在外部脚本中进行下载与覆盖，当前进程只负责启动与退出。"""
        try:
            # 标记进行中，供GUI侧避免重复外部安装
            setattr(self, '_force_update_in_progress', True)

            # 更新信息序列化为 JSON，并准备目标可执行文件路径
            update_info_json = json.dumps(update_info)
            try:
                target_exe = sys.executable if getattr(sys, 'frozen', False) else sys.argv[0]
            except Exception:
                target_exe = sys.executable

            # 获取当前进程PID
            current_pid = os.getpid()

            # 准备外部更新脚本
            if getattr(sys, 'frozen', False):
                # 打包后的情况：创建一个独立的Python脚本来执行更新
                self._create_external_updater_script(update_info_json, target_exe, current_pid)
            else:
                # 源码运行：直接调用 Python 执行外部更新器
                import external_updater
                script_path = os.path.abspath(external_updater.__file__)
                # 传递主程序PID作为第三个参数
                args = [sys.executable, script_path, update_info_json, target_exe, str(current_pid)]
                
                if sys.platform == 'win32':
                    # 不使用CREATE_NO_WINDOW，让用户能看到更新过程
                    DETACHED_PROCESS = 0x00000008
                    creationflags = DETACHED_PROCESS
                    subprocess.Popen(args, creationflags=creationflags)
                else:
                    subprocess.Popen(args)

            # 通知并退出当前应用，交由外部脚本处理
            self._notify_callbacks('install_progress', '外部更新程序已启动，应用将退出以完成更新...')
            
            # 复位状态标记
            try:
                setattr(self, '_force_update_in_progress', False)
            except Exception:
                pass
            
            # 使用安全退出方法
            self._terminate_current_process(delay=1.0)
        except Exception as e:
            self._notify_callbacks('force_update_error', str(e))
            print(f"启动外部更新失败: {e}")
            try:
                setattr(self, '_force_update_in_progress', False)
            except Exception:
                pass

    def _create_external_updater_script(self, update_info_json: str, target_exe: str, current_pid: int = None):
        """创建并运行外部更新脚本（用于打包后的exe）"""
        if current_pid is None:
            current_pid = os.getpid()
        temp_dir = tempfile.gettempdir()
        
        # 创建Python更新脚本
        updater_script = os.path.join(temp_dir, 'tomato_updater.py')
        
        # 将 external_updater.py 的内容复制过来（简化版）
        script_content = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os
import time
import json
import shutil
import tempfile
import subprocess

def log_message(msg, level="INFO"):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] [{level}] {msg}"
    print(line)
    try:
        log_file = os.path.join(tempfile.gettempdir(), 'update.log')
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(line + '\\n')
    except Exception:
        pass

def download_file(url, dest, headers=None):
    """简单的文件下载函数"""
    try:
        import urllib.request
        import urllib.error
        
        req = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(req, timeout=60) as response:
            with open(dest, 'wb') as f:
                shutil.copyfileobj(response, f)
        return True
    except Exception as e:
        log_message(f"下载失败: {e}", "ERROR")
        return False

def main():
    if len(sys.argv) < 3:
        log_message("参数错误", "ERROR")
        sys.exit(1)
    
    update_info = json.loads(sys.argv[1])
    target_exe = sys.argv[2]
    
    # 获取主程序PID（如果传递了第三个参数）
    main_pid = int(sys.argv[3]) if len(sys.argv) > 3 else None
    
    log_message(f"开始更新到版本: {update_info.get('version', 'unknown')}")
    
    # 等待主程序退出
    if main_pid:
        log_message(f"等待主程序(PID: {main_pid})退出...")
        for i in range(60):  # 等待30秒
            try:
                # Windows: 检查进程是否存在
                if sys.platform == 'win32':
                    import ctypes
                    kernel32 = ctypes.windll.kernel32
                    SYNCHRONIZE = 0x00100000
                    process = kernel32.OpenProcess(SYNCHRONIZE, 0, main_pid)
                    if process == 0:
                        log_message("主程序已退出")
                        break
                    kernel32.CloseHandle(process)
                else:
                    # Unix: 尝试发送信号0来检查进程
                    os.kill(main_pid, 0)
            except:
                log_message("主程序已退出")
                break
            time.sleep(0.5)
    else:
        # 没有PID，简单等待几秒
        log_message("等待主程序退出...")
        time.sleep(3)
    
    # 下载新文件
    assets = update_info.get('assets', [])
    if not assets:
        log_message("没有找到下载文件", "ERROR")
        sys.exit(1)
    
    # 选择合适的文件（简化版：选择第一个exe文件）
    download_url = None
    for asset in assets:
        if asset['name'].endswith('.exe'):
            download_url = asset['download_url']
            break
    
    if not download_url:
        log_message("没有找到合适的更新文件", "ERROR")
        sys.exit(1)
    
    # 下载到临时文件
    temp_file = os.path.join(tempfile.gettempdir(), 'update_temp.exe')
    log_message(f"下载更新文件: {download_url}")
    
    headers = {'User-Agent': 'Tomato-Novel-Downloader'}
    if not download_file(download_url, temp_file, headers):
        log_message("下载失败", "ERROR")
        sys.exit(1)
    
    # 备份并替换文件
    backup_file = target_exe + '.backup'
    log_message(f"备份原文件: {backup_file}")
    try:
        if os.path.exists(target_exe):
            shutil.copy2(target_exe, backup_file)
    except Exception as e:
        log_message(f"备份失败: {e}", "ERROR")
    
    # 替换文件
    log_message(f"替换程序文件: {target_exe}")
    max_retries = 10
    for i in range(max_retries):
        try:
            if os.path.exists(target_exe):
                os.remove(target_exe)
            shutil.copy2(temp_file, target_exe)
            log_message("更新成功完成")
            break
        except Exception as e:
            if i == max_retries - 1:
                log_message(f"替换失败: {e}", "ERROR")
                # 恢复备份
                if os.path.exists(backup_file):
                    shutil.copy2(backup_file, target_exe)
                sys.exit(1)
            time.sleep(0.5)
    
    # 清理临时文件
    try:
        os.remove(temp_file)
        if os.path.exists(backup_file):
            os.remove(backup_file)
    except:
        pass
    
    # 重启程序
    log_message("重启程序...")
    if sys.platform == 'win32':
        subprocess.Popen([target_exe], creationflags=subprocess.DETACHED_PROCESS)
    else:
        subprocess.Popen([target_exe])
    
    log_message("更新完成")
    # 显示完成提示
    print("\n" + "="*50)
    print("更新完成！程序将自动重启...")
    print("按任意键关闭此窗口...")
    print("="*50)
    input()

if __name__ == "__main__":
    main()
'''
        
        with open(updater_script, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        # 使用批处理启动Python脚本
        batch_script = os.path.join(temp_dir, 'run_updater.bat')
        batch_content = f'''@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1

REM 等待主程序退出
timeout /t 2 /nobreak >nul

REM 查找Python
set PYTHON_CMD=
where python >nul 2>&1 && set "PYTHON_CMD=python"
if not defined PYTHON_CMD where python3 >nul 2>&1 && set "PYTHON_CMD=python3"
if not defined PYTHON_CMD where py >nul 2>&1 && set "PYTHON_CMD=py"

if not defined PYTHON_CMD (
    echo 未找到Python，尝试直接下载和替换
    goto direct_update
) else (
    echo 使用Python执行更新
    !PYTHON_CMD! "{updater_script}" {json.dumps(update_info_json)} "{target_exe}" {current_pid}
    goto end
)

:direct_update
REM 如果没有Python，使用PowerShell下载和替换
echo 使用PowerShell进行更新...
powershell -ExecutionPolicy Bypass -Command "& {{
    $updateInfo = '{update_info_json}' | ConvertFrom-Json
    $targetExe = '{target_exe}'
    $tempFile = [System.IO.Path]::GetTempPath() + 'update_temp.exe'
    
    # 等待主程序退出
    Start-Sleep -Seconds 2
    
    # 查找合适的下载URL
    $downloadUrl = $null
    foreach ($asset in $updateInfo.assets) {{
        if ($asset.name -like '*.exe') {{
            $downloadUrl = $asset.download_url
            break
        }}
    }}
    
    if (-not $downloadUrl) {{
        Write-Host '没有找到下载文件' -ForegroundColor Red
        exit 1
    }}
    
    # 下载文件
    try {{
        Write-Host "下载更新: $downloadUrl"
        $client = New-Object System.Net.WebClient
        $client.Headers['User-Agent'] = 'Tomato-Novel-Downloader'
        $client.DownloadFile($downloadUrl, $tempFile)
    }} catch {{
        Write-Host "下载失败: $_" -ForegroundColor Red
        exit 1
    }}
    
    # 替换文件
    try {{
        if (Test-Path $targetExe) {{
            Copy-Item $targetExe "$targetExe.backup" -Force
            Remove-Item $targetExe -Force
        }}
        Copy-Item $tempFile $targetExe -Force
        Remove-Item $tempFile -Force
        Write-Host '更新成功完成' -ForegroundColor Green
        
        # 重启程序
        Start-Process $targetExe
    }} catch {{
        Write-Host "替换失败: $_" -ForegroundColor Red
        if (Test-Path "$targetExe.backup") {{
            Copy-Item "$targetExe.backup" $targetExe -Force
        }}
        exit 1
    }}
}}"

:end
echo.
echo 更新完成！
echo 按任意键关闭窗口...
pause >nul
exit /b 0
'''
        
        with open(batch_script, 'w', encoding='gbk') as f:
            f.write(batch_content)
        
        # 启动批处理脚本
        if sys.platform == 'win32':
            # 不使用CREATE_NO_WINDOW，让用户能看到更新过程
            DETACHED_PROCESS = 0x00000008
            creationflags = DETACHED_PROCESS
            subprocess.Popen(['cmd', '/c', batch_script], creationflags=creationflags)
        
        self._notify_callbacks('install_progress', '外部更新程序已启动，应用将退出以完成更新...')

    def _install_windows_exe(self, exe_path: str, restart: bool):
        """安装Windows可执行文件（使用外部更新机制）"""
        # 对于直接调用此方法的情况，使用外部更新器
        try:
            # 准备更新信息
            update_info = {
                'version': 'local_update',
                'assets': [{
                    'name': os.path.basename(exe_path),
                    'download_url': 'file:///' + exe_path.replace('\\', '/'),
                }]
            }
            
            # 调用外部更新流程
            self._start_force_update(update_info)
        except Exception as e:
            self._create_update_log(f"启动外部更新失败，使用备用方案: {e}", "WARNING")
            
            # 备用方案：使用简单的批处理
            current_pid = os.getpid()
            current_exe = sys.executable
            
            helper_script = f'''@echo off
setlocal enabledelayedexpansion
taskkill /PID {current_pid} /F >nul 2>&1
timeout /t 3 /nobreak >nul
move /y "{exe_path}" "{current_exe}" >nul 2>&1
if errorlevel 1 (
    del /f /q "{current_exe}" >nul 2>&1
    copy /y "{exe_path}" "{current_exe}" >nul 2>&1
)
if "{restart}"=="True" start "" "{current_exe}"
exit /b 0
'''
            
            helper_path = os.path.join(tempfile.gettempdir(), 'quick_update.bat')
            with open(helper_path, 'w', encoding='gbk') as f:
                f.write(helper_script)
            
            # 不使用CREATE_NO_WINDOW，让用户能看到更新过程
            DETACHED_PROCESS = 0x00000008
            creationflags = DETACHED_PROCESS
            subprocess.Popen(['cmd', '/c', helper_path], creationflags=creationflags)
            
            self._notify_callbacks('install_progress', '更新程序已启动，应用将退出...')
            self._terminate_current_process(delay=0.5)
    
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

        script = fr"""
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

        subprocess.Popen(script_file, shell=True)
        self._terminate_current_process(delay=0.5)
    
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

        subprocess.Popen(['/bin/bash', script_file])
        self._terminate_current_process(delay=0.5)

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

                # 分析最后几行日志（增强兼容性）
                for line in reversed(lines[-50:]):  # 扩大到最后50行，提升容错
                    try:
                        text = line.strip()
                        # 提取时间戳（以方括号包裹的第一段）
                        import re
                        ts_match = re.search(r'\[(.*?)\]', text)

                        # 识别开始标记
                        if ('开始安装更新' in text) or ('准备更新到版本' in text):
                            if ts_match:
                                status['last_update_time'] = ts_match.group(1)
                            continue

                        # 识别成功标记
                        if ('更新成功完成' in text) or ('更新安装成功' in text):
                            status['update_success'] = True
                            continue

                        # 识别错误标记
                        if ('[ERROR]' in text or '安装失败' in text or '下载失败' in text or '更新失败' in text or '错误：' in text):
                            # 尝试提取更友好的错误消息
                            if '] ' in text:
                                status['error_message'] = text.split('] ', 2)[-1].strip()
                            else:
                                # 去掉时间戳后返回剩余内容
                                status['error_message'] = re.sub(r'^\[[^\]]+\]\s*', '', text)
                            # 一旦检测到错误，仍继续扫描以获取可能的时间戳
                            continue
                    except Exception:
                        # 忽略单行解析异常
                        pass

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
    优先从 version.py 获取，其次回退到 config.py，最后默认值。
    
    Returns:
        版本号字符串
    """
    # 优先：动态导入 version 模块（由 GitHub Actions 生成，包含准确版本）
    try:
        import importlib
        mod = importlib.import_module("version")
        if hasattr(mod, "__version__"):
            return str(getattr(mod, "__version__"))
    except Exception:
        pass

    # 次优先：读取本地 version.py 文件
    try:
        version_file = os.path.join(os.path.dirname(__file__), 'version.py')
        if os.path.exists(version_file):
            with open(version_file, 'r', encoding='utf-8') as f:
                content = f.read()
            for line in content.split('\n'):
                if line.strip().startswith('__version__'):
                    version_str = line.split('=')[1].strip().strip('\"\'')
                    if version_str:
                        return version_str
    except Exception as e:
        print(f"读取版本文件失败: {e}")


def check_and_notify_update(updater: AutoUpdater, callback: Optional[Callable] = None):
    """
    后台检查更新并通知
{{ ... }}
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
