# -*- coding: utf-8 -*-
"""稳定启动器：仅负责拉取并启动远程 Runtime。"""

import concurrent.futures
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import zipfile
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

# 导入仓库配置管理模块（带异常处理）
try:
    from utils.repo_config import get_effective_repo
    REPO_CONFIG_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ 仓库配置模块不可用: {e}，使用默认配置")
    REPO_CONFIG_AVAILABLE = False
    def get_effective_repo():
        return "POf-L/Fanqie-novel-Downloader", "默认值"
from pathlib import Path

import requests

# TUI组件导入
try:
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, DownloadColumn, TimeRemainingColumn
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich.live import Live
    from rich.prompt import Prompt, Confirm
    from rich.align import Align
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

try:
    from InquirerPy import inquirer
    INQUIRER_AVAILABLE = True
except ImportError:
    INQUIRER_AVAILABLE = False


@dataclass
class DownloadOption:
    id: str
    name: str
    description: str


@dataclass
class MirrorInfo:
    name: str
    url: str
    latency: Optional[float] = None


class LauncherTUI:

    def __init__(self):
        self.console = Console() if RICH_AVAILABLE else None
        self.use_tui = RICH_AVAILABLE and self._is_tui_available()

    def _is_tui_available(self) -> bool:
        if not sys.stdout.isatty():
            return False
        return True

    def print(self, *args, **kwargs):
        if self.use_tui and self.console:
            self.console.print(*args, **kwargs)
        else:
            print(*args, **kwargs)

    def show_header(self):
        if self.use_tui:
            header_text = Text("番茄小说下载器 启动器", style="bold blue")
            panel = Panel(
                Align.center(header_text),
                border_style="blue",
                padding=(1, 2)
            )
            self.console.print(panel)
        else:
            print("=" * 50)
            print("番茄小说下载器 启动器")
            print("=" * 50)

    def show_debug_info(self, debug_info: dict):
        if self.use_tui:
            table = Table(title="环境信息", show_header=False, box=None)
            table.add_column("Key", style="cyan")
            table.add_column("Value", style="white")
            for key, value in debug_info.items():
                table.add_row(key, str(value))
            panel = Panel(table, title="DEBUG", border_style="dim")
            self.console.print(panel)
        else:
            self.print("[DEBUG] ========== 启动环境信息 ==========")
            for key, value in debug_info.items():
                self.print(f"[DEBUG] {key}: {value}")
            self.print("[DEBUG] ======================================")

    def _inquirer_select(self, message: str, choices: List[dict], default: Any = None) -> Any:
        if INQUIRER_AVAILABLE:
            try:
                return inquirer.select(
                    message=message,
                    choices=choices,
                    default=default,
                    pointer="▸",
                    instruction="(↑/↓ 移动, Enter 确认)",
                ).execute()
            except Exception:
                pass
        return None

    def _arrow_select(self, message: str, options: List[DownloadOption], default: str = "3") -> str:
        """使用方向键选择选项"""
        if not self.use_tui or not self.console:
            # 回退到数字输入
            for i, opt in enumerate(options, 1):
                print(f"  {i}. {opt.name} - {opt.description}")
            try:
                choice = input(f"请输入选项 [1-{len(options)}] (默认 {default}): ").strip()
            except (EOFError, KeyboardInterrupt):
                choice = default
            if choice.isdigit() and 1 <= int(choice) <= len(options):
                return options[int(choice) - 1].id
            return default

        # Windows系统检查
        if sys.platform == "win32":
            return self._windows_arrow_select(message, options, default)
        else:
            return self._unix_arrow_select(message, options, default)

    def _windows_arrow_select(self, message: str, options: List[DownloadOption], default: str = "3") -> str:
        """Windows系统的方向键选择"""
        import msvcrt
        
        console = Console()
        
        # 找到默认选项的索引
        default_index = 0
        for i, opt in enumerate(options):
            if opt.id == default:
                default_index = i
                break
        
        current_index = default_index
        
        def display_options():
            console.clear()
            console.print(f"\n[bold cyan]{message}[/bold cyan]")
            console.print("[dim](使用 ↑/↓ 移动, Enter 确认)[/dim]\n")
            
            for i, opt in enumerate(options):
                if i == current_index:
                    console.print(f"▸ [bold green]{opt.name}[/bold green] - [dim]{opt.description}[/dim]")
                else:
                    console.print(f"  {opt.name} - [dim]{opt.description}[/dim]")
        
        display_options()
        
        try:
            while True:
                try:
                    if msvcrt.kbhit():
                        key = msvcrt.getch()
                        
                        if key == b'\xe0':  # Special key prefix
                            key = msvcrt.getch()
                            if key == b'H':  # Up arrow
                                current_index = (current_index - 1) % len(options)
                                display_options()
                            elif key == b'P':  # Down arrow
                                current_index = (current_index + 1) % len(options)
                                display_options()
                        elif key == b'\r':  # Enter
                            return options[current_index].id
                        elif key == b'\x03':  # Ctrl+C
                            raise KeyboardInterrupt()
                            
                except (KeyboardInterrupt, EOFError):
                    return default
                    
        except Exception:
            # 如果方向键支持失败，回退到rich prompt
            return self._fallback_rich_select(message, options, default)

    def _unix_arrow_select(self, message: str, options: List[DownloadOption], default: str = "3") -> str:
        """Unix/Linux系统的方向键选择"""
        from rich.prompt import Prompt
        from rich.console import Console
        
        console = Console()
        
        # 找到默认选项的索引
        default_index = 0
        for i, opt in enumerate(options):
            if opt.id == default:
                default_index = i
                break
        
        current_index = default_index
        
        def display_options():
            console.clear()
            console.print(f"\n[bold cyan]{message}[/bold cyan]")
            console.print("[dim](使用 ↑/↓ 移动, Enter 确认)[/dim]\n")
            
            for i, opt in enumerate(options):
                if i == current_index:
                    console.print(f"▸ [bold green]{opt.name}[/bold green] - [dim]{opt.description}[/dim]")
                else:
                    console.print(f"  {opt.name} - [dim]{opt.description}[/dim]")
        
        display_options()
        
        import sys
        import tty
        import termios
        
        def get_key():
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(sys.stdin.fileno())
                ch = sys.stdin.read(1)
                if ch == '\x1b':  # ESC sequence
                    ch += sys.stdin.read(2)
                return ch
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        
        try:
            while True:
                try:
                    key = get_key()
                    
                    if key == '\x1b[A':  # Up arrow
                        current_index = (current_index - 1) % len(options)
                        display_options()
                    elif key == '\x1b[B':  # Down arrow
                        current_index = (current_index + 1) % len(options)
                        display_options()
                    elif key == '\r' or key == '\n':  # Enter
                        return options[current_index].id
                    elif key == '\x03':  # Ctrl+C
                        raise KeyboardInterrupt()
                        
                except (KeyboardInterrupt, EOFError):
                    return default
                    
        except Exception:
            # 如果方向键支持失败，回退到rich prompt
            return self._fallback_rich_select(message, options, default)

    def _fallback_rich_select(self, message: str, options: List[DownloadOption], default: str = "3") -> str:
        """Rich prompt回退方案"""
        from rich.prompt import Prompt
        
        self.print(f"\n[bold cyan]{message}[/bold cyan]")
        choice_map = {}
        for i, opt in enumerate(options):
            choice_map[str(i + 1)] = opt.id
            self.print(f"  [yellow]{i + 1}[/yellow]. {opt.name} - [dim]{opt.description}[/dim]")
        
        try:
            choice = Prompt.ask(
                f"请输入选项 [1-{len(options)}]",
                default=default,
                choices=list(choice_map.keys())
            )
            return choice_map[choice]
        except (EOFError, KeyboardInterrupt):
            return default

    def select_download_mode(self, options: List[DownloadOption], default: str = "3") -> str:
        if INQUIRER_AVAILABLE:
            choices = [
                {"name": f"{opt.name} - {opt.description}", "value": opt.id}
                for opt in options
            ]
            result = self._inquirer_select("选择下载方式:", choices, default=default)
            if result is not None:
                return result

        # 使用自定义方向键选择器
        return self._arrow_select("选择下载方式:", options, default)

    def show_progress_test(self, title: str, items: List[Any], test_func: Callable, timeout: float = 3.0) -> List[Any]:
        deadline = time.perf_counter() + timeout + 2.0
        results = []

        if self.use_tui:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                transient=True,
                console=self.console
            ) as progress:
                task = progress.add_task(f"{title}...", total=len(items))

                def test_with_progress(item):
                    result = test_func(item)
                    progress.advance(task)
                    return result

                with ThreadPoolExecutor(max_workers=8) as executor:
                    futures = {executor.submit(test_with_progress, item): item for item in items}
                    for future in as_completed(futures):
                        if time.perf_counter() > deadline:
                            break
                        try:
                            result = future.result(timeout=0.1)
                            if result:
                                results.append(result)
                        except Exception:
                            pass
                    for f in futures:
                        f.cancel()
        else:
            self.print(f"{title}...")
            with ThreadPoolExecutor(max_workers=8) as executor:
                futures = {executor.submit(test_func, item): item for item in items}
                for future in as_completed(futures):
                    if time.perf_counter() > deadline:
                        break
                    try:
                        result = future.result(timeout=0.1)
                        if result:
                            results.append(result)
                    except Exception:
                        pass
                for f in futures:
                    f.cancel()

        return results

    def _arrow_select_mirror(self, mirrors: List[MirrorInfo], title: str, default_index: int = 0) -> int:
        """使用方向键选择镜像"""
        if not self.use_tui or not self.console:
            # 回退到数字输入
            max_name_len = max(len(m.name) for m in mirrors) if mirrors else 10
            for i, mirror in enumerate(mirrors, 1):
                latency_str = f"{mirror.latency:.0f}ms" if mirror.latency else "N/A"
                self.print(f"  {i:>3}. {mirror.name:<{max_name_len}}  {latency_str:>7}")
            try:
                sel = input(f"\n请选择编号 [1-{len(mirrors)}] (默认 {default_index + 1}): ").strip()
            except (EOFError, KeyboardInterrupt):
                sel = str(default_index + 1)
            try:
                idx = int(sel) - 1 if sel else default_index
                if not (0 <= idx < len(mirrors)):
                    idx = default_index
            except ValueError:
                idx = default_index
            return idx

        # Windows系统检查
        if sys.platform == "win32":
            return self._windows_arrow_select_mirror(mirrors, title, default_index)
        else:
            return self._unix_arrow_select_mirror(mirrors, title, default_index)

    def _windows_arrow_select_mirror(self, mirrors: List[MirrorInfo], title: str, default_index: int = 0) -> int:
        """Windows系统的镜像方向键选择"""
        import msvcrt
        
        console = Console()
        current_index = default_index
        
        def display_mirrors():
            console.clear()
            console.print(f"\n[bold cyan]{title}[/bold cyan]")
            console.print("[dim](使用 ↑/↓ 移动, Enter 确认)[/dim]\n")
            
            # 显示表头
            console.print("  编号  镜像名称                        延迟")
            console.print("  ----  ----------------------------  ----")
            
            for i, mirror in enumerate(mirrors):
                latency_str = f"{mirror.latency:.0f}ms" if mirror.latency else "N/A"
                if i == current_index:
                    console.print(f"▸ {i+1:>4}  [bold green]{mirror.name:<28}[/bold green]  {latency_str:>7}")
                else:
                    console.print(f"  {i+1:>4}  {mirror.name:<28}  {latency_str:>7}")
        
        display_mirrors()
        
        try:
            while True:
                try:
                    if msvcrt.kbhit():
                        key = msvcrt.getch()
                        
                        if key == b'\xe0':  # Special key prefix
                            key = msvcrt.getch()
                            if key == b'H':  # Up arrow
                                current_index = (current_index - 1) % len(mirrors)
                                display_mirrors()
                            elif key == b'P':  # Down arrow
                                current_index = (current_index + 1) % len(mirrors)
                                display_mirrors()
                        elif key == b'\r':  # Enter
                            return current_index
                        elif key == b'\x03':  # Ctrl+C
                            raise KeyboardInterrupt()
                            
                except (KeyboardInterrupt, EOFError):
                    return default_index
                    
        except Exception:
            # 如果方向键支持失败，回退到rich prompt
            return self._fallback_rich_mirror_select(mirrors, title, default_index)

    def _unix_arrow_select_mirror(self, mirrors: List[MirrorInfo], title: str, default_index: int = 0) -> int:
        """Unix/Linux系统的镜像方向键选择"""
        console = Console()
        current_index = default_index
        
        def display_mirrors():
            console.clear()
            console.print(f"\n[bold cyan]{title}[/bold cyan]")
            console.print("[dim](使用 ↑/↓ 移动, Enter 确认)[/dim]\n")
            
            # 显示表头
            console.print("  编号  镜像名称                        延迟")
            console.print("  ----  ----------------------------  ----")
            
            for i, mirror in enumerate(mirrors):
                latency_str = f"{mirror.latency:.0f}ms" if mirror.latency else "N/A"
                if i == current_index:
                    console.print(f"▸ {i+1:>4}  [bold green]{mirror.name:<28}[/bold green]  {latency_str:>7}")
                else:
                    console.print(f"  {i+1:>4}  {mirror.name:<28}  {latency_str:>7}")
        
        display_mirrors()
        
        import sys
        import tty
        import termios
        
        def get_key():
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(sys.stdin.fileno())
                ch = sys.stdin.read(1)
                if ch == '\x1b':  # ESC sequence
                    ch += sys.stdin.read(2)
                return ch
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        
        try:
            while True:
                try:
                    key = get_key()
                    
                    if key == '\x1b[A':  # Up arrow
                        current_index = (current_index - 1) % len(mirrors)
                        display_mirrors()
                    elif key == '\x1b[B':  # Down arrow
                        current_index = (current_index + 1) % len(mirrors)
                        display_mirrors()
                    elif key == '\r' or key == '\n':  # Enter
                        return current_index
                    elif key == '\x03':  # Ctrl+C
                        raise KeyboardInterrupt()
                        
                except (KeyboardInterrupt, EOFError):
                    return default_index
                    
        except Exception:
            # 如果方向键支持失败，回退到rich prompt
            return self._fallback_rich_mirror_select(mirrors, title, default_index)

    def _fallback_rich_mirror_select(self, mirrors: List[MirrorInfo], title: str, default_index: int = 0) -> int:
        """Rich prompt镜像选择回退方案"""
        from rich.prompt import Prompt
        
        table = Table(title=title, show_header=True, header_style="bold magenta")
        table.add_column("编号", style="cyan", width=6)
        table.add_column("镜像名称", style="white")
        table.add_column("延迟", style="green", justify="right")
        for i, mirror in enumerate(mirrors, 1):
            latency_str = f"{mirror.latency:.0f}ms" if mirror.latency else "N/A"
            table.add_row(str(i), mirror.name, latency_str)
        self.console.print(table)
        
        try:
            choice = Prompt.ask(
                f"请选择镜像编号 [1-{len(mirrors)}]",
                default=str(default_index + 1)
            )
            idx = int(choice) - 1
            if 0 <= idx < len(mirrors):
                return idx
            self.print("[red]无效的选择，请重新输入[/red]")
            return default_index
        except (EOFError, KeyboardInterrupt, ValueError):
            return default_index

    def show_mirror_table(self, mirrors: List[MirrorInfo], title: str, default_index: int = 0) -> int:
        if INQUIRER_AVAILABLE:
            choices = []
            for i, mirror in enumerate(mirrors):
                latency_str = f"{mirror.latency:.0f}ms" if mirror.latency else "N/A"
                choices.append({"name": f"{mirror.name}  ({latency_str})", "value": i})
            result = self._inquirer_select(title, choices, default=default_index)
            if result is not None:
                return result

        # 使用自定义方向键选择器
        return self._arrow_select_mirror(mirrors, title, default_index)

    def show_download_progress(self, description: str, download_func: Callable, *args, **kwargs) -> Any:
        if not self.use_tui:
            self.print(f"{description}...")
            return download_func(*args, **kwargs)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            DownloadColumn(),
            TextColumn("•"),
            TimeRemainingColumn(),
            console=self.console
        ) as progress:
            def download_with_progress():
                task = progress.add_task(description, total=100)
                progress_callback = lambda downloaded, total, start: self._update_download_progress(
                    progress, task, downloaded, total, start
                )
                original_render = _render_download_progress
                _render_download_progress = progress_callback
                try:
                    result = download_func(*args, **kwargs)
                finally:
                    _render_download_progress = original_render
                progress.update(task, completed=100)
                return result
            return download_with_progress()

    def _update_download_progress(self, progress_obj, task_id, downloaded, total, start_ts):
        if total > 0:
            progress_obj.update(task_id, completed=int(downloaded * 100 / total))

    def show_installation_progress(self, title: str, install_func: Callable, *args, **kwargs) -> bool:
        if not self.use_tui:
            self.print(f"{title}...")
            try:
                install_func(*args, **kwargs)
                return True
            except Exception as e:
                self.print(f"安装失败: {e}")
                return False

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
            console=self.console
        ) as progress:
            task = progress.add_task(title, total=None)
            try:
                install_func(*args, **kwargs)
                progress.update(task, description=f"[green]{title} 完成[/green]")
                return True
            except Exception as e:
                progress.update(task, description=f"[red]{title} 失败: {e}[/red]")
                return False

    def show_status(self, message: str, status_type: str = "info"):
        if not self.use_tui:
            self.print(message)
            return
        style_map = {
            "info": "blue",
            "success": "green",
            "warning": "yellow",
            "error": "red"
        }
        style = style_map.get(status_type, "white")
        self.print(f"[{style}]{message}[/{style}]")

    def show_error(self, message: str, pause: bool = False):
        if self.use_tui:
            self.print(f"[red bold]错误: {message}[/red bold]")
        else:
            self.print(f"错误: {message}")
        if pause and getattr(sys, "frozen", False):
            try:
                input("按回车键退出...")
            except Exception:
                pass

    def confirm_action(self, message: str, default: bool = True) -> bool:
        if INQUIRER_AVAILABLE:
            try:
                return inquirer.confirm(message=message, default=default).execute()
            except Exception:
                pass
        if not self.use_tui:
            try:
                response = input(f"{message} ({'Y/n' if default else 'y/N'}): ").strip().lower()
                if not response:
                    return default
                return response in ['y', 'yes']
            except (EOFError, KeyboardInterrupt):
                return default
        return Confirm.ask(message, default=default)


