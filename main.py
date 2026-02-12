# -*- coding: utf-8 -*-
"""
主入口 - 启动 Web 应用并用 PyWebView 显示
支持多平台：Windows, macOS, Linux, Termux
"""

import sys
import os
import traceback
from pathlib import Path
from utils.runtime_bootstrap import ensure_runtime_path, apply_packaging_fixes, apply_encoding_fixes

try:
    from utils.dependency_manager import auto_manage_dependencies
    DEP_MANAGER_AVAILABLE = True
except Exception:
    DEP_MANAGER_AVAILABLE = False

# 使用最底层的方式写入错误信息（不依赖print）
def _write_error(msg):
    """直接写入stderr，不经过任何包装"""
    try:
        if hasattr(sys, '__stderr__') and sys.__stderr__:
            sys.__stderr__.write(msg + '\n')
            sys.__stderr__.flush()
        elif hasattr(sys, 'stderr') and sys.stderr:
            sys.stderr.write(msg + '\n')
            sys.stderr.flush()
    except Exception:
        pass

# 全局异常处理 - 确保打包后能看到错误
def _global_exception_handler(exc_type, exc_value, exc_tb):
    """全局异常处理器，确保错误信息不会丢失"""
    try:
        error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))
        _write_error("\n" + "="*50)
        _write_error("程序发生错误:")
        _write_error(error_msg)
        _write_error("="*50)
    except Exception as e:
        _write_error(f"无法格式化错误: {e}")
    
    # 打包环境下暂停以便查看错误
    if getattr(sys, 'frozen', False):
        try:
            _write_error("\n按回车键退出...")
            input()
        except Exception:
            import time
            time.sleep(10)

sys.excepthook = _global_exception_handler

# 添加打包环境路径 - 必须在所有其他导入之前
_base = ensure_runtime_path()
if getattr(sys, 'frozen', False):
    _write_error(f"[DEBUG] 打包环境路径: {_base}")
    _write_error(f"[DEBUG] sys.path: {sys.path[:3]}...")


def _ensure_source_dependencies() -> None:
    """源码运行模式下自动补齐缺失依赖。"""
    if getattr(sys, 'frozen', False):
        return
    if not DEP_MANAGER_AVAILABLE:
        return

    root = Path(_base)
    targets = ["main.py", "core", "utils", "web", "config"]
    print("正在检查并自动管理依赖（含 requirements 同步）...")
    result = auto_manage_dependencies(
        project_root=root,
        targets=targets,
        python_executable=sys.executable,
        requirements_file=root / "config" / "requirements.txt",
        state_file=root / ".deps_state.json",
        extra_packages=["requests", "rich", "InquirerPy", "aiohttp"],
        install_missing=True,
        sync_requirements=True,
        pin_versions=True,
        skip_if_unchanged=True,
    )

    installed = result.get("installed_packages", [])
    if installed:
        print(f"已安装依赖: {', '.join(installed)}")


_ensure_source_dependencies()

# 打包兼容性修复
apply_packaging_fixes(lambda msg: _write_error(f"[DEBUG] {msg}"))

# 编码处理
_safe_print = apply_encoding_fixes(lambda msg: _write_error(f"[DEBUG] {msg}"))
if _safe_print:
    print = _safe_print

# 禁用 SSL 警告
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import subprocess
import time
import threading
import requests
import secrets
import socket
from utils.platform_utils import (
    detect_platform,
    get_window_config,
    is_feature_available,
    get_feature_status_report,
    get_unavailable_feature_message,
    WindowPositionManager
)

