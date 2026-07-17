from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from doppler_manager.processing.core.commands import command_prefix_for_stage
from doppler_manager.processing.core.models import ProcessingJob


POSTPROCESS_INPUT_METHODS = (
    "single_file",
    "file_batch",
    "cohort_batch",
    "zip_batch",
)


@dataclass(frozen=True)
class AngioEyePostprocessDescriptor:
    """Metadata copied from one AngioEye postprocess decorator."""

    name: str
    description: str = ""
    input_methods: tuple[str, ...] = POSTPROCESS_INPUT_METHODS
    available: bool = True
    missing_deps: tuple[str, ...] = ()
    required_pipelines: tuple[str, ...] = ()
    required_pipeline_options: tuple[tuple[str, ...], ...] = ()
    required_options: tuple[str, ...] = ()
    missing_pipelines: tuple[str, ...] = ()
    visibility: str = "visible"


def discover_angioeye_postprocesses() -> tuple[AngioEyePostprocessDescriptor, ...]:
    """Discover postprocesses through AngioEye's decorator registry.

    AngioEye is an optional processing dependency. Discovery therefore stays
    best-effort so the main scan UI remains usable when AngioEye is absent.
    Older installed AngioEye versions do not expose ``input_methods`` yet;
    those descriptors cannot be proposed safely because their supported input
    modes are unknown.
    """

    try:
        descriptors = _discover_from_catalog(_load_angioeye_postprocess_catalog)
    except Exception:  # noqa: BLE001
        return ()
    return descriptors


@lru_cache(maxsize=8)
def _discover_from_catalog(loader) -> tuple[AngioEyePostprocessDescriptor, ...]:
    available, missing = loader()
    descriptors = [
        _descriptor_from_upstream(item, available=True)
        for item in available
    ]
    descriptors.extend(
        _descriptor_from_upstream(item, available=False)
        for item in missing
    )
    return tuple(sorted(descriptors, key=lambda item: item.name.lower()))


def proposed_angioeye_postprocesses(
    postprocesses: Iterable[AngioEyePostprocessDescriptor],
    input_count: int,
    selected_pipelines: Iterable[str] | None = None,
) -> tuple[AngioEyePostprocessDescriptor, ...]:
    """Return visible postprocesses compatible with the selected file count.

    The manager currently discovers source HDF5 outputs through acquisitions,
    so ZIP input is not a selectable input mode here. A single acquisition is
    a ``single_file`` run; two or more acquisitions form a ``file_batch``.
    ``cohort_batch`` is deliberately not inferred from an acquisition count.

    When AngioEye pipelines are selected for the same run, their DAG upstream
    pipelines are included before checking postprocess requirements. This is
    important for a downstream selection such as ``pdf_generator``: its
    selected target may not explicitly contain the ``waveform_shape_metrics``
    pipeline required by a postprocess, even though the AngioEye DAG will run
    that upstream pipeline first.

    ``None`` means that no AngioEye pipeline run is pending. In that case the
    existing-output workflow is responsible for checking pipeline data in the
    HDF5 file; the catalog's own availability result is used here.
    """

    method = input_method_for_count(input_count)
    if method is None:
        return ()

    candidates = tuple(
        postprocess
        for postprocess in postprocesses
        if postprocess.visibility != "hidden"
        and method in postprocess.input_methods
    )
    if not candidates:
        return ()

    effective_pipelines = (
        None
        if selected_pipelines is None
        else (
            _selected_pipeline_closure(selected_pipelines)
            if any(_pipeline_options_for(postprocess) for postprocess in candidates)
            else frozenset()
        )
    )
    return tuple(
        postprocess
        for postprocess in candidates
        if _postprocess_is_available_for_selection(postprocess, effective_pipelines)
    )


def input_method_for_count(input_count: int) -> str | None:
    if input_count == 1:
        return "single_file"
    if input_count > 1:
        return "file_batch"
    return None


