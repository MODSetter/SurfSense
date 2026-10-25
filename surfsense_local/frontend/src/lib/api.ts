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
        // The app menu's Check for Updates…. Mirrors electron/src/preload/index.ts.
        onCheckRequested: (listener: () => void) => () => void
      }
      // Update checks and usage statistics: where each goes, what it sent, and
      // the switches (docs/contracts/05-desktop-telemetry.md, part C). Mirrors
      // electron/src/preload/index.ts.
      privacy?: {
        // null outside the app's own window.
        getState: () => Promise<PrivacyState | null>
        setUsageStatistics: (enabled: boolean) => Promise<void>
        // The updates bridge's own switch, so the two stay one setting.
        setUpdatesAutomatic: (enabled: boolean) => Promise<void>
        // The exact next report, built but not sent; null when none can be built.
        previewUsageReport: () => Promise<unknown>
        completeFirstRun: (choices: FirstRunChoices) => Promise<void>
        onStateChanged: (listener: (state: PrivacyState) => void) => () => void
      }
      setTitleBarOverlay?: (overlay: {
        color: string
        symbolColor: string
      }) => Promise<void>
      openExternal?: (url: string) => Promise<void>
      // A content link the user confirmed in the link popup: any https page.
      openConfirmedLink?: (url: string) => Promise<void>
      // A listed plugin's homepage or privacy policy, found by its id.
      openPluginPage?: (
        pluginId: string,
        page: "homepage" | "privacy_policy"
      ) => Promise<void>
      about?: {
        details: () => Promise<AppDetails>
        // Where models, workspaces and settings live. Mirrors electron/src/preload/index.ts.
        dataFolder?: () => Promise<string | null>
        // "" once opened, else the OS's reason.
        openDataFolder?: () => Promise<string>
      }
      // This run's log, oldest line first. Mirrors electron/src/preload/index.ts.
      sessionLog?: {
        read: () => Promise<string[]>
      }
      // The system's switch for SurfSense's microphone; Electron decides the
      // page's own permission. Mirrors electron/src/preload/index.ts.
      microphone?: {
        status: () => Promise<MicrophoneAccess>
        // macOS prompts the first time; call it before getUserMedia.
        request: () => Promise<MicrophoneAccess>
        // False where the system has no microphone settings to open (Linux).
        openSettings: () => Promise<boolean>
      }
      // Unexpected sidecar exits pushed by main. Mirrors electron/src/preload/index.ts.
      sidecars?: {
        onCrash: (listener: (crash: SidecarCrash) => void) => () => void
      }
      // The app menu's Help › Report Issue…. Mirrors electron/src/preload/index.ts.
      help?: {
        onReportIssue: (listener: () => void) => () => void
      }
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

// Mirrors electron/src/main/about/app-details.ts.
export type AppDetails = {
  version: string
  electron: string
  chrome: string
  node: string
  os: string
  arch: string
}

// Mirrors electron/src/main/updater.ts.
export type UpdatePrefs = { automatic: boolean; lastCheckedAt?: string }
export type UpdateState =
  | { status: "idle" }
  | { status: "checking" }
  | { status: "up-to-date" }
  | { status: "downloading"; version: string; percent: number | null }
  | { status: "ready"; version: string }
  | { status: "error"; message: string }

// Mirrors electron/src/main/privacy-choices/privacy-controller.ts.
export type PrivacyState = {
  updates: {
    automatic: boolean
    // An admin policy turned update checks off, or a package manager owns updates.
    locked: boolean
    // The policy wins when both apply.
    lockedReason: "policy" | "channel" | null
    // The package manager that owns updates; null unless that is the lock.
    channel: InstallChannel | null
    // updates.surfsense.com, or the mirror an admin policy names.
    host: string
    // null with a mirror, which never falls back.
    fallbackHost: "github.com" | null
    lastCheckedAt: string | null
    // The last request to `host`, exactly as sent.
    lastRequest: { url: string; headers: Record<string, string> } | null
  }
  usageStatistics: {
    // null: never asked.
    enabled: boolean | null
    locked: boolean
    lockedReason: "policy" | "do_not_track" | null
    host: string
    lastSent: { at: string; body: object } | null
  }
  firstRunAsked: boolean
}
export type FirstRunChoices = { updates: boolean; usageStatistics: boolean }
// Mirrors electron/src/main/install-channel/install-channel.ts.
export type InstallChannel =
  "scoop" | "aur" | "snap" | "flatpak" | "nix" | "apt"

export type SidecarCrash = {
  name: string
  code: number | null
}

// Mirrors electron/src/main/microphone/system-access.ts. Linux has no switch
// and reports "granted"; getUserMedia's own error says the rest there.
export type MicrophoneAccess =
  "not-determined" | "granted" | "denied" | "restricted" | "unknown"

// Packaged (Electron) exposes the sidecar's dynamic origin. A browser build
// with no bridge (Docker) reaches the API under VITE_API_BASE. A bare dev
// browser leaves both empty so root-relative paths still hit the Vite proxy.
const apiBase =
  (typeof window !== "undefined" ? window.surfsense?.apiUrl : undefined) ??
  import.meta.env.VITE_API_BASE ??
  ""

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
        return {
          message: body.detail.message,
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
