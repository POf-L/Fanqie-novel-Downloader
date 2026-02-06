# -*- coding: utf-8 -*-
"""
命令行界面入口 - 支持 Termux 和无 GUI 环境
"""

import sys
import os

if __package__ in (None, ""):
    _parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _parent_dir not in sys.path:
        sys.path.insert(0, _parent_dir)

from utils.runtime_bootstrap import ensure_runtime_path, apply_encoding_fixes

# 添加父目录到路径以便导入其他模块（打包环境和开发环境都需要）
ensure_runtime_path()

# 一劳永逸的编码处理 - 必须在所有其他导入之前
_safe_print = apply_encoding_fixes()
if _safe_print:
    print = _safe_print

import argparse
from typing import Optional
import asyncio
import subprocess
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from utils.book_id import extract_book_id

from utils.platform_utils import detect_platform, get_feature_status_report


def _extract_book_id(raw_value: str) -> str:
    """从输入值中提取书籍ID，支持纯ID或fanqie URL。"""
    return extract_book_id(raw_value) or ""


def _normalize_single_book_id(raw_value: str) -> Optional[str]:
    """标准化单个书籍ID；无效时返回None。"""
    book_id = _extract_book_id(raw_value)
    return book_id if book_id.isdigit() else None


def _normalize_file_format(file_format: Optional[str]) -> str:
    """标准化导出格式，非法值回退txt并输出警告。"""
    fmt = file_format or 'txt'
    if fmt not in ['txt', 'epub']:
        print(f"警告: 不支持的格式 '{fmt}'，使用默认格式 txt")
        return 'txt'
    return fmt


def _resolve_save_path(raw_path: Optional[str], default_subdir: Optional[str] = None) -> str:
    """标准化保存路径并确保目录存在。"""
    save_path = raw_path
    if not save_path:
        home = os.path.expanduser('~')
        if default_subdir:
            save_path = os.path.join(home, default_subdir)
        else:
            save_path = os.path.join(home, 'Downloads')
            if not os.path.exists(save_path):
                save_path = home

    os.makedirs(save_path, exist_ok=True)
    return save_path


def format_table(headers: list, rows: list, col_widths: Optional[list] = None) -> str:
    """
    格式化文本表格
    
    Args:
        headers: 表头列表
        rows: 数据行列表
        col_widths: 列宽列表（可选）
    
    Returns:
        格式化的表格字符串
    """
    if not rows:
        return "无数据"
    
    # 计算列宽
    if col_widths is None:
        col_widths = []
        for i, header in enumerate(headers):
            max_width = len(str(header))
            for row in rows:
                if i < len(row):
                    max_width = max(max_width, len(str(row[i])))
            col_widths.append(min(max_width, 40))  # 最大宽度 40
    
    # 格式化表头
    header_line = " | ".join(
        str(h).ljust(col_widths[i])[:col_widths[i]] 
        for i, h in enumerate(headers)
    )
    separator = "-+-".join("-" * w for w in col_widths)
    
    # 格式化数据行
    data_lines = []
    for row in rows:
        line = " | ".join(
            str(row[i] if i < len(row) else "").ljust(col_widths[i])[:col_widths[i]]
            for i in range(len(headers))
        )
        data_lines.append(line)
    
    return "\n".join([header_line, separator] + data_lines)


def cmd_search(args):
    """搜索书籍命令"""
    from core.novel_downloader import get_api_manager
    from config.config import CONFIG
    
    keyword = args.keyword
    if not keyword:
        print("错误: 请提供搜索关键词")
        return 1
    
    print(f"正在搜索: {keyword}")
    
    api = get_api_manager()
    result = api.search_books(keyword, offset=0)
    
    if not result or not result.get('data'):
        print("未找到相关书籍")
        return 0
    
    # 解析搜索结果
    search_data = result.get('data', {})
    books = []
    
    search_tabs = search_data.get('search_tabs', [])
    for tab in search_tabs:
        if tab.get('tab_type') == 3:
            tab_data = tab.get('data', [])
            for item in tab_data:
                book_data_list = item.get('book_data', [])
                for book in book_data_list:
                    if isinstance(book, dict):
                        status_code = str(book.get('creation_status', ''))
                        if status_code == '0':
                            status = '已完结'
                        elif status_code == '1':
                            status = '连载中'
                        else:
                            status = ''
                        
                        books.append([
                            book.get('book_id', ''),
                            book.get('book_name', '未知')[:20],
                            book.get('author', '未知')[:10],
                            status
                        ])
            break
    
    if not books:
        print("未找到相关书籍")
        return 0
    
    # 显示结果表格
    headers = ['书籍ID', '书名', '作者', '状态']
    print(f"\n找到 {len(books)} 本书籍:\n")
    print(format_table(headers, books))
    
    return 0


