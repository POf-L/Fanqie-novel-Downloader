# -*- coding: utf-8 -*-
"""
更新模块平台支持的属性测试和单元测试
"""

import os
import sys
import pytest
from unittest.mock import patch
from hypothesis import given, strategies as st, settings

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from updater import (
    get_current_platform,
    filter_assets_for_platform,
    parse_release_assets,
)


# ============================================================
# Property 6: Update Asset Filtering
# **Validates: Requirements 5.1, 5.4**
# ============================================================

class TestUpdateAssetFiltering:
    """
    **Feature: multi-platform-support, Property 6: Update Asset Filtering**
    
    *For any* list of GitHub release assets and target platform, the filter 
    function SHALL return only assets matching the platform pattern, or an 
    empty list if none match.
    """
    
    # 模拟的 GitHub release assets
    MOCK_ASSETS = [
        {'name': 'TomatoNovelDownloader.exe', 'size': 50000000, 'browser_download_url': 'https://example.com/win.exe'},
        {'name': 'TomatoNovelDownloader-Standalone.exe', 'size': 80000000, 'browser_download_url': 'https://example.com/win-standalone.exe'},
        {'name': 'TomatoNovelDownloader-debug.exe', 'size': 60000000, 'browser_download_url': 'https://example.com/win-debug.exe'},
        {'name': 'TomatoNovelDownloader-linux', 'size': 45000000, 'browser_download_url': 'https://example.com/linux'},
        {'name': 'TomatoNovelDownloader-linux-debug', 'size': 55000000, 'browser_download_url': 'https://example.com/linux-debug'},
        {'name': 'TomatoNovelDownloader-macos', 'size': 48000000, 'browser_download_url': 'https://example.com/macos'},
    ]
    
    @given(st.sampled_from(['windows', 'linux', 'macos']))
    @settings(max_examples=100, deadline=None)
    def test_filtered_assets_match_platform(self, platform):
        """过滤后的资源应该匹配目标平台"""
        filtered = filter_assets_for_platform(self.MOCK_ASSETS, platform)
        
        for asset in filtered:
            name = asset['name'].lower()
            
            if platform == 'windows':
                assert name.endswith('.exe'), \
                    f"Windows asset should be .exe: {name}"
            elif platform == 'linux':
                assert 'linux' in name and not name.endswith('.exe'), \
                    f"Linux asset should contain 'linux' and not be .exe: {name}"
            elif platform == 'macos':
                assert ('macos' in name or 'darwin' in name) and not name.endswith('.exe'), \
                    f"macOS asset should contain 'macos' or 'darwin': {name}"
    
    def test_windows_filter_returns_exe_only(self):
        """Windows 过滤应该只返回 .exe 文件"""
        filtered = filter_assets_for_platform(self.MOCK_ASSETS, 'windows')
        
        assert len(filtered) == 3  # 3 个 Windows exe 文件
        for asset in filtered:
            assert asset['name'].endswith('.exe')
    
    def test_linux_filter_returns_linux_binaries(self):
        """Linux 过滤应该返回 Linux 二进制文件"""
        filtered = filter_assets_for_platform(self.MOCK_ASSETS, 'linux')
        
        assert len(filtered) == 2  # 2 个 Linux 文件
        for asset in filtered:
            assert 'linux' in asset['name'].lower()
            assert not asset['name'].endswith('.exe')
    
    def test_macos_filter_returns_macos_binaries(self):
        """macOS 过滤应该返回 macOS 二进制文件"""
        filtered = filter_assets_for_platform(self.MOCK_ASSETS, 'macos')
        
        assert len(filtered) == 1  # 1 个 macOS 文件
        for asset in filtered:
            assert 'macos' in asset['name'].lower() or 'darwin' in asset['name'].lower()
    
    def test_termux_returns_empty(self):
        """Termux 平台应该返回空列表"""
        filtered = filter_assets_for_platform(self.MOCK_ASSETS, 'termux')
        assert filtered == []
    
    def test_unknown_platform_returns_empty(self):
        """未知平台应该返回空列表"""
        filtered = filter_assets_for_platform(self.MOCK_ASSETS, 'unknown')
        assert filtered == []
    
    def test_empty_assets_returns_empty(self):
        """空资源列表应该返回空列表"""
        filtered = filter_assets_for_platform([], 'windows')
        assert filtered == []


# ============================================================
# Unit Tests
# ============================================================

class TestGetCurrentPlatform:
    """get_current_platform 单元测试"""
    
    def test_returns_valid_platform(self):
        """应该返回有效的平台标识符"""
        platform = get_current_platform()
        
        valid_platforms = ['windows', 'linux', 'macos', 'termux', 'unknown']
        assert platform in valid_platforms
    
    def test_windows_detection(self):
        """Windows 平台检测"""
        with patch('updater.sys.platform', 'win32'):
            with patch.dict(os.environ, {'PREFIX': ''}, clear=False):
                platform = get_current_platform()
                assert platform == 'windows'
    
    def test_linux_detection(self):
        """Linux 平台检测"""
        with patch('updater.sys.platform', 'linux'):
            with patch.dict(os.environ, {'PREFIX': ''}, clear=False):
                platform = get_current_platform()
                assert platform == 'linux'
    
    def test_macos_detection(self):
        """macOS 平台检测"""
        with patch('updater.sys.platform', 'darwin'):
            with patch.dict(os.environ, {'PREFIX': ''}, clear=False):
                platform = get_current_platform()
                assert platform == 'macos'
    
    def test_termux_detection(self):
        """Termux 平台检测"""
        with patch.dict(os.environ, {'PREFIX': '/data/data/com.termux/files/usr'}, clear=False):
            platform = get_current_platform()
            assert platform == 'termux'


class TestParseReleaseAssets:
    """parse_release_assets 单元测试"""
    
    MOCK_RELEASE_INFO = {
        'tag_name': 'v1.0.0',
        'assets': [
            {'name': 'App.exe', 'size': 50000000, 'browser_download_url': 'https://example.com/app.exe'},
            {'name': 'App-Standalone.exe', 'size': 80000000, 'browser_download_url': 'https://example.com/app-standalone.exe'},
        ]
    }
    
    def test_returns_list(self):
        """应该返回列表"""
        result = parse_release_assets(self.MOCK_RELEASE_INFO, 'windows')
        assert isinstance(result, list)
    
    def test_parsed_asset_has_required_fields(self):
        """解析后的资源应该包含必需字段"""
        result = parse_release_assets(self.MOCK_RELEASE_INFO, 'windows')
        
        if result:
            asset = result[0]
            required_fields = ['name', 'type', 'size', 'size_mb', 'download_url', 'description', 'recommended']
            for field in required_fields:
                assert field in asset, f"Asset should have field '{field}'"
    
    def test_standalone_is_recommended(self):
        """Standalone 版本应该被标记为推荐"""
        result = parse_release_assets(self.MOCK_RELEASE_INFO, 'windows')
        
        standalone = [a for a in result if 'Standalone' in a['name']]
        if standalone:
            assert standalone[0]['recommended'] == True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
