from __future__ import annotations

import importlib.util
import json
import os
import sys
import tomllib
from importlib import metadata
from pathlib import Path
from types import ModuleType


CLI_TOOLS = {
    "eyeflow": {
        "distribution": "EyeFlow",
        "project": "EyeFlow",
        "root_module": "eye_flow",
        "alias": "_doppler_manager_eyeflow_cli",
        "marker": "Run EyeFlow pipelines",
    },
    "angioeye": {
        "distribution": "AngioEye",
        "project": "AngioEye",
        "root_module": "angio_eye",
        "alias": "_doppler_manager_angioeye_cli",
        "marker": "Run AngioEye pipelines",
    },
}


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        available = ", ".join(sorted(CLI_TOOLS))
        print(f"Expected one CLI tool name: {available}", file=sys.stderr)
        return 2

    tool = args.pop(0).lower()
    try:
        tool_config = CLI_TOOLS[tool]
    except KeyError:
        available = ", ".join(sorted(CLI_TOOLS))
        print(f"Unknown CLI tool '{tool}'. Expected one of: {available}", file=sys.stderr)
        return 2

    if tool == "eyeflow":
        import doppler_manager._eyeflow_runtime_limits as runtime_limits

        sys.modules.setdefault("runtime_limits", runtime_limits)

    try:
        cli_module = _load_tool_cli(tool_config)
    except Exception as exc:  # noqa: BLE001
        print(f"Could not load {tool} CLI: {exc}", file=sys.stderr)
        return 1

    return int(cli_module.main(args))


def _load_tool_cli(tool_config: dict[str, str]) -> ModuleType:
    cli_path = _find_uv_git_cli(tool_config)
    if cli_path is None:
        cli_path = _find_installed_sibling_cli(tool_config["root_module"])
    _validate_cli_marker(cli_path, tool_config["marker"])
    return _load_cli_from_path(cli_path, tool_config["alias"])


def _find_uv_git_cli(tool_config: dict[str, str]) -> Path | None:
    try:
        dist = metadata.distribution(tool_config["distribution"])
    except metadata.PackageNotFoundError:
        return None

    direct_url_text = dist.read_text("direct_url.json")
    if not direct_url_text:
        return None

    try:
        direct_url = json.loads(direct_url_text)
    except json.JSONDecodeError:
        return None

    commit_id = direct_url.get("vcs_info", {}).get("commit_id")
    if not commit_id:
        return None

    commit_prefix = commit_id[:7].lower()
    for cache_root in _uv_cache_roots():
        checkout_root = cache_root / "git-v0" / "checkouts"
        if not checkout_root.is_dir():
            continue
        for pyproject_path in checkout_root.rglob("pyproject.toml"):
            if not any(part.lower().startswith(commit_prefix) for part in pyproject_path.parts):
                continue
            if _project_name(pyproject_path) != tool_config["project"].lower():
                continue
            cli_path = pyproject_path.parent / "src" / "cli.py"
            if cli_path.is_file():
                return cli_path
    return None


def _uv_cache_roots() -> list[Path]:
    candidates: list[Path] = []
    if os.getenv("UV_CACHE_DIR"):
        candidates.append(Path(os.environ["UV_CACHE_DIR"]))
    if os.getenv("LOCALAPPDATA"):
        candidates.append(Path(os.environ["LOCALAPPDATA"]) / "uv" / "cache")
    if os.getenv("XDG_CACHE_HOME"):
        candidates.append(Path(os.environ["XDG_CACHE_HOME"]) / "uv")
    candidates.append(Path.home() / ".cache" / "uv")

    roots: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        try:
            resolved = candidate.expanduser().resolve()
        except OSError:
            resolved = candidate.expanduser().absolute()
        if resolved not in seen:
            seen.add(resolved)
            roots.append(resolved)
    return roots


def _project_name(pyproject_path: Path) -> str | None:
    try:
        payload = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return None
    name = payload.get("project", {}).get("name")
    return name.lower() if isinstance(name, str) else None


def _find_installed_sibling_cli(root_module: str) -> Path:
    root_spec = importlib.util.find_spec(root_module)
    if root_spec is None or root_spec.origin is None:
        raise ModuleNotFoundError(root_module)
    return Path(root_spec.origin).with_name("cli.py")


def _validate_cli_marker(cli_path: Path, marker: str) -> None:
    try:
        text = cli_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise FileNotFoundError(f"Cannot read CLI file: {cli_path}") from exc
    if marker not in text:
        raise RuntimeError(
            f"Resolved CLI does not match the expected tool: {cli_path}. "
            "Install processing dependencies with uv, or set the matching DM_*_COMMAND override."
        )


def _load_sibling_cli(root_module: str, cli_alias: str) -> ModuleType:
    cli_path = _find_installed_sibling_cli(root_module)
    return _load_cli_from_path(cli_path, cli_alias)


def _load_cli_from_path(cli_path: Path, cli_alias: str) -> ModuleType:
    if not cli_path.is_file():
        raise FileNotFoundError(f"CLI file not found: {cli_path}")
    source_dir = str(cli_path.parent)
    if source_dir in sys.path:
        sys.path.remove(source_dir)
    sys.path.insert(0, source_dir)

    cli_spec = importlib.util.spec_from_file_location(cli_alias, cli_path)
    if cli_spec is None or cli_spec.loader is None:
        raise ImportError(f"Cannot load CLI module from {cli_path}")

    module = importlib.util.module_from_spec(cli_spec)
    sys.modules[cli_alias] = module
    cli_spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    raise SystemExit(main())
