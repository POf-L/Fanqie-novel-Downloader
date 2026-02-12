# -*- coding: utf-8 -*-
"""自动化依赖管理：扫描、安装、requirements 生成与更新。"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.metadata
import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set


DEFAULT_TARGETS: List[str] = ["main.py", "launcher.py", "core", "utils", "web", "config"]
DEFAULT_REQUIREMENTS_FILE = "config/requirements.txt"

KNOWN_IMPORT_TO_PACKAGE: Dict[str, str] = {
    "PIL": "Pillow",
    "bs4": "beautifulsoup4",
    "yaml": "PyYAML",
    "cv2": "opencv-python",
    "Crypto": "pycryptodome",
    "fitz": "PyMuPDF",
    "sklearn": "scikit-learn",
    "OpenSSL": "pyOpenSSL",
    "fake_useragent": "fake-useragent",
    "webview": "pywebview",
    "inquirerpy": "InquirerPy",
}

IGNORED_IMPORT_MODULES: Set[str] = {
    "version",
    # Runtime 环境中不包含 launcher.py，避免误判为第三方依赖
    "launcher",
}


def _normalize_targets(targets: Optional[Iterable[str]]) -> List[str]:
    if not targets:
        return list(DEFAULT_TARGETS)
    return [target for target in targets if target]


def _stdlib_modules() -> Set[str]:
    modules = set(getattr(sys, "stdlib_module_names", set()))
    modules.update({"__future__"})
    return modules


def _local_top_level_modules(project_root: Path) -> Set[str]:
    local_modules: Set[str] = set()
    for entry in project_root.iterdir():
        if entry.name.startswith("."):
            continue
        if entry.is_dir() and (entry / "__init__.py").exists():
            local_modules.add(entry.name)
        elif entry.is_file() and entry.suffix == ".py":
            local_modules.add(entry.stem)
    return local_modules


def _iter_python_files(project_root: Path, targets: Iterable[str]) -> Iterable[Path]:
    for target in _normalize_targets(targets):
        path = project_root / target
        if path.is_file() and path.suffix == ".py":
            yield path
        elif path.is_dir():
            for py_file in path.rglob("*.py"):
                yield py_file


def discover_import_roots(project_root: Path, targets: Iterable[str]) -> Set[str]:
    imports: Set[str] = set()
    for py_file in _iter_python_files(project_root, targets):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        except Exception:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_name = alias.name.split(".", 1)[0].strip()
                    if root_name:
                        imports.add(root_name)
            elif isinstance(node, ast.ImportFrom):
                if node.level and node.level > 0:
                    continue
                if node.module:
                    root_name = node.module.split(".", 1)[0].strip()
                    if root_name:
                        imports.add(root_name)
    return imports


def _import_to_distribution_map() -> Dict[str, str]:
    mapping: Dict[str, str] = {}

    try:
        packages_distributions = importlib.metadata.packages_distributions()
        for import_name, dist_names in packages_distributions.items():
            if dist_names:
                mapping.setdefault(import_name, dist_names[0])
    except Exception:
        pass

    for dist in importlib.metadata.distributions():
        dist_name = dist.metadata.get("Name")
        if not dist_name:
            continue
        mapping.setdefault(dist_name, dist_name)
        mapping.setdefault(dist_name.replace("-", "_"), dist_name)
        top_level = dist.read_text("top_level.txt") or ""
        for item in top_level.splitlines():
            import_name = item.strip()
            if import_name:
                mapping.setdefault(import_name, dist_name)
    return mapping


def _resolve_package_name(import_name: str, import_to_dist: Dict[str, str]) -> str:
    if import_name in KNOWN_IMPORT_TO_PACKAGE:
        return KNOWN_IMPORT_TO_PACKAGE[import_name]
    if import_name in import_to_dist:
        return import_to_dist[import_name]
    return import_name


def resolve_required_packages(project_root: Path, targets: Iterable[str]) -> List[str]:
    discovered = discover_import_roots(project_root, targets)
    stdlib_modules = _stdlib_modules()
    local_modules = _local_top_level_modules(project_root)
    import_to_dist = _import_to_distribution_map()

    packages: Set[str] = set()
    for import_name in discovered:
        if import_name in IGNORED_IMPORT_MODULES:
            continue
        if import_name in stdlib_modules or import_name in local_modules:
            continue
        package_name = _resolve_package_name(import_name, import_to_dist)
        if package_name:
            packages.add(package_name)
    return sorted(packages)


def module_exists(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except Exception:
        return False


def detect_missing_imports(project_root: Path, targets: Iterable[str]) -> List[str]:
    discovered = discover_import_roots(project_root, targets)
    stdlib_modules = _stdlib_modules()
    local_modules = _local_top_level_modules(project_root)

    missing: List[str] = []
    for import_name in sorted(discovered):
        if import_name in IGNORED_IMPORT_MODULES:
            continue
        if import_name in stdlib_modules or import_name in local_modules:
            continue
        if not module_exists(import_name):
            missing.append(import_name)
    return missing


def _is_package_installed(package_name: str) -> bool:
    normalized = package_name.replace("_", "-")
    candidates = [package_name, normalized]
    for candidate in candidates:
        try:
            importlib.metadata.version(candidate)
            return True
        except importlib.metadata.PackageNotFoundError:
            continue
        except Exception:
            continue
    return False


def install_packages(
    python_executable: str,
    packages: Iterable[str],
    installer=None,
) -> List[str]:
    installed: List[str] = []
    for package in sorted(set(packages)):
        if not package:
            continue
        if installer:
            installer([package])
        else:
            subprocess.check_call([
                python_executable,
                "-m",
                "pip",
                "install",
                "--prefer-binary",
                package,
            ])
        installed.append(package)
    return installed


def _resolve_missing_packages(
    missing_imports: Iterable[str],
    import_to_dist: Dict[str, str],
    extra_packages: Optional[Iterable[str]] = None,
) -> List[str]:
    packages: Set[str] = set()
    for import_name in missing_imports:
        packages.add(_resolve_package_name(import_name, import_to_dist))
    for package in extra_packages or []:
        if package and not _is_package_installed(package):
            packages.add(package)
    return sorted(packages)


def build_dependency_signature(project_root: Path, targets: Iterable[str]) -> str:
    hasher = hashlib.sha256()
    for py_file in sorted(_iter_python_files(project_root, targets), key=lambda file_path: str(file_path).lower()):
        try:
            relative = py_file.relative_to(project_root).as_posix()
            hasher.update(relative.encode("utf-8", errors="ignore"))
            hasher.update(py_file.read_bytes())
        except Exception:
            continue
    return hasher.hexdigest()


def _resolve_installed_version(package_name: str) -> Optional[str]:
    candidates = [package_name, package_name.replace("_", "-")]
    for candidate in candidates:
        try:
            return importlib.metadata.version(candidate)
        except importlib.metadata.PackageNotFoundError:
            continue
        except Exception:
            continue
    return None


def generate_requirements_entries(packages: Iterable[str], pin_versions: bool = True) -> List[str]:
    normalized_package_map: Dict[str, str] = {}
    for package in packages:
        if not package:
            continue
        normalized_key = package.replace("_", "-").lower()
        if normalized_key not in normalized_package_map:
            normalized_package_map[normalized_key] = package

    entries: List[str] = []
    for _, package in sorted(normalized_package_map.items(), key=lambda item: item[0]):
        if not package:
            continue
        if not pin_versions:
            entries.append(package)
            continue

        installed_version = _resolve_installed_version(package)
        if installed_version:
            entries.append(f"{package}=={installed_version}")
        else:
            entries.append(package)
    return entries


def sync_requirements_file(requirements_path: Path, entries: Iterable[str]) -> bool:
    requirements_path.parent.mkdir(parents=True, exist_ok=True)

    header = [
        "# Auto-generated by utils/dependency_manager.py",
        "# Run: python -m utils.dependency_manager",
        "",
    ]
    content = "\n".join(header + list(entries)) + "\n"

    if requirements_path.exists():
        old_content = requirements_path.read_text(encoding="utf-8", errors="ignore")
        if old_content == content:
            return False

    requirements_path.write_text(content, encoding="utf-8")
    return True


def ensure_project_dependencies(
    project_root: Path,
    targets: Iterable[str],
    python_executable: str,
    installer=None,
    extra_packages: Optional[Iterable[str]] = None,
) -> List[str]:
    missing_imports = detect_missing_imports(project_root, targets)
    import_to_dist = _import_to_distribution_map()
    missing_packages = _resolve_missing_packages(missing_imports, import_to_dist, extra_packages=extra_packages)
    if not missing_packages:
        return []
    return install_packages(python_executable, missing_packages, installer=installer)


def auto_manage_dependencies(
    project_root: Path,
    targets: Iterable[str],
    python_executable: str,
    requirements_file: Path,
    state_file: Path,
    installer=None,
    extra_packages: Optional[Iterable[str]] = None,
    install_missing: bool = True,
    sync_requirements: bool = True,
    pin_versions: bool = True,
    skip_if_unchanged: bool = True,
) -> Dict[str, Any]:
    normalized_targets = _normalize_targets(targets)
    signature = build_dependency_signature(project_root, normalized_targets)

    previous_state: Dict[str, Any] = {}
    if state_file.exists():
        try:
            previous_state = json.loads(state_file.read_text(encoding="utf-8"))
        except Exception:
            previous_state = {}

    if skip_if_unchanged and previous_state.get("dependency_signature") == signature:
        missing_imports_now = detect_missing_imports(project_root, normalized_targets)
        missing_extra_packages = [
            package for package in (extra_packages or [])
            if package and not _is_package_installed(package)
        ]
        requirements_ready = (not sync_requirements) or requirements_file.exists()

        if not missing_imports_now and not missing_extra_packages and requirements_ready:
            return {
                "skipped": True,
                "dependency_signature": signature,
                "installed_packages": [],
                "requirements_changed": False,
                "requirements_file": str(requirements_file),
            }

    discovered_imports = sorted(discover_import_roots(project_root, normalized_targets))
    required_packages = resolve_required_packages(project_root, normalized_targets)
    if extra_packages:
        required_packages = sorted(set(required_packages) | set(extra_packages))

    installed_packages: List[str] = []
    missing_imports = detect_missing_imports(project_root, normalized_targets)
    if install_missing:
        import_to_dist = _import_to_distribution_map()
        missing_packages = _resolve_missing_packages(missing_imports, import_to_dist, extra_packages=extra_packages)
        if missing_packages:
            installed_packages = install_packages(
                python_executable,
                missing_packages,
                installer=installer,
            )

    requirements_changed = False
    requirements_entries: List[str] = []
    if sync_requirements:
        requirements_entries = generate_requirements_entries(required_packages, pin_versions=pin_versions)
        requirements_changed = sync_requirements_file(requirements_file, requirements_entries)

    new_state = {
        "dependency_signature": signature,
        "updated_at": int(time.time()),
        "installed_packages": installed_packages,
        "requirements_file": str(requirements_file),
        "required_package_count": len(required_packages),
    }
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(new_state, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "skipped": False,
        "dependency_signature": signature,
        "imports": discovered_imports,
        "missing_imports": missing_imports,
        "required_packages": required_packages,
        "installed_packages": installed_packages,
        "requirements_changed": requirements_changed,
        "requirements_entries": requirements_entries,
        "requirements_file": str(requirements_file),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="自动扫描、安装并同步项目依赖")
    parser.add_argument("--project-root", default=".", help="项目根目录")
    parser.add_argument("--targets", nargs="*", default=list(DEFAULT_TARGETS), help="扫描目标")
    parser.add_argument("--python-executable", default=sys.executable, help="用于安装依赖的Python解释器")
    parser.add_argument("--requirements-file", default=DEFAULT_REQUIREMENTS_FILE, help="requirements 输出路径")
    parser.add_argument("--state-file", default=".deps_state.json", help="依赖状态文件路径")
    parser.add_argument("--extra-package", action="append", default=[], help="额外强制纳入的依赖包")
    parser.add_argument("--no-install", action="store_true", help="仅扫描，不安装缺失依赖")
    parser.add_argument("--no-sync-requirements", action="store_true", help="不更新 requirements 文件")
    parser.add_argument("--no-pin-versions", action="store_true", help="requirements 不固定版本")
    parser.add_argument("--no-skip-if-unchanged", action="store_true", help="源码未变化也强制执行")
    parser.add_argument("--json", action="store_true", help="输出 JSON 结果")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    project_root = Path(args.project_root).resolve()
    requirements_file = (project_root / args.requirements_file).resolve()
    state_file = (project_root / args.state_file).resolve()

    result = auto_manage_dependencies(
        project_root=project_root,
        targets=args.targets,
        python_executable=args.python_executable,
        requirements_file=requirements_file,
        state_file=state_file,
        extra_packages=args.extra_package,
        install_missing=not args.no_install,
        sync_requirements=not args.no_sync_requirements,
        pin_versions=not args.no_pin_versions,
        skip_if_unchanged=not args.no_skip_if_unchanged,
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("Dependency management completed")
        print(f"- skipped: {result.get('skipped')}")
        print(f"- requirements: {result.get('requirements_file')}")
        print(f"- requirements_changed: {result.get('requirements_changed')}")
        print(f"- installed_packages: {', '.join(result.get('installed_packages', [])) or 'None'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
