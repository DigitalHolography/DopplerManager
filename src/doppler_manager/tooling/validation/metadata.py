"""Validate installed distributions against a resolved graph."""
from __future__ import annotations

import json
from importlib import metadata
from pathlib import Path

def validate_metadata(plan: dict, root: Path, *, output: Path) -> None:
    """Verify the installed distributions, including transitively enabled extras."""
    if output.resolve().is_relative_to(root.resolve()):
        raise ValueError("Validation output must be outside the runtime directory")
    from packaging.markers import default_environment
    from packaging.requirements import Requirement
    from packaging.specifiers import SpecifierSet
    from packaging.utils import canonicalize_name

    distributions = {}
    for key, node in plan["nodes"].items():
        candidates = list(metadata.distributions(path=[str(root / "packages" / key)]))
        matches = [d for d in candidates if canonicalize_name(d.metadata["Name"]) == canonicalize_name(node["name"])]
        if len(matches) != 1 or matches[0].version != node["version"]:
            raise RuntimeError(f"Installed artifact does not match graph: {node['name']}")
        distributions[key] = matches[0]
    report = {}
    for app, profile in plan["apps"].items():
        selected = {canonicalize_name(plan["nodes"][key]["name"]): key for key in profile["nodes"]}
        extras = {name: set() for name in selected}
        env = default_environment()
        env.update(python_version=".".join(profile["python"].split(".")[:2]),
                   python_full_version=profile["python"], implementation_version=profile["python"])
        edges = set()

        def check(text: str, parent: str) -> bool:
            req = Requirement(text)
            contexts = extras.get(parent, set()) | {""}
            if req.marker and not any(req.marker.evaluate({**env, "extra": extra}) for extra in contexts):
                return False
            name = canonicalize_name(req.name)
            if name not in selected:
                raise RuntimeError(f"{app}: {parent} requires missing {req}")
            key = selected[name]
            if plan["nodes"][key]["version"] not in req.specifier:
                raise RuntimeError(f"{app}: installed {name} violates {req}")
            edges.add((parent, name, str(req)))
            changed = not req.extras.issubset(extras[name])
            extras[name].update(req.extras)
            return changed

        for req in profile["requirements"]:
            check(req, app)
        changed = True
        while changed:
            changed = False
            for name, key in selected.items():
                dist = distributions[key]
                if profile["python"] not in SpecifierSet(dist.metadata.get("Requires-Python", "")):
                    raise RuntimeError(f"{app}: {name} does not support Python {profile['python']}")
                for req in dist.requires or []:
                    changed |= check(req, name)
        report[app] = [dict(parent=p, dependency=d, requirement=r) for p, d, r in sorted(edges)]
    output.mkdir(parents=True, exist_ok=True)
    (output / "installed-dependencies.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
