import type { RepoDetail, SearchRow } from "@/features/models/local/chat/api"
import type { SearchSource } from "@/features/models/local/chat/search-source"
import { requestJson } from "@/lib/api"

/** ONNX embedders on Hugging Face, answered in the GGUF search's shapes. */
export const EMBEDDING_SEARCH: SearchSource = {
  key: "embedding",
  search: (query, signal) =>
    requestJson<{ results: SearchRow[] }>(
      `/embedding/huggingface/search?q=${encodeURIComponent(query)}`,
      { signal }
    ),
  repo: (repo, signal) =>
    requestJson<RepoDetail>(`/embedding/huggingface/repo/${repo}`, { signal }),
}
