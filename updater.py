# -*- coding: utf-8 -*-
"""
自动更新检查模块 - 从GitHub检查新版本
"""

import requests
import re
from packaging import version as pkg_version
from typing import Optional, Dict, Tuple

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
    
    for asset in assets:
        name = asset.get('name', '')
        size = asset.get('size', 0)
        download_url = asset.get('browser_download_url', '')
        
        # 只处理指定平台的文件
        if platform == 'windows':
            if not name.endswith('.exe'):
                continue
            
            # 分类 Windows 版本
            if 'Standalone' in name:
                asset_type = 'standalone'
                description = '完整版 - 内置 WebView2 运行时,开箱即用'
                recommended = True
            elif 'debug' in name.lower():
                asset_type = 'debug'
                description = '调试版 - 包含调试信息和控制台窗口'
                recommended = False
            else:
                asset_type = 'standard'
                description = '标准版 - 需要系统已安装 WebView2'
                recommended = False
        
        elif platform == 'linux':
            if not ('linux' in name.lower() and not name.endswith('.exe')):
                continue
            asset_type = 'debug' if 'debug' in name.lower() else 'release'
            description = '调试版' if asset_type == 'debug' else '发布版'
            recommended = asset_type == 'release'
        
        elif platform == 'macos':
            if not ('macos' in name.lower() and not name.endswith('.exe')):
                continue
            asset_type = 'debug' if 'debug' in name.lower() else 'release'
            description = '调试版' if asset_type == 'debug' else '发布版'
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
    
    message = f"""
🎉 发现新版本可用！

📦 最新版本: {version}
📝 版本名称: {name}

📄 更新说明:
{body if body else '(无更新说明)'}

🔗 下载地址:
{url}

建议更新到最新版本以获得更好的体验和新功能！
""".strip()
    
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
            print('⚠️ 无法检查更新，请检查网络连接')
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
            print(f'✅ 当前已是最新版本 ({current_version})')
        return {
            'has_update': False,
            'current_version': current_version,
            'latest_version': latest_info.get('tag_name', ''),
            'message': '',
            'url': '',
            'release_info': latest_info
        }

if __name__ == '__main__':
    # 测试代码
    from config import __version__, __github_repo__
    
    print(f'当前版本: {__version__}')
    print(f'检查仓库: {__github_repo__}')
    print('-' * 60)
    
    check_and_notify(__version__, __github_repo__)
