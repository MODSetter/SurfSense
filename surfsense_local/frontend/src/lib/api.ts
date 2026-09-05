export type Health = {
  status: "ok"
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
  const response = await fetch(input, init)
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
