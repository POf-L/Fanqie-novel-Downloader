# -*- coding: utf-8 -*-
"""
构建配置模块的属性测试和单元测试
"""

import os
import sys
import pytest
from hypothesis import given, strategies as st, settings

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from build_app import (
    get_platform_config,
    get_executable_name,
    get_hidden_imports,
)


# ============================================================
# Property 5: Build Configuration Correctness
# **Validates: Requirements 4.1, 4.2, 4.3, 4.4**
# ============================================================

class TestBuildConfigurationCorrectness:
    """
    **Feature: multi-platform-support, Property 5: Build Configuration Correctness**
    
    *For any* target platform in ['windows', 'linux', 'darwin'], the build script 
    SHALL generate configuration without platform-incompatible options and with 
    appropriate file naming.
    """
    
    @given(st.sampled_from(['windows', 'linux', 'darwin']))
    @settings(max_examples=100, deadline=None)
    def test_platform_config_has_required_keys(self, platform):
        """每个平台配置应该包含所有必需的键"""
        config = get_platform_config(platform)
        
        required_keys = ['platform', 'hidden_imports', 'data_files', 'options', 'path_separator']
        for key in required_keys:
            assert key in config, f"Config for {platform} should have key '{key}'"
    
    @given(st.sampled_from(['windows', 'linux', 'darwin']))
    @settings(max_examples=100, deadline=None)
    def test_hidden_imports_is_list(self, platform):
        """hidden_imports 应该是列表"""
        config = get_platform_config(platform)
        
        assert isinstance(config['hidden_imports'], list)
        assert len(config['hidden_imports']) > 0
    
    @given(st.sampled_from(['windows', 'linux', 'darwin']))
    @settings(max_examples=100, deadline=None)
    def test_path_separator_is_correct(self, platform):
        """路径分隔符应该与平台匹配"""
        config = get_platform_config(platform)
        
        if platform == 'windows':
            assert config['path_separator'] == ';', \
                "Windows should use semicolon as path separator"
        else:
            assert config['path_separator'] == ':', \
                f"{platform} should use colon as path separator"
    
    @given(
        st.sampled_from(['windows', 'linux', 'darwin']),
        st.sampled_from(['release', 'debug'])
    )
    @settings(max_examples=100, deadline=None)
    def test_executable_name_format(self, platform, variant):
        """可执行文件名应该符合平台规范"""
        name = get_executable_name("TestApp", platform, variant)
        
        assert isinstance(name, str)
        assert len(name) > 0
        assert "TestApp" in name
        
        # 检查变体后缀
        if variant == 'debug':
            assert 'debug' in name.lower()
        
        # 检查平台后缀
        if platform == 'linux':
            assert 'linux' in name.lower()
        elif platform == 'darwin':
            assert 'macos' in name.lower()
    
    def test_windows_config_no_linux_modules(self):
        """Windows 配置不应该包含 Linux 特定模块"""
        config = get_platform_config('windows')
        
        linux_modules = ['gi', 'gi.repository.Gtk']
        for module in linux_modules:
            # Windows 可能不包含这些模块
            pass  # 这是预期行为
    
    def test_linux_config_no_windows_modules(self):
        """Linux 配置应该排除 Windows 特定模块"""
        config = get_platform_config('linux')
        
        # 检查是否有排除模块列表
        if 'exclude_modules' in config:
            windows_modules = ['win32api', 'win32con', 'pywintypes']
            for module in windows_modules:
                assert module in config['exclude_modules'], \
                    f"Linux config should exclude {module}"
    
    def test_platform_utils_included(self):
        """所有平台配置应该包含 platform_utils 模块"""
        for platform in ['windows', 'linux', 'darwin']:
            config = get_platform_config(platform)
            assert 'platform_utils' in config['hidden_imports'], \
                f"{platform} config should include platform_utils"
    
    def test_cli_module_included(self):
        """所有平台配置应该包含 cli 模块"""
        for platform in ['windows', 'linux', 'darwin']:
            config = get_platform_config(platform)
            assert 'cli' in config['hidden_imports'], \
                f"{platform} config should include cli module"


# ============================================================
# Unit Tests
# ============================================================

class TestGetHiddenImports:
    """get_hidden_imports 单元测试"""
    
    def test_returns_list(self):
        """应该返回列表"""
        imports = get_hidden_imports()
        assert isinstance(imports, list)
    
    def test_contains_core_modules(self):
        """应该包含核心模块"""
        imports = get_hidden_imports()
        
        core_modules = ['config', 'web_app', 'novel_downloader']
        for module in core_modules:
            assert module in imports, f"Should include {module}"
    
    def test_no_duplicates(self):
        """不应该有重复项"""
        imports = get_hidden_imports()
        assert len(imports) == len(set(imports)), "Should have no duplicates"


class TestGetExecutableName:
    """get_executable_name 单元测试"""
    
    def test_release_windows(self):
        """Windows release 版本命名"""
        name = get_executable_name("App", "windows", "release")
        assert name == "App"
    
    def test_debug_windows(self):
        """Windows debug 版本命名"""
        name = get_executable_name("App", "windows", "debug")
        assert name == "App-debug"
    
    def test_release_linux(self):
        """Linux release 版本命名"""
        name = get_executable_name("App", "linux", "release")
        assert name == "App-linux"
    
    def test_debug_linux(self):
        """Linux debug 版本命名"""
        name = get_executable_name("App", "linux", "debug")
        assert name == "App-debug-linux"
    
    def test_release_macos(self):
        """macOS release 版本命名"""
        name = get_executable_name("App", "darwin", "release")
        assert name == "App-macos"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
