# Roadmap

What the maintainers are working on, grouped by when. This page names the initiatives and points at the design each one builds on; the tasks and their state belong in GitHub issues, not here. There are no target dates here, only deadlines that are already fixed.

## Now

- **Release and CI health.** The next release is the first to carry the llama.cpp runtime, and no workflow runs the desktop tests on pull requests. See [packaging](architecture/packaging.md) and [updates](architecture/updates.md).
- **Egress gaps.** The follow-up fetch for a remote image URL leaves without a consent decision, Electron's spellchecker likely fetches dictionaries without one, and some stored grants no longer match what Settings › Network shows. See [egress](architecture/egress.md).
- **Import from cloud.** The hosted export window closes on 18 Oct 2026. Imports need a progress summary, and a re-run must bring back the chat threads an interrupted import missed. See [import](architecture/import.md).
- **Scraper API and MCP license mode.** PATs are purged on 18 Oct 2026; after that, license mode is how scraper API and MCP users keep access. See [contract 2](contracts/02-scraper-api-auth.md).
- **Hosted wind-down to 18 Oct 2026.** `/sunset` lacks the deletion date, the refund offer and the MCP change; background jobs keep running through the export-only tail; and the purge is still ahead. See [sunset](architecture/sunset.md), the [license portal](architecture/license/portal.md) and the page plan in [`plans/community-local/portal/02-pages.md`](../plans/community-local/portal/02-pages.md).

## Next

- **Plugins.** The plugin system, then the paid scraper plugin on top of it. See the [proposal](proposals/plugins/README.md).
- **Studio.** Four Office formats break the builder rule, podcasts are WAV only, and deleting an artifact through the documents route leaves its files behind. See [Studio](architecture/studio.md).
- **Local models follow-ups.** What the llama.cpp runtime left open: bugs in fit and fingerprinting, install screen gaps, vision, adding a `.gguf` from disk, and constrained decoding. See [local models](architecture/local-models/runtime.md).
- **Desktop app gaps.** Small, bounded gaps in documents, freshness and license settings, plus folders, which need a design first. See [documents](architecture/documents.md).

## Later

- **CUDA backend.** Deferred until a measurement shows it is worth 685 MB. See the [proposal](proposals/cuda-backend.md).
- **Reranker.** ADR 0006 names a cross-encoder reranker as a later opt-in; it needs a design first. See [search](architecture/search.md).
