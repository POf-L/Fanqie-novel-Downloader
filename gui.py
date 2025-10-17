import tkinter as tk
from tkinter import ttk, messagebox, filedialog, font, scrolledtext
import threading
import os
import time
import json
import requests
import webbrowser
from PIL import Image, ImageTk
from io import BytesIO
from novel_downloader import NovelDownloaderAPI, api_manager, async_api_manager
import novel_downloader
from ebooklib import epub
from config import __version__, __github_repo__
import sys
import platform
import tempfile
import shutil

# 内置外部更新入口：当以 '--run-updater' 启动时，直接运行 external_updater 而非 GUI
if '--run-updater' in sys.argv:
    try:
        import external_updater as _ext_updater
        # 重写 sys.argv 以兼容 external_updater.main() 的入参格式
        idx = sys.argv.index('--run-updater')
        new_argv = [sys.argv[0]]
        if len(sys.argv) > idx + 1:
            new_argv.append(sys.argv[idx + 1])  # update_info_json
        if len(sys.argv) > idx + 2:
            new_argv.append(sys.argv[idx + 2])  # target_exe
        sys.argv = new_argv
        _ext_updater.main()
    except Exception as _e:
        print(f"外部更新执行失败: {_e}")
    finally:
        sys.exit(0)

# 添加HEIC支持
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    print("HEIC format support enabled")
except ImportError:
    print("pillow-heif not installed, HEIC format may not display properly")

class ModernNovelDownloaderGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("番茄小说下载器 - 现代版")
        self.root.geometry("1200x800")
        self.root.minsize(1000, 700)
        
        # 设置主题色彩
        self.colors = {
            'primary': '#1976D2',      # 主色调 - 蓝色
            'primary_dark': '#1565C0', # 深蓝色
            'secondary': '#FF5722',    # 次要色 - 橙色
            'success': '#4CAF50',      # 成功色 - 绿色
            'warning': '#FF9800',      # 警告色 - 橙色
            'error': '#F44336',        # 错误色 - 红色
            'background': '#FAFAFA',   # 背景色
            'surface': '#FFFFFF',      # 表面色
            'text_primary': '#212121', # 主要文本
            'text_secondary': '#757575', # 次要文本
            'border': '#E0E0E0'        # 边框色
        }
        
        self.root.configure(bg=self.colors['background'])
        
        # 下载状态
        self.is_downloading = False
        self.start_time = None
        self.api = None  # 延迟初始化，避免阻塞界面
        self.search_results_data = []  # 存储搜索结果数据
        self.cover_images = {}  # 存储封面图片，防止被垃圾回收
        
        # 性能优化：限制并发下载
        self.max_concurrent_downloads = 2  # 限制同时下载的封面数
        self.download_semaphore = threading.Semaphore(self.max_concurrent_downloads)
        self.cover_download_queue = []  # 封面下载队列
        
        # 初始化版本信息和自动更新
        self.current_version = __version__
        
        # 尝试导入 updater 模块（可选）
        try:
            from updater import AutoUpdater, is_official_release_build
            self.updater = AutoUpdater(__github_repo__, self.current_version)
            self.updater.register_callback(self.on_update_event)
            self.official_build = is_official_release_build()
        except ImportError as e:
            print(f"updater 模块不可用: {e}")
            self.updater = None
            self.official_build = False

        # 清理可能残留的更新备份文件和旧日志
        self._cleanup_update_backups()
        self._cleanup_old_update_logs()
        
        # 配置文件路径
        self.config_file = "config.json"

        # 加载配置
        self.config = self.load_config()
        

        
        # 设置字体
        self.setup_fonts()
        
        # 创建样式
        self.setup_styles()
        
        # 创建UI
        self.create_widgets()
        
        # 检查已有的验证状态
        self.check_existing_verification()

        # 启用更新系统
        self._check_last_update_status()
        # 启动时自动检查更新（仅官方打包版），受配置项 auto_check_update 控制
        try:
            auto_check = bool(self.config.get('auto_check_update', True))
        except Exception:
            auto_check = True
        if self.official_build and auto_check:
            self.root.after(800, self.check_update_force)

        # 禁用启动时的API测试，避免启动卡顿
        # self.root.after(1000, self._test_api_connection_at_startup)
    
    def setup_fonts(self):
        """设置字体"""
        self.fonts = {
            'title': font.Font(family="微软雅黑", size=20, weight="bold"),
            'subtitle': font.Font(family="微软雅黑", size=14, weight="bold"),
            'body': font.Font(family="微软雅黑", size=10),
            'button': font.Font(family="微软雅黑", size=10, weight="bold"),
            'small': font.Font(family="微软雅黑", size=9),
            'input': font.Font(family="微软雅黑", size=10)
        }
    
    def setup_styles(self):
        """设置ttk样式"""
        style = ttk.Style()
        
        # 配置Notebook样式
        style.configure('Modern.TNotebook', background=self.colors['background'])
        style.configure('Modern.TNotebook.Tab', 
                       padding=[20, 10],
                       font=self.fonts['body'])
        
        # 配置Frame样式
        style.configure('Card.TFrame', 
                       background=self.colors['surface'],
                       relief='flat',
                       borderwidth=1)
        
        # 配置Progressbar样式
        style.configure('Modern.Horizontal.TProgressbar',
                       background=self.colors['primary'],
                       troughcolor=self.colors['border'],
                       borderwidth=0,
                       lightcolor=self.colors['primary'],
                       darkcolor=self.colors['primary'])
    
    def create_widgets(self):
        """创建界面组件"""
        # 主容器
        main_frame = tk.Frame(self.root, bg=self.colors['background'])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 标题栏
        self.create_header(main_frame)
        
        # 主内容区域 - 使用标签页
        self.create_main_content(main_frame)
    
    def create_header(self, parent):
        """创建标题栏"""
        header_frame = tk.Frame(parent, bg=self.colors['primary'], height=80)
        header_frame.pack(fill=tk.X, pady=(0, 20))
        header_frame.pack_propagate(False)
        
        # 标题
        title_label = tk.Label(header_frame, 
                              text="🍅 番茄小说下载器", 
                              font=self.fonts['title'],
                              bg=self.colors['primary'], 
                              fg='white')
        title_label.pack(expand=True)
        
        # 副标题
        subtitle_label = tk.Label(header_frame, 
                                 text="现代化界面 | 高效下载 | 多格式支持", 
                                 font=self.fonts['small'],
                                 bg=self.colors['primary'], 
                                 fg='white')
        subtitle_label.pack()
    
    def create_main_content(self, parent):
        """创建主内容区域"""
        # 创建标签页
        self.notebook = ttk.Notebook(parent, style='Modern.TNotebook')
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # 搜索标签页 - 暂时禁用
        # self.search_frame = ttk.Frame(self.notebook, style='Card.TFrame')
        # self.notebook.add(self.search_frame, text="🔍 搜索")
        # self.create_search_tab()
        
        # 下载标签页
        self.download_frame = ttk.Frame(self.notebook, style='Card.TFrame')
        self.notebook.add(self.download_frame, text="💾 下载管理")
        self.create_download_tab()
        
        # 隐藏设置标签页
        # self.settings_frame = ttk.Frame(self.notebook, style='Card.TFrame')
        # self.notebook.add(self.settings_frame, text="⚙️ 设置")
        # self.create_settings_tab()
    
    def create_card(self, parent, title: str):
        """创建通用卡片容器，带标题栏和内边距，返回内容容器"""
        card_outer = tk.Frame(parent, bg=self.colors['surface'], highlightthickness=1, highlightbackground=self.colors['border'])
        card_outer.pack(fill=tk.X, expand=False, pady=(0, 12))

        # 标题栏
        title_bar = tk.Frame(card_outer, bg=self.colors['surface'])
        title_bar.pack(fill=tk.X, padx=14, pady=(10, 6))
        tk.Label(title_bar,
                 text=title,
                 font=self.fonts['subtitle'],
                 bg=self.colors['surface'],
                 fg=self.colors['text_primary']).pack(side=tk.LEFT)

        # 内容容器
        content_frame = tk.Frame(card_outer, bg=self.colors['surface'])
        content_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 14))
        return content_frame

    def create_button(self, parent, text: str, command, color: str):
        """创建统一风格按钮"""
        btn = tk.Button(parent,
                        text=text,
                        font=self.fonts['button'],
                        bg=color,
                        fg='white',
                        activebackground=color,
                        activeforeground='white',
                        relief=tk.FLAT,
                        bd=0,
                        padx=12,
                        pady=6,
                        cursor='hand2',
                        command=command)
        return btn
    
    def create_search_tab(self):
        """创建搜索标签页"""
        # 主容器
        main_container = tk.Frame(self.search_frame, bg=self.colors['surface'])
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 搜索卡片
        search_card = self.create_card(main_container, "🔍 搜索小说")
        
        # 搜索框架
        search_input_frame = tk.Frame(search_card, bg=self.colors['surface'])
        search_input_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(search_input_frame, text="关键词：", 
                font=self.fonts['body'],
                bg=self.colors['surface'],
                fg=self.colors['text_primary']).pack(side=tk.LEFT, padx=(0, 10))
        
        self.search_entry = tk.Entry(search_input_frame, 
                                    font=self.fonts['input'],
                                    bg='white',
                                    fg=self.colors['text_primary'],
                                    insertbackground=self.colors['primary'])
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.search_entry.bind('<Return>', lambda e: self.search_novels())
        
        self.search_btn = self.create_button(search_input_frame, "🔍 搜索", 
                                            self.search_novels, 
                                            self.colors['primary'])
        self.search_btn.pack(side=tk.LEFT)
        
        # 搜索结果区域
        results_card = self.create_card(main_container, "📚 搜索结果")
        
        # 创建结果滚动区域
        self.results_canvas = tk.Canvas(results_card, bg=self.colors['surface'], 
                                       highlightthickness=0, height=400)
        scrollbar = tk.Scrollbar(results_card, orient="vertical", command=self.results_canvas.yview)
        self.results_scrollable_frame = tk.Frame(self.results_canvas, bg=self.colors['surface'])
        
        self.results_scrollable_frame.bind(
            "<Configure>",
            lambda e: self.results_canvas.configure(scrollregion=self.results_canvas.bbox("all"))
        )
        
        self.results_canvas.create_window((0, 0), window=self.results_scrollable_frame, anchor="nw")
        self.results_canvas.configure(yscrollcommand=scrollbar.set)
        
        self.results_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 初始化搜索结果数据
        self.search_results_data = []
        self.cover_images = {}
    
    def create_download_tab(self):
        """创建下载标签页"""
        # 主容器
        main_container = tk.Frame(self.download_frame, bg=self.colors['surface'])
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 工具栏（在顶部添加）
        toolbar_frame = tk.Frame(main_container, bg=self.colors['surface'])
        toolbar_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 右侧工具按钮
        toolbar_right = tk.Frame(toolbar_frame, bg=self.colors['surface'])
        toolbar_right.pack(side=tk.RIGHT)
        
        # 检查更新按钮
        check_update_btn = self.create_button(toolbar_right,
                                              "🔄 检查更新",
                                              self.manual_check_update,
                                              self.colors['primary'])
        check_update_btn.pack(side=tk.RIGHT, padx=5)
        
        # 版本信息标签
        try:
            from updater import get_current_version
            version_text = f"版本: {get_current_version()}"
        except ImportError:
            version_text = f"版本: {self.current_version}"
        
        version_label = tk.Label(toolbar_frame,
                                text=version_text,
                                font=self.fonts['small'],
                                bg=self.colors['surface'],
                                fg=self.colors['text_secondary'])
        version_label.pack(side=tk.LEFT, padx=5)
        
        # 下载设置卡片
        download_card = self.create_card(main_container, "💾 下载设置")
        
        # 书籍ID输入
        id_frame = tk.Frame(download_card, bg=self.colors['surface'])
        id_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(id_frame, text="书籍ID:", 
                font=self.fonts['body'], 
                bg=self.colors['surface'], 
                fg=self.colors['text_primary']).pack(side=tk.LEFT)
        
        self.book_id_entry = tk.Entry(id_frame, 
                                     font=self.fonts['body'],
                                     bg='white',
                                     fg=self.colors['text_primary'],
                                     relief=tk.FLAT,
                                     bd=1,
                                     highlightthickness=1,
                                     highlightcolor=self.colors['primary'])
        self.book_id_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0))
        
        # 保存路径
        path_frame = tk.Frame(download_card, bg=self.colors['surface'])
        path_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(path_frame, text="保存路径:", 
                font=self.fonts['body'], 
                bg=self.colors['surface'], 
                fg=self.colors['text_primary']).pack(side=tk.LEFT)
        
        self.save_path_entry = tk.Entry(path_frame, 
                                       font=self.fonts['body'],
                                       bg='white',
                                       fg=self.colors['text_primary'],
                                       relief=tk.FLAT,
                                       bd=1,
                                       highlightthickness=1,
                                       highlightcolor=self.colors['primary'])
        self.save_path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 10))
        # 使用配置中的保存路径
        saved_path = self.config.get('save_path', os.getcwd())
        self.save_path_entry.insert(0, saved_path)
        
        browse_btn = self.create_button(path_frame, 
                                       "📁 浏览", 
                                       self.browse_save_path,
                                       self.colors['secondary'])
        browse_btn.pack(side=tk.RIGHT)
        
        # 格式选择
        format_frame = tk.Frame(download_card, bg=self.colors['surface'])
        format_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(format_frame, text="文件格式:", 
                font=self.fonts['body'], 
                bg=self.colors['surface'], 
                fg=self.colors['text_primary']).pack(side=tk.LEFT)
        
        self.format_var = tk.StringVar(value=self.config.get('file_format', 'txt'))
        self.format_var.trace('w', lambda *args: self.save_config())  # 监听变化并保存
        txt_radio = tk.Radiobutton(format_frame, text="TXT", 
                                  variable=self.format_var, value="txt",
                                  font=self.fonts['body'], 
                                  bg=self.colors['surface'], 
                                  fg=self.colors['text_primary'],
                                  selectcolor=self.colors['surface'])
        txt_radio.pack(side=tk.LEFT, padx=(20, 10))
        
        epub_radio = tk.Radiobutton(format_frame, text="EPUB", 
                                   variable=self.format_var, value="epub",
                                   font=self.fonts['body'], 
                                   bg=self.colors['surface'], 
                                   fg=self.colors['text_primary'],
                                   selectcolor=self.colors['surface'])
        epub_radio.pack(side=tk.LEFT, padx=(0, 10))
        
        # 移除章节下载模式选择，只保留整本下载
        
        # 下载按钮
        button_frame = tk.Frame(download_card, bg=self.colors['surface'])
        button_frame.pack(fill=tk.X)
        
        self.download_btn = self.create_button(button_frame, 
                                              "🚀 开始下载", 
                                              self.start_download,
                                              self.colors['success'])
        self.download_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.clear_btn = self.create_button(button_frame, 
                                           "🧹 清理设置", 
                                           self.clear_settings,
                                           self.colors['warning'])
        self.clear_btn.pack(side=tk.LEFT)
        
        # 进度卡片
        progress_card = self.create_card(main_container, "📈 下载进度")
        
        # 进度条
        self.progress = ttk.Progressbar(progress_card, 
                                       orient=tk.HORIZONTAL, 
                                       mode='determinate',
                                       style='Modern.Horizontal.TProgressbar')
        self.progress.pack(fill=tk.X, pady=(0, 10))
        
        # 进度信息
        self.progress_info = tk.Label(progress_card, 
                                     text="准备就绪", 
                                     font=self.fonts['body'],
                                     bg=self.colors['surface'], 
                                     fg=self.colors['text_secondary'])
        self.progress_info.pack(pady=(0, 5))
        
        # 状态标签
        self.status_label = tk.Label(progress_card, 
                                    text="准备就绪", 
                                    font=self.fonts['body'],
                                    bg=self.colors['surface'], 
                                    fg=self.colors['text_primary'])
        self.status_label.pack()
        
        # 日志卡片
        log_card = self.create_card(main_container, "📜 下载日志")
        
        # 日志文本框
        log_frame = tk.Frame(log_card, bg=self.colors['surface'])
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = tk.Text(log_frame, 
                               font=self.fonts['small'],
                               bg='white',
                               fg=self.colors['text_primary'],
                               relief=tk.FLAT,
                               wrap=tk.WORD,
                               height=8)
        
        log_scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scrollbar.set)
        
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def create_settings_tab(self):
        """创建设置标签页"""
        # 主容器
        main_container = tk.Frame(self.settings_frame, bg=self.colors['surface'])
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # API连接卡片
        verification_card = self.create_card(main_container, "🔒 API连接")
        
        # 验证状态显示
        verification_status_frame = tk.Frame(verification_card, bg=self.colors['surface'])
        verification_status_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.verification_status_label = tk.Label(verification_status_frame, 
                                                 text="状态: 检查中...", 
                                                 font=self.fonts['body'],
                                                 bg=self.colors['surface'],
                                                 fg=self.colors['text_secondary'])
        self.verification_status_label.pack(anchor='w')
        
        # 立即更新验证状态
        self.check_existing_verification()
        
        # 验证按钮
        verification_buttons_frame = tk.Frame(verification_card, bg=self.colors['surface'])
        verification_buttons_frame.pack(fill=tk.X, pady=(0, 10))
        
        manual_verify_btn = self.create_button(verification_buttons_frame, 
                                              "🔒 手动验证", 
                                              self.manual_verification,
                                              self.colors['warning'])
        manual_verify_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        clear_token_btn = self.create_button(verification_buttons_frame, 
                                           "🧹 清除验证", 
                                           self.clear_verification_token,
                                           self.colors['error'])
        clear_token_btn.pack(side=tk.LEFT)
        
        # API管理按钮
        api_manage_btn = self.create_button(verification_buttons_frame, 
                                          "🔧 API管理", 
                                          self.show_api_management,
                                          self.colors['primary'])
        api_manage_btn.pack(side=tk.LEFT, padx=(10, 0))
        
        # 版本信息卡片
        version_card = self.create_card(main_container, "📦 版本信息")
        
        # 当前版本信息与更新操作
        version_frame = tk.Frame(version_card, bg=self.colors['surface'])
        version_frame.pack(fill=tk.X, pady=(0, 10))
        
        version_text = f"当前版本: {self.current_version}"
        version_color = self.colors['text_primary']
        
        tk.Label(version_frame, text=version_text, 
                font=self.fonts['body'], 
                bg=self.colors['surface'], 
                fg=version_color).pack(side=tk.LEFT)
        
        # 自动检查更新开关（源码/非官方构建禁用）
        self.auto_update_var = tk.BooleanVar(value=self.config.get('auto_check_update', True))
        auto_check_btn = tk.Checkbutton(version_frame,
                                        text="启动时自动检查更新",
                                        variable=self.auto_update_var,
                                        command=self.save_config,
                                        font=self.fonts['body'],
                                        bg=self.colors['surface'])
        if not getattr(self, 'official_build', False):
            auto_check_btn.configure(state=tk.DISABLED)
        auto_check_btn.pack(side=tk.LEFT, padx=(20, 10))
        
        # 前往发布页按钮
        releases_url = f"https://github.com/{__github_repo__}/releases/latest"
        open_release_btn = self.create_button(version_frame,
                                             "🌐 发布页",
                                             lambda: webbrowser.open(releases_url),
                                             self.colors['secondary'])
        open_release_btn.pack(side=tk.RIGHT)
        
        # 检查更新按钮（源码/非官方构建跳转到Releases页面）
        check_update_btn = self.create_button(version_frame,
                                             "🔄 检查更新",
                                             (self.check_update_now if getattr(self, 'official_build', False) else (lambda: webbrowser.open(releases_url))),
                                             self.colors['primary'])
        check_update_btn.pack(side=tk.RIGHT, padx=(0, 10))
        
        # 关于信息卡片
        about_card = self.create_card(main_container, "ℹ️ 关于")
        
        about_text = f"""🍅 番茄小说下载器 - 现代版 v{self.current_version}

✨ 特性:
• 现代化界面设计
• 多格式支持 (TXT, EPUB)
• 高效搜索和下载
• 实时进度显示
• 智能错误处理
• 自动更新系统

💻 技术支持:
• Python 3.x
• Tkinter GUI
• 多线程下载
• Material Design 风格
• GitHub Actions CI/CD

📞 使用说明:
1. 在搜索标签页中搜索小说
2. 选择想要下载的书籍
3. 在下载标签页中设置参数
4. 点击开始下载

© 2024 番茄小说下载器团队"""
        
        about_label = tk.Label(about_card, 
                              text=about_text,
                              font=self.fonts['small'],
                              bg=self.colors['surface'],
                              fg=self.colors['text_primary'],
                              justify=tk.LEFT,
                              anchor='nw')
        about_label.pack(fill=tk.BOTH, expand=True)
    
    def load_config(self):
        """加载配置文件"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                # 返回默认配置
                return {
                    'save_path': os.getcwd(),
                    'file_format': 'txt',
                    'download_mode': 'full',
                    'auto_check_update': True
                }
        except Exception as e:
            print(f"加载配置失败: {e}")
            return {
                'save_path': os.getcwd(),
                'file_format': 'txt',
                'download_mode': 'full',
                'auto_check_update': True
            }
    
    def save_config(self):
        """保存配置文件"""
        try:
            config = {
                'save_path': self.save_path_entry.get() if hasattr(self, 'save_path_entry') else os.getcwd(),
                'file_format': self.format_var.get() if hasattr(self, 'format_var') else 'txt',
                'download_mode': 'full',  # 固定为整本下载
                'auto_check_update': self.auto_update_var.get() if hasattr(self, 'auto_update_var') else True
            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            print(f"配置已保存到: {self.config_file}")
        except Exception as e:
            print(f"保存配置失败: {e}")
    
    # ========== 事件处理方法 ==========
    

    
    
    def search_novels(self):
        """搜索小说"""
        keyword = self.search_entry.get().strip()
        if not keyword:
            messagebox.showwarning("警告", "请输入搜索关键词")
            return
        
        # 清空之前的结果  
        for widget in self.results_scrollable_frame.winfo_children():
            widget.destroy()
        self.search_results_data.clear()
        self.cover_images.clear()  # 清空封面图片缓存
        
        # 显示搜索中提示
        loading_label = tk.Label(self.results_scrollable_frame, 
                               text="🔍 搜索中，请稍候...", 
                               font=self.fonts['body'],
                               bg=self.colors['surface'],
                               fg=self.colors['text_secondary'])
        loading_label.pack(pady=50)
        
        # 在新线程中执行搜索
        threading.Thread(target=self._search_novels_thread, args=(keyword,), daemon=True).start()
    
    def _is_novel_content(self, book):
        """判断是否为小说内容，过滤掉听书、漫画等"""
        # 检查来源，过滤听书工作室
        source = book.get('source', '')
        if '畅听工作室' in source or '有声' in source or '听书' in source:
            return False
        
        # 检查作者字段，如果包含"主播"关键词，很可能是听书
        author = book.get('author', '')
        if '主播' in author or '播音' in author or '朗读' in author:
            return False
        
        # 检查字数，听书通常word_number为0或很小
        # 但是新API可能不返回word_number，所以如果字段不存在或为空就不过滤
        word_number = book.get('word_number')
        if word_number is not None and word_number != '':
            word_number_str = str(word_number)
            if word_number_str == '0' or (word_number_str.isdigit() and int(word_number_str) < 1000):
                # 但要排除一些特殊情况，如果是正在连载的小说
                creation_status = book.get('creation_status', '1')
                serial_count = book.get('serial_count', '0')
                if creation_status == '1' and serial_count and serial_count.isdigit() and int(serial_count) > 10:
                    # 连载中且章节数较多，可能是小说
                    pass
                else:
                    return False
        
        # 检查书籍类型字段
        book_type = book.get('book_type', '0')
        is_ebook = book.get('is_ebook', '1')
        
        # book_type为"1"的是听书，"0"是小说
        if book_type == '1':
            return False
            
        # is_ebook为"0"的是听书，"1"是电子书/小说
        if is_ebook == '0':
            return False
        
        # 检查分类，排除明确的非小说分类
        category = book.get('category', '').lower()
        excluded_categories = ['听书', '有声书', '漫画', '连环画', '绘本', '音频']
        
        for excluded in excluded_categories:
            if excluded in category:
                return False
        
        # 检查sub_info字段，听书通常显示"章"而不是"人在读"
        sub_info = book.get('sub_info', '')
        if '章' in sub_info and '人在读' not in sub_info:
            # 这可能是听书，进一步检查
            if word_number == '0':
                return False
        
        # 其余情况认为是小说
        return True

    def _search_novels_thread(self, keyword):
        """搜索小说线程函数"""
        try:
            self.search_btn.config(state=tk.DISABLED, text="搜索中...")
            
            # 确保API已初始化
            if self.api is None:
                self.initialize_api()
                
            result = self.api.search_novels(keyword)
            
            if result and result.get('success') and result.get('data'):
                # 从搜索结果中提取书籍数据
                novels = []
                data = result['data']
                
                # 检查新的数据结构 - API返回的是简化格式
                items = data.get('items', [])
                if isinstance(items, list):
                    # 直接处理items列表中的书籍数据
                    for book in items:
                        if (isinstance(book, dict) and 
                            book.get('book_name') and 
                            book.get('author') and 
                            book.get('book_id') and
                            self._is_novel_content(book)):
                            novels.append(book)
                else:
                    # 检查旧的数据结构（兼容性处理）
                    search_tabs = data.get('search_tabs', [])
                    if isinstance(search_tabs, list):
                        for tab_data in search_tabs:
                            # 只处理小说相关的标签页，过滤掉听书等其他类型
                            tab_type = tab_data.get('tab_type', 0)
                            tab_title = tab_data.get('title', '')
                            
                            # tab_type=1 通常是综合/小说，过滤掉听书(tab_type=2)等其他类型
                            if tab_type == 1 and isinstance(tab_data, dict) and tab_data.get('data'):
                                tab_novels = tab_data['data']
                                if isinstance(tab_novels, list):
                                    for item in tab_novels:
                                        if isinstance(item, dict) and item.get('book_data'):
                                            book_data_list = item['book_data']
                                            if isinstance(book_data_list, list):
                                                # 过滤小说内容，排除听书、漫画等其他类型
                                                for book in book_data_list:
                                                    if (book.get('book_name') and 
                                                        book.get('author') and
                                                        self._is_novel_content(book)):
                                                        novels.append(book)
                
                if novels:
                    self.search_results_data = novels
                    # 在主线程中更新UI
                    self.root.after(0, self._update_search_results, novels)
                else:
                    self.root.after(0, lambda: messagebox.showwarning("搜索失败", "未找到相关小说"))
            else:
                self.root.after(0, lambda: self.check_and_handle_api_error("搜索失败或未返回有效结果"))
        except Exception as e:
            self.root.after(0, lambda: self.check_and_handle_api_error(f"搜索失败: {str(e)}"))
        finally:
            self.root.after(0, lambda: self.search_btn.config(state=tk.NORMAL, text="🔍 搜索"))
    
    def _update_search_results(self, novels):
        """更新搜索结果显示"""
        # 清空之前的结果
        for widget in self.results_scrollable_frame.winfo_children():
            widget.destroy()
        
        if not novels:
            no_result_label = tk.Label(self.results_scrollable_frame, 
                                     text="未找到相关小说", 
                                     font=self.fonts['body'],
                                     bg=self.colors['surface'],
                                     fg=self.colors['text_secondary'])
            no_result_label.pack(pady=50)
            return
        
        # 为每本小说创建卡片
        for i, novel in enumerate(novels):
            self.create_novel_card(self.results_scrollable_frame, novel, i)
    
    def create_novel_card(self, parent, novel, index):
        """创建小说卡片"""
        # 主卡片框架
        card_frame = tk.Frame(parent, bg='white', relief=tk.RAISED, bd=1)
        card_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # 内容框架
        content_frame = tk.Frame(card_frame, bg='white')
        content_frame.pack(fill=tk.X, padx=15, pady=15)
        
        # 异步加载封面
        cover_url = novel.get('thumb_url') or novel.get('expand_thumb_url') or novel.get('audio_thumb_url_hd')
        
        # 只有有封面URL时才创建封面框架
        if cover_url:
            # 左侧：封面图片
            cover_frame = tk.Frame(content_frame, bg='white')
            cover_frame.pack(side=tk.LEFT, padx=(0, 15))
            
            # 创建封面占位符（先不显示）
            cover_label = tk.Label(cover_frame)
            
            def load_cover():
                # 使用信号量限制并发
                with self.download_semaphore:
                    try:
                        cover_image = self.download_image(cover_url, (120, 160))
                        if cover_image:
                            book_id = novel.get('book_id', '')
                            self.root.after(0, lambda img=cover_image, bid=book_id: self._update_cover_label(cover_label, img, bid))
                            # 图片加载成功才显示
                            self.root.after(0, lambda: cover_label.pack())
                        else:
                            # 如果加载失败，销毁封面框架
                            self.root.after(0, lambda: cover_frame.destroy())
                    except Exception:
                        # 出错时销毁封面框架
                        self.root.after(0, lambda: cover_frame.destroy())
            
            # 延迟启动下载，避免同时创建过多线程
            threading.Thread(target=load_cover, daemon=True).start()
        
        # 右侧：详细信息
        info_frame = tk.Frame(content_frame, bg='white')
        info_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 书名（大标题）
        title_label = tk.Label(info_frame, text=novel.get('book_name', '未知'), 
                              font=self.fonts['subtitle'],
                              bg='white',
                              fg=self.colors['text_primary'],
                              anchor='w')
        title_label.pack(fill=tk.X, pady=(0, 5))
        
        # 基本信息行
        info_line1 = tk.Frame(info_frame, bg='white')
        info_line1.pack(fill=tk.X, pady=(0, 5))
        
        # 作者
        author_label = tk.Label(info_line1, text=f"作者：{novel.get('author', '未知')}", 
                               font=self.fonts['body'],
                               bg='white',
                               fg=self.colors['text_primary'])
        author_label.pack(side=tk.LEFT)
        
        # 状态
        creation_status = novel.get('creation_status', '0')
        # 修复状态显示：creation_status为'0'表示完结，'1'表示连载中
        status_text = "完结" if creation_status == '0' else "连载中"
        status_color = self.colors['success'] if creation_status == '0' else self.colors['warning']
        
        status_label = tk.Label(info_line1, text=f"  •  {status_text}", 
                               font=self.fonts['body'],
                               bg='white',
                               fg=status_color)
        status_label.pack(side=tk.LEFT)
        
        # 分类
        category_label = tk.Label(info_line1, text=f"  •  {novel.get('category', '未知')}", 
                                 font=self.fonts['body'],
                                 bg='white',
                                 fg=self.colors['text_secondary'])
        category_label.pack(side=tk.LEFT)
        
        # 统计信息行
        info_line2 = tk.Frame(info_frame, bg='white')
        info_line2.pack(fill=tk.X, pady=(0, 8))
        
        # 字数
        word_number = novel.get('word_number', '0')
        try:
            word_count = int(word_number)
            if word_count > 10000:
                word_display = f"{word_count // 10000}万字"
            else:
                word_display = f"{word_count}字"
        except (ValueError, TypeError):
            word_display = "未知"
        
        word_label = tk.Label(info_line2, text=f"📖 {word_display}", 
                             font=self.fonts['small'],
                             bg='white',
                             fg=self.colors['text_secondary'])
        word_label.pack(side=tk.LEFT, padx=(0, 15))
        
        # 评分
        score = novel.get('score', '0')
        try:
            if score and score != '0':
                score_display = f"⭐ {float(score):.1f}分"
            else:
                score_display = "⭐ 无评分"
        except (ValueError, TypeError):
            score_display = "⭐ 无评分"
        
        score_label = tk.Label(info_line2, text=score_display, 
                              font=self.fonts['small'],
                              bg='white',
                              fg=self.colors['text_secondary'])
        score_label.pack(side=tk.LEFT, padx=(0, 15))
        
        # 阅读人数
        read_cnt_text = novel.get('read_cnt_text', novel.get('sub_info', ''))
        if not read_cnt_text:
            read_count = novel.get('read_count', '0')
            try:
                count = int(read_count)
                if count > 10000:
                    read_cnt_text = f"{count // 10000}万人在读"
                else:
                    read_cnt_text = f"{count}人在读"
            except (ValueError, TypeError):
                read_cnt_text = "未知"
        
        read_label = tk.Label(info_line2, text=f"👥 {read_cnt_text}", 
                             font=self.fonts['small'],
                             bg='white',
                             fg=self.colors['text_secondary'])
        read_label.pack(side=tk.LEFT)
        
        # 简介
        description = novel.get('abstract', novel.get('book_abstract_v2', '无简介'))
        desc_label = tk.Label(info_frame, text=description, 
                             font=self.fonts['small'],
                             bg='white',
                             fg=self.colors['text_primary'],
                             wraplength=600,
                             justify=tk.LEFT,
                             anchor='nw')
        desc_label.pack(fill=tk.X, pady=(0, 10))
        
        # 操作按钮
        button_frame = tk.Frame(info_frame, bg='white')
        button_frame.pack(fill=tk.X)
        
        download_btn = tk.Button(button_frame, text="💾 下载此书", 
                                font=self.fonts['small'],
                                bg=self.colors['success'],
                                fg='white',
                                relief=tk.FLAT,
                                bd=0,
                                padx=15,
                                pady=5,
                                cursor='hand2',
                                command=lambda n=novel: self.download_selected_novel(n))
        download_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # 标签信息（如果有）
        tags = novel.get('tags', '')
        if tags:
            tags_frame = tk.Frame(info_frame, bg='white')
            tags_frame.pack(fill=tk.X, pady=(5, 0))
            
            tag_list = tags.split(',')[:5]  # 最多显示5个标签
            for tag in tag_list:
                tag_label = tk.Label(tags_frame, text=tag.strip(), 
                                   font=self.fonts['small'],
                                   bg=self.colors['border'],
                                   fg=self.colors['text_secondary'],
                                   padx=8, pady=2)
                tag_label.pack(side=tk.LEFT, padx=(0, 5))
    
    def _update_cover_label(self, label, image, book_id):
        """更新封面标签"""
        try:
            if label.winfo_exists():  # 检查标签是否还存在
                # 将图片存储到全局缓存中，防止被垃圾回收
                self.cover_images[book_id] = image
                # 更新标签显示图片
                label.config(image=image, bg='white', width=120, height=160)
                # 设置标签的图片引用
                label.image = image
        except Exception:
            # 静默处理错误
            pass
    
    def download_selected_novel(self, novel):
        """下载选中的小说"""
        book_id = novel.get('book_id', '')
        if book_id:
            # 切换到下载标签页并填入ID
            self.notebook.select(self.download_frame)  # 选择下载标签页
            self.book_id_entry.delete(0, tk.END)
            self.book_id_entry.insert(0, book_id)
            messagebox.showinfo("成功", f"已选择《{novel.get('book_name', '未知')}》用于下载")
        else:
            messagebox.showerror("错误", "无法获取书籍ID")
    
    def download_image(self, url, size=(120, 160)):
        """下载并调整图片大小"""
        if not url:
            return None
            
        try:
            from PIL import Image, ImageTk
        except ImportError:
            return None
            
        try:
            # 基于测试结果优化URL尝试顺序
            original_url = url
            urls_to_try = []
            
            if '.heic' in url.lower():
                # HEIC格式成功率最高，优先使用原始HEIC URL
                urls_to_try.append(original_url)
                
                # 只在HEIC失败时尝试JPG（JPG偶尔会成功）
                jpg_url = url.replace('.heic', '.jpg').replace('.HEIC', '.jpg')
                urls_to_try.append(jpg_url)
                
                # 跳过WebP和PNG，因为测试显示它们都返回403
            else:
                # 对于非HEIC格式，直接使用原URL
                urls_to_try.append(original_url)
            
            print(f"尝试加载封面: {len(urls_to_try)}个优化URL")
            
            # 添加请求头，模拟浏览器访问
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Referer': 'https://www.tomatonovel.com/',
                'Accept': 'image/webp,image/apng,image/jpeg,image/png,image/*,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Cache-Control': 'no-cache'
            }
            
            for i, test_url in enumerate(urls_to_try):
                try:
                    # 静默处理，不输出调试信息
                    
                    response = requests.get(test_url, headers=headers, timeout=15)
                    response.raise_for_status()
                    
                    # 检查响应内容类型
                    content_type = response.headers.get('content-type', '')
                    content_length = len(response.content)
                    
                    if not content_type.startswith('image/') or content_length < 1000:
                        continue
                    
                    # 尝试打开图片
                    try:
                        image = Image.open(BytesIO(response.content))
                        
                        # 转换图片模式
                        if image.mode == 'RGBA':
                            # 创建白色背景
                            background = Image.new('RGB', image.size, (255, 255, 255))
                            background.paste(image, mask=image.split()[-1])
                            image = background
                        elif image.mode not in ('RGB', 'L'):
                            image = image.convert('RGB')
                        
                        # 调整大小
                        image = image.resize(size, Image.Resampling.LANCZOS)
                        photo = ImageTk.PhotoImage(image)
                        
                        return photo
                        
                    except Exception:
                        continue
                        
                except requests.RequestException as req_error:
                    pass  # 静默处理
                    continue
                except Exception as e:
                    pass  # 静默处理
                    continue
            
            return None
                
        except Exception:
            return None
    
    def show_book_details(self):
        """显示书籍详情"""
        selection = self.results_tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请选择一本小说")
            return
        
        # 获取选中的索引
        item = selection[0]
        index = self.results_tree.index(item)
        
        if index < len(self.search_results_data):
            selected_novel = self.search_results_data[index]
            book_id = selected_novel.get('book_id', '')
            # 如果用户确认，开始下载
            if confirmed:
                self.log("开始下载更新...")
                threading.Thread(target=self.updater.download_update, args=(update_info,), daemon=True).start()
                threading.Thread(target=self.start_external_update, daemon=True).start()
    
    def _show_book_details_thread(self, book_id):
        """显示书籍详情线程函数"""
        try:
            # 确保API已初始化
            if self.api is None:
                self.initialize_api()
                
            info_result = self.api.get_novel_info(book_id)
            details_result = self.api.get_book_details(book_id)
            
            self.root.after(0, self._create_details_window, info_result, details_result, book_id)
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("错误", f"获取书籍详情失败: {str(e)}"))
    
    def _create_details_window(self, info_result, details_result, book_id):
        """创建详情窗口"""
        details_window = tk.Toplevel(self.root)
        details_window.title(f"书籍详情")
        details_window.geometry("1000x800")
        details_window.configure(bg=self.colors['background'])
        
        # 创建主框架
        main_frame = tk.Frame(details_window, bg=self.colors['background'])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 获取选中的小说信息
        selection = self.results_tree.selection()
        selected_novel = None
        if selection:
            index = self.results_tree.index(selection[0])
            if index < len(self.search_results_data):
                selected_novel = self.search_results_data[index]
        
        if not selected_novel:
            tk.Label(main_frame, text="未找到选中的小说信息", 
                    font=self.fonts['body'], bg=self.colors['background']).pack()
            return
        
        # 创建上部分：封面和基本信息
        top_frame = tk.Frame(main_frame, bg=self.colors['background'])
        top_frame.pack(fill=tk.X, pady=(0, 20))
        
        # 左侧：封面图片
        cover_frame = tk.Frame(top_frame, bg=self.colors['surface'], relief=tk.RAISED, bd=1)
        cover_frame.pack(side=tk.LEFT, padx=(0, 20))
        
        # 下载并显示封面
        cover_url = selected_novel.get('thumb_url') or selected_novel.get('expand_thumb_url')
        if cover_url:
            # 在新线程中下载图片
            def load_cover():
                cover_image = self.download_image(cover_url, (200, 280))
                if cover_image:
                    details_window.after(0, lambda: self._display_cover(cover_frame, cover_image, selected_novel.get('book_name', '未知')))
                else:
                    details_window.after(0, lambda: self._display_no_cover(cover_frame))
            
            threading.Thread(target=load_cover, daemon=True).start()
            # 先显示加载中
            loading_label = tk.Label(cover_frame, text="封面加载中...", 
                                   font=self.fonts['small'],
                                   bg=self.colors['surface'],
                                   fg=self.colors['text_secondary'],
                                   width=25, height=15)
            loading_label.pack(padx=10, pady=10)
        else:
            self._display_no_cover(cover_frame)
        
        # 右侧：基本信息
        info_frame = tk.Frame(top_frame, bg=self.colors['surface'], relief=tk.RAISED, bd=1)
        info_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 标题
        title_label = tk.Label(info_frame, text=selected_novel.get('book_name', '未知'), 
                              font=self.fonts['title'],
                              bg=self.colors['surface'],
                              fg=self.colors['text_primary'])
        title_label.pack(pady=(15, 10))
        
        # 基本信息
        creation_status = selected_novel.get('creation_status', '0')
        status_text = "完结" if creation_status == '0' else "连载中"
        
        word_number = selected_novel.get('word_number', '0')
        try:
            word_count = int(word_number)
            if word_count > 10000:
                word_display = f"{word_count // 10000}万字"
            else:
                word_display = f"{word_count}字"
        except (ValueError, TypeError):
            word_display = "未知"
        
        score = selected_novel.get('score', '0')
        try:
            if score and score != '0':
                score_display = f"{float(score):.1f}分"
            else:
                score_display = "无评分"
        except (ValueError, TypeError):
            score_display = "无评分"
        
        info_text = f"""作者：{selected_novel.get('author', '未知')}