def cmd_info(args):
    """显示书籍信息命令"""
    from core.novel_downloader import get_api_manager
    
    if not args.book_id:
        print("错误: 请提供书籍ID")
        return 1

    book_id = _normalize_single_book_id(args.book_id)
    if not book_id:
        print("错误: 书籍ID必须是数字")
        return 1
    
    print(f"正在获取书籍信息: {book_id}")
    
    api = get_api_manager()
    
    # 获取书籍详情
    book_detail = api.get_book_detail(book_id)
    if not book_detail:
        print("错误: 无法获取书籍信息")
        return 1
    
    # 获取章节列表
    chapters_data = api.get_chapter_list(book_id)
    chapter_count = 0
    if chapters_data:
        if isinstance(chapters_data, dict):
            all_ids = chapters_data.get("allItemIds", [])
            chapter_count = len(all_ids)
        elif isinstance(chapters_data, list):
            chapter_count = len(chapters_data)
    
    # 显示信息
    print("\n" + "=" * 50)
    print(f"书名: {book_detail.get('book_name', '未知')}")
    print(f"作者: {book_detail.get('author', '未知')}")
    print(f"章节数: {chapter_count}")
    print("-" * 50)
    
    abstract = book_detail.get('abstract', '')
    if abstract:
        print("简介:")
        # 限制简介长度
        if len(abstract) > 200:
            abstract = abstract[:200] + "..."
        print(abstract)
    
    print("=" * 50)
    
    return 0


def cmd_download(args):
    """下载书籍命令"""
    from core.novel_downloader import downloader_instance
    from utils.platform_utils import detect_platform
    
    if not args.book_id:
        print("错误: 请提供书籍ID")
        return 1

    book_id = _normalize_single_book_id(args.book_id)
    if not book_id:
        print("错误: 书籍ID必须是数字")
        return 1

    save_path = _resolve_save_path(args.path)
    file_format = _normalize_file_format(args.format)
    
    print(f"开始下载书籍: {book_id}")
    print(f"保存路径: {save_path}")
    print(f"文件格式: {file_format}")
    print("-" * 50)
    
    # 进度回调
    def progress_callback(progress, message):
        if progress >= 0:
            print(f"[{progress:3d}%] {message}")
        else:
            print(f"       {message}")
    
    # 执行下载
    success = downloader_instance.run_download(
        book_id=book_id,
        save_path=save_path,
        file_format=file_format,
        gui_callback=progress_callback,
    )
    
    if success:
        print("\n下载完成!")
        return 0
    else:
        print("\n下载失败")
        return 1


