# Frontend — Phase 5: Install UX

## Goal

Download and airgap flows in packaged app.

## Work

- Model download progress (bytes, %, cancel).
- Disk space warning before download.
- Import from folder (airgap parser/model packs).
- Packaged app smoke: same flows as dev.

## Acceptance

- Path B: download progress → chat works after complete.
- Path A: import folder → app recognizes models/parser.

## Needs from API

Download manifest or paths — [`../api/05-packaging.md`](../api/05-packaging.md).
