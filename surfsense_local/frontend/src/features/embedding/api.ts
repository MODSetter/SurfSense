import { requestJson } from "@/lib/api"

export type EmbeddingIndex = {
  name: string
  spec: {
    id: string
    source: "curated" | "huggingface" | "remote"
    identified: "measured" | "declared" | "inferred" | "unverified"
    dimension: number
  }
}

/** Which search model the library is built with. Null before onboarding. */
export type EmbeddingIndexRead = {
  active: EmbeddingIndex | null
  building: EmbeddingIndex | null
}

export function getEmbeddingIndex(
  signal?: AbortSignal
): Promise<EmbeddingIndexRead> {
  return requestJson<EmbeddingIndexRead>("/embedding/index", { signal })
}
