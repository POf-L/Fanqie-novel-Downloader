# -*- coding: utf-8 -*-
"""
主入口 - 启动 Web 应用并用 PyWebView 显示
支持多平台：Windows, macOS, Linux, Termux
"""

import os
import sys
import subprocess
import time
import threading
import requests
import secrets
import socket
from pathlib import Path
from locales import t
from platform_utils import (
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
        from web_app import app, set_access_token
        
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
        print(t("main_flask_fail", e))
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
                print(t("main_app_closed"))
            
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
                    print(t("main_webview_init_fail", error_msg))
                    print(t("main_switch_browser"))
                    raise ImportError("WebView engine failed")
                else:
                    raise
            except Exception as e:
                # 处理其他 webview 相关错误
                error_msg = str(e)
                if any(keyword in error_msg.lower() for keyword in ['browser', 'webview', 'edge', 'chromium']):
                    print(t("main_webview_fail", error_msg))
                    print(t("main_switch_browser"))
                    raise ImportError("WebView failed to start")
                else:
                    raise
            
        except ImportError:
            print(t("main_webview_unavailable"))
            import webbrowser
            time.sleep(2)  # 等待 Flask 启动
            webbrowser.open(url)
            
            # 保持运行
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n" + t("main_app_closed"))
                sys.exit(0)
    
    except Exception as e:
        print(t("main_interface_fail", e))
        sys.exit(1)

def main():
    """主函数"""
    print("=" * 50)
    print(t("main_title"))
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
    from config import __version__, __github_repo__
    print(t("main_version", __version__))
    
    # 显示配置文件路径
    import tempfile
    config_file = os.path.join(tempfile.gettempdir(), 'fanqie_novel_downloader_config.json')
    print(t("main_config_path", config_file))
    
    # 生成随机访问令牌
    access_token = secrets.token_urlsafe(32)
    
    # 检查是否存在内置的 WebView2 Runtime (用于 Standalone 版本)
    if getattr(sys, 'frozen', False):
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        webview2_path = os.path.join(base_path, 'WebView2')
        if os.path.exists(webview2_path):
            print(t("main_webview2_config", webview2_path))
            os.environ["WEBVIEW2_BROWSER_EXECUTABLE_FOLDER"] = webview2_path
    
    # 查找可用端口
    port = find_free_port()
    
    # 检查更新(异步，不阻塞启动)
    def check_update_async():
        try:
            from updater import check_and_notify
            import time
            time.sleep(2)
            check_and_notify(__version__, __github_repo__, silent=False)
        except Exception:
            pass
    
    update_thread = threading.Thread(target=check_update_async, daemon=True)
    update_thread.start()
    
    # 检查依赖
    print("\n" + t("main_check_deps"))
    required_packages = {
        'flask': 'Flask',
        'flask_cors': 'Flask-CORS',
    }
    
    missing_packages = []
    for module, name in required_packages.items():
        try:
            __import__(module)
            print(f"[OK] {name}")
        except ImportError:
            print(f"[X] {name}")
            missing_packages.append(name)
    
    if missing_packages:
        print(f"\n{t('main_missing_deps', ', '.join(missing_packages))}")
        print(t("main_install_deps"))
        sys.exit(1)
    
    print("\n" + t("main_starting"))
    
    # 在后台线程中启动 Flask
    flask_thread = threading.Thread(target=run_flask_app, args=(port, access_token), daemon=True)
    flask_thread.start()
    
    # 等待 Flask 启动
    print(t("main_wait_server"))
    max_retries = 30
    url = f'http://127.0.0.1:{port}?token={access_token}'
    for i in range(max_retries):
        try:
            response = requests.get(url, timeout=1)
            if response.status_code == 200:
                print(t("main_server_started"))
                break
        except:
            if i < max_retries - 1:
                time.sleep(0.5)
            else:
                print(t("main_server_timeout"))
                sys.exit(1)
    
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
            print("\n" + t("main_app_closed"))
            sys.exit(0)
    elif not platform_info.is_gui_available:
        # GUI 不可用：使用浏览器模式
        print("\n" + get_unavailable_feature_message('gui_webview'))
        print("将使用浏览器模式...")
        
        import webbrowser
        time.sleep(1)
        webbrowser.open(url)
        
        # 保持运行
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n" + t("main_app_closed"))
            sys.exit(0)
    else:
        # 正常 GUI 模式
        print("\n" + t("main_opening_interface"))
        open_web_interface(port, access_token)

if __name__ == '__main__':
    main()
