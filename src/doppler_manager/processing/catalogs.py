from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future
from threading import Lock, Thread
from typing import TypeVar, cast


T = TypeVar("T")

_catalog_lock = Lock()
_catalog_futures: dict[str, Future[object]] = {}


def load_catalog(key: str, loader: Callable[[], T]) -> T:
    """Return a catalog, sharing any background preload already in progress."""

    with _catalog_lock:
        future = _catalog_futures.get(key)
    if future is not None:
        return cast(T, future.result())
    return loader()


def preload_catalog(key: str, loader: Callable[[], T]) -> bool:
    """Start one daemon preload for a catalog key if it has not started yet."""

    with _catalog_lock:
        if key in _catalog_futures:
            return True
        future: Future[object] = Future()
        _catalog_futures[key] = future

    Thread(
        target=_run_catalog_loader,
        args=(future, loader),
        daemon=True,
        name=f"processing-catalog-{key.replace(':', '-')}",
    ).start()
    return True


def _run_catalog_loader(
    future: Future[object],
    loader: Callable[[], T],
) -> None:
    try:
        future.set_result(loader())
    except BaseException as exc:  # noqa: BLE001
        future.set_exception(exc)


__all__ = ["load_catalog", "preload_catalog"]
