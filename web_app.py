# -*- coding: utf-8 -*-
"""
Web应用程序 - Flask后端，用于HTML GUI
"""

import os
import json
import threading
import queue
import tempfile
import secrets
import time
from flask import Flask, render_template, request, jsonify, send_from_directory, abort
from flask_cors import CORS
import logging
import re

# 禁用Flask默认日志
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)

# 访问令牌（由main.py在启动时设置）
ACCESS_TOKEN = None

def set_access_token(token):
    """设置访问令牌"""
    global ACCESS_TOKEN
    ACCESS_TOKEN = token

# 配置文件路径 - 保存到系统临时目录
TEMP_DIR = tempfile.gettempdir()
CONFIG_FILE = os.path.join(TEMP_DIR, 'fanqie_novel_downloader_config.json')

# 全局变量
download_queue = queue.Queue()
current_download_status = {
    'is_downloading': False,
    'progress': 0,
    'message': '',
    'book_name': '',
    'total_chapters': 0,
    'downloaded_chapters': 0
}
status_lock = threading.Lock()

# 更新下载状态
update_download_status = {
    'is_downloading': False,
    'progress': 0,
    'message': '',
    'filename': '',
    'total_size': 0,
    'downloaded_size': 0,
    'completed': False,
    'error': None,
    'save_path': ''
}
update_lock = threading.Lock()

def get_update_status():
    """获取更新下载状态"""
    with update_lock:
        return update_download_status.copy()

def set_update_status(**kwargs):
    """设置更新下载状态"""
    with update_lock:
        for key, value in kwargs.items():
            if key in update_download_status:
                update_download_status[key] = value

