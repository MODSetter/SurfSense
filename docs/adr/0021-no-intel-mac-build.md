# ADR 0021: There is no Intel Mac build

- **Status:** Accepted
- **Date:** 2026-09-14
- **Source:** [Pivot plan L80](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00d-pivot-plan.md#L80), [Pivot plan L83](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00d-pivot-plan.md#L83), [Pivot plan L231](https://github.com/MODSetter/SurfSense/blob/431914fae066e0c42a38b1fdbbab64e8f92d3d00/plans/community-local/00d-pivot-plan.md#L231)

## Context

The API and the worker are frozen into native binaries together with their Python dependencies. `torch` and `onnxruntime` no longer publish x86_64 macOS wheels; the release workflow notes that torch 2.3+ and onnxruntime 1.24+ ship none. macOS 26 is Apple's last Intel release. Packaging as built is in [packaging](../architecture/packaging.md).

## Decision

Apple Silicon only. Revisit only if users ask.

## Consequences

- The release matrix in [`.github/workflows/release-local.yml`](../../.github/workflows/release-local.yml) has one macOS runner, `macos-15`, marked Apple Silicon only. The `macos-15-intel` entry was removed.
- Installers ship for four targets: macOS arm64, Windows x64, Linux AppImage and Linux deb.
- A Mac with an Intel chip has no installer.
- The plugin interpreter proposal follows the same rule and has no Intel Mac asset ([`proposals/plugins/python/01-interpreter.md`](../proposals/plugins/python/01-interpreter.md)).
