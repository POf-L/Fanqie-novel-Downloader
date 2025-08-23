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
        self.cached_releases_list = None  # 缓存版本列表
        self.release_channels = {
            'stable': {'patterns': ['stable', 'release'], 'prerelease': False},
            'beta': {'patterns': ['beta', 'rc'], 'prerelease': True},
            'dev': {'patterns': ['dev', 'alpha', 'nightly'], 'prerelease': True}
        }
        
    def get_all_releases(self, force_check: bool = False, per_page: int = 30) -> Optional[list]:
        """
        获取所有版本列表
        
        Args:
            force_check: 是否强制检查（忽略缓存）
            per_page: 每页返回的版本数量
            
        Returns:
            版本列表
        """
        # 检查缓存
        if not force_check and self.cached_releases_list and self.last_check_time:
            if time.time() - self.last_check_time < self.check_interval:
                return self.cached_releases_list
        
        try:
            url = f"{self.api_base}/repos/{self.github_repo}/releases"
            headers = {
                'Accept': 'application/vnd.github.v3+json',
                'User-Agent': 'Tomato-Novel-Downloader'
            }
            token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
            if token:
                headers['Authorization'] = f'Bearer {token}'
            
            params = {'per_page': per_page}
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            
            releases_data = response.json()
            releases_list = []
            
            for release_data in releases_data:
                release_info = {
                    'version': release_data['tag_name'].lstrip('v'),
                    'name': release_data['name'],
                    'body': release_data['body'],
                    'published_at': release_data['published_at'],
                    'html_url': release_data['html_url'],
                    'prerelease': release_data['prerelease'],
                    'draft': release_data['draft'],
                    'assets': []
                }
                
                # 解析下载链接（构建产物）
                for asset in release_data.get('assets', []):
                    asset_info = {
                        'name': asset.get('name') or 'asset',
                        'size': asset.get('size', 0),
                        'download_url': asset.get('browser_download_url'),
                        'content_type': asset.get('content_type', ''),
                        # 标记是否为源代码包
                        'is_source': False,
                    }
                    release_info['assets'].append(asset_info)

                # 追加源代码zip（zipball），便于以源码方式运行的用户更新
                if release_data.get('zipball_url'):
                    release_info['assets'].append({
                        'name': 'source_code.zip',
                        'size': 0,
                        'download_url': release_data['zipball_url'],
                        'content_type': 'application/zip',
                        'is_source': True,
                    })
                
                releases_list.append(release_info)
            
            # 更新缓存
            self.cached_releases_list = releases_list
            self.last_check_time = time.time()
            
            return releases_list
            
        except requests.exceptions.RequestException as e:
            print(f"获取版本列表失败: {e}")
            return None
        except Exception as e:
            print(f"解析版本列表失败: {e}")
            return None
    
    def get_releases_by_channel(self, channel: str = 'stable', force_check: bool = False) -> Optional[list]:
        """
        根据发布渠道获取版本
        
        Args:
            channel: 发布渠道（'stable', 'beta', 'dev'）
            force_check: 是否强制检查
            
        Returns:
            版本列表
        """
        all_releases = self.get_all_releases(force_check)
        if not all_releases:
            return None
        
        if channel not in self.release_channels:
            print(f"不支持的发布渠道: {channel}")
            return None
        
        channel_config = self.release_channels[channel]
        filtered_releases = []
        
        for release in all_releases:
            # 跳过草稿
            if release['draft']:
                continue
            
            # 根据预发布状态过滤
            if channel == 'stable' and release['prerelease']:
                continue
            elif channel in ['beta', 'dev'] and not release['prerelease']:
                # 对于beta和dev渠道，也可以包含稳定版本
                pass
            
            # 根据名称模式过滤
            release_name_lower = release['name'].lower() if release['name'] else ''
            version_lower = release['version'].lower()
            
            is_match = False
            if channel == 'stable':
                # 稳定版：不包含特殊标识的版本
                excluded_patterns = ['beta', 'alpha', 'rc', 'dev', 'nightly']
                is_match = not any(pattern in release_name_lower or pattern in version_lower 
                                 for pattern in excluded_patterns)
            else:
                # 测试版/开发版：包含特定标识
                patterns = channel_config['patterns']
                is_match = any(pattern in release_name_lower or pattern in version_lower 
                             for pattern in patterns)
            
            if is_match:
                filtered_releases.append(release)
        
        return filtered_releases
    
    def get_latest_release_by_channel(self, channel: str = 'stable', force_check: bool = False) -> Optional[Dict[str, Any]]:
        """
        根据发布渠道获取最新版本
        
        Args:
            channel: 发布渠道
            force_check: 是否强制检查
            
        Returns:
            最新版本信息
        """
        releases = self.get_releases_by_channel(channel, force_check)
        if not releases:
            return None
        
        # 返回最新的版本（列表已按发布时间排序）
        return releases[0]

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
                    'name': asset.get('name') or 'asset',
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
    
    def __init__(self, github_repo: str, current_version: str, preferred_channel: str = 'stable'):
        """
        初始化自动更新器
        
        Args:
            github_repo: GitHub仓库地址
            current_version: 当前版本号
            preferred_channel: 首选发布渠道（'stable', 'beta', 'dev'）
        """
        self.github_repo = github_repo
        self.current_version = current_version
        self.preferred_channel = preferred_channel
        self.checker = UpdateChecker(github_repo, current_version)
        self.download_progress = 0
        self.download_total = 0
        self.is_downloading = False
        self.update_callbacks = []
        
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
    
    def check_for_updates(self, force: bool = False) -> Optional[Dict[str, Any]]:
        """
        检查更新
        
        Args:
            force: 是否强制检查
            
        Returns:
            更新信息
        """
        return self.check_for_updates_by_channel(self.preferred_channel, force)
    
    def check_for_updates_by_channel(self, channel: str, force: bool = False) -> Optional[Dict[str, Any]]:
        """
        根据渠道检查更新
        
        Args:
            channel: 发布渠道
            force: 是否强制检查
            
        Returns:
            更新信息
        """
        latest_release = self.checker.get_latest_release_by_channel(channel, force)
        if not latest_release:
            return None
        
        # 检查是否有更新
        try:
            latest_version = latest_release['version']
            current_version = self.current_version
            
            # 使用UpdateChecker的版本比较逻辑
            if self.checker._is_timestamp_version(latest_version) or self.checker._is_timestamp_version(current_version):
                has_update = self.checker._compare_timestamp_versions(latest_version, current_version)
            else:
                from packaging import version
                latest_ver = version.parse(latest_version)
                current_ver = version.parse(current_version)
                has_update = latest_ver > current_ver
            
            if has_update:
                return latest_release
            
        except Exception as e:
            print(f"版本比较失败: {e}")
        
        return None
    
    def get_available_channels(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有可用的发布渠道和对应的最新版本
        
        Returns:
            渠道信息字典
        """
        channels_info = {}
        
        for channel in ['stable', 'beta', 'dev']:
            try:
                latest_release = self.checker.get_latest_release_by_channel(channel)
                if latest_release:
                    channels_info[channel] = {
                        'latest_version': latest_release['version'],
                        'published_at': latest_release['published_at'],
                        'name': latest_release['name'],
                        'prerelease': latest_release['prerelease'],
                        'has_update': self.check_for_updates_by_channel(channel) is not None,
                        'assets_count': len(latest_release['assets'])
                    }
                else:
                    channels_info[channel] = {
                        'latest_version': None,
                        'has_update': False
                    }
            except Exception as e:
                print(f"获取{channel}渠道信息失败: {e}")
                channels_info[channel] = {
                    'latest_version': None,
                    'has_update': False,
                    'error': str(e)
                }
        
        return channels_info
    
    def set_preferred_channel(self, channel: str):
        """
        设置首选发布渠道
        
        Args:
            channel: 发布渠道
        """
        if channel in ['stable', 'beta', 'dev']:
            self.preferred_channel = channel
        else:
            raise ValueError(f"不支持的发布渠道: {channel}")
    
    def _get_platform_asset(self, assets: list) -> Optional[Dict[str, Any]]:
        """
        根据平台选择合适的下载文件
        
        Args:
            assets: 资源列表
            
        Returns:
            合适的资源信息
        """
        platform = sys.platform.lower()

        # 是否为打包后的可执行程序运行（如 PyInstaller）
        is_frozen = getattr(sys, 'frozen', False)
        is_windows_exe = (platform == 'win32' and str(sys.argv[0]).lower().endswith('.exe'))
        running_packaged = bool(is_frozen or is_windows_exe)

        # 定义平台关键字
        platform_keywords = {
            'win32': ['windows', 'win', '.exe'],
            'darwin': ['macos', 'mac', 'darwin', '.dmg', '.app'],
            'linux': ['linux', '.appimage', '.deb', '.rpm']
        }
        keywords = platform_keywords.get(platform, [])

        # 源码运行优先选择源代码包（zipball）
        if not running_packaged:
            for asset in assets:
                if asset.get('is_source'):
                    return asset
            # 退而求其次：选择不含明显平台关键字的通用zip
            for asset in assets:
                name_l = asset['name'].lower()
                if name_l.endswith('.zip') and not any(k in name_l for k in (platform_keywords['win32'] + platform_keywords['darwin'] + platform_keywords['linux'])):
                    return asset

        # 打包运行优先选择对应平台产物
        for asset in assets:
            name_l = asset['name'].lower()
            if any(k in name_l for k in keywords):
                return asset

        # 兜底：任意zip
        for asset in assets:
            if asset['name'].lower().endswith('.zip'):
                return asset

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
            
            # 显示下载信息
            print(f"下载文件: {asset['name']}")
            print(f"下载位置: {file_path}")
            print(f"文件大小: {asset.get('size', 0) // 1024 // 1024} MB")
            
            # 下载文件（为 GitHub API zipball 等端点附带必要头）
            url = asset['download_url']
            headers = {
                'User-Agent': 'Tomato-Novel-Downloader',
                'Accept': 'application/octet-stream',  # 兼容 zipball/codeload
            }
            token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
            if token:
                headers['Authorization'] = f'Bearer {token}'

            response = requests.get(url, headers=headers, stream=True, timeout=60)
            response.raise_for_status()

            self.download_total = int(response.headers.get('content-length', 0))
            self.download_progress = 0

            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024 * 256):  # 256KB
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
        try:
            self._notify_callbacks('install_start', update_file)
            
            # 根据文件类型处理
            if update_file.endswith('.exe'):
                # Windows可执行文件
                self._install_windows_exe(update_file, restart)
            elif update_file.endswith('.zip'):
                # ZIP压缩包
                self._install_from_zip(update_file, restart)
            else:
                raise Exception(f"不支持的更新文件类型: {update_file}")
            
            self._notify_callbacks('install_complete', None)
            return True
            
        except Exception as e:
            self._notify_callbacks('install_error', str(e))
            print(f"安装更新失败: {e}")
            return False
    
    def _install_windows_exe(self, exe_path: str, restart: bool):
        """安装Windows可执行文件"""
        # 获取当前程序信息
        current_exe = sys.executable
        current_pid = os.getpid()
        
        # 创建批处理脚本来替换文件
        batch_script = f"""@echo off
chcp 65001 > nul
echo 正在等待旧程序关闭...
timeout /t 3 /nobreak > nul

echo 正在关闭旧程序...
taskkill /pid {current_pid} /f > nul 2>&1
timeout /t 2 /nobreak > nul

echo 正在更新程序文件...
move /y "{exe_path}" "{current_exe}"
if %errorlevel% neq 0 (
    echo 更新失败！
    pause
    exit /b 1
)

if "{restart}" == "True" (
    echo 正在重新启动程序...
    start "" "{current_exe}"
    if %errorlevel% neq 0 (
        echo 启动程序失败！
        pause
    )
)

echo 更新完成！
timeout /t 2 /nobreak > nul
del "%~f0"
"""
        
        batch_file = os.path.join(tempfile.gettempdir(), 'tomato_update.bat')
        with open(batch_file, 'w', encoding='utf-8') as f:
            f.write(batch_script)
        
        # 执行批处理脚本
        subprocess.Popen(batch_file, shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE)
        
        # 退出当前程序
        sys.exit(0)
    
    def _install_from_zip(self, zip_path: str, restart: bool):
        """从ZIP文件安装更新"""
        # 解压到临时目录
        temp_extract_dir = os.path.join(tempfile.gettempdir(), 'update_extract')
        os.makedirs(temp_extract_dir, exist_ok=True)

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_extract_dir)

        # 如果是GitHub zipball，顶层可能是单一目录，展开一层
        source_dir = temp_extract_dir
        try:
            entries = os.listdir(temp_extract_dir)
            if len(entries) == 1:
                single = os.path.join(temp_extract_dir, entries[0])
                if os.path.isdir(single):
                    source_dir = single
        except Exception:
            pass

        # 获取当前程序目录
        app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

        # 创建更新脚本
        if sys.platform == 'win32':
            # 若为打包运行（PyInstaller），优先重启当前可执行文件
            current_exe = sys.executable if getattr(sys, 'frozen', False) or str(sys.argv[0]).lower().endswith('.exe') else ""
            self._create_windows_update_script(source_dir, app_dir, restart, current_exe)
        else:
            self._create_unix_update_script(source_dir, app_dir, restart)
    
    def _create_windows_update_script(self, source_dir: str, target_dir: str, restart: bool, current_exe: str = ""):
        """创建Windows更新脚本"""
        script = f"""@echo off
chcp 65001 > nul
echo 正在等待旧程序关闭...
timeout /t 3 /nobreak > nul

echo 正在关闭旧程序...
taskkill /pid {os.getpid()} /f > nul 2>&1
timeout /t 2 /nobreak > nul

echo 正在更新程序文件...
xcopy /s /e /y "{source_dir}\\*" "{target_dir}\\"
if %errorlevel% neq 0 (
    echo 更新失败！
    pause
    exit /b 1
)

echo 清理临时文件...
rmdir /s /q "{source_dir}" > nul 2>&1

if "{restart}" == "True" (
    echo 正在重新启动程序...
    cd /d "{target_dir}"
    set "CUR_EXE={current_exe}"
    if not "%CUR_EXE%"=="" (
        start "" "%CUR_EXE%"
    ) else (
        if exist "main.py" (
            start "" python "main.py"
        ) else if exist "gui.py" (
            start "" python "gui.py"
        ) else (
            echo 未找到启动文件！
            pause
        )
    )
)

echo 更新完成！
timeout /t 2 /nobreak > nul
del "%~f0"
"""

        script_file = os.path.join(tempfile.gettempdir(), 'tomato_update.bat')
        with open(script_file, 'w', encoding='utf-8') as f:
            f.write(script)

        subprocess.Popen(script_file, shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE)
        sys.exit(0)
    
    def _create_unix_update_script(self, source_dir: str, target_dir: str, restart: bool):
        """创建Unix更新脚本"""
        script = f"""#!/bin/bash
sleep 2
cp -rf "{source_dir}"/* "{target_dir}/"
if [ $? -eq 0 ]; then
    rm -rf "{source_dir}"
    if [ "{restart}" = "True" ]; then
        cd "{target_dir}"
        ./{os.path.basename(sys.executable)} &
    fi
fi
rm -f "$0"
"""
        
        script_file = os.path.join(tempfile.gettempdir(), 'update.sh')
        with open(script_file, 'w') as f:
            f.write(script)
        
        os.chmod(script_file, 0o755)
        subprocess.Popen(['/bin/bash', script_file])
        sys.exit(0)


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