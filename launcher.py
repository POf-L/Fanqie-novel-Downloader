# -*- coding: utf-8 -*-
"""稳定启动器：仅负责拉取并启动远程 Runtime。"""

import asyncio
import concurrent.futures
import hashlib
import json
import os
import platform
import re
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
        env_repo = os.environ.get("FANQIE_GITHUB_REPO", "").strip()
        if env_repo and re.match(r'^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$', env_repo):
            return env_repo, "环境变量(降级)"

        try:
            import version as _version_module
            version_repo = str(getattr(_version_module, "__github_repo__", "")).strip()
            if version_repo and re.match(r'^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$', version_repo):
                return version_repo, "version.py(降级)"
        except Exception:
            pass

        return "POf-L/Fanqie-novel-Downloader", "默认值"
from pathlib import Path

import requests

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    aiohttp = None
    AIOHTTP_AVAILABLE = False

try:
    from utils.dependency_manager import auto_manage_dependencies
    DEP_MANAGER_AVAILABLE = True
except Exception:
    DEP_MANAGER_AVAILABLE = False



from utils.launcher_tui import LauncherTUI, DownloadOption, MirrorInfo, get_tui, RICH_AVAILABLE

try:
    import version as _launcher_ver_module
    LAUNCHER_VERSION = getattr(_launcher_ver_module, "__version__", "1.0.0")
except Exception:
    LAUNCHER_VERSION = "1.0.0"
APP_DIR_NAME = "FanqieNovelDownloader"
STATE_FILE = "launcher_state.json"
RUNTIME_DIR = "runtime"
BUNDLED_PYTHON_DIR = "python"
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

NODE_TEST_TIMEOUT_SECONDS = 5.0
NODE_TEST_CONNECT_TIMEOUT_SECONDS = 1.0
NODE_TEST_MAX_WORKERS = 500  # 并发测试线程上限

PIP_INDEX_MIRRORS = [
    ("清华", "https://pypi.tuna.tsinghua.edu.cn/simple"),
    ("腾讯", "https://mirrors.cloud.tencent.com/pypi/simple"),
    ("阿里", "https://mirrors.aliyun.com/pypi/simple"),
    ("PyPI", "https://pypi.org/simple"),
]

_selected_pip_mirror_name = "PyPI"
_selected_pip_index_url = "https://pypi.org/simple"
_available_pip_mirrors: List[Tuple[str, str, float]] = []
_available_runtime_mirrors: List[Tuple[str, float]] = []


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
    try:
        response = _do_get(url, headers=headers, timeout=(3, 10))
    except Exception:
        return None
    if response.status_code != 200:
        return None
    try:
        data = response.json()
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _fetch_recent_releases(repo: str, per_page: int = 20) -> List[Dict]:
    url = f"https://api.github.com/repos/{repo}/releases?per_page={per_page}"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "FanqieLauncher",
    }
    try:
        response = _do_get(url, headers=headers, timeout=(3, 10))
    except Exception:
        return []
    if response.status_code != 200:
        return []
    try:
        data = response.json()
    except ValueError:
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def _get_asset_url(release_data: Dict, asset_name: str) -> Optional[str]:
    for asset in release_data.get("assets", []):
        if asset.get("name") == asset_name:
            return asset.get("browser_download_url")
    return None


def _load_platform_manifest(repo: str, platform: str) -> Optional[Dict]:
    asset_name = f"runtime-manifest-{platform}.json"
    candidates: List[Dict] = []

    latest_release = _fetch_latest_release(repo)
    if latest_release:
        candidates.append(latest_release)

    for release in _fetch_recent_releases(repo):
        if latest_release and release.get("id") == latest_release.get("id"):
            continue
        candidates.append(release)

    headers = {"User-Agent": "FanqieLauncher"}
    for release_data in candidates:
        manifest_url = _get_asset_url(release_data, asset_name)
        if not manifest_url:
            continue

        try:
            response = _do_get(manifest_url, headers=headers, timeout=(3, 10))
        except Exception:
            continue
        if response.status_code != 200:
            continue

        try:
            data = response.json()
        except ValueError:
            continue
        if isinstance(data, dict):
            return data

    direct_url = f"https://github.com/{repo}/releases/latest/download/{asset_name}"
    for attempt_url in _build_mirror_urls(direct_url):
        try:
            response = _session.get(attempt_url, headers=headers, timeout=(5, 15), allow_redirects=True)
        except Exception:
            continue
        if response.status_code != 200:
            continue
        try:
            data = response.json()
        except ValueError:
            continue
        if isinstance(data, dict):
            return data

    return None