def build_angioeye_postprocess_call(
    input_paths: Sequence[Path] | Path,
    postprocess_file: Path,
    pipeline_file: Path | None = None,
) -> tuple[str, ...]:
    """Build a postprocess-only AngioEye invocation.

    Pass actual HDF5 inputs to the filesystem workflow. A manager-generated
    Holo ``.txt`` list is not valid for AngioEye's postprocess-only dispatch:
    that route treats each entry in ``request.holo_paths`` as an actual Holo
    path and does not expand the list file.
    """

    if isinstance(input_paths, Path):
        paths = (input_paths,)
    else:
        paths = tuple(input_paths)
    if not paths:
        raise ValueError("At least one AngioEye postprocess input is required.")

    command: tuple[str, ...] = (*command_prefix_for_stage("ae"),)
    for input_path in paths:
        command += ("--data", str(input_path))
    if pipeline_file is not None:
        command += ("--pipelines", str(pipeline_file))
    return command + (
        "--postprocesses",
        str(postprocess_file),
    )


def build_angioeye_postprocess_job(
    input_paths: Sequence[Path] | Path,
    postprocess_file: Path,
    postprocess_names: Sequence[str],
    *,
    pipeline_file: Path | None = None,
) -> ProcessingJob:
    names = tuple(
        str(name).strip() for name in postprocess_names if str(name).strip()
    )
    if isinstance(input_paths, Path):
        paths = (input_paths,)
    else:
        paths = tuple(input_paths)
    if not paths:
        raise ValueError("At least one AngioEye postprocess input is required.")
    label = ", ".join(names) if names else "selected steps"
    return ProcessingJob(
        acquisition_id="__angioeye_postprocess__",
        stage="ae_postprocess",
        command=build_angioeye_postprocess_call(
            paths,
            postprocess_file,
            pipeline_file,
        ),
        cwd=paths[0].parent,
        description=f"AngioEye postprocess: {label}",
    )


def _load_angioeye_postprocess_catalog():
    from postprocess import load_postprocess_catalog

    return load_postprocess_catalog()


def _load_angioeye_pipeline_catalog():
    from pipelines import load_pipeline_catalog

    return load_pipeline_catalog()


@lru_cache(maxsize=8)
def _pipeline_catalog_for(loader):
    return loader()


def _postprocess_is_available_for_selection(
    postprocess: AngioEyePostprocessDescriptor,
    selected_pipelines: frozenset[str] | None,
) -> bool:
    if postprocess.visibility == "hidden" or postprocess.missing_deps:
        return False

    required_options = _pipeline_options_for(postprocess)
    if selected_pipelines is None:
        return postprocess.available and not postprocess.missing_pipelines

    if not _pipeline_options_are_satisfied(required_options, selected_pipelines):
        return False

    # AngioEye's postprocess catalog currently puts descriptors with missing
    # pipeline names in its ``missing`` result. A selected pipeline (or one of
    # its DAG upstreams) can satisfy that requirement for this pending run.
    # Other unavailable descriptors still remain unavailable.
    return postprocess.available or bool(postprocess.missing_pipelines)


def _pipeline_options_for(
    postprocess: AngioEyePostprocessDescriptor,
) -> tuple[tuple[str, ...], ...]:
    if postprocess.required_pipeline_options:
        return tuple(
            tuple(name for name in option if name)
            for option in postprocess.required_pipeline_options
            if option
        )
    return tuple((name,) for name in postprocess.required_pipelines if name)


def _pipeline_options_are_satisfied(
    options: tuple[tuple[str, ...], ...],
    selected_pipelines: frozenset[str],
) -> bool:
    return all(
        any(name in selected_pipelines for name in option)
        for option in options
    )