_tui_instance = None

def get_tui() -> LauncherTUI:
    global _tui_instance
    if _tui_instance is None:
        _tui_instance = LauncherTUI()
    return _tui_instance

LAUNCHER_VERSION = "1.0.0"
APP_DIR_NAME = "FanqieNovelDownloader"
STATE_FILE = "launcher_state.json"
RUNTIME_DIR = "runtime"
BACKUP_DIR = "runtime_backup"
DEPS_STATE_FILE = "deps_state.json"

MIRROR_NODES = [
    "ghproxy.vip",
    "gh.llkk.cc",
    "gitproxy.click",
    "ghpr.cc",
    "github.tmby.shop",
    "cccccccccccccccccccccccccccccccccccccccccccccccccccc.cc",
    "ghproxy.net",
    "gh.5050net.cn",
    "gh.felicity.ac.cn",
    "github.dpik.top",
    "gh.monlor.com",
    "gh-proxy.com",
    "ghfile.geekertao.top",
    "gh.sixyin.com",
    "gh.927223.xyz",
    "ghp.keleyaa.com",
    "gh.fhjhy.top",
    "gh.ddlc.top",
    "github.chenc.dev",
    "gh.bugdey.us.kg",
    "ghproxy.cxkpro.top",
    "gh-proxy.net",
    "gh.xxooo.cf",
    "gh-proxy.top",
    "fastgit.cc",
    "gh.chjina.com",
    "github.xxlab.tech",
    "j.1win.ggff.net",
    "cdn.akaere.online",
    "ghproxy.cn",
    "gh.inkchills.cn",
    "github-proxy.memory-echoes.cn",
    "jiashu.1win.eu.org",
    "free.cn.eu.org",
    "gh.jasonzeng.dev",
    "gh.wsmdn.dpdns.org",
    "github.tbedu.top",
    "gitproxy.mrhjx.cn",
    "gh.dpik.top",
    "gp.zkitefly.eu.org",
    "github.ednovas.xyz",
    "tvv.tw",
    "github.geekery.cn",
    "ghpxy.hwinzniej.top",
    "j.1lin.dpdns.org",
    "git.669966.xyz",
    "github-proxy.teach-english.tech",
    "gitproxy.127731.xyz",
    "ghproxy.cfd",
    "gh.catmak.name",
    "ghm.078465.xyz",
    "ghproxy.imciel.com",
    "git.yylx.win",
    "ghf.xn--eqrr82bzpe.top",
    "ghfast.top",
    "cf.ghproxy.cc",
    "cdn.gh-proxy.com",
    "proxy.yaoyaoling.net",
    "gh.b52m.cn",
    "gh.noki.icu",
    "ghproxy.monkeyray.net",
    "gh.idayer.com",
]