状态：{status_text}
分类：{selected_novel.get('category', '未知')}
字数：{word_display}
评分：{score_display}
阅读：{selected_novel.get('read_cnt_text', selected_novel.get('sub_info', '未知'))}
来源：{selected_novel.get('source', '未知')}
标签：{selected_novel.get('tags', '无')}"""
        
        info_label = tk.Label(info_frame, text=info_text, 
                            font=self.fonts['body'],
                            bg=self.colors['surface'],
                            fg=self.colors['text_primary'],
                            justify=tk.LEFT, anchor='nw')
        info_label.pack(fill=tk.X, padx=15, pady=10)
        
        # 下部分：完整简介
        desc_frame = tk.LabelFrame(main_frame, text="📖 作品简介", 
                                  font=self.fonts['subtitle'],
                                  bg=self.colors['surface'],
                                  fg=self.colors['text_primary'])
        desc_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建文本框显示完整简介
        text_frame = tk.Frame(desc_frame, bg=self.colors['surface'])
        text_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        desc_text = tk.Text(text_frame, 
                          font=self.fonts['body'],
                          bg='white',
                          fg=self.colors['text_primary'],
                          wrap=tk.WORD,
                          relief=tk.FLAT,
                          bd=1)
        
        desc_scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=desc_text.yview)
        desc_text.configure(yscrollcommand=desc_scrollbar.set)
        
        # 插入完整简介
        full_description = selected_novel.get('abstract', selected_novel.get('book_abstract_v2', '暂无简介'))
        desc_text.insert(tk.END, full_description)
        desc_text.config(state=tk.DISABLED)
        
        desc_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        desc_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 底部按钮
        button_frame = tk.Frame(main_frame, bg=self.colors['background'])
        button_frame.pack(fill=tk.X, pady=(20, 0))
        
        download_btn = self.create_button(button_frame, 
                                         "💾 下载此书", 
                                         lambda: self._download_from_details(selected_novel, details_window),
                                         self.colors['success'])
        download_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        close_btn = self.create_button(button_frame, 
                                      "❌ 关闭", 
                                      details_window.destroy,
                                      self.colors['error'])
        close_btn.pack(side=tk.RIGHT)
    
    def _display_cover(self, parent, image, book_name):
        """显示封面图片"""
        # 清空父容器
        for widget in parent.winfo_children():
            widget.destroy()
        
        cover_label = tk.Label(parent, image=image, bg=self.colors['surface'])
        cover_label.image = image  # 保持引用
        cover_label.pack(padx=10, pady=10)
        
        name_label = tk.Label(parent, text=book_name, 
                             font=self.fonts['small'],
                             bg=self.colors['surface'],
                             fg=self.colors['text_primary'],
                             wraplength=180)
        name_label.pack(pady=(0, 10))
    
    def _display_no_cover(self, parent):
        """显示无封面占位符"""
        # 清空父容器
        for widget in parent.winfo_children():
            widget.destroy()
        
        no_cover_label = tk.Label(parent, text="📚\n暂无封面", 
                                 font=self.fonts['body'],
                                 bg=self.colors['surface'],
                                 fg=self.colors['text_secondary'],
                                 width=25, height=15)
        no_cover_label.pack(padx=10, pady=10)
    
    def _download_from_details(self, novel, window):
        """从详情窗口下载书籍"""
        book_id = novel.get('book_id', '')
        if book_id:
            # 切换到下载标签页并填入ID
            self.notebook.select(self.download_frame)  # 选择下载标签页
            self.book_id_entry.delete(0, tk.END)
            self.book_id_entry.insert(0, book_id)
            window.destroy()
            messagebox.showinfo("成功", f"已选择《{novel.get('book_name', '未知')}》用于下载")
        else:
            messagebox.showerror("错误", "无法获取书籍ID")
        
        # 显示标签和关键词
        if selected_novel and (selected_novel.get('tags') or selected_novel.get('role')):
            tag_card = self.create_detail_card(scrollable_frame, "🏷️ 标签信息")
            
            tag_info = ""
            if selected_novel.get('role'):
                tag_info += f"主要角色：{selected_novel.get('role')}\n"
            if selected_novel.get('tags'):
                tag_info += f"标签：{selected_novel.get('tags')}"
            
            if tag_info:
                tag_label = tk.Label(tag_card, text=tag_info,
                                   font=self.fonts['body'],
                                   bg=self.colors['surface'],
                                   fg=self.colors['text_primary'],
                                   justify=tk.LEFT, anchor='nw')
                tag_label.pack(fill=tk.X, pady=5)
        
        # 绑定鼠标滚轮事件
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
    
    def create_detail_card(self, parent, title):
        """创建详情卡片"""
        card_frame = tk.Frame(parent, bg=self.colors['surface'], relief=tk.RAISED, bd=1)
        card_frame.pack(fill=tk.X, pady=(0, 15), padx=10)
        
        # 标题
        title_label = tk.Label(card_frame, text=title,
                              font=self.fonts['subtitle'],
                              bg=self.colors['surface'],
                              fg=self.colors['primary'])
        title_label.pack(anchor='w', padx=15, pady=(10, 5))
        
        return card_frame
    
    def _format_word_count(self, word_count):
        """格式化字数显示"""
        if isinstance(word_count, str):
            try:
                word_count = int(word_count)
            except ValueError:
                return "未知"
        
        if word_count > 10000:
            return f"{word_count // 10000}万字"
        else:
            return f"{word_count}字"
    
    def _format_score(self, score):
        """格式化评分显示"""
        if isinstance(score, str) and score.isdigit():
            return f"{float(score)/10:.1f}分"
        else:
            return "无评分"
        
    def browse_save_path(self):
        """选择保存路径"""
        path = filedialog.askdirectory()
        if path:
            self.save_path_entry.delete(0, tk.END)
            self.save_path_entry.insert(0, path)
            # 自动保存配置
            self.save_config()
    
    def log(self, message):
        """记录日志"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, time.strftime("[%H:%M:%S] ", time.localtime()) + message + "\n")
        self.log_text.config(state=tk.DISABLED)
        self.log_text.see(tk.END)
    
    def format_time(self, seconds):
        """格式化时间显示"""
        if seconds < 60:
            return f"{int(seconds)}秒"
        elif seconds < 3600:
            return f"{int(seconds // 60)}分{int(seconds % 60)}秒"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            secs = seconds % 60
            return f"{int(hours)}时{int(minutes)}分{int(secs)}秒"
    
    def progress_callback(self, progress, message):
        """进度回调"""
        try:
            # 更新进度条
            if progress >= 0:
                self.progress['value'] = progress

                # 计算剩余时间
                if self.start_time and progress > 0 and progress < 100:
                    elapsed_time = time.time() - self.start_time
                    estimated_total_time = elapsed_time * 100 / progress
                    remaining_time = estimated_total_time - elapsed_time
                    remaining_str = self.format_time(remaining_time)
                    progress_info_text = f"进度: {progress}% (预计剩余时间: {remaining_str})"
                elif progress == 100:
                    elapsed_time = time.time() - self.start_time
                    elapsed_str = self.format_time(elapsed_time)
                    progress_info_text = f"下载完成! 总耗时: {elapsed_str}"
                else:
                    progress_info_text = f"进度: {progress}%" if progress >= 0 else "处理中..."

                self.progress_info.config(text=progress_info_text)

            # 更新状态标签
            self.status_label.config(text=message)

            # 检测下载完成消息，自动清理chapter.json文件
            if progress == 100 or ("下载完成" in message and "失败" not in message):
                self._auto_cleanup_chapter_json()

            # 只有在非递归情况下才记录日志，避免递归调用
            if not hasattr(self, '_in_progress_callback'):
                self._in_progress_callback = True
                try:
                    # 只记录重要消息，避免过多日志
                    if progress < 0 or progress in [0, 25, 50, 75, 100] or "完成" in message or "失败" in message:
                        self.log(f"{message}")
                finally:
                    delattr(self, '_in_progress_callback')

            self.root.update_idletasks()  # 使用update_idletasks避免递归

        except Exception as e:
            # 静默处理异常，避免递归错误
            pass
    
    def _auto_cleanup_chapter_json(self):
        """自动清理chapter.json文件"""
        try:
            save_path = self.save_path_entry.get().strip()
            if not save_path or not os.path.isdir(save_path):
                return
                
            chapter_json_path = os.path.join(save_path, "chapter.json")
            if os.path.exists(chapter_json_path):
                os.remove(chapter_json_path)
                self.log("已自动清理下载状态文件: chapter.json")
        except Exception as e:
            # 静默处理，避免影响用户体验
            pass

    def clear_settings(self):
        """清理设置文件"""
        try:
            # 清理GUI配置文件
            config_files = ['gui_config.json', 'downloader_state.json', 'config.json']
            cleared_files = []
            
            for config_file in config_files:
                if os.path.exists(config_file):
                    os.remove(config_file)
                    cleared_files.append(config_file)
            
            if cleared_files:
                messagebox.showinfo("清理成功", f"已清理文件: {', '.join(cleared_files)}")
                self.log(f"清理设置文件: {', '.join(cleared_files)}")
            else:
                messagebox.showinfo("清理结果", "没有找到需要清理的设置文件")
                
        except Exception as e:
            messagebox.showerror("错误", f"清理设置文件失败: {str(e)}")
            self.log(f"清理设置文件失败: {str(e)}")
    
    def start_download(self):
        """开始下载 - 先显示章节选择对话框"""
        if self.is_downloading:
            return
            
        book_id = self.book_id_entry.get().strip()
        save_path = self.save_path_entry.get().strip()
        file_format = self.format_var.get()
        
        if not book_id:
            messagebox.showerror("错误", "请输入书籍ID")
            return
            
        if not os.path.isdir(save_path):
            messagebox.showerror("错误", "保存路径无效")
            return
        
        # 先获取章节列表，然后显示选择对话框
        self.log("正在获取章节列表...")
        threading.Thread(target=self._fetch_chapters_and_show_dialog,
                        args=(book_id, save_path, file_format),
                        daemon=True).start()
    
    def _fetch_chapters_and_show_dialog(self, book_id, save_path, file_format):
        """获取章节列表并显示选择对话框"""
        try:
            # api_manager 已经在文件开头导入
            
            # 获取章节列表
            chapters = api_manager.get_chapter_list(book_id)
            
            if not chapters:
                self.root.after(0, lambda: messagebox.showerror("错误", "无法获取章节列表"))
                return
            
            # 在主线程中显示对话框
            self.root.after(0, lambda: self._show_chapter_selection_dialog(
                book_id, save_path, file_format, chapters))
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("错误", f"获取章节列表失败: {str(e)}"))
    
    def _show_chapter_selection_dialog(self, book_id, save_path, file_format, chapters):
        """显示章节选择对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("选择下载章节")
        dialog.geometry("800x600")
        dialog.configure(bg=self.colors['background'])
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 居中显示
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (800 // 2)
        y = (dialog.winfo_screenheight() // 2) - (600 // 2)
        dialog.geometry(f"800x600+{x}+{y}")
        
        # 主容器
        main_frame = tk.Frame(dialog, bg=self.colors['background'])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 标题
        title_label = tk.Label(main_frame,
                              text=f"共找到 {len(chapters)} 个章节，请选择下载范围",
                              font=self.fonts['subtitle'],
                              bg=self.colors['background'],
                              fg=self.colors['text_primary'])
        title_label.pack(pady=(0, 10))
        
        # 快速选择按钮区
        quick_frame = tk.Frame(main_frame, bg=self.colors['background'])
        quick_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(quick_frame, text="快速选择:",
                font=self.fonts['body'],
                bg=self.colors['background'],
                fg=self.colors['text_primary']).pack(side=tk.LEFT, padx=(0, 10))
        
        self.create_button(quick_frame, "全选",
                          lambda: self._select_all_chapters(chapter_listbox, chapters),
                          self.colors['primary']).pack(side=tk.LEFT, padx=5)
        
        self.create_button(quick_frame, "前100章",
                          lambda: self._select_range_chapters(chapter_listbox, 0, min(100, len(chapters))),
                          self.colors['secondary']).pack(side=tk.LEFT, padx=5)
        
        self.create_button(quick_frame, "最新100章",
                          lambda: self._select_range_chapters(chapter_listbox, max(0, len(chapters)-100), len(chapters)),
                          self.colors['secondary']).pack(side=tk.LEFT, padx=5)
        
        # 章节范围输入
        range_frame = tk.Frame(main_frame, bg=self.colors['background'])
        range_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(range_frame, text="自定义范围:",
                font=self.fonts['body'],
                bg=self.colors['background'],
                fg=self.colors['text_primary']).pack(side=tk.LEFT, padx=(0, 10))
        
        tk.Label(range_frame, text="从第",
                font=self.fonts['body'],
                bg=self.colors['background'],
                fg=self.colors['text_primary']).pack(side=tk.LEFT)
        
        start_entry = tk.Entry(range_frame, font=self.fonts['body'], width=8)
        start_entry.pack(side=tk.LEFT, padx=5)
        start_entry.insert(0, "1")
        
        tk.Label(range_frame, text="章到第",
                font=self.fonts['body'],
                bg=self.colors['background'],
                fg=self.colors['text_primary']).pack(side=tk.LEFT)
        
        end_entry = tk.Entry(range_frame, font=self.fonts['body'], width=8)
        end_entry.pack(side=tk.LEFT, padx=5)
        end_entry.insert(0, str(len(chapters)))
        
        def apply_custom_range():
            try:
                start = int(start_entry.get()) - 1
                end = int(end_entry.get())
                if start < 0 or end > len(chapters) or start >= end:
                    messagebox.showwarning("无效范围", "请输入有效的章节范围")
                    return
                self._select_range_chapters(chapter_listbox, start, end)
            except ValueError:
                messagebox.showwarning("输入错误", "请输入有效的数字")
        
        self.create_button(range_frame, "应用", apply_custom_range,
                          self.colors['success']).pack(side=tk.LEFT, padx=5)
        
        # 章节列表区域
        list_frame = tk.Frame(main_frame, bg=self.colors['surface'])
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        chapter_listbox = tk.Listbox(list_frame,
                                     font=self.fonts['body'],
                                     bg='white',
                                     fg=self.colors['text_primary'],
                                     selectmode=tk.EXTENDED,
                                     yscrollcommand=scrollbar.set)
        chapter_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=chapter_listbox.yview)
        
        # 填充章节列表
        for idx, chapter in enumerate(chapters):
            chapter_title = chapter.get("chapter_name", f"第{idx+1}章")
            chapter_listbox.insert(tk.END, f"{idx+1}. {chapter_title}")
        
        # 默认全选
        chapter_listbox.select_set(0, tk.END)
        
        # 选择信息
        selection_info = tk.Label(main_frame,
                                 text=f"已选择: {len(chapters)} 章",
                                 font=self.fonts['body'],
                                 bg=self.colors['background'],
                                 fg=self.colors['text_secondary'])
        selection_info.pack(pady=(0, 10))
        
        def update_selection_info(event=None):
            selected_count = len(chapter_listbox.curselection())
            selection_info.config(text=f"已选择: {selected_count} 章")
        
        chapter_listbox.bind('<<ListboxSelect>>', update_selection_info)
        
        # 按钮区
        button_frame = tk.Frame(main_frame, bg=self.colors['background'])
        button_frame.pack(fill=tk.X)
        
        def start_selected_download():
            selected_indices = chapter_listbox.curselection()
            if not selected_indices:
                messagebox.showwarning("未选择章节", "请至少选择一个章节")
                return
            
            start_chapter = min(selected_indices)
            end_chapter = max(selected_indices)
            
            is_continuous = len(selected_indices) == (end_chapter - start_chapter + 1)
            
            if not is_continuous:
                result = messagebox.askyesno("非连续选择",
                                           f"您选择了非连续的章节，系统将下载第{start_chapter+1}章到第{end_chapter+1}章之间的所有章节。\n\n是否继续？")
                if not result:
                    return
            
            dialog.destroy()
            self._start_download_with_range(book_id, save_path, file_format,
                                           start_chapter, end_chapter)
        
        self.create_button(button_frame, "🚀 开始下载选中章节",
                          start_selected_download,
                          self.colors['success']).pack(side=tk.LEFT, padx=(0, 10))
        
        self.create_button(button_frame, "❌ 取消",
                          dialog.destroy,
                          self.colors['error']).pack(side=tk.RIGHT)
    
    def _select_all_chapters(self, listbox, chapters):
        """全选章节"""
        listbox.select_set(0, tk.END)
    
    def _select_range_chapters(self, listbox, start, end):
        """选择指定范围的章节"""
        listbox.selection_clear(0, tk.END)
        for i in range(start, end):
            listbox.select_set(i)
    
    def _start_download_with_range(self, book_id, save_path, file_format, start_chapter, end_chapter):
        """开始下载指定范围的章节"""
        self.is_downloading = True
        self.start_time = time.time()
        self.download_btn.config(state=tk.DISABLED, bg=self.colors['text_secondary'], text="下载中...")
        self.progress['value'] = 0
        self.progress_info.config(text="准备开始下载...")
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.log(f"开始下载书籍: {book_id} (第{start_chapter+1}章 - 第{end_chapter+1}章)")
        
        threading.Thread(target=self._download_thread,
                        args=(book_id, save_path, file_format, start_chapter, end_chapter),
                        daemon=True).start()
    
    def _download_thread(self, book_id, save_path, file_format, start_chapter=None, end_chapter=None):
        """下载线程函数 - 支持章节范围选择"""
        try:
            # 检查API连接
            # api_manager 已经在文件开头导入
            if not api_manager.test_connection():
                # API连接失败
                self.root.after(0, lambda: messagebox.showerror(
                    "API未验证",
                    "API接口列表为空，可能启动时验证失败。\n\n"
                    "请重新启动程序并完成验证码验证，\n"
                    "或在设置中手动进行验证。"
                ))
                return
                
            # 确保API实例存在
            if self.api is None:
                self.log("API实例不存在，正在重新创建...")
                self.initialize_api()

            # 设置进度回调
            def gui_progress_callback(progress, message):
                """GUI进度回调，将下载器的回调转发到GUI"""
                if progress >= 0:  # 只有有效进度才更新
                    self.root.after(0, lambda p=progress, m=message: self.progress_callback(p, m))
                else:
                    # 只更新消息，不改变进度
                    self.root.after(0, lambda m=message: self.log(m))
            
            # 设置API的进度回调
            self.api.set_progress_callback(gui_progress_callback)
            
            self.root.after(0, lambda: self.progress_callback(5, "初始化增强型下载器（集成enhanced_downloader.py功能）..."))
            
            # 获取书籍信息
            info_result = self.api.get_novel_info(book_id)
            if not info_result or not info_result.get('isSuccess'):
                error_msg = info_result.get('errorMsg', '未知错误') if info_result else '无响应'
                raise Exception(f"获取书籍信息失败: {error_msg}")
            
            # 检查API返回的消息
            api_data = info_result.get('data', {})
            api_message = api_data.get('message', '')
            if api_message == 'BOOK_REMOVE':
                raise Exception(f"书籍 {book_id} 已被移除或不存在")
            
            # 获取书名
            raw_data = api_data.get('data', {})
            if isinstance(raw_data, dict) and raw_data:
                book_data = raw_data
                book_name = book_data.get('book_name', book_id)
                author_name = book_data.get('author', '未知作者')
                description = book_data.get('abstract', '无简介')
            else:
                raise Exception(f"无法获取书籍 {book_id} 的详细信息")
            
            self.root.after(0, lambda: self.progress_callback(10, f"准备使用enhanced_downloader.py的高速下载《{book_name}》..."))
            
            # 整本下载 - 直接使用增强型下载器（移除章节下载模式）
            self.root.after(0, lambda: self.progress_callback(15, f"启动enhanced_downloader.py高速下载模式..."))
            
            # 直接使用增强型下载器的run_download方法，传递章节范围参数
            downloader = self.api.enhanced_downloader
            downloader.set_progress_callback(gui_progress_callback)

            # 在线程中运行下载，传递GUI验证回调和章节范围
            downloader.run_download(book_id, save_path, file_format, start_chapter, end_chapter)
            
            # 检查是否取消
            if downloader.is_cancelled:
                self.root.after(0, lambda: self.progress_callback(0, "下载已取消"))
                return
            
            # 完成消息由下载器内部处理，不需要在这里重复发送
                
        except Exception as e:
            error_msg = str(e)
            self.root.after(0, lambda: self.check_and_handle_api_error(f"下载失败: {error_msg}"))
            self.root.after(0, lambda: self.log(f"下载失败: {error_msg}"))
        finally:
            # 清理进度回调
            if hasattr(self.api, 'set_progress_callback'):
                self.api.set_progress_callback(None)
            self.root.after(0, self._download_finished)
    

    
    def _filter_watermark(self, text):
        """过滤章节内容中的水印"""
        if not text:
            return text
        
        # 常见的水印模式
        watermarks = [
            '兔兔',
            '【兔兔】',
            '（兔兔）',
            'tutuxka',
            'TUTUXKA',
            '兔小说',
            '兔读',
            '兔书',
            # 可以根据需要添加更多水印模式
        ]
        
        # 过滤末尾的水印
        for watermark in watermarks:
            if text.strip().endswith(watermark):
                text = text.strip()[:-len(watermark)].strip()
        
        # 过滤行末的水印
        lines = text.split('\n')
        filtered_lines = []
        for line in lines:
            for watermark in watermarks:
                if line.strip().endswith(watermark):
                    line = line.strip()[:-len(watermark)].strip()
            if line.strip():  # 只保留非空行
                filtered_lines.append(line)
        
        return '\n'.join(filtered_lines)
    
    def _save_as_txt(self, filepath, book_data, chapters):
        """保存为TXT格式，包含详细信息"""
        content = self._generate_book_info(book_data)
        content += "\n" + "="*50 + "\n\n"
        
        for item in chapters:
            title = item.get('title', '')
            text_content = item.get('content', '')
            # 过滤章节末尾的"兔兔"水印
            text_content = self._filter_watermark(text_content)
            content += f"\n\n{title}\n\n{text_content}"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def _save_as_epub(self, filepath, book_data, chapters, subtitle=""):
        """保存为EPUB格式，包含封面和详细信息"""
        # 创建EPUB书籍
        book = epub.EpubBook()
        
        # 设置书籍元数据
        book_title = book_data.get('book_name', '未知书名')
        if subtitle:
            book_title += f" - {subtitle}"
        
        book.set_identifier(book_data.get('book_id', 'unknown'))
        book.set_title(book_title)
        book.set_language('zh-cn')
        book.add_author(book_data.get('author', '未知作者'))
        
        # 添加描述
        description = book_data.get('abstract', book_data.get('book_abstract_v2', ''))
        if description:
            book.add_metadata('DC', 'description', description)
        
        # 添加封面
        cover_added = False
        cover_urls = [
            book_data.get('thumb_url'),
            book_data.get('expand_thumb_url'),
            book_data.get('audio_thumb_url_hd')
        ]
        
        for cover_url in cover_urls:
            if cover_url and self._add_epub_cover(book, cover_url):
                cover_added = True
                break
        
        # 创建样式
        style = '''
        body { font-family: "Microsoft YaHei", "SimSun", serif; line-height: 1.8; margin: 20px; }
        h1 { text-align: center; color: #333; border-bottom: 2px solid #ccc; padding-bottom: 10px; }
        h2 { color: #555; margin-top: 30px; }
        .book-info { background-color: #f9f9f9; padding: 15px; border-left: 4px solid #4CAF50; margin: 20px 0; }
        .chapter { margin-top: 30px; }
        .chapter-title { font-size: 1.2em; font-weight: bold; color: #2c3e50; border-bottom: 1px solid #eee; padding-bottom: 5px; }
        '''
        
        nav_css = epub.EpubItem(uid="nav", file_name="style/nav.css", media_type="text/css", content=style)
        book.add_item(nav_css)
        
        # 创建书籍信息页面
        info_content = f"""
        <html>
        <head>
            <title>书籍信息</title>
            <link rel="stylesheet" type="text/css" href="style/nav.css"/>
        </head>
        <body>
            <h1>书籍信息</h1>
            <div class="book-info">
                {self._generate_book_info_html(book_data)}
            </div>
        </body>
        </html>
        """
        
        info_chapter = epub.EpubHtml(title='书籍信息', file_name='info.xhtml', lang='zh-cn')
        info_chapter.content = info_content
        book.add_item(info_chapter)
        
        # 添加章节
        spine = ['nav', info_chapter]
        toc = [epub.Link("info.xhtml", "书籍信息", "info")]
        
        for i, item in enumerate(chapters):
            title = item.get('title', f'第{i+1}章')
            text_content = item.get('content', '')
            # 过滤章节末尾的"兔兔"水印
            text_content = self._filter_watermark(text_content)
            
            # 将换行转换为HTML段落
            paragraphs = text_content.split('\n')
            html_content = ""
            for para in paragraphs:
                para = para.strip()
                if para:
                    html_content += f"<p>{para}</p>\n"
            
            chapter_content = f"""
            <html>
            <head>
                <title>{title}</title>
                <link rel="stylesheet" type="text/css" href="style/nav.css"/>
            </head>
            <body>
                <div class="chapter">
                    <h2 class="chapter-title">{title}</h2>
                    {html_content}
                </div>
            </body>
            </html>
            """
            
            chapter = epub.EpubHtml(title=title, file_name=f'chapter_{i+1}.xhtml', lang='zh-cn')
            chapter.content = chapter_content
            book.add_item(chapter)
            spine.append(chapter)
            toc.append(epub.Link(f"chapter_{i+1}.xhtml", title, f"chapter_{i+1}"))
        
        # 设置目录和spine
        book.toc = toc
        book.spine = spine
        
        # 添加导航文件
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        
        # 保存EPUB文件
        epub.write_epub(filepath, book, {})
    
    def _add_epub_cover(self, book, cover_url):
        """为EPUB添加封面"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://www.tomatonovel.com/',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8'
            }
            
            response = requests.get(cover_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # 检查是否是图片
            content_type = response.headers.get('content-type', '')
            if not content_type.startswith('image/'):
                return False
            
            # 确定文件扩展名
            if 'jpeg' in content_type or 'jpg' in content_type:
                ext = 'jpg'
            elif 'png' in content_type:
                ext = 'png'
            elif 'webp' in content_type:
                ext = 'webp'
            elif 'heic' in content_type:
                # EPUB不支持heic格式，转换为jpg
                ext = 'jpg'
                print("检测到HEIC格式封面，转换为JPG格式")
            else:
                ext = 'jpg'  # 默认
            
            # 添加封面
            book.set_cover(f"cover.{ext}", response.content)
            print(f"成功添加封面 (格式: {ext})")
            return True
            
        except Exception as e:
            print(f"添加封面失败: {e}")
            return False
    
    def _generate_book_info(self, book_data):
        """生成书籍信息文本"""
        info_lines = []
        info_lines.append(f"书名：{book_data.get('book_name', '未知')}")
        info_lines.append(f"作者：{book_data.get('author', '未知')}")
        
        # 状态
        creation_status = book_data.get('creation_status', '0')
        status_text = "完结" if creation_status == '0' else "连载中"
        info_lines.append(f"状态：{status_text}")
        
        info_lines.append(f"分类：{book_data.get('category', '未知')}")
        
        # 字数
        word_number = book_data.get('word_number', '0')
        try:
            word_count = int(word_number)
            if word_count > 10000:
                word_display = f"{word_count // 10000}万字"
            else:
                word_display = f"{word_count}字"
        except (ValueError, TypeError):
            word_display = "未知"
        info_lines.append(f"字数：{word_display}")
        
        # 评分
        score = book_data.get('score', '0')
        try:
            if score and score != '0':
                score_display = f"{float(score):.1f}分"
            else:
                score_display = "无评分"
        except (ValueError, TypeError):
            score_display = "无评分"
        info_lines.append(f"评分：{score_display}")
        
        info_lines.append(f"来源：{book_data.get('source', '未知')}")
        
        tags = book_data.get('tags', '')
        if tags:
            info_lines.append(f"标签：{tags}")
        
        # 简介
        description = book_data.get('abstract', book_data.get('book_abstract_v2', ''))
        if description:
            info_lines.append(f"\n简介：\n{description}")
        
        return '\n'.join(info_lines)
    
    def _generate_book_info_html(self, book_data):
        """生成书籍信息HTML"""
        html_lines = []
        html_lines.append(f"<p><strong>书名：</strong>{book_data.get('book_name', '未知')}</p>")
        html_lines.append(f"<p><strong>作者：</strong>{book_data.get('author', '未知')}</p>")
        
        # 状态
        creation_status = book_data.get('creation_status', '0')
        status_text = "完结" if creation_status == '0' else "连载中"
        html_lines.append(f"<p><strong>状态：</strong>{status_text}</p>")
        
        html_lines.append(f"<p><strong>分类：</strong>{book_data.get('category', '未知')}</p>")
        
        # 字数
        word_number = book_data.get('word_number', '0')
        try:
            word_count = int(word_number)
            if word_count > 10000:
                word_display = f"{word_count // 10000}万字"
            else:
                word_display = f"{word_count}字"
        except (ValueError, TypeError):
            word_display = "未知"
        html_lines.append(f"<p><strong>字数：</strong>{word_display}</p>")
        
        # 评分
        score = book_data.get('score', '0')
        try:
            if score and score != '0':
                score_display = f"{float(score):.1f}分"
            else:
                score_display = "无评分"
        except (ValueError, TypeError):
            score_display = "无评分"
        html_lines.append(f"<p><strong>评分：</strong>{score_display}</p>")
        
        html_lines.append(f"<p><strong>来源：</strong>{book_data.get('source', '未知')}</p>")
        
        tags = book_data.get('tags', '')
        if tags:
            html_lines.append(f"<p><strong>标签：</strong>{tags}</p>")
        
        # 简介
        description = book_data.get('abstract', book_data.get('book_abstract_v2', ''))
        if description:
            # 将换行转换为HTML段落
            desc_paragraphs = description.split('\n')
            desc_html = ""
            for para in desc_paragraphs:
                para = para.strip()
                if para:
                    desc_html += f"<p>{para}</p>"
            html_lines.append(f"<div><strong>简介：</strong><br/>{desc_html}</div>")
        
        return '\n'.join(html_lines)

    def _download_finished(self):
        """下载完成后的清理工作"""
        self.is_downloading = False
        self.download_btn.config(state=tk.NORMAL, bg=self.colors['success'], text="🚀 开始下载")
        # 确保下载完成后清理状态文件
        self._auto_cleanup_chapter_json()
    
    def initialize_api(self):
        """初始化API，只在需要时调用"""
        if self.api is None:
            # 创建GUI验证码处理回调
            def gui_verification_callback(captcha_url):
                """在GUI中处理验证码输入"""
                result = {'token': None}
                event = threading.Event()

                def show_dialog_and_wait():
                    dialog = self._create_captcha_dialog_for_api(captcha_url, result, event)
                    if dialog:
                        # 使对话框成为模态窗口并等待
                        dialog.grab_set()
                        self.root.wait_window(dialog)

                if threading.current_thread() is threading.main_thread():
                    show_dialog_and_wait()
                else:
                    self.root.after(0, show_dialog_and_wait)
                    event.wait(timeout=300)

                return result.get('token')

            # 创建API实例，传入GUI回调
            self.api = NovelDownloaderAPI(gui_verification_callback)

            # 注意：不在这里调用预加载，避免重复触发验证

        return self.api

    def _test_api_connection_at_startup(self):
        """在启动时测试API连接"""
        try:
            self.log("程序启动完成，正在测试API连接...")
            
            # 测试API连接
            # api_manager 已经在文件开头导入
            if api_manager.test_connection():
                self.log("API连接正常，可以开始使用")
                self.update_verification_status("API连接正常 ✓", self.colors['success'])
            else:
                self.log("API连接失败，请检查网络")
                self.update_verification_status("API连接失败", self.colors['error'])
                messagebox.showwarning(
                    "API连接失败",
                    "无法连接到API服务器。\n\n"
                    "请检查网络连接，稍后可在设置中重新测试。"
                )
            
        except Exception as e:
            self.log(f"API测试失败: {str(e)}")
            messagebox.showerror("启动错误", f"API测试失败: {str(e)}")
    
    def _show_api_selection_dialog(self, saved_api_data):
        """显示API选择对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("API选择")
        dialog.geometry("500x400")
        dialog.configure(bg=self.colors['background'])
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 居中显示
        dialog.geometry("+%d+%d" % (
            self.root.winfo_rootx() + 50,
            self.root.winfo_rooty() + 50
        ))
        
        result = {'choice': None}
        
        # 标题
        title_label = tk.Label(dialog, 
                             text="发现保存的API配置",
                             font=self.fonts['subtitle'],
                             bg=self.colors['background'],
                             fg=self.colors['text_primary'])
        title_label.pack(pady=20)
        
        # API信息显示
        update_info = api_manager.get_last_update_info()
        if update_info:
            update_time = api_manager.format_update_time(update_info['last_update'])
            api_count = update_info['api_count']
            batch_enabled = update_info['batch_enabled']
            
            info_text = f"""发现保存的API配置：

API数量: {api_count}个
批量下载: {'启用' if batch_enabled else '禁用'}
更新时间: {update_time}

请选择操作："""
        else:
            info_text = """发现保存的API配置：

请选择操作："""
        
        info_label = tk.Label(dialog, 
                            text=info_text,
                            font=self.fonts['body'],
                            bg=self.colors['background'],
                            fg=self.colors['text_secondary'],
                            justify=tk.LEFT)
        info_label.pack(pady=20)
        
        # 按钮框架
        button_frame = tk.Frame(dialog, bg=self.colors['background'])
        button_frame.pack(pady=30)
        
        def use_saved():
            result['choice'] = 'use_saved'
            dialog.destroy()
        
        def update_api():
            result['choice'] = 'update'
            dialog.destroy()
        
        def clear_and_update():
            result['choice'] = 'clear_and_update'
            dialog.destroy()
        
        # 使用保存的API
        use_btn = self.create_button(button_frame, "使用保存的API", use_saved, self.colors['success'])
        use_btn.pack(pady=5)
        
        # 更新API
        update_btn = self.create_button(button_frame, "更新API", update_api, self.colors['primary'])
        update_btn.pack(pady=5)
        
        # 清除并更新
        clear_btn = self.create_button(button_frame, "清除并重新获取", clear_and_update, self.colors['warning'])
        clear_btn.pack(pady=5)
        
        # 等待用户选择
        dialog.wait_window()
        
        # 处理用户选择
        if result['choice'] == 'use_saved':
            self.log("用户选择使用保存的API")
            api_manager.apply_saved_apis(saved_api_data)
            self.log("已应用保存的API配置")
        elif result['choice'] == 'update':
            self.log("用户选择更新API")
            self._perform_network_verification()
        elif result['choice'] == 'clear_and_update':
            self.log("用户选择清除并重新获取API")
            api_manager.clear_saved_apis()
            self._perform_network_verification()
        else:
            self.log("用户取消选择，使用保存的API")
            api_manager.apply_saved_apis(saved_api_data)
    
    def _perform_network_verification(self):
        """执行网络验证"""
        try:
            # 先检查网络连接
            self.log("检查网络连接...")
            try:
                import requests
                test_response = requests.get("https://www.baidu.com", timeout=5)
                if test_response.status_code == 200:
                    self.log("网络连接正常")
                else:
                    self.log(f"网络连接异常，状态码: {test_response.status_code}")
            except Exception as net_e:
                self.log(f"网络连接测试失败: {str(net_e)}")
                messagebox.showerror(
                    "网络连接问题",
                    f"网络连接测试失败: {str(net_e)}\n\n"
                    "请检查网络连接后重启程序。"
                )
                return
            
            # 显示欢迎信息和验证要求
            welcome_msg = (
                "欢迎使用番茄小说下载器！\n\n"
                "为了正常使用下载功能，需要先进行人机验证。\n"
                "验证成功后，API接口将保存到内存中供下载使用。\n\n"
                "点击确定开始验证"
            )
            
            # 提供跳过选项
            custom_dialog = tk.Toplevel(self.root)
            custom_dialog.title("验证码验证")
            custom_dialog.geometry("400x300")
            custom_dialog.configure(bg=self.colors['background'])
            custom_dialog.resizable(False, False)
            custom_dialog.transient(self.root)
            custom_dialog.grab_set()
            
            # 居中显示
            custom_dialog.geometry("+%d+%d" % (
                self.root.winfo_rootx() + 50,
                self.root.winfo_rooty() + 50
            ))
            
            result_var = tk.StringVar(value="")
            
            # 标题
            title_label = tk.Label(custom_dialog, 
                                 text="欢迎使用番茄小说下载器！",
                                 font=self.fonts['subtitle'],
                                 bg=self.colors['background'],
                                 fg=self.colors['text_primary'])
            title_label.pack(pady=20)
            
            # 说明文本
            info_text = tk.Text(custom_dialog, 
                              height=6, width=45,
                              bg=self.colors['surface'],
                              fg=self.colors['text_primary'],
                              font=self.fonts['body'],
                              wrap=tk.WORD,
                              relief=tk.FLAT)
            info_text.pack(pady=10, padx=20)
            
            info_content = (
                "为了正常使用下载功能，建议先进行人机验证。\n"
                "验证成功后，API接口将保存到内存中供下载使用。\n\n"
                "如果当前网络环境无法连接验证服务器，\n"
                "您也可以选择跳过验证，稍后在设置中手动验证。"
            )
            info_text.insert(tk.END, info_content)
            info_text.config(state=tk.DISABLED)
            
            # 按钮框架
            button_frame = tk.Frame(custom_dialog, bg=self.colors['background'])
            button_frame.pack(pady=20)
            
            def verify_now():
                result_var.set("verify")
                custom_dialog.destroy()
                
            def skip_verification():
                result_var.set("skip")
                custom_dialog.destroy()
                
            def cancel_startup():
                result_var.set("cancel")
                custom_dialog.destroy()
            
            verify_btn = self.create_button(button_frame, "🔒 开始验证", verify_now, self.colors['primary'])
            verify_btn.pack(side=tk.LEFT, padx=5)
            
            skip_btn = self.create_button(button_frame, "⏭️ 跳过验证", skip_verification, self.colors['warning'])
            skip_btn.pack(side=tk.LEFT, padx=5)
            
            cancel_btn = self.create_button(button_frame, "❌ 取消", cancel_startup, self.colors['error'])
            cancel_btn.pack(side=tk.LEFT, padx=5)
            
            # 等待用户选择
            self.root.wait_window(custom_dialog)
            user_choice = result_var.get()
            
            if user_choice == "cancel":
                self.log("用户取消启动")
                self.root.quit()
                return
            elif user_choice == "skip":
                self.log("用户跳过验证")
                messagebox.showinfo(
                    "验证已跳过",
                    "已跳过启动验证。\n\n"
                    "如需下载功能，请稍后在设置中手动进行验证。"
                )
                return
            # user_choice == "verify" 继续验证流程
            
            # 确保API实例已创建
            if self.api is None:
                self.log("创建API实例...")
                if self.initialize_api() is None:
                    self.log("API实例创建失败")
                    messagebox.showerror(
                        "初始化失败",
                        "无法创建API实例，请检查网络连接后重启程序。"
                    )
                    return

            # 强制进行API初始化（这会触发验证码验证）
            self.log("开始验证码验证流程...")
            self.log("正在连接服务器获取验证码挑战...")
            
            if self.api.initialize_api():
                self.log("API连接成功！")
                import novel_downloader
                messagebox.showinfo(
                    "连接成功", 
                    f"验证码验证成功！\n已获取{api_count}个API接口并保存到内存。\n现在可以正常使用下载功能了。"
                )
            else:
                self.log("验证码验证失败")
                messagebox.showerror(
                    "验证失败",
                    "验证码验证失败。可能的原因：\n"
                    "1. 网络连接不稳定\n"
                    "2. 服务器暂时无法访问\n"
                    "3. 验证码输入错误或过期\n\n"
                    "解决方案：\n"
                    "• 检查网络连接后重启程序重试\n"
                    "• 在设置中手动进行验证\n"
                    "• 联系开发者获取帮助"
                )

        except Exception as e:
            error_msg = str(e)
            self.log(f"启动验证异常: {error_msg}")
            messagebox.showerror(
                "启动验证错误",
                f"启动时验证过程出现异常：\n{error_msg}\n\n"
                "解决方案：\n"
                "• 重启程序重试\n"
                "• 在设置中手动进行验证\n"
                "• 检查网络连接和防火墙设置"
            )

    def _preload_api_at_startup(self):
        """保留原方法以保持兼容性（已弃用，现在使用_require_captcha_verification_at_startup）"""
        self._require_captcha_verification_at_startup()

    def _preload_api_in_background(self):
        """保留原方法以保持兼容性，现在调用新的方法"""
        self._preload_api_at_startup()
    
    def check_and_handle_api_error(self, error_message=""):
        """检查API错误并提供解决方案"""
        # 检查错误消息中是否包含验证相关的关键词
        verification_keywords = ['403', 'FORBIDDEN', 'UNAUTHORIZED', '401', '验证', 'captcha', 'verification']
        needs_verification = any(keyword.lower() in error_message.lower() for keyword in verification_keywords)
        
        if needs_verification:
            # 显示验证码解决方案对话框
            self.show_verification_solution_dialog(error_message)
        else:
            # 显示一般错误对话框
            messagebox.showerror("操作失败", f"操作失败：{error_message}\n\n如果持续出现问题，可能需要进行验证。")
    
    def show_verification_solution_dialog(self, error_message):
        """显示验证解决方案对话框"""
        result = messagebox.askyesno(
            "需要验证", 
            f"操作失败，可能需要进行人机验证：\n\n{error_message}\n\n是否现在进行验证？",
            icon='warning'
        )
        
        if result:
            self.show_captcha_dialog()
    
    def show_captcha_dialog(self):
        """显示验证码对话框"""
        try:
            from network import NetworkManager
            network_manager = NetworkManager()
            base_url = network_manager._get_server_base()
            captcha_url = f"{base_url}/api/get-captcha-challenge"
            
            # 获取验证码URL
            headers = network_manager.get_headers()
            headers.update({
                'X-Auth-Token': network_manager.config.AUTH_TOKEN,
                'Content-Type': 'application/json'
            })
            
            verification_url = None
            # 与网络层保持一致，关闭SSL验证，避免部分环境证书校验失败
            challenge_res = network_manager.make_request(captcha_url, headers=headers, timeout=10, verify=False)
            if challenge_res and challenge_res.status_code == 200:
                challenge_data = challenge_res.json()
                verification_url = challenge_data.get("challenge_url")
            
            # 回退到固定URL，确保总能显示输入框
            fixed_verification_url = "https://dlbkltos.s7123.xyz:5080/captcha"
            final_verification_url = verification_url or fixed_verification_url
            # 端口补全
            if "dlbkltos.s7123.xyz" in final_verification_url and ":5080" not in final_verification_url:
                final_verification_url = final_verification_url.replace("dlbkltos.s7123.xyz", "dlbkltos.s7123.xyz:5080")
            
            self._create_captcha_dialog(final_verification_url)
                
        except Exception as e:
            messagebox.showerror("验证码获取失败", f"获取验证码时出错: {str(e)}")
    
    def _create_captcha_dialog_for_api(self, verification_url, result_container, event):
        """为API初始化创建验证码对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("API初始化需要验证")
        dialog.geometry("600x450")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 居中显示
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (600 // 2)
        y = (dialog.winfo_screenheight() // 2) - (450 // 2)
        dialog.geometry(f"600x450+{x}+{y}")
        
        # 主容器
        main_frame = tk.Frame(dialog, bg=self.colors['background'])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 标题
        title_frame = tk.Frame(main_frame, bg=self.colors['primary'], height=60)
        title_frame.pack(fill=tk.X, pady=(0, 20))
        title_frame.pack_propagate(False)
        
        title_label = tk.Label(title_frame, 
                              text="🔒 API需要验证", 
                              font=self.fonts['subtitle'],
                              bg=self.colors['primary'],
                              fg='white')
        title_label.pack(expand=True)
        
        # 说明文本
        info_frame = tk.Frame(main_frame, bg=self.colors['surface'])
        info_frame.pack(fill=tk.X, pady=(0, 15))
        
        info_text = """获取下载服务器API列表需要进行人机验证。
请按照以下步骤操作：

1. 点击下方"打开验证页面"按钮
2. 在浏览器中完成验证
3. 复制获得的验证令牌
4. 粘贴到下方输入框并确认"""
        
        info_label = tk.Label(info_frame, 
                            text=info_text,
                            font=self.fonts['body'],
                            bg=self.colors['surface'],
                            fg=self.colors['text_primary'],
                            justify=tk.LEFT)
        info_label.pack(padx=15, pady=10)
        
        # 验证URL按钮
        url_frame = tk.Frame(main_frame, bg=self.colors['background'])
        url_frame.pack(fill=tk.X, pady=(0, 15))
        
        # 强制使用固定的验证页面URL
        fixed_verification_url = "https://dlbkltos.s7123.xyz:5080/captcha"
        open_btn = self.create_button(url_frame,
                                     "🌐 打开验证页面",
                                     lambda: webbrowser.open(fixed_verification_url),
                                     self.colors['primary'])
        open_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # 使用更健壮的复制链接（优先服务端返回，其次固定URL，并补全端口）
        def _resolved_verification_url():
            url = verification_url or fixed_verification_url
            if "dlbkltos.s7123.xyz" in url and ":5080" not in url:
                url = url.replace("dlbkltos.s7123.xyz", "dlbkltos.s7123.xyz:5080")
            return url
        copy_btn = self.create_button(url_frame,
                                     "📋 复制验证链接",
                                     lambda: self._copy_to_clipboard(_resolved_verification_url()),
                                     self.colors['secondary'])
        copy_btn.pack(side=tk.LEFT)
        
        # 验证令牌输入
        token_frame = tk.Frame(main_frame, bg=self.colors['background'])
        token_frame.pack(fill=tk.X, pady=(0, 20))
        
        tk.Label(token_frame,
                text="验证令牌:",
                font=self.fonts['body'],
                bg=self.colors['background'],
                fg=self.colors['text_primary']).pack(side=tk.LEFT)
        
        token_entry = tk.Entry(token_frame,
                             font=self.fonts['body'],
                             bg='white',
                             fg=self.colors['text_primary'],
                             relief=tk.SOLID,
                             bd=1,
                             highlightthickness=1,
                             highlightcolor=self.colors['primary'])
        token_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0))
        
        # 按钮框架
        button_frame = tk.Frame(main_frame, bg=self.colors['background'])
        button_frame.pack(fill=tk.X)
        
        def confirm_verification():
            token = token_entry.get().strip()
            if token:
                # 保存token到环境变量（仅本次会话有效）
                os.environ["TOMATO_VERIFICATION_TOKEN"] = token
                result_container['token'] = token
                if event:
                    event.set()
                # 在销毁对话框之前弹出提示，并以根窗口为父级，避免已销毁窗口作为父级导致的错误
                try:
                    messagebox.showinfo("验证成功", "🎉 验证令牌已保存，API初始化继续...", parent=self.root)
                except Exception:
                    messagebox.showinfo("验证成功", "🎉 验证令牌已保存，API初始化继续...")
                dialog.destroy()
            else:
                messagebox.showwarning("提示", "请输入验证令牌", parent=dialog)
        
        def skip_verification():
            result_container['token'] = '' # 空令牌表示跳过
            dialog.destroy()
            if event:
                event.set()
        
        confirm_btn = self.create_button(button_frame,
                                        "✅ 确认验证",
                                        confirm_verification,
                                        self.colors['success'])
        confirm_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        skip_btn = self.create_button(button_frame,
                                     "⏭️ 跳过验证",
                                     skip_verification,
                                     self.colors['warning'])
        skip_btn.pack(side=tk.LEFT)
        
        # 绑定回车键
        token_entry.bind('<Return>', lambda e: confirm_verification())
        
        # 窗口关闭处理
        def on_close():
            result_container['token'] = None # None表示取消
            dialog.destroy()
            if event:
                event.set()
        
        dialog.protocol("WM_DELETE_WINDOW", on_close)
        
        # 设置焦点
        token_entry.focus_set()
        
        return dialog
    
    def _create_captcha_dialog(self, verification_url):
        """创建验证码对话框（用于手动验证）"""
        dialog = tk.Toplevel(self.root)
        dialog.title("🔒 需要人机验证")
        dialog.geometry("500x400")
        dialog.configure(bg=self.colors['background'])
        dialog.resizable(False, False)
        
        # 设置对话框为模态
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 居中显示
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        # 标题
        title_frame = tk.Frame(dialog, bg=self.colors['primary'], height=60)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)
        
        title_label = tk.Label(title_frame, 
                              text="🔒 安全验证", 
                              font=self.fonts['title'],
                              bg=self.colors['primary'], 
                              fg='white')
        title_label.pack(expand=True)
        
        # 内容区域
        content_frame = tk.Frame(dialog, bg=self.colors['surface'])
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 说明文本
        info_text = """为了保护服务器安全，需要进行人机验证。

请按照以下步骤操作：
1. 点击下方"打开验证页面"按钮
2. 在浏览器中完成验证
3. 复制获得的验证令牌
4. 粘贴到下方输入框中
5. 点击"确认"按钮"""
        
        info_label = tk.Label(content_frame, 
                             text=info_text,
                             font=self.fonts['body'],
                             bg=self.colors['surface'],
                             fg=self.colors['text_primary'],
                             justify=tk.LEFT,
                             anchor='w')
        info_label.pack(fill=tk.X, pady=(0, 20))
        
        # 验证URL按钮
        url_frame = tk.Frame(content_frame, bg=self.colors['surface'])
        url_frame.pack(fill=tk.X, pady=(0, 20))
        
        # 强制使用固定的验证页面URL
        fixed_verification_url = "https://dlbkltos.s7123.xyz:5080/captcha"
        open_url_btn = self.create_button(url_frame, 
                                         "🌐 打开验证页面", 
                                         lambda: webbrowser.open(fixed_verification_url),
                                         self.colors['primary'])
        open_url_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # 复制URL按钮
        def _resolved_verification_url_manual():
            url = verification_url or fixed_verification_url
            if "dlbkltos.s7123.xyz" in url and ":5080" not in url:
                url = url.replace("dlbkltos.s7123.xyz", "dlbkltos.s7123.xyz:5080")
            return url
        copy_url_btn = self.create_button(url_frame, 
                                         "📋 复制验证链接", 
                                         lambda: self._copy_to_clipboard(_resolved_verification_url_manual()),
                                         self.colors['secondary'])
        copy_url_btn.pack(side=tk.LEFT)
        
        # 验证令牌输入
        token_frame = tk.Frame(content_frame, bg=self.colors['surface'])
        token_frame.pack(fill=tk.X, pady=(0, 20))
        
        token_label = tk.Label(token_frame, 
                              text="验证令牌:", 
                              font=self.fonts['body'],
                              bg=self.colors['surface'],
                              fg=self.colors['text_primary'])
        token_label.pack(anchor='w', pady=(0, 5))
        
        token_entry = tk.Entry(token_frame, 
                              font=self.fonts['body'],
                              bg='white',
                              fg=self.colors['text_primary'],
                              relief=tk.SOLID,
                              bd=1,
                              highlightthickness=2,
                              highlightcolor=self.colors['primary'])
        token_entry.pack(fill=tk.X, pady=(0, 10))
        token_entry.focus()
        
        # 按钮区域
        button_frame = tk.Frame(content_frame, bg=self.colors['surface'])
        button_frame.pack(fill=tk.X)
        
        def confirm_verification():
            token = token_entry.get().strip()
            if not token:
                messagebox.showwarning("输入错误", "请输入验证令牌")
                return

            # 保存验证令牌到环境变量（仅本次会话有效）
            os.environ["TOMATO_VERIFICATION_TOKEN"] = token

            # 测试验证令牌是否有效
            self._test_verification_token(token, dialog)
        
        def skip_verification():
            result = messagebox.askyesno("跳过验证", 
                                       "跳过验证可能导致部分功能无法使用。\n\n确定要跳过验证吗？")
            if result:
                dialog.destroy()
        
        confirm_btn = self.create_button(button_frame, 
                                        "✅ 确认验证", 
                                        confirm_verification,
                                        self.colors['success'])
        confirm_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        skip_btn = self.create_button(button_frame, 
                                     "⏭️ 跳过验证", 
                                     skip_verification,
                                     self.colors['warning'])
        skip_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        close_btn = self.create_button(button_frame, 
                                      "❌ 关闭", 
                                      dialog.destroy,
                                      self.colors['error'])
        close_btn.pack(side=tk.RIGHT)
        
        # 回车键确认
        token_entry.bind('<Return>', lambda e: confirm_verification())
    
    def _copy_to_clipboard(self, text):
        """复制文本到剪贴板"""
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            messagebox.showinfo("复制成功", "验证链接已复制到剪贴板")
        except Exception as e:
            messagebox.showerror("复制失败", f"无法复制到剪贴板: {str(e)}")
    
    def _test_verification_token(self, token, dialog):
        """测试验证令牌是否有效"""
        def test_in_background():
            try:
                from network import NetworkManager
                network_manager = NetworkManager()
                headers = network_manager.get_headers()
                headers.update({
                    'X-Auth-Token': network_manager.config.AUTH_TOKEN,
                    'X-Verification-Token': token,
                    'Content-Type': 'application/json'
                })
                
                # 测试API访问
                response = network_manager.make_request(network_manager.config.SERVER_URL, 
                                                      headers=headers, timeout=10, verify=False)
                
                if response and response.status_code == 200:
                    # 验证成功
                    self.root.after(0, lambda: self._verification_success(dialog))
                else:
                    # 验证失败
                    self.root.after(0, lambda: self._verification_failed())
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("验证错误", f"验证过程中出错: {str(e)}"))
        
        threading.Thread(target=test_in_background, daemon=True).start()
    
    def _verification_success(self, dialog):
        """验证成功"""
        messagebox.showinfo("验证成功", "🎉 人机验证通过！现在可以正常使用所有功能。")
        dialog.destroy()
        # 验证成功后初始化API
        self.initialize_api()
        # 更新状态显示
        self.update_verification_status("已验证 ✓", self.colors['success'])
    
    def _verification_failed(self):
        """验证失败"""
        messagebox.showerror("验证失败", "验证令牌无效或已过期，请重新获取。")
    
    def manual_verification(self):
        """手动进行验证并获取API接口"""
        try:
            # 提示用户即将进行验证
            result = messagebox.askquestion(
                "手动验证",
                "即将进行验证码验证并获取API接口。\n\n是否继续？",
                icon='question'
            )
            
            if result != 'yes':
                return
                
            # 确保API实例存在
            if self.api is None:
                self.initialize_api()
                
            if self.api is None:
                messagebox.showerror("错误", "无法创建API实例")
                return
            
            # 测试API连接
            # api_manager 和 novel_downloader 已经在文件开头导入
            
            # 进行连接测试
            self.update_verification_status("正在测试连接...", self.colors['warning'])
            
            if api_manager.test_connection():
                # 连接成功，更新状态
                self.update_verification_status("API连接正常 ✓", self.colors['success'])
                messagebox.showinfo(
                    "连接成功",
                    "API连接测试成功！\n现在可以正常使用下载功能了。"
                )
            else:
                self.update_verification_status("验证失败", self.colors['error'])
                messagebox.showerror("验证失败", "验证码验证失败，请重试。")
                
        except Exception as e:
            error_msg = str(e)
            self.update_verification_status("验证异常", self.colors['error'])
            messagebox.showerror("验证异常", f"验证过程出现异常：{error_msg}")
    
    def clear_verification_token(self):
        """清除验证令牌和API接口"""
        try:
            result = messagebox.askquestion(
                "清除验证",
                "确定要清除验证令牌和API接口吗？\n清除后需要重新验证才能下载。",
                icon='warning'
            )
            
            if result != 'yes':
                return
                
            # 清除环境变量中的验证令牌
            if "TOMATO_VERIFICATION_TOKEN" in os.environ:
                del os.environ["TOMATO_VERIFICATION_TOKEN"]
                
            # 更新状态显示
            self.update_verification_status("已清除设置", self.colors['text_secondary'])
            messagebox.showinfo("清除成功", "设置已清除")
        except Exception as e:
            messagebox.showerror("清除失败", f"清除失败: {str(e)}")
    
    def update_verification_status(self, status_text, color=None):
        """更新验证状态显示"""
        if hasattr(self, 'verification_status_label'):
            if color is None:
                color = self.colors['text_secondary']
            self.verification_status_label.config(text=f"状态: {status_text}", fg=color)
    
    def show_api_management(self):
        """显示API管理对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("API管理")
        dialog.geometry("600x500")
        dialog.configure(bg=self.colors['background'])
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 居中显示
        dialog.geometry("+%d+%d" % (
            self.root.winfo_rootx() + 50,
            self.root.winfo_rooty() + 50
        ))
        
        # 标题
        title_label = tk.Label(dialog, 
                             text="API管理",
                             font=self.fonts['subtitle'],
                             bg=self.colors['background'],
                             fg=self.colors['text_primary'])
        title_label.pack(pady=20)
        
        # 当前API状态
        # api_manager 已经在文件开头导入
        api_connected = api_manager.test_connection()
        
        status_text = f"""当前API状态:
