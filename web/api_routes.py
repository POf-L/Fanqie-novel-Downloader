# -*- coding: utf-8 -*-
"""
API路由模块 - Flask后端API路由
"""

import os
import re
import sys
from flask import jsonify, request

# 添加父目录到路径
if getattr(sys, 'frozen', False):
    if hasattr(sys, '_MEIPASS'):
        _base_path = sys._MEIPASS
    else:
        _base_path = os.path.dirname(sys.executable)
    if _base_path not in sys.path:
        sys.path.insert(0, _base_path)
else:
    _parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _parent_dir not in sys.path:
        sys.path.insert(0, _parent_dir)

from config.config import CONFIG
from .download_history import get_download_history_manager
from .task_manager import task_manager
from .parsers import BookListParser, ChapterRangeParser


def init_routes(app):
    """初始化所有API路由"""
    
    @app.route('/api/upload-book-list', methods=['POST'])
    def api_upload_book_list():
        """上传并解析书籍列表文件"""
        # 检查是否有文件上传
        if 'file' in request.files:
            file = request.files['file']
            if file.filename == '':
                return jsonify({'success': False, 'message': '未选择文件'}), 400
            
            try:
                content = file.read().decode('utf-8')
            except UnicodeDecodeError:
                try:
                    file.seek(0)
                    content = file.read().decode('gbk')
                except:
                    return jsonify({'success': False, 'message': '文件编码不支持，请使用 UTF-8 或 GBK 编码'}), 400
        else:
            # 也支持直接传递文本内容
            data = request.get_json() or {}
            content = data.get('content', '')
        
        if not content:
            return jsonify({'success': False, 'message': '文件内容为空'}), 400
        
        result = BookListParser.parse_file_content(content)
        
        return jsonify({
            'success': True,
            'data': {
                'books': result['books'],
                'skipped': result['skipped'],
                'total_lines': result['total_lines'],
                'valid_count': len(result['books']),
                'skipped_count': len(result['skipped'])
            }
        })

    @app.route('/api/parse-chapter-range', methods=['POST'])
    def api_parse_chapter_range():
        """解析章节范围字符串"""
        data = request.get_json() or {}
        input_str = data.get('input', '').strip()
        max_chapter = data.get('max_chapter', 0)
        
        if not input_str:
            return jsonify({
                'success': True,
                'data': {
                    'chapters': [],
                    'errors': [],
                    'warnings': []
                }
            })
        
        try:
            max_chapter = int(max_chapter)
        except (ValueError, TypeError):
            return jsonify({'success': False, 'message': '无效的最大章节数'}), 400
        
        result = ChapterRangeParser.parse(input_str, max_chapter)
        
        return jsonify({
            'success': result['success'],
            'data': {
                'chapters': result['chapters'],
                'errors': result['errors'],
                'warnings': result['warnings']
            }
        })

    # ===================== 下载历史 API =====================

    @app.route('/api/download-history/check', methods=['POST'])
    def api_download_history_check():
        """检查书籍是否已下载"""
        data = request.get_json() or {}
        book_id = data.get('book_id')
        book_ids = data.get('book_ids', [])
        
        history_manager = get_download_history_manager()
        
        # 单个检查
        if book_id:
            record = history_manager.check_exists(book_id)
            return jsonify({
                'success': True,
                'exists': record is not None,
                'record': record
            })
        
        # 批量检查
        if book_ids:
            results = history_manager.check_batch(book_ids)
            return jsonify({
                'success': True,
                'results': results
            })
        
        return jsonify({'success': False, 'message': '请提供 book_id 或 book_ids'}), 400

    @app.route('/api/download-history/list', methods=['GET'])
    def api_download_history_list():
        """获取下载历史列表"""
        history_manager = get_download_history_manager()
        records = history_manager.get_all_records()
        
        return jsonify({
            'success': True,
            'records': records,
            'total': len(records)
        })

    @app.route('/api/download-history/add', methods=['POST'])
    def api_download_history_add():
        """添加下载记录"""
        data = request.get_json() or {}
        
        required_fields = ['book_id', 'book_name', 'save_path', 'file_format']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'success': False, 'message': f'缺少必填字段: {field}'}), 400
        
        history_manager = get_download_history_manager()
        success = history_manager.add_record(
            book_id=data['book_id'],
            book_name=data['book_name'],
            author=data.get('author', ''),
            save_path=data['save_path'],
            file_format=data['file_format'],
            chapter_count=data.get('chapter_count', 0)
        )
        
        return jsonify({'success': success})

    @app.route('/api/download-history/remove', methods=['POST'])
    def api_download_history_remove():
        """删除下载记录"""
        data = request.get_json() or {}
        book_id = data.get('book_id')
        
        if not book_id:
            return jsonify({'success': False, 'message': '请提供 book_id'}), 400
        
        history_manager = get_download_history_manager()
        success = history_manager.remove_record(book_id)
        
        return jsonify({'success': success})

    # ===================== 队列管理 API =====================

    @app.route('/api/queue/status', methods=['GET'])
    def api_queue_status():
        """获取队列状态
        
        返回队列中所有任务的详细信息，包括状态、进度等
        """
        status = task_manager.get_queue_status()
        return jsonify({
            'success': True,
            'data': status
        })

    @app.route('/api/queue/skip', methods=['POST'])
    def api_queue_skip():
        """跳过当前任务
        
        停止当前书籍的下载并开始下载队列中的下一本书
        """
        result = task_manager.skip_current()
        if result:
            return jsonify({
                'success': True,
                'message': '已跳过当前任务'
            })
        else:
            return jsonify({
                'success': False,
                'message': '无法跳过：没有正在下载的任务'
            }), 400

    @app.route('/api/queue/retry', methods=['POST'])
    def api_queue_retry():
        """重试指定任务或所有失败任务
        
        请求体:
        - task_id: 指定任务ID（可选）
        - retry_all: 是否重试所有失败任务（可选）
        """
        data = request.get_json() or {}
        task_id = data.get('task_id')
        retry_all = data.get('retry_all', False)
        
        if retry_all:
            count = task_manager.retry_all_failed()
            if count > 0:
                return jsonify({
                    'success': True,
                    'message': f'已重置 {count} 个失败任务',
                    'count': count
                })
            else:
                return jsonify({
                    'success': False,
                    'message': '没有失败的任务需要重试'
                }), 400
        elif task_id:
            # 重试单个任务（需要实现）
            return jsonify({
                'success': False,
                'message': '重试单个任务功能未实现'
            }), 400
        
        return jsonify({'success': False, 'message': '请指定 task_id 或 retry_all'}), 400

    return app
