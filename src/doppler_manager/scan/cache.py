from __future__ import annotations

import streamlit as st

from doppler_manager.scan.core import scan_root
from doppler_manager.scan.options import ScanOptions


@st.cache_data(show_spinner=False)
def _cached_scan(
    root: str,
    max_depth: int,
    max_entries: int,
    preview_limit: int,
    read_versions: bool,
    holo_filter_ids: tuple[str, ...] | None,
    holo_filter_entries: tuple[str, ...] | None,
):
    options = ScanOptions(
        max_depth=max_depth,
        max_entries=max_entries,
        preview_limit_per_stage=preview_limit,
        read_versions=read_versions,
        holo_filter_ids=set(holo_filter_ids) if holo_filter_ids is not None else None,
        holo_filter_entries=holo_filter_entries,
    )
    return scan_root(root, options)


def refresh_scan(root: str, options: ScanOptions):
    _cached_scan.clear()
    return scan_with_options(root, options)


def scan_with_options(root: str, options: ScanOptions):
    return _cached_scan(
        root,
        options.max_depth,
        options.max_entries,
        options.preview_limit_per_stage,
        options.read_versions,
        _holo_filter_cache_key(options),
        _holo_filter_entries_cache_key(options),
    )


def _holo_filter_cache_key(options: ScanOptions) -> tuple[str, ...] | None:
    if options.holo_filter_ids is None:
        return None
    return tuple(sorted(options.holo_filter_ids))


def _holo_filter_entries_cache_key(options: ScanOptions) -> tuple[str, ...] | None:
    if options.holo_filter_entries is None:
        return None
    return tuple(options.holo_filter_entries)
