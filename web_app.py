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
                
                # 获取书籍信息
                update_status(message='获取书籍信息...')
                book_detail = api_manager.get_book_detail(book_id)
                if not book_detail:
                    update_status(message='获取书籍信息失败', is_downloading=False)
                    continue
                
                book_name = book_detail.get('book_name', book_id)
                update_status(book_name=book_name, message=f'准备下载《{book_name}》...')
                
                # 执行下载
                update_status(message='启动下载...')
                success = api.run_download(book_id, save_path, file_format, start_chapter, end_chapter, progress_callback)
                
                if success:
                    update_status(progress=100, message=f'✅ 下载完成！已保存至 {save_path}', is_downloading=False)
                else:
                    update_status(message='下载失败', progress=0, is_downloading=False)
                    
            except Exception as e:
                error_str = str(e)
                update_status(message=f'❌ 下载失败: {error_str}', progress=0, is_downloading=False)
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
        book_detail = api_manager.get_book_detail(book_id)
        if not book_detail:
            return jsonify({'success': False, 'message': '获取书籍信息失败'}), 400
        
        # 获取章节列表
        chapters_data = api_manager.get_chapter_list(book_id)
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
        'end_chapter': end_chapter
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

if __name__ == '__main__':
    print(f'配置文件位置: {CONFIG_FILE}')
    app.run(host='127.0.0.1', port=5000, debug=False)
