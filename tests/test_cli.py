# -*- coding: utf-8 -*-
"""
CLI 模块的属性测试和单元测试
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from hypothesis import given, strategies as st, settings

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cli import (
    create_parser,
    format_table,
    cmd_search,
    cmd_info,
    cmd_download,
    cmd_status,
)


# ============================================================
# Property 2: CLI Command Completeness
# **Validates: Requirements 2.1, 2.2, 2.3**
# ============================================================

class TestCLICommandCompleteness:
    """
    **Feature: multi-platform-support, Property 2: CLI Command Completeness**
    
    *For any* core download function (search, download, info), there SHALL exist 
    a corresponding CLI command that accepts appropriate arguments and produces 
    formatted output.
    """
    
    def test_all_core_commands_exist(self):
        """所有核心命令应该存在"""
        parser = create_parser()
        
        # 测试 search 命令
        args = parser.parse_args(['search', 'test'])
        assert hasattr(args, 'func')
        assert args.keyword == 'test'
        
        # 测试 info 命令
        args = parser.parse_args(['info', '12345'])
        assert hasattr(args, 'func')
        assert args.book_id == '12345'
        
        # 测试 download 命令
        args = parser.parse_args(['download', '12345'])
        assert hasattr(args, 'func')
        assert args.book_id == '12345'
        
        # 测试 status 命令
        args = parser.parse_args(['status'])
        assert hasattr(args, 'func')
    
    def test_download_command_accepts_format_option(self):
        """download 命令应该接受格式选项"""
        parser = create_parser()
        
        # txt 格式
        args = parser.parse_args(['download', '12345', '-f', 'txt'])
        assert args.format == 'txt'
        
        # epub 格式
        args = parser.parse_args(['download', '12345', '-f', 'epub'])
        assert args.format == 'epub'
    
    def test_download_command_accepts_path_option(self):
        """download 命令应该接受路径选项"""
        parser = create_parser()
        
        args = parser.parse_args(['download', '12345', '-p', '/tmp/novels'])
        assert args.path == '/tmp/novels'
    
    @given(st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('L', 'N'))))
    @settings(max_examples=100, deadline=None)
    def test_search_accepts_any_keyword(self, keyword):
        """search 命令应该接受任何关键词"""
        if not keyword.strip():
            return  # 跳过空白关键词
        
        parser = create_parser()
        args = parser.parse_args(['search', keyword])
        assert args.keyword == keyword


# ============================================================
# Property 4: Path Input Acceptance
# **Validates: Requirements 3.2, 3.3**
# ============================================================

class TestPathInputAcceptance:
    """
    **Feature: multi-platform-support, Property 4: Path Input Acceptance**
    
    *For any* valid filesystem path string, the CLI and web interface SHALL 
    accept it as a download destination without path format errors.
    """
    
    @given(st.sampled_from([
        '/home/user/downloads',
        '/tmp/novels',
        'C:\\Users\\Test\\Downloads',
        'D:\\小说',
        './downloads',
        '../novels',
        '~/Downloads',
        '/data/data/com.termux/files/home',
    ]))
    @settings(max_examples=100, deadline=None)
    def test_cli_accepts_various_path_formats(self, path):
        """CLI 应该接受各种路径格式"""
        parser = create_parser()
        args = parser.parse_args(['download', '12345', '-p', path])
        assert args.path == path
    
    def test_path_with_spaces_accepted(self):
        """包含空格的路径应该被接受"""
        parser = create_parser()
        args = parser.parse_args(['download', '12345', '-p', '/path/with spaces/here'])
        assert args.path == '/path/with spaces/here'
    
    def test_path_with_unicode_accepted(self):
        """包含 Unicode 字符的路径应该被接受"""
        parser = create_parser()
        args = parser.parse_args(['download', '12345', '-p', '/路径/下载'])
        assert args.path == '/路径/下载'


# ============================================================
# Unit Tests
# ============================================================

class TestFormatTable:
    """表格格式化单元测试"""
    
    def test_format_table_with_data(self):
        """有数据时应该正确格式化"""
        headers = ['ID', 'Name']
        rows = [['1', 'Test'], ['2', 'Demo']]
        
        result = format_table(headers, rows)
        
        assert 'ID' in result
        assert 'Name' in result
        assert 'Test' in result
        assert 'Demo' in result
    
    def test_format_table_empty_rows(self):
        """空数据时应该返回提示"""
        headers = ['ID', 'Name']
        rows = []
        
        result = format_table(headers, rows)
        assert '无数据' in result
    
    def test_format_table_contains_separator(self):
        """表格应该包含分隔线"""
        headers = ['A', 'B']
        rows = [['1', '2']]
        
        result = format_table(headers, rows)
        assert '-' in result


class TestParserHelp:
    """解析器帮助信息测试"""
    
    def test_parser_has_description(self):
        """解析器应该有描述"""
        parser = create_parser()
        assert parser.description is not None
        assert len(parser.description) > 0
    
    def test_parser_has_examples(self):
        """解析器应该有示例"""
        parser = create_parser()
        assert parser.epilog is not None
        assert 'search' in parser.epilog
        assert 'download' in parser.epilog


class TestStatusCommand:
    """status 命令测试"""
    
    def test_status_command_returns_zero(self):
        """status 命令应该返回 0"""
        parser = create_parser()
        args = parser.parse_args(['status'])
        
        result = cmd_status(args)
        assert result == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
