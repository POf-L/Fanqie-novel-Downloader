# -*- coding: utf-8 -*-
"""项目依赖自动管理入口脚本。"""

from pathlib import Path
import sys


def main() -> int:
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from utils.dependency_manager import auto_manage_dependencies

    result = auto_manage_dependencies(
        project_root=project_root,
        targets=["main.py", "launcher.py", "core", "utils", "web", "config"],
        python_executable=sys.executable,
        requirements_file=project_root / "config" / "requirements.txt",
        state_file=project_root / ".deps_state.json",
        extra_packages=["requests", "rich", "InquirerPy", "aiohttp"],
        install_missing=True,
        sync_requirements=True,
        pin_versions=True,
        skip_if_unchanged=False,
    )

    print("依赖自动管理完成")
    print(f"- requirements_changed: {result.get('requirements_changed')}")
    print(f"- installed_packages: {', '.join(result.get('installed_packages', [])) or 'None'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