def cmd_batch_download(args):
    """批量下载书籍命令"""
    from core.novel_downloader import batch_downloader
    import time

    # 解析书籍ID列表
    book_ids = []
    if args.book_ids:
        # 从命令行参数获取
        for raw_value in args.book_ids:
            normalized_id = _normalize_single_book_id(raw_value)
            if normalized_id:
                book_ids.append(normalized_id)
            else:
                print(f"警告: 跳过无效的书籍ID: {raw_value}")

    if args.file:
        # 从文件读取书籍ID列表
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        # 支持 ID 或 URL 格式
                        normalized_id = _normalize_single_book_id(line)
                        if normalized_id:
                            book_ids.append(normalized_id)
        except FileNotFoundError:
            print(f"错误: 文件不存在: {args.file}")
            return 1
        except Exception as e:
            print(f"错误: 读取文件失败: {e}")
            return 1

    if not book_ids:
        print("错误: 请提供至少一个书籍ID")
        return 1

    save_path = _resolve_save_path(args.path, default_subdir='Downloads/FanqieNovels')
    file_format = _normalize_file_format(args.format)

    # 并发设置
    max_concurrent = min(args.concurrent or 3, 5)  # 最大5个并发

    print(f"开始批量下载 {len(book_ids)} 本书籍")
    print(f"保存路径: {save_path}")
    print(f"文件格式: {file_format}")
    print(f"并发数量: {max_concurrent}")
    print("-" * 50)

    # 使用统一的批量下载核心（core.novel_downloader.BatchDownloader）
    start_time = time.time()

    def batch_progress_callback(current, total, book_name, status, message):
        """批量下载进度回调 (current=书籍序号，从1开始)"""
        try:
            book_id = book_ids[current - 1] if 1 <= current <= len(book_ids) else ""
        except Exception:
            book_id = ""

        prefix = f"[{current}/{total}]"

        if status == 'success':
            print(f"{prefix} ✓ 下载完成: {book_id} - {book_name}")
        elif status == 'failed':
            print(f"{prefix} ✗ 下载失败: {book_id} - {book_name} - {message}")
        else:
            # downloading / 其他状态
            if book_id:
                print(f"{prefix} {book_id} - {message}")
            else:
                print(f"{prefix} {message}")

    batch_result = batch_downloader.run_batch(
        book_ids=book_ids,
        save_path=save_path,
        file_format=file_format,
        progress_callback=batch_progress_callback,
        delay_between_books=0.0,
        max_concurrent=max_concurrent,
    )

    # 显示批量下载结果
    end_time = time.time()
    duration = end_time - start_time

    successful_downloads = int(batch_result.get('success_count', 0) or 0)
    failed_downloads = int(batch_result.get('failed_count', 0) or 0)
    download_results_list = batch_result.get('results', []) or []

    print("\n" + "=" * 60)
    print("批量下载完成!")
    print(f"总计: {len(book_ids)} 本书籍")
    print(f"成功: {successful_downloads} 本")
    print(f"失败: {failed_downloads} 本")
    print(f"用时: {duration:.1f} 秒")

    # 显示详细结果
    if download_results_list:
        print("\n详细结果:")
        headers = ['序号', '书籍ID', '状态', '时间']
        rows = []
        for r in download_results_list:
            book_id = r.get('book_id', '')
            ok = bool(r.get('success'))
            status = "✓ 成功" if ok else "✗ 失败"
            msg = str(r.get('message', '') or '')
            if msg and not ok:
                status += f" ({msg[:30]}...)" if len(msg) > 30 else f" ({msg})"

            rows.append([
                int(r.get('index', 0) or 0),
                book_id,
                status,
                r.get('timestamp', '')
            ])

        # 按序号排序
        rows.sort(key=lambda x: x[0])
        print(format_table(headers, rows))

    # Git提交功能
    if args.commit and successful_downloads > 0:
        print("\n" + "-" * 50)
        print("正在执行Git提交...")

        try:
            # 检查是否在Git仓库中
            result = subprocess.run(['git', 'rev-parse', '--git-dir'],
                                  capture_output=True, text=True, cwd=save_path)
            if result.returncode != 0:
                print("警告: 当前目录不是Git仓库，跳过提交")
            else:
                # 添加所有新文件
                subprocess.run(['git', 'add', '.'], cwd=save_path, check=True)

                # 创建提交信息
                commit_msg = f"批量下载完成: {successful_downloads}本书籍 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})"
                if failed_downloads > 0:
                    commit_msg += f" (失败: {failed_downloads}本)"

                # 执行提交
                result = subprocess.run(['git', 'commit', '-m', commit_msg],
                                      capture_output=True, text=True, cwd=save_path)

                if result.returncode == 0:
                    print(f"✓ Git提交成功: {commit_msg}")
                else:
                    print(f"Git提交失败: {result.stderr}")

        except subprocess.CalledProcessError as e:
            print(f"Git操作失败: {e}")
        except FileNotFoundError:
            print("警告: 未找到Git命令，请确保Git已安装")

    print("=" * 60)

    # 返回状态码
    return 0 if failed_downloads == 0 else 1




def cmd_status(args):
    """显示平台状态命令"""
    report = get_feature_status_report()
    print(report)
    return 0