_download_mode = "direct"
_mirror_domain = None
_session = requests.Session()

NODE_TEST_TIMEOUT_SECONDS = 3.0
NODE_TEST_CONNECT_TIMEOUT_SECONDS = 0.8
NODE_TEST_MAX_WORKERS = 120

PIP_INDEX_MIRRORS = [
    ("清华", "https://pypi.tuna.tsinghua.edu.cn/simple"),
    ("腾讯", "https://mirrors.cloud.tencent.com/pypi/simple"),
    ("阿里", "https://mirrors.aliyun.com/pypi/simple"),
    ("PyPI", "https://pypi.org/simple"),
]

_selected_pip_mirror_name = "PyPI"
_selected_pip_index_url = "https://pypi.org/simple"


def _write_error(message: str) -> None:
    try:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        stderr = sys.__stderr__ if hasattr(sys, "__stderr__") and sys.__stderr__ else sys.stderr
        stderr.write(formatted_message + "\n")
        stderr.flush()
    except Exception:
        pass


def _global_exception_handler(exc_type, exc_value, exc_tb):
    error = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    _write_error("\n" + "=" * 60)
    _write_error("Launcher 发生未捕获异常:")
    _write_error(error)
    _write_error("=" * 60)


sys.excepthook = _global_exception_handler


