# Roadmap

What the maintainers are working on, grouped by when. This page names the initiatives and points at the design each one builds on; the tasks and their state belong in GitHub issues, not here. There are no target dates here, only deadlines that are already fixed.

## Now

- **Release and CI health.** v2.0.3 was the first release to carry the llama.cpp, sd.cpp and audio.cpp runtimes, built and packaged on all three runners, and [`desktop-tests.yml`](../.github/workflows/desktop-tests.yml) runs the desktop backend, frontend and Electron tests on pull requests. What is left is the CI that proves the runtimes: no job generates an image with the staged `sd-server`, and the release workflow still accepts a prerelease version. See [packaging](architecture/packaging.md) and [updates](architecture/updates.md).
- **Egress gaps.** The follow-up fetch for a remote image URL leaves without a consent decision, and some stored grants no longer match what Settings › Network shows. See [egress](architecture/egress.md).
- **Import from cloud.** The hosted export window closes on 18 Oct 2026. Imports need a progress summary, and a re-run must bring back the chat threads an interrupted import missed. See [import](architecture/import.md).
- **Scraper API and MCP license mode.** PATs are purged on 18 Oct 2026; after that, license mode is how scraper API and MCP users keep access. See [contract 2](contracts/02-scraper-api-auth.md).
- **Model catalog.** One catalog for local and remote models, each classified offline from a reviewed, packaged manifest and keyed by model type. See the [proposal](proposals/model-catalog.md).
- **Hosted wind-down to 18 Oct 2026.** `/sunset` lacks the deletion date, the refund offer and the MCP change; background jobs keep running through the export-only tail; and the purge is still ahead. See [sunset](architecture/sunset.md), the [license portal](architecture/license/portal.md) and the page plan in [`plans/community-local/portal/02-pages.md`](../plans/community-local/portal/02-pages.md).
- **Plugins.** Redesigned: a plugin is an MCP server the agent, the chat engine and the user call through one Tool Gateway, remote servers hosted by their publishers first, with SurfSense's paid scrapers as the first paid plugin once the scraper API has license mode. The earlier local runner is kept for bundles later. See the [proposal](proposals/plugins/README.md) and ADRs [0051](adr/0051-plugins-are-mcp-servers-behind-one-tool-gateway.md) to [0053](adr/0053-plugins-are-listed-in-a-registry-and-third-party-ones-start-off.md).
- **Agent.** In progress: a chat thread can be the agent's, answered in steps by opencode over the workspace's extracted text, with SurfSense's search and Studio, for a model known to call tools. opencode stays out of installers and dev runs until a model passes the agent test. Next is that test; every other model will run fixed workflows with structured output. Outputs first: nothing edits the user's files. See [agent](architecture/agent.md), the [proposal](proposals/agent/README.md) and [ADR 0028](adr/0028-model-written-code-runs-with-approval.md).

## Next

- **Studio.** Four Office formats break the builder rule, podcasts are WAV only, and deleting an artifact through the documents route leaves its files behind. See [Studio](architecture/studio.md).
- **Local models follow-ups.** What the llama.cpp runtime left open: bugs in fit and fingerprinting, install screen gaps, adding a `.gguf` from disk, and constrained decoding. See [local models](architecture/local-models/runtime.md).
- **Desktop app gaps.** Small, bounded gaps in documents, freshness and license settings, plus folders, which need a design first. See [documents](architecture/documents.md).
- **Chat eval.** Score the chat's answers on every curated chat model: up to 8B on the real files on our own machines, 8B to 32B on Featherless, with 8B in both places as the check. See the [proposal](proposals/chat-eval.md).
- **Retrieval: a multilingual embedder.** Ranking is done and measured; the remaining gap is that a question in one language does not find its answer in another, which no ranking change reaches. The swap is small and the re-embed migration is the work. See the [proposal](proposals/retrieval.md) and [search](architecture/search.md).

## Later

- **CUDA backend.** Deferred until a measurement shows it is worth 685 MB. See the [proposal](proposals/cuda-backend.md).
- **Reranker.** ADR 0006 names a cross-encoder reranker as a later opt-in; it needs a design first. See [search](architecture/search.md).