def cmd_config(args):
    """配置管理命令"""
    from config.config import CONFIG
    import tempfile

    config_file = os.path.join(tempfile.gettempdir(), 'fanqie_novel_downloader_config.json')

    # 读取本地配置
    def read_config():
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    # 写入本地配置
    def write_config(updates):
        try:
            cfg = read_config()
            cfg.update(updates)
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存配置失败: {e}")
            return False

    # 列出所有配置
    if args.action == 'list':
        cfg = read_config()
        print("\n当前配置:")
        print("=" * 50)

        # API 节点配置
        api_mode = cfg.get('api_base_url_mode', 'auto')
        api_url = cfg.get('api_base_url', '')
        print(f"API 节点模式: {api_mode}")
        if api_url:
            print(f"API 节点 URL: {api_url}")

        # 下载参数配置
        if 'max_workers' in cfg:
            print(f"最大并发数: {cfg['max_workers']}")
        if 'api_rate_limit' in cfg:
            print(f"API 速率限制: {cfg['api_rate_limit']}")
        if 'request_rate_limit' in cfg:
            print(f"请求速率限制: {cfg['request_rate_limit']}")
        if 'connection_pool_size' in cfg:
            print(f"连接池大小: {cfg['connection_pool_size']}")

        # 水印配置
        if 'watermark_enabled' in cfg:
            print(f"水印开关: {'开启' if cfg['watermark_enabled'] else '关闭'}")

        # 保存路径
        if 'save_path' in cfg:
            print(f"默认保存路径: {cfg['save_path']}")

        print("=" * 50)
        return 0

    # 设置配置项
    elif args.action == 'set':
        if not args.key or args.value is None:
            print("错误: 请提供配置键和值")
            print("用法: config set <key> <value>")
            return 1

        # 验证和转换配置值
        key = args.key
        value = args.value

        # 数值类型配置
        if key in ['max_workers', 'api_rate_limit', 'request_rate_limit', 'connection_pool_size']:
            try:
                if '.' in value:
                    value = float(value)
                else:
                    value = int(value)
            except ValueError:
                print(f"错误: {key} 必须是数值")
                return 1

        # 布尔类型配置
        elif key in ['watermark_enabled']:
            value = value.lower() in ['true', '1', 'yes', 'on', '开启']

        # 字符串类型配置
        elif key in ['api_base_url', 'api_base_url_mode', 'save_path']:
            value = str(value)

        else:
            print(f"警告: 未知的配置项 '{key}'，将按字符串保存")

        # 保存配置
        if write_config({key: value}):
            print(f"✓ 配置已保存: {key} = {value}")
            return 0
        else:
            return 1

    # 获取配置项
    elif args.action == 'get':
        if not args.key:
            print("错误: 请提供配置键")
            print("用法: config get <key>")
            return 1

        cfg = read_config()
        if args.key in cfg:
            print(f"{args.key} = {cfg[args.key]}")
            return 0
        else:
            print(f"配置项 '{args.key}' 不存在")
            return 1

    # 重置配置
    elif args.action == 'reset':
        if args.key:
            # 重置单个配置项
            cfg = read_config()
            if args.key in cfg:
                del cfg[args.key]
                try:
                    with open(config_file, 'w', encoding='utf-8') as f:
                        json.dump(cfg, f, ensure_ascii=False, indent=2)
                    print(f"✓ 已重置配置: {args.key}")
                    return 0
                except Exception as e:
                    print(f"重置配置失败: {e}")
                    return 1
            else:
                print(f"配置项 '{args.key}' 不存在")
                return 1
        else:
            # 重置所有配置
            try:
                if os.path.exists(config_file):
                    os.remove(config_file)
                print("✓ 已重置所有配置")
                return 0
            except Exception as e:
                print(f"重置配置失败: {e}")
                return 1

    else:
        print(f"错误: 未知的操作 '{args.action}'")
        return 1