连接状态: {'正常' if api_connected else '失败'}
API服务器: {CONFIG.get('api_base_url', '未配置')}"""
        
        status_label = tk.Label(dialog, 
                              text=status_text,
                              font=self.fonts['body'],
                              bg=self.colors['background'],
                              fg=self.colors['text_secondary'],
                              justify=tk.LEFT)
        status_label.pack(pady=10)
        
        # 保存的API信息
        saved_api_data = api_manager.load_apis()
        if saved_api_data:
            update_info = api_manager.get_last_update_info()
            if update_info:
                update_time = api_manager.format_update_time(update_info['last_update'])
                saved_api_count = update_info['api_count']
                saved_batch_enabled = update_info['batch_enabled']
                
                saved_text = f"""保存的API信息:
API数量: {saved_api_count}个
批量下载: {'启用' if saved_batch_enabled else '禁用'}
更新时间: {update_time}"""
            else:
                saved_text = "保存的API信息: 可用"
        else:
            saved_text = "保存的API信息: 无"
        
        saved_label = tk.Label(dialog, 
                             text=saved_text,
                             font=self.fonts['body'],
                             bg=self.colors['background'],
                             fg=self.colors['text_secondary'],
                             justify=tk.LEFT)
        saved_label.pack(pady=10)
        
        # 操作按钮框架
        button_frame = tk.Frame(dialog, bg=self.colors['background'])
        button_frame.pack(pady=30)
        
        def refresh_api():
            dialog.destroy()
            self._perform_network_verification()
        
        def apply_saved():
            if saved_api_data:
                api_manager.apply_saved_apis(saved_api_data)
                messagebox.showinfo("成功", "已应用保存的API配置")
                dialog.destroy()
            else:
                messagebox.showwarning("警告", "没有保存的API配置")
        
        def clear_saved():
            if messagebox.askyesno("确认", "确定要清除保存的API配置吗？"):
                api_manager.clear_saved_apis()
                messagebox.showinfo("成功", "已清除保存的API配置")
                dialog.destroy()
        
        def export_api():
            # 新API不支持导出功能
            messagebox.showinfo("提示", "当前使用的新API架构不需要导出配置")
        
        # 刷新API
        refresh_btn = self.create_button(button_frame, "🔄 刷新API", refresh_api, self.colors['primary'])
        refresh_btn.pack(pady=5)
        
        # 应用保存的API
        if saved_api_data:
            apply_btn = self.create_button(button_frame, "📥 应用保存的API", apply_saved, self.colors['success'])
            apply_btn.pack(pady=5)
        
        # 导出API
        export_btn = self.create_button(button_frame, "📤 导出API配置", export_api, self.colors['secondary'])
        export_btn.pack(pady=5)
        
        # 清除保存的API
        clear_btn = self.create_button(button_frame, "🗑️ 清除保存的API", clear_saved, self.colors['error'])
        clear_btn.pack(pady=5)
    


    def check_existing_verification(self):
        """检查API连接状态"""
        # 检查新API连接
        # api_manager 和 novel_downloader 已经在文件开头导入
        
        if api_manager.test_connection():
            self.update_verification_status("API连接正常 ✓", self.colors['success'])
        else:
            self.update_verification_status("API连接失败 (请检查网络)", self.colors['error'])

    def check_update_silent(self):
        """在后台静默检查更新"""
        if not getattr(self, 'official_build', False):
            return
        
        try:
            from updater import check_and_notify_update
        except ImportError:
            print("updater 模块不可用，跳过静默更新检查")
            return
        
        def notify(update_info):
            if not update_info:
                return
            self.root.after(0, lambda: self._prompt_update(update_info))
        try:
            check_and_notify_update(self.updater, notify)
        except Exception as e:
            print(f"静默检查更新失败: {e}")
    
    def check_update_force(self):
        """启动时的强制更新检查"""
        if not getattr(self, 'official_build', False):
            return
        
        def worker():
            try:
                # 检查是否有新版本
                update_info = self.updater.checker.get_update_info() if self.updater.checker.has_update(force=True) else None
                
                if update_info:
                    # 发现新版本，启动强制更新流程
                    self.root.after(0, lambda: self.updater._start_force_update(update_info))
                else:
                    # 没有新版本，正常启动
                    print("当前已是最新版本")
                    
            except Exception as e:
                # 检查更新失败，继续启动程序
                print(f"强制更新检查失败: {e}")
        
        threading.Thread(target=worker, daemon=True).start()

    def _prompt_update(self, update_info):
        """弹窗提示用户是否更新，并在确认后触发强制更新流程"""
        try:
            ver = update_info.get('version', '?') if isinstance(update_info, dict) else '?'
            body = update_info.get('body', '') if isinstance(update_info, dict) else ''
            msg = f"发现新版本 v{ver}，是否现在更新？"
            if body:
                msg += f"\n\n更新内容:\n{body[:800]}"
            if messagebox.askyesno("发现新版本", msg):
                if hasattr(self, 'updater') and self.updater:
                    # 保存配置
                    self.save_config()
                    # 开始更新流程（内部会自动退出程序）
                    self.updater._start_force_update(update_info)
        except Exception as e:
            self.log(f"提示更新失败: {e}")

    def check_update_now(self):
        """立即检查更新（手动触发）"""
        try:
            if not hasattr(self, 'updater') or self.updater is None:
                messagebox.showerror("更新系统未初始化", "更新系统未正确初始化，无法检查更新。")
                return
            # 强制检查最新版本
            if self.updater.checker.has_update(force=True):
                info = self.updater.checker.get_latest_release(force_check=True)
                if info:
                    self._prompt_update(info)
                else:
                    messagebox.showinfo("检查更新", "检测到新版本，但获取详细信息失败。")
            else:
                messagebox.showinfo("检查更新", "当前已是最新版本。")
        except Exception as e:
            messagebox.showerror("检查更新失败", f"{e}")

    def manual_check_update(self):
        """手动检查更新（新方法，统一入口）"""
        try:
            # 检查 updater 模块是否可用
            try:
                from updater import check_and_notify_update, is_official_release_build
            except ImportError as e:
                messagebox.showerror("功能不可用",
                    "更新功能需要安装依赖库：\n\n"
                    "pip install requests packaging\n\n"
                    f"详细错误：{str(e)}")
                return
            
            # 对于非官方构建，直接跳转到发布页
            if not getattr(self, 'official_build', False):
                releases_url = f"https://github.com/{__github_repo__}/releases/latest"
                try:
                    webbrowser.open(releases_url)
                    messagebox.showinfo("检查更新",
                                      "已在浏览器中打开GitHub发布页面。\n\n"
                                      "源码运行环境不支持自动更新，\n"
                                      "请手动下载最新版本。")
                except Exception as e:
                    messagebox.showerror("打开失败", f"无法打开浏览器：{str(e)}")
                return
            
            # 确保 updater 已初始化
            if not hasattr(self, 'updater') or self.updater is None:
                messagebox.showerror("更新系统未初始化", "更新系统未正确初始化，无法检查更新。")
                return
            
            # 显示检查中提示
            self.log("正在检查更新...")
            
            # 调用现有的更新检测方法（内部会弹窗询问，用户选择后才会继续）
            self.check_update_now()

        except Exception as e:
            self.log(f"启动外部更新程序失败: {e}")
            messagebox.showerror("更新失败", f"启动更新程序失败: {e}")

    def _create_external_update_script(self, update_info):
        """创建并启动外部更新脚本"""
        try:
            import json
            import subprocess

            # 解析脚本来源目录（优先 PyInstaller 解包目录）
            script_dir = os.path.dirname(os.path.abspath(__file__))
            bundle_dir = getattr(sys, '_MEIPASS', script_dir)
            external_src = os.path.join(bundle_dir, 'external_updater.py')
            if not os.path.exists(external_src):
                # 兼容性回退：尝试从可执行文件同目录查找
                try:
                    exe_dir = os.path.dirname(sys.executable)
                except Exception:
                    exe_dir = script_dir
                external_src = os.path.join(exe_dir, 'external_updater.py')

            # 最终校验
            if not os.path.exists(external_src):
                raise Exception(f"外部更新脚本不存在: {external_src}")

            # 将更新器脚本复制到系统临时目录运行，避免路径/权限问题
            temp_dir = tempfile.gettempdir()
            external_script = os.path.join(temp_dir, 'external_updater.py')
            try:
                shutil.copy2(external_src, external_script)
            except Exception as copy_err:
                raise Exception(f"复制更新脚本失败: {copy_err}")

            # 将更新信息序列化为 JSON 字符串
            update_info_json = json.dumps(update_info)

            # 创建批处理脚本或 shell 脚本启动外部更新程序
            if platform.system() == 'Windows':
                # Windows 批处理脚本
                escaped_json = update_info_json.replace('"', '\\"')
                batch_script = f"""@echo off
