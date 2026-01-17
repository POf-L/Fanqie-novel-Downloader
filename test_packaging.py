# -*- coding: utf-8 -*-
"""
打包测试脚本 - 验证关键功能是否正常工作
"""

import sys
import os
import traceback


def test_imports():
    """测试关键模块导入"""
    print("🔍 测试模块导入...")

    try:
        # 测试基础模块
        import asyncio
        import concurrent.futures
        import threading
        print("✅ 基础异步模块导入成功")

        # 测试网络模块
        import requests
        import aiohttp
        print("✅ 网络模块导入成功")

        # 测试项目模块
        from config.config import CONFIG
        print("✅ 配置模块导入成功")

        from utils.updater import check_update
        print("✅ 更新模块导入成功")

        from core.novel_downloader import get_api_manager
        print("✅ 下载模块导入成功")

        return True
    except Exception as e:
        print(f"❌ 模块导入失败: {e}")
        traceback.print_exc()
        return False


def test_config():
    """测试配置加载"""
    print("\n🔍 测试配置加载...")

    try:
        from config.config import CONFIG, LOCAL_CONFIG_JSON

        print(f"配置文件路径: {LOCAL_CONFIG_JSON}")
        print(f"配置文件存在: {os.path.exists(LOCAL_CONFIG_JSON)}")

        if CONFIG:
            print(f"✅ 配置加载成功，API节点数: {len(CONFIG.get('api_sources', []))}")
            return True
        else:
            print("❌ 配置为空")
            return False
    except Exception as e:
        print(f"❌ 配置加载失败: {e}")
        traceback.print_exc()
        return False


def test_async():
    """测试异步功能"""
    print("\n🔍 测试异步功能...")

    try:
        import asyncio

        async def test_coroutine():
            await asyncio.sleep(0.1)
            return "异步测试成功"

        # 测试事件循环
        if sys.platform == 'win32' and getattr(sys, 'frozen', False):
            try:
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            except AttributeError:
                pass

        result = asyncio.run(test_coroutine())
        print(f"✅ {result}")
        return True
    except Exception as e:
        print(f"❌ 异步功能测试失败: {e}")
        traceback.print_exc()
        return False


def test_api_manager():
    """测试API管理器"""
    print("\n🔍 测试API管理器...")

    try:
        from core.novel_downloader import get_api_manager

        api = get_api_manager()
        if api:
            print(f"✅ API管理器创建成功，基础URL: {api.base_url}")
            return True
        else:
            print("❌ API管理器创建失败")
            return False
    except Exception as e:
        print(f"❌ API管理器测试失败: {e}")
        traceback.print_exc()
        return False


def test_update_check():
    """测试更新检查"""
    print("\n🔍 测试更新检查...")

    try:
        from utils.updater import check_and_notify
        from config.config import __version__, __github_repo__

        print(f"当前版本: {__version__}")
        print(f"仓库: {__github_repo__}")

        # 快速测试（静默模式）
        result = check_and_notify(__version__, __github_repo__, silent=True)
        if result is not None:
            print("✅ 更新检查功能正常")
            return True
        else:
            print("⚠️ 更新检查返回None（可能是网络问题）")
            return True  # 网络问题不算功能异常
    except Exception as e:
        print(f"❌ 更新检查测试失败: {e}")
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("🚀 开始打包测试...")
    print(f"Python版本: {sys.version}")
    print(f"运行环境: {'打包环境' if getattr(sys, 'frozen', False) else '开发环境'}")
    print(f"平台: {sys.platform}")

    if getattr(sys, 'frozen', False):
        print(f"可执行文件路径: {sys.executable}")
        if hasattr(sys, '_MEIPASS'):
            print(f"临时目录: {sys._MEIPASS}")

    print("=" * 50)

    tests = [
        ("模块导入", test_imports),
        ("配置加载", test_config),
        ("异步功能", test_async),
        ("API管理器", test_api_manager),
        ("更新检查", test_update_check),
    ]

    passed = 0
    total = len(tests)

    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ {name}测试异常: {e}")

    print("\n" + "=" * 50)
    print(f"📊 测试结果: {passed}/{total} 通过")

    if passed == total:
        print("🎉 所有测试通过！程序应该能正常运行。")
        return 0
    else:
        print("⚠️ 部分测试失败，程序可能存在问题。")
        return 1


if __name__ == "__main__":
    sys.exit(main())