def _build_mirror_urls(url: str) -> List[str]:
    urls = []
    if _download_mode == "mirror" and _mirror_domain:
        urls.append(f"https://{_mirror_domain}/{url}")
    for node in MIRROR_NODES[:10]:
        mirror = f"https://{node}/{url}"
        if mirror not in urls:
            urls.append(mirror)
    urls.append(url)
    return urls



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


def _download_runtime_archive(url: str, expected_sha256: str, progress_callback=None) -> bytes:
    _progress = progress_callback or _render_download_progress
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
                _progress(downloaded, total, start_ts)
                last_refresh = now

        _progress(downloaded, total, start_ts)
        if not progress_callback:
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


def _bundled_python_path() -> Optional[Path]:
    python_dir = _runtime_root() / BUNDLED_PYTHON_DIR
    if not python_dir.exists():
        return None
    if sys.platform == "win32":
        py = python_dir / "python.exe"
    else:
        py = python_dir / "bin" / "python3"
    return py if py.exists() else None


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


def _looks_like_python_executable(executable: Path) -> bool:
    name = executable.name.lower()
    if "python" in name:
        return True
    return name in {"py", "py.exe"}


def _probe_python_command(cmd_prefix: List[str]) -> Tuple[bool, str]:
    try:
        result = subprocess.run(
            [*cmd_prefix, "-c", "import sys, venv; print(sys.executable)"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except Exception as exc:
        return False, str(exc)

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        return False, stderr or f"returncode={result.returncode}"

    detected = (result.stdout or "").strip()
    return True, detected or "unknown"


def _resolve_venv_builder_command() -> Tuple[List[str], str]:
    """自动寻找可用于创建 venv 的 Python 命令。"""
    candidates: List[List[str]] = []
    seen = set()

    def _add_candidate(cmd: List[str]) -> None:
        key = tuple(cmd)
        if key not in seen:
            seen.add(key)
            candidates.append(cmd)

    env_python = os.environ.get("FANQIE_BOOTSTRAP_PYTHON", "").strip()
    if env_python:
        _add_candidate([env_python])

    for raw_path in (sys.executable, getattr(sys, "_base_executable", "")):
        if not raw_path:
            continue
        candidate = Path(raw_path)
        if candidate.exists() and _looks_like_python_executable(candidate):
            _add_candidate([str(candidate)])

    for cmd_name in ("python", "python3"):
        resolved = shutil.which(cmd_name)
        if resolved:
            _add_candidate([resolved])

    if sys.platform == "win32":
        py_launcher = shutil.which("py")
        if py_launcher:
            _add_candidate([py_launcher, "-3"])

    for cmd in candidates:
        ok, details = _probe_python_command(cmd)
        _write_error(f"[DEBUG] Python候选检查: {' '.join(cmd)} -> {'OK' if ok else 'FAIL'} {details}")
        if ok:
            return cmd, details

    raise RuntimeError(
        "未找到可用 Python 解释器，无法创建 Runtime 虚拟环境。"
        "请安装 Python 3（建议 3.11+），或设置 FANQIE_BOOTSTRAP_PYTHON 指向 python 可执行文件。"
    )


def _repair_venv_pyvenv_cfg(venv_path: Path) -> bool:
    cfg_path = venv_path / "pyvenv.cfg"
    if not cfg_path.exists():
        _write_error("[DEBUG] pyvenv.cfg not found")
        return False

    try:
        cfg_text = cfg_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        _write_error(f"[DEBUG] Failed to read pyvenv.cfg: {e}")
        return False

    cfg_lines = cfg_text.splitlines()
    home_value = None
    for line in cfg_lines:
        if line.strip().startswith("home"):
            parts = line.split("=", 1)
            if len(parts) == 2:
                home_value = parts[1].strip()
                break

    if home_value and Path(home_value).exists():
        _write_error(f"[DEBUG] pyvenv.cfg home path valid: {home_value}")
        return False

    _write_error(f"[DEBUG] pyvenv.cfg home path invalid: {home_value}, attempting repair")

    try:
        builder_cmd, detected_python = _resolve_venv_builder_command()
    except RuntimeError:
        _write_error("[DEBUG] No usable system Python found, cannot repair pyvenv.cfg")
        return False

    local_python = Path(detected_python)
    if not local_python.exists():
        _write_error(f"[DEBUG] Detected Python path does not exist: {detected_python}")
        return False

    local_home = str(local_python.parent)
    _write_error(f"[DEBUG] Repairing pyvenv.cfg home to: {local_home}")

    new_lines = []
    for line in cfg_lines:
        stripped = line.strip()
        if stripped.startswith("home"):
            new_lines.append(f"home = {local_home}")
        elif stripped.startswith("executable"):
            new_lines.append(f"executable = {detected_python}")
        elif stripped.startswith("command"):
            new_lines.append(f"command = {detected_python} -m venv {venv_path}")
        else:
            new_lines.append(line)

    try:
        cfg_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    except Exception as e:
        _write_error(f"[DEBUG] Failed to write pyvenv.cfg: {e}")
        return False

    if sys.platform == "win32":
        venv_python_exe = venv_path / "Scripts" / "python.exe"
        if venv_python_exe.exists() and local_python.exists():
            try:
                shutil.copy2(str(local_python), str(venv_python_exe))
                pythonw = local_python.parent / "pythonw.exe"
                venv_pythonw = venv_path / "Scripts" / "pythonw.exe"
                if pythonw.exists():
                    shutil.copy2(str(pythonw), str(venv_pythonw))
            except Exception as e:
                _write_error(f"[DEBUG] Failed to copy Python executables: {e}")
    else:
        venv_python_bin = venv_path / "bin" / "python"
        if venv_python_bin.is_symlink() or venv_python_bin.exists():
            try:
                venv_python_bin.unlink(missing_ok=True)
                os.symlink(detected_python, str(venv_python_bin))
                for name in ("python3",):
                    link = venv_path / "bin" / name
                    link.unlink(missing_ok=True)
                    os.symlink(detected_python, str(link))
            except Exception as e:
                _write_error(f"[DEBUG] Failed to update symlinks: {e}")

    py_path = _runtime_venv_python()
    try:
        result = subprocess.run(
            [str(py_path), "--version"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            _write_error(f"[DEBUG] venv repair succeeded: {result.stdout.strip()}")
            return True
        else:
            _write_error(f"[DEBUG] venv still broken after repair: {result.stderr}")
            return False
    except Exception as e:
        _write_error(f"[DEBUG] venv verification failed after repair: {e}")
        return False


def _ensure_runtime_venv() -> Path:
    bundled = _bundled_python_path()
    if bundled:
        _write_error(f"[DEBUG] 使用内置 Python: {bundled}")
        return bundled

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
        except Exception as e:
            _write_error(f"[DEBUG] 虚拟环境测试失败: {e}")
        
        venv_path = runtime_root / ".venv"
        _write_error("[DEBUG] 尝试修复 pyvenv.cfg")
        if _repair_venv_pyvenv_cfg(venv_path):
            return _runtime_venv_python()

        _write_error("[DEBUG] 修复失败，将重新创建虚拟环境")
        try:
            if venv_path.exists():
                shutil.rmtree(venv_path)
                _write_error("[DEBUG] 已删除损坏的虚拟环境")
        except Exception as e:
            _write_error(f"[DEBUG] 删除虚拟环境失败: {e}")

    print("正在创建 Runtime 虚拟环境...")
    builder_cmd, detected_python = _resolve_venv_builder_command()
    _write_error(f"[DEBUG] 使用系统Python命令: {' '.join(builder_cmd)}")
    _write_error(f"[DEBUG] 探测到解释器: {detected_python}")
    _write_error(f"[DEBUG] 目标路径: {runtime_root / '.venv'}")
    
    try:
        result = subprocess.run(
            [*builder_cmd, "-m", "venv", str(runtime_root / ".venv")],
            check=True,
            cwd=str(runtime_root),
            capture_output=True,
            text=True,
            timeout=300,
        )
        _write_error(f"[DEBUG] 虚拟环境创建成功")
        if result.stdout:
            _write_error(f"[DEBUG] stdout: {result.stdout.strip()}")
        if result.stderr:
            _write_error(f"[DEBUG] stderr: {result.stderr.strip()}")
    except subprocess.CalledProcessError as e:
        _write_error(f"[DEBUG] 虚拟环境创建失败: {e}")
        _write_error(f"[DEBUG] stdout: {e.stdout}")
        _write_error(f"[DEBUG] stderr: {e.stderr}")
        raise RuntimeError(f"虚拟环境创建失败: {e}")
    except subprocess.TimeoutExpired as e:
        _write_error(f"[DEBUG] 虚拟环境创建超时: {e}")
        raise RuntimeError("虚拟环境创建超时（300秒）")

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
    """自动选择 pip 镜像源，并保存候选列表用于失败回退。"""
    global _selected_pip_mirror_name, _selected_pip_index_url, _available_pip_mirrors

    tui = get_tui() if RICH_AVAILABLE else None

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
        _available_pip_mirrors = [("PyPI", "https://pypi.org/simple", 0.0)]
        _selected_pip_mirror_name = "PyPI"
        _selected_pip_index_url = "https://pypi.org/simple"
        return

    _available_pip_mirrors = available
    _selected_pip_mirror_name, _selected_pip_index_url, _ = available[0]
    if tui:
        tui.show_status(f"已自动选择最快 pip 镜像: {_selected_pip_mirror_name}", "info")
    else:
        print(f"已自动选择最快 pip 镜像: {_selected_pip_mirror_name} ({_selected_pip_index_url})")


def _run_pip_install_command(cmd: List[str], timeout_seconds: int = 900) -> None:
    env = os.environ.copy()
    env.setdefault("PIP_DISABLE_PIP_VERSION_CHECK", "1")
    env.setdefault("PIP_NO_INPUT", "1")
    subprocess.run(
        cmd,
        check=True,
        timeout=timeout_seconds,
        text=True,
        env=env,
    )


def _pip_install_with_mirrors(
    py_path: Path,
    install_args: List[str],
) -> None:
    install_target = " ".join(install_args).strip() or "(无参数)"
    if len(install_target) > 160:
        install_target = install_target[:157] + "..."
    _write_error(f"[DEBUG] pip安装参数: {install_args}")
    _write_error(f"[DEBUG] 使用Python路径: {py_path}")

    def _build_cmd(index_url: str) -> List[str]:
        return [
            str(py_path),
            "-m",
            "pip",
            "install",
            "--progress-bar",
            "on",
            "--index-url",
            index_url,
            *install_args,
        ]

    mirror_attempts: List[Tuple[str, str]] = []
    seen_urls = set()

    def _append_attempt(name: str, index_url: str) -> None:
        if not index_url or index_url in seen_urls:
            return
        seen_urls.add(index_url)
        mirror_attempts.append((name, index_url))

    _append_attempt(_selected_pip_mirror_name, _selected_pip_index_url)
    for name, index_url, _ in _available_pip_mirrors:
        _append_attempt(name, index_url)
    _append_attempt("PyPI", "https://pypi.org/simple")

    last_error: Optional[Exception] = None
    total_attempts = len(mirror_attempts)

    for attempt_index, (mirror_name, index_url) in enumerate(mirror_attempts, 1):
        print(
            f"使用 {mirror_name} 源安装依赖: {install_target} "
            f"(尝试 {attempt_index}/{total_attempts})",
            flush=True
        )
        try:
            cmd = _build_cmd(index_url)
            _write_error(f"[DEBUG] 执行命令: {' '.join(cmd)}")
            _run_pip_install_command(cmd, timeout_seconds=900)
            _write_error(f"[DEBUG] pip安装成功: {mirror_name}")
            return
        except subprocess.CalledProcessError as exc:
            last_error = exc
            _write_error(f"[DEBUG] pip安装失败: {mirror_name}, returncode={exc.returncode}")
            continue
        except subprocess.TimeoutExpired as exc:
            last_error = exc
            _write_error(f"[DEBUG] pip安装超时: {mirror_name}, {exc}")
            continue
        except Exception as exc:
            last_error = exc
            _write_error(f"[DEBUG] pip安装异常: {mirror_name}, {exc}")
            continue

    raise RuntimeError(f"pip 安装失败（全部镜像均重试失败）: {last_error}")


def _ensure_runtime_dependencies() -> None:
    if _bundled_python_path():
        _write_error("[DEBUG] 内置 Python 已包含所有依赖，跳过安装")
        print("✓ 使用内置 Python，无需安装依赖")
        return

    runtime_root = _runtime_root()
    if not runtime_root.exists():
        raise RuntimeError("Runtime 不存在，无法安装依赖")

    tui = get_tui() if RICH_AVAILABLE else None

    requirements_path = _requirements_file_for_platform()
    dep_targets = ["main.py", "core", "utils", "web", "config"]

    py_path = _ensure_runtime_venv()

    if tui:
        tui.show_status("正在安装 Runtime 依赖...", "info")
    else:
        print("正在安装 Runtime 依赖...")

    print("依赖安装进度 1/3: 扫描并校验依赖状态", flush=True)

    pip_upgraded = False
    install_step_announced = False

    def _ensure_pip_upgraded() -> None:
        nonlocal pip_upgraded
        if pip_upgraded:
            return
        _write_error("[DEBUG] 开始升级pip（仅在需要安装依赖时执行）")
        _pip_install_with_mirrors(py_path, ["--upgrade", "pip"])
        pip_upgraded = True

    def _install_missing_packages(pkgs: List[str]) -> None:
        nonlocal install_step_announced
        if not install_step_announced:
            print("依赖安装进度 2/3: 安装缺失依赖", flush=True)
            install_step_announced = True
        _ensure_pip_upgraded()
        _pip_install_with_mirrors(py_path, pkgs)

    installed_dynamic: List[str] = []
    if DEP_MANAGER_AVAILABLE:
        try:
            result = auto_manage_dependencies(
                project_root=runtime_root,
                targets=dep_targets,
                python_executable=str(py_path),
                requirements_file=requirements_path,
                state_file=_deps_state_path(),
                installer=_install_missing_packages,
                extra_packages=["requests", "rich", "InquirerPy", "aiohttp"],
                install_missing=True,
                sync_requirements=True,
                pin_versions=True,
                skip_if_unchanged=True,
            )
            installed_dynamic = result.get("installed_packages", [])
            if result.get("skipped"):
                if tui:
                    tui.show_status("依赖已就绪", "success")
                else:
                    print("✓ 依赖已就绪")
                print("依赖安装进度 3/3: 完成（无需安装）", flush=True)
                return

            if installed_dynamic:
                _write_error(f"[DEBUG] 动态安装依赖: {installed_dynamic}")
        except Exception as exc:
            _write_error(f"[DEBUG] 自动依赖管理失败，回退requirements: {exc}")
            if requirements_path.exists():
                print("依赖安装进度 2/3: 回退安装 requirements", flush=True)
                _ensure_pip_upgraded()
                _pip_install_with_mirrors(py_path, ["-r", str(requirements_path)])
            _write_json(
                _deps_state_path(),
                {
                    "requirements_file": str(requirements_path.relative_to(runtime_root)) if requirements_path.exists() else "",
                    "python_version": platform.python_version(),
                    "updated_at": int(time.time()),
                },
            )
    else:
        if requirements_path.exists():
            print("依赖安装进度 2/3: 安装 requirements", flush=True)
            _ensure_pip_upgraded()
            _pip_install_with_mirrors(py_path, ["-r", str(requirements_path)])
        _write_json(
            _deps_state_path(),
            {
                "requirements_file": str(requirements_path.relative_to(runtime_root)) if requirements_path.exists() else "",
                "python_version": platform.python_version(),
                "updated_at": int(time.time()),
            },
        )
    
    if tui:
        tui.show_status("Runtime 依赖安装完成", "success")
    else:
        print("✓ Runtime 依赖安装完成")
    print("依赖安装进度 3/3: 完成", flush=True)


async def _test_node_latency_async(domain: str, session: Any) -> Tuple[str, Optional[float]]:
    """异步测试单个节点延迟。"""
    try:
        start = time.perf_counter()
        timeout = aiohttp.ClientTimeout(total=NODE_TEST_TIMEOUT_SECONDS, connect=NODE_TEST_CONNECT_TIMEOUT_SECONDS)
        async with session.head(
            f"https://{domain}",
            timeout=timeout,
            allow_redirects=False,
            ssl=False  # 跳过 SSL 验证以提升速度
        ) as response:
            if response.status < 500:
                return (domain, (time.perf_counter() - start) * 1000)
            return (domain, None)
    except Exception:
        return (domain, None)


def _test_node_latency(domain: str) -> Tuple[str, Optional[float]]:
    """同步测试单个节点延迟 - 兼容性保留"""
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


async def _test_all_nodes_async() -> List[Tuple[str, float]]:
    """异步测试所有镜像节点延迟。"""
    if not AIOHTTP_AVAILABLE:
        return []

    print(f"正在测试 {len(MIRROR_NODES)} 个镜像节点延迟（并发）...")
    
    # 配置 aiohttp 连接器用于并发测速
    connector = aiohttp.TCPConnector(
        limit=1000,  # 总连接池大小
        limit_per_host=50,  # 每个主机的连接数
        ttl_dns_cache=300,  # DNS 缓存时间
        use_dns_cache=True,
        ssl=False,  # 跳过 SSL 验证提升速度
        enable_cleanup_closed=True
    )
    
    timeout = aiohttp.ClientTimeout(total=NODE_TEST_TIMEOUT_SECONDS, connect=NODE_TEST_CONNECT_TIMEOUT_SECONDS)
    
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        # 创建所有任务
        tasks = [_test_node_latency_async(domain, session) for domain in MIRROR_NODES]
        
        # 并发执行所有任务
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        available = []
        for result in results:
            if isinstance(result, tuple) and len(result) == 2:
                domain, latency = result
                if latency is not None:
                    available.append((domain, latency))
        
        available.sort(key=lambda x: x[1])
        print(f"异步测速完成，可用节点: {len(available)}/{len(MIRROR_NODES)}")
        return available


def _ensure_launcher_dependency(module_name: str, package_name: Optional[str] = None) -> bool:
    """为启动器自身尝试安装缺失依赖。"""
    package = package_name or module_name
    python_for_install = sys.executable
    try:
        resolved_cmd, _ = _resolve_venv_builder_command()
        if resolved_cmd:
            python_for_install = resolved_cmd[0]
    except Exception as exc:
        _write_error(f"[DEBUG] 解析启动器依赖安装解释器失败，回退sys.executable: {exc}")

    if DEP_MANAGER_AVAILABLE:
        try:
            result = auto_manage_dependencies(
                project_root=_base_dir(),
                targets=["launcher.py", "utils", "config"],
                python_executable=python_for_install,
                requirements_file=_base_dir() / "config" / "requirements.txt",
                state_file=_base_dir() / ".launcher_deps_state.json",
                extra_packages=[package],
                install_missing=True,
                sync_requirements=True,
                pin_versions=True,
                skip_if_unchanged=False,
            )
            installed = result.get("installed_packages", [])
            if installed:
                _write_error(f"[DEBUG] 启动器补装依赖: {installed}")
        except Exception as exc:
            _write_error(f"[DEBUG] 启动器依赖管理安装失败: {exc}")

    try:
        __import__(module_name)
        return True
    except Exception as exc:
        _write_error(f"[DEBUG] 启动器依赖导入失败: {module_name}, {exc}")
        return False


def _resolve_repo_with_fallback() -> Tuple[str, str]:
    """获取仓库配置并做强兜底，避免回退到错误默认值。"""
    try:
        repo, source = get_effective_repo()
    except Exception as exc:
        _write_error(f"[DEBUG] 读取仓库配置失败: {exc}")
        repo, source = "", "读取失败"

    if repo and re.match(r'^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$', repo):
        return repo, source

    env_repo = os.environ.get("FANQIE_GITHUB_REPO", "").strip()
    if env_repo and re.match(r'^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$', env_repo):
        return env_repo, "环境变量(兜底)"

    try:
        import version as _version_module
        version_repo = str(getattr(_version_module, "__github_repo__", "")).strip()
        if version_repo and re.match(r'^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$', version_repo):
            return version_repo, "version.py(兜底)"
    except Exception:
        pass

    return "POf-L/Fanqie-novel-Downloader", "默认值"


def _test_all_nodes() -> List[Tuple[str, float]]:
    """同步测试所有镜像节点延迟 - 兼容性保留"""
    print("正在同步测试镜像节点延迟...")
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


def _has_proxy_env() -> bool:
    proxy_keys = ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy")
    return any(os.environ.get(key, "").strip() for key in proxy_keys)


def _select_download_mode() -> None:
    global _download_mode, _mirror_domain, aiohttp, AIOHTTP_AVAILABLE, _available_runtime_mirrors
    tui = get_tui() if RICH_AVAILABLE else None

    # 全自动：默认优先镜像，失败后自动回退
    _download_mode = "mirror"
    _session.trust_env = False
    _mirror_domain = None
    _available_runtime_mirrors = []

    if tui:
        tui.show_status("下载策略：自动模式（优先镜像）", "info")
    else:
        print("下载策略：自动模式（优先镜像）")

    try:
        if AIOHTTP_AVAILABLE:
            if hasattr(asyncio, 'run'):
                available = asyncio.run(_test_all_nodes_async())
            else:
                loop = asyncio.get_event_loop()
                available = loop.run_until_complete(_test_all_nodes_async())
        else:
            if _ensure_launcher_dependency("aiohttp", "aiohttp"):
                import aiohttp as _aiohttp
                aiohttp = _aiohttp
                AIOHTTP_AVAILABLE = True
                if hasattr(asyncio, 'run'):
                    available = asyncio.run(_test_all_nodes_async())
                else:
                    loop = asyncio.get_event_loop()
                    available = loop.run_until_complete(_test_all_nodes_async())
            else:
                raise RuntimeError("aiohttp 未安装")
    except Exception as e:
        print(f"异步测速不可用，回退到同步模式: {e}")
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
        if _has_proxy_env():
            _download_mode = "proxy"
            _session.trust_env = True
            if tui:
                tui.show_status("镜像不可用，检测到系统代理，自动使用代理直连", "warning")
            else:
                print("镜像不可用，检测到系统代理，自动使用代理直连")
        else:
            _download_mode = "direct"
            _session.trust_env = False
            if tui:
                tui.show_status("所有镜像节点均不可用，自动使用直连", "warning")
            else:
                print("所有镜像节点均不可用，自动使用直连")
        return

    _available_runtime_mirrors = available
    _mirror_domain = available[0][0]
    latency_ms = available[0][1]
    if tui:
        tui.show_status(f"已自动选择最快镜像: {_mirror_domain} ({latency_ms:.0f}ms)", "info")
    else:
        print(f"已自动选择最快镜像: {_mirror_domain} ({latency_ms:.0f}ms)")


def _ensure_runtime(repo: str) -> None:
    global _mirror_domain
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
    
    def _download_with_progress(target_url: str) -> bytes:
        if tui and tui.use_tui:
            return tui.show_download_progress(
                f"下载 Runtime ({runtime_version})",
                _download_runtime_archive,
                target_url, runtime_sha
            )
        return _download_runtime_archive(target_url, runtime_sha)

    archive_bytes: Optional[bytes] = None
    mirror_errors: List[str] = []

    # 下载 Runtime：全自动策略
    # 1) 若启用镜像，按测速结果依次尝试镜像
    # 2) 全部失败后自动回退直连
    if _download_mode == "mirror":
        mirror_candidates: List[str] = []
        if _mirror_domain:
            mirror_candidates.append(_mirror_domain)
        for domain, _ in _available_runtime_mirrors:
            if domain not in mirror_candidates:
                mirror_candidates.append(domain)

        for idx, domain in enumerate(mirror_candidates, 1):
            mirror_url = f"https://{domain}/{runtime_url}"
            try:
                if idx == 1:
                    if tui:
                        tui.show_status(f"尝试镜像下载: {domain}", "info")
                    else:
                        print(f"尝试镜像下载: {domain}")
                else:
                    if tui:
                        tui.show_status(f"镜像重试({idx}/{len(mirror_candidates)}): {domain}", "warning")
                    else:
                        print(f"镜像重试({idx}/{len(mirror_candidates)}): {domain}")
                archive_bytes = _download_with_progress(mirror_url)
                _mirror_domain = domain
                break
            except Exception as exc:
                mirror_errors.append(f"{domain}: {exc}")
                _write_error(f"[DEBUG] 镜像下载失败: {domain}, {exc}")
                continue

        if archive_bytes is None:
            if tui:
                tui.show_status("镜像均失败，自动回退直连下载", "warning")
            else:
                print("镜像均失败，自动回退直连下载")

    if archive_bytes is None:
        try:
            archive_bytes = _download_with_progress(runtime_url)
        except Exception as exc:
            detail = "; ".join(mirror_errors) if mirror_errors else "无镜像失败记录"
            raise RuntimeError(f"Runtime 下载失败（直连失败，镜像错误: {detail}）: {exc}")
    
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

    bundled = _bundled_python_path()
    if bundled:
        runtime_python = bundled
    else:
        runtime_venv = runtime_root / ".venv"
        if sys.platform == "win32":
            runtime_python = runtime_venv / "Scripts" / "python.exe"
        else:
            runtime_python = runtime_venv / "bin" / "python"

    if not runtime_python.exists():
        raise FileNotFoundError(
            f"Runtime Python not found: {runtime_python}\n"
            f"Please delete {runtime_root} and restart to re-download Runtime"
        )

    env = os.environ.copy()
    env["FANQIE_RUNTIME_BASE"] = str(runtime_root)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    result = subprocess.run(
        [str(runtime_python), str(runtime_main)],
        cwd=str(runtime_root),
        env=env,
    )
    sys.exit(result.returncode)

def _get_launcher_asset_name() -> str:
    if sys.platform == "win32":
        return "FanqieLauncher-windows-x64.exe"
    if sys.platform == "darwin":
        return "FanqieLauncher-macos-x64"
    return "FanqieLauncher-linux-x64"


def _check_launcher_update(repo: str) -> None:
    if not getattr(sys, 'frozen', False):
        return

    manifest_url = f"https://github.com/{repo}/releases/download/launcher-stable/launcher-manifest.json"
    headers = {"User-Agent": "FanqieLauncher"}
    manifest = None
    for url in _build_mirror_urls(manifest_url):
        try:
            resp = _session.get(url, headers=headers, timeout=(5, 10), allow_redirects=True)
        except Exception:
            continue
        if resp.status_code != 200:
            continue
        try:
            data = resp.json()
        except ValueError:
            continue
        if isinstance(data, dict) and "launcher_version" in data:
            manifest = data
            break

    if not manifest:
        _write_error("[DEBUG] 无法获取启动器更新清单，跳过自更新检查")
        return

    remote_ver = str(manifest.get("launcher_version", ""))
    if not remote_ver or remote_ver <= LAUNCHER_VERSION:
        return

    tui = get_tui() if RICH_AVAILABLE else None
    msg = f"发现启动器新版本: {remote_ver} (当前: {LAUNCHER_VERSION})"
    if tui:
        tui.show_status(msg, "info")
    else:
        print(msg)

    asset_name = _get_launcher_asset_name()
    download_url = f"https://github.com/{repo}/releases/download/launcher-stable/{asset_name}"

    current_exe = Path(sys.executable)
    backup_exe = current_exe.with_suffix(current_exe.suffix + ".old")

    try:
        if backup_exe.exists():
            backup_exe.unlink()
    except Exception:
        pass

    new_data = None
    for url in _build_mirror_urls(download_url):
        try:
            resp = _session.get(url, headers=headers, timeout=(10, 120), stream=True, allow_redirects=True)
        except Exception:
            continue
        if resp.status_code != 200:
            continue
        new_data = resp.content
        break

    if not new_data or len(new_data) < 1024:
        _write_error("[DEBUG] 启动器下载失败或文件过小，跳过更新")
        return

    try:
        os.rename(current_exe, backup_exe)
        with open(current_exe, 'wb') as f:
            f.write(new_data)
        if sys.platform != "win32":
            os.chmod(current_exe, 0o755)
    except Exception as e:
        _write_error(f"[DEBUG] 启动器替换失败: {e}")
        if backup_exe.exists() and not current_exe.exists():
            try:
                os.rename(backup_exe, current_exe)
            except Exception:
                pass
        return

    msg = f"启动器已更新到 {remote_ver}，正在重启..."
    if tui:
        tui.show_status(msg, "success")
    else:
        print(msg)

    try:
        if sys.platform == "win32":
            os.execv(str(current_exe), [str(current_exe)] + sys.argv[1:])
        else:
            os.execv(str(current_exe), [str(current_exe)] + sys.argv[1:])
    except Exception:
        print("请手动重启启动器以使用新版本")


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
    repo, repo_source = _resolve_repo_with_fallback()

    # 强制注入仓库环境变量，确保后续子进程与动态模块统一使用
    os.environ["FANQIE_GITHUB_REPO"] = repo
    
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
        
        # 启动器自更新检查
        if tui:
            tui.show_status("检查启动器更新...", "info")
        _check_launcher_update(repo)
        
        # Runtime检查和更新
        if tui:
            tui.show_status("检查Runtime更新...", "info")
        _ensure_runtime(repo)
        
        # 依赖安装（直接输出 pip 实时日志，避免进度被静默）
        if tui:
            tui.show_status("安装Runtime依赖（显示实时日志）...", "info")
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
                    time.sleep(30)
        sys.exit(1)


if __name__ == "__main__":
    main()
