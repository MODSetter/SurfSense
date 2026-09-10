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
      setTitleBarOverlay?: (overlay: {
        color: string
        symbolColor: string
      }) => Promise<void>
    }
  }
}

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

  constructor(status: number, message: string, code: string | null = null) {
    super(message)
    this.name = "ApiError"
    this.status = status
    this.code = code
  }
}

async function responseError(
  response: Response
): Promise<{ message: string; code: string | null }> {
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
              ? `${body.detail.message} (${(required / 1e9).toFixed(1)} GB required, ${(available / 1e9).toFixed(1)} GB available)`
              : body.detail.message,
          code:
            "code" in body.detail && typeof body.detail.code === "string"
              ? body.detail.code
              : null,
        }
      }
    }
  } catch {
    // The status text is the useful fallback for a non-JSON response.
  }

  return {
    message:
      response.statusText || `Request failed with status ${response.status}`,
    code: null,
  }
}

export async function request(
  input: RequestInfo | URL,
  init?: RequestInit
): Promise<Response> {
  const response = await fetch(withBase(input), init)
  if (!response.ok) {
    const error = await responseError(response)
    throw new ApiError(response.status, error.message, error.code)
  }
  return response
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
