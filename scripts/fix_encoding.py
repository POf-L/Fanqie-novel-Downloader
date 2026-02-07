# -*- coding: utf-8 -*-
"""
编码修复脚本 - 修复项目中所有文件的编码问题
"""

import os
import sys
import chardet
from typing import List, Tuple, Optional

def detect_file_encoding(file_path: str) -> Tuple[str, float]:
    """
    检测文件编码
    
    Args:
        file_path: 文件路径
        
    Returns:
        (编码名称, 置信度)
    """
    try:
        with open(file_path, 'rb') as f:
            raw_data = f.read()
            result = chardet.detect(raw_data)
            return result['encoding'], result['confidence']
    except Exception as e:
        print(f"检测文件编码失败 {file_path}: {e}")
        return None, 0.0

def fix_file_encoding(file_path: str, backup: bool = True) -> bool:
    """
    修复文件编码，确保保存为UTF-8
    
    Args:
        file_path: 文件路径
        backup: 是否创建备份
        
    Returns:
        是否修复成功
    """
    try:
        # 检测当前编码
        encoding, confidence = detect_file_encoding(file_path)
        
        if encoding is None:
            print(f"无法检测文件编码: {file_path}")
            return False
            
        print(f"文件: {file_path}")
        print(f"  检测到编码: {encoding} (置信度: {confidence:.2f})")
        
        # 读取文件内容
        with open(file_path, 'rb') as f:
            raw_data = f.read()
        
        # 尝试多种编码方式解码
        decoded_content = None
        encodings_to_try = [
            encoding,  # 检测到的编码
            'utf-8',
            'gbk',
            'gb2312',
            'gb18030',
            'big5',
            'latin1',
            'cp1252'
        ]
        
        for enc in encodings_to_try:
            try:
                if enc:
                    decoded_content = raw_data.decode(enc)
                    print(f"  成功使用编码: {enc}")
                    break
            except (UnicodeDecodeError, LookupError):
                continue
        
        if decoded_content is None:
            print(f"  无法解码文件内容")
            return False
        
        # 检查是否包含乱码字符
        has_mojibake = False
        common_mojibake = [
            'ä¸', 'å', 'è', 'äº', 'ä»', 'ä¸', 'æ', 'ä»¬', 'è¿', 'ä¸ª',
            'ç¨', 'åº', 'å', 'ç', 'ç«', 'ä½¿', 'ç¨', 'äº', 'è¿', 'ä¸ª'
        ]
        
        for moji in common_mojibake:
            if moji in decoded_content:
                has_mojibake = True
                break
        
        if not has_mojibake and encoding.lower() == 'utf-8':
            print(f"  文件已经是正确的UTF-8编码，无需修复")
            return True
        
        # 创建备份
        if backup:
            backup_path = file_path + '.backup'
            try:
                with open(backup_path, 'wb') as f:
                    f.write(raw_data)
                print(f"  已创建备份: {backup_path}")
            except Exception as e:
                print(f"  创建备份失败: {e}")
        
        # 尝试修复乱码
        if has_mojibake:
            print(f"  检测到乱码，尝试修复...")
            # 尝试将乱码字符重新编码为正确的UTF-8
            try:
                # 常见的乱码模式：UTF-8被错误地解码为Latin-1
                fixed_content = decoded_content.encode('latin1').decode('utf-8')
                decoded_content = fixed_content
                print(f"  乱码修复成功")
            except (UnicodeEncodeError, UnicodeDecodeError):
                try:
                    # 另一种常见模式：GBK被错误地解码为UTF-8
                    fixed_content = decoded_content.encode('utf-8').decode('gbk')
                    decoded_content = fixed_content
                    print(f"  乱码修复成功（GBK模式）")
                except (UnicodeEncodeError, UnicodeDecodeError):
                    print(f"  无法自动修复乱码，保持原内容")
        
        # 写入UTF-8编码的文件
        with open(file_path, 'w', encoding='utf-8', newline='') as f:
            f.write(decoded_content)
        
        print(f"  文件已修复并保存为UTF-8编码")
        return True
        
    except Exception as e:
        print(f"修复文件失败 {file_path}: {e}")
        return False

def find_files_to_fix(root_dir: str, extensions: Optional[List[str]] = None) -> List[str]:
    """
    查找需要修复的文件
    
    Args:
        root_dir: 根目录
        extensions: 文件扩展名列表，None表示所有文件
        
    Returns:
        需要修复的文件路径列表
    """
    files_to_fix = []
    
    for root, dirs, files in os.walk(root_dir):
        # 跳过一些目录
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'node_modules']]
        
        for file in files:
            if extensions is None or any(file.endswith(ext) for ext in extensions):
                file_path = os.path.join(root, file)
                files_to_fix.append(file_path)
    
    return files_to_fix

def main():
    """主函数"""
    print("=== 编码修复工具 ===")
    print("正在修复项目中的编码问题...")
    
    # 获取项目根目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    
    print(f"项目根目录: {project_root}")
    
    # 查找需要修复的文件类型
    extensions = [
        '.py', '.md', '.txt', '.html', '.htm', '.css', '.js',
        '.json', '.yml', '.yaml', '.sh', '.bat', '.cmd'
    ]
    
    files_to_fix = find_files_to_fix(project_root, extensions)
    print(f"找到 {len(files_to_fix)} 个文件需要检查")
    
    # 统计信息
    fixed_count = 0
    failed_count = 0
    skipped_count = 0
    
    # 逐个修复文件
    for i, file_path in enumerate(files_to_fix, 1):
        print(f"\n[{i}/{len(files_to_fix)}] 处理文件: {file_path}")
        
        try:
            if fix_file_encoding(file_path, backup=True):
                fixed_count += 1
            else:
                failed_count += 1
        except KeyboardInterrupt:
            print("\n用户中断操作")
            break
        except Exception as e:
            print(f"处理文件时发生错误: {e}")
            failed_count += 1
    
    # 输出统计信息
    print(f"\n=== 修复完成 ===")
    print(f"总文件数: {len(files_to_fix)}")
    print(f"修复成功: {fixed_count}")
    print(f"修复失败: {failed_count}")
    print(f"跳过文件: {skipped_count}")
    
    if failed_count > 0:
        print(f"\n注意: 有 {failed_count} 个文件修复失败，请手动检查")
    
    print(f"\n所有备份文件都以 .backup 扩展名保存")
    print(f"如果修复结果不满意，可以从备份文件恢复")

if __name__ == "__main__":
    # 安装必要的依赖
    try:
        import chardet
    except ImportError:
        print("正在安装 chardet...")
        os.system(f"{sys.executable} -m pip install chardet")
        import chardet
    
    main()
