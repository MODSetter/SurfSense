import { request, requestJson, requestVoid } from "@/lib/api"
import type { ModelSelection } from "@/features/model-selection/api"

export type Fit = "perfect" | "good" | "marginal" | "too_tight" | "unknown"

export type CatalogRow = {
  catalog_id: string
  canonical_id: string
  family: string
  label: string
  publisher: string | null
  parameter_count: string | number | null
  fit: Fit
  score: number | null
  memory_required_gb: number | null
  disk_size_gb: number | null
  estimated_tps: number | null
  prefill_tps: number | null
  ttft_ms: number | null
  effective_context_length: number | null
  estimate_confidence: string | null
  license: string | null
  runtime: string
  runtime_model: string
  quantization: string | null
  installed: boolean
  selected: boolean
  can_install: boolean
  can_delete: boolean
  warnings: string[]
}

export type RuntimeStatus =
  | string
  | boolean
  | {
      healthy?: boolean
      available?: boolean
      status?: string
      message?: string
    }

export type RecommendationWarning = {
  code: string
  message: string
}

export type HardwareProfile = {
  cpu_name: string | null
  cpu_cores: number | null
  total_ram_gb: number | null
  available_ram_gb: number | null
  has_gpu: boolean
  gpu_name: string | null
  gpu_vram_gb: number | null
  gpu_count: number
  backend: string | null
  unified_memory: boolean
}

export type ModelCatalog = {
  hardware: HardwareProfile | null
  llmfit_version: string | null
  // Always populated, scan-free — SurfSense's curated picks, shown with a
  // fit badge once scanned and without one before. Never contains a row
  // also present in `explore`.
  curated: CatalogRow[]
  explore: CatalogRow[]
  installed: CatalogRow[]
  // False when served without running the hardware scan (no cache existed
  // yet and none was requested this session) — `curated`/`installed` are
  // still fully populated either way, only `explore` and curated fit badges
  // are scan-derived.
  scanned: boolean
  warnings: RecommendationWarning[]
  runtime_status: Record<string, RuntimeStatus>
}

export type InstallEvent =
  | { type: "starting" | "verifying" | "selecting"; message?: string }
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

export function getModelCatalog(
  refresh = false,
  signal?: AbortSignal
): Promise<ModelCatalog> {
  return requestJson<ModelCatalog>(
    refresh ? "/llm/catalog?refresh=true" : "/llm/catalog",
    { signal }
  )
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

export function deleteLocalModel(
  provider: string,
  modelName: string
): Promise<DeleteModelResult> {
  return requestJson<DeleteModelResult>(
    `/llm/providers/${encodeURIComponent(provider)}/models/${encodeURIComponent(modelName)}`,
    { method: "DELETE" }
  )
}
