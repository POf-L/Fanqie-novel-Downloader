# -*- coding: utf-8 -*-
"""
番茄小说下载器核心模块 - 主下载器类
"""

import sys
import os
import time
import threading
import signal
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

# 添加父目录到路径以便导入其他模块（打包环境和开发环境都需要）
if getattr(sys, 'frozen', False):
    # 打包环境
    if hasattr(sys, '_MEIPASS'):
        _base_path = sys._MEIPASS
    else:
        _base_path = os.path.dirname(sys.executable)
    if _base_path not in sys.path:
        sys.path.insert(0, _base_path)
else:
    # 开发环境
    _parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _parent_dir not in sys.path:
        sys.path.insert(0, _parent_dir)

try:
    from utils.packaging_fixes import apply_all_fixes
    apply_all_fixes()
except ImportError:
    pass

from datetime import datetime
from .api_manager import get_api_manager
from .download_manager import Run


class NovelDownloader:
    """小说下载器类"""
    
    def __init__(self):
        self.is_cancelled = False
        self.current_progress_callback = None
        self.gui_verification_callback = None
    
    def cancel_download(self):
        """取消下载"""
        self.is_cancelled = True
    
    def run_download(self, book_id, save_path, file_format='txt', start_chapter=None, end_chapter=None, selected_chapters=None, gui_callback=None):
        """运行下载"""
        try:
            if gui_callback:
                self.gui_verification_callback = gui_callback
            
            return Run(book_id, save_path, file_format, start_chapter, end_chapter, selected_chapters, gui_callback)
        except Exception as e:
            print(f"下载失败: {str(e)}")
            return False
    
    def search_novels(self, keyword, offset=0):
        """搜索小说"""
        try:
            api = get_api_manager()
            if api is None:
                return None
            
            search_results = api.search_books(keyword, offset)
            if search_results and search_results.get("data"):
                return search_results["data"]
            return None
        except Exception as e:
            print(f"搜索失败: {str(e)}")
            return None


downloader_instance = NovelDownloader()


