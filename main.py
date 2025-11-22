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
        print(f"Flask 应用启动失败: {e}")
        sys.exit(1)

def open_web_interface(port, access_token):
    """用浏览器打开 Web 界面"""
    try:
        url = f'http://127.0.0.1:{port}?token={access_token}'
        
        # 尝试使用 PyWebView
        try:
            import webview
            
            def on_closed():
                print("应用已关闭")
            
            # 创建窗口
            webview.create_window(
                title='番茄小说下载器',
                url=url,
                width=1200,
                height=800,
                min_size=(1000, 700),
                background_color='#FAFAFA'
            )
            
            try:
                webview.start()
            except AttributeError as e:
                # 处理 'NoneType' object has no attribute 'BrowserProcessId' 等浏览器引擎初始化错误
                error_msg = str(e)
                if 'BrowserProcessId' in error_msg or 'NoneType' in error_msg:
                    print(f"PyWebView 浏览器引擎初始化失败: {error_msg}")
                    print("自动切换到系统浏览器...")
                    raise ImportError("WebView engine failed")
                else:
                    raise
            except Exception as e:
                # 处理其他 webview 相关错误
                error_msg = str(e)
                if any(keyword in error_msg.lower() for keyword in ['browser', 'webview', 'edge', 'chromium']):
                    print(f"PyWebView 启动失败: {error_msg}")
                    print("自动切换到系统浏览器...")
                    raise ImportError("WebView failed to start")
                else:
                    raise
            
        except ImportError:
            print("PyWebView 未安装或不可用，使用系统浏览器打开...")
            import webbrowser
            time.sleep(2)  # 等待 Flask 启动
            webbrowser.open(url)
            
            # 保持运行
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n应用已关闭")
                sys.exit(0)
    
    except Exception as e:
        print(f"打开界面失败: {e}")
        sys.exit(1)

def main():
    """主函数"""
    print("=" * 50)
    print("番茄小说下载器 - Web 版")
    print("=" * 50)
    
    # 显示版本信息
    from config import __version__, __github_repo__
    print(f"当前版本: {__version__}")
    
    # 显示配置文件路径
    import tempfile
    config_file = os.path.join(tempfile.gettempdir(), 'fanqie_novel_downloader_config.json')
    print(f"配置文件: {config_file}")
    
    # 生成随机访问令牌
    access_token = secrets.token_urlsafe(32)
    
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
    print("\n检查依赖...")
    required_packages = {
        'flask': 'Flask',
        'flask_cors': 'Flask-CORS',
    }
    
    missing_packages = []
    for module, name in required_packages.items():
        try:
            __import__(module)
            print(f"✓ {name}")
        except ImportError:
            print(f"✗ {name}")
            missing_packages.append(name)
    
    if missing_packages:
        print(f"\n缺少依赖: {', '.join(missing_packages)}")
        print("请运行: pip install flask flask-cors")
        sys.exit(1)
    
    print("\n启动应用...")
    
    # 在后台线程中启动 Flask
    flask_thread = threading.Thread(target=run_flask_app, args=(port, access_token), daemon=True)
    flask_thread.start()
    
    # 等待 Flask 启动
    print("等待服务器启动...")
    max_retries = 30
    url = f'http://127.0.0.1:{port}?token={access_token}'
    for i in range(max_retries):
        try:
            response = requests.get(url, timeout=1)
            if response.status_code == 200:
                print("✓ 服务器已启动")
                break
        except:
            if i < max_retries - 1:
                time.sleep(0.5)
            else:
                print("✗ 服务器启动超时")
                sys.exit(1)
    
    # 打开 Web 界面
    print("\n打开应用界面...")
    open_web_interface(port, access_token)

if __name__ == '__main__':
    main()
