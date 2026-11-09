// The Docker image's access service, which Caddy serves at /access/* on the
// page's own origin, outside the API (ADR 0074).

export type AccessState = {
  /** Whether the instance has a password; until it does, the app asks to set one. */
  password: boolean
  signedIn: boolean
  /** Whether this browser is on the Docker host itself. */
  host: boolean
  /** Who may change it: the app, or only the server's setup; null with none. */
  source: "app" | "setup" | null
  /** The server's own proxy or VPN signs people in, so this never asks. */
  signInOff: boolean
}

export const MIN_PASSWORD_LENGTH = 8

export type SignInResult =
  | { status: "signed-in" }
  | { status: "wrong" }
  | { status: "slowed"; retryAfterSeconds: number }
  | { status: "failed" }

export type PasswordResult =
  "saved" | "wrong-current" | "set-by-setup" | "slowed" | "too-short" | "failed"

function post(path: string, body?: unknown): Promise<Response> {
  return fetch(path, {
    method: "POST",
    headers:
      body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}

export async function getAccessState(): Promise<AccessState> {
  const response = await fetch("/access/state")
  if (!response.ok) throw new Error(`access state: ${response.status}`)
  return (await response.json()) as AccessState
}

export async function signIn(password: string): Promise<SignInResult> {
  const response = await post("/access/sign-in", { password })
  if (response.status === 204) return { status: "signed-in" }
  if (response.status === 401) return { status: "wrong" }
  if (response.status === 429) {
    return {
      status: "slowed",
      retryAfterSeconds: Number(response.headers.get("Retry-After")) || 60,
    }
  }
  return { status: "failed" }
}

export async function signOut(): Promise<void> {
  await post("/access/sign-out")
}

/** Creates the first password, or changes it with the current one. */
export async function savePassword(
  password: string,
  current?: string
): Promise<PasswordResult> {
  const response = await post(
    "/access/password",
    current === undefined ? { password } : { current, password }
  )
  if (response.status === 204) return "saved"
  if (response.status === 403) return "wrong-current"
  if (response.status === 409) return "set-by-setup"
  if (response.status === 429) return "slowed"
  if (response.status === 422) return "too-short"
  return "failed"
}
