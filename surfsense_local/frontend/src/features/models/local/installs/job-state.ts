import type { ModelType } from "../../model-type"
import type { InstallJob } from "./api"

const ENDED = new Set(["complete", "error", "cancelled"])

export function isRunning(job: InstallJob): boolean {
  return !ENDED.has(job.event.type)
}

/** The job downloading this build, if one is running or waiting. */
export function jobFor(
  jobs: readonly InstallJob[],
  catalogId: string
): InstallJob | undefined {
  return jobs.find((job) => job.catalog_id === catalogId && isRunning(job))
}

/** Running jobs whose model can fill `slot`. */
export function jobsFor(
  jobs: readonly InstallJob[],
  slot: ModelType
): InstallJob[] {
  return jobs.filter((job) => isRunning(job) && job.model_types.includes(slot))
}