def cmd_api(args):
    """API 节点管理命令"""
    from config.config import CONFIG
    import tempfile
    import requests
    import time

    config_file = os.path.join(tempfile.gettempdir(), 'fanqie_novel_downloader_config.json')

    # 读取本地配置
    def read_config():
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    # 写入本地配置
    def write_config(updates):
        try:
            cfg = read_config()
            cfg.update(updates)
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存配置失败: {e}")
            return False

    # 探测 API 节点
    def probe_api_source(base_url, timeout=2.0):
        """探测 API 节点的可用性和延迟"""
        base_url = base_url.strip().rstrip('/')
        test_url = f"{base_url}/api/health"

        try:
            start = time.time()
            response = requests.get(test_url, timeout=timeout, verify=False)
            latency_ms = int((time.time() - start) * 1000)

            available = response.status_code == 200
            return {
                'base_url': base_url,
                'available': available,
                'latency_ms': latency_ms,
                'status_code': response.status_code
            }
        except requests.exceptions.Timeout:
            return {
                'base_url': base_url,
                'available': False,
                'latency_ms': None,
                'error': '超时'
            }
        except Exception as e:
            return {
                'base_url': base_url,
                'available': False,
                'latency_ms': None,
                'error': str(e)[:50]
            }

    # 列出所有 API 节点
    if args.action == 'list':
        api_sources = CONFIG.get('api_sources', [])
        current_url = CONFIG.get('api_base_url', '')

        print("\n可用的 API 节点:")
        print("=" * 70)

        # 并发探测所有节点
        print("正在探测节点可用性...\n")

        results = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for source in api_sources:
                if isinstance(source, dict):
                    base_url = source.get('base_url', '')
                else:
                    base_url = str(source)

                if base_url:
                    futures.append(executor.submit(probe_api_source, base_url))

            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    print(f"探测失败: {e}")

        # 按可用性和延迟排序
        results.sort(key=lambda x: (
            not x.get('available'),
            x.get('latency_ms') or 999999
        ))

        # 显示结果表格
        headers = ['序号', 'URL', '状态', '延迟 (ms)', '当前']
        rows = []
        for i, result in enumerate(results, 1):
            url = result['base_url']
            available = result.get('available', False)
            latency = result.get('latency_ms')
            error = result.get('error', '')

            status = "✓ 可用" if available else f"✗ 不可用"
            if error:
                status += f" ({error})"

            latency_str = str(latency) if latency else "-"
            is_current = "★" if url == current_url else ""

            rows.append([i, url[:40], status, latency_str, is_current])

        print(format_table(headers, rows))
        print("=" * 70)

        cfg = read_config()
        mode = cfg.get('api_base_url_mode', 'auto')
        print(f"\n当前模式: {mode}")
        if current_url:
            print(f"当前节点: {current_url}")
        print()

        return 0

    # 选择 API 节点
    elif args.action == 'select':
        if args.mode == 'auto':
            # 自动选择最快的可用节点
            api_sources = CONFIG.get('api_sources', [])
            print("正在探测节点可用性...")

            results = []
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = []
                for source in api_sources:
                    if isinstance(source, dict):
                        base_url = source.get('base_url', '')
                    else:
                        base_url = str(source)

                    if base_url:
                        futures.append(executor.submit(probe_api_source, base_url))

                for future in as_completed(futures):
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception:
                        pass

            # 选择最快的可用节点
            available = [r for r in results if r.get('available')]
            if not available:
                print("错误: 没有可用的 API 节点")
                return 1

            available.sort(key=lambda x: x.get('latency_ms') or 999999)
            best = available[0]

            if write_config({'api_base_url_mode': 'auto', 'api_base_url': best['base_url']}):
                print(f"✓ 已选择最快节点: {best['base_url']} (延迟: {best['latency_ms']}ms)")
                return 0
            else:
                return 1

        elif args.mode == 'manual':
            if not args.url:
                print("错误: 请提供 API 节点 URL")
                print("用法: api select manual <url>")
                return 1

            # 探测指定节点
            result = probe_api_source(args.url)
            if not result.get('available'):
                error = result.get('error', '不可用')
                print(f"错误: 节点不可用: {args.url} ({error})")
                return 1

            if write_config({'api_base_url_mode': 'manual', 'api_base_url': args.url}):
                print(f"✓ 已选择节点: {args.url} (延迟: {result['latency_ms']}ms)")
                return 0
            else:
                return 1

        else:
            print(f"错误: 未知的模式 '{args.mode}'")
            return 1

    else:
        print(f"错误: 未知的操作 '{args.action}'")
        return 1


