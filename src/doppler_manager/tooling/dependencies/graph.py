"""Artifact identities, app ownership and resolved dependency edges."""
from __future__ import annotations

import platform
import sys
import tomllib
from pathlib import Path
from urllib.parse import parse_qs, urlsplit, urlunsplit

from packaging.markers import Marker, default_environment
from packaging.tags import compatible_tags, cpython_tags
from packaging.utils import canonicalize_name, parse_wheel_filename
from .lock import SCHEMA, digest

def marker_env(version: str) -> dict[str, str]:
    env = default_environment()
    env.update(python_version=".".join(version.split(".")[:2]), python_full_version=version,
               implementation_version=version)
    return env


def artifact(package: dict, version: str) -> dict:
    major, minor = map(int, version.split(".")[:2])
    if sys.platform == "win32":
        platforms = ["win_amd64"] if platform.machine().endswith("64") else ["win32"]
    else:
        from packaging.tags import platform_tags
        platforms = list(platform_tags())
    tags = list(cpython_tags((major, minor), platforms=platforms))
    tags += list(compatible_tags((major, minor), platforms=platforms))
    rank = {tag: i for i, tag in enumerate(tags)}
    choices = []
    for wheel in package.get("wheels", []):
        filename = Path(urlsplit(wheel["url"]).path).name
        wheel_tags = parse_wheel_filename(filename)[3]
        score = min((rank[t] for t in wheel_tags if t in rank), default=None)
        if score is not None:
            choices.append((score, wheel["url"], wheel, wheel_tags))
    if choices:
        _, _, wheel, tags = min(choices, key=lambda item: item[:2])
        return {"url": wheel["url"], "hash": wheel["hash"],
                "abi": "pure" if all(t.abi == "none" and t.platform == "any" for t in tags) else version}
    if "sdist" in package:
        return {**{k: package["sdist"][k] for k in ("url", "hash")}, "abi": version}
    source = package["source"]
    if "git" in source:
        url = urlsplit(source["git"])
        if len(url.fragment) != 40:
            raise RuntimeError(f"Unpinned Git source: {source}")
        subdir = parse_qs(url.query).get("subdirectory", [])
        git = urlunsplit((url.scheme, url.netloc, url.path, "", ""))
        return {"git": (git if git.startswith("git+") else "git+" + git) + "@" + url.fragment + ("#subdirectory=" + subdir[0] if subdir else ""),
                "abi": version}
    raise RuntimeError(f"No distributable artifact for {package['name']}: {source}")


def requirement(node: dict) -> str:
    item = node["artifact"]
    if "git" in item:
        return f"{node['name']} @ {item['git']}"
    return f"{node['name']} @ {item['url']}#{item['hash'].replace(':', '=', 1)}"


def graph_from_locks(assignments: dict[str, str], projects: dict, config: dict) -> dict:
    nodes: dict[str, dict] = {}
    apps = {}
    for app, version in assignments.items():
        lock = tomllib.loads((projects[app] / "uv.lock").read_text(encoding="utf-8"))
        selected = {}
        packages = {}
        virtual = None
        env = marker_env(version)
        for package in lock["package"]:
            if "virtual" in package["source"]:
                virtual = package
                continue
            # uv's per-version, per-platform project may still fork dependencies.
            markers = package.get("resolution-markers", [])
            if markers and not any(Marker(m).evaluate(env) for m in markers):
                continue
            item = artifact(package, version)
            identity = {"name": package["name"], "version": package["version"], "artifact": item}
            key = digest(identity)[:24]
            node = nodes.setdefault(key, {**identity, "consumers": [], "dependencies": package.get("dependencies", []),
                                          "requires_dist": package.get("metadata", {}).get("requires-dist", [])})
            node["consumers"].append(app)
            name = canonicalize_name(package["name"])
            if name in selected:
                raise RuntimeError(f"Ambiguous resolution for {app}: {name}")
            selected[name] = key
            packages[key] = package
        edges = []
        for key in selected.values():
            package = packages[key]
            dependencies = [(None, dep) for dep in package.get("dependencies", [])]
            dependencies += [(extra, dep) for extra, deps in package.get("optional-dependencies", {}).items() for dep in deps]
            for extra, dependency in dependencies:
                marker = dependency.get("marker")
                if marker and not Marker(marker).evaluate(env):
                    continue
                target = selected.get(canonicalize_name(dependency["name"]))
                if target:
                    edges.append({"from": key, "to": target, "requirement": dependency, "extra": extra})
        apps[app] = {"python": version, "nodes": sorted(selected.values()), "edges": edges,
                     "requirements": config["apps"][app]["requirements"],
                     "direct_dependencies": virtual.get("dependencies", []) if virtual else [],
                     "stage": config["apps"][app].get("stage")}
    return {"schema": SCHEMA, "input_hash": digest(config), "inputs": config,
            "apps": apps, "nodes": nodes, "python_versions": list(dict.fromkeys(assignments.values()))}
