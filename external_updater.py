#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
外部更新脚本 - 独立处理所有更新操作
当主程序退出后，由这个脚本接管所有更新流程
"""

import sys
import os
import time
import tempfile
import json
import platform
import subprocess
import shutil
import stat
from pathlib import Path

# 延迟导入 requests，避免模块导入失败
_requests = None
# 目标可执行文件路径（由主程序传入）
CURRENT_EXE_PATH = None

def _get_requests():
    """延迟导入并获取 requests 模块"""
    global _requests
    if _requests is None:
        try:
            import requests as req
            _requests = req
        except ImportError as e:
            print(f"[Updater] 错误: requests 库未安装")
            print("[Updater] 请运行: pip install requests")
            raise ImportError(f"requests 模块未安装: {e}")
    return _requests

# 添加项目路径以导入内部模块
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

try:
    from updater import AutoUpdater
    from config import __github_repo__, __version__, CONFIG
except ImportError as e:
    print(f"[Updater] 导入失败: {e}")
    sys.exit(1)


def log_message(message, level="INFO"):
    """记录日志消息（同时写入临时 update.log 以便 GUI 检测状态）"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] [{level}] {message}"
    print(line)
    # 同步写入 GUI 解析的日志文件（与 updater._create_update_log 一致）
    try:
        log_file = os.path.join(tempfile.gettempdir(), 'update.log')
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        # 日志写入失败不影响主流程
        pass


def wait_for_process_exit(pid, timeout=30):
    """等待指定进程退出"""
    log_message(f"等待主程序(PID: {pid})退出...")
    
    for i in range(timeout * 2):  # 每0.5秒检查一次
        try:
            if platform.system() == 'Windows':
                # Windows: 使用OpenProcess检查进程是否存在
                import ctypes
                kernel32 = ctypes.windll.kernel32
                SYNCHRONIZE = 0x00100000
                process = kernel32.OpenProcess(SYNCHRONIZE, 0, pid)
                if process == 0:
                    log_message("主程序已退出")
                    # Windows需要额外延迟以确保文件锁完全释放
                    log_message("等待文件锁释放...")
                    time.sleep(2)
                    return True
                kernel32.CloseHandle(process)
            else:
                # Unix: 发送信号0检查进程
                os.kill(pid, 0)
        except (OSError, ProcessLookupError):
            log_message("主程序已退出")
            # 额外延迟以确保所有资源被释放
            log_message("等待文件锁释放...")
            time.sleep(1)
            return True
        
        time.sleep(0.5)
    
    log_message(f"等待超时，继续执行更新", "WARNING")
    # 即使超时也等待一下，给文件锁释放的机会
    time.sleep(2)
    return False


def get_current_exe_path():
    """获取待更新的目标可执行文件路径（由主程序传入）。"""
    global CURRENT_EXE_PATH
    if CURRENT_EXE_PATH and os.path.exists(CURRENT_EXE_PATH):
        return CURRENT_EXE_PATH
    # 回退：尽力推断，但不可靠
    try:
        if getattr(sys, 'frozen', False):
            return sys.executable
    except Exception:
        pass
    return os.path.abspath(sys.argv[0])


def backup_current_exe():
    """备份当前可执行文件"""
    current_exe = get_current_exe_path()
    backup_path = current_exe + ".backup"

    if os.path.exists(current_exe):
        log_message(f"创建备份: {backup_path}")
        shutil.copy2(current_exe, backup_path)
        return backup_path
    return None


def restore_backup(backup_path):
    """从备份恢复文件"""
    if backup_path and os.path.exists(backup_path):
        current_exe = get_current_exe_path()
        log_message(f"从备份恢复: {backup_path}")
        shutil.copy2(backup_path, current_exe)
        return True
    return False


def cleanup_backup(backup_path):
    """清理备份文件"""
    if backup_path and os.path.exists(backup_path):
        try:
            os.remove(backup_path)
            log_message(f"清理备份文件: {backup_path}")
        except Exception as e:
            log_message(f"清理备份文件失败: {e}", "WARNING")


