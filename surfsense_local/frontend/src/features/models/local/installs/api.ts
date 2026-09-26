import { request, requestJson, requestVoid } from "@/lib/api"

import type { ModelType } from "../../model-type"
import type { InstallEvent } from "../chat/api"
import { parseNdjson } from "../read-ndjson"

/** One install the API runs, waits to run, or has just finished. */
export type InstallJob = {
  id: string
  catalog_id: string
  /** What the screens call it while it downloads. */
  label: string
  /** The slots its model can fill; each section shows only its own. */
  model_types: ModelType[]
  select: boolean
  model_type: ModelType | null
  event: InstallEvent
}

export type InstallJobs = { jobs: InstallJob[] }

export function startInstall(
  catalogId: string,
  { select, modelType }: { select: boolean; modelType?: ModelType }
): Promise<InstallJob> {
  return requestJson<InstallJob>("/llm/installs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      catalog_id: catalogId,
      select,
      ...(modelType ? { model_type: modelType } : {}),
    }),
  })
}

export function listInstalls(signal?: AbortSignal): Promise<InstallJobs> {
  return requestJson<InstallJobs>("/llm/installs", { signal })
}

export function cancelInstall(jobId: string): Promise<void> {
  return requestVoid(`/llm/installs/${encodeURIComponent(jobId)}`, {
    method: "DELETE",
  })
}

/** Every job now, then again on each change, until `signal` aborts. */
export async function* followInstalls(
  signal: AbortSignal
): AsyncGenerator<InstallJobs> {
  const response = await request("/llm/installs/events", { signal })
  if (!response.body) return
  yield* parseNdjson<InstallJobs>(response.body)
}
