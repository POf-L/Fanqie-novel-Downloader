# -*- coding: utf-8 -*-
"""固定中文消息定义（已移除多语言支持）。"""

from typing import Dict


MESSAGES_ZH: Dict[str, str] = {
    "dl_search_error": "搜索异常: {}",
    "dl_detail_error": "获取书籍详情异常: {}",
    "dl_chapter_list_start": "[DEBUG] 开始获取章节列表: ID={}",
    "dl_chapter_list_resp": "[DEBUG] 章节列表响应: {}",
    "dl_chapter_list_error": "获取章节列表异常: {}",
    "dl_content_error": "获取章节内容异常: {}",
    "dl_save_status_fail": "保存下载状态失败: {}",
    "dl_cover_fail": "下载封面失败: {}",
    "dl_cover_add_fail": "添加封面失败: {}",
    "dl_search_fail": "搜索失败: {}",
    "dl_batch_no_books": "没有要下载的书籍",
    "dl_batch_api_fail": "API 初始化失败",
    "dl_batch_start": "开始批量下载，共 {} 本书籍",
    "dl_batch_cancelled": "批量下载已取消",
    "dl_batch_downloading": "[{}/{}] 开始下载: 《{}》",
    "dl_batch_progress": "正在下载第 {} 本...",
    "dl_batch_success": "《{}》下载完成",
    "dl_batch_fail": "《{}》下载失败",
    "dl_batch_exception": "《{}》下载异常: {}",
    "dl_batch_summary": "批量下载完成统计:",
    "dl_batch_stats_success": "   成功: {} 本",
    "dl_batch_stats_fail": "   失败: {} 本",
    "dl_batch_stats_total": "   总计: {} 本",
    "dl_batch_fail_list": "失败列表:",
    "dl_batch_complete": "完成 {}/{} 本",
    "dl_full_content_error": "获取整书内容异常: {}",
    "dl_fetching_info": "正在获取书籍信息...",
    "dl_fetch_info_fail": "获取书籍信息失败",
    "dl_book_info_log": "书名: {}, 作者: {}",
    "dl_try_speed_mode": "正在尝试极速下载模式 (整书下载)...",
    "dl_speed_mode_success": "整书内容获取成功，正在解析...",
    "dl_speed_mode_parsed": "解析成功，共 {} 章",
    "dl_processing_chapters": "处理章节",
    "dl_process_complete": "章节处理完成",
    "dl_speed_mode_fail": "极速下载失败，切换回普通模式",
    "dl_fetch_list_fail": "获取章节列表失败",
    "dl_no_chapters_found": "未找到章节",
    "dl_found_chapters": "共找到 {} 章",
    "dl_range_log": "下载章节范围: {} 到 {}",
    "dl_selected_log": "已选择 {} 个特定章节",
    "dl_filter_error": "章节筛选出错: {}",
    "dl_all_downloaded": "所有章节已下载",
    "dl_start_download_log": "开始下载 {} 章...",
    "dl_analyzing_completeness": "正在分析下载完整性...",
    "dl_analyze_no_chapters": "没有下载到任何章节",
    "dl_analyze_summary": "完整性检查: 期望 {} 章，已下载 {} 章，缺失 {} 章",
    "dl_analyze_missing": "   缺失章节: {}...",
    "dl_analyze_pass": "完整性检查通过: 共 {} 章全部下载",
    "dl_analyze_gap": "检测到章节索引不连续，可能缺失: {}...",
    "dl_analyze_order_fail": "章节顺序检查: 发现 {} 处不连续，共缺少 {} 个位置",
    "dl_analyze_order_pass": "章节顺序检查通过",
    "dl_missing_retry": "发现 {} 个缺失章节，正在补充下载...",
    "dl_retry_log": "补充下载第 {} 次尝试，剩余 {} 章",
    "dl_retry_success": "所有缺失章节补充完成",
    "dl_retry_fail": "仍有 {} 章无法下载: {}...",
    "dl_verifying_order": "正在验证章节顺序...",
    "dl_intro_title": "简介",
    "dl_book_detail_title": "书籍详情",
    "label_author": "作者: ",
    "dl_unknown_author": "未知作者",
    "dl_chapter_title": "第{}章",
}


def t(key: str, *args) -> str:
    """返回固定中文消息；找不到 key 时回退为 key。"""
    message = MESSAGES_ZH.get(key, key)
    if not args:
        return message
    try:
        return message.format(*args)
    except Exception:
        return message

