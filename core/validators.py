# -*- coding: utf-8 -*-
"""
章节顺序验证器 - 验证和修复章节顺序
"""

from typing import List, Dict


class ChapterOrderValidator:
    """验证和修复章节顺序
    
    确保下载的章节按正确顺序排列，检测缺失和重复
    """
    
    def __init__(self, expected_chapters: List[dict]):
        """
        Args:
            expected_chapters: 期望的章节列表 [{'id': str, 'title': str, 'index': int}, ...]
        """
        self.expected_chapters = expected_chapters
        self.chapter_map = {str(ch.get('id', ch.get('item_id', ''))): ch.get('index', i) 
                          for i, ch in enumerate(expected_chapters)}
        self.index_to_chapter = {ch.get('index', i): ch for i, ch in enumerate(expected_chapters)}
    
    def validate_order(self, chapter_results: dict) -> dict:
        """
        验证章节顺序
        
        Args:
            chapter_results: 下载结果 {index: {'title': str, 'content': str}, ...}
        
        Returns:
            {
                'is_valid': bool,
                'gaps': List[int],      # 缺失的章节索引
                'out_of_order': List[tuple],  # 顺序错误的章节对
                'duplicates': List[int]  # 重复的章节索引
            }
        """
        result = {
            'is_valid': True,
            'gaps': [],
            'out_of_order': [],
            'duplicates': []
        }
        
        if not chapter_results:
            return result
        
        # 获取所有索引并排序
        indices = sorted(chapter_results.keys())
        
        if not indices:
            return result
        
        # 检查缺失的章节（在期望范围内）
        expected_indices = set(range(len(self.expected_chapters)))
        downloaded_indices = set(indices)
        result['gaps'] = sorted(list(expected_indices - downloaded_indices))
        
        # 检查顺序是否正确（索引应该是连续递增的）
        for i in range(1, len(indices)):
            if indices[i] != indices[i-1] + 1:
                # 发现不连续
                result['out_of_order'].append((indices[i-1], indices[i]))
        
        # 检查是否有效
        if result['gaps'] or result['out_of_order'] or result['duplicates']:
            result['is_valid'] = False
        
        return result
    
    def sort_chapters(self, chapter_results: dict) -> List[dict]:
        """
        按正确顺序排序章节

        Args:
            chapter_results: 下载结果 {index: {'title': str, 'content': str}, ...}

        Returns:
            排序后的章节列表 [{'index': int, 'title': str, 'content': str}, ...]
        """
        sorted_chapters = []

        # 确保 key 是整数类型后排序
        int_keys = []
        for k in chapter_results.keys():
            try:
                int_keys.append(int(k))
            except (ValueError, TypeError):
                # 如果无法转换为整数，跳过
                continue

        int_keys.sort()

        for index in int_keys:
            chapter_data = chapter_results.get(index) or chapter_results.get(str(index))
            if chapter_data:
                sorted_chapters.append({
                    'index': index,
                    'title': chapter_data.get('title', f'第{index + 1}章'),
                    'content': chapter_data.get('content', '')
                })

        return sorted_chapters
    
    def map_bulk_content(self, bulk_data: dict, item_ids: List[str]) -> dict:
        """
        将批量下载内容映射到正确的章节索引
        
        Args:
            bulk_data: 批量下载的原始数据 {item_id: content, ...}
            item_ids: 章节ID列表（按目录顺序）
        
        Returns:
            映射后的结果 {index: {'title': str, 'content': str}, ...}
        """
        result = {}
        
        for idx, item_id in enumerate(item_ids):
            item_id_str = str(item_id)
            if item_id_str in bulk_data:
                content_data = bulk_data[item_id_str]
                if isinstance(content_data, dict):
                    result[idx] = {
                        'title': content_data.get('title', f'第{idx + 1}章'),
                        'content': content_data.get('content', '')
                    }
                else:
                    result[idx] = {
                        'title': f'第{idx + 1}章',
                        'content': str(content_data)
                    }
        
        return result
    
    def verify_sequential(self, chapter_results: dict) -> dict:
        """
        验证章节索引是否连续无间隙
        
        Args:
            chapter_results: 下载结果
        
        Returns:
            {
                'is_sequential': bool,
                'missing_count': int,
                'missing_indices': List[int]
            }
        """
        if not chapter_results:
            return {'is_sequential': True, 'missing_count': 0, 'missing_indices': []}
        
        indices = sorted(chapter_results.keys())
        min_idx, max_idx = indices[0], indices[-1]
        
        expected_set = set(range(min_idx, max_idx + 1))
        actual_set = set(indices)
        missing = sorted(list(expected_set - actual_set))
        
        return {
            'is_sequential': len(missing) == 0,
            'missing_count': len(missing),
            'missing_indices': missing
        }
    
    def map_text_parsed_content(self, parsed_chapters: List[dict], catalog: List[dict]) -> dict:
        """
        将文本解析模式的章节内容映射到正确的索引
        
        使用目录中的章节标题来匹配解析出的章节，确保顺序正确
        
        Args:
            parsed_chapters: 解析出的章节列表 [{'title': str, 'content': str}, ...]
            catalog: 目录章节列表 [{'id': str, 'title': str, 'index': int}, ...]
        
        Returns:
            映射后的结果 {index: {'title': str, 'content': str}, ...}
        """
        result = {}
        
        # 构建标题到目录索引的映射
        title_to_index = {}
        for ch in catalog:
            # 标准化标题（去除空白、统一格式）
            normalized_title = ch.get('title', '').strip()
            title_to_index[normalized_title] = ch.get('index', 0)
        
        # 映射解析出的章节
        for parsed_ch in parsed_chapters:
            parsed_title = parsed_ch.get('title', '').strip()
            
            # 尝试精确匹配
            if parsed_title in title_to_index:
                idx = title_to_index[parsed_title]
                result[idx] = {
                    'title': parsed_title,
                    'content': parsed_ch.get('content', '')
                }
            else:
                # 尝试模糊匹配（去除标点符号和空格）
                import re
                clean_parsed = re.sub(r'[\s\u3000]+', '', parsed_title)
                for cat_title, idx in title_to_index.items():
                    clean_cat = re.sub(r'[\s\u3000]+', '', cat_title)
                    if clean_parsed == clean_cat:
                        result[idx] = {
                            'title': cat_title,  # 使用目录中的标准标题
                            'content': parsed_ch.get('content', '')
                        }
                        break
        
        return result
    
    def get_validation_summary(self, chapter_results: dict) -> str:
        """
        获取验证结果的摘要信息
        
        Args:
            chapter_results: 下载结果
        
        Returns:
            摘要字符串
        """
        validation = self.validate_order(chapter_results)
        sequential = self.verify_sequential(chapter_results)
        
        lines = []
        
        if validation['is_valid'] and sequential['is_sequential']:
            lines.append("✓ 章节顺序验证通过")
        else:
            if validation['gaps']:
                lines.append(f"⚠ 缺失章节: {len(validation['gaps'])} 个")
            if validation['out_of_order']:
                lines.append(f"⚠ 顺序异常: {len(validation['out_of_order'])} 处")
            if sequential['missing_indices']:
                lines.append(f"⚠ 索引不连续: 缺失 {sequential['missing_count']} 个")
        
        return '\n'.join(lines) if lines else "章节顺序正常"
