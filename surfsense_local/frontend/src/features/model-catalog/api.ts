import { request, requestJson, requestVoid } from "@/lib/api"
import type { ModelSelection } from "@/features/model-selection/api"

/**
 * Where a model's weights will live. Three states, and no `unknown`: every row
 * has a file size, so every row can be priced.
 */
export type FitState = "fits" | "partial" | "too_big"

export type Fit = {
  state: FitState
  need_bytes: number
  budget_bytes: number
  /**
   * 0 fully resident, 1 entirely on the processor. The reason line is graded by
   * this, and it is never recomputed here: the same number drives the badge and
   * the recommendation, so they cannot disagree.
   */
  offload_fraction: number
  /** Priced from file size alone, before the header was read. */
  approximate: boolean
}

/** A verdict plus one plain line of why. The API owns this copy. */
export type Badge = {
  verdict: string
  reason: string
}

export type CatalogRow = {
  /** Opaque install token. The renderer never assembles one. */
  catalog_id: string
  /** Stable identity of the model, used as a React key. */
  model_id: string
  /** What the runtime calls the installed file, for selection and deletion. */
  variant_model_id: string
  label: string
  family: string
  parameter_count: string
  quantization: string
  size_bytes: number
  context_length: number
  fit: Fit
  badge: Badge
  capabilities: string[]
  installed: boolean
  selected: boolean
  can_install: boolean
  recommended: boolean
}

export type InstalledRow = {
  model_id: string
  file: string
  size_bytes: number
  selected: boolean
}

/** One device, never a sum across devices. */
export type Budget = {
  device_total_bytes: number
  device_free_bytes: number
  usable_vram_bytes: number
  fit_reserve_bytes: number
  ram_available_bytes: number
  /** Unified memory: selects badge copy, since there is nothing to spill into. */
  uma: boolean
  has_gpu: boolean
}

/**
 * Curated plus installed. No `scanned` flag, because there is no scan: the
 * budget comes from the runtime's own allocator in about 180ms.
 */
export type ModelCatalog = {
  budget: Budget
  curated: CatalogRow[]
  installed: InstalledRow[]
  recommended_model_id: string | null
}

/** A repo, described. Search rows carry no rank and no quality claim. */
export type SearchRow = {
  repo: string
  downloads: number
  likes: number
  license: string | null
  gated: boolean
  /** "quantized from Qwen/Qwen3-8B", which is provenance and not a grade. */
  quantized_from: string | null
  last_modified: string | null
}

export type RepoBuild = {
  catalog_id: string
  file: string
  quantization: string
  size_bytes: number
  fit: Fit
  badge: Badge
  can_install: boolean
}

export type RepoDetail = {
  repo: string
  architecture: string
  context_length: number
  supported: boolean
  builds: RepoBuild[]
  /** Eligibility is not fit: a model can fit and still be refused here. */
  ineligible_reason: string | null
}

export type InstallEvent =
  | {
      // `preparing` is the wait for the runtime to restart and pick the model
      // up; the router learns about a new file only at startup.
      type: "starting" | "verifying" | "preparing" | "selecting"
      message?: string
    }
  | {
      type: "downloading"
      message?: string
      completed: number
      total: number
    }
  | { type: "complete"; message?: string; selection: ModelSelection }
  | { type: "error"; message: string }

export type DeleteModelResult = {
  name: string
  selection_cleared: boolean
}

export async function* parseNdjson<T>(
  stream: ReadableStream<Uint8Array>
): AsyncGenerator<T> {
  const reader = stream.getReader()
  const decoder = new TextDecoder()
  let buffer = ""

  try {
    while (true) {
      const { value, done } = await reader.read()
      buffer += decoder.decode(value, { stream: !done })
      const lines = buffer.split(/\r?\n/)
      buffer = lines.pop() ?? ""

      for (const line of lines) {
        if (line.trim()) {
          yield JSON.parse(line) as T
        }
      }

      if (done) {
        if (buffer.trim()) {
          yield JSON.parse(buffer) as T
        }
        return
      }
    }
  } finally {
    reader.releaseLock()
  }
}

export type LocalImageModel = {
  name: string
  label: string
  detail: string
  size_bytes: number
  installed: boolean
  selected: boolean
}

/** `offered` is false where no sd-server shipped for the platform. */
export type LocalImageCatalog = {
  provider: string
  offered: boolean
  ready: boolean
  models: LocalImageModel[]
}

export type DownloadStep = {
  status: string
  completed: number
  total: number
}

export function getLocalImageCatalog(
  signal?: AbortSignal
): Promise<LocalImageCatalog> {
  return requestJson<LocalImageCatalog>("/llm/image/local", { signal })
}

export function deleteLocalImageModel(
  name: string,
  signal?: AbortSignal
): Promise<void> {
  return requestVoid(`/llm/image/local/${encodeURIComponent(name)}`, {
    method: "DELETE",
    signal,
  })
}

export async function installLocalImageModel(
  name: string,
  onStep: (step: DownloadStep) => void,
  signal?: AbortSignal
): Promise<void> {
  const response = await request(
    `/llm/image/local/${encodeURIComponent(name)}/install`,
    { method: "POST", signal }
  )
  if (!response.body) throw new Error("The download returned no progress")
  for await (const step of parseNdjson<DownloadStep>(response.body)) {
    onStep(step)
  }
}

export function getModelCatalog(signal?: AbortSignal): Promise<ModelCatalog> {
  return requestJson<ModelCatalog>("/llm/catalog", { signal })
}

export function getSystem(signal?: AbortSignal): Promise<{ budget: Budget }> {
  return requestJson<{ budget: Budget }>("/llm/system", { signal })
}

export function searchModels(
  query: string,
  signal?: AbortSignal
): Promise<{ results: SearchRow[] }> {
  return requestJson<{ results: SearchRow[] }>(
    `/llm/search?q=${encodeURIComponent(query)}`,
    { signal }
  )
}

/**
 * Reads 2 to 4 MB of the model's header, so the trigger is opening a result
 * rather than hovering or typing. The list badge stays approximate until then.
 */
export function getRepoDetail(
  repo: string,
  signal?: AbortSignal
): Promise<RepoDetail> {
  return requestJson<RepoDetail>(`/llm/search/${repo}`, { signal })
}

export async function installCatalogModel(
  catalogId: string,
  onEvent: (event: InstallEvent) => void,
  signal?: AbortSignal
): Promise<ModelSelection> {
  const response = await request("/llm/install", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ catalog_id: catalogId, select: true }),
    signal,
  })
  if (!response.body) {
    throw new Error("The install stream ended before completion")
  }

  for await (const event of parseNdjson<InstallEvent>(response.body)) {
    onEvent(event)
    if (event.type === "error") {
      throw new Error(event.message)
    }
    if (event.type === "complete") {
      return event.selection
    }
  }
  throw new Error("The install stream ended before completion")
}

export function deleteLocalModel(modelId: string): Promise<DeleteModelResult> {
  return requestJson<DeleteModelResult>(
    `/llm/models/${encodeURIComponent(modelId)}`,
    { method: "DELETE" }
  )
}
