# -*- coding: utf-8 -*-
"""
Web应用程序 - Flask后端，用于HTML GUI
"""

import os
import json
import threading
import queue
import tempfile
import subprocess
import re
from locales import t
from flask import Flask, render_template, request, jsonify, send_from_directory, abort
from flask_cors import CORS
import logging
import re

# 预先导入版本信息（确保在模块加载时就获取正确版本）
from config import __version__ as APP_VERSION

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

# 配置文件路径 - 保存到系统临时目录（跨平台兼容）
TEMP_DIR = tempfile.gettempdir()
CONFIG_FILE = os.path.join(TEMP_DIR, 'fanqie_novel_downloader_config.json')

def get_default_download_path():
    """获取默认下载路径（跨平台兼容）"""
    import sys
    # 优先使用用户下载目录
    home = os.path.expanduser('~')
    if sys.platform == 'win32':
        # Windows: 尝试使用 Downloads 文件夹
        downloads = os.path.join(home, 'Downloads')
    elif sys.platform == 'darwin':
        # macOS
        downloads = os.path.join(home, 'Downloads')
    else:
        # Linux / Termux / 其他 Unix
        downloads = os.path.join(home, 'Downloads')
        # 如果 Downloads 不存在，尝试使用 XDG 用户目录
        if not os.path.exists(downloads):
            xdg_download = os.environ.get('XDG_DOWNLOAD_DIR')
            if xdg_download and os.path.exists(xdg_download):
                downloads = xdg_download
            else:
                # 回退到用户主目录
                downloads = home
    
    # 确保目录存在
    if not os.path.exists(downloads):
        try:
            os.makedirs(downloads, exist_ok=True)
        except:
            downloads = home
    
    return downloads