def _platform_name() -> str:
    if sys.platform == "win32":
        return "windows-x64"
    if sys.platform == "darwin":
        return "macos-x64"

    prefix = os.environ.get("PREFIX", "")
    if "com.termux" in prefix:
        return "termux-arm64"
    return "linux-x64"


def _base_dir() -> Path:
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            base = Path(local_app_data) / APP_DIR_NAME
            base.mkdir(parents=True, exist_ok=True)
            return base
    base = Path.home() / f".{APP_DIR_NAME.lower()}"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _state_path() -> Path:
    return _base_dir() / STATE_FILE


def _runtime_root() -> Path:
    return _base_dir() / RUNTIME_DIR


def _runtime_backup_root() -> Path:
    return _base_dir() / BACKUP_DIR


def _deps_state_path() -> Path:
    return _runtime_root() / DEPS_STATE_FILE


def _read_json(path: Path) -> Optional[Dict]:
    try:
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as file_obj:
            data = json.load(file_obj)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _write_json(path: Path, data: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as file_obj:
        json.dump(data, file_obj, ensure_ascii=False, indent=2)
    os.replace(temp_path, path)


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _format_size(size: float) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)}{unit}"
            return f"{value:.2f}{unit}"
        value /= 1024


def _render_download_progress(downloaded: int, total: int, start_ts: float) -> None:
    elapsed = max(time.time() - start_ts, 1e-6)
    speed = downloaded / elapsed

    if total > 0:
        ratio = min(downloaded / total, 1.0)
        bar_width = 30
        filled = int(ratio * bar_width)
        bar = "#" * filled + "-" * (bar_width - filled)
        print(
            f"\r下载 Runtime: [{bar}] {ratio * 100:6.2f}% "
            f"({_format_size(downloaded)}/{_format_size(total)}) "
            f"{_format_size(speed)}/s",
            end="",
            flush=True,
        )
        return

    print(
        f"\r下载 Runtime: {_format_size(downloaded)} {_format_size(speed)}/s",
        end="",
        flush=True,
    )


def _do_get(url: str, **kwargs) -> requests.Response:
    if _download_mode == "mirror" and _mirror_domain:
        mirror_url = f"https://{_mirror_domain}/{url}"
        try:
            resp = _session.get(mirror_url, **kwargs)
            if resp.status_code < 400:
                return resp
        except Exception:
            pass
    return _session.get(url, **kwargs)


def _fetch_latest_release(repo: str) -> Optional[Dict]:
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "FanqieLauncher",
    }
    response = _do_get(url, headers=headers, timeout=(3, 10))
    if response.status_code != 200:
        return None
    try:
        data = response.json()
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _get_asset_url(release_data: Dict, asset_name: str) -> Optional[str]:
    for asset in release_data.get("assets", []):
        if asset.get("name") == asset_name:
            return asset.get("browser_download_url")
    return None


def _load_platform_manifest(repo: str, platform: str) -> Optional[Dict]:
    release_data = _fetch_latest_release(repo)
    if not release_data:
        return None

    asset_name = f"runtime-manifest-{platform}.json"
    manifest_url = _get_asset_url(release_data, asset_name)
    if not manifest_url:
        return None

    headers = {"User-Agent": "FanqieLauncher"}
    response = _do_get(manifest_url, headers=headers, timeout=(3, 10))
    if response.status_code != 200:
        return None

    try:
        data = response.json()
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def _is_launcher_update_required(remote_manifest: Dict) -> bool:
    min_launcher_version = str(remote_manifest.get("min_launcher_version", "")).strip()
    if not min_launcher_version:
        return False
    return min_launcher_version != LAUNCHER_VERSION


