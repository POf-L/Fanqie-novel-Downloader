# -*- coding: utf-8 -*-
"""批量下载相关API路由"""

from flask import Blueprint, request, jsonify
import threading
import os
import re

from .shared_state import get_default_download_path

batch_bp = Blueprint('batch', __name__)


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
    from core.novel_downloader import batch_downloader
    
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
            message=f"批量下载完成: {result['message']}"
        )
        
    except Exception as e:
        update_batch_status(
            is_downloading=False,
            message=f'批量下载失败: {str(e)}'
        )


@batch_bp.route('/api/batch-download', methods=['POST'])
def api_batch_download():
    """开始批量下载"""
    data = request.get_json()
    
    if get_batch_status()['is_downloading']:
        return jsonify({'success': False, 'message': '批量下载正在进行中'}), 400
    
    book_ids = data.get('book_ids', [])
    save_path = data.get('save_path', get_default_download_path()).strip()
    file_format = data.get('file_format', 'txt')
    
    if not book_ids:
        return jsonify({'success': False, 'message': '请提供书籍ID列表'}), 400
    
    cleaned_ids = []
    for bid in book_ids:
        bid = str(bid).strip()
        if 'fanqienovel.com' in bid:
            match = re.search(r'/page/(\d+)', bid)
            if match:
                bid = match.group(1)
        if bid.isdigit():
            cleaned_ids.append(bid)
    
    if not cleaned_ids:
        return jsonify({'success': False, 'message': '没有有效的书籍ID'}), 400
    
    os.makedirs(save_path, exist_ok=True)
    
    t = threading.Thread(
        target=batch_download_worker,
        args=(cleaned_ids, save_path, file_format),
        daemon=True
    )
    t.start()
    
    return jsonify({
        'success': True,
        'message': f'开始批量下载，共 {len(cleaned_ids)} 本书',
        'count': len(cleaned_ids)
    })


@batch_bp.route('/api/batch-status', methods=['GET'])
def api_batch_status():
    """获取批量下载状态"""
    return jsonify(get_batch_status())


@batch_bp.route('/api/batch-cancel', methods=['POST'])
def api_batch_cancel():
    """取消批量下载"""
    from core.novel_downloader import batch_downloader
    
    try:
        batch_downloader.cancel()
        update_batch_status(
            is_downloading=False,
            message='批量下载已取消'
        )
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
