# -*- coding: utf-8 -*-
"""
主入口 - 启动 Web 应用并用 PyWebView 显示
支持多平台：Windows, macOS, Linux, Termux
"""

import sys
import os
import traceback

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
    except:
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
        except:
            import time
            time.sleep(10)

sys.excepthook = _global_exception_handler

# 添加打包环境路径 - 必须在所有其他导入之前
if getattr(sys, 'frozen', False):
    if hasattr(sys, '_MEIPASS'):
        _base = sys._MEIPASS
    else:
        _base = os.path.dirname(sys.executable)
    if _base not in sys.path:
        sys.path.insert(0, _base)
    _write_error(f"[DEBUG] 打包环境路径: {_base}")
    _write_error(f"[DEBUG] sys.path: {sys.path[:3]}...")

# 打包兼容性修复
try:
    from utils.packaging_fixes import apply_all_fixes
    apply_all_fixes()
    _write_error("[DEBUG] packaging_fixes 加载成功")
except ImportError as e:
    _write_error(f"[DEBUG] packaging_fixes 导入失败: {e}")
except Exception as e:
    _write_error(f"[DEBUG] packaging_fixes 执行失败: {e}")

# 编码处理
try:
    from utils.encoding_utils import setup_utf8_encoding, patch_print, safe_print
    setup_utf8_encoding()
    patch_print()
    print = safe_print
    _write_error("[DEBUG] encoding_utils 加载成功")
except ImportError as e:
    _write_error(f"[DEBUG] encoding_utils 导入失败: {e}")
    if sys.platform == 'win32':
        try:
            os.system('chcp 65001 >nul 2>&1')
            os.environ['PYTHONIOENCODING'] = 'utf-8'
        except:
            pass
except Exception as e:
    _write_error(f"[DEBUG] encoding_utils 执行失败: {e}")

import subprocess
import time
import threading
import requests
import secrets
import socket
from pathlib import Path

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
        print(f"[DEBUG] Flask 线程启动，端口: {port}")
        # 获取脚本所在目录
        script_dir = Path(__file__).parent
        os.chdir(script_dir)
        print(f"[DEBUG] 工作目录: {script_dir}")

        # 启动 Flask 应用
        from web.web_app import app, set_access_token
        print("[DEBUG] Flask app 导入成功")

        # 设置访问令牌
        set_access_token(access_token)
        print(f"[DEBUG] Access token 已设置")

        print(f"[DEBUG] 开始启动 Flask 服务器 http://127.0.0.1:{port}")
        # 使用线程运行 Flask，不使用调试模式
        app.run(
            host='127.0.0.1',
            port=port,
            debug=False,
            use_reloader=False,
            threaded=True
        )
    except Exception as e:
        print(f"[ERROR] Flask 应用启动失败: {e}")
        import traceback
        traceback.print_exc()
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
                print("应用已关闭")
            
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
                # Windows 下若 WebView2 不可用，PyWebView 可能回退到 MSHTML 内核，
                # 该内核不支持 ES Modules，前端将无法执行并卡在“正在启动服务器...”界面。
                # 因此这里强制优先使用 Edge Chromium；失败则回退到系统浏览器。
                if sys.platform == 'win32':
                    webview.start(gui='edgechromium')
                else:
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
                if sys.platform == 'win32':
                    # Windows 强制使用 Edge Chromium：失败则直接回退到系统浏览器
                    print(f"PyWebView 启动失败: {error_msg}")
                    print("自动切换到系统浏览器...")
                    raise ImportError("WebView failed to start")
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
    
    # 检测平台信息
    platform_info = detect_platform()
    print(f"\n平台: {platform_info.os_name} ({platform_info.os_version})")
    if platform_info.desktop_env:
        print(f"桌面环境: {platform_info.desktop_env}")
    if platform_info.is_termux:
        print("运行环境: Termux (Android)")
        print("\n提示: Termux 环境请使用 CLI 模式: python cli.py --help")
    
    # 显示版本信息
    from config.config import __version__, __github_repo__
    print(f"当前版本: {__version__}")
    
    # 显示配置文件路径
    from utils.app_data_manager import get_app_config_path
    config_file = get_app_config_path()
    print(f"配置文件: {config_file}")
    
    # 生成随机访问令牌
    access_token = secrets.token_urlsafe(32)
    
    # 检查是否存在内置的 WebView2 Runtime (用于 Standalone 版本)
    if getattr(sys, 'frozen', False):
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        webview2_path = os.path.join(base_path, 'WebView2')
        if os.path.exists(webview2_path):
            print(f"正在配置内置 WebView2: {webview2_path}")
            os.environ["WEBVIEW2_BROWSER_EXECUTABLE_FOLDER"] = webview2_path
    
    # 查找可用端口
    port = find_free_port()
    
    # 检查依赖 - 优化版：并行检查，减少阻塞时间
    print("\n检查依赖...")
    required_packages = {
        'flask': 'Flask',
        'flask_cors': 'Flask-CORS',
    }

    def check_package(module_name):
        """检查单个包是否可用"""
        try:
            __import__(module_name)
            return module_name, True
        except ImportError:
            return module_name, False

    # 并行检查所有依赖
    import concurrent.futures
    missing_packages = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        # 提交所有检查任务
        future_to_module = {
            executor.submit(check_package, module): (module, name)
            for module, name in required_packages.items()
        }

        # 收集结果
        for future in concurrent.futures.as_completed(future_to_module):
            module, name = future_to_module[future]
            try:
                _, available = future.result(timeout=2)  # 2秒超时
                if available:
                    print(f"[OK] {name}")
                else:
                    print(f"[X] {name}")
                    missing_packages.append(name)
            except Exception:
                print(f"[X] {name}")
                missing_packages.append(name)
    
    if missing_packages:
        print(f"\n缺少依赖: {', '.join(missing_packages)}")
        print("请运行: pip install flask flask-cors")
        sys.exit(1)
    
    print("\n启动应用...")
    print(f"[DEBUG] 使用端口: {port}")
    print(f"[DEBUG] Access token 长度: {len(access_token)}")

    # 在后台线程中启动 Flask
    flask_thread = threading.Thread(target=run_flask_app, args=(port, access_token), daemon=True)
    flask_thread.start()
    print("[DEBUG] Flask 后台线程已启动")

    # 不等待 Flask 启动，立即打开界面（前端会轮询检测服务器状态）
    print("[DEBUG] 准备打开应用界面...")
    print(f"[DEBUG] URL: http://127.0.0.1:{port}?token={access_token[:10]}...")
    
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
            print("\n应用已关闭")
            sys.exit(0)
    elif not platform_info.is_gui_available:
        # GUI 不可用：使用浏览器模式
        print("\n" + get_unavailable_feature_message('gui_webview'))
        print("将使用浏览器模式...")
        
        url = f'http://127.0.0.1:{port}?token={access_token}'
        import webbrowser
        time.sleep(1)
        webbrowser.open(url)
        
        # 保持运行
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n应用已关闭")
            sys.exit(0)
    else:
        # 正常 GUI 模式
        print("\n正在打开应用界面...")
        open_web_interface(port, access_token)

if __name__ == '__main__':
    main()