def _is_runtime_up_to_date(local_state: Dict, remote_manifest: Dict) -> bool:
    if not local_state:
        return False

    local_ver = str(local_state.get("runtime_version", ""))
    local_sha = str(local_state.get("runtime_sha256", "")).lower()
    remote_ver = str(remote_manifest.get("runtime_version", ""))
    remote_sha = str(remote_manifest.get("runtime_archive_sha256", "")).lower()

    if local_ver != remote_ver:
        return False
    if local_sha != remote_sha:
        return False
    return (_runtime_root() / "main.py").exists()


def _download_runtime_archive(url: str, expected_sha256: str) -> bytes:
    headers = {"User-Agent": "FanqieLauncher"}
    with _session.get(url, headers=headers, timeout=(5, 30), stream=True) as response:
        response.raise_for_status()
        total = int(response.headers.get("Content-Length", "0") or "0")

        start_ts = time.time()
        last_refresh = 0.0
        downloaded = 0
        chunks = []
        hasher = hashlib.sha256()

        for chunk in response.iter_content(chunk_size=1024 * 256):
            if not chunk:
                continue

            chunks.append(chunk)
            hasher.update(chunk)
            downloaded += len(chunk)

            now = time.time()
            if now - last_refresh >= 0.08:
                _render_download_progress(downloaded, total, start_ts)
                last_refresh = now

        _render_download_progress(downloaded, total, start_ts)
        print()

        if total > 0 and downloaded != total:
            raise RuntimeError("Runtime 下载大小不完整")

        content = b"".join(chunks)

    current_sha = hasher.hexdigest()
    if current_sha != expected_sha256.lower():
        raise ValueError("Runtime 压缩包 sha256 校验失败")
    return content


def _replace_runtime_archive(content: bytes) -> None:
    runtime_root = _runtime_root()
    backup_root = _runtime_backup_root()
    temp_extract = Path(tempfile.mkdtemp(prefix="fanqie_runtime_"))

    try:
        zip_path = temp_extract / "runtime.zip"
        zip_path.write_bytes(content)
        with zipfile.ZipFile(zip_path, "r") as zip_obj:
            zip_obj.extractall(temp_extract / "new_runtime")

        new_runtime_root = temp_extract / "new_runtime"
        if not (new_runtime_root / "main.py").exists():
            if (new_runtime_root / "runtime" / "main.py").exists():
                new_runtime_root = new_runtime_root / "runtime"
            else:
                raise ValueError("Runtime 包结构无效，缺少 main.py")

        if backup_root.exists():
            shutil.rmtree(backup_root, ignore_errors=True)

        if runtime_root.exists():
            os.replace(runtime_root, backup_root)

        shutil.copytree(new_runtime_root, runtime_root)

        if backup_root.exists():
            shutil.rmtree(backup_root, ignore_errors=True)
    except Exception:
        if backup_root.exists() and not runtime_root.exists():
            os.replace(backup_root, runtime_root)
        raise
    finally:
        shutil.rmtree(temp_extract, ignore_errors=True)


def _runtime_venv_python() -> Path:
    runtime_venv = _runtime_root() / ".venv"
    if sys.platform == "win32":
        return runtime_venv / "Scripts" / "python.exe"
    return runtime_venv / "bin" / "python"


def _requirements_file_for_platform() -> Path:
    runtime_root = _runtime_root()
    if _platform_name() == "termux-arm64":
        termux_req = runtime_root / "config" / "requirements-termux.txt"
        if termux_req.exists():
            return termux_req

    default_req = runtime_root / "config" / "requirements.txt"
    if default_req.exists():
        return default_req

    root_req = runtime_root / "requirements.txt"
    if root_req.exists():
        return root_req

    raise FileNotFoundError("未找到 requirements 文件")