# 全局变量
download_queue = queue.Queue()
current_download_status = {
    'is_downloading': False,
    'progress': 0,
    'message': '',
    'book_name': '',
    'total_chapters': 0,
    'downloaded_chapters': 0,
    'messages': []  # 消息队列，存储所有待传递的消息
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
    'save_path': '',
    'temp_file_path': ''  # 临时下载文件路径
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
    """更新下载工作线程 - 下载到临时文件避免权限问题"""
    print(f'[DEBUG] update_download_worker started')
    print(f'[DEBUG]   url: {url}')
    print(f'[DEBUG]   save_path: {save_path}')
    print(f'[DEBUG]   filename: {filename}')
    
    try:
        set_update_status(
            is_downloading=True, 
            progress=0, 
            message=t('web_update_status_connect'), 
            filename=filename,
            completed=False,
            error=None,
            save_path=save_path
        )
        
        import requests
        import tempfile
        
        # 下载到临时目录的 .new 文件，避免覆盖正在运行的程序
        temp_dir = tempfile.gettempdir()
        temp_filename = filename + '.new'
        full_path = os.path.join(temp_dir, temp_filename)
        print(f'[DEBUG]   temp_path: {full_path}')
        
        print(f'[DEBUG] Sending GET request...')
        response = requests.get(url, stream=True, timeout=30)
        print(f'[DEBUG] Response status: {response.status_code}')
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        print(f'[DEBUG] Total size: {total_size} bytes')
        set_update_status(total_size=total_size, message=t('web_update_status_start'))
        
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
                        message=t('web_update_status_dl', progress)
                    )
        
        if get_update_status()['is_downloading']:
            print(f'[DEBUG] Download completed successfully!')
            print(f'[DEBUG] File saved to: {full_path}')
            print(f'[DEBUG] File exists: {os.path.exists(full_path)}')
            if os.path.exists(full_path):
                print(f'[DEBUG] File size: {os.path.getsize(full_path)} bytes')
            # 保存临时文件路径供后续应用更新使用
            set_update_status(
                is_downloading=False, 
                completed=True, 
                progress=100, 
                message=t('web_update_complete'),
                temp_file_path=full_path
            )
        else:
            # 被取消
            print(f'[DEBUG] Download was cancelled')
            if os.path.exists(full_path):
                os.remove(full_path)
                
    except Exception as e:
        import traceback
        print(f'[DEBUG] Download failed with exception:')
        print(f'[DEBUG]   {type(e).__name__}: {str(e)}')
        traceback.print_exc()
        set_update_status(
            is_downloading=False, 
            error=str(e), 
            message=t('web_update_fail', str(e))
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
        print(t("msg_module_fail", e))
        return False

def get_status():
    """获取当前下载状态"""
    with status_lock:
        status = current_download_status.copy()
        # 获取并清空消息队列
        status['messages'] = current_download_status['messages'].copy()
        current_download_status['messages'] = []
        return status

def update_status(progress=None, message=None, **kwargs):
    """更新下载状态"""
    with status_lock:
        if progress is not None:
            current_download_status['progress'] = progress
        if message is not None:
            current_download_status['message'] = message
            # 将消息添加到队列（用于前端显示完整日志）
            current_download_status['messages'].append(message)
            # 限制队列长度，防止内存溢出
            if len(current_download_status['messages']) > 100:
                current_download_status['messages'] = current_download_status['messages'][-50:]
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
            
            update_status(is_downloading=True, progress=0, message=t('web_init'))
            
            if not api:
                update_status(message=t('web_api_not_init'), progress=0, is_downloading=False)
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
                update_status(message=t('web_connecting_book'))
                
                # 增加超时重试机制
                book_detail = None
                for _ in range(3):
                    book_detail = api_manager.get_book_detail(book_id)
                    if book_detail:
                        break
                    time.sleep(1)
                
                if not book_detail:
                    update_status(message=t('web_book_info_fail_check'), is_downloading=False)
                    continue
                
                book_name = book_detail.get('book_name', book_id)
                update_status(book_name=book_name, message=t('web_preparing_download', book_name))
                
                # 执行下载
                update_status(message=t('web_starting_engine'))
                success = api.run_download(book_id, save_path, file_format, start_chapter, end_chapter, selected_chapters, progress_callback)
                
                if success:
                    update_status(progress=100, message=t('web_download_success_path', save_path), is_downloading=False)
                else:
                    update_status(message=t('web_download_interrupted'), progress=0, is_downloading=False)
                    
            except Exception as e:
                import traceback
                traceback.print_exc()
                error_str = str(e)
                update_status(message=t('web_download_exception', error_str), progress=0, is_downloading=False)
                print(f"下载异常: {error_str}")
        
        except queue.Empty:
            continue
        except Exception as e:
            error_str = str(e)
            update_status(message=t('web_worker_error', error_str), progress=0, is_downloading=False)
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
    from config import __version__
    token = request.args.get('token', '')
    return render_template('index.html', version=__version__, access_token=token)

@app.route('/api/init', methods=['POST'])
def api_init():
    """初始化模块"""
    if init_modules():
        return jsonify({'success': True, 'message': t('web_module_loaded')})
    return jsonify({'success': False, 'message': t('web_module_fail_msg')}), 500

@app.route('/api/version', methods=['GET'])
def api_version():
    """获取当前版本号"""
    from config import __version__
    return jsonify({'success': True, 'version': __version__})

@app.route('/api/status', methods=['GET'])
def api_status():
    """获取下载状态"""
    return jsonify(get_status())

@app.route('/api/search', methods=['POST'])
def api_search():
    """搜索书籍"""
    data = request.get_json()
    keyword = data.get('keyword', '').strip()
    offset = data.get('offset', 0)
    
    if not keyword:
        return jsonify({'success': False, 'message': t('web_search_keyword_empty')}), 400
    
    if not api_manager:
        return jsonify({'success': False, 'message': t('web_api_not_init')}), 500
    
    try:
        result = api_manager.search_books(keyword, offset)
        if result and result.get('data'):
            # 解析搜索结果
            search_data = result.get('data', {})
            books = []
            has_more = False
            
            # 新 API 数据结构: data.search_tabs[].data[].book_data[]
            # 需要找到 tab_type=3 (书籍) 的 tab
            search_tabs = search_data.get('search_tabs', [])
            for tab in search_tabs:
                if tab.get('tab_type') == 3:  # 书籍 tab
                    has_more = tab.get('has_more', False)
                    tab_data = tab.get('data', [])
                    if isinstance(tab_data, list):
                        for item in tab_data:
                            # 每个 item 包含 book_data 数组
                            book_data_list = item.get('book_data', [])
                            for book in book_data_list:
                                if isinstance(book, dict):
                                    # 解析字数 (可能是字符串)
                                    word_count = book.get('word_number', 0) or book.get('word_count', 0)
                                    if isinstance(word_count, str):
                                        try:
                                            word_count = int(word_count)
                                        except:
                                            word_count = 0
                                    
                                    # 解析章节数
                                    chapter_count = book.get('serial_count', 0) or book.get('chapter_count', 0)
                                    if isinstance(chapter_count, str):
                                        try:
                                            chapter_count = int(chapter_count)
                                        except:
                                            chapter_count = 0
                                    
                                    # 解析状态 (0=已完结, 1=连载中, 2=完结)
                                    status_code = book.get('creation_status', '')
                                    # 转换为字符串进行比较
                                    status_code_str = str(status_code) if status_code is not None else ''
                                    if status_code_str == '0':
                                        status = t('dl_status_finished')
                                    elif status_code_str == '1':
                                        status = t('dl_status_serializing')
                                    elif status_code_str == '2':
                                        status = t('dl_status_completed_2')
                                    else:
                                        status = ''
                                    
                                    books.append({
                                        'book_id': str(book.get('book_id', '')),
                                        'book_name': book.get('book_name', t('dl_unknown_book')),
                                        'author': book.get('author', t('dl_unknown_author')),
                                        'abstract': book.get('abstract', '') or book.get('book_abstract_v2', t('dl_no_intro')),
                                        'cover_url': book.get('thumb_url', '') or book.get('cover', ''),
                                        'word_count': word_count,
                                        'chapter_count': chapter_count,
                                        'status': status,
                                        'category': book.get('category', '') or book.get('genre', '')
                                    })
                    break  # 找到书籍 tab 后退出
            
            return jsonify({
                'success': True,
                'data': {
                    'books': books,
                    'total': len(books),
                    'offset': offset,
                    'has_more': has_more
                }
            })
        else:
            return jsonify({
                'success': True,
                'data': {
                    'books': [],
                    'total': 0,
                    'offset': offset,
                    'has_more': False
                }
            })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': t('web_search_fail', str(e))}), 500

@app.route('/api/book-info', methods=['POST'])
def api_book_info():
    """获取书籍详情和章节列表"""
    print(f"[DEBUG] Received book-info request: {request.data}")
    data = request.get_json()
    book_id = data.get('book_id', '').strip()
    
    if not book_id:
        return jsonify({'success': False, 'message': t('web_book_id_empty')}), 400
    
    # 从URL中提取ID
    if 'fanqienovel.com' in book_id:
        match = re.search(r'/page/(\d+)', book_id)
        if match:
            book_id = match.group(1)
        else:
            return jsonify({'success': False, 'message': t('web_url_error')}), 400
    
    # 验证book_id是数字
    if not book_id.isdigit():
        return jsonify({'success': False, 'message': t('web_id_not_digit')}), 400
    
    if not api:
        return jsonify({'success': False, 'message': t('web_api_not_init')}), 500
    
    try:
        # 获取书籍信息
        print(f"[DEBUG] calling get_book_detail for {book_id}")
        book_detail = api_manager.get_book_detail(book_id)
        print(f"[DEBUG] book_detail result: {str(book_detail)[:100]}")
        if not book_detail:
            return jsonify({'success': False, 'message': t('web_book_info_fail')}), 400
        
        # 获取章节列表
        print(f"[DEBUG] calling get_chapter_list for {book_id}")
        chapters_data = api_manager.get_chapter_list(book_id)
        print(f"[DEBUG] chapters_data type: {type(chapters_data)}")
        if not chapters_data:
            return jsonify({'success': False, 'message': t('web_chapter_list_fail')}), 400
        
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
                                title = ch.get("title", t("dl_chapter_title", idx+1))
                                if item_id:
                                    chapters.append({"id": str(item_id), "title": title, "index": idx})
                                    idx += 1
            else:
                for idx, item_id in enumerate(all_item_ids):
                    chapters.append({"id": str(item_id), "title": t("dl_chapter_title", idx+1), "index": idx})
        elif isinstance(chapters_data, list):
            for idx, ch in enumerate(chapters_data):
                item_id = ch.get("item_id") or ch.get("chapter_id")
                title = ch.get("title", t("dl_chapter_title", idx+1))
                if item_id:
                    chapters.append({"id": str(item_id), "title": title, "index": idx})
        
        print(f"[DEBUG] Found {len(chapters)} chapters")

        # 返回书籍信息和章节列表
        return jsonify({
            'success': True,
            'data': {
                'book_id': book_id,
                'book_name': book_detail.get('book_name', t('dl_unknown_book')),
                'author': book_detail.get('author', t('dl_unknown_author')),
                'abstract': book_detail.get('abstract', t('dl_no_intro')),
                'cover_url': book_detail.get('thumb_url', ''),
                'chapters': chapters
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': t('web_get_info_fail', str(e))}), 500

@app.route('/api/download', methods=['POST'])
def api_download():
    """开始下载"""
    data = request.get_json()
    
    if get_status()['is_downloading']:
        return jsonify({'success': False, 'message': t('web_download_exists')}), 400
    
    book_id = data.get('book_id', '').strip()
    save_path = data.get('save_path', get_default_download_path()).strip()
    file_format = data.get('file_format', 'txt')
    start_chapter = data.get('start_chapter')
    end_chapter = data.get('end_chapter')
    selected_chapters = data.get('selected_chapters')
    
    if not book_id:
        return jsonify({'success': False, 'message': t('web_book_id_empty')}), 400
    
    # 从URL中提取ID
    if 'fanqienovel.com' in book_id:
        match = re.search(r'/page/(\d+)', book_id)
        if match:
            book_id = match.group(1)
        else:
            return jsonify({'success': False, 'message': t('web_url_error')}), 400
    
    # 验证book_id是数字
    if not book_id.isdigit():
        return jsonify({'success': False, 'message': t('web_id_not_digit')}), 400
    
    # 确保路径存在
    try:
        os.makedirs(save_path, exist_ok=True)
    except Exception as e:
        return jsonify({'success': False, 'message': t('web_save_path_error', str(e))}), 400
    
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
    update_status(is_downloading=True, progress=0, message=t('web_task_added'))
    
    return jsonify({'success': True, 'message': t('web_task_started')})

@app.route('/api/cancel', methods=['POST'])
def api_cancel():
    """取消下载"""
    if downloader_instance:
        try:
            downloader_instance.cancel_download()
            update_status(is_downloading=False, progress=0, message=t('web_batch_cancelled_msg'))
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 400
    return jsonify({'success': False}), 400

# ===================== 批量下载状态 =====================
batch_download_status = {
    'is_downloading': False,
    'current_index': 0,
    'total_count': 0,
    'current_book': '',
    'results': [],
    'message': ''
}
batch_lock = threading.Lock()

def get_batch_status():
    """获取批量下载状态"""
    with batch_lock:
        return batch_download_status.copy()

def update_batch_status(**kwargs):
    """更新批量下载状态"""
    with batch_lock:
        for key, value in kwargs.items():
            if key in batch_download_status:
                batch_download_status[key] = value

def batch_download_worker(book_ids, save_path, file_format):
    """批量下载工作线程"""
    from novel_downloader import batch_downloader
    
    def progress_callback(current, total, book_name, status, message):
        update_batch_status(
            current_index=current,
            total_count=total,
            current_book=book_name,
            message=f'[{current}/{total}] {book_name}: {message}'
        )
    
    try:
        update_batch_status(
            is_downloading=True,
            current_index=0,
            total_count=len(book_ids),
            results=[],
            message='开始批量下载...'
        )
        
        result = batch_downloader.run_batch(
            book_ids, save_path, file_format,
            progress_callback=progress_callback,
            delay_between_books=2.0
        )
        
        update_batch_status(
            is_downloading=False,
            results=result.get('results', []),
            message=f"✅ 批量下载完成: {result['message']}"
        )
        
    except Exception as e:
        update_batch_status(
            is_downloading=False,
            message=f'❌ 批量下载失败: {str(e)}'
        )

@app.route('/api/batch-download', methods=['POST'])
def api_batch_download():
    """开始批量下载"""
    data = request.get_json()
    
    if get_batch_status()['is_downloading']:
        return jsonify({'success': False, 'message': t('web_batch_running')}), 400
    
    book_ids = data.get('book_ids', [])
    save_path = data.get('save_path', get_default_download_path()).strip()
    file_format = data.get('file_format', 'txt')
    
    if not book_ids:
        return jsonify({'success': False, 'message': t('web_provide_ids')}), 400
    
    # 清理和验证book_ids
    cleaned_ids = []
    for bid in book_ids:
        bid = str(bid).strip()
        # 从URL提取ID
        if 'fanqienovel.com' in bid:
            match = re.search(r'/page/(\d+)', bid)
            if match:
                bid = match.group(1)
        if bid.isdigit():
            cleaned_ids.append(bid)
    
    if not cleaned_ids:
        return jsonify({'success': False, 'message': t('web_no_valid_ids')}), 400
    
    # 确保保存目录存在
    os.makedirs(save_path, exist_ok=True)
    
    # 启动批量下载线程
    t = threading.Thread(
        target=batch_download_worker,
        args=(cleaned_ids, save_path, file_format),
        daemon=True
    )
    t.start()
    
    return jsonify({
        'success': True,
        'message': t('web_batch_start_count', len(cleaned_ids)),
        'count': len(cleaned_ids)
    })

@app.route('/api/batch-status', methods=['GET'])
def api_batch_status():
    """获取批量下载状态"""
    return jsonify(get_batch_status())

@app.route('/api/batch-cancel', methods=['POST'])
def api_batch_cancel():
    """取消批量下载"""
    from novel_downloader import batch_downloader
    
    try:
        batch_downloader.cancel()
        update_batch_status(
            is_downloading=False,
            message=t('web_batch_cancelled_msg')
        )
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/language', methods=['GET', 'POST'])
def api_language():
    """获取/设置语言配置"""
    from locales import get_current_lang, set_current_lang
    
    if request.method == 'GET':
        return jsonify({'language': get_current_lang()})
    else:
        data = request.get_json()
        lang = data.get('language', 'zh')
        if lang not in ['zh', 'en']:
            lang = 'zh'
        if set_current_lang(lang):
            return jsonify({'success': True, 'language': lang})
        else:
            return jsonify({'success': False, 'message': 'Failed to save language'}), 500

@app.route('/api/config/save-path', methods=['GET', 'POST'])
def api_config_save_path():
    """获取/保存下载路径配置"""
    
    if request.method == 'GET':
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    return jsonify({'path': config.get('save_path', get_default_download_path())})
        except:
            pass
        return jsonify({'path': get_default_download_path()})
    
    else:
        data = request.get_json()
        path = data.get('path', get_default_download_path())
        
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
        
        current_path = request.get_json().get('current_path', get_default_download_path())
        
        folder_path = filedialog.askdirectory(
            title='选择小说保存目录',
            initialdir=current_path if os.path.exists(current_path) else get_default_download_path()
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
            return jsonify({'success': False, 'message': t('web_folder_unselected')})
            
    except Exception as e:
        return jsonify({'success': False, 'message': t('web_folder_select_fail', str(e))}), 500

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
        return jsonify({'success': False, 'message': t('web_check_update_fail', str(e))}), 500

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
    save_path = get_default_download_path()
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
            save_path = get_default_download_path()

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
    """应用已下载的更新（支持 Windows/Linux/macOS）"""
    print('[DEBUG] api_apply_update called')
    try:
        from updater import apply_update, can_auto_update
        import sys
        
        print(f'[DEBUG] sys.frozen: {getattr(sys, "frozen", False)}')
        print(f'[DEBUG] sys.executable: {sys.executable}')
        
        # 检查是否支持自动更新
        can_update = can_auto_update()
        print(f'[DEBUG] can_auto_update: {can_update}')
        if not can_update:
            return jsonify({
                'success': False, 
                'message': t('web_auto_update_unsupported')
            }), 400
        
        # 获取下载的更新文件信息
        status = get_update_status()
        print(f'[DEBUG] update_status: {status}')
        if not status.get('completed'):
            return jsonify({
                'success': False, 
                'message': t('web_update_not_ready')
            }), 400
        
        # 使用临时文件路径
        new_file_path = status.get('temp_file_path', '')
        print(f'[DEBUG] temp_file_path: {new_file_path}')
        
        if not new_file_path:
            # 兼容旧逻辑
            save_path = status.get('save_path', '')
            filename = status.get('filename', '')
            if save_path and filename:
                new_file_path = os.path.join(save_path, filename)
        
        print(f'[DEBUG] new_file_path: {new_file_path}')
        
        if not new_file_path:
            return jsonify({
                'success': False, 
                'message': t('web_update_info_incomplete')
            }), 400
        
        print(f'[DEBUG] file exists: {os.path.exists(new_file_path)}')
        
        if not os.path.exists(new_file_path):
            return jsonify({
                'success': False, 
                'message': t('web_update_file_missing', new_file_path)
            }), 400
        
        print(f'[DEBUG] file size: {os.path.getsize(new_file_path)} bytes')
        
        # 应用更新（自动检测平台）
        print('[DEBUG] Calling apply_update...')
        if apply_update(new_file_path):
            # 更新成功启动，准备退出程序
            # 等待足够时间确保更新脚本已启动并开始监控进程
            def delayed_exit():
                import time
                print('[DEBUG] Waiting for update script to start...')
                time.sleep(3)  # 给更新脚本足够的启动时间
                print('[DEBUG] Exiting application for update...')
                os._exit(0)
            
            # 使用非守护线程确保退出逻辑能完成
            exit_thread = threading.Thread(target=delayed_exit, daemon=False)
            exit_thread.start()
            
            return jsonify({
                'success': True, 
                'message': t('web_update_start_success')
            })
        else:
            return jsonify({
                'success': False, 
                'message': t('web_update_start_fail')
            }), 500
            
    except Exception as e:
        return jsonify({'success': False, 'message': t('web_apply_update_fail', str(e))}), 500

@app.route('/api/open-folder', methods=['POST'])
def api_open_folder():
    """打开文件夹"""
    data = request.get_json()
    path = data.get('path')
    
    if not path or not os.path.exists(path):
        return jsonify({'success': False, 'message': t('web_path_not_exist')}), 400
        
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
    print(t('web_server_started'))
    app.run(host='127.0.0.1', port=5000, debug=False)
