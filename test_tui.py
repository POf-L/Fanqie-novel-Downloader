#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TUI功能测试脚本"""

import sys
import os
import time
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_tui_basic():
    """测试TUI基础功能"""
    print("=== TUI基础功能测试 ===")
    
    try:
        from utils.launcher_tui import get_tui, DownloadOption, MirrorInfo
        tui = get_tui()
        
        print(f"TUI可用: {tui.use_tui}")
        
        # 测试头部显示
        tui.show_header()
        
        # 测试状态显示
        tui.show_status("这是一个信息消息", "info")
        tui.show_status("这是一个成功消息", "success")
        tui.show_status("这是一个警告消息", "warning")
        tui.show_status("这是一个错误消息", "error")
        
        # 测试调试信息
        debug_info = {
            "测试键1": "测试值1",
            "测试键2": "测试值2",
            "测试键3": "测试值3"
        }
        tui.show_debug_info(debug_info)
        
        return True
        
    except Exception as e:
        print(f"TUI测试失败: {e}")
        return False

def test_tui_interactive():
    """测试TUI交互功能"""
    print("\n=== TUI交互功能测试 ===")
    
    try:
        from utils.launcher_tui import get_tui, DownloadOption, MirrorInfo
        tui = get_tui()
        
        if not tui.use_tui:
            print("TUI不可用，跳过交互测试")
            return True
        
        # 测试下载方式选择
        options = [
            DownloadOption("1", "测试选项1", "这是第一个测试选项"),
            DownloadOption("2", "测试选项2", "这是第二个测试选项"),
            DownloadOption("3", "测试选项3", "这是第三个测试选项")
        ]
        
        choice = tui.select_download_mode(options, default="1")
        print(f"用户选择了: {choice}")
        
        # 测试镜像表格显示
        mirrors = [
            MirrorInfo("测试镜像1", "https://test1.com", 100.5),
            MirrorInfo("测试镜像2", "https://test2.com", 200.3),
            MirrorInfo("测试镜像3", "https://test3.com", 150.7)
        ]
        
        idx = tui.show_mirror_table(mirrors, "选择测试镜像", default_index=0)
        print(f"用户选择了镜像: {mirrors[idx].name}")
        
        return True
        
    except Exception as e:
        print(f"TUI交互测试失败: {e}")
        return False

def test_progress_simulation():
    """测试进度显示模拟"""
    print("\n=== 进度显示测试 ===")
    
    try:
        from utils.launcher_tui import get_tui
        tui = get_tui()
        
        if not tui.use_tui:
            print("TUI不可用，跳过进度测试")
            return True
        
        # 模拟测试进度
        def mock_test_func(item):
            time.sleep(0.1)  # 模拟测试延迟
            import random
            if random.random() > 0.3:  # 70%成功率
                return (item, random.uniform(50, 500))
            return None
        
        items = [f"test_item_{i}" for i in range(5)]
        results = tui.show_progress_test(
            "模拟测试延迟",
            items,
            mock_test_func,
            timeout=1.0
        )
        
        print(f"测试结果: {len(results)} 个项目可用")
        
        # 模拟安装进度
        def mock_install_func():
            time.sleep(2)  # 模拟安装时间
        
        success = tui.show_installation_progress(
            "模拟安装过程",
            mock_install_func
        )
        
        print(f"安装结果: {'成功' if success else '失败'}")
        
        return True
        
    except Exception as e:
        print(f"进度显示测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("番茄小说下载器 TUI 功能测试")
    print("=" * 50)
    
    tests = [
        ("基础功能", test_tui_basic),
        ("交互功能", test_tui_interactive),
        ("进度显示", test_progress_simulation)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"测试 {test_name} 异常: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 50)
    print("测试结果汇总:")
    
    for test_name, success in results:
        status = "✓ 通过" if success else "✗ 失败"
        print(f"  {test_name}: {status}")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    print(f"\n总计: {passed}/{total} 个测试通过")
    
    if passed == total:
        print("🎉 所有测试通过！TUI功能正常")
        return True
    else:
        print("⚠️  部分测试失败，请检查相关功能")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
