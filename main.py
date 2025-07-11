"""番茄小说下载器主程序入口"""

import os
import sys
import logging
import tempfile
import datetime

# 日志配置
log_file = os.path.join(tempfile.gettempdir(), f"fanqie_downloader_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
logging.basicConfig(
    filename=log_file,
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 启动日志
logging.info("番茄小说下载器启动")

# 启动时检查更新
try:
    from updater import check_update
    update_msg = check_update()
    if update_msg:
        print(update_msg)
        logging.info(update_msg)
except Exception as _e:
    # 更新检查失败不影响主流程
    logging.debug(f"更新检查失败: {_e}")
logging.info(f"Python版本: {sys.version}")
logging.info(f"运行路径: {os.getcwd()}")
logging.info(f"日志文件: {log_file}")



try:
    from gui import NovelDownloaderGUI
    from utils import center_window_on_screen
    from config import CONFIG
    import customtkinter as ctk
except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保已安装所有必需的依赖包")
    print("运行: pip install -r requirements.txt")
    sys.exit(1)

def main():
    """程序主入口"""
    try:
        app = NovelDownloaderGUI()
        app.mainloop()
    except Exception as e:
        logging.exception(f"程序运行出错: {str(e)}")
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("错误", f"程序运行出错: {str(e)}\n\n详细日志已保存到: {log_file}")
        root.destroy()
        raise

if __name__ == "__main__":
    try:
        logging.info("调用main()函数")
        main()
    except Exception as e:
        logging.exception(f"未捕获的异常: {str(e)}")
        print(f"程序出错! 详细日志已保存到: {log_file}")
        input("按Enter键退出...")