def is_file_locked(filepath):
    """检测文件是否被锁定（Windows专用）"""
    if platform.system() != 'Windows':
        return False
    
    if not os.path.exists(filepath):
        return False
    
    try:
        # 尝试以独占写入模式打开文件
        with open(filepath, 'a') as f:
            pass
        return False
    except (IOError, OSError):
        return True


def wait_for_file_unlock(filepath, timeout=10):
    """等待文件解锁"""
    if not os.path.exists(filepath):
        return True
    
    log_message(f"检查文件锁状态: {filepath}")
    
    for i in range(timeout * 2):  # 每0.5秒检查一次
        if not is_file_locked(filepath):
            log_message("文件已解锁")
            return True
        
        if i == 0:
            log_message("文件被锁定，等待释放...")
        time.sleep(0.5)
    
    log_message("文件锁等待超时", "WARNING")
    return False


class MultiThreadDownloader:
    """多线程分段下载器（支持 Range）。"""
    def __init__(self, url: str, dest: str, headers: dict | None = None, threads: int = 6):
        self.url = url
        self.dest = dest
        self.headers = headers or {}
        self.threads = max(2, int(threads))
        self._stop = False

    def _supports_range(self, requests):
        try:
            resp = requests.head(self.url, headers=self.headers, allow_redirects=True, timeout=15)
            accept_ranges = resp.headers.get('Accept-Ranges', '')
            cl = int(resp.headers.get('Content-Length', '0') or 0)
            return ('bytes' in accept_ranges.lower()) and cl > 0, cl
        except Exception:
            # HEAD 失败，尝试 GET
            try:
                resp = requests.get(self.url, headers=self.headers, stream=True, timeout=15)
                cl = int(resp.headers.get('Content-Length', '0') or 0)
                accept_ranges = resp.headers.get('Accept-Ranges', '')
                resp.close()
                return ('bytes' in accept_ranges.lower()) and cl > 0, cl
            except Exception:
                return False, 0

    def download(self) -> bool:
        requests = _get_requests()
        support, total = self._supports_range(requests)
        if not support or total <= 0:
            # 回退到单线程
            return self._single_thread_download(requests)

        # 分段范围
        part_size = max(1, total // self.threads)
        ranges = []
        start = 0
        for i in range(self.threads):
            end = (start + part_size - 1) if i < self.threads - 1 else (total - 1)
            ranges.append((start, end))
            start = end + 1

        temp_dir = tempfile.gettempdir()
        part_files = [os.path.join(temp_dir, f"{os.path.basename(self.dest)}.part{i}") for i in range(self.threads)]

        import threading
        errs: list[Exception] = []

        def worker(idx: int, byte_range: tuple[int, int]):
            nonlocal errs
            if self._stop:
                return
            s, e = byte_range
            hdrs = dict(self.headers)
            hdrs['Range'] = f'bytes={s}-{e}'
            try:
                with requests.get(self.url, headers=hdrs, stream=True, timeout=60) as resp:
                    resp.raise_for_status()
                    with open(part_files[idx], 'wb') as f:
                        for chunk in resp.iter_content(chunk_size=8192):
                            if self._stop:
                                return
                            if chunk:
                                f.write(chunk)
            except Exception as ex:
                errs.append(ex)
                self._stop = True

        threads = []
        for i, r in enumerate(ranges):
            t = threading.Thread(target=worker, args=(i, r), daemon=True)
            t.start()
            threads.append(t)
        for t in threads:
            t.join()

        if errs or self._stop:
            for pf in part_files:
                try:
                    if os.path.exists(pf):
                        os.remove(pf)
                except Exception:
                    pass
            return False

        # 合并
        try:
            with open(self.dest, 'wb') as out:
                for pf in part_files:
                    with open(pf, 'rb') as p:
                        shutil.copyfileobj(p, out)
            # 校验大小
            if os.path.getsize(self.dest) != total:
                raise IOError("合并后文件大小与预期不符")
        finally:
            for pf in part_files:
                try:
                    if os.path.exists(pf):
                        os.remove(pf)
                except Exception:
                    pass
        return True

    def _single_thread_download(self, requests) -> bool:
        try:
            with requests.get(self.url, headers=self.headers, stream=True, timeout=60) as resp:
                resp.raise_for_status()
                with open(self.dest, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
            return True
        except Exception:
            return False


def download_update_file(update_info):
    """下载更新文件（优先多线程分段）。"""
    try:
        log_message("开始下载更新文件...")

        # 创建更新器实例，仅用于选择资产
        updater = AutoUpdater(__github_repo__, __version__)

        # 选择合适的下载资源
        asset = updater._get_platform_asset(update_info['assets'])
        if not asset:
            log_message("没有找到适合当前平台的更新文件", "ERROR")
            return None

        log_message(f"选择下载文件: {asset['name']}")

        # 创建临时文件
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, asset['name'])

        # 下载文件（带 Range 支持）
        headers = {
            'User-Agent': 'Tomato-Novel-Downloader',
            'Accept': 'application/octet-stream'
        }
        token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
        if token:
            headers['Authorization'] = f'Bearer {token}'

        dl = MultiThreadDownloader(asset['download_url'], file_path, headers=headers, threads=min(8, max(4, (os.cpu_count() or 4))))
        ok = dl.download()
        if not ok:
            log_message("多线程下载失败，回退单线程...", "WARNING")
            # 回退单线程
            requests = _get_requests()
            with requests.get(asset['download_url'], headers=headers, stream=True, timeout=60) as resp:
                resp.raise_for_status()
                with open(file_path, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

        log_message(f"下载完成: {file_path}")
        return file_path

    except Exception as e:
        log_message(f"下载失败: {e}", "ERROR")
        return None


def install_update_windows(update_file):
    """Windows 平台安装更新"""
    backup_path = None
    try:
        current_exe = get_current_exe_path()
        log_message("开始安装更新 (Windows)...")

        # 备份当前文件
        backup_path = backup_current_exe()
        if not backup_path:
            log_message("创建备份失败", "ERROR")
            return False

        # 等待文件解锁
        if not wait_for_file_unlock(current_exe, timeout=15):
            log_message("文件锁等待超时，尝试强制替换", "WARNING")

        # 尝试去除只读属性
        try:
            os.chmod(current_exe, stat.S_IWRITE | stat.S_IREAD)
        except Exception:
            pass

        # 替换文件（多种策略，带指数退避重试）
        log_message(f"替换文件: {current_exe}")
        max_retries = 30
        success = False
        
        for i in range(max_retries):
            try:
                # 策略1: 直接复制覆盖
                shutil.copy2(update_file, current_exe)
                success = True
                break
            except PermissionError as e:
                if i == 0:
                    log_message(f"文件被锁定，等待释放后重试: {e}")
                # 指数退避，但最大不超过2秒
                wait_time = min(0.5 * (1.5 ** (i // 5)), 2.0)
                time.sleep(wait_time)
            except Exception as e:
                if i == 0:
                    log_message(f"文件操作失败，重试中: {e}")
                time.sleep(0.5)
        
        if not success:
            # 策略2: 删除后复制
            log_message("尝试删除-复制策略...")
            try:
                # 尝试移除只读属性
                try:
                    os.chmod(current_exe, stat.S_IWRITE)
                except Exception:
                    pass
                
                # 删除原文件
                for attempt in range(5):
                    try:
                        os.remove(current_exe)
                        break
                    except Exception as e:
                        if attempt == 4:
                            raise
                        time.sleep(0.5)
                
                # 等待一下确保删除完成
                time.sleep(0.5)
                
                # 复制新文件
                shutil.copy2(update_file, current_exe)
                success = True
            except Exception as e2:
                log_message(f"删除-复制策略失败: {e2}", "ERROR")
        
        if success:
            log_message("更新安装成功")
            # 清理备份
            cleanup_backup(backup_path)
            return True
        else:
            log_message("所有替换策略均失败", "ERROR")
            # 恢复备份
            restore_backup(backup_path)
            return False

    except Exception as e:
        log_message(f"安装失败: {e}", "ERROR")
        # 尝试恢复备份
        if backup_path:
            restore_backup(backup_path)
        return False


def install_update_unix(update_file):
    """Unix 平台安装更新"""
    backup_path = None
    temp_extract_dir = None
    try:
        current_exe = get_current_exe_path()
        current_dir = os.path.dirname(current_exe)
        log_message("开始安装更新 (Unix)...")

        # 如果是压缩包，解压到临时目录
        if update_file.endswith('.zip'):
            import zipfile
            temp_extract_dir = os.path.join(tempfile.gettempdir(), 'update_extract')
            os.makedirs(temp_extract_dir, exist_ok=True)

            log_message("解压更新文件...")
            with zipfile.ZipFile(update_file, 'r') as zip_ref:
                zip_ref.extractall(temp_extract_dir)
        elif update_file.endswith('.tar.gz') or update_file.endswith('.tgz'):
            import tarfile
            temp_extract_dir = os.path.join(tempfile.gettempdir(), 'update_extract')
            os.makedirs(temp_extract_dir, exist_ok=True)
            log_message("解压tarball更新文件...")
            with tarfile.open(update_file, 'r:gz') as tar:
                tar.extractall(temp_extract_dir)
        elif update_file.lower().endswith('.appimage'):
            # AppImage 单文件直接覆盖
            temp_extract_dir = None
        else:
            temp_extract_dir = None

        update_exe = update_file
        if temp_extract_dir:
            # 查找主要可执行文件（使用当前可执行文件名匹配）
            exe_name = os.path.basename(current_exe)
            candidates = []
            for root, dirs, files in os.walk(temp_extract_dir):
                for file in files:
                    if file == exe_name or exe_name in file:
                        candidates.append(os.path.join(root, file))
            if not candidates:
                log_message("未找到匹配的可执行文件", "ERROR")
                return False
            update_exe = candidates[0]

        # 备份当前文件
        backup_path = backup_current_exe()
        if not backup_path:
            log_message("创建备份失败", "ERROR")
            return False

        # 替换文件（带重试机制）
        log_message(f"替换文件: {current_exe}")
        success = False
        
        for attempt in range(5):
            try:
                shutil.copy2(update_exe, current_exe)
                success = True
                break
            except Exception as e:
                if attempt == 0:
                    log_message(f"文件替换失败，重试中: {e}")
                time.sleep(0.5)
        
        if not success:
            log_message("文件替换失败", "ERROR")
            restore_backup(backup_path)
            return False

        # 设置可执行权限
        try:
            os.chmod(current_exe, 0o755)
        except Exception as e:
            log_message(f"设置可执行权限失败: {e}", "WARNING")

        log_message("更新安装成功")
        # 清理备份和临时文件
        cleanup_backup(backup_path)
        if temp_extract_dir and os.path.exists(temp_extract_dir):
            try:
                shutil.rmtree(temp_extract_dir)
            except Exception:
                pass
        return True

    except Exception as e:
        log_message(f"安装失败: {e}", "ERROR")
        # 尝试恢复备份
        if backup_path:
            restore_backup(backup_path)
        # 清理临时目录
        if temp_extract_dir and os.path.exists(temp_extract_dir):
            try:
                shutil.rmtree(temp_extract_dir)
            except Exception:
                pass
        return False


def restart_application():
    """重启应用程序"""
    try:
        current_exe = get_current_exe_path()
        log_message("重启应用程序...")

        if platform.system() == 'Windows':
            subprocess.Popen([current_exe], creationflags=subprocess.DETACHED_PROCESS)
        else:
            subprocess.Popen([current_exe], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        log_message("应用程序已重启")
        return True

    except Exception as e:
        log_message(f"重启失败: {e}", "ERROR")
        return False


def pause_on_windows(message="按任意键继续..."):
    """Windows平台暂停等待用户输入"""
    if platform.system() == 'Windows':
        print("\n" + "="*50)
        print(message)
        print("="*50)
        try:
            input()
        except:
            time.sleep(5)


def main():
    """主函数"""
    log_message("=== 外部更新脚本启动 ===")

    # 检查命令行参数
    if len(sys.argv) < 2:
        log_message("错误：缺少更新信息参数", "ERROR")
        pause_on_windows("错误：缺少更新信息参数\n按任意键退出...")
        sys.exit(1)

    try:
        # 解析更新信息
        update_info_json = sys.argv[1]
        update_info = json.loads(update_info_json)

        # 可选：第二个参数为目标可执行文件路径
        global CURRENT_EXE_PATH
        if len(sys.argv) >= 3:
            CURRENT_EXE_PATH = os.path.abspath(sys.argv[2])
        
        # 可选：第三个参数为主程序PID
        main_pid = None
        if len(sys.argv) >= 4:
            try:
                main_pid = int(sys.argv[3])
                log_message(f"接收到主程序PID: {main_pid}")
            except ValueError:
                log_message("无效的PID参数", "WARNING")
        log_message(f"准备更新到版本: {update_info.get('version', 'unknown')}")
        
        # 等待主程序退出（如果提供了PID）
        if main_pid:
            wait_for_process_exit(main_pid)
        else:
            # 没有PID，简单等待
            log_message("等待主程序退出...")
            time.sleep(3)
        
        # 标记开始安装（供 GUI 通过 update.log 解析 last_update_time）
        log_message(f"开始安装更新: {update_info.get('version', 'unknown')}")
        
        # 步骤1: 下载更新文件
        update_file = download_update_file(update_info)
        if not update_file:
            log_message("下载失败，保留旧版本", "ERROR")
            pause_on_windows("更新下载失败，程序保持原版本\n按任意键退出...")
            sys.exit(1)

        # 步骤2: 安装更新
        if platform.system() == 'Windows':
            success = install_update_windows(update_file)
        else:
            success = install_update_unix(update_file)

        if not success:
            log_message("安装失败，已恢复旧版本", "ERROR")
            pause_on_windows("更新安装失败，已恢复旧版本\n按任意键退出...")
            sys.exit(1)

        # 步骤3: 清理临时文件
        try:
            os.remove(update_file)
            log_message("清理临时文件完成")
        except Exception as e:
            log_message(f"清理临时文件失败: {e}", "WARNING")

        # 清理备份文件
        backup_path = get_current_exe_path() + ".backup"
        cleanup_backup(backup_path)

        # 写入成功标记，供 GUI 判断更新成功
        log_message("更新成功完成")

        # 步骤4: 重启应用程序
        log_message("更新完成，准备重启应用程序...")
        time.sleep(1)

        if not restart_application():
            log_message("重启失败，请手动重启应用程序", "WARNING")
            pause_on_windows("更新完成，但自动重启失败\n请手动启动程序\n按任意键退出...")
        else:
            log_message("=== 更新脚本执行完成 ===")
            pause_on_windows("更新完成！程序已自动重启\n按任意键关闭此窗口...")

    except json.JSONDecodeError as e:
        log_message(f"解析更新信息失败: {e}", "ERROR")
        pause_on_windows(f"错误：解析更新信息失败\n{e}\n按任意键退出...")
        sys.exit(1)
    except Exception as e:
        log_message(f"更新过程中发生错误: {e}", "ERROR")
        import traceback
        error_detail = traceback.format_exc()
        log_message(f"详细错误:\n{error_detail}", "ERROR")
        pause_on_windows(f"更新失败：{e}\n详细信息已记录到日志\n按任意键退出...")
        sys.exit(1)


if __name__ == "__main__":
    main()