def find_free_port():
    """查找一个可用的随机端口"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port

def run_flask_app(port, access_token):
    """在后台启动 Flask 应用"""
    try:
        # 获取脚本所在目录
        script_dir = Path(__file__).parent
        os.chdir(script_dir)
        
        # 启动 Flask 应用
        from web.web_app import app, set_access_token
        
        # 设置访问令牌
        set_access_token(access_token)
        
        # 使用线程运行 Flask，不使用调试模式
        app.run(
            host='127.0.0.1',
            port=port,
            debug=False,
            use_reloader=False,
            threaded=True
        )
    except Exception as e:
        print(f"Flask 启动失败: {e}")
        sys.exit(1)

def open_web_interface(port, access_token):
    """用浏览器打开 Web 界面"""
    try:
        url = f'http://127.0.0.1:{port}?token={access_token}'
        
        # 尝试使用 PyWebView
        try:
            import webview
            
            # 窗口位置管理器
            position_manager = WindowPositionManager()
            
            # 窗口控制 API (延迟绑定)
            _window = None
            
            class WindowApi:
                def __init__(self):
                    self._is_maximized = False
                    self._drag_start_x = 0
                    self._drag_start_y = 0

                def minimize_window(self):
                    if _window:
                        _window.minimize()
                
                def toggle_maximize(self):
                    if _window:
                        # 优先处理全屏状态
                        is_fullscreen = getattr(_window, 'fullscreen', False)
                        
                        if is_fullscreen:
                            if hasattr(_window, 'toggle_fullscreen'):
                                _window.toggle_fullscreen()
                            else:
                                _window.restore()
                            self._is_maximized = False
                        elif self._is_maximized:
                            _window.restore()
                            self._is_maximized = False
                        else:
                            _window.maximize()
                            self._is_maximized = True
                
                def close_window(self):
                    if _window:
                        # 保存窗口位置
                        try:
                            position_manager.save_position(
                                _window.x, _window.y,
                                _window.width, _window.height,
                                self._is_maximized
                            )
                        except Exception:
                            pass
                        _window.destroy()
                
                def start_drag(self, offset_x, offset_y):
                    """开始拖动窗口，记录鼠标在窗口内的偏移"""
                    if _window and not self._is_maximized:
                        self._drag_start_x = offset_x
                        self._drag_start_y = offset_y
                
                def drag_window(self, screen_x, screen_y):
                    """拖动窗口到新位置"""
                    if _window and not self._is_maximized:
                        new_x = screen_x - self._drag_start_x
                        new_y = screen_y - self._drag_start_y
                        _window.move(new_x, new_y)
            
            api = WindowApi()
            
            def on_closed():
                # 保存窗口位置
                if _window:
                    try:
                        position_manager.save_position(
                            _window.x, _window.y,
                            _window.width, _window.height,
                            api._is_maximized
                        )
                    except Exception:
                        pass
                print("程序已关闭")
            
            # 获取平台适配的窗口配置
            window_config = get_window_config()
            
            # 获取恢复的窗口位置
            restored_position = position_manager.get_restored_position(
                window_config['width'],
                window_config['height']
            )
            
            # 创建窗口 (使用恢复的位置)
            _window = webview.create_window(
                title=window_config['title'],
                url=url,
                x=restored_position['x'],
                y=restored_position['y'],
                width=restored_position['width'],
                height=restored_position['height'],
                min_size=window_config['min_size'],
                background_color=window_config['background_color'],
                frameless=window_config['frameless'],
                js_api=api
            )
            
            # 设置最大化状态
            if restored_position.get('maximized', False):
                api._is_maximized = True
            
            try:
                webview.start()
            except AttributeError as e:
                # 处理 'NoneType' object has no attribute 'BrowserProcessId' 等浏览器引擎初始化错误
                error_msg = str(e)
                if 'BrowserProcessId' in error_msg or 'NoneType' in error_msg:
                    print("WebView 初始化失败: " + error_msg)
                    print("将切换到浏览器模式")
                    raise ImportError("WebView engine failed")
                else:
                    raise
            except Exception as e:
                # 处理其他 webview 相关错误
                error_msg = str(e)
                if any(keyword in error_msg.lower() for keyword in ['browser', 'webview', 'edge', 'chromium']):
                    print("WebView 启动失败: " + error_msg)
                    print("将切换到浏览器模式")
                    raise ImportError("WebView failed to start")
                else:
                    raise
            
        except ImportError:
            print("当前环境不可用 WebView，将使用浏览器打开")
            import webbrowser
            time.sleep(2)  # 等待 Flask 启动
            webbrowser.open(url)
            
            # 保持运行
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n程序已关闭")
                sys.exit(0)
    
    except Exception as e:
        print("界面启动失败: " + str(e))
        sys.exit(1)

def main():
    """主函数"""
    print("=" * 50)
    print("番茄小说下载器")
    print("=" * 50)
    
    # 检测平台信息
    platform_info = detect_platform()
    print(f"\n平台: {platform_info.os_name} ({platform_info.os_version})")
    if platform_info.desktop_env:
        print(f"桌面环境: {platform_info.desktop_env}")
    if platform_info.is_termux:
        print("运行环境: Termux (Android)")
        print("\n提示: Termux 环境请使用 CLI 模式: python cli.py --help")
    
    # 显示版本信息
    from config.config import __version__, __github_repo__, CONFIG
    print(f"版本: {__version__}")

    # 云同步（仅 GitHub Actions 打包发布版）
    try:
        from utils.cloud_sync import should_run_cloud_sync, ensure_cloud_runtime_synced

        if should_run_cloud_sync():
            print("正在执行云同步检查...")
            sync_result = ensure_cloud_runtime_synced(__github_repo__)
            status = sync_result.get("status", "unknown")
            if status == "ok":
                print(
                    "云同步完成 "
                    f"(来源: {sync_result.get('source', '-')}, "
                    f"更新: {sync_result.get('updated', '0')}, "
                    f"新增: {sync_result.get('added', '0')}, "
                    f"删除: {sync_result.get('deleted', '0')})"
                )
            else:
                print(f"云同步状态: {status} - {sync_result.get('message', '')}")
    except Exception as sync_error:
        print(f"⚠ 云同步异常（不影响启动）: {sync_error}")
    
    # 显示配置文件路径
    import tempfile
    config_file = os.path.join(tempfile.gettempdir(), 'fanqie_novel_downloader_config.json')
    print(f"配置文件路径: {config_file}")
    
    # 生成随机访问令牌
    access_token = secrets.token_urlsafe(32)
    
    # 检查是否存在内置的 WebView2 Runtime (用于 Standalone 版本)
    if getattr(sys, 'frozen', False):
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        webview2_path = os.path.join(base_path, 'WebView2')
        if os.path.exists(webview2_path):
            print(f"使用打包内置 WebView2: {webview2_path}")
            os.environ["WEBVIEW2_BROWSER_EXECUTABLE_FOLDER"] = webview2_path
    
    # 查找可用端口
    port = find_free_port()
    
    print("\n正在启动...")
    
    # 在后台线程中启动 Flask
    flask_thread = threading.Thread(target=run_flask_app, args=(port, access_token), daemon=True)
    flask_thread.start()
    
    # 等待 Flask 启动
    print("等待服务启动...")
    max_retries = 30
    url = f'http://127.0.0.1:{port}?token={access_token}'
    for i in range(max_retries):
        try:
            response = requests.get(url, timeout=1)
            if response.status_code == 200:
                print("服务已启动")
                break
        except Exception:
            if i < max_retries - 1:
                time.sleep(0.5)
            else:
                print("服务启动超时")
                sys.exit(1)

    # 检查更新(异步，不阻塞启动) - 优化版：移除延迟，增加超时控制
    def check_update_async():
        try:
            from utils.updater import check_and_notify
            # 移除 time.sleep(2) 延迟，立即开始检查
            # 使用更短的超时时间，避免长时间阻塞
            check_and_notify(__version__, __github_repo__, silent=False)
        except Exception as e:
            # 显示更新检测失败的提示，但不影响程序运行
            print(f"\n⚠ 更新检测失败: {str(e)}")
            print("💡 这不影响程序正常使用，可以手动检查更新:")
            print(f"   GitHub: {__github_repo__}/releases")

    # 使用守护线程，程序退出时自动结束
    update_thread = threading.Thread(target=check_update_async, daemon=True)
    update_thread.start()

    # 同步测试API节点并选择最优节点（等待测试完成）
    print("\n正在测试API节点可用性和速度...")
    optimal_node = None
    node_tester = None

    def test_api_nodes_async():
        """后台线程测试API节点"""
        nonlocal optimal_node, node_tester
        try:
            import asyncio
            from utils.node_manager import test_and_select_optimal_node, initialize_node_management, get_node_tester, get_health_monitor

            # 在新的事件循环中运行异步测试
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                # 设置15秒超时（测试8个节点需要更多时间）
                optimal_node = loop.run_until_complete(
                    asyncio.wait_for(test_and_select_optimal_node(CONFIG), timeout=15.0)
                )
                if optimal_node:
                    print(f"✓ 已选择最优API节点: {optimal_node}")
                else:
                    print("❌ 所有API节点都不可用")
                    print("=" * 50)
                    print("程序无法启动，原因如下：")
                    print("1. 网络连接问题")
                    print("2. 所有API节点都已下线")
                    print("3. 防火墙或代理拦截")
                    print("4. 节点返回防护页面（非JSON格式）")
                    print("=" * 50)
                    print("请联系开发者修复节点列表")
                    print(f"GitHub: {__github_repo__}")
                    print("=" * 50)
                    # 退出程序
                    sys.exit(1)

                # 初始化节点管理模块
                node_tester = get_node_tester()
                if node_tester:
                    status_cache, health_monitor = initialize_node_management(node_tester)
                    health_monitor.start_monitoring()
                    print("✓ 节点健康监控已启动")

            except asyncio.TimeoutError:
                print("⚠ API节点测试超时（15秒），将使用默认配置")
            except Exception as e:
                print(f"⚠ API节点测试异常: {e}")
            finally:
                loop.close()
        except Exception as e:
            print(f"⚠ API节点测试初始化异常: {e}")

    # 在后台线程中执行节点测试
    test_thread = threading.Thread(target=test_api_nodes_async, daemon=True)
    test_thread.start()
    
    # 检查 GUI 可用性并选择合适的界面模式
    if platform_info.is_termux:
        # Termux 环境：提示使用 CLI
        print("\n" + "=" * 50)
        print("Termux 环境不支持 GUI，请使用命令行模式:")
        print("  python cli.py search <关键词>")
        print("  python cli.py download <书籍ID>")
        print("  python cli.py info <书籍ID>")
        print("=" * 50)
        print(f"\n服务器已启动: http://127.0.0.1:{port}")
        print("您也可以在浏览器中访问上述地址使用 Web 界面")
        
        # 保持运行
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n程序已关闭")
            sys.exit(0)
    elif not platform_info.is_gui_available:
        # GUI 不可用：使用浏览器模式
        print("\n" + "GUI 不可用，将使用浏览器模式...")
        
        import webbrowser
        time.sleep(1)
        webbrowser.open(url)
        
        # 保持运行
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n程序已关闭")
            sys.exit(0)
    else:
        # 正常 GUI 模式 - 先打开界面
        print("\n正在打开界面...")
        open_web_interface(port, access_token)
        
        # 等待节点测试完成（GUI 已打开）
        print("等待节点测试完成...")
        test_thread.join(timeout=20)
        if test_thread.is_alive():
            print("⚠ 节点测试超时，但程序将继续运行")

if __name__ == '__main__':
    main()