class BatchDownloader:
    """批量下载器"""
    
    def __init__(self):
        self.is_cancelled = False
        self.results = []
        self.current_index = 0
        self.total_count = 0
    
    def cancel(self):
        """取消批量下载"""
        self.is_cancelled = True
    
    def reset(self):
        """重置状态"""
        self.is_cancelled = False
        self.results = []
        self.current_index = 0
        self.total_count = 0
    
    def run_batch(
        self,
        book_ids: list,
        save_path: str,
        file_format: str = 'txt',
        progress_callback=None,
        delay_between_books: float = 2.0,
        max_concurrent: int = 1,
        log_func=None,
    ):
        """
        批量下载多本书籍
        
        Args:
            book_ids: 书籍ID列表
            save_path: 保存路径
            file_format: 文件格式 ('txt' 或 'epub')
            progress_callback: 进度回调函数 (current, total, book_name, status, message)
            delay_between_books: 每本书之间的延迟（秒）
            max_concurrent: 并发下载数量（>=1）。为保证稳定性会强制限制最大值。
            log_func: 日志输出函数，None 表示不输出（默认：无 progress_callback 时输出到控制台）
        
        Returns:
            dict: 批量下载结果
        """
        from config.config import CONFIG, print_lock
        from utils.async_logger import safe_print
        
        self.reset()
        self.total_count = len(book_ids)
        
        if not book_ids:
            return {'success': False, 'message': '没有书籍ID', 'results': []}
        
        api = get_api_manager()
        if api is None:
            return {'success': False, 'message': 'API初始化失败', 'results': []}
        
        # 默认日志策略：只有在非 GUI/回调模式下才输出到控制台，避免污染 Web 端日志
        if log_func is None and progress_callback is None:
            log_func = print

        def log(msg: str) -> None:
            if not log_func:
                return
            try:
                with print_lock:
                    log_func(msg)
            except Exception:
                try:
                    log_func(msg)
                except Exception:
                    pass

        def safe_progress(current, total, book_name, status, message) -> None:
            if not progress_callback:
                return
            try:
                progress_callback(current, total, book_name, status, message)
            except Exception:
                pass

        # 并发限制（默认与 CLI 一致，避免创建过多线程/请求过快）
        try:
            max_concurrent = int(max_concurrent or 1)
        except Exception:
            max_concurrent = 1
        max_concurrent = max(1, max_concurrent)
        max_concurrent = min(max_concurrent, 5)
        max_concurrent = min(max_concurrent, len(book_ids))

        def get_book_name(book_id: str) -> str:
            book_name = f"书籍_{book_id}"
            try:
                book_detail = api.get_book_detail(book_id)
                if isinstance(book_detail, dict) and not book_detail.get('_error'):
                    book_name = book_detail.get('book_name', book_name)
            except Exception:
                pass
            return book_name

        def download_single_book(book_id: str, index: int) -> dict:
            """下载单本书籍（支持并发执行）"""
            if self.is_cancelled:
                return {
                    'book_id': str(book_id).strip(),
                    'book_name': f"书籍_{str(book_id).strip()}",
                    'success': False,
                    'message': "批量下载已取消",
                    'index': index,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }

            book_id = str(book_id).strip()
            book_name = get_book_name(book_id)
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            log(f"\n[{index}/{self.total_count}] 开始下载: 《{book_name}》")
            safe_progress(index, self.total_count, book_name, 'downloading', f"正在下载第 {index} 本...")

            result = {
                'book_id': book_id,
                'book_name': book_name,
                'success': False,
                'message': '',
                'index': index,
                'timestamp': timestamp
            }

            try:
                def single_book_callback(progress, message):
                    safe_progress(index, self.total_count, book_name, 'downloading', message)

                success = Run(book_id, save_path, file_format, gui_callback=single_book_callback)

                if success:
                    result['success'] = True
                    result['message'] = '下载成功'
                    log(f"《{book_name}》下载完成")
                else:
                    result['message'] = '下载失败'
                    log(f"《{book_name}》下载失败")

            except Exception as e:
                result['message'] = str(e)
                log(f"《{book_name}》下载异常: {str(e)}")

            status = 'success' if result['success'] else 'failed'
            safe_progress(index, self.total_count, book_name, status, result['message'])
            return result

        log(f"开始批量下载，共 {self.total_count} 本书籍")
        log("=" * 50)

        # 单线程：保持原有顺序与延迟逻辑（Web 默认行为）
        if max_concurrent <= 1:
            for idx, book_id in enumerate(book_ids):
                if self.is_cancelled:
                    log("批量下载已取消")
                    break

                self.current_index = idx + 1
                result = download_single_book(book_id, self.current_index)
                self.results.append(result)

                # 延迟，避免请求过快
                if idx < len(book_ids) - 1 and not self.is_cancelled:
                    time.sleep(delay_between_books)
        else:
            # 并发：用于 CLI / Actions 等环境
            results_by_index = {}
            results_lock = threading.Lock()

            with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
                future_to_index = {
                    executor.submit(download_single_book, book_id, idx + 1): (idx + 1, book_id)
                    for idx, book_id in enumerate(book_ids)
                    if not self.is_cancelled
                }

                for future in as_completed(future_to_index):
                    index, raw_book_id = future_to_index[future]
                    try:
                        result = future.result()
                    except Exception as e:
                        result = {
                            'book_id': str(raw_book_id).strip(),
                            'book_name': f"书籍_{str(raw_book_id).strip()}",
                            'success': False,
                            'message': str(e),
                            'index': index,
                            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        }

                    with results_lock:
                        results_by_index[index] = result

            # 按输入顺序输出结果
            for i in range(1, len(book_ids) + 1):
                if i in results_by_index:
                    self.results.append(results_by_index[i])
        
        # 统计结果
        success_count = sum(1 for r in self.results if r['success'])
        failed_count = len(self.results) - success_count
        
        log("\n" + "=" * 50)
        log("批量下载完成统计:")
        log(f"   成功: {success_count} 本")
        log(f"   失败: {failed_count} 本")
        log(f"   总计: {len(self.results)} 本")
        
        if failed_count > 0:
            log("\n失败列表:")
            for r in self.results:
                if not r['success']:
                    log(f"   - 《{r['book_name']}》: {r['message']}")
        
        return {
            'success': failed_count == 0,
            'message': f"完成 {success_count}/{len(self.results)} 本",
            'total': len(self.results),
            'success_count': success_count,
            'failed_count': failed_count,
            'results': self.results
        }


batch_downloader = BatchDownloader()


def signal_handler(sig, frame):
    """信号处理"""
    print('\n正在取消下载...')
    downloader_instance.cancel_download()
    batch_downloader.cancel()
    sys.exit(0)


if __name__ == "__main__":
    try:
        signal.signal(signal.SIGINT, signal_handler)
    except ValueError:
        pass
    
    print("番茄小说下载器")
    print("="*50)
    print("1. 单本下载")
    print("2. 批量下载")
    mode = input("选择模式 (1/2, 默认: 1): ").strip() or "1"
    
    save_path = input("请输入保存路径(默认: ./novels): ").strip() or "./novels"
    file_format = input("选择格式 (txt/epub, 默认: txt): ").strip() or "txt"
    os.makedirs(save_path, exist_ok=True)
    
    if mode == "2":
        # 批量下载模式
        print("\n请输入书籍ID列表（每行一个，输入空行结束）:")
        book_ids = []
        while True:
            line = input().strip()
            if not line:
                break
            # 支持逗号/空格/换行分隔
            for bid in re.split(r'[,\s]+', line):
                bid = bid.strip()
                if bid:
                    book_ids.append(bid)
        
        if book_ids:
            print(f"\n共 {len(book_ids)} 本书籍待下载")
            result = batch_downloader.run_batch(book_ids, save_path, file_format)
            print(f"\n批量下载结束: {result['message']}")
        else:
            print("没有输入书籍ID")
    else:
        # 单本下载模式
        book_id = input("请输入书籍ID: ").strip()
        success = Run(book_id, save_path, file_format)
        if success:
            print("下载完成!")
        else:
            print("下载失败!")
