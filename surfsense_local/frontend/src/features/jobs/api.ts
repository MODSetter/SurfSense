import type { DocumentStatus } from "@/features/sources/api"
import { ApiError, requestJson } from "@/lib/api"

// The app backend's job routes, typed from the frozen interface the backend's
// tests assert key by key.

/** Why a job may not run here; null while it may. */
export type LockedCode =
  "none" | "not_included" | "expired" | "clock" | "no_entitlement"

export type JobInfo = {
  key: string
  name: string
  description: string
  // The license entitlement that unlocks it, for a paid pack's job.
  entitlement: string | null
  // What runs it, as the pack names it ("workbook-rows/1", "word-clauses/1"),
  // which picks the form and the wording of its runs.
  runner: string
  unlocked: boolean
  locked_reason: string
  locked_code: LockedCode | null
}

export type PackInfo = {
  id: string
  version: string
  name: string
  publisher: string
  access: string
  // Whether any of its jobs may run, and else why its first may not.
  unlocked: boolean
  locked_reason: string
  locked_code: LockedCode | null
  jobs: JobInfo[]
}

export type PackOutcomeCode =
  | "installed"
  | "current"
  | "deferred"
  | "job_not_included"
  // Every pack with the job also has a job the license does not include.
  | "pack_not_covered"
  | "license_not_valid"
  | "license_not_found"
  | "needs_newer_app"
  | "unknown_job"
  | "rate_limited"
  | "unavailable"
  | "refused"
  // The pack sent has a job this computer's license file does not list
  // (PACK_NOT_INCLUDED): the license server's record is newer.
  | "license_outdated"
  | "not_written"

/** What the license server's answer did for one entitlement code. */
export type PackOutcome = {
  entitlement: string
  outcome: PackOutcomeCode
  message: string
  // The version installed now, once one is: a deferred check names the one it
  // was held back from replacing.
  version: string | null
  // The server's or the install's own code, when one came with it.
  detail: string | null
}

export type PackDownload = { outcomes: PackOutcome[]; packs: PackInfo[] }

export type ModelRef = {
  provider: string
  name: string
  connection_id: number | null
}

export type JobSetting = {
  key: string
  label: string
  description: string
  default: boolean
  value: boolean
}

export type JobSettings = {
  job: string
  settings: JobSetting[]
  // Whether the job checks its answers a second time; a checker is used only when it does.
  checks: boolean
  // The model that makes the second checks; null checks on the answering model.
  checker: ModelRef | null
}

/** The whole of a job's settings: one left out is set to its default. */
export type JobSettingsWrite = {
  settings: Record<string, boolean>
  checker: ModelRef | null
}

export type JobRunStart = {
  job: string
  document_id: number
  source_ids: number[]
}

export type RunProgress = { done: number; total: number }

/** Every question is answered, left for a person, or suggested; skipped rows are apart. */
export type RunTally = {
  questions: number
  answered: number
  for_person: number
  suggested: number
  skipped: number
}

export type JobRunSummary = {
  artifact_id: number
  title: string
  job: string
  pack_id: string
  pack_version: string
  status: DocumentStatus
  error: string | null
  created_at: string
  progress: RunProgress | null
  tally: RunTally | null
  open_suggestion_count: number
  newest_version_id: number
  newest_version_number: number
  newest_ready_version_id: number | null
  // Any version of the run's copy is pending or processing.
  running: boolean
}

/** One thing a run left for a person: a workbook's [sheet, cell, question,
 *  answer, why], a contract's [where, anchor, point, verdict, why]. */
export type ReportException = [string, string, string, string, string]

/** The stored report: only what the screens read is typed. */
export type JobReport = {
  // The runner that wrote it; an older workbook's report names none.
  runner?: string
  model: string
  checker: string | null
  // A workbook's answer words as the pack writes them, plus "blank" and
  // "skipped"; a contract's outcomes (changed, meets, not_covered,
  // for_person), plus "skipped".
  counts: Record<string, number>
  // The two sheets a workbook's run adds; a contract's report has none.
  sheets?: { answers: string; exceptions: string }
  exceptions?: ReportException[]
}

export type OpenSuggestion = {
  sheet: string
  cell: string
  question: string
  suggested: string
  // The cell's own spelling of the suggestion, which confirming writes.
  written: string
  comment: string | null
}

export type ConfirmedCell = { sheet: string; cell: string; artifact_id: number }

export type JobRunRead = JobRunSummary & {
  pack: string
  report: JobReport | null
  open_suggestions: OpenSuggestion[]
  confirmed: ConfirmedCell[]
}

const JSON_HEADERS = { "Content-Type": "application/json" }

export function listJobPacks(signal?: AbortSignal): Promise<PackInfo[]> {
  return requestJson<PackInfo[]>("/job-packs", { signal })
}

// No body: the backend sends the stored license's key and asks for every job
// it includes, never the renderer.
export function requestPackDownload(): Promise<PackDownload> {
  return requestJson<PackDownload>("/job-packs/download", { method: "POST" })
}

export function importPackFile(file: File): Promise<PackInfo[]> {
  const body = new FormData()
  body.append("file", file)
  return requestJson<PackInfo[]>("/job-packs/import", { method: "POST", body })
}

function settingsPath(job: string) {
  return `/job-packs/jobs/${encodeURIComponent(job)}/settings`
}

export function readJobSettings(
  job: string,
  signal?: AbortSignal
): Promise<JobSettings> {
  return requestJson<JobSettings>(settingsPath(job), { signal })
}

export function saveJobSettings(
  job: string,
  body: JobSettingsWrite
): Promise<JobSettings> {
  return requestJson<JobSettings>(settingsPath(job), {
    method: "PUT",
    headers: JSON_HEADERS,
    body: JSON.stringify(body),
  })
}

export function startJobRun(
  workspaceId: number,
  body: JobRunStart
): Promise<{ artifact_id: number }> {
  return requestJson<{ artifact_id: number }>(
    `/workspaces/${workspaceId}/job-runs`,
    { method: "POST", headers: JSON_HEADERS, body: JSON.stringify(body) }
  )
}

/** Newest first. */
export function listJobRuns(
  workspaceId: number,
  limit: number,
  signal?: AbortSignal
): Promise<JobRunSummary[]> {
  return requestJson<JobRunSummary[]>(
    `/workspaces/${workspaceId}/job-runs?limit=${limit}`,
    { signal }
  )
}

/** Any version of a run's copy reads the run; null when no run has that copy,
 *  such as a workbook the agent revised. */
export async function readJobRun(
  workspaceId: number,
  artifactId: number,
  signal?: AbortSignal
): Promise<JobRunRead | null> {
  try {
    return await requestJson<JobRunRead>(
      `/workspaces/${workspaceId}/job-runs/${artifactId}`,
      { signal }
    )
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null
    throw error
  }
}

/** Every suggestion still open, as the next version of the run's copy: the
 *  screens offer no per-cell choice. Takes the run's own (first) version. */
export function confirmRunSuggestions(
  workspaceId: number,
  rootId: number
): Promise<{ artifact_id: number }> {
  return requestJson<{ artifact_id: number }>(
    `/workspaces/${workspaceId}/job-runs/${rootId}/confirm`,
    { method: "POST", headers: JSON_HEADERS, body: "{}" }
  )
}
