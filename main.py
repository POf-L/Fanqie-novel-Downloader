#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
番茄小说下载器主入口文件
支持GUI和命令行两种模式
"""

import sys
import os
import argparse

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="番茄小说下载器")
    parser.add_argument("--cli", action="store_true", help="使用命令行模式")
    parser.add_argument("--enhanced", action="store_true", help="使用增强下载器")
    parser.add_argument("--gui", action="store_true", help="使用图形界面模式（默认）")
    
    args = parser.parse_args()
    
    # 如果没有指定模式，默认使用GUI
    if not any([args.cli, args.enhanced, args.gui]):
        args.gui = True
    
    try:
        if args.enhanced:
            # 启动增强下载器
            from enhanced_downloader import main as enhanced_main
            enhanced_main()
        elif args.cli:
            # 启动命令行模式
            from tomato_novel_api import main as cli_main
            cli_main()
        else:
            # 启动GUI模式
            import tkinter as tk
            from gui import ModernNovelDownloaderGUI
            
            root = tk.Tk()
            app = ModernNovelDownloaderGUI(root)
            root.mainloop()
            
    except ImportError as e:
        print(f"导入模块失败: {e}")
        print("请确保已安装所有必要的依赖包")
        sys.exit(1)
    except Exception as e:
        print(f"程序运行出错: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()