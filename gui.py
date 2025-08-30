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
from tomato_novel_api import TomatoNovelAPI
from ebooklib import epub
from updater import AutoUpdater, get_current_version, check_and_notify_update
from version import __version__, __github_repo__

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
        
        # 配置文件路径
        self.config_file = "config.json"
        
        # 加载配置
        self.config = self.load_config()
        
        # 应用主题配置
        saved_theme = self.config.get('theme_color')
        if saved_theme and saved_theme != self.colors['primary']:
            self.colors['primary'] = saved_theme
            self.colors['primary_dark'] = saved_theme
        
        # 设置字体
        self.setup_fonts()
        
        # 创建样式
        self.setup_styles()
        
        # 创建UI
        self.create_widgets()
        
        # 检查已有的验证状态
        self.check_existing_verification()
        
        # 启动时自动检查更新
        if self.config.get('auto_check_update', True):
            self.root.after(1500, self.check_update_silent)
    
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
        
        # 下载模式
        mode_frame = tk.Frame(download_card, bg=self.colors['surface'])
        mode_frame.pack(fill=tk.X, pady=(0, 15))
        
        tk.Label(mode_frame, text="下载模式:", 
                font=self.fonts['body'], 
                bg=self.colors['surface'], 
                fg=self.colors['text_primary']).pack(side=tk.LEFT)
        
        self.mode_var = tk.StringVar(value=self.config.get('download_mode', 'full'))
        self.mode_var.trace('w', lambda *args: self.save_config())  # 监听变化并保存
        full_radio = tk.Radiobutton(mode_frame, text="整本下载", 
                                   variable=self.mode_var, value="full",
                                   font=self.fonts['body'], 
                                   bg=self.colors['surface'], 
                                   fg=self.colors['text_primary'],
                                   selectcolor=self.colors['surface'])
        full_radio.pack(side=tk.LEFT, padx=(20, 10))
        
        chapter_radio = tk.Radiobutton(mode_frame, text="章节下载", 
                                      variable=self.mode_var, value="chapter",
                                      font=self.fonts['body'], 
                                      bg=self.colors['surface'], 
                                      fg=self.colors['text_primary'],
                                      selectcolor=self.colors['surface'])
        chapter_radio.pack(side=tk.LEFT, padx=(0, 10))
        
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
        
        # 应用设置卡片
        app_card = self.create_card(main_container, "⚙️ 应用设置")
        
        # 主题设置
        theme_frame = tk.Frame(app_card, bg=self.colors['surface'])
        theme_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(theme_frame, text="主题色彩:", 
                font=self.fonts['body'], 
                bg=self.colors['surface'], 
                fg=self.colors['text_primary']).pack(side=tk.LEFT)
        
        # 主题选择按钮
        theme_buttons_frame = tk.Frame(theme_frame, bg=self.colors['surface'])
        theme_buttons_frame.pack(side=tk.LEFT, padx=(20, 0))
        
        themes = [
            ("🔵 蓝色", self.colors['primary']),
            ("🔴 红色", '#F44336'),
            ("🟢 绿色", '#4CAF50'),
            ("🟡 橙色", '#FF9800')
        ]
        
        for theme_name, color in themes:
            theme_btn = tk.Button(theme_buttons_frame,
                                 text=theme_name,
                                 font=self.fonts['small'],
                                 bg=color,
                                 fg='white',
                                 relief=tk.FLAT,
                                 bd=0,
                                 padx=10,
                                 pady=5,
                                 cursor='hand2',
                                 command=lambda c=color: self.change_theme(c))
            theme_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # 恢复默认蓝色主题按钮
        reset_theme_btn = self.create_button(theme_frame,
                                           "↺ 恢复默认",
                                           lambda: self.change_theme('#1976D2'),
                                           self.colors['primary'])
        reset_theme_btn.pack(side=tk.RIGHT)
        
        # 验证设置卡片
        verification_card = self.create_card(main_container, "🔒 人机验证")
        
        # 验证状态显示
        verification_status_frame = tk.Frame(verification_card, bg=self.colors['surface'])
        verification_status_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.verification_status_label = tk.Label(verification_status_frame, 
                                                 text="状态: 未验证 (如遇到403/401错误时需要验证)", 
                                                 font=self.fonts['body'],
                                                 bg=self.colors['surface'],
                                                 fg=self.colors['text_secondary'])
        self.verification_status_label.pack(anchor='w')
        
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
        
        # 自动检查更新开关
        self.auto_update_var = tk.BooleanVar(value=self.config.get('auto_check_update', True))
        auto_check_btn = tk.Checkbutton(version_frame,
                                        text="启动时自动检查更新",
                                        variable=self.auto_update_var,
                                        command=self.save_config,
                                        font=self.fonts['body'],
                                        bg=self.colors['surface'])
        auto_check_btn.pack(side=tk.LEFT, padx=(20, 10))
        
        # 前往发布页按钮
        releases_url = f"https://github.com/{__github_repo__}/releases/latest"
        open_release_btn = self.create_button(version_frame,
                                             "🌐 发布页",
                                             lambda: webbrowser.open(releases_url),
                                             self.colors['secondary'])
        open_release_btn.pack(side=tk.RIGHT)
        
        # 检查更新按钮
        check_update_btn = self.create_button(version_frame,
                                             "🔄 检查更新",
                                             self.check_update_now,
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
                    'theme_color': self.colors['primary'],
                    'file_format': 'txt',
                    'download_mode': 'full',
                    'auto_check_update': True
                }
        except Exception as e:
            print(f"加载配置失败: {e}")
            return {
                'save_path': os.getcwd(),
                'theme_color': self.colors['primary'],
                'file_format': 'txt',
                'download_mode': 'full',
                'auto_check_update': True
            }
    
    def save_config(self):
        """保存配置文件"""
        try:
            config = {
                'save_path': self.save_path_entry.get() if hasattr(self, 'save_path_entry') else os.getcwd(),
                'theme_color': self.colors['primary'],
                'file_format': self.format_var.get() if hasattr(self, 'format_var') else 'txt',
                'download_mode': self.mode_var.get() if hasattr(self, 'mode_var') else 'full',
                'auto_check_update': self.auto_update_var.get() if hasattr(self, 'auto_update_var') else True
            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            print(f"配置已保存到: {self.config_file}")
        except Exception as e:
            print(f"保存配置失败: {e}")
    
    # ========== 事件处理方法 ==========
    
    def change_theme(self, color):
        """更改主题色彩"""
        self.colors['primary'] = color
        self.colors['primary_dark'] = color  # 简化处理
        # 保存配置
        self.save_config()
        messagebox.showinfo("主题更改", "主题色彩已更改并保存，重启应用后生效")
    
    
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
        download_btn.pack(side=tk.LEFT)
        
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
        
        self.status_label.config(text=message)
        self.log(f"{message}")
        self.root.update()
    
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
        mode = self.mode_var.get()
        
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
        threading.Thread(target=self._download_thread, args=(book_id, save_path, file_format, mode), daemon=True).start()
    
    def _download_thread(self, book_id, save_path, file_format, mode):
        """下载线程函数 - 完全集成enhanced_downloader.py的高速下载功能"""
        try:
            # 确保API已初始化
            if self.api is None:
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
            
            if mode == "full":
                # 整本下载 - 直接使用增强型下载器
                self.root.after(0, lambda: self.progress_callback(15, f"启动enhanced_downloader.py高速下载模式..."))
                
                # 直接使用增强型下载器的run_download方法
                downloader = self.api.enhanced_downloader
                downloader.progress_callback = gui_progress_callback
                
                # 在线程中运行下载，传递GUI验证回调
                downloader.run_download(book_id, save_path, file_format, gui_callback=self.api.gui_verification_callback)
                
                # 检查是否取消
                if downloader.is_cancelled:
                    self.root.after(0, lambda: self.progress_callback(0, "下载已取消"))
                    return
                
                # 获取保存的文件路径
                filename = f"{book_name}.{file_format}"
                filepath = os.path.join(save_path, filename)
                
                self.root.after(0, lambda path=filepath: self.progress_callback(100, f"高速下载完成！文件已保存到: {path}"))
                
            else:
                # 章节下载模式
                self.root.after(0, lambda: self.progress_callback(15, "章节下载模式：请选择章节范围..."))
                
                # 在主线程中创建章节选择对话框
                chapter_range = None
                def get_range():
                    nonlocal chapter_range
                    # 确保API已初始化
                    if self.api is None:
                        self.initialize_api()
                    # 获取章节总数
                    details_result = self.api.get_book_details(book_id)
                    if details_result and details_result.get('data', {}).get('allItemIds'):
                        total_chapters = len(details_result['data']['allItemIds'])
                        chapter_range = self._get_chapter_range(total_chapters)
                
                self.root.after(0, get_range)
                
                # 等待用户选择
                import time
                timeout = 30  # 30秒超时
                elapsed = 0
                while chapter_range is None and elapsed < timeout:
                    time.sleep(0.1)
                    elapsed += 0.1
                
                if not chapter_range:
                    self.root.after(0, lambda: self.progress_callback(0, "章节选择超时或用户取消"))
                    return
                
                start_idx, end_idx = chapter_range
                
                self.root.after(0, lambda: self.progress_callback(20, f"使用enhanced_downloader.py高速下载章节 {start_idx+1}-{end_idx+1}..."))
                
                # 使用增强型下载器的范围下载功能
                downloader = self.api.enhanced_downloader
                downloader.progress_callback = gui_progress_callback
                
                # 在线程中运行下载
                downloader.run_download(book_id, save_path, file_format, start_idx, end_idx)
                
                # 检查是否取消
                if downloader.is_cancelled:
                    self.root.after(0, lambda: self.progress_callback(0, "下载已取消"))
                    return
                
                # 获取保存的文件路径
                filename = f"{book_name}_第{start_idx+1}-{end_idx+1}章.{file_format}"
                filepath = os.path.join(save_path, filename)
                
                self.root.after(0, lambda path=filepath: self.progress_callback(100, f"章节高速下载完成！文件已保存到: {path}"))
                
        except Exception as e:
            error_msg = str(e)
            self.root.after(0, lambda: self.check_and_handle_api_error(f"下载失败: {error_msg}"))
            self.root.after(0, lambda: self.log(f"下载失败: {error_msg}"))
        finally:
            # 清理进度回调
            if hasattr(self.api, 'set_progress_callback'):
                self.api.set_progress_callback(None)
            self.root.after(0, self._download_finished)
    
    def _get_chapter_range(self, total_chapters):
        """获取章节范围选择"""
        # 创建章节选择对话框
        dialog = tk.Toplevel(self.root)
        dialog.title("选择章节范围")
        dialog.geometry("400x200")
        dialog.configure(bg=self.colors['background'])
        dialog.resizable(False, False)
        
        # 居中显示
        dialog.transient(self.root)
        dialog.grab_set()
        
        result = {'range': None}
        
        # 标题
        title_label = tk.Label(dialog, text=f"请选择要下载的章节范围 (共{total_chapters}章)", 
                              font=self.fonts['subtitle'],
                              bg=self.colors['background'],
                              fg=self.colors['text_primary'])
        title_label.pack(pady=20)
        
        # 输入框框架
        input_frame = tk.Frame(dialog, bg=self.colors['background'])
        input_frame.pack(pady=10)
        
        # 起始章节
        tk.Label(input_frame, text="起始章节:", 
                font=self.fonts['body'],
                bg=self.colors['background'],
                fg=self.colors['text_primary']).grid(row=0, column=0, padx=5)
        
        start_var = tk.StringVar(value="1")
        start_entry = tk.Entry(input_frame, textvariable=start_var, width=10)
        start_entry.grid(row=0, column=1, padx=5)
        
        # 结束章节
        tk.Label(input_frame, text="结束章节:", 
                font=self.fonts['body'],
                bg=self.colors['background'],
                fg=self.colors['text_primary']).grid(row=0, column=2, padx=5)
        
        end_var = tk.StringVar(value=str(total_chapters))
        end_entry = tk.Entry(input_frame, textvariable=end_var, width=10)
        end_entry.grid(row=0, column=3, padx=5)
        
        # 按钮框架
        button_frame = tk.Frame(dialog, bg=self.colors['background'])
        button_frame.pack(pady=20)
        
        def confirm():
            try:
                start = int(start_var.get())
                end = int(end_var.get())
                
                if start < 1 or end > total_chapters or start > end:
                    messagebox.showerror("错误", f"章节范围无效！请输入1-{total_chapters}之间的数字")
                    return
                
                result['range'] = (start - 1, end - 1)  # 转换为0基索引
                dialog.destroy()
            except ValueError:
                messagebox.showerror("错误", "请输入有效的数字")
        
        def cancel():
            dialog.destroy()
        
        confirm_btn = self.create_button(button_frame, "确定", confirm, self.colors['success'])
        confirm_btn.pack(side=tk.LEFT, padx=10)
        
        cancel_btn = self.create_button(button_frame, "取消", cancel, self.colors['error'])
        cancel_btn.pack(side=tk.LEFT, padx=10)
        
        # 等待对话框关闭
        dialog.wait_window()
        return result['range']
    
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
    
    def initialize_api(self):
        """初始化API，只在需要时调用"""
        if self.api is None:
            # 创建GUI验证码处理回调
            def gui_verification_callback(captcha_url):
                """在GUI中处理验证码输入"""
                # 创建一个临时变量存储结果
                result = {'token': None}
                
                # 创建一个事件等待对话框完成
                import threading
                event = threading.Event()
                
                def show_dialog():
                    try:
                        # 创建验证码对话框
                        self._create_captcha_dialog_for_api(captcha_url, result, event)
                    except Exception as e:
                        print(f"Error showing captcha dialog: {e}")
                        event.set()
                
                # 在主线程中显示对话框
                if threading.current_thread() is threading.main_thread():
                    show_dialog()
                else:
                    self.root.after(0, show_dialog)
                    event.wait(timeout=300)  # 等待5分钟
                
                return result.get('token', '')
            
            # 创建API实例，传入GUI回调
            self.api = TomatoNovelAPI(gui_verification_callback)
        return self.api
    
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
    
    def _create_captcha_dialog_for_api(self, verification_url, result, event):
        """为API初始化创建验证码对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("🔒 API初始化需要验证")
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
            if not token:
                messagebox.showwarning("输入错误", "请输入验证令牌")
                return
            
            # 保存token到环境变量
            os.environ["TOMATO_VERIFICATION_TOKEN"] = token
            result['token'] = token
            dialog.destroy()
            event.set()
            messagebox.showinfo("验证成功", "🎉 验证令牌已保存，API初始化继续...")
        
        def skip_verification():
            result['token'] = ''
            dialog.destroy()
            event.set()
            messagebox.showwarning("跳过验证", "跳过验证可能导致部分下载功能不可用")
        
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
            result['token'] = ''
            dialog.destroy()
            event.set()
        
        dialog.protocol("WM_DELETE_WINDOW", on_close)
        
        # 设置焦点
        token_entry.focus_set()
    
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
            
            # 保存验证令牌到环境变量
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
        """手动进行验证"""
        self.show_captcha_dialog()
    
    def clear_verification_token(self):
        """清除验证令牌"""
        try:
            # 清除环境变量中的验证令牌
            if "TOMATO_VERIFICATION_TOKEN" in os.environ:
                del os.environ["TOMATO_VERIFICATION_TOKEN"]
            
            # 更新状态显示
            self.update_verification_status("已清除验证令牌")
            messagebox.showinfo("清除成功", "验证令牌已清除")
        except Exception as e:
            messagebox.showerror("清除失败", f"清除验证令牌失败: {str(e)}")
    
    def update_verification_status(self, status_text, color=None):
        """更新验证状态显示"""
        if hasattr(self, 'verification_status_label'):
            if color is None:
                color = self.colors['text_secondary']
            self.verification_status_label.config(text=f"状态: {status_text}", fg=color)
    
    def check_existing_verification(self):
        """检查已有的验证状态"""
        verification_token = os.environ.get("TOMATO_VERIFICATION_TOKEN")
        if verification_token:
            self.update_verification_status("已保存验证令牌 ✓", self.colors['success'])
        else:
            self.update_verification_status("未验证 (如遇到403/401错误时需要验证)", self.colors['text_secondary'])

    def check_update_silent(self):
        """在后台静默检查更新"""
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
        """开始下载并安装更新（带进度窗口）"""
        # 创建进度窗口
        self._create_update_window()
        
        def progress_callback(current, total):
            percent = 0
            if total > 0:
                percent = int(current * 100 / total)
            self._update_download_progress(percent, current, total)
        
        def worker():
            file_path = self.updater.download_update(update_info, progress_callback=progress_callback)
            if not file_path:
                self.root.after(0, lambda: self._set_update_status("下载失败", error=True))
                return
            self.root.after(0, lambda: self._set_update_status("下载完成，正在安装..."))
            ok = self.updater.install_update(file_path, restart=True)
            if not ok:
                self.root.after(0, lambda: self._set_update_status("安装失败", error=True))
        threading.Thread(target=worker, daemon=True).start()

    def _create_update_window(self):
        if hasattr(self, 'update_window') and self.update_window and tk.Toplevel.winfo_exists(self.update_window):
            return
        self.update_window = tk.Toplevel(self.root)
        self.update_window.title("更新中")
        self.update_window.geometry("420x160")
        self.update_window.resizable(False, False)
        self.update_window.grab_set()
        
        frame = tk.Frame(self.update_window, bg=self.colors['surface'])
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        self.update_status_var = tk.StringVar(value="正在准备下载...")
        status_lbl = tk.Label(frame, textvariable=self.update_status_var, font=self.fonts['body'], bg=self.colors['surface'], fg=self.colors['text_primary'])
        status_lbl.pack(anchor='w')
        
        self.update_progress = tk.IntVar(value=0)
        self.update_progressbar = ttk.Progressbar(frame, orient='horizontal', mode='determinate', length=360, variable=self.update_progress, style='Modern.Horizontal.TProgressbar')
        self.update_progressbar.pack(pady=(12, 0))
        
        self.update_detail_var = tk.StringVar(value="0%")
        detail_lbl = tk.Label(frame, textvariable=self.update_detail_var, font=self.fonts['small'], bg=self.colors['surface'], fg=self.colors['text_secondary'])
        detail_lbl.pack(anchor='e', fill=tk.X)

    def _update_download_progress(self, percent, current, total):
        if hasattr(self, 'update_progress'):
            self.update_progress.set(percent)
        if hasattr(self, 'update_detail_var'):
            if total > 0:
                self.update_detail_var.set(f"{percent}%  ({current // 1024} KB / {total // 1024} KB)")
            else:
                self.update_detail_var.set(f"{current // 1024} KB")
        if hasattr(self, 'update_status_var'):
            self.update_status_var.set("正在下载更新...")
        self.root.update_idletasks()

    def _set_update_status(self, text, error=False):
        if hasattr(self, 'update_status_var'):
            self.update_status_var.set(text)
        if error:
            try:
                messagebox.showerror("更新失败", text)
            except Exception:
                pass

    def on_update_event(self, event, data):
        """处理更新过程中的事件回调"""
        if event == 'download_start':
            self._create_update_window()
            self._set_update_status("开始下载更新...")
        elif event == 'download_progress':
            cur = data.get('current', 0)
            total = data.get('total', 0)
            percent = data.get('percent', 0)
            self._update_download_progress(int(percent), cur, total)
        elif event == 'download_complete':
            self._set_update_status("下载完成，准备安装...")
        elif event == 'download_error':
            self._set_update_status(f"下载失败: {data}", error=True)
        elif event == 'install_start':
            self._set_update_status("正在安装更新...")
        elif event == 'install_error':
            self._set_update_status(f"安装失败: {data}", error=True)
        elif event == 'install_complete':
            # 某些平台安装成功后会退出当前程序并重启
            try:
                messagebox.showinfo("更新完成", "更新已安装，程序将重启")
            except Exception:
                pass

# 主程序入口
if __name__ == "__main__":
    root = tk.Tk()
    app = ModernNovelDownloaderGUI(root)
    root.mainloop()