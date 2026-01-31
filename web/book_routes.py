# -*- coding: utf-8 -*-
"""书籍相关API路由"""

from flask import Blueprint, request, jsonify
import os
import re
import threading

from .shared_state import (
    get_status, update_status, init_download_queue,
    get_default_download_path, _read_local_config, _write_local_config,
    CONFIG_FILE
)

# 初始化队列
init_download_queue()

book_bp = Blueprint('book', __name__)

@book_bp.route('/api/search', methods=['POST'])
def api_search():
    """搜索书籍"""
    data = request.get_json()
    keyword = data.get('keyword', '').strip()
    offset = data.get('offset', 0)
    
    if not keyword:
        return jsonify({'success': False, 'message': '搜索关键词不能为空'}), 400
    
    try:
        from core.api_manager import get_api_manager
        api_manager = get_api_manager()
        if not api_manager:
            return jsonify({'success': False, 'message': 'API 未初始化'}), 500
        
        result = api_manager.search_books(keyword, offset)
        if result and result.get("data"):
            search_data = result.get("data", {})
            books = []
            has_more = False
            
            search_tabs = search_data.get('search_tabs', [])
            for tab in search_tabs:
                if tab.get('tab_type') == 3:
                    has_more = tab.get('has_more', False)
                    tab_data = tab.get('data', [])
                    if isinstance(tab_data, list):
                        for item in tab_data:
                            book_data_list = item.get('book_data', [])
                            for book in book_data_list:
                                if isinstance(book, dict):
                                    word_count = book.get('word_number', 0) or book.get('word_count', 0)
                                    if isinstance(word_count, str):
                                        try:
                                            word_count = int(word_count)
                                        except:
                                            word_count = 0
                                    
                                    chapter_count = book.get('serial_count', 0) or book.get('chapter_count', 0)
                                    if isinstance(chapter_count, str):
                                        try:
                                            chapter_count = int(chapter_count)
                                        except:
                                            chapter_count = 0
                                    
                                    status_code = book.get('creation_status', '')
                                    status_code_str = str(status_code) if status_code is not None else ''
                                    if status_code_str == '0':
                                        status = '已完结'
                                    elif status_code_str == '1':
                                        status = '连载中'
                                    elif status_code_str == '2':
                                        status = '完结'
                                    else:
                                        status = ''
                                    
                                    books.append({
                                        'book_id': str(book.get('book_id', '')),
                                        'book_name': book.get('book_name', '未知书籍'),
                                        'author': book.get('author', '未知作者'),
                                        'abstract': book.get('abstract', '') or book.get('book_abstract_v2', '暂无简介'),
                                        'cover_url': book.get('thumb_url', '') or book.get('cover', ''),
                                        'word_count': word_count,
                                        'chapter_count': chapter_count,
                                        'status': status,
                                        'category': book.get('category', '') or book.get('genre', '')
                                    })
                    break
            
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
        return jsonify({'success': False, 'message': f'搜索失败: {str(e)}'}), 500


@book_bp.route('/api/book-info', methods=['POST'])
def api_book_info():
    """获取书籍详情和章节列表"""
    data = request.get_json()
    book_id = data.get('book_id', '').strip()
    
    if not book_id:
        return jsonify({'success': False, 'message': '书籍ID不能为空'}), 400
    
    if 'fanqienovel.com' in book_id:
        match = re.search(r'/page/(\d+)', book_id)
        if match:
            book_id = match.group(1)
        else:
            return jsonify({'success': False, 'message': 'URL格式错误'}), 400
    
    if not book_id.isdigit():
        return jsonify({'success': False, 'message': '书籍ID必须是数字'}), 400
    
    try:
        from core.api_manager import get_api_manager
        api_manager = get_api_manager()
        if not api_manager:
            return jsonify({'success': False, 'message': 'API 未初始化'}), 500
        
        book_detail = api_manager.get_book_detail(book_id)
        if not book_detail:
            return jsonify({'success': False, 'message': '获取书籍信息失败'}), 400
        
        if isinstance(book_detail, dict) and book_detail.get('_error'):
            error_type = book_detail.get('_error')
            if error_type == 'BOOK_REMOVE':
                return jsonify({'success': False, 'message': '该书籍已下架，无法下载'}), 400
            return jsonify({'success': False, 'message': f'获取书籍信息失败: {error_type}'}), 400
        
        chapters_data = api_manager.get_chapter_list(book_id)
        if not chapters_data:
            return jsonify({'success': False, 'message': '获取章节列表失败'}), 400
        
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
        
        return jsonify({
            'success': True,
            'data': {
                'book_id': book_id,
                'book_name': book_detail.get('book_name', '未知书籍'),
                'author': book_detail.get('author', '未知作者'),
                'abstract': book_detail.get('abstract', '暂无简介'),
                'cover_url': book_detail.get('thumb_url', ''),
                'chapters': chapters
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'获取书籍信息失败: {str(e)}'}), 500


@book_bp.route('/api/download', methods=['POST'])
def api_download():
    """开始下载"""
    data = request.get_json()
    
    if get_status()['is_downloading']:
        return jsonify({'success': False, 'message': '已有下载任务正在进行'}), 400
    
    book_id = data.get('book_id', '').strip()
    save_path = data.get('save_path', get_default_download_path()).strip()
    file_format = data.get('file_format', 'txt')
    start_chapter = data.get('start_chapter')
    end_chapter = data.get('end_chapter')
    selected_chapters = data.get('selected_chapters')
    
    if not book_id:
        return jsonify({'success': False, 'message': '书籍ID不能为空'}), 400
    
    if 'fanqienovel.com' in book_id:
        match = re.search(r'/page/(\d+)', book_id)
        if match:
            book_id = match.group(1)
        else:
            return jsonify({'success': False, 'message': 'URL格式错误'}), 400
    
    if not book_id.isdigit():
        return jsonify({'success': False, 'message': '书籍ID必须是数字'}), 400
    
    try:
        os.makedirs(save_path, exist_ok=True)
    except Exception as e:
        return jsonify({'success': False, 'message': f'保存路径错误: {str(e)}'}), 400
    
    from .download_worker import download_queue
    task = {
        'book_id': book_id,
        'save_path': save_path,
        'file_format': file_format,
        'start_chapter': start_chapter,
        'end_chapter': end_chapter,
        'selected_chapters': selected_chapters
    }
    download_queue.put(task)
    update_status(is_downloading=True, progress=0, message='任务已添加到队列')
    
    return jsonify({'success': True, 'message': '任务已开始'})


@book_bp.route('/api/cancel', methods=['POST'])
def api_cancel():
    """取消下载"""
    try:
        from core.novel_downloader import downloader_instance
        if downloader_instance:
            downloader_instance.cancel_download()
            update_status(is_downloading=False, progress=0, message='下载已取消')
            return jsonify({'success': True})
        return jsonify({'success': False}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400
