import { request, requestJson } from "@/lib/api"

import type { ModelSelection } from "../../selection/api"
import { parseNdjson } from "../read-ndjson"

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

/**
 * A warning when there is one, plus one plain line of why. `none` means there
 * is nothing to flag: the verdict is empty and the reason, if any, is quiet.
 * The API owns this copy.
 */
export type Badge = {
  level: "none" | "notice" | "refuse"
  verdict: string
  reason: string
}

export type BuildFile = {
  role: "weights" | "projector"
  path: string
  size_bytes: number
}

/**
 * One build of a model: a set of files that runs as one. The same shape for a
 * curated, downloaded or searched model, so nothing here asks where it came
 * from. Every field is the server's answer; none is computed in the renderer.
 */
export type LocalBuild = {
  /** Opaque install token; empty for a build that cannot be installed. */
  catalog_id: string
  quantization: string
  /** Everything that lands on disk and loads together, projector included. */
  footprint_bytes: number
  files: BuildFile[]
  fit: Fit
  badge: Badge
  can_install: boolean
  /** What the runtime calls this build on disk, which Use and Delete act on. */
  installed_as: string | null
  selected: boolean
  /** The build to install on this machine. Curated models only. */
  recommended: boolean
  reads_images: boolean
  /** The projector's header was read. Until then a searched build's image
   *  support is what its listing names, not what its header says. */
  projector_checked: boolean
}

export type LocalSupport = {
  context: number | null
  reads_images: boolean
  tools: boolean | null
  reasoning: boolean | null
}

export type LocalRow = {
  id: string
  source: "local"
  origin: "curated" | "downloaded" | "search"
  name: string
  family: string
  types: string[]
  known: boolean
  approximate: boolean
  selectable_for: string[]
  support: LocalSupport
  runnable: boolean
  not_runnable_reason: string | null
  builds: LocalBuild[]
  /** Curated models only. */
  default_quantization: string | null
  /** The one model starred for this computer. Curated models only. */
  recommended: boolean
  /**
   * The build the row shows and its Download fetches, and why the server chose
   * it. Absent for a searched repo, which lists every build and leads with none.
   */
  lead: {
    quantization: string
    why: "in_use" | "installed" | "recommended" | "fits_slower" | "nothing_fits"
  } | null
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
 * Whether the runtime can reach this machine's graphics hardware.
 *
 * Kept apart from the budget on purpose. An empty device list means nothing on
 * its own: a laptop with no card and a workstation whose backend library did
 * not ship both report one, and calling the second a machine without a GPU
 * tells a user their card is broken when a file is missing from ours.
 */
export type GpuStatus = "present" | "absent" | "broken_install" | "unknown"

/**
 * Curated plus installed. No `scanned` flag, because there is no scan: the
 * budget comes from the runtime's own allocator in about 180ms.
 */
export type ModelCatalog = {
  budget: Budget
  gpu_status: GpuStatus
  rows: LocalRow[]
  recommended_id: string | null
}

/** A repo, described. Search rows carry no rank and no quality claim. */
export type SearchRow = {
  repo: string
  downloads: number
  likes: number
  license: string | null
  gated: boolean
  /**
   * The repo it was quantized from, from its `base_model:quantized:` tag.
   * Provenance, not a grade. Not shown on the row: it names the exact parent
   * repo (an intermediate `...-unquantized` repo for a QAT build), which the
   * repo's own name usually already says. Kept for matching a typed search
   * against a repo's base model.
   */
  quantized_from: string | null
  last_modified: string | null
  /** The repo ships a vision projector, judged by its file names. A guess
   *  until the header is read before install. */
  reads_images: boolean
}

/** A repo's builds from its listing alone: no file is read to draw it. */
export type RepoDetail = {
  repo: string
  gated: boolean
  row: LocalRow
}

export type InstallEvent =
  | {
      type: "starting" | "verifying" | "selecting"
      message?: string
    }
  | {
      // `preparing` covers two waits: the runtime restarting and picking the
      // model up, which the router only does at startup, and then loading the
      // weights. `progress` is the runtime's own account of the second, absent
      // until it has one to give.
      type: "preparing"
      message?: string
      progress?: number | null
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

export function getModelCatalog(signal?: AbortSignal): Promise<ModelCatalog> {
  return requestJson<ModelCatalog>("/llm/catalog/local", { signal })
}

export function searchModels(
  query: string,
  signal?: AbortSignal
): Promise<{ results: SearchRow[] }> {
  return requestJson<{ results: SearchRow[] }>(
    `/llm/catalog/local/search?q=${encodeURIComponent(query)}`,
    { signal }
  )
}

/**
 * One listing, no header read: every build's size is exact and its fit an
 * estimate. The one header read happens when a build is installed.
 */
export function getRepoDetail(
  repo: string,
  signal?: AbortSignal
): Promise<RepoDetail> {
  return requestJson<RepoDetail>(`/llm/catalog/local/search/${repo}`, {
    signal,
  })
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
