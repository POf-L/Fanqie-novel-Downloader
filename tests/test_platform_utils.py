# -*- coding: utf-8 -*-
"""
平台检测模块的属性测试和单元测试
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from hypothesis import given, strategies as st, settings

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from platform_utils import (
    PlatformInfo,
    detect_platform,
    is_frameless_supported,
    get_window_config,
    check_gui_dependencies,
    get_feature_status_report,
    is_feature_available,
    get_unavailable_feature_message,
    PROBLEMATIC_WINDOW_MANAGERS,
    ALL_FEATURES,
    _detect_termux,
    _detect_desktop_environment,
    _get_os_name,
)


# ============================================================
# Property 1: Platform Detection Consistency
# **Validates: Requirements 1.1, 1.2, 6.1**
# ============================================================

class TestPlatformDetectionConsistency:
    """
    **Feature: multi-platform-support, Property 1: Platform Detection Consistency**
    
    *For any* system environment configuration, the platform detection function 
    SHALL return a valid PlatformInfo object with os_name in 
    ['windows', 'linux', 'darwin', 'termux'] and consistent feature availability flags.
    """
    
    @given(st.sampled_from(['win32', 'linux', 'darwin', 'linux2']))
    @settings(max_examples=100, deadline=None)
    def test_os_name_is_valid_for_any_platform(self, mock_platform):
        """对于任何平台，os_name 应该是有效值之一"""
        with patch('platform_utils.sys.platform', mock_platform):
            with patch.dict(os.environ, {'PREFIX': ''}, clear=False):
                info = detect_platform()
                
                valid_os_names = ['windows', 'linux', 'darwin', 'termux']
                assert info.os_name in valid_os_names, \
                    f"os_name '{info.os_name}' not in valid list"
    
    @given(st.sampled_from([
        '/data/data/com.termux/files/usr',
        '/usr',
        '/usr/local',
        '',
        '/home/user'
    ]))
    @settings(max_examples=100)
    def test_termux_detection_consistency(self, prefix_value):
        """Termux 检测应该基于 PREFIX 环境变量一致工作"""
        with patch.dict(os.environ, {'PREFIX': prefix_value}, clear=False):
            is_termux = _detect_termux()
            
            # 如果 PREFIX 包含 com.termux，应该检测为 Termux
            expected = 'com.termux' in prefix_value
            assert is_termux == expected, \
                f"PREFIX='{prefix_value}' should {'be' if expected else 'not be'} Termux"
    
    def test_platform_info_has_all_required_fields(self):
        """PlatformInfo 应该包含所有必需字段"""
        info = detect_platform()
        
        assert hasattr(info, 'os_name')
        assert hasattr(info, 'os_version')
        assert hasattr(info, 'desktop_env')
        assert hasattr(info, 'is_gui_available')
        assert hasattr(info, 'is_termux')
        assert hasattr(info, 'available_features')
        
        assert isinstance(info.os_name, str)
        assert isinstance(info.os_version, str)
        assert isinstance(info.desktop_env, str)
        assert isinstance(info.is_gui_available, bool)
        assert isinstance(info.is_termux, bool)
        assert isinstance(info.available_features, list)
    
    @given(st.sampled_from(['gnome', 'kde', 'xfce', 'i3', 'sway', 'unknown', '']))
    @settings(max_examples=100)
    def test_frameless_support_consistency_with_desktop_env(self, desktop_env):
        """无边框支持应该与桌面环境检测一致"""
        with patch('platform_utils.sys.platform', 'linux'):
            with patch.dict(os.environ, {
                'XDG_CURRENT_DESKTOP': desktop_env,
                'PREFIX': ''
            }, clear=False):
                supported = is_frameless_supported()
                
                # 有问题的窗口管理器不应该支持无边框
                is_problematic = any(wm in desktop_env.lower() 
                                    for wm in PROBLEMATIC_WINDOW_MANAGERS)
                
                if is_problematic:
                    assert not supported, \
                        f"Desktop '{desktop_env}' should not support frameless"


# ============================================================
# Property 7: Feature Availability Reporting
# **Validates: Requirements 6.2, 6.3**
# ============================================================

class TestFeatureAvailabilityReporting:
    """
    **Feature: multi-platform-support, Property 7: Feature Availability Reporting**
    
    *For any* platform configuration, the feature availability report SHALL list 
    all features with their availability status (available/unavailable) and 
    provide explanatory messages for unavailable features.
    """
    
    def test_feature_report_contains_all_features(self):
        """功能报告应该包含所有功能的状态"""
        report = get_feature_status_report()
        
        # 报告应该包含所有功能名称
        feature_names = [
            'PyWebView GUI',
            '浏览器模式',
            '文件夹选择对话框',
            '命令行模式',
            '自动更新',
            '无边框窗口',
        ]
        
        for name in feature_names:
            assert name in report, f"Report should contain '{name}'"
    
    def test_feature_report_shows_status_indicators(self):
        """功能报告应该显示状态指示符"""
        report = get_feature_status_report()
        
        # 应该包含状态指示符
        assert '✓' in report or '✗' in report, \
            "Report should contain status indicators"
    
    @given(st.sampled_from(ALL_FEATURES))
    @settings(max_examples=100)
    def test_unavailable_feature_has_message(self, feature):
        """每个不可用的功能应该有说明消息"""
        message = get_unavailable_feature_message(feature)
        
        assert isinstance(message, str)
        assert len(message) > 0, f"Feature '{feature}' should have a message"
    
    def test_is_feature_available_returns_bool(self):
        """is_feature_available 应该返回布尔值"""
        for feature in ALL_FEATURES:
            result = is_feature_available(feature)
            assert isinstance(result, bool), \
                f"is_feature_available('{feature}') should return bool"
    
    def test_cli_mode_always_available(self):
        """CLI 模式应该在所有平台都可用"""
        assert is_feature_available('cli_mode'), \
            "CLI mode should always be available"


# ============================================================
# Unit Tests
# ============================================================

class TestWindowConfig:
    """窗口配置单元测试"""
    
    def test_window_config_has_required_keys(self):
        """窗口配置应该包含所有必需的键"""
        config = get_window_config()
        
        required_keys = ['title', 'width', 'height', 'min_size', 
                        'background_color', 'frameless']
        
        for key in required_keys:
            assert key in config, f"Config should have key '{key}'"
    
    def test_window_config_values_are_valid(self):
        """窗口配置值应该是有效的"""
        config = get_window_config()
        
        assert isinstance(config['width'], int)
        assert isinstance(config['height'], int)
        assert config['width'] > 0
        assert config['height'] > 0
        assert isinstance(config['frameless'], bool)


class TestGUIDependencyChecker:
    """GUI 依赖检查单元测试"""
    
    def test_check_gui_dependencies_returns_tuple(self):
        """check_gui_dependencies 应该返回元组"""
        result = check_gui_dependencies()
        
        assert isinstance(result, tuple)
        assert len(result) == 2
        
        is_available, missing = result
        assert isinstance(is_available, bool)
        assert isinstance(missing, list)
    
    def test_missing_dependencies_are_strings(self):
        """缺失的依赖应该是字符串列表"""
        _, missing = check_gui_dependencies()
        
        for dep in missing:
            assert isinstance(dep, str)


class TestDesktopEnvironmentDetection:
    """桌面环境检测单元测试"""
    
    def test_returns_empty_on_non_linux(self):
        """非 Linux 平台应该返回空字符串"""
        with patch('platform_utils.sys.platform', 'win32'):
            result = _detect_desktop_environment()
            assert result == ''
    
    def test_detects_xdg_current_desktop(self):
        """应该检测 XDG_CURRENT_DESKTOP 环境变量"""
        with patch('platform_utils.sys.platform', 'linux'):
            with patch.dict(os.environ, {'XDG_CURRENT_DESKTOP': 'GNOME'}, clear=False):
                result = _detect_desktop_environment()
                assert 'gnome' in result.lower()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])


# ============================================================
# Property 3: Graceful Degradation
# **Validates: Requirements 1.3, 2.4, 3.1**
# ============================================================

class TestGracefulDegradation:
    """
    **Feature: multi-platform-support, Property 3: Graceful Degradation**
    
    *For any* missing GUI dependency, the application SHALL either fall back 
    to CLI mode or browser mode without raising unhandled exceptions.
    """
    
    def test_cli_mode_available_when_gui_missing(self):
        """当 GUI 不可用时，CLI 模式应该可用"""
        # CLI 模式应该始终可用
        assert is_feature_available('cli_mode'), \
            "CLI mode should always be available as fallback"
    
    def test_browser_mode_available_as_fallback(self):
        """浏览器模式应该作为回退选项可用"""
        # 浏览器模式在大多数环境都可用
        info = detect_platform()
        if not info.is_termux:
            assert 'gui_browser' in info.available_features, \
                "Browser mode should be available as fallback"
    
    def test_check_gui_dependencies_no_exception(self):
        """检查 GUI 依赖不应该抛出异常"""
        try:
            is_available, missing = check_gui_dependencies()
            assert isinstance(is_available, bool)
            assert isinstance(missing, list)
        except Exception as e:
            pytest.fail(f"check_gui_dependencies raised exception: {e}")
    
    def test_detect_platform_no_exception(self):
        """平台检测不应该抛出异常"""
        try:
            info = detect_platform()
            assert info is not None
        except Exception as e:
            pytest.fail(f"detect_platform raised exception: {e}")
    
    @given(st.booleans())
    @settings(max_examples=100, deadline=None)
    def test_feature_check_returns_bool_for_any_state(self, _):
        """功能检查应该始终返回布尔值"""
        for feature in ALL_FEATURES:
            result = is_feature_available(feature)
            assert isinstance(result, bool), \
                f"is_feature_available('{feature}') should return bool"