def create_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        prog='fanqie-cli',
        description='番茄小说下载器 - 命令行版本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s search "斗破苍穹"                    搜索书籍
  %(prog)s info 12345                           查看书籍信息
  %(prog)s download 12345                       下载书籍
  %(prog)s download 12345 -f epub               下载为 EPUB 格式
  %(prog)s batch-download 12345 67890 --commit  批量下载并提交
  %(prog)s batch-download -i books.txt --commit 从文件批量下载
  %(prog)s status                               显示平台状态
        """
    )
    
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='显示详细输出')
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # search 命令
    search_parser = subparsers.add_parser('search', help='搜索书籍')
    search_parser.add_argument('keyword', help='搜索关键词')
    search_parser.set_defaults(func=cmd_search)
    
    # info 命令
    info_parser = subparsers.add_parser('info', help='查看书籍信息')
    info_parser.add_argument('book_id', help='书籍ID或URL')
    info_parser.set_defaults(func=cmd_info)
    
    # download 命令
    download_parser = subparsers.add_parser('download', help='下载书籍')
    download_parser.add_argument('book_id', help='书籍ID或URL')
    download_parser.add_argument('-p', '--path', help='保存路径')
    download_parser.add_argument('-f', '--format', choices=['txt', 'epub'],
                                default='txt', help='输出格式 (默认: txt)')
    download_parser.set_defaults(func=cmd_download)

    # batch-download 命令
    batch_parser = subparsers.add_parser('batch-download', help='批量下载书籍')
    batch_parser.add_argument('book_ids', nargs='*', help='书籍ID或URL列表')
    batch_parser.add_argument('-i', '--file', help='包含书籍ID列表的文件路径')
    batch_parser.add_argument('-p', '--path', help='保存路径')
    batch_parser.add_argument('-f', '--format', choices=['txt', 'epub'],
                             default='txt', help='输出格式 (默认: txt)')
    batch_parser.add_argument('-c', '--concurrent', type=int, default=3,
                             help='并发下载数量 (默认: 3, 最大: 5)')
    batch_parser.add_argument('--commit', action='store_true',
                             help='下载完成后自动Git提交')
    batch_parser.set_defaults(func=cmd_batch_download)

    # status 命令
    status_parser = subparsers.add_parser('status', help='显示平台状态')
    status_parser.set_defaults(func=cmd_status)

    # config 命令
    config_parser = subparsers.add_parser('config', help='配置管理')
    config_parser.add_argument('action', choices=['list', 'set', 'get', 'reset'],
                               help='操作: list(列出所有配置), set(设置配置), get(获取配置), reset(重置配置)')
    config_parser.add_argument('key', nargs='?', help='配置键')
    config_parser.add_argument('value', nargs='?', help='配置值')
    config_parser.set_defaults(func=cmd_config)

    # api 命令
    api_parser = subparsers.add_parser('api', help='API 节点管理')
    api_parser.add_argument('action', choices=['list', 'select'],
                           help='操作: list(列出所有节点), select(选择节点)')
    api_parser.add_argument('mode', nargs='?', choices=['auto', 'manual'],
                           help='选择模式: auto(自动选择最快节点), manual(手动指定节点)')
    api_parser.add_argument('url', nargs='?', help='API 节点 URL (仅 manual 模式需要)')
    api_parser.set_defaults(func=cmd_api)

    return parser


def check_termux_dependencies():
    """检查 Termux 环境下的依赖"""
    platform_info = detect_platform()
    
    if platform_info.is_termux:
        # 检查是否缺少依赖
        missing = []
        try:
            import requests
        except ImportError:
            missing.append('requests')
        
        try:
            import aiohttp
        except ImportError:
            missing.append('aiohttp')
        
        if missing:
            print("=" * 50)
            print("Termux 环境检测到缺少依赖:")
            print(f"  缺少: {', '.join(missing)}")
            print("")
            print("建议使用 Termux 专用依赖文件安装:")
            print("  pip install -r requirements-termux.txt")
            print("=" * 50)
            print("")


def main():
    """CLI 主入口"""
    # 检测平台
    platform_info = detect_platform()
    
    # Termux 环境检查依赖
    check_termux_dependencies()
    
    parser = create_parser()
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        return 0
    
    # 执行命令
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\n操作已取消")
        return 130
    except Exception as e:
        print(f"错误: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
