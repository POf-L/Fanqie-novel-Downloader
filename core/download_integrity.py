# -*- coding: utf-8 -*-
"""
下载完整性分析 - 从 download_manager.py 拆分
"""

from __future__ import annotations


def analyze_download_completeness(chapter_results: dict, expected_chapters: list = None, log_func=None) -> dict:
    """
    分析下载完整性

    Args:
        chapter_results: 已下载的章节结果 {index: {'title': ..., 'content': ...}}
        expected_chapters: 期望的章节列表 [{'id': ..., 'title': ..., 'index': ...}]
        log_func: 日志输出函数

    Returns:
        分析结果字典:
        - total_expected: 期望总章节数
        - total_downloaded: 已下载章节数
        - missing_indices: 缺失的章节索引列表
        - order_correct: 顺序是否正确
        - completeness_percent: 完整度百分比
    """
    def log(msg, progress=-1):
        if log_func:
            log_func(msg, progress)
        else:
            print(msg)

    result = {
        'total_expected': 0,
        'total_downloaded': len(chapter_results),
        'missing_indices': [],
        'order_correct': True,
        'completeness_percent': 100.0
    }

    if not chapter_results:
        log("没有下载到任何章节")
        result['completeness_percent'] = 0
        return result

    # 获取已下载的章节索引
    downloaded_indices = set(chapter_results.keys())

    # 如果有期望的章节列表，进行完整性比对
    if expected_chapters:
        expected_indices = set(ch['index'] for ch in expected_chapters)
        result['total_expected'] = len(expected_indices)

        # 查找缺失的章节
        missing_indices = expected_indices - downloaded_indices
        result['missing_indices'] = sorted(list(missing_indices))

        if missing_indices:
            missing_count = len(missing_indices)
            log(f"完整性检查: 期望 {len(expected_indices)} 章，已下载 {len(downloaded_indices)} 章，缺失 {missing_count} 章")

            # 显示部分缺失章节信息
            if missing_count <= 10:
                missing_titles = []
                for ch in expected_chapters:
                    if ch['index'] in missing_indices:
                        missing_titles.append(f"第{ch['index']+1}章: {ch['title']}")
                log(f"   缺失章节: {', '.join(missing_titles[:5])}...")
        else:
            log(f"完整性检查通过: 共 {len(expected_indices)} 章全部下载")
    else:
        # 没有期望列表，使用已下载内容分析
        result['total_expected'] = len(chapter_results)

        # 检查索引是否连续
        sorted_indices = sorted(downloaded_indices)
        if sorted_indices:
            min_idx, max_idx = sorted_indices[0], sorted_indices[-1]
            expected_range = set(range(min_idx, max_idx + 1))
            missing_in_range = expected_range - downloaded_indices

            if missing_in_range:
                result['missing_indices'] = sorted(list(missing_in_range))
                log(f"检测到章节索引不连续，可能缺失: {sorted(missing_in_range)[:10]}...")

    # 验证章节顺序（检查标题中的章节号是否递增）
    sorted_results = sorted(chapter_results.items(), key=lambda x: x[0])
    order_issues = []

    for i in range(1, len(sorted_results)):
        prev_idx, prev_data = sorted_results[i-1]
        curr_idx, curr_data = sorted_results[i]

        # 检查索引是否连续
        if curr_idx != prev_idx + 1:
            order_issues.append({
                'type': 'gap',
                'from_index': prev_idx,
                'to_index': curr_idx,
                'gap': curr_idx - prev_idx - 1
            })

    if order_issues:
        result['order_correct'] = False
        total_gaps = sum(issue['gap'] for issue in order_issues)
        log(f"章节顺序检查: 发现 {len(order_issues)} 处不连续，共缺少 {total_gaps} 个位置")
    else:
        log("章节顺序检查通过")

    # 计算完整度
    if result['total_expected'] > 0:
        result['completeness_percent'] = (result['total_downloaded'] / result['total_expected']) * 100

    return result

