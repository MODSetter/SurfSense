import { act } from "@testing-library/react"
import { vi } from "vitest"

import type { LicenseStatus } from "@/features/license/api"
import type { WorkspaceDocument } from "@/features/sources/api"

import type {
  JobInfo,
  JobRunRead,
  JobRunSummary,
  JobSettings,
  LockedCode,
  PackInfo,
  PackOutcome,
  PackOutcomeCode,
} from "./api"
import { XLSX_MIME } from "./run/run-sources"

// Stand-ins for the app backend's job routes, typed by api.ts. Nothing here is
// a real pack: the private packs never reach this repository.

export const TEST_JOB: JobInfo = {
  key: "test-questionnaire",
  name: "Test questionnaire",
  description: "A stand-in job.",
  entitlement: "JOB_QUESTIONNAIRE",
  unlocked: true,
  locked_reason: "",
  locked_code: null,
}

export const TEST_PACK: PackInfo = {
  id: "test-pack",
  version: "0.4.3",
  name: "Test pack",
  publisher: "SurfSense",
  access: "paid",
  unlocked: true,
  locked_reason: "",
  locked_code: null,
  jobs: [TEST_JOB],
}

/** What a download came to for the stand-in job, in the backend's shape;
 *  `version` is the one installed now, which a deferred check keeps. */
export function packOutcome(
  outcome: PackOutcomeCode,
  overrides: Partial<PackOutcome> = {}
): PackOutcome {
  return {
    entitlement: "JOB_QUESTIONNAIRE",
    outcome,
    message: "The backend’s own words.",
    version: null,
    detail: null,
    ...overrides,
  }
}

/** The stand-in pack, installed but locked for `code`. */
export function lockedPack(
  code: LockedCode,
  job: Partial<JobInfo> = {}
): PackInfo {
  return {
    ...TEST_PACK,
    unlocked: false,
    locked_reason: "The backend’s own reason.",
    locked_code: code,
    jobs: [
      {
        ...TEST_JOB,
        unlocked: false,
        locked_reason: "The backend’s own reason.",
        locked_code: code,
        ...job,
      },
    ],
  }
}

export const NO_LICENSE: LicenseStatus = {
  state: "none",
  plan: null,
  email: null,
  expiry: null,
  max_users: null,
  firm: null,
  jobs: [],
}

export const INDIVIDUAL: LicenseStatus = {
  state: "active",
  plan: "individual",
  email: "ada@example.com",
  expiry: "2027-09-10T00:00:00Z",
  max_users: null,
  firm: null,
  jobs: [],
}

export const BUSINESS: LicenseStatus = {
  state: "active",
  plan: "business",
  email: "partner@example.com",
  expiry: "2027-10-10T00:00:00Z",
  max_users: 5,
  firm: "Example Accounting LLP",
  jobs: ["JOB_QUESTIONNAIRE"],
}

/** A trial issued before trials carried jobs. */
export const TRIAL: LicenseStatus = {
  state: "active",
  plan: "trial",
  email: "ada@example.com",
  expiry: "2026-11-17T00:00:00Z",
  max_users: null,
  firm: null,
  jobs: [],
}

export const BUSINESS_TRIAL: LicenseStatus = {
  ...TRIAL,
  firm: "Example Accounting LLP",
  jobs: ["JOB_QUESTIONNAIRE"],
}

/** A ready PDF source; a higher id was added later. */
export function source(
  id: number,
  title: string,
  overrides: Partial<WorkspaceDocument> = {}
): WorkspaceDocument {
  const added = new Date(Date.UTC(2026, 10, 1, 9, id)).toISOString()
  return {
    id,
    title,
    document_type: "FILE",
    mime_type: "application/pdf",
    status: "ready",
    error_message: null,
    created_at: added,
    updated_at: added,
    folder_id: null,
    ...overrides,
  }
}

export function workbook(
  id: number,
  title: string,
  overrides: Partial<WorkspaceDocument> = {}
): WorkspaceDocument {
  return source(id, title, { mime_type: XLSX_MIME, ...overrides })
}

export function runSummary(
  overrides: Partial<JobRunSummary> = {}
): JobRunSummary {
  return {
    artifact_id: 41,
    title: "Vendor questionnaire (revised)",
    job: "test-questionnaire",
    pack_id: "test-pack",
    pack_version: "0.4.3",
    status: "ready",
    error: null,
    created_at: "2026-11-03T09:00:00Z",
    progress: { done: 40, total: 40 },
    tally: {
      questions: 40,
      answered: 31,
      for_person: 6,
      suggested: 3,
      skipped: 2,
    },
    open_suggestion_count: 2,
    newest_version_id: 41,
    newest_version_number: 1,
    newest_ready_version_id: 41,
    running: false,
    ...overrides,
  }
}

