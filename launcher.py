# -*- coding: utf-8 -*-
"""稳定启动器：仅负责拉取并启动远程 Runtime。"""

import concurrent.futures
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
import traceback
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests


LAUNCHER_VERSION = "1.0.0"
APP_DIR_NAME = "FanqieNovelDownloader"
STATE_FILE = "launcher_state.json"
RUNTIME_DIR = "runtime"
BACKUP_DIR = "runtime_backup"

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


def _write_error(message: str) -> None:
    try:
        stderr = sys.__stderr__ if hasattr(sys, "__stderr__") and sys.__stderr__ else sys.stderr
        stderr.write(message + "\n")
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
    data = response.json()
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

    data = response.json()
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


def _test_node_latency(domain: str) -> Tuple[str, Optional[float]]:
    try:
        start = time.time()
        requests.head(f"https://{domain}", timeout=3, allow_redirects=True)
        return (domain, (time.time() - start) * 1000)
    except Exception:
        return (domain, None)


def _test_all_nodes() -> List[Tuple[str, float]]:
    print("正在测试镜像节点延迟...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
        results = list(executor.map(_test_node_latency, MIRROR_NODES))
    available = sorted(
        [(d, l) for d, l in results if l is not None],
        key=lambda x: x[1],
    )
    return available


def _select_download_mode() -> None:
    global _download_mode, _mirror_domain

    print("\n请选择下载方式:")
    print("  1. 直连 GitHub (不使用代理)")
    print("  2. 直连 GitHub (使用系统代理)")
    print("  3. 使用镜像节点")

    try:
        choice = input("请输入选项 [1/2/3] (默认 3): ").strip()
    except (EOFError, KeyboardInterrupt):
        choice = ""

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

    available = _test_all_nodes()
    if not available:
        print("所有镜像节点均不可用，将使用直连")
        _download_mode = "direct"
        return

    max_len = max(len(d) for d, _ in available)
    for i, (domain, latency) in enumerate(available, 1):
        print(f"  {i:>3}. {domain:<{max_len}}  {latency:>7.0f}ms")

    try:
        sel = input(f"\n请选择节点编号 [1-{len(available)}] (默认 1): ").strip()
    except (EOFError, KeyboardInterrupt):
        sel = ""

    try:
        idx = int(sel) - 1 if sel else 0
        if not (0 <= idx < len(available)):
            idx = 0
    except ValueError:
        idx = 0

    _mirror_domain = available[idx][0]
    print(f"已选择镜像: {_mirror_domain}")


def _ensure_runtime(repo: str) -> None:
    platform = _platform_name()
    state_path = _state_path()
    local_state = _read_json(state_path) or {}

    remote_manifest = _load_platform_manifest(repo, platform)
    if not remote_manifest:
        if (_runtime_root() / "main.py").exists():
            print("⚠ 无法获取远程 Runtime 清单，使用本地 Runtime")
            return
        raise RuntimeError("无法获取远程 Runtime 清单，且本地 Runtime 不可用")

    if _is_runtime_up_to_date(local_state, remote_manifest):
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

    print(f"正在更新 Runtime: {runtime_version}")
    if _download_mode == "mirror" and _mirror_domain:
        mirror_url = f"https://{_mirror_domain}/{runtime_url}"
        try:
            archive_bytes = _download_runtime_archive(mirror_url, runtime_sha)
        except Exception:
            print("\n镜像下载失败，尝试直连...")
            archive_bytes = _download_runtime_archive(runtime_url, runtime_sha)
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
    print("✓ Runtime 更新完成")


def _launch_runtime() -> None:
    runtime_main = _runtime_root() / "main.py"
    if not runtime_main.exists():
        raise FileNotFoundError(f"未找到 Runtime 入口: {runtime_main}")

    os.environ["FANQIE_RUNTIME_BASE"] = str(_runtime_root())
    sys.path.insert(0, str(_runtime_root()))

    runtime_venv = _runtime_root() / ".venv"
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
    print("=" * 50)
    print("番茄小说下载器 启动器")
    print("=" * 50)

    repo = os.environ.get("FANQIE_GITHUB_REPO", "POf-L/Fanqie-novel-Downloader")
    try:
        _select_download_mode()
        _ensure_runtime(repo)
        _launch_runtime()
    except Exception as error:
        _write_error(f"启动失败: {error}")
        if getattr(sys, "frozen", False):
            try:
                _write_error("按回车键退出...")
                input()
            except Exception:
                pass
        raise


if __name__ == "__main__":
    main()