def _ensure_runtime_venv() -> Path:
    runtime_root = _runtime_root()
    py_path = _runtime_venv_python()
    
    _write_error(f"[DEBUG] 检查虚拟环境: {py_path}")
    
    if py_path.exists():
        # 验证虚拟环境是否可用
        try:
            result = subprocess.run(
                [str(py_path), "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                _write_error(f"[DEBUG] 虚拟环境可用: {result.stdout.strip()}")
                return py_path
            else:
                _write_error(f"[DEBUG] 虚拟环境不可用: {result.stderr}")
                _write_error("[DEBUG] 将重新创建虚拟环境")
        except Exception as e:
            _write_error(f"[DEBUG] 虚拟环境测试失败: {e}")
            _write_error("[DEBUG] 将重新创建虚拟环境")
        
        # 删除损坏的虚拟环境
        try:
            venv_path = runtime_root / ".venv"
            if venv_path.exists():
                shutil.rmtree(venv_path)
                _write_error("[DEBUG] 已删除损坏的虚拟环境")
        except Exception as e:
            _write_error(f"[DEBUG] 删除虚拟环境失败: {e}")

    print("正在创建 Runtime 虚拟环境...")
    _write_error(f"[DEBUG] 使用系统Python: {sys.executable}")
    _write_error(f"[DEBUG] 目标路径: {runtime_root / '.venv'}")
    
    try:
        result = subprocess.run(
            [sys.executable, "-m", "venv", str(runtime_root / ".venv")],
            check=True,
            cwd=str(runtime_root),
            capture_output=True,
            text=True
        )
        _write_error(f"[DEBUG] 虚拟环境创建成功")
    except subprocess.CalledProcessError as e:
        _write_error(f"[DEBUG] 虚拟环境创建失败: {e}")
        _write_error(f"[DEBUG] stdout: {e.stdout}")
        _write_error(f"[DEBUG] stderr: {e.stderr}")
        raise RuntimeError(f"虚拟环境创建失败: {e}")

    py_path = _runtime_venv_python()
    if not py_path.exists():
        raise RuntimeError("虚拟环境创建失败，未找到 Python 可执行文件")
    
    # 验证新创建的虚拟环境
    try:
        result = subprocess.run(
            [str(py_path), "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            _write_error(f"[DEBUG] 新虚拟环境验证成功: {result.stdout.strip()}")
        else:
            _write_error(f"[DEBUG] 新虚拟环境验证失败: {result.stderr}")
            raise RuntimeError("新虚拟环境不可用")
    except Exception as e:
        _write_error(f"[DEBUG] 新虚拟环境验证异常: {e}")
        raise RuntimeError(f"新虚拟环境验证失败: {e}")
    
    return py_path


def _test_pip_mirror_latency(mirror: Tuple[str, str]) -> Tuple[str, str, Optional[float]]:
    mirror_name, index_url = mirror
    test_url = index_url.rstrip("/") + "/pip/"
    try:
        start = time.perf_counter()
        _session.get(
            test_url,
            timeout=(NODE_TEST_CONNECT_TIMEOUT_SECONDS, NODE_TEST_TIMEOUT_SECONDS),
            allow_redirects=True,
        )
        return (mirror_name, index_url, (time.perf_counter() - start) * 1000)
    except Exception:
        return (mirror_name, index_url, None)


def _test_all_pip_mirrors() -> List[Tuple[str, str, float]]:
    print("正在测试 pip 镜像源延迟...")
    max_workers = max(1, min(len(PIP_INDEX_MIRRORS), 8))
    deadline = time.perf_counter() + NODE_TEST_TIMEOUT_SECONDS + 2.0
    available: List[Tuple[str, str, float]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_test_pip_mirror_latency, m): m for m in PIP_INDEX_MIRRORS}
        for future in concurrent.futures.as_completed(futures):
            if time.perf_counter() > deadline:
                break
            try:
                name, url, latency = future.result(timeout=0.1)
                if latency is not None:
                    available.append((name, url, latency))
            except Exception:
                pass
        for f in futures:
            f.cancel()
    available.sort(key=lambda item: item[2])
    return available


def _select_pip_mirror() -> None:
    global _selected_pip_mirror_name, _selected_pip_index_url

    # 获取TUI实例
    tui = get_tui() if RICH_AVAILABLE else None

    # 测试pip镜像
    if tui and tui.use_tui:
        available = tui.show_progress_test(
            "正在测试 pip 镜像源延迟",
            PIP_INDEX_MIRRORS,
            _test_pip_mirror_latency,
            timeout=NODE_TEST_TIMEOUT_SECONDS
        )
    else:
        available = _test_all_pip_mirrors()

    if not available:
        if tui:
            tui.show_status("pip 镜像测速失败，将使用官方 PyPI", "warning")
        else:
            print("pip 镜像测速失败，将使用官方 PyPI")
        _selected_pip_mirror_name = "PyPI"
        _selected_pip_index_url = "https://pypi.org/simple"
        return

    # 选择pip镜像
    if tui and tui.use_tui:
        mirror_infos = [MirrorInfo(name, url, latency) for name, url, latency in available]
        idx = tui.show_mirror_table(mirror_infos, "选择pip镜像源", default_index=0)
    else:
        max_name_len = max(len(name) for name, _, _ in available)
        for i, (name, url, latency) in enumerate(available, 1):
            print(f"  {i:>3}. {name:<{max_name_len}}  {latency:>7.0f}ms  {url}")

        try:
            sel = input(f"\n请选择 pip 镜像编号 [1-{len(available)}] (默认 1): ").strip()
        except (EOFError, KeyboardInterrupt):
            sel = ""

        try:
            idx = int(sel) - 1 if sel else 0
            if not (0 <= idx < len(available)):
                idx = 0
        except ValueError:
            idx = 0

    _selected_pip_mirror_name, _selected_pip_index_url, _ = available[idx]
    if tui:
        tui.show_status(f"已选择 pip 镜像: {_selected_pip_mirror_name}", "success")
    else:
        print(f"已选择 pip 镜像: {_selected_pip_mirror_name} ({_selected_pip_index_url})")


def _pip_install_with_mirrors(py_path: Path, install_args: List[str]) -> None:
    print(f"使用 {_selected_pip_mirror_name} 源安装依赖...")
    _write_error(f"[DEBUG] pip安装参数: {install_args}")
    _write_error(f"[DEBUG] 使用Python路径: {py_path}")
    
    try:
        cmd = [
            str(py_path),
            "-m",
            "pip",
            "install",
            "--index-url",
            _selected_pip_index_url,
            *install_args,
        ]
        _write_error(f"[DEBUG] 执行命令: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=300  # 5分钟超时
        )
        
        _write_error(f"[DEBUG] pip安装成功")
        if result.stdout:
            _write_error(f"[DEBUG] pip stdout: {result.stdout[-500:]}")  # 只显示最后500字符
        return
        
    except subprocess.CalledProcessError as exc:
        _write_error(f"[DEBUG] {_selected_pip_mirror_name} 源安装失败")
        _write_error(f"[DEBUG] 返回码: {exc.returncode}")
        if exc.stdout:
            _write_error(f"[DEBUG] stdout: {exc.stdout}")
        if exc.stderr:
            _write_error(f"[DEBUG] stderr: {exc.stderr}")
        
        if _selected_pip_index_url == "https://pypi.org/simple":
            raise RuntimeError(f"pip 安装失败: {exc}")

        print(f"{_selected_pip_mirror_name} 源安装失败，回退到官方 PyPI...")
        _write_error("[DEBUG] 尝试使用官方PyPI...")
        
        try:
            fallback_cmd = [
                str(py_path),
                "-m",
                "pip",
                "install",
                "--index-url",
                "https://pypi.org/simple",
                *install_args,
            ]
            _write_error(f"[DEBUG] 回退命令: {' '.join(fallback_cmd)}")
            
            result = subprocess.run(
                fallback_cmd,
                check=True,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            _write_error(f"[DEBUG] PyPI回退安装成功")
            if result.stdout:
                _write_error(f"[DEBUG] PyPI stdout: {result.stdout[-500:]}")
                
        except subprocess.CalledProcessError as exc2:
            _write_error(f"[DEBUG] PyPI回退也失败")
            _write_error(f"[DEBUG] 返回码: {exc2.returncode}")
            if exc2.stdout:
                _write_error(f"[DEBUG] stdout: {exc2.stdout}")
            if exc2.stderr:
                _write_error(f"[DEBUG] stderr: {exc2.stderr}")
            raise RuntimeError(f"pip 安装失败（包括PyPI回退）: {exc2}")
            
    except subprocess.TimeoutExpired as exc:
        _write_error(f"[DEBUG] pip安装超时: {exc}")
        raise RuntimeError(f"pip 安装超时: {exc}")
    except Exception as exc:
        _write_error(f"[DEBUG] pip安装异常: {exc}")
        raise RuntimeError(f"pip 安装异常: {exc}")


def _ensure_runtime_dependencies() -> None:
    runtime_root = _runtime_root()
    if not runtime_root.exists():
        raise RuntimeError("Runtime 不存在，无法安装依赖")

    tui = get_tui() if RICH_AVAILABLE else None

    requirements_path = _requirements_file_for_platform()
    requirements_bytes = requirements_path.read_bytes()
    requirements_sha = _sha256_bytes(requirements_bytes)

    deps_state = _read_json(_deps_state_path()) or {}
    if (
        deps_state.get("requirements_sha256") == requirements_sha
        and deps_state.get("requirements_file") == str(requirements_path.relative_to(runtime_root))
        and _runtime_venv_python().exists()
    ):
        if tui:
            tui.show_status("依赖已就绪", "success")
        else:
            print("✓ 依赖已就绪")
        return

    py_path = _ensure_runtime_venv()

    if tui:
        tui.show_status("正在安装 Runtime 依赖...", "info")
    else:
        print("正在安装 Runtime 依赖...")
    
    _pip_install_with_mirrors(py_path, ["--upgrade", "pip"])
    _pip_install_with_mirrors(py_path, ["-r", str(requirements_path)])

    _write_json(
        _deps_state_path(),
        {
            "requirements_file": str(requirements_path.relative_to(runtime_root)),
            "requirements_sha256": requirements_sha,
            "python_version": platform.python_version(),
            "updated_at": int(time.time()),
        },
    )
    
    if tui:
        tui.show_status("Runtime 依赖安装完成", "success")
    else:
        print("✓ Runtime 依赖安装完成")


def _test_node_latency(domain: str) -> Tuple[str, Optional[float]]:
    try:
        start = time.perf_counter()
        _session.head(
            f"https://{domain}",
            timeout=(NODE_TEST_CONNECT_TIMEOUT_SECONDS, NODE_TEST_TIMEOUT_SECONDS),
            allow_redirects=False,
        )
        return (domain, (time.perf_counter() - start) * 1000)
    except Exception:
        return (domain, None)


def _test_all_nodes() -> List[Tuple[str, float]]:
    print("正在测试镜像节点延迟...")
    max_workers = max(1, min(len(MIRROR_NODES), NODE_TEST_MAX_WORKERS))
    deadline = time.perf_counter() + NODE_TEST_TIMEOUT_SECONDS + 2.0
    available: List[Tuple[str, float]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_test_node_latency, d): d for d in MIRROR_NODES}
        for future in concurrent.futures.as_completed(futures):
            if time.perf_counter() > deadline:
                break
            try:
                domain, latency = future.result(timeout=0.1)
                if latency is not None:
                    available.append((domain, latency))
            except Exception:
                pass
        for f in futures:
            f.cancel()
    available.sort(key=lambda x: x[1])
    return available


def _select_download_mode() -> None:
    global _download_mode, _mirror_domain

    # 获取TUI实例
    tui = get_tui() if RICH_AVAILABLE else None

    # 定义下载选项
    options = [
        DownloadOption("1", "直连 GitHub", "不使用代理，直接连接GitHub"),
        DownloadOption("2", "直连 GitHub", "使用系统代理"),
        DownloadOption("3", "使用镜像节点", "通过GitHub镜像节点下载")
    ]

    if tui and tui.use_tui:
        # TUI模式
        choice = tui.select_download_mode(options, default="3")
    else:
        # 传统命令行模式
        print("\n请选择下载方式:")
        for i, opt in enumerate(options, 1):
            print(f"  {i}. {opt.name} - {opt.description}")

        try:
            choice = input("请输入选项 [1/2/3] (默认 3): ").strip()
        except (EOFError, KeyboardInterrupt):
            choice = "3"

    if choice == "1":
        _download_mode = "direct"
        _session.trust_env = False
        return

    if choice == "2":
        _download_mode = "proxy"
        _session.trust_env = True
        return

    _download_mode = "mirror"
    _session.trust_env = False

    # 测试镜像节点
    if tui and tui.use_tui:
        available = tui.show_progress_test(
            "正在测试镜像节点延迟",
            MIRROR_NODES,
            _test_node_latency,
            timeout=NODE_TEST_TIMEOUT_SECONDS
        )
    else:
        available = _test_all_nodes()

    if not available:
        if tui:
            tui.show_status("所有镜像节点均不可用，将使用直连", "warning")
        else:
            print("所有镜像节点均不可用，将使用直连")
        _download_mode = "direct"
        return

    # 选择镜像节点
    if tui and tui.use_tui:
        mirror_infos = [MirrorInfo(domain, f"https://{domain}", latency) for domain, latency in available]
        idx = tui.show_mirror_table(mirror_infos, "选择镜像节点", default_index=0)
    else:
        max_len = max(len(d) for d, _ in available)
        for i, (domain, latency) in enumerate(available, 1):
            print(f"  {i:>3}. {domain:<{max_len}}  {latency:>7.0f}ms")

        try:
            sel = input(f"\n请选择节点编号 [1-{len(available)}] (默认 1): ").strip()
        except (EOFError, KeyboardInterrupt):
            sel = "1"

        try:
            idx = int(sel) - 1 if sel else 0
            if not (0 <= idx < len(available)):
                idx = 0
        except ValueError:
            idx = 0

    _mirror_domain = available[idx][0]
    if tui:
        tui.show_status(f"已选择镜像: {_mirror_domain}", "info")
    else:
        print(f"已选择镜像: {_mirror_domain}")


def _ensure_runtime(repo: str) -> None:
    platform = _platform_name()
    state_path = _state_path()
    local_state = _read_json(state_path) or {}
    
    # 获取TUI实例
    tui = get_tui() if RICH_AVAILABLE else None

    remote_manifest = _load_platform_manifest(repo, platform)
    if not remote_manifest:
        runtime_root = _runtime_root()
        runtime_ok = (
            (runtime_root / "main.py").exists()
            and (runtime_root / "utils" / "runtime_bootstrap.py").exists()
            and (runtime_root / "config" / "config.py").exists()
        )
        if runtime_ok:
            if tui:
                tui.show_status("无法获取远程 Runtime 清单，使用本地 Runtime", "warning")
            else:
                print("无法获取远程 Runtime 清单，使用本地 Runtime")
            return
        raise RuntimeError(
            "无法获取远程 Runtime 清单，且本地 Runtime 不可用或不完整。\n"
            f"请检查网络连接，或删除 {runtime_root} 目录后重试"
        )

    if _is_runtime_up_to_date(local_state, remote_manifest):
        if tui:
            tui.show_status("Runtime 已是最新", "success")
        else:
            print("✓ Runtime 已是最新")
        return

    if _is_launcher_update_required(remote_manifest):
        raise RuntimeError(
            "远程运行时要求更高版本启动器，请更新 Launcher 后重试"
        )

    runtime_url = str(remote_manifest.get("runtime_archive_url", ""))
    runtime_sha = str(remote_manifest.get("runtime_archive_sha256", "")).lower()
    runtime_version = str(remote_manifest.get("runtime_version", ""))
    if not runtime_url or len(runtime_sha) != 64:
        raise RuntimeError("远程 Runtime 清单缺少必要字段")

    if tui:
        tui.show_status(f"正在更新 Runtime: {runtime_version}", "info")
    else:
        print(f"正在更新 Runtime: {runtime_version}")
    
    # 下载Runtime
    if _download_mode == "mirror" and _mirror_domain:
        mirror_url = f"https://{_mirror_domain}/{runtime_url}"
        try:
            if tui and tui.use_tui:
                archive_bytes = tui.show_download_progress(
                    f"下载 Runtime ({runtime_version})",
                    _download_runtime_archive,
                    mirror_url, runtime_sha
                )
            else:
                archive_bytes = _download_runtime_archive(mirror_url, runtime_sha)
        except Exception:
            if tui:
                tui.show_status("镜像下载失败，尝试直连...", "warning")
            else:
                print("\n镜像下载失败，尝试直连...")
            if tui and tui.use_tui:
                archive_bytes = tui.show_download_progress(
                    f"下载 Runtime ({runtime_version})",
                    _download_runtime_archive,
                    runtime_url, runtime_sha
                )
            else:
                archive_bytes = _download_runtime_archive(runtime_url, runtime_sha)
    else:
        if tui and tui.use_tui:
            archive_bytes = tui.show_download_progress(
                f"下载 Runtime ({runtime_version})",
                _download_runtime_archive,
                runtime_url, runtime_sha
            )
        else:
            archive_bytes = _download_runtime_archive(runtime_url, runtime_sha)
    
    _replace_runtime_archive(archive_bytes)

    _write_json(
        state_path,
        {
            "launcher_version": LAUNCHER_VERSION,
            "platform": platform,
            "runtime_version": runtime_version,
            "runtime_sha256": runtime_sha,
            "runtime_updated_at": int(__import__("time").time()),
        },
    )
    
    if tui:
        tui.show_status("Runtime 更新完成", "success")
    else:
        print("✓ Runtime 更新完成")


def _launch_runtime() -> None:
    runtime_root = _runtime_root()
    runtime_main = runtime_root / "main.py"
    if not runtime_main.exists():
        raise FileNotFoundError(f"未找到 Runtime 入口: {runtime_main}")

    critical_modules = [
        runtime_root / "utils" / "__init__.py",
        runtime_root / "utils" / "runtime_bootstrap.py",
        runtime_root / "config" / "__init__.py",
        runtime_root / "config" / "config.py",
        runtime_root / "core" / "__init__.py",
    ]
    missing = [str(p) for p in critical_modules if not p.exists()]
    if missing:
        raise FileNotFoundError(
            "Runtime 不完整，缺少关键文件:\n"
            + "\n".join(f"  - {m}" for m in missing)
            + f"\n请删除 {runtime_root} 目录后重新运行启动器以重新下载 Runtime"
        )

    os.environ["FANQIE_RUNTIME_BASE"] = str(runtime_root)
    sys.path.insert(0, str(runtime_root))

    runtime_venv = runtime_root / ".venv"
    if runtime_venv.exists():
        if sys.platform == "win32":
            if (runtime_venv / "Lib" / "site-packages").exists():
                sys.path.insert(0, str(runtime_venv / "Lib" / "site-packages"))
        else:
            for candidate in (runtime_venv / "lib").glob("python*/site-packages"):
                sys.path.insert(0, str(candidate))

    namespace = {
        "__name__": "__main__",
        "__file__": str(runtime_main),
    }
    code = compile(runtime_main.read_text(encoding="utf-8"), str(runtime_main), "exec")
    exec(code, namespace, namespace)

def main() -> None:
    # 获取TUI实例
    tui = get_tui() if RICH_AVAILABLE else None
    
    # 显示启动器头部
    if tui:
        tui.show_header()
    else:
        print("=" * 50)
        print("番茄小说下载器 启动器")
        print("=" * 50)
    
    # 准备调试信息
    debug_info = {
        "Python版本": sys.version,
        "Python路径": sys.executable,
        "平台": sys.platform,
        "是否打包": getattr(sys, 'frozen', False),
        "工作目录": os.getcwd(),
        "TUI状态": "启用" if (tui and tui.use_tui) else "禁用"
    }
    
    if getattr(sys, 'frozen', False):
        if hasattr(sys, '_MEIPASS'):
            debug_info["_MEIPASS"] = sys._MEIPASS
        debug_info["sys.executable"] = sys.executable
    
    debug_info.update({
        "基础目录": str(_base_dir()),
        "运行时目录": str(_runtime_root()),
        "状态文件": str(_state_path())
    })
    
    # 显示调试信息
    if tui:
        tui.show_debug_info(debug_info)
    else:
        _write_error("[DEBUG] ========== 启动环境信息 ==========")
        for key, value in debug_info.items():
            _write_error(f"[DEBUG] {key}: {value}")
        _write_error("[DEBUG] ======================================")

    # 获取仓库配置，使用统一的管理模块
    repo, repo_source = get_effective_repo()
    
    if tui:
        tui.show_debug_info({"使用仓库": repo, "仓库来源": repo_source})
    else:
        _write_error(f"[DEBUG] 使用仓库: {repo}")
        _write_error(f"[DEBUG] 仓库来源: {repo_source}")
    
    try:
        # 使用TUI增强的各个步骤
        if tui:
            tui.show_status("开始初始化启动器...", "info")
        
        _select_download_mode()
        _select_pip_mirror()
        
        # Runtime检查和更新
        if tui:
            tui.show_status("检查Runtime更新...", "info")
        _ensure_runtime(repo)
        
        # 依赖安装
        if tui:
            success = tui.show_installation_progress(
                "安装Runtime依赖",
                _ensure_runtime_dependencies
            )
            if not success:
                tui.show_status("依赖安装失败，但继续尝试启动...", "warning")
        else:
            _ensure_runtime_dependencies()
        
        # 启动Runtime
        if tui:
            tui.show_status("启动应用程序...", "info")
        _launch_runtime()
        
    except Exception as error:
        if tui:
            tui.show_error(f"启动失败: {error}", pause=True)
        else:
            _write_error(f"启动失败: {error}")
            _write_error(f"[DEBUG] 异常类型: {type(error).__name__}")
            
            # 添加更详细的异常信息
            import traceback
            exc_type, exc_value, exc_tb = sys.exc_info()
            if exc_type and exc_value and exc_tb:
                _write_error("[DEBUG] ========== 详细异常信息 ==========")
                tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)
                for line in tb_lines:
                    _write_error(f"[DEBUG] {line.rstrip()}")
                _write_error("[DEBUG] ======================================")
            
            if getattr(sys, "frozen", False):
                try:
                    _write_error("按回车键退出...")
                    input()
                except Exception:
                    pass
        raise


if __name__ == "__main__":
    main()
