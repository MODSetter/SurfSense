import {
  getRepoDetail,
  searchModels,
  type RepoDetail,
  type SearchRow,
} from "./api"

/**
 * Where a Hugging Face search looks: one list renders every engine's search,
 * each answering in these shapes. `key` keeps their caches apart.
 */
export type SearchSource = {
  key: string
  search: (
    query: string,
    signal?: AbortSignal
  ) => Promise<{ results: SearchRow[] }>
  repo: (repo: string, signal?: AbortSignal) => Promise<RepoDetail>
}

/** GGUF repos, which llama.cpp runs. */
export const GGUF_SEARCH: SearchSource = {
  key: "gguf",
  search: searchModels,
  repo: getRepoDetail,
}
