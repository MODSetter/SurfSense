import { intl } from "@/i18n/intl"

export type Health = {
  status: "ok"
}

declare global {
  interface Window {
    surfsense?: {
      apiUrl: string
      platform: string
      openDocument: (workspaceId: number, documentId: number) => Promise<string>
      revealDocument: (
        workspaceId: number,
        documentId: number
      ) => Promise<string>
      updates: {
        prefs: () => Promise<UpdatePrefs>
        setAutomatic: (automatic: boolean) => Promise<UpdatePrefs>
        state: () => Promise<UpdateState>
        check: () => Promise<void>
        install: () => Promise<void>
        onState: (listener: (state: UpdateState) => void) => () => void
      }
      setTitleBarOverlay?: (overlay: {
        color: string
        symbolColor: string
      }) => Promise<void>
      openExternal?: (url: string) => Promise<void>
      // Mirrors electron/src/preload/index.ts; main resolves and owns the locale.
      locale?: {
        get: () => string
        preference: () => Promise<string>
        set: (preference: string) => Promise<void>
        onChange: (listener: (locale: string) => void) => () => void
      }
      theme?: {
        set: (theme: "dark" | "light" | "system") => Promise<void>
        getSystemTheme: () => "dark" | "light"
        onSystemThemeChange: (
          listener: (theme: "dark" | "light") => void
        ) => () => void
      }
    }
  }
}

// Mirrors electron/src/main/updater.ts.
export type UpdatePrefs = { automatic: boolean; lastCheckedAt?: string }
export type UpdateState =
  | { status: "idle" }
  | { status: "checking" }
  | { status: "up-to-date" }
  | { status: "downloading"; version: string }
  | { status: "ready"; version: string }
  | { status: "error"; message: string }

// Packaged (Electron) exposes the sidecar's dynamic origin; a bare dev browser
// leaves it empty so root-relative paths still hit the Vite proxy.
const apiBase =
  typeof window !== "undefined" ? (window.surfsense?.apiUrl ?? "") : ""

function withBase(input: RequestInfo | URL): RequestInfo | URL {
  return typeof input === "string" && input.startsWith("/")
    ? apiBase + input
    : input
}

// The absolute URL for a root-relative path, for an <a>/<img>/<audio> src that
// the browser resolves itself instead of going through the fetch helper.
export function apiUrl(path: string): string {
  return apiBase + path
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string | null
  readonly detail: Record<string, unknown>

  constructor(
    status: number,
    message: string,
    code: string | null = null,
    detail: Record<string, unknown> = {}
  ) {
    super(message)
    this.name = "ApiError"
    this.status = status
    this.code = code
    this.detail = detail
  }
}

type ErrorDetails = {
  message: string
  code: string | null
  detail?: Record<string, unknown>
}

async function responseError(response: Response): Promise<ErrorDetails> {
  try {
    const body: unknown = await response.json()
    if (typeof body === "object" && body !== null && "detail" in body) {
      if (typeof body.detail === "string") {
        return { message: body.detail, code: null }
      }
      if (
        typeof body.detail === "object" &&
        body.detail !== null &&
        "message" in body.detail &&
        typeof body.detail.message === "string"
      ) {
        const required =
          "required" in body.detail && typeof body.detail.required === "number"
            ? body.detail.required
            : null
        const available =
          "available" in body.detail &&
          typeof body.detail.available === "number"
            ? body.detail.available
            : null
        return {
          message:
            required !== null && available !== null
              ? intl.formatMessage(
                  {
                    id: "app_api_insufficient_space_error",
                    defaultMessage:
                      "{message} ({required} GB required, {available} GB available)",
                  },
                  {
                    message: body.detail.message,
                    required: (required / 1e9).toFixed(1),
                    available: (available / 1e9).toFixed(1),
                  }
                )
              : body.detail.message,
          code:
            "code" in body.detail && typeof body.detail.code === "string"
              ? body.detail.code
              : null,
          detail: body.detail as Record<string, unknown>,
        }
      }
    }
  } catch {
    // The status text is the useful fallback for a non-JSON response.
  }

  return {
    message:
      response.statusText ||
      intl.formatMessage(
        {
          id: "app_api_request_failed_error",
          defaultMessage: "Request failed with status {status}",
        },
        {
          status: String(response.status),
        }
      ),
    code: null,
  }
}

// Resolves true once the user allowed the refused destination.
let egressPrompt: ((error: ApiError) => Promise<boolean>) | null = null

export function setEgressPrompt(handler: typeof egressPrompt): void {
  egressPrompt = handler
}

export async function request(
  input: RequestInfo | URL,
  init?: RequestInit,
  { prompted = false } = {}
): Promise<Response> {
  const response = await fetch(withBase(input), init)
  if (response.ok) return response
  const { message, code, detail } = await responseError(response)
  const error = new ApiError(response.status, message, code, detail)
  // ponytail: method stands in for "user action"; reads run unattended at boot.
  const userAction = (init?.method ?? "GET").toUpperCase() !== "GET"
  if (
    !prompted &&
    userAction &&
    error.code === "egress_disabled" &&
    egressPrompt &&
    (await egressPrompt(error))
  ) {
    return request(input, init, { prompted: true })
  }
  throw error
}

export async function requestJson<T>(
  input: RequestInfo | URL,
  init?: RequestInit
): Promise<T> {
  const response = await request(input, init)
  return response.json() as Promise<T>
}

export async function requestVoid(
  input: RequestInfo | URL,
  init?: RequestInit
): Promise<void> {
  await request(input, init)
}

export async function getHealth(signal?: AbortSignal): Promise<Health> {
  return requestJson<Health>("/health", { signal })
}
