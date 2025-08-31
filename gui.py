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
from novel_downloader import NovelDownloaderAPI
from api_manager import api_manager
import novel_downloader
from ebooklib import epub
from updater import AutoUpdater, get_current_version, check_and_notify_update
from updater import is_official_release_build
from version import __version__, __github_repo__
import sys
import platform
import tempfile

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
        
        # 初始化版本信息和自动更新
        self.current_version = __version__
        self.updater = AutoUpdater(__github_repo__, self.current_version)
        self.updater.register_callback(self.on_update_event)
        self.official_build = is_official_release_build()

        # 清理可能残留的更新备份文件
        self._cleanup_update_backups()
        
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

        # 检查上次更新状态
        self._check_last_update_status()

        # 启动时自动检查更新（仅官方构建）
        if self.official_build and self.config.get('auto_check_update', True):
            self.root.after(1500, self.check_update_silent)

        # GUI初始化完成后获取API列表（延迟执行，确保GUI已完全显示）
        # 在GUI启动完成后要求验证码验证并获取API
        self.root.after(1000, self._require_captcha_verification_at_startup)
    
    def setup_fonts(self):
        """设置字体"""
        self.fonts = {
            'title': font.Font(family="微软雅黑", size=20, weight="bold"),
            'subtitle': font.Font(family="微软雅黑", size=14, weight="bold"),
            'body': font.Font(family="微软雅黑", size=10),
            'button': font.Font(family="微软雅黑", size=10, weight="bold"),
            'small': font.Font(family="微软雅黑", size=9)
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
        
        # 搜索标签页暂时隐藏（搜索接口失效）
        
        # 下载标签页
        self.download_frame = ttk.Frame(self.notebook, style='Card.TFrame')
        self.notebook.add(self.download_frame, text="💾 下载管理")
        self.create_download_tab()
        
        # 设置标签页
        self.settings_frame = ttk.Frame(self.notebook, style='Card.TFrame')
        self.notebook.add(self.settings_frame, text="⚙️ 设置")
        self.create_settings_tab()
    
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
    
    def create_download_tab(self):
        """创建下载标签页"""
        # 主容器
        main_container = tk.Frame(self.download_frame, bg=self.colors['surface'])
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
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
        
        # 验证设置卡片
        verification_card = self.create_card(main_container, "🔒 人机验证")
        
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
        word_number = str(book.get('word_number', '0'))
        if word_number == '0' or word_number == '' or (word_number.isdigit() and int(word_number) < 1000):
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
        
        # 左侧：封面图片
        cover_frame = tk.Frame(content_frame, bg='white')
        cover_frame.pack(side=tk.LEFT, padx=(0, 15))
        
        # 创建封面占位符
        cover_label = tk.Label(cover_frame, text="📚\n加载中...", 
                              font=self.fonts['small'],
                              bg='#f0f0f0',
                              fg=self.colors['text_secondary'],
                              relief=tk.SUNKEN, bd=1)
        cover_label.pack()
        
        # 异步加载封面
        cover_url = novel.get('thumb_url') or novel.get('expand_thumb_url') or novel.get('audio_thumb_url_hd')
        print(f"尝试加载封面: {novel.get('book_name', '未知')} - URL: {cover_url}")
        
        # 调试：显示所有可能的封面URL
        debug_urls = {
            'thumb_url': novel.get('thumb_url'),
            'expand_thumb_url': novel.get('expand_thumb_url'), 
            'audio_thumb_url_hd': novel.get('audio_thumb_url_hd')
        }
        print(f"所有封面URL选项: {debug_urls}")
        
        # 调试：检查PIL导入状态
        try:
            import PIL
            from PIL import Image, ImageTk
            print(f"PIL版本: {PIL.__version__}, Image模块: {Image}, ImageTk模块: {ImageTk}")
        except ImportError as e:
            print(f"PIL导入失败: {e}")
        
        if cover_url:
            def load_cover():
                try:
                    print(f"开始下载封面: {cover_url}")
                    cover_image = self.download_image(cover_url, (120, 160))
                    if cover_image:
                        print(f"封面下载成功: {novel.get('book_name', '未知')}")
                        book_id = novel.get('book_id', '')
                        self.root.after(0, lambda img=cover_image, bid=book_id: self._update_cover_label(cover_label, img, bid))
                    else:
                        print(f"主封面下载失败，尝试备用URL")
                        # 如果主封面加载失败，尝试其他封面URL
                        alt_urls = [
                            novel.get('expand_thumb_url'),
                            novel.get('audio_thumb_url_hd'),
                            novel.get('horiz_thumb_url')
                        ]
                        for alt_url in alt_urls:
                            if alt_url and alt_url != cover_url:
                                print(f"尝试备用封面URL: {alt_url}")
                                alt_image = self.download_image(alt_url, (120, 160))
                                if alt_image:
                                    print(f"备用封面下载成功")
                                    book_id = novel.get('book_id', '')
                                    self.root.after(0, lambda img=alt_image, bid=book_id: self._update_cover_label(cover_label, img, bid))
                                    break
                        else:
                            # 所有封面都加载失败，显示默认图标
                            print(f"所有封面URL都加载失败")
                            self.root.after(0, lambda: cover_label.config(text="📚\n暂无封面", bg='#f0f0f0'))
                except Exception as e:
                    print(f"封面加载异常: {e}")
                    self.root.after(0, lambda: cover_label.config(text="📚\n加载失败", bg='#f0f0f0'))
            
            threading.Thread(target=load_cover, daemon=True).start()
        else:
            print(f"没有找到封面URL: {novel.get('book_name', '未知')}")
            cover_label.config(text="📚\n暂无封面", bg='#f0f0f0')
        
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
                # 更新标签显示图片，移除文本
                label.config(image=image, text="", bg='white')
                # 设置标签的图片引用
                label.image = image
                print(f"封面更新成功，书籍ID: {book_id}")
            else:
                print("标签已被销毁，无法更新封面")
        except Exception as e:
            print(f"更新封面标签失败: {e}")
            if label.winfo_exists():
                label.config(text="📚\n显示失败", bg='#f0f0f0')
    
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
        print(f"=== 开始下载图片 ===")
        print(f"原始URL: {url}")
        print(f"目标尺寸: {size}")
        
        if not url:
            print("URL为空，返回None")
            return None
            
        # 调试：检查当前PIL模块状态
        try:
            from PIL import Image, ImageTk
            print(f"PIL模块检查通过")
        except ImportError as e:
            print(f"CRITICAL: PIL模块导入失败: {e}")
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
                    print(f"尝试URL {i+1}/{len(urls_to_try)}: {test_url[:100]}...")
                    
                    response = requests.get(test_url, headers=headers, timeout=15)
                    response.raise_for_status()
                    
                    # 检查响应内容类型
                    content_type = response.headers.get('content-type', '')
                    content_length = len(response.content)
                    
                    print(f"响应: {content_type}, 大小: {content_length} bytes")
                    
                    if not content_type.startswith('image/') or content_length < 1000:
                        print(f"无效的图片响应，跳过")
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
                        
                        print(f"封面加载成功！")
                        return photo
                        
                    except Exception as img_error:
                        print(f"PIL处理失败: {img_error}")
                        continue
                        
                except requests.RequestException as req_error:
                    print(f"请求失败: {req_error}")
                    continue
                except Exception as e:
                    print(f"URL处理失败: {e}")
                    continue
            
            print("所有URL都失败了")
            return None
                
        except Exception as e:
            print(f"图片下载完全失败: {e}")
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
            
            # 在新线程中获取详情
            threading.Thread(target=self._show_book_details_thread, args=(book_id,), daemon=True).start()
    
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
            config_files = ['gui_config.json', 'downloader_state.json']
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
        """开始下载"""
        if self.is_downloading:
            return
            
        book_id = self.book_id_entry.get().strip()
        save_path = self.save_path_entry.get().strip()
        file_format = self.format_var.get()
        mode = 'full'  # 固定为整本下载
        
        if not book_id:
            messagebox.showerror("错误", "请输入书籍ID")
            return
            
        if not os.path.isdir(save_path):
            messagebox.showerror("错误", "保存路径无效")
            return
            
        self.is_downloading = True
        self.start_time = time.time()
        self.download_btn.config(state=tk.DISABLED, bg=self.colors['text_secondary'], text="下载中...")
        self.progress['value'] = 0
        self.progress_info.config(text="准备开始下载...")
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.log(f"开始下载书籍: {book_id}")
        
        # 在新线程中执行下载
        threading.Thread(target=self._download_thread, args=(book_id, save_path, file_format), daemon=True).start()
    
    def _download_thread(self, book_id, save_path, file_format):
        """下载线程函数 - 完全集成enhanced_downloader.py的高速下载功能"""
        try:
            # 检查API接口是否已经获取
            if not novel_downloader.CONFIG["api_endpoints"]:
                # API列表为空，可能验证失败或未验证
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
            
            # 直接使用增强型下载器的run_download方法
            downloader = self.api.enhanced_downloader
            downloader.set_progress_callback(gui_progress_callback)

            # 在线程中运行下载，传递GUI验证回调
            downloader.run_download(book_id, save_path, file_format)
            
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
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Referer': 'https://www.tomatonovel.com/',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            
            # 使用更长的超时时间
            response = requests.get(cover_url, headers=headers, timeout=15, verify=False)
            response.raise_for_status()
            
            # 检查响应内容
            if not response.content or len(response.content) < 500:
                print(f"封面图片内容无效或过小: {len(response.content)} 字节")
                return False
            
            # 检查是否是图片
            content_type = response.headers.get('content-type', '')
            if not content_type.startswith('image/'):
                print(f"封面内容类型不是图片: {content_type}")
                return False
            
            # 检查图片格式（通过文件头验证）
            content = response.content
            if not (content.startswith(b'\xff\xd8') or  # JPEG
                    content.startswith(b'\x89PNG') or   # PNG
                    content.startswith(b'GIF8') or      # GIF
                    content.startswith(b'RIFF') or      # WEBP
                    content.startswith(b'BM') or        # BMP
                    content.startswith(b'\x00\x00\x01\x00')):  # ICO
                print(f"封面图片格式无效，内容头: {content[:8].hex()}")
                return False
            
            # 确定文件扩展名和MIME类型
            if 'jpeg' in content_type or 'jpg' in content_type:
                ext = 'jpg'
                mime_type = 'image/jpeg'
            elif 'png' in content_type:
                ext = 'png'
                mime_type = 'image/png'
            elif 'webp' in content_type:
                ext = 'webp'
                mime_type = 'image/webp'
            elif 'gif' in content_type:
                ext = 'gif'
                mime_type = 'image/gif'
            else:
                # 从URL推断格式
                if '.jpg' in cover_url or '.jpeg' in cover_url:
                    ext = 'jpg'
                    mime_type = 'image/jpeg'
                elif '.png' in cover_url:
                    ext = 'png'
                    mime_type = 'image/png'
                else:
                    ext = 'jpg'
                    mime_type = 'image/jpeg'
            
            # 创建封面图片项
            cover_filename = f'cover.{ext}'
            cover_item = epub.EpubItem(
                uid='cover-image',
                file_name=cover_filename,
                media_type=mime_type,
                content=content
            )
            book.add_item(cover_item)
            
            # 设置封面
            book.set_cover(cover_filename, content)
            
            # 添加封面元数据
            book.add_metadata('DC', 'relation', 'cover-image')
            book.add_metadata('OPF', 'cover', 'cover-image')
            
            print(f"成功添加封面 (格式: {ext}, 大小: {len(content)} 字节)")
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"下载封面失败: {e}")
            return False
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

    def _require_captcha_verification_at_startup(self):
        """在启动时要求验证码验证并获取API列表"""
        try:
            self.log("程序启动完成，准备进行API验证...")
            
            # 先检查是否有保存的API
            saved_api_data = api_manager.load_apis()
            if saved_api_data:
                # 有保存的API，询问用户选择
                self._show_api_selection_dialog(saved_api_data)
                return
            
            # 没有保存的API，进行网络验证
            self._perform_network_verification()
            
        except Exception as e:
            self.log(f"启动验证失败: {str(e)}")
            messagebox.showerror("启动错误", f"启动验证失败: {str(e)}")
    
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
                self.log("验证码验证成功！API接口已保存到内存")
                import novel_downloader
                api_count = len(novel_downloader.CONFIG["api_endpoints"])
                messagebox.showinfo(
                    "验证成功", 
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
            
            # 强制重新获取API接口
            import novel_downloader
            novel_downloader.CONFIG["api_endpoints"] = []  # 清空现有接口
            
            # 进行验证和API获取
            self.update_verification_status("正在验证...", self.colors['warning'])
            
            if self.api.initialize_api():
                # 验证成功，更新状态
                api_count = len(novel_downloader.CONFIG["api_endpoints"])
                self.update_verification_status(f"验证成功 ✓ (已获取{api_count}个API接口)", self.colors['success'])
                messagebox.showinfo(
                    "验证成功",
                    f"验证码验证成功！\n已获取{api_count}个API接口。\n现在可以正常使用下载功能了。"
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
                
            # 清除内存中的API接口
            import novel_downloader
            novel_downloader.CONFIG["api_endpoints"] = []

            # 更新状态显示
            self.update_verification_status("已清除验证令牌和API接口", self.colors['text_secondary'])
            messagebox.showinfo("清除成功", "验证令牌和API接口已清除\n需要重新验证才能下载")
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
        current_api_count = len(novel_downloader.CONFIG["api_endpoints"])
        batch_enabled = novel_downloader.CONFIG["batch_config"]["enabled"]
        
        status_text = f"""当前API状态:
API数量: {current_api_count}个
批量下载: {'启用' if batch_enabled else '禁用'}"""
        
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
            if current_api_count > 0:
                try:
                    import json
                    filename = f"api_backup_{int(time.time())}.json"
                    backup_data = {
                        "timestamp": time.time(),
                        "api_endpoints": novel_downloader.CONFIG["api_endpoints"],
                        "batch_config": novel_downloader.CONFIG["batch_config"]
                    }
                    with open(filename, 'w', encoding='utf-8') as f:
                        json.dump(backup_data, f, ensure_ascii=False, indent=2)
                    messagebox.showinfo("成功", f"API配置已导出到: {filename}")
                except Exception as e:
                    messagebox.showerror("错误", f"导出失败: {str(e)}")
            else:
                messagebox.showwarning("警告", "当前没有可导出的API配置")
        
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
        """检查已有的验证状态"""
        # 检查API接口是否已获取
        import novel_downloader
        if novel_downloader.CONFIG["api_endpoints"]:
            api_count = len(novel_downloader.CONFIG["api_endpoints"])
            self.update_verification_status(f"已验证 ✓ (已获取{api_count}个API接口)", self.colors['success'])
        else:
            verification_token = os.environ.get("TOMATO_VERIFICATION_TOKEN")
            if verification_token:
                self.update_verification_status("已保存验证令牌但API接口未获取", self.colors['warning'])
            else:
                self.update_verification_status("未验证 (需要进行验证码验证)", self.colors['text_secondary'])

    def check_update_silent(self):
        """在后台静默检查更新"""
        if not getattr(self, 'official_build', False):
            return
        def notify(update_info):
            if not update_info:
                return
            self.root.after(0, lambda: self._prompt_update(update_info))
        try:
            check_and_notify_update(self.updater, notify)
        except Exception as e:
            print(f"静默检查更新失败: {e}")

    def check_update_now(self):
        """手动检查更新（带提示）"""
        if not getattr(self, 'official_build', False):
            releases_url = f"https://github.com/{__github_repo__}/releases/latest"
            try:
                webbrowser.open(releases_url)
            except Exception:
                pass
            return
        def worker():
            try:
                update_info = self.updater.check_for_updates(force=True)
                if update_info:
                    self.root.after(0, lambda: self._prompt_update(update_info))
                else:
                    self.root.after(0, lambda: messagebox.showinfo("检查更新", "当前已是最新版本"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("检查更新失败", str(e)))
        threading.Thread(target=worker, daemon=True).start()

    def _prompt_update(self, update_info):
        """弹窗提示用户更新"""
        ver = update_info.get('version', '?')
        body = update_info.get('body', '').strip()
        msg = f"发现新版本 v{ver}，是否现在更新？"
        if body:
            msg += f"\n\n更新内容:\n{body[:800]}"  # 限制显示长度
        if messagebox.askyesno("发现新版本", msg):
            self._start_update(update_info)

    def _start_update(self, update_info):
        """开始更新（调用外部脚本处理所有更新操作）"""
        try:
            self.log(f"开始更新到版本: {update_info.get('version', 'unknown')}")

            # 创建外部更新脚本
            self._create_external_update_script(update_info)

            # 显示退出提示
            messagebox.showinfo("更新启动",
                              "更新程序已启动，应用程序将关闭。\n"
                              "更新完成后会自动重启程序。")

            # 立即退出应用程序
            self.root.quit()
            sys.exit(0)

        except Exception as e:
            self.log(f"启动外部更新程序失败: {e}")
            messagebox.showerror("更新失败", f"启动更新程序失败: {e}")

    def _create_external_update_script(self, update_info):
        """创建并启动外部更新脚本"""
        try:
            import json
            import subprocess

            # 获取外部脚本路径
            script_dir = os.path.dirname(os.path.abspath(__file__))
            external_script = os.path.join(script_dir, 'external_updater.py')

            # 检查外部脚本是否存在
            if not os.path.exists(external_script):
                raise Exception(f"外部更新脚本不存在: {external_script}")

            # 将更新信息序列化为 JSON 字符串
            update_info_json = json.dumps(update_info)

            # 创建批处理脚本或 shell 脚本启动外部更新程序
            if platform.system() == 'Windows':
                # Windows 批处理脚本
                escaped_json = update_info_json.replace('"', '\\"')
                batch_script = f"""@echo off
cd /d "{script_dir}"
python "{external_script}" "{escaped_json}"
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
cd "{script_dir}"
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
            import os
            import shutil
            import sys

            # 获取当前程序目录和可执行文件路径
            if getattr(sys, 'frozen', False):
                current_dir = os.path.dirname(sys.executable)
                exe_name = os.path.basename(sys.executable)
                backup_file = os.path.join(current_dir, f"{exe_name}.backup")
                backup_dir = os.path.join(current_dir, "backup")

                # 清理单个备份文件
                if os.path.exists(backup_file):
                    try:
                        os.remove(backup_file)
                        print("已清理残留的备份文件")
                    except Exception as e:
                        print(f"清理备份文件失败: {e}")

                # 清理备份目录
                if os.path.exists(backup_dir):
                    try:
                        # 检查目录是否为空
                        if not os.listdir(backup_dir):
                            os.rmdir(backup_dir)
                            print("已清理空的备份目录")
                        else:
                            # 如果目录不为空，尝试删除其中的备份文件
                            for file in os.listdir(backup_dir):
                                if file.endswith('.backup'):
                                    try:
                                        os.remove(os.path.join(backup_dir, file))
                                    except Exception:
                                        pass
                            # 再次检查是否为空
                            if not os.listdir(backup_dir):
                                os.rmdir(backup_dir)
                                print("已清理备份目录")
                    except Exception as e:
                        print(f"清理备份目录失败: {e}")

        except Exception as e:
            print(f"清理备份文件时出错: {e}")

    def _check_last_update_status(self):
        """检查上次更新的状态"""
        try:
            from updater import AutoUpdater
            status = AutoUpdater.check_update_status()

            if status['log_exists']:
                if status['update_success'] and status['last_update_time']:
                    print(f"上次更新成功完成于: {status['last_update_time']}")
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
                    print("检测到更新日志，但无法确定更新状态")
        except Exception as e:
            print(f"检查更新状态失败: {e}")

    def on_update_event(self, event, data):
        """处理更新过程中的事件回调（外部脚本处理，不需要GUI响应）"""
        # 由于更新现在由外部脚本完全处理，GUI不再需要响应这些事件
        # 只记录日志即可
        if event in ['download_error', 'install_error']:
            self.log(f"更新事件: {event} - {data}")

# 主程序入口
if __name__ == "__main__":
    root = tk.Tk()
    app = ModernNovelDownloaderGUI(root)
    root.mainloop()