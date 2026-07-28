from __future__ import annotations

import contextlib
import json
import sys
from collections.abc import Iterable
from typing import Any


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1 or args[0] not in {"pipelines", "postprocesses"}:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "Expected exactly one catalog kind: pipelines or postprocesses.",
                }
            )
        )
        return 2

    try:
        with contextlib.redirect_stdout(sys.stderr):
            available, missing = _load_catalog(args[0])
        print(
            json.dumps(
                {
                    "ok": True,
                    "available": _serialize_catalog(
                        available,
                        kind=args[0],
                        available=True,
                    ),
                    "missing": _serialize_catalog(
                        missing,
                        kind=args[0],
                        available=False,
                    ),
                }
            )
        )
    except Exception as exc:  # noqa: BLE001
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
        )
        return 1
    return 0


def _load_catalog(kind: str):
    if kind == "pipelines":
        from pipelines import load_pipeline_catalog

        return load_pipeline_catalog()

    from postprocess import load_postprocess_catalog

    return load_postprocess_catalog()


def _serialize_catalog(
    records: Iterable[Any],
    *,
    kind: str,
    available: bool,
) -> list[dict[str, Any]]:
    fields = (
        (
            "name",
            "description",
            "requires",
            "missing_deps",
            "dag_requires",
            "dag_produces",
            "input_slot",
            "missing_pipelines",
            "error_msg",
            "visibility",
        )
        if kind == "pipelines"
        else (
            "name",
            "description",
            "requires",
            "missing_deps",
            "required_pipelines",
            "required_pipeline_options",
            "required_option",
            "input_methods",
            "missing_pipelines",
            "error_msg",
            "visibility",
        )
    )

    result: list[dict[str, Any]] = []
    for record in records:
        payload = {
            field: _json_value(getattr(record, field, None))
            for field in fields
            if hasattr(record, field)
        }
        payload["name"] = str(payload.get("name", "")).strip()
        payload["description"] = str(payload.get("description", "") or "").strip()
        payload["available"] = (
            bool(getattr(record, "available", available)) and available
        )
        result.append(payload)
    return result


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_value(item) for item in value]
    return str(value)


if __name__ == "__main__":
    raise SystemExit(main())
