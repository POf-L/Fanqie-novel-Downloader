
import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter as ctk
import threading
import os
import time
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import OrderedDict
import sys

# 导入项目中的其他模块
from config import CONFIG, save_user_config
# from request_handler import RequestHandler # Will be imported specifically below
from library import LibraryWindow, add_to_library
from request_handler import get_book_info, extract_chapters, down_text, get_headers as get_request_headers
from request_handler import RequestHandler # For cookie generation

# 设置 CustomTkinter 外观
ctk.set_appearance_mode("dark")  # 默认使用暗色主题
ctk.set_default_color_theme("blue")  # 默认使用蓝色主题

class NovelDownloaderGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # 基本窗口设置
        self.title("番茄小说下载器")
        self.geometry(CONFIG.get("default_window_geometry", "800x600"))
        
        # 状态变量
        self.is_downloading = False
        # self.downloaded_chapters = set() # Will be loaded in download_novel
        # self.content_cache = OrderedDict() # Will be replaced by chapter_results
        self.chapter_results = {} # Stores downloaded chapter content {index: {"base_title": ..., "api_title": ..., "content": ...}}
        self.request_handler = RequestHandler() # For cookie generation
        self.lock = threading.Lock()

        # Variables for graceful shutdown
        self.current_book_output_path = None
        self.current_book_name = None
        self.current_book_author = None
        self.current_book_description = None
        self.current_book_chapters_list = None
        self.downloaded_chapters_set = set() # Holds IDs of successfully downloaded chapters

        # 加载图标 (移到 setup_ui 之前)
        self.load_icons()

        # 设置UI
        self.setup_ui()

        # 绑定关闭事件
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def load_icons(self):
        """加载应用图标"""
        self.icons = {}
        icon_size = (20, 20)
        # 使用 resource_path 获取 assets 文件夹的绝对路径
        assets_path = resource_path("assets")
        
        # 尝试加载图标
        try:
            from PIL import Image
            icon_files = {
                "download": "download.png",
                "folder": "folder.png",
                "library": "library.png",
                "settings": "settings.png"
            }
            
            for name, file in icon_files.items():
                icon_path = os.path.join(assets_path, file)
                if os.path.exists(icon_path):
                    try:
                        img = Image.open(icon_path).resize(icon_size)
                        self.icons[name] = ctk.CTkImage(light_image=img, dark_image=img)
                    except Exception as e:
                        print(f"无法加载图标 {file}: {e}")
        except ImportError:
            print("PIL 模块未安装，无法加载图标")
    
    def setup_ui(self):
        """设置用户界面"""
        # 配置网格布局
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        
        # 创建主框架
        main_frame = ctk.CTkFrame(self)
        main_frame.grid(row=0, column=0, padx=20, pady=20, sticky="ew")
        main_frame.grid_columnconfigure(1, weight=1)
        
        # 小说ID输入区域
        id_label = ctk.CTkLabel(main_frame, text="小说ID:", anchor="w")
        id_label.grid(row=0, column=0, padx=(0, 10), pady=10, sticky="w")
        
        self.novel_id = ctk.CTkEntry(main_frame, placeholder_text="输入番茄小说ID")
        self.novel_id.grid(row=0, column=1, padx=5, pady=10, sticky="ew")
        
        # 保存路径区域
        path_label = ctk.CTkLabel(main_frame, text="保存路径:", anchor="w")
        path_label.grid(row=1, column=0, padx=(0, 10), pady=10, sticky="w")
        
        self.save_path = ctk.CTkEntry(main_frame, placeholder_text="选择保存位置")
        self.save_path.grid(row=1, column=1, padx=5, pady=10, sticky="ew")
        self.save_path.insert(0, CONFIG["file"].get("default_save_path", "downloads"))
        
        # 浏览按钮
        browse_button = ctk.CTkButton(
            main_frame, 
            text="浏览",
            command=self.browse_folder,
            width=80,
            image=self.icons.get("folder"),
            compound="left" if "folder" in self.icons else "none"
        )
        browse_button.grid(row=1, column=2, padx=5, pady=10)
        
        # 下载按钮
        self.download_button = ctk.CTkButton(
            main_frame, 
            text="开始下载",
            command=self.start_download,
            width=120,
            image=self.icons.get("download"),
            compound="left" if "download" in self.icons else "none"
        )
        self.download_button.grid(row=1, column=3, padx=5, pady=10)
        
        # 书库按钮
        library_button = ctk.CTkButton(
            main_frame, 
            text="我的书库",
            command=self.open_library,
            width=120,
            image=self.icons.get("library"),
            compound="left" if "library" in self.icons else "none"
        )
        library_button.grid(row=0, column=3, padx=5, pady=10)
        
        # 进度区域
        progress_frame = ctk.CTkFrame(self)
        progress_frame.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="ew")
        progress_frame.grid_columnconfigure(0, weight=1)
        
        # 进度条
        self.progress_var = ctk.DoubleVar(value=0)
        self.progress_bar = ctk.CTkProgressBar(progress_frame)
        self.progress_bar.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        self.progress_bar.set(0)
        
        # 状态标签
        self.status_label = ctk.CTkLabel(progress_frame, text="准备就绪", anchor="center")
        self.status_label.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="ew")
        
        # 日志区域
        log_frame = ctk.CTkFrame(self)
        log_frame.grid(row=2, column=0, padx=20, pady=(0, 20), sticky="nsew")
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(0, weight=1)
        
        # 日志文本框
        self.log_text = ctk.CTkTextbox(log_frame, wrap="word")
        self.log_text.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.log_text.configure(state="disabled")
        
        # 底部按钮区域
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.grid(row=3, column=0, padx=20, pady=(0, 20), sticky="ew")
        
        # 设置按钮
        settings_button = ctk.CTkButton(
            bottom_frame, 
            text="设置",
            command=self.open_settings,
            width=100,
            image=self.icons.get("settings"),
            compound="left" if "settings" in self.icons else "none"
        )
        settings_button.pack(side="left", padx=5)
        
        # 清空日志按钮
        clear_log_button = ctk.CTkButton(
            bottom_frame, 
            text="清空日志",
            command=self.clear_log,
            width=100
        )
        clear_log_button.pack(side="right", padx=5)
    
    def log(self, message):
        """添加日志"""
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
        self.update_idletasks()
    
    def update_progress(self, value, status_text):
        """更新进度和状态"""
        self.progress_var.set(value)
        self.progress_bar.set(value / 100)  # 进度条值范围是0-1
        self.status_label.configure(text=status_text)
        self.update_idletasks()
    
    def browse_folder(self):
        """打开文件夹选择对话框"""
        folder_path = filedialog.askdirectory(title="选择保存位置")
        if folder_path:
            self.save_path.delete(0, "end")
            self.save_path.insert(0, folder_path)
    
    def start_download(self):
        """开始下载"""
        if self.is_downloading:
            messagebox.showwarning("提示", "下载正在进行中")
            return
        
        novel_id = self.novel_id.get().strip()
        if not novel_id:
            messagebox.showerror("错误", "请输入小说ID")
            return
        
        save_path = self.save_path.get().strip()
        if not save_path:
            save_path = CONFIG["file"].get("default_save_path", "downloads")
        
        # 检查cookie是否可用
        try:
            # 尝试获取cookie，如果失败会抛出异常
            self.request_handler.get_cookie()
        except Exception as e:
            self.log(f"Cookie错误: {str(e)}")
            messagebox.showerror(
                "Cookie错误",
                f"无法获取有效Cookie，请检查网络连接或手动清除cookie.json文件\n\n错误详情:\n{str(e)}"
            )
            return
        
        self.download_button.configure(state="disabled")
        self.is_downloading = True
        self.chapter_results = {} # Reset for current download
        
        # Initial call to update progress bar and status
        self.update_progress(0, "开始下载...")

        threading.Thread(target=self.download_novel_thread, # Changed target
                       args=(novel_id, save_path),
                       daemon=True).start()

    def load_status(self, save_path):
        status_file = os.path.join(save_path, CONFIG["file"]["status_file"])
        if os.path.exists(status_file):
            try:
                with open(status_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return set(data)
                    self.log(f"警告: 状态文件 {status_file} 格式不正确, 将重新开始下载.")
                    return set()
            except Exception as e:
                self.log(f"加载状态文件 {status_file} 失败: {e}. 将重新开始下载.")
                return set()
        return set()

    def save_status(self, save_path, downloaded_ids):
        status_file = os.path.join(save_path, CONFIG["file"]["status_file"])
        try:
            os.makedirs(save_path, exist_ok=True) # Ensure directory exists
            with open(status_file, 'w', encoding='utf-8') as f:
                json.dump(list(downloaded_ids), f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.log(f"保存状态到 {status_file} 失败: {e}")

    def write_downloaded_chapters_in_order(self, output_file_path, book_name, author, description, chapters_list, chapter_results_map):
        self.log(f"正在按顺序写入章节到 {output_file_path}...")
        try:
            os.makedirs(os.path.dirname(output_file_path), exist_ok=True) # Ensure directory exists
            with open(output_file_path, 'w', encoding='utf-8') as f:
                f.write(f"小说名: {book_name}\n作者: {author}\n内容简介: {description}\n\n")
                
                processed_content_hashes = set() # For basic deduplication by content

                for chapter_data in chapters_list:
                    idx = chapter_data["index"]
                    if idx in chapter_results_map:
                        result = chapter_results_map[idx]
                        
                        # Basic content deduplication check
                        content_hash = hash(result["content"])
                        if content_hash in processed_content_hashes:
                            self.log(f"跳过内容重复的章节: {result['base_title']}")
                            continue
                        processed_content_hashes.add(content_hash)

                        title = f'{result["base_title"]}'
                        # api_title from down_text is not directly available in the current down_text implementation
                        # If down_text were to return a dict with 'title' and 'content', this could be used.
                        # For now, api_title part is omitted.
                        # if result.get("api_title"): 
                        #     title += f' {result["api_title"]}'
                        
                        f.write(f"{title}\n\n") # Extra newline for readability between title and content
                        f.write(result["content"] + '\n\n\n') # Extra newlines for readability between chapters
                    # else:
                        # Chapter was not downloaded or failed.
                        # Optionally log this or write a placeholder.
                        # self.log(f"章节 {chapter_data['title']} (ID: {chapter_data['id']}) 未下载。")
            self.log(f"完成写入章节到 {output_file_path}.")
        except Exception as e:
            self.log(f"写入章节到文件时发生错误: {e}")
            
    def _download_chapter_task(self, chapter_info, book_id_for_fqv, current_api_index, success_counter_list, failed_chapters_list, total_chapters_for_progress):
        """
        Worker task for downloading a single chapter.
        success_counter_list is a list with one int element to allow modification by reference.
        """
        try:
            # The new down_text doesn't strictly need book_id for FqReq's primary path,
            # but FqVariable init does. current_api_index is for down_text's fallback.
            # down_text now directly returns the content string or raises an error.
            content = down_text(chapter_info["id"], current_api_index=current_api_index)
            
            if content:
                with self.lock:
                    self.chapter_results[chapter_info["index"]] = {
                        "base_title": chapter_info["title"], 
                        "api_title": None, # down_text currently doesn't return a separate API title
                        "content": content
                    }
                    self.downloaded_chapters_set.add(chapter_info["id"]) # Use the shared set
                    success_counter_list[0] += 1
                self.log(f"已下载: {chapter_info['title']}")
            else:
                # This case might not be reached if down_text raises error on empty content
                self.log(f"下载内容为空: {chapter_info['title']}")
                with self.lock:
                    failed_chapters_list.append(chapter_info)
        except Exception as e:
            self.log(f"下载失败: {chapter_info['title']} - {str(e)}")
            with self.lock:
                failed_chapters_list.append(chapter_info)
        finally:
            with self.lock:
                # Calculate progress based on chapters attempted vs total initial todo_chapters or total_chapters overall
                # For simplicity, using success_counter_list[0] against total_chapters_for_progress
                progress = (success_counter_list[0] / total_chapters_for_progress) * 100 if total_chapters_for_progress > 0 else 0
                self.update_progress(progress, f"下载进度: {success_counter_list[0]}/{total_chapters_for_progress}")

    def download_novel_thread(self, book_id, save_path): # Renamed from download_novel
        name = None
        author_name = None
        description = None
        chapters_list = []
        output_file = ""
        initial_total_chapters = 0
        
        # Reset graceful shutdown variables at the start of a new download
        self.current_book_output_path = None
        self.current_book_name = None
        self.current_book_author = None
        self.current_book_description = None
        self.current_book_chapters_list = None
        # self.downloaded_chapters_set is loaded/cleared based on user choice later

        try:
            self.log("开始下载流程...")
            headers = get_request_headers() # Get headers once

            self.log("正在获取书籍信息...")
            name, author_name, description = get_book_info(book_id, headers)
            if not name or not author_name: # Description can be empty
                self.log("无法获取书籍信息。请检查小说ID或网络。")
                messagebox.showerror("错误", "无法获取书籍信息，请检查小说ID或网络连接。")
                return # Exit thread

            self.log(f"书名: 《{name}》, 作者: {author_name}")
            output_file = os.path.join(save_path, f"{name}.txt")
            os.makedirs(save_path, exist_ok=True)
            
            # Store info for graceful shutdown
            self.current_book_output_path = output_file
            self.current_book_name = name
            self.current_book_author = author_name
            self.current_book_description = description

            self.log("正在获取章节列表...")
            chapters_list = extract_chapters(book_id, headers)
            if not chapters_list:
                self.log("未找到任何章节。")
                messagebox.showerror("错误", "未找到任何章节。")
                # Reset before exiting due to no chapters
                self.current_book_output_path = None 
                return # Exit thread
            
            self.current_book_chapters_list = chapters_list # Store for graceful shutdown
            initial_total_chapters = len(chapters_list)
            self.log(f"共找到 {initial_total_chapters} 章。")

            self.downloaded_chapters_set = self.load_status(save_path) # Load downloaded chapter IDs
            
            # Load already downloaded content if status exists and user doesn't want full re-download
            # This part requires chapters_list to be available
            if self.downloaded_chapters_set:
                self.log(f"检测到 {len(self.downloaded_chapters_set)} 个已下载章节的记录。")
                if messagebox.askyesno("重新下载?", 
                                       f"检测到之前下载过的章节记录。\n是否要清除记录并重新下载所有章节？\n"
                                       f"(选择“否”将仅下载未完成的章节)", parent=self):
                    self.log("用户选择重新下载所有章节。清除本地下载记录。")
                    self.downloaded_chapters_set.clear()
                    self.chapter_results.clear() 
                    self.save_status(save_path, set()) # Clear status file
                else:
                    self.log("用户选择仅下载未完成的章节。")
                    # Try to populate chapter_results for already downloaded chapters if we want to rewrite the whole file
                    # For now, this logic is simplified: we only download new chapters, and write_downloaded_chapters_in_order
                    # will write what's in chapter_results. If old chapters are not in chapter_results, they won't be written.
                    # To include them, they'd need to be re-fetched or their content stored persistently.
                    # The current prompt implies chapter_results is for the current session's downloads.
                    pass


            todo_chapters = [ch for ch in chapters_list if ch["id"] not in self.downloaded_chapters_set]

            if not todo_chapters:
                self.log("所有章节均已下载。")
                messagebox.showinfo("完成", "所有章节均已下载。如果您想重新下载，请在提示时选择“是”。", parent=self)
                # Ensure final file is written with all content if not re-downloading everything
                # This requires populating self.chapter_results with *all* chapters, potentially re-downloading if not careful
                # For now, if todo_chapters is empty, we assume the existing file is fine, or it will be handled by a full re-download choice.
                # To be robust, if not re-downloading all and todo is empty, we should ensure existing content is loaded into chapter_results
                # or that write_downloaded_chapters_in_order can somehow access previously stored content.
                # The simplest approach is to re-download if the user wants a fresh file.
                # If they hit "No" on re-download and todo is empty, we can just exit.
                return

            self.log(f"准备下载 {len(todo_chapters)} 个新章节。")
            
            # This success_count tracks chapters downloaded in *this session* or *this major attempt*
            # It's wrapped in a list to be mutable by the thread tasks
            current_session_success_count_list = [0] 
            
            # Initial write of book info, even if some chapters fail, this will be at the top
            # self.write_downloaded_chapters_in_order(output_file, name, author_name, description, chapters_list, self.chapter_results)

            max_retries_for_failed_batches = CONFIG["request"].get('max_retries', 3)
            
            for attempt in range(max_retries_for_failed_batches):
                if not todo_chapters: # All chapters successfully downloaded
                    break

                self.log(f"开始下载批次 (尝试 {attempt + 1}/{max_retries_for_failed_batches}) - {len(todo_chapters)} 章节待处理。")
                failed_chapters_this_attempt = []
                
                # Progress is based on initial_total_chapters, not just todo_chapters, to give a sense of overall completion
                # However, success_counter_list tracks successful downloads in the current session's attempts.
                # For progress bar: total_for_progress = initial_total_chapters
                # For success_counter: current_session_success_count_list[0]
                # This means the progress bar reflects total book completion including previous downloads.

                # Let's adjust success_counter to reflect total known downloaded chapters for progress bar
                # It should be len(self.downloaded_chapters_set) + newly_downloaded_in_session
                # For simplicity, _download_chapter_task updates progress based on total_chapters_for_progress which is initial_total_chapters.
                # And current_session_success_count_list[0] is the number of *newly* downloaded ones.
                # So, update_progress inside the task should use (len(self.downloaded_chapters_set) + new_successes) / initial_total_chapters
                # For now, _download_chapter_task uses its own success_counter_list[0] which tracks NEW successes.
                # The total number of chapters to calculate percentage against in _download_chapter_task should be initial_total_chapters.

                with ThreadPoolExecutor(max_workers=CONFIG["request"].get("max_workers", 5)) as executor:
                    futures = {
                        executor.submit(self._download_chapter_task, chapter, book_id, attempt, current_session_success_count_list, failed_chapters_this_attempt, initial_total_chapters): chapter
                        for chapter in todo_chapters # download chapters from the current todo_chapters list
                    }
                    for future in as_completed(futures):
                        # Exception handling is within _download_chapter_task
                        # We just wait for completion here
                        future.result() # Call result to raise exceptions from the task if not caught inside

                # After each batch attempt, save progress
                self.write_downloaded_chapters_in_order(output_file, name, author_name, description, chapters_list, self.chapter_results)
                self.save_status(save_path, self.downloaded_chapters_set)

                todo_chapters = failed_chapters_this_attempt
                if todo_chapters:
                    self.log(f"批次尝试 {attempt + 1} 后，仍有 {len(todo_chapters)} 个章节下载失败。")
                    if attempt < max_retries_for_failed_batches - 1:
                         self.log("将在1秒后重试...")
                         time.sleep(1)
                else:
                    self.log("当前批次所有章节已成功下载。")
                    break # Exit retry loop if all successful

            if todo_chapters: # If after all retries, some chapters still failed
                self.log(f"完成所有下载尝试后，仍有 {len(todo_chapters)} 个章节下载失败。")
                messagebox.showwarning("下载未完整", f"部分章节下载失败。已成功下载 {current_session_success_count_list[0]} 个新章节。\n"
                                                  f"总计已完成 {len(self.downloaded_chapters_set)}/{initial_total_chapters} 章节。\n"
                                                  f"文件保存在: {output_file}", parent=self)
            else:
                self.log("所有章节已成功下载！")
                messagebox.showinfo("下载完成", 
                                    f"小说《{name}》所有章节已成功下载！\n"
                                    f"总计 {len(self.downloaded_chapters_set)}/{initial_total_chapters} 章节。\n"
                                    f"文件保存在: {output_file}", parent=self)

            # Add to library
            if name and author_name: # Ensure book info was fetched
                book_info_lib = {
                    "name": name, "author": author_name, "description": description, "save_path": save_path
                }
                add_to_library(book_id, book_info_lib, output_file)
                self.log("已添加到书库。")

        except Exception as e:
            self.log(f"下载小说时发生严重错误: {e}")
            messagebox.showerror("严重错误", f"下载过程中发生错误: {str(e)}", parent=self)
            # Save any progress made before the critical error
            if name and chapters_list and output_file: # Check if these variables are initialized
                 self.write_downloaded_chapters_in_order(output_file, name, author_name, description, chapters_list, self.chapter_results)
            if hasattr(self, 'downloaded_chapters_set'): # Check if set was initialized
                 self.save_status(save_path, self.downloaded_chapters_set)
        finally:
            self.is_downloading = False
            self.download_button.configure(state="normal")
            self.update_progress(100, "下载结束") # Final progress update
            self.log("下载流程结束。")
            
            # Reset graceful shutdown variables after successful completion or error handled within
            self.current_book_output_path = None
            self.current_book_name = None
            self.current_book_author = None
            self.current_book_description = None
            self.current_book_chapters_list = None
            # self.downloaded_chapters_set is persisted by save_status

    def open_library(self):
        """打开书库窗口"""
        try:
            # 获取当前窗口几何信息
            current_geometry = self.geometry()
            library_window = LibraryWindow(self, geometry=current_geometry)
            library_window.focus()
        except Exception as e:
            messagebox.showerror("错误", f"无法打开书库: {str(e)}")
    
    def open_settings(self):
        """打开设置窗口"""
        # 创建设置窗口
        settings_window = SettingsWindow(self)
        settings_window.focus()
    
    def clear_log(self):
        """清空日志"""
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
    
    def on_closing(self):
        """窗口关闭处理"""
        if self.is_downloading:
            if messagebox.askyesno("确认", "下载正在进行中，确定要退出吗？\n未保存的进度将会尝试保存。", parent=self):
                self.log("下载被用户中断。正在尝试保存进度...")
                
                # Save status (chapter IDs)
                # Ensure self.save_path.get().strip() is the correct directory path
                current_save_dir = self.save_path.get().strip()
                if not current_save_dir: # Fallback if UI field is empty for some reason
                    current_save_dir = CONFIG["file"].get("default_save_path", "downloads")

                if hasattr(self, 'downloaded_chapters_set') and self.downloaded_chapters_set:
                    self.save_status(current_save_dir, self.downloaded_chapters_set)
                    self.log(f"已保存 {len(self.downloaded_chapters_set)} 个章节的下载状态。")
                else:
                    self.log("没有已下载章节的状态信息可保存。")

                # Save content (write to file)
                if (hasattr(self, 'current_book_output_path') and self.current_book_output_path and
                        hasattr(self, 'current_book_name') and self.current_book_name and # Ensure name is not None
                        hasattr(self, 'current_book_chapters_list') and self.current_book_chapters_list and
                        isinstance(self.chapter_results, dict)): # Ensure chapter_results is a dict
                    
                    self.log(f"正在写入已下载内容到 {self.current_book_output_path}...")
                    self.write_downloaded_chapters_in_order(
                        self.current_book_output_path,
                        self.current_book_name,
                        self.current_book_author if hasattr(self, 'current_book_author') else "未知作者", # Handle if author is None
                        self.current_book_description if hasattr(self, 'current_book_description') else "无简介", # Handle if desc is None
                        self.current_book_chapters_list,
                        self.chapter_results 
                    )
                    self.log("内容写入尝试完成。")
                else:
                    self.log("没有足够的书籍信息或章节内容来写入文件。")
                
                self.is_downloading = False # Explicitly stop download state
                self.destroy()
            else:
                # User chose not to exit
                return 
        else:
            self.destroy()


class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("设置")
        self.geometry("500x400")
        
        # 加载当前配置
        self.config = CONFIG.copy()
        
        # 设置UI
        self.setup_ui()
        
        # 使窗口模态
        self.transient(master)
        self.grab_set()
        
        # 绑定关闭事件
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def setup_ui(self):
        """设置UI"""
        # 创建选项卡
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=20)
        
        # 添加选项卡
        self.tabview.add("下载设置")
        self.tabview.add("阅读器设置")
        self.tabview.add("文件设置")
        
        # 下载设置选项卡
        download_tab = self.tabview.tab("下载设置")
        download_tab.grid_columnconfigure(1, weight=1)
        
        # 线程数设置
        ctk.CTkLabel(download_tab, text="下载线程数:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.max_workers_var = ctk.StringVar(value=str(self.config["request"].get("max_workers", 5)))
        max_workers_entry = ctk.CTkEntry(download_tab, textvariable=self.max_workers_var, width=100)
        max_workers_entry.grid(row=0, column=1, padx=10, pady=10, sticky="w")
        
        # 重试次数设置
        ctk.CTkLabel(download_tab, text="重试次数:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.max_retries_var = ctk.StringVar(value=str(self.config["request"].get("max_retries", 3)))
        max_retries_entry = ctk.CTkEntry(download_tab, textvariable=self.max_retries_var, width=100)
        max_retries_entry.grid(row=1, column=1, padx=10, pady=10, sticky="w")
        
        # 请求超时设置
        ctk.CTkLabel(download_tab, text="请求超时(秒):").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self.request_timeout_var = ctk.StringVar(value=str(self.config["request"].get("request_timeout", 15)))
        request_timeout_entry = ctk.CTkEntry(download_tab, textvariable=self.request_timeout_var, width=100)
        request_timeout_entry.grid(row=2, column=1, padx=10, pady=10, sticky="w")
        
        # 阅读器设置选项卡
        reader_tab = self.tabview.tab("阅读器设置")
        reader_tab.grid_columnconfigure(1, weight=1)
        
        # 默认字体设置
        ctk.CTkLabel(reader_tab, text="默认字体:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.default_font_var = ctk.StringVar(value=self.config["reader"].get("default_font", "Arial"))
        default_font_entry = ctk.CTkEntry(reader_tab, textvariable=self.default_font_var, width=150)
        default_font_entry.grid(row=0, column=1, padx=10, pady=10, sticky="w")
        
        # 默认字体大小设置
        ctk.CTkLabel(reader_tab, text="默认字体大小:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.default_size_var = ctk.StringVar(value=str(self.config["reader"].get("default_size", 12)))
        default_size_entry = ctk.CTkEntry(reader_tab, textvariable=self.default_size_var, width=100)
        default_size_entry.grid(row=1, column=1, padx=10, pady=10, sticky="w")
        
        # 暗色模式设置
        ctk.CTkLabel(reader_tab, text="默认使用暗色模式:").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self.dark_mode_var = ctk.BooleanVar(value=self.config["reader"].get("dark_mode", True))
        dark_mode_switch = ctk.CTkSwitch(reader_tab, text="", variable=self.dark_mode_var)
        dark_mode_switch.grid(row=2, column=1, padx=10, pady=10, sticky="w")
        
        # 文件设置选项卡
        file_tab = self.tabview.tab("文件设置")
        file_tab.grid_columnconfigure(1, weight=1)

        # 默认保存路径设置
        ctk.CTkLabel(file_tab, text="默认保存路径:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.default_save_path_var = ctk.StringVar(value=self.config["file"].get("default_save_path", "downloads"))
        default_save_path_entry = ctk.CTkEntry(file_tab, textvariable=self.default_save_path_var, width=250)
        default_save_path_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        # 浏览按钮
        browse_button = ctk.CTkButton(file_tab, text="浏览", command=self.browse_save_path, width=80)
        browse_button.grid(row=0, column=2, padx=10, pady=10)

        # 清除 Cookie 按钮
        clear_cookie_button = ctk.CTkButton(file_tab, text="清除 Cookie", command=self.clear_cookie_file, width=120, fg_color="red", hover_color="#C40000")
        clear_cookie_button.grid(row=1, column=0, columnspan=3, padx=10, pady=(20, 10), sticky="w")


        # --- 添加阅读器颜色设置 ---
        # 默认文字颜色
        ctk.CTkLabel(reader_tab, text="默认文字颜色:").grid(row=3, column=0, padx=10, pady=10, sticky="w")
        self.default_fg_var = ctk.StringVar(value=self.config["reader"].get("default_fg", "#000000"))
        fg_color_entry = ctk.CTkEntry(reader_tab, textvariable=self.default_fg_var, width=100)
        fg_color_entry.grid(row=3, column=1, padx=10, pady=10, sticky="w")
        fg_color_button = ctk.CTkButton(reader_tab, text="选择", command=self.choose_fg_color, width=60)
        fg_color_button.grid(row=3, column=2, padx=5, pady=10)

        # 默认背景颜色
        ctk.CTkLabel(reader_tab, text="默认背景颜色:").grid(row=4, column=0, padx=10, pady=10, sticky="w")
        self.default_bg_var = ctk.StringVar(value=self.config["reader"].get("default_bg", "#FFFFFF"))
        bg_color_entry = ctk.CTkEntry(reader_tab, textvariable=self.default_bg_var, width=100)
        bg_color_entry.grid(row=4, column=1, padx=10, pady=10, sticky="w")
        bg_color_button = ctk.CTkButton(reader_tab, text="选择", command=self.choose_bg_color, width=60)
        bg_color_button.grid(row=4, column=2, padx=5, pady=10)
        # --- 结束添加阅读器颜色设置 ---

        # 底部按钮
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        # 保存按钮
        save_button = ctk.CTkButton(button_frame, text="保存设置", command=self.save_settings, width=120)
        save_button.pack(side="right", padx=10)
        
        # 取消按钮
        cancel_button = ctk.CTkButton(button_frame, text="取消", command=self.on_closing, width=120)
        cancel_button.pack(side="right", padx=10)
    
    def browse_save_path(self):
        """浏览保存路径"""
        folder_path = filedialog.askdirectory(title="选择默认保存位置")
        if folder_path:
            self.default_save_path_var.set(folder_path)

    def clear_cookie_file(self):
        """清除 Cookie 文件"""
        cookie_path = CONFIG["file"]["cookie_file"]
        if os.path.exists(cookie_path):
            if messagebox.askyesno("确认", f"确定要清除 Cookie 文件 ({cookie_path}) 吗？\n这将需要重新生成 Cookie。", parent=self):
                try:
                    os.remove(cookie_path)
                    messagebox.showinfo("成功", "Cookie 文件已清除。", parent=self)
                except Exception as e:
                    messagebox.showerror("错误", f"清除 Cookie 文件失败: {str(e)}", parent=self)
        else:
            messagebox.showinfo("提示", "Cookie 文件不存在。", parent=self)

    def choose_fg_color(self):
        """选择默认文字颜色"""
        from tkinter import colorchooser
        color = colorchooser.askcolor(title="选择默认文字颜色", initialcolor=self.default_fg_var.get())[1]
        if color:
            self.default_fg_var.set(color)

    def choose_bg_color(self):
        """选择默认背景颜色"""
        from tkinter import colorchooser
        color = colorchooser.askcolor(title="选择默认背景颜色", initialcolor=self.default_bg_var.get())[1]
        if color:
            self.default_bg_var.set(color)

    def save_settings(self):
        """保存设置"""
        try:
            # 更新下载设置
            self.config["request"]["max_workers"] = int(self.max_workers_var.get())
            self.config["request"]["max_retries"] = int(self.max_retries_var.get())
            self.config["request"]["request_timeout"] = int(self.request_timeout_var.get())

            # 更新阅读器设置
            self.config["reader"]["default_font"] = self.default_font_var.get()
            self.config["reader"]["default_size"] = int(self.default_size_var.get())
            self.config["reader"]["dark_mode"] = self.dark_mode_var.get()
            self.config["reader"]["default_fg"] = self.default_fg_var.get() # 保存文字颜色
            self.config["reader"]["default_bg"] = self.default_bg_var.get() # 保存背景颜色

            # 更新文件设置
            self.config["file"]["default_save_path"] = self.default_save_path_var.get()

            # 保存配置
            save_user_config(self.config)

            messagebox.showinfo("成功", "设置已保存")
            self.destroy()
        except ValueError as e:
            messagebox.showerror("错误", f"输入值无效: {str(e)}")
        except Exception as e:
            messagebox.showerror("错误", f"保存设置失败: {str(e)}")

    def on_closing(self):
        """关闭窗口"""
        self.destroy()


if __name__ == "__main__":
    # 检查是否已安装 customtkinter
    try:
        import customtkinter
    except ImportError:
        print("未安装 customtkinter 模块，将使用传统 tkinter 界面")
        from tkinter import Tk
        root = Tk()
        root.withdraw()
        messagebox.showerror("错误", "未安装 customtkinter 模块，请安装后再运行程序")
        sys.exit(1)
# 解决打包后的资源路径问题
def resource_path(relative_path):
    """获取打包后的资源绝对路径"""
    try:
        # PyInstaller创建临时文件夹存储资源
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# 导入并显示启动画面
try:
    from splash import SplashScreen # 导入 SplashScreen 类

    # 1. 创建主应用实例
    app = NovelDownloaderGUI()
    # 2. 隐藏主应用窗口
    app.withdraw()

    # 3. 创建并显示启动画面，主应用实例作为父窗口
    # SplashScreen 内部会使用 after 调用 app.deiconify() 来显示主窗口
    # 使用 resource_path 获取 logo 路径
    logo_path = resource_path("assets/app_icon.png")
    splash = SplashScreen(app, logo_path=logo_path, duration=2.0)
    # splash.mainloop() # 不需要单独的 mainloop for splash

    # 4. 启动主应用的 mainloop
    app.mainloop()

except ImportError:
    print("无法导入 splash 模块，跳过启动画面。")
    # 如果无法导入启动画面，直接启动主应用
    app = NovelDownloaderGUI()
    app.mainloop()
except Exception as e:
    print(f"显示启动画面时出错: {e}")
    # 即使启动画面出错，也尝试启动主应用
    app = NovelDownloaderGUI()
    app.mainloop()