def update_download_worker(url, save_path, filename):
    """更新下载工作线程"""
    try:
        set_update_status(
            is_downloading=True, 
            progress=0, 
            message='正在连接服务器...', 
            filename=filename,
            completed=False,
            error=None,
            save_path=save_path
        )
        
        import requests
        full_path = os.path.join(save_path, filename)
        
        # 支持断点续传（简单的检查文件是否存在）
        # 这里为了安全起见，如果是更新包，最好是重新下载，避免文件损坏
        
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        set_update_status(total_size=total_size, message='开始下载...')
        
        downloaded = 0
        chunk_size = 8192
        
        with open(full_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if not get_update_status()['is_downloading']: # 检查是否取消
                    break
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    progress = int((downloaded / total_size) * 100) if total_size > 0 else 0
                    set_update_status(
                        progress=progress, 
                        downloaded_size=downloaded,
                        message=f'正在下载: {progress}%'
                    )
        
        if get_update_status()['is_downloading']:
            set_update_status(
                is_downloading=False, 
                completed=True, 
                progress=100, 
                message='下载完成'
            )
        else:
            # 被取消
            if os.path.exists(full_path):
                os.remove(full_path)
                
    except Exception as e:
        set_update_status(
            is_downloading=False, 
            error=str(e), 
            message=f'下载失败: {str(e)}'
        )

# 延迟导入重型模块
api = None
api_manager = None
novel_downloader = None
downloader_instance = None

def init_modules():
    """初始化核心模块"""
    global api, api_manager, novel_downloader, downloader_instance
    try:
        from novel_downloader import NovelDownloader, get_api_manager
        novel_downloader = __import__('novel_downloader')
        api = NovelDownloader()
        api_manager = get_api_manager()
        downloader_instance = api
        return True
    except Exception as e:
        print(f"模块加载失败: {e}")
        return False

def get_status():
    """获取当前下载状态"""
    with status_lock:
        return current_download_status.copy()

def update_status(progress=None, message=None, **kwargs):
    """更新下载状态"""
    with status_lock:
        if progress is not None:
            current_download_status['progress'] = progress
        if message is not None:
            current_download_status['message'] = message
        for key, value in kwargs.items():
            if key in current_download_status:
                current_download_status[key] = value

def download_worker():
    """后台下载工作线程"""
    while True:
        try:
            task = download_queue.get(timeout=1)
            if task is None:
                break
            
            book_id = task.get('book_id')
            save_path = task.get('save_path', os.getcwd())
            file_format = task.get('file_format', 'txt')
            start_chapter = task.get('start_chapter', None)
            end_chapter = task.get('end_chapter', None)
            selected_chapters = task.get('selected_chapters', None)
            
            update_status(is_downloading=True, progress=0, message='初始化...')
            
            if not api:
                update_status(message='API未初始化', progress=0, is_downloading=False)
                continue
            
            try:
                # 设置进度回调
                def progress_callback(progress, message):
                    if progress >= 0:
                        update_status(progress=progress, message=message)
                    else:
                        update_status(message=message)
                
                # 强制刷新 API 实例，防止线程间 Session 污染
                if hasattr(api_manager, '_tls'):
                    api_manager._tls = threading.local()
                
                # 获取书籍信息
                update_status(message='正在连接服务器获取书籍信息...')
                
                # 增加超时重试机制
                book_detail = None
                for _ in range(3):
                    book_detail = api_manager.get_book_detail(book_id)
                    if book_detail:
                        break
                    time.sleep(1)
                
                if not book_detail:
                    update_status(message='获取书籍信息失败，请检查网络或书籍ID', is_downloading=False)
                    continue
                
                book_name = book_detail.get('book_name', book_id)
                update_status(book_name=book_name, message=f'准备下载《{book_name}》...')
                
                # 执行下载
                update_status(message='启动下载引擎...')
                success = api.run_download(book_id, save_path, file_format, start_chapter, end_chapter, selected_chapters, progress_callback)
                
                if success:
                    update_status(progress=100, message=f'✅ 下载完成！已保存至 {save_path}', is_downloading=False)
                else:
                    update_status(message='下载过程中断或失败', progress=0, is_downloading=False)
                    
            except Exception as e:
                import traceback
                traceback.print_exc()
                error_str = str(e)
                update_status(message=f'❌ 下载异常: {error_str}', progress=0, is_downloading=False)
                print(f"下载异常: {error_str}")
        
        except queue.Empty:
            continue
        except Exception as e:
            error_str = str(e)
            update_status(message=f'❌ 错误: {error_str}', progress=0, is_downloading=False)
            print(f"工作线程异常: {error_str}")

# 启动后台下载线程
download_thread = threading.Thread(target=download_worker, daemon=True)
download_thread.start()

# ===================== 访问控制中间件 =====================

@app.before_request
def check_access():
    """请求前验证访问令牌"""
    # 静态文件不需要验证
    if request.path.startswith('/static/'):
        return None
    
    # 验证token
    if ACCESS_TOKEN is not None:
        token = request.args.get('token') or request.headers.get('X-Access-Token')
        if token != ACCESS_TOKEN:
            return jsonify({'error': 'Forbidden'}), 403
    
    return None

# ===================== API 路由 =====================

@app.route('/')
def index():
    """主页"""
    token = request.args.get('token', '')
    return render_template('index.html', access_token=token)

@app.route('/api/init', methods=['POST'])
def api_init():
    """初始化模块"""
    if init_modules():
        return jsonify({'success': True, 'message': '模块加载完成'})
    return jsonify({'success': False, 'message': '模块加载失败'}), 500

@app.route('/api/status', methods=['GET'])
def api_status():
    """获取下载状态"""
    return jsonify(get_status())

@app.route('/api/book-info', methods=['POST'])
def api_book_info():
    """获取书籍详情和章节列表"""
    print(f"[DEBUG] Received book-info request: {request.data}")
    data = request.get_json()
    book_id = data.get('book_id', '').strip()
    
    if not book_id:
        return jsonify({'success': False, 'message': '请输入书籍ID或URL'}), 400
    
    # 从URL中提取ID
    if 'fanqienovel.com' in book_id:
        match = re.search(r'/page/(\d+)', book_id)
        if match:
            book_id = match.group(1)
        else:
            return jsonify({'success': False, 'message': 'URL格式错误'}), 400
    
    # 验证book_id是数字
    if not book_id.isdigit():
        return jsonify({'success': False, 'message': '书籍ID应为纯数字'}), 400
    
    if not api:
        return jsonify({'success': False, 'message': 'API未初始化'}), 500
    
    try:
        # 获取书籍信息
        print(f"[DEBUG] calling get_book_detail for {book_id}")
        book_detail = api_manager.get_book_detail(book_id)
        print(f"[DEBUG] book_detail result: {str(book_detail)[:100]}")
        if not book_detail:
            return jsonify({'success': False, 'message': '获取书籍信息失败'}), 400
        
        # 获取章节列表
        print(f"[DEBUG] calling get_chapter_list for {book_id}")
        chapters_data = api_manager.get_chapter_list(book_id)
        print(f"[DEBUG] chapters_data type: {type(chapters_data)}")
        if not chapters_data:
            return jsonify({'success': False, 'message': '无法获取章节列表'}), 400
        
        chapters = []
        if isinstance(chapters_data, dict):
            all_item_ids = chapters_data.get("allItemIds", [])
            chapter_list = chapters_data.get("chapterListWithVolume", [])
            
            if chapter_list:
                idx = 0
                for volume in chapter_list:
                    if isinstance(volume, list):
                        for ch in volume:
                            if isinstance(ch, dict):
                                item_id = ch.get("itemId") or ch.get("item_id")
                                title = ch.get("title", f"第{idx+1}章")
                                if item_id:
                                    chapters.append({"id": str(item_id), "title": title, "index": idx})
                                    idx += 1
            else:
                for idx, item_id in enumerate(all_item_ids):
                    chapters.append({"id": str(item_id), "title": f"第{idx+1}章", "index": idx})
        elif isinstance(chapters_data, list):
            for idx, ch in enumerate(chapters_data):
                item_id = ch.get("item_id") or ch.get("chapter_id")
                title = ch.get("title", f"第{idx+1}章")
                if item_id:
                    chapters.append({"id": str(item_id), "title": title, "index": idx})
        
        print(f"[DEBUG] Found {len(chapters)} chapters")

        # 返回书籍信息和章节列表
        return jsonify({
            'success': True,
            'data': {
                'book_id': book_id,
                'book_name': book_detail.get('book_name', '未知小说'),
                'author': book_detail.get('author', '未知作者'),
                'abstract': book_detail.get('abstract', '暂无简介'),
                'cover_url': book_detail.get('thumb_url', ''),
                'chapters': chapters
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'获取信息失败: {str(e)}'}), 500

@app.route('/api/download', methods=['POST'])
def api_download():
    """开始下载"""
    data = request.get_json()
    
    if get_status()['is_downloading']:
        return jsonify({'success': False, 'message': '已有下载任务在进行'}), 400
    
    book_id = data.get('book_id', '').strip()
    save_path = data.get('save_path', os.path.expanduser('~\\Downloads')).strip()
    file_format = data.get('file_format', 'txt')
    start_chapter = data.get('start_chapter')
    end_chapter = data.get('end_chapter')
    selected_chapters = data.get('selected_chapters')
    
    if not book_id:
        return jsonify({'success': False, 'message': '请输入书籍ID或URL'}), 400
    
    # 从URL中提取ID
    if 'fanqienovel.com' in book_id:
        match = re.search(r'/page/(\d+)', book_id)
        if match:
            book_id = match.group(1)
        else:
            return jsonify({'success': False, 'message': 'URL格式错误'}), 400
    
    # 验证book_id是数字
    if not book_id.isdigit():
        return jsonify({'success': False, 'message': '书籍ID应为纯数字'}), 400
    
    # 确保路径存在
    try:
        os.makedirs(save_path, exist_ok=True)
    except Exception as e:
        return jsonify({'success': False, 'message': f'保存路径错误: {str(e)}'}), 400
    
    # 添加到下载队列
    task = {
        'book_id': book_id,
        'save_path': save_path,
        'file_format': file_format,
        'start_chapter': start_chapter,
        'end_chapter': end_chapter,
        'selected_chapters': selected_chapters
    }
    download_queue.put(task)
    update_status(is_downloading=True, progress=0, message='任务已加入队列')
    
    return jsonify({'success': True, 'message': '下载任务已开始'})

@app.route('/api/cancel', methods=['POST'])
def api_cancel():
    """取消下载"""
    if downloader_instance:
        try:
            downloader_instance.cancel_download()
            update_status(is_downloading=False, progress=0, message='⏹ 下载已取消')
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 400
    return jsonify({'success': False}), 400

@app.route('/api/config/save-path', methods=['GET', 'POST'])
def api_config_save_path():
    """获取/保存下载路径配置"""
    
    if request.method == 'GET':
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    return jsonify({'path': config.get('save_path', os.path.expanduser('~\\Downloads'))})
        except:
            pass
        return jsonify({'path': os.path.expanduser('~\\Downloads')})
    
    else:
        data = request.get_json()
        path = data.get('path', os.path.expanduser('~\\Downloads'))
        
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                config = {}
            
            config['save_path'] = path
            
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/select-folder', methods=['POST'])
def api_select_folder():
    """弹出文件夹选择对话框"""
    try:
        import tkinter as tk
        from tkinter import filedialog
        
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        
        current_path = request.get_json().get('current_path', os.path.expanduser('~\\Downloads'))
        
        folder_path = filedialog.askdirectory(
            title='选择小说保存目录',
            initialdir=current_path if os.path.exists(current_path) else os.path.expanduser('~\\Downloads')
        )
        
        root.destroy()
        
        if folder_path:
            try:
                if os.path.exists(CONFIG_FILE):
                    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                else:
                    config = {}
                
                config['save_path'] = folder_path
                
                with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                    json.dump(config, f, ensure_ascii=False, indent=2)
                
                return jsonify({'success': True, 'path': folder_path})
            except Exception as e:
                return jsonify({'success': False, 'message': str(e)}), 500
        else:
            return jsonify({'success': False, 'message': '未选择文件夹'})
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'文件夹选择失败: {str(e)}'}), 500

