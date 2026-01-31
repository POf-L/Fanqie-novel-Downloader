# -*- coding: utf-8 -*-
"""
CLI 工具函数 - 从 core/cli.py 拆分
"""

from __future__ import annotations

from typing import Optional

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