setlocal
cd /d "{temp_dir}"
set "PYCMD="
where python >nul 2>&1 && set "PYCMD=python"
if not defined PYCMD where py >nul 2>&1 && set "PYCMD=py -3"
if not defined PYCMD where python3 >nul 2>&1 && set "PYCMD=python3"
if not defined PYCMD (
  echo [Updater] 未找到可用的 Python 解释器
  exit /b 1
)
%PYCMD% "{external_script}" "{escaped_json}"
"""
                batch_file = os.path.join(tempfile.gettempdir(), 'start_update.bat')
                with open(batch_file, 'w', encoding='gbk') as f:
                    f.write(batch_script)

                # 启动批处理脚本（脱离控制台）
                subprocess.Popen(['cmd', '/c', batch_file],
                               creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW)
            else:
                # Unix shell 脚本
                shell_script = f"""#!/bin/bash
set -euo pipefail
cd "{temp_dir}"
python3 "{external_script}" '{update_info_json}'
"""
                shell_file = os.path.join(tempfile.gettempdir(), 'start_update.sh')
                with open(shell_file, 'w') as f:
                    f.write(shell_script)
                os.chmod(shell_file, 0o755)

                # 启动 shell 脚本
                subprocess.Popen([shell_file], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            self.log("外部更新脚本已启动")

        except Exception as e:
            self.log(f"创建外部更新脚本失败: {e}")
            raise

    def _cleanup_update_backups(self):
        """清理可能残留的更新备份文件"""
        try:
            # 获取当前可执行文件路径
            current_exe = sys.executable if getattr(sys, 'frozen', False) else sys.argv[0]
            backup_path = current_exe + '.backup'
            
            # 如果存在备份文件，删除它
            if os.path.exists(backup_path):
                try:
                    os.remove(backup_path)
                    print(f"已清理更新备份文件: {backup_path}")
                except Exception as e:
                    print(f"清理备份文件失败: {e}")
            
            # 清理临时目录中可能残留的备份
            temp_backup = os.path.join(tempfile.gettempdir(), 'updater_backup.exe')
            if os.path.exists(temp_backup):
                try:
                    os.remove(temp_backup)
                    print(f"已清理临时备份文件: {temp_backup}")
                except Exception as e:
                    print(f"清理临时备份文件失败: {e}")
                    
        except Exception as e:
            print(f"清理更新备份时出错: {e}")
    
    def _cleanup_old_update_logs(self):
        """清理超过7天的更新日志"""
        try:
            import time
            log_file = os.path.join(tempfile.gettempdir(), 'update.log')
            
            if os.path.exists(log_file):
                # 检查文件修改时间
                file_mtime = os.path.getmtime(log_file)
                current_time = time.time()
                days_old = (current_time - file_mtime) / (24 * 3600)
                
                # 如果日志超过7天，删除它
                if days_old > 7:
                    os.remove(log_file)
                    print(f"已清理过期的更新日志（{days_old:.1f}天前）")
        except Exception:
            # 忽略清理失败，不影响程序运行
            pass

    def _check_last_update_status(self):
        """检查上次更新的状态"""
        try:
            from updater import AutoUpdater
        except ImportError:
            print("updater 模块不可用，跳过更新状态检查")
            return
        
        try:
            status = AutoUpdater.check_update_status()

            if status['log_exists']:
                if status['update_success'] and status['last_update_time']:
                    print(f"上次更新成功完成于: {status['last_update_time']}")
                    # 清理成功的更新日志
                    AutoUpdater.clear_update_log()
                elif status['error_message']:
                    print(f"上次更新失败: {status['error_message']}")
                    # 可以在这里添加用户友好的提示
                    try:
                        # 在GUI完全加载后显示更新失败提示
                        self.root.after(2000, lambda: messagebox.showwarning(
                            "更新状态",
                            f"检测到上次更新可能失败: {status['error_message']}\n"
                            "建议重新运行更新或检查程序完整性。"
                        ))
                    except Exception:
                        pass
                else:
                    # 这通常是更新过程被中断或者是旧的日志文件
                    # 不显示误导性消息，只在调试模式下输出
                    if hasattr(sys, '_MEIPASS') and '-debug' in sys.argv[0].lower():
                        print("[DEBUG] 检测到未完成的更新日志")
                    # 清理旧的不完整日志，避免下次启动时再次提示
                    AutoUpdater.clear_update_log()
        except Exception as e:
            # 只在调试模式下显示错误
            if hasattr(sys, '_MEIPASS') and '-debug' in sys.argv[0].lower():
                print(f"[DEBUG] 检查更新状态失败: {e}")

    def start_external_update(self, update_file_path: str):
        """启动外部更新脚本"""
        try:
            # 确保 external_updater.py 存在
            external_updater_script = os.path.join(os.path.dirname(sys.executable), 'external_updater.py')
            if not os.path.exists(external_updater_script):
                # 如果在源码模式下，路径可能不同
                external_updater_script = os.path.join(os.path.dirname(__file__), 'external_updater.py')
            
            if not os.path.exists(external_updater_script):
                raise FileNotFoundError(f"找不到外部更新脚本: {external_updater_script}")
            
            self.log("外部更新脚本已准备就绪")
        except Exception as e:
            self.log(f"启动外部更新脚本失败: {e}")
            messagebox.showerror("更新失败", f"无法启动更新程序: {e}")

    def on_update_event(self, event: str, data: any):
        """处理所有更新相关的GUI事件"""
        if event == 'check_start':
            self.log("正在检查更新...")
        
        elif event == 'update_available':
            self.log(f"发现新版本: {data['version']}")
            ver = data.get('version', '?')
            body = data.get('body', '').strip()
            msg = f"发现新版本 v{ver}，是否现在更新？"
            if body:
                msg += f"\n\n更新内容:\n{body[:800]}" # 限制显示长度
            
            if messagebox.askyesno("发现新版本", msg):
                self.log("启动外部更新流程...")
                # 使用外部更新脚本执行下载与覆盖，避免在程序内操作
                self.updater._start_force_update(data)

        elif event == 'no_update':
            self.log("当前已是最新版本。")
            messagebox.showinfo("检查更新", "当前已是最新版本。")

        elif event == 'download_progress':
            current = data.get('current', 0)
            total = data.get('total', 1)
            percent = data.get('percent', 0)
            self.update_progress(percent, f"正在下载更新: {current//1024}KB / {total//1024}KB")

        elif event == 'download_complete':
            self.log("更新文件下载完成，准备安装...")
            self.update_progress(100, "下载完成，准备安装...")
            # 若为强制更新流程，内部会直接 install 并重启，此处不再触发外部安装
            try:
                if hasattr(self, 'updater') and getattr(self.updater, '_force_update_in_progress', False):
                    return
            except Exception:
                pass
            # 手动更新流程：启动外部更新脚本
            self.start_external_update(data)  # data 是下载的文件路径

        elif event == 'download_error':
            messagebox.showerror("更新失败", f"下载更新文件失败: {data}")
            self.update_progress(0, "更新失败")


if __name__ == '__main__':
    root = tk.Tk()
    app = ModernNovelDownloaderGUI(root)
    root.mainloop()