export function runRead(overrides: Partial<JobRunRead> = {}): JobRunRead {
  return {
    ...runSummary(),
    pack: "test-pack 0.4.3",
    report: {
      model: "qwen3-4b.gguf",
      checker: null,
      counts: { Yes: 20, No: 8, "N/A": 3, blank: 9, skipped: 2 },
      sheets: {
        answers: "SurfSense answers",
        exceptions: "SurfSense exceptions",
      },
    },
    open_suggestions: [
      {
        sheet: "Questions",
        cell: "B2",
        question: "Do you encrypt backups?",
        suggested: "Yes",
        written: "Yes",
        comment: null,
      },
      {
        sheet: "Questions",
        cell: "B7",
        question: "Is there a named security officer?",
        suggested: "N/A",
        written: "Not applicable",
        comment: "Only one person works here.",
      },
    ],
    confirmed: [],
    ...overrides,
  }
}

export function jobSettings(overrides: Partial<JobSettings> = {}): JobSettings {
  return {
    job: "test-questionnaire",
    settings: [
      {
        key: "quote_every_yes",
        label: "Quote every Yes",
        description: "A Yes needs a quote from your documents.",
        default: false,
        value: false,
      },
    ],
    checker: null,
    ...overrides,
  }
}

/** The chat model the dashboard has selected: a local one by default. */
export const LOCAL_SELECTION = {
  model_type: "text_gen" as const,
  provider: "llamacpp",
  connection_id: null,
  name: "qwen3-4b.gguf",
  updated_at: "2026-11-01T00:00:00Z",
}

/** The routes the chat candidates are read from: one local model, one remote. */
export const CHAT_CANDIDATE_ROUTES: Record<string, Answer> = {
  "GET /llm/providers": [
    {
      name: "llamacpp",
      healthy: true,
      can_download: true,
      requires_key: false,
      configured: true,
    },
  ],
  "GET /llm/providers/llamacpp/models": [
    {
      name: "qwen3-4b.gguf",
      installed: true,
      capabilities: ["text_gen"],
      display_name: "Qwen3 4B",
      types: ["text_gen"],
      selectable_for: ["text_gen"],
    },
  ],
  "GET /llm/connections": [{ id: 9, label: "OpenRouter" }],
  "GET /llm/connections/9/models": [
    {
      connection_id: 9,
      connection_label: "OpenRouter",
      name: "m",
      types: ["text_gen"],
      capability_source: "catalog",
      selectable_for: ["text_gen"],
      reads_images: false,
    },
  ],
}

/** What the Jobs screens read on opening over workspace 1. */
export function dialogRoutes({
  license = BUSINESS,
  packs = [TEST_PACK],
  runs = [],
}: {
  license?: LicenseStatus
  packs?: PackInfo[]
  runs?: JobRunSummary[]
} = {}): Record<string, Answer> {
  return {
    "GET /license/status": license,
    "GET /job-packs": packs,
    "GET /workspaces/1/job-runs?limit=11": runs,
    "GET /workspaces/1/artifacts": [],
    "GET /job-packs/jobs/test-questionnaire/settings": jobSettings(),
    ...CHAT_CANDIDATE_ROUTES,
  }
}

export type StubRequest = {
  method: string
  path: string
  body: BodyInit | null | undefined
}

/** A JSON body, or a function that answers the request itself. */
export type Answer =
  ((request: StubRequest) => Response | Promise<Response>) | object | null

/** Answers fetch from `routes`, keyed "METHOD /path?query"; anything else is a 404.
 *  Routes are read at each request, so a test may change one between steps. */
export function stubJobsApi(routes: Record<string, Answer>) {
  const calls: StubRequest[] = []
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = {
        method: (init?.method ?? "GET").toUpperCase(),
        path: String(input),
        body: init?.body,
      }
      calls.push(request)
      const key = `${request.method} ${request.path}`
      if (!Object.hasOwn(routes, key))
        return Response.json({ detail: "not found" }, { status: 404 })
      const answer = routes[key]
      return typeof answer === "function"
        ? answer(request)
        : Response.json(answer)
    })
  )
  return calls
}

/** A refusal as the backend sends one, in its own English. */
export function refusal(
  status: number,
  code: string,
  message = "The backend’s own words.",
  extra: Record<string, unknown> = {}
) {
  return () =>
    Response.json({ detail: { code, message, ...extra } }, { status })
}

/** The backend's answer while the license server is off in Settings › Network. */
export const LICENSE_SERVER_OFF = refusal(
  403,
  "egress_disabled",
  "The backend’s own words.",
  {
    destination: "host:api.surfsense.com",
    host: "api.surfsense.com",
    hosts: ["api.surfsense.com"],
    purpose: "job_packs",
  }
)

/**
 * The app's window shown again over 30 s later (createQueryClient's
 * staleTime), as after a while in another app: React Query reads what is on
 * screen again. Mocks the clock; the test's afterEach calls vi.useRealTimers.
 */
export function showWindowAgainLater() {
  vi.setSystemTime(Date.now() + 31_000)
  act(() => {
    window.dispatchEvent(new Event("visibilitychange"))
  })
}

/** The bridge's link opener, so a test sees which page a link would open. */
export function stubOpenExternal() {
  const openExternal = vi.fn<(url: string) => Promise<void>>(
    async () => undefined
  )
  window.surfsense = { ...window.surfsense!, openExternal }
  return openExternal
}