def _selected_pipeline_closure(
    selected_pipelines: Iterable[str],
) -> frozenset[str]:
    selected = frozenset(
        str(name).strip() for name in selected_pipelines if str(name).strip()
    )
    if not selected:
        return selected

    try:
        available, missing = _pipeline_catalog_for(_load_angioeye_pipeline_catalog)
    except Exception:  # noqa: BLE001
        return selected

    descriptors = tuple((*available, *missing))
    by_name = {
        str(getattr(descriptor, "name", "")).strip(): descriptor
        for descriptor in descriptors
        if str(getattr(descriptor, "name", "")).strip()
    }
    producers: dict[str, str] = {}
    for descriptor in descriptors:
        name = str(getattr(descriptor, "name", "")).strip()
        for key in _pipeline_output_keys(descriptor):
            producers.setdefault(key, name)

    dependencies: dict[str, set[str]] = {}
    for name, descriptor in by_name.items():
        dependencies[name] = set()
        for required_key in _dag_required_keys(descriptor):
            dependency = producers.get(required_key)
            if dependency is not None and dependency != name:
                dependencies[name].add(dependency)

    closure = set(selected)
    pending = list(selected)
    while pending:
        name = pending.pop()
        for dependency in dependencies.get(name, ()):
            if dependency not in closure:
                closure.add(dependency)
                pending.append(dependency)
    return frozenset(closure)


def _pipeline_output_keys(descriptor) -> tuple[str, ...]:
    name = str(getattr(descriptor, "name", "")).strip()
    produced = getattr(descriptor, "dag_produces", ()) or ()
    produced_keys = (str(key).strip() for key in produced if str(key).strip())
    return tuple(dict.fromkeys((name, *produced_keys)))


def _dag_required_keys(descriptor) -> tuple[str, ...]:
    required = getattr(descriptor, "dag_requires", ()) or ()
    return tuple(str(key).strip() for key in required if str(key).strip())


def _descriptor_from_upstream(
    upstream,
    *,
    available: bool,
) -> AngioEyePostprocessDescriptor:
    input_methods = _input_methods_for(upstream)
    required_options = getattr(upstream, "required_option", None)
    if required_options is None:
        required_options = getattr(upstream, "required_options", ())
    if isinstance(required_options, str):
        required_options = (required_options,)

    pipeline_options = getattr(upstream, "required_pipeline_options", ()) or ()
    return AngioEyePostprocessDescriptor(
        name=str(getattr(upstream, "name", "")).strip(),
        description=str(getattr(upstream, "description", "") or "").strip(),
        input_methods=input_methods,
        available=bool(getattr(upstream, "available", available)) and available,
        missing_deps=tuple(
            str(value) for value in (getattr(upstream, "missing_deps", ()) or ())
        ),
        required_pipelines=tuple(
            str(value) for value in (getattr(upstream, "required_pipelines", ()) or ())
        ),
        required_pipeline_options=tuple(
            tuple(str(value) for value in option)
            for option in pipeline_options
            if option
        ),
        required_options=tuple(str(value) for value in required_options or ()),
        missing_pipelines=tuple(
            str(value)
            for value in (getattr(upstream, "missing_pipelines", ()) or ())
        ),
        visibility=str(getattr(upstream, "visibility", "visible") or "visible"),
    )


def _input_methods_for(upstream) -> tuple[str, ...]:
    methods = getattr(upstream, "input_methods", None)
    if methods is None:
        # A catalog from an AngioEye version predating decorator input-method
        # metadata cannot be classified safely. Fail closed rather than
        # offering, for example, a cohort-only postprocess for one file.
        return ()
    normalized: list[str] = []
    for method in methods:
        value = str(method).strip()
        if value and value not in normalized:
            normalized.append(value)
    return tuple(normalized)


__all__ = [
    "AngioEyePostprocessDescriptor",
    "POSTPROCESS_INPUT_METHODS",
    "build_angioeye_postprocess_call",
    "build_angioeye_postprocess_job",
    "discover_angioeye_postprocesses",
    "input_method_for_count",
    "proposed_angioeye_postprocesses",
]
