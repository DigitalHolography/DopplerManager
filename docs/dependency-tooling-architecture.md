# Dependency and release tooling architecture

Status: implemented. Runtime code, developer tooling, committed dependency locks
and generated evidence have separate owners and locations.

The dependency graph remains the common input to development synchronization and
release packaging. This cleanup changes ownership and storage, rather than the
five apps' namespace separation or runtime selection policy.

## Source layout

```text
src/doppler_manager/
  runtime/
    apps.py                 App identities, CLI entry points and overrides
    manifest.py             Read a generation and construct its invocation
    bootstrap.py            Standalone isolated Python entry point
    external_process.py     Native-library isolation during child creation
    defaults.py             Runtime settings and legacy distribution lookup
  tooling/
    dependencies/
      manifest.py           Read declared inputs and pin upstream revisions
      resolver.py           Invoke uv for candidate Python versions
      graph.py              Construct artifact identities and app ownership
      lock.py               Read, verify and publish the selected lock bundle
      __main__.py           dependency-plan CLI
    environments.py         Install and publish immutable runtime generations
    validation/
      metadata.py           Verify installed requirements, markers and extras
      startup.py            Import and CLI probes in isolated app-data folders
      relocation.py         Validate a moved runtime or frozen bundle
      __main__.py           Shared validation CLI
    sync.py                 CLI orchestration for plan, refresh and sync
    release.py              Generate spec, stage payload and invoke PyInstaller
  processing/               Acquisition jobs, output handling and app integration
  ...                       Existing interface, scan and model code

scripts/
  sync_processing.ps1        Thin platform wrapper
  build_installer.ps1        Thin platform wrapper and Inno Setup invocation

tests/
  runtime/                  Manifest selection and namespace isolation
  tooling/                  Resolver, graph, synchronization and packaging tests
  integration/              Explicit runtime/frozen startup and relocation tests
```

Keeping tooling in `src` makes it installable through the existing `uv run sync`
entry point and testable through ordinary imports. Its namespace identifies it
as developer/build code. Runtime code must not import `tooling`; PyInstaller can
exclude that namespace from the shipped application. Shared app definitions and
generation-reading functions belong in `runtime`, where both sides can use them.

Keep a small number of cohesive modules at first. Split further only where the
current responsibilities are already substantial; avoid one module per helper.

## Lock storage

The selected dependencies are stored in a stable lock bundle:

```text
pyproject.toml                        Human-maintained dependency inputs
uv.lock                               Lock for the uv tool-host environment
dependencies/
  windows-x86_64/
    runtime-lock.json                 Selected Python versions and artifact graph
    apps/
      manager/{pyproject.toml,uv.lock}
      holodoppler/{pyproject.toml,uv.lock}
      dopplerview/{pyproject.toml,uv.lock}
      eyeflow/{pyproject.toml,uv.lock}
      angioeye/{pyproject.toml,uv.lock}
.cache/doppler-manager/               Ignored downloads and resolver workspaces
build/<run-id>/                       Ignored specs, payloads and test evidence
processing_runtimes/                  Ignored installed generations and pointer
```

Use a top-level `dependencies` directory because the lock bundle serves both
development and packaging. It is not exclusively a packaging asset. Platform
qualification prevents an incompatible machine from silently replacing a lock.

The committed lock bundle contains only selected projects. Candidate resolutions,
failed attempts, UUID work directories, Python downloads and reports belong in
the ignored cache or build directory. Git provides lock history; UUID revisions
do not need to duplicate that history in the committed tree.

The graph records selected artifact identity, hashes, Python assignments and app
ownership. The per-app uv locks preserve the resolver's complete resolution. The
graph is derived from those locks and checked against their hashes; do not edit
both independently. Human-readable summaries are generated reports.

A refresh stages a complete bundle, verifies it, and publishes it with a single
controlled directory replacement. On failure, retain the previous bundle. A
locked reader must reject partial or inconsistent files. Sync takes a verified
snapshot before installation so concurrent refreshes cannot mix lock revisions.
App processes read their installed generation manifest, not the source lock
bundle, so refreshing a lock never changes a running job's environment.

## Validation ownership

Reusable validation belongs in `tooling/validation`, with one documented CLI
entry point for installed runtimes and frozen bundles. Ad hoc probes such as the
initial missing-Python investigation remain disposable evidence under `build`.
Do not promote each historical probe script into an application module.

Validation takes explicit runtime, output and app-data paths. It must not write
reports or temporary app-data directories into a published runtime generation.
Required checks run before generation publication; subsequent diagnostics write
to a separate build run. Validation must not require real user acquisition data.
An optional copied acquisition fixture can exercise processing separately from
startup tests, with that distinction visible in the report.

## Maintained boundaries

- Runtime and app imports must not load `tooling`; an isolated import test
  enforces this, and the generated PyInstaller spec excludes tooling explicitly.
- Lock refreshes resolve under `.cache/doppler-manager/resolve`, publish only
  selected projects, and preserve the previous bundle if publication fails.
- A reader lock prevents observation of the replacement interval. Installation
  uses a private verified snapshot so a later refresh cannot mix its inputs.
- Lock migration preserves package artifacts and Python assignments; only paths
  and the path-dependent bundle ID change.
- Validation and relocation use explicit build output directories. A relocation
  failure restores the disposable build directory; diagnostics copy live inputs.
- Existing generations and legacy `.venv` fallbacks remain supported.

`processing_runtimes/` contains generated installations only and is fully ignored
by Git. EyeFlow supplies its own `runtime_limits.py`; DopplerManager neither copies
nor overrides it. Unused runtimes can be deleted and recreated with sync. Do not
delete a runtime that a running application or processing job is using.