@app.route('/api/check-update', methods=['GET'])
def api_check_update():
    """检查更新"""
    try:
        from updater import check_and_notify
        from config import __version__, __github_repo__
        
        update_info = check_and_notify(__version__, __github_repo__, silent=True)
        
        if update_info:
            return jsonify({
                'success': True,
                'has_update': update_info.get('has_update', False),
                'data': update_info
            })
        else:
            return jsonify({
                'success': True,
                'has_update': False
            })
    except Exception as e:
        return jsonify({'success': False, 'message': f'检查更新失败: {str(e)}'}), 500

@app.route('/api/get-update-assets', methods=['GET'])
def api_get_update_assets():
    """获取更新文件的下载选项"""
    try:
        from updater import get_latest_release, parse_release_assets
        from config import __github_repo__
        import platform
        
        # 获取最新版本信息
        latest_info = get_latest_release(__github_repo__)
        if not latest_info:
            return jsonify({'success': False, 'message': '无法获取版本信息'}), 500
        
        # 检测当前平台
        system = platform.system().lower()
        if system == 'darwin':
            platform_name = 'macos'
        elif system == 'linux':
            platform_name = 'linux'
        else:
            platform_name = 'windows'
        
        # 解析 assets
        assets = parse_release_assets(latest_info, platform_name)
        
        return jsonify({
            'success': True,
            'platform': platform_name,
            'assets': assets,
            'release_url': latest_info.get('html_url', '')
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取下载选项失败: {str(e)}'}), 500

@app.route('/api/download-update', methods=['POST'])
def api_download_update():
    """开始下载更新包"""
    data = request.get_json()
    url = data.get('url')
    filename = data.get('filename')
    
    if not url or not filename:
        return jsonify({'success': False, 'message': '参数错误'}), 400
        
    # 使用默认下载路径或配置路径
    save_path = os.path.expanduser('~\\Downloads')
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                save_path = config.get('save_path', save_path)
        except:
            pass
            
    if not os.path.exists(save_path):
        try:
            os.makedirs(save_path)
        except:
            save_path = os.path.expanduser('~\\Downloads')

    # 启动下载线程
    t = threading.Thread(
        target=update_download_worker, 
        args=(url, save_path, filename),
        daemon=True
    )
    t.start()
    
    return jsonify({'success': True, 'message': '开始下载'})

@app.route('/api/update-status', methods=['GET'])
def api_get_update_status_route():
    """获取更新下载状态"""
    return jsonify(get_update_status())

@app.route('/api/can-auto-update', methods=['GET'])
def api_can_auto_update():
    """检查是否支持自动更新"""
    try:
        from updater import can_auto_update
        return jsonify({
            'success': True,
            'can_auto_update': can_auto_update()
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/apply-update', methods=['POST'])
def api_apply_update():
    """应用已下载的更新（仅 Windows）"""
    try:
        from updater import apply_windows_update, can_auto_update
        import sys
        
        # 检查是否支持自动更新
        if not can_auto_update():
            return jsonify({
                'success': False, 
                'message': '当前环境不支持自动更新，请手动替换程序文件'
            }), 400
        
        # 获取下载的更新文件信息
        status = get_update_status()
        if not status.get('completed'):
            return jsonify({
                'success': False, 
                'message': '更新文件尚未下载完成'
            }), 400
        
        save_path = status.get('save_path', '')
        filename = status.get('filename', '')
        
        if not save_path or not filename:
            return jsonify({
                'success': False, 
                'message': '更新文件信息不完整'
            }), 400
        
        new_exe_path = os.path.join(save_path, filename)
        
        if not os.path.exists(new_exe_path):
            return jsonify({
                'success': False, 
                'message': f'更新文件不存在: {new_exe_path}'
            }), 400
        
        # 应用更新
        if apply_windows_update(new_exe_path):
            # 更新成功启动，准备退出程序
            def delayed_exit():
                import time
                time.sleep(1)
                os._exit(0)
            
            threading.Thread(target=delayed_exit, daemon=True).start()
            
            return jsonify({
                'success': True, 
                'message': '更新程序已启动，应用即将关闭并自动更新...'
            })
        else:
            return jsonify({
                'success': False, 
                'message': '启动更新程序失败'
            }), 500
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'应用更新失败: {str(e)}'}), 500

@app.route('/api/open-folder', methods=['POST'])
def api_open_folder():
    """打开文件夹"""
    data = request.get_json()
    path = data.get('path')
    
    if not path or not os.path.exists(path):
        return jsonify({'success': False, 'message': '路径不存在'}), 400
        
    try:
        if os.name == 'nt':
            os.startfile(path)
        elif os.name == 'posix':
            subprocess.call(['open', path])
        else:
            subprocess.call(['xdg-open', path])
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

if __name__ == '__main__':
    print(f'配置文件位置: {CONFIG_FILE}')
    app.run(host='127.0.0.1', port=5000, debug=False)
