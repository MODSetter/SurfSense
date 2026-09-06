export type Health = {
  status: "ok"
}

declare global {
  interface Window {
    surfsense?: { apiUrl: string }
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

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = "ApiError"
    this.status = status
  }
}

async function responseError(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json()
    if (
      typeof body === "object" &&
      body !== null &&
      "detail" in body &&
      typeof body.detail === "string"
    ) {
      return body.detail
    }
  } catch {
    // The status text is the useful fallback for a non-JSON response.
  }

  return response.statusText || `Request failed with status ${response.status}`
}

export async function request(
  input: RequestInfo | URL,
  init?: RequestInit
): Promise<Response> {
  const response = await fetch(withBase(input), init)
  if (!response.ok) {
    throw new ApiError(response.status, await responseError(response))
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
