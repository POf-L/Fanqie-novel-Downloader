# -*- coding: utf-8 -*-
"""
下载管理器 - 处理下载状态管理和断点续传
"""

import os
import time
import asyncio
import sys
import inspect
from typing import Optional, Dict, List
from tqdm import tqdm

from config.config import CONFIG, print_lock
from utils.async_logger import safe_print
from .api_manager import get_api_manager
from .text_parser import parse_novel_text_with_catalog, parse_novel_text
from .file_utils import process_chapter_content, create_epub, create_txt

from .download_async import APIManagerExt
from .download_integrity import analyze_download_completeness
from .download_state import clear_status, load_saved_content, load_status, save_content, save_status


def Run(book_id, save_path, file_format='txt', start_chapter=None, end_chapter=None, selected_chapters=None, gui_callback=None):
    """运行下载 - 优化版：减少初始化时间"""

    api = get_api_manager()
    if api is None:
        return False

    def log_message(message, progress=-1):
        if gui_callback and len(inspect.signature(gui_callback).parameters) > 1:
            gui_callback(progress, message)
        else:
            print(message)

    async def async_download_flow():
        """异步下载流程，减少初始化延迟"""
        try:
            # 预初始化异步会话
            log_message("正在初始化下载器...", 2)
            await api.pre_initialize()

            log_message("正在获取书籍信息...", 5)
            book_detail = api.get_book_detail(book_id)
            if not book_detail:
                log_message("获取书籍信息失败")
                return False

            name = book_detail.get("book_name", f"未知小说_{book_id}")
            author_name = book_detail.get("author", "未知作者")
            description = book_detail.get("abstract", "")
            cover_url = book_detail.get("thumb_url", "")

            log_message(f"书名: {name}, 作者: {author_name}", 10)

            chapter_results = {}
            use_full_download = False
            speed_mode_downloaded_ids = set()

            # 并行获取章节目录（使用异步方式）
            log_message("正在获取章节列表...", 15)
            chapters = []

            # 并行尝试两个接口
            directory_task = asyncio.create_task(api.get_directory_async(book_id))
            chapter_list_task = asyncio.create_task(api.get_chapter_list_async(book_id))

            # 等待directory接口结果
            directory_data = await directory_task
            if directory_data:
                for idx, ch in enumerate(directory_data):
                    item_id = ch.get("item_id")
                    title = ch.get("title", f"第{idx+1}章")
                    if item_id:
                        chapters.append({"id": str(item_id), "title": title, "index": idx})

            # 如果directory失败，使用chapter_list结果
            if not chapters:
                chapters_data = await chapter_list_task
                if chapters_data:
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

            if not chapters:
                log_message("获取章节列表失败")
                return False

            total_chapters = len(chapters)
            log_message(f"共找到 {total_chapters} 章", 20)

            # 尝试极速下载模式 (仅当没有指定范围且没有选择特定章节时)
            if start_chapter is None and end_chapter is None and not selected_chapters:
                log_message("正在尝试极速下载模式 (整书下载)...", 25)
                full_content = api.get_full_content(book_id)
                if full_content:
                    log_message("整书内容获取成功，正在解析...", 30)
                    # 批量模式：返回 {item_id: content}，可精准与目录对齐
                    if isinstance(full_content, dict):
                        with tqdm(total=len(chapters), desc="处理章节", disable=gui_callback is not None) as pbar:
                            for ch in chapters:
                                raw = full_content.get(ch['id'])
                                if isinstance(raw, str) and raw.strip():
                                    processed = process_chapter_content(raw)
                                    chapter_results[ch['index']] = {
                                        'title': ch['title'],
                                        'content': processed
                                    }
                                    speed_mode_downloaded_ids.add(ch['id'])
                                if pbar:
                                    pbar.update(1)

                        parsed_count = len(speed_mode_downloaded_ids)
                        log_message(f"解析成功，共 {parsed_count} 章", 50)

                        if parsed_count == total_chapters:
                            use_full_download = True
                            log_message("章节处理完成", 80)
                        else:
                            log_message(f"急速模式批量内容不完整 ({parsed_count}/{total_chapters})，将缺失章节切换到普通模式下载")
                    else:
                        full_text = str(full_content)
                        # 使用目录标题来分割内容（兼容旧节点/下载模式）
                        chapters_parsed = parse_novel_text_with_catalog(full_text, chapters)

                        if chapters_parsed and len(chapters_parsed) >= len(chapters) * 0.8:
                            # 成功解析出至少80%的章节
                            log_message(f"解析成功，共 {len(chapters_parsed)} 章", 50)
                            with tqdm(total=len(chapters_parsed), desc="处理章节", disable=gui_callback is not None) as pbar:
                                for ch in chapters_parsed:
                                    processed = process_chapter_content(ch['content'])
                                    chapter_results[ch['index']] = {
                                        'title': ch['title'],
                                        'content': processed
                                    }
                                    if pbar:
                                        pbar.update(1)

                            use_full_download = True
                            log_message("章节处理完成", 80)
                        else:
                            parsed_count = len(chapters_parsed) if chapters_parsed else 0
                            log_message(f"急速模式解析不完整 ({parsed_count}/{total_chapters})，切换到普通模式")
                else:
                    log_message("极速下载失败，切换回普通模式")

            # 如果没有使用极速模式，则走优化的异步模式
            if not use_full_download:

                if not chapters:
                    log_message("未找到章节")
                    return False

                total_chapters = len(chapters)
                log_message(f"共找到 {total_chapters} 章", 20)

                if start_chapter is not None or end_chapter is not None:
                    start_idx = (start_chapter - 1) if start_chapter else 0
                    end_idx = end_chapter if end_chapter else total_chapters
                    chapters = chapters[start_idx:end_idx]
                    log_message(f"下载章节范围: {start_idx+1} 到 {end_idx}")

                if selected_chapters:
                    try:
                        selected_indices = set(int(x) for x in selected_chapters)
                        chapters = [ch for ch in chapters if ch['index'] in selected_indices]
                        log_message(f"已选择 {len(chapters)} 个特定章节")
                    except Exception as e:
                        log_message(f"章节筛选出错: {e}")

                downloaded_ids = load_status(book_id)
                if speed_mode_downloaded_ids:
                    downloaded_ids.update(speed_mode_downloaded_ids)

                # 加载已保存的章节内容（断点续传）
                saved_content = load_saved_content(book_id)
                if saved_content:
                    log_message(f"发现已保存的下载进度，已有 {len(saved_content)} 个章节", 22)
                    chapter_results.update(saved_content)

                chapters_to_download = [ch for ch in chapters if ch["id"] not in downloaded_ids]

                if not chapters_to_download:
                    log_message("所有章节已下载")
                else:
                    log_message(f"开始下载 {len(chapters_to_download)} 章...", 25)

                # 使用优化的异步下载替代ThreadPoolExecutor
                if chapters_to_download:
                    def progress_callback(progress, message):
                        if gui_callback:
                            gui_callback(25 + int(progress * 0.6), message)

                    # 直接复用同一个 API 实例的异步能力，避免复制/共享内部会话状态
                    if hasattr(api, 'download_chapters_async'):
                        api_ext = APIManagerExt()
                        api_ext.base_url = api.base_url
                        api_ext.endpoints = api.endpoints
                        async_results = await api_ext.download_chapters_async(chapters_to_download, progress_callback)
                    else:
                        async_results = await api.download_chapters_async(chapters_to_download, progress_callback)

                    # 合并结果
                    for idx, data in async_results.items():
                        chapter_results[idx] = data
                        # 找到对应的章节ID并标记为已下载
                        for ch in chapters_to_download:
                            if ch['index'] == idx:
                                downloaded_ids.add(ch['id'])
                                break

                # 保存下载状态和章节内容
                save_status(book_id, downloaded_ids)
                save_content(book_id, chapter_results)

            # 其余处理逻辑保持不变...
            # ==================== 下载完整性分析 ====================
            if gui_callback:
                gui_callback(85, "正在分析下载完整性...")
            else:
                log_message("正在分析下载完整性...", 85)

            # 分析结果
            analysis_result = analyze_download_completeness(
                chapter_results,
                chapters if not use_full_download else None,
                log_message
            )

            # 如果有缺失章节，尝试补充下载
            if analysis_result['missing_indices'] and not use_full_download:
                missing_count = len(analysis_result['missing_indices'])
                log_message(f"发现 {missing_count} 个缺失章节，正在补充下载...", 87)

                # 获取缺失章节的信息
                missing_chapters = [ch for ch in chapters if ch['index'] in analysis_result['missing_indices']]

                # 补充下载缺失章节（最多重试3次）
                for retry in range(3):
                    if not missing_chapters:
                        break

                    log_message(f"补充下载第 {retry + 1} 次尝试，剩余 {len(missing_chapters)} 章", 88)
                    still_missing = []

                    for ch in missing_chapters:
                        try:
                            data = api.get_chapter_content(ch["id"])
                            if data and data.get('content'):
                                processed = process_chapter_content(data.get('content', ''))
                                chapter_results[ch['index']] = {
                                    'title': ch['title'],
                                    'content': processed
                                }
                                downloaded_ids.add(ch['id'])
                            else:
                                still_missing.append(ch)
                        except Exception:
                            still_missing.append(ch)
                        time.sleep(0.5)  # 避免请求过快

                    missing_chapters = still_missing
                    if not missing_chapters:
                        log_message("所有缺失章节补充完成", 90)
                        break

                # 更新状态
                save_status(book_id, downloaded_ids)

                # 最终检查
                if missing_chapters:
                    missing_indices = [ch['index'] + 1 for ch in missing_chapters]
                    log_message(f"仍有 {len(missing_chapters)} 章无法下载: {missing_indices[:10]}...", 90)

            # 验证章节顺序（使用 ChapterOrderValidator）
            if gui_callback:
                gui_callback(92, "正在验证章节顺序...")

            # 创建验证器实例
            from .validators import ChapterOrderValidator
            order_validator = ChapterOrderValidator(chapters)

            # 验证顺序
            validation_result = order_validator.validate_order(chapter_results)
            sequential_result = order_validator.verify_sequential(chapter_results)

            if not validation_result['is_valid']:
                if validation_result['gaps']:
                    log_message(f"检测到缺失章节: {len(validation_result['gaps'])} 个", 93)
                if validation_result['out_of_order']:
                    issues_preview = validation_result['out_of_order'][:5]
                    log_message(f"检测到章节序号不连续: {issues_preview}{'...' if len(validation_result['out_of_order']) > 5 else ''}", 93)
            else:
                log_message("章节顺序验证通过", 93)

            # 使用验证器排序章节
            sorted_chapters = order_validator.sort_chapters(chapter_results)

            # 最终统计
            total_expected = len(chapters) if not use_full_download else len(chapter_results)
            total_downloaded = len(chapter_results)
            completeness = (total_downloaded / total_expected * 100) if total_expected > 0 else 100

            log_message(f"下载统计: {total_downloaded}/{total_expected} 章 ({completeness:.1f}%)", 95)

            if gui_callback:
                gui_callback(95, "正在生成文件...")

            if file_format == 'epub':
                output_file = create_epub(name, author_name, description, cover_url, sorted_chapters, save_path)
            else:
                output_file = create_txt(name, author_name, description, sorted_chapters, save_path)

            # 下载完成后清除临时状态文件
            clear_status(book_id)

            # 最终结果
            if completeness >= 100:
                log_message(f"下载完成! 文件: {output_file}", 100)
            else:
                log_message(f"下载完成(部分章节缺失)! 文件: {output_file}", 100)

            return True

        except Exception as e:
            log_message(f"下载失败: {str(e)}")
            return False
        finally:
            # 清理异步会话
            try:
                await api.close_async()
            except:
                pass

    # 运行异步下载流程 - 打包环境兼容版
    try:
        # 检查是否已有事件循环
        try:
            loop = asyncio.get_running_loop()
            # 如果已有运行中的循环，创建任务
            task = loop.create_task(async_download_flow())
            return asyncio.run_coroutine_threadsafe(task, loop).result()
        except RuntimeError:
            # 没有运行中的循环，创建新的
            if sys.platform == 'win32' and getattr(sys, 'frozen', False):
                # Windows打包环境特殊处理
                try:
                    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
                except AttributeError:
                    pass

            return asyncio.run(async_download_flow())
    except Exception as e:
        log_message(f"下载失败: {str(e)}")
        return False
