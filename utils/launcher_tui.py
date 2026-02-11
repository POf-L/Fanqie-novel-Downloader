# -*- coding: utf-8 -*-
"""TUI组件 - 为启动器提供可视化界面（支持方向键交互选择）"""

import sys
import time
import threading
from typing import List, Optional, Callable, Tuple, Any
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

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

    def select_download_mode(self, options: List[DownloadOption], default: str = "3") -> str:
        if INQUIRER_AVAILABLE:
            choices = [
                {"name": f"{opt.name} - {opt.description}", "value": opt.id}
                for opt in options
            ]
            result = self._inquirer_select("选择下载方式:", choices, default=default)
            if result is not None:
                return result

        if not self.use_tui:
            print("\n请选择下载方式:")
            for i, opt in enumerate(options, 1):
                print(f"  {i}. {opt.name} - {opt.description}")
            try:
                choice = input(f"请输入选项 [1-{len(options)}] (默认 {default}): ").strip()
            except (EOFError, KeyboardInterrupt):
                choice = default
            if choice.isdigit() and 1 <= int(choice) <= len(options):
                return options[int(choice) - 1].id
            return default

        self.print("\n[bold cyan]选择下载方式[/bold cyan]")
        choice_map = {}
        for i, opt in enumerate(options):
            choice_map[str(i + 1)] = opt.id
            self.print(f"  [yellow]{i + 1}[/yellow]. {opt.name} - [dim]{opt.description}[/dim]")
        while True:
            try:
                choice = Prompt.ask(
                    f"请输入选项 [1-{len(options)}]",
                    default=default,
                    choices=list(choice_map.keys())
                )
                return choice_map[choice]
            except (EOFError, KeyboardInterrupt):
                return default

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

    def show_mirror_table(self, mirrors: List[MirrorInfo], title: str, default_index: int = 0) -> int:
        if INQUIRER_AVAILABLE:
            choices = []
            for i, mirror in enumerate(mirrors):
                latency_str = f"{mirror.latency:.0f}ms" if mirror.latency else "N/A"
                choices.append({"name": f"{mirror.name}  ({latency_str})", "value": i})
            result = self._inquirer_select(title, choices, default=default_index)
            if result is not None:
                return result

        if not self.use_tui:
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

        table = Table(title=title, show_header=True, header_style="bold magenta")
        table.add_column("编号", style="cyan", width=6)
        table.add_column("镜像名称", style="white")
        table.add_column("延迟", style="green", justify="right")
        for i, mirror in enumerate(mirrors, 1):
            latency_str = f"{mirror.latency:.0f}ms" if mirror.latency else "N/A"
            table.add_row(str(i), mirror.name, latency_str)
        self.console.print(table)
        while True:
            try:
                choice = Prompt.ask(
                    f"请选择镜像编号 [1-{len(mirrors)}]",
                    default=str(default_index + 1)
                )
                idx = int(choice) - 1
                if 0 <= idx < len(mirrors):
                    return idx
                self.print("[red]无效的选择，请重新输入[/red]")
            except (EOFError, KeyboardInterrupt, ValueError):
                return default_index

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
                import launcher
                # 在可能抛出的代码之前先保存全局回调，避免 finally 中访问时未定义
                original_render = launcher._render_download_progress
                task = progress.add_task(description, total=100)
                progress_callback = lambda downloaded, total, start: self._update_download_progress(
                    progress, task, downloaded, total, start
                )
                launcher._render_download_progress = progress_callback
                try:
                    result = download_func(*args, **kwargs)
                finally:
                    launcher._render_download_progress = original_render
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
