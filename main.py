# -*- coding: utf-8 -*-
"""
主入口 - 启动 Web 应用并用 PyWebView 显示
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
            
            # 窗口控制 API (延迟绑定)
            _window = None
            
            class WindowApi:
                def minimize_window(self):
                    if _window:
                        _window.minimize()
                
                def toggle_maximize(self):
                    if _window:
                        is_maximized = hasattr(_window, 'maximized') and _window.maximized
                        is_fullscreen = hasattr(_window, 'fullscreen') and _window.fullscreen
                        if is_maximized or is_fullscreen:
                            _window.restore()
                        else:
                            _window.maximize()
                
                def close_window(self):
                    if _window:
                        _window.destroy()
            
            api = WindowApi()
            
            def on_closed():
                print(t("main_app_closed"))
            
            # 创建窗口 (无边框模式)
            _window = webview.create_window(
                title='番茄小说下载器',
                url=url,
                width=1200,
                height=800,
                min_size=(1000, 700),
                background_color='#0a0a0a',
                frameless=True,
                js_api=api
            )
            
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
    
    # 打开 Web 界面
    print("\n" + t("main_opening_interface"))
    open_web_interface(port, access_token)

if __name__ == '__main__':
    main()
