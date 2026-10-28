// The access service on loopback: Caddy's forward_auth asks /verify about every
// request, and the app reaches /access/* for its sign-in screen (ADR 0074).
import { createServer, type IncomingMessage, type Server, type ServerResponse } from "node:http"

import { GuessLimit } from "./guess-limit.ts"
import { hostName, isHostRequest } from "./host-request.ts"
import { checkPassword, MIN_LENGTH, readPassword, setPassword } from "./password-store.ts"
import { clearedCookieHeader, cookieHeader, issue, readCookie, sessionKey, valid } from "./session.ts"
import { allowedHost, verify } from "./verify.ts"

const MAX_BODY_BYTES = 4096

export type AccessOptions = {
  dataDir: string
  secret: string
  /** Comma-separated, from SURFSENSE_ALLOWED_HOSTS; empty allows any. */
  allowedHosts: string
  /** SURFSENSE_AUTH=none: the server's own proxy or VPN signs people in, so this never asks. */
  signInOff: boolean
  gateway: () => string | null
  port?: number
}

type Request = {
  host: string | undefined
  client: string
  secure: boolean
  token: string | undefined
}

function describe(request: IncomingMessage): Request {
  // Only Caddy reaches this loopback port, and it sets these from the browser's request.
  const forwarded = String(request.headers["x-forwarded-for"] ?? "").split(",")[0].trim()
  return {
    host: request.headers["x-forwarded-host"]?.toString() ?? request.headers.host,
    client: forwarded || request.socket.remoteAddress || "",
    secure: request.headers["x-forwarded-proto"] === "https",
    token: readCookie(request.headers.cookie),
  }
}

/** A cross-site page posting a sign-in or sign-out is refused; a browser always sends Origin here. */
function sameOrigin(request: IncomingMessage, host: string | undefined): boolean {
  const origin = request.headers.origin
  if (!origin) return true
  try {
    return new URL(origin).host === (host ?? "")
  } catch {
    return false
  }
}

async function readJson(request: IncomingMessage): Promise<Record<string, unknown>> {
  const chunks: Buffer[] = []
  let size = 0
  for await (const chunk of request) {
    size += (chunk as Buffer).length
    if (size > MAX_BODY_BYTES) throw new Error("body too large")
    chunks.push(chunk as Buffer)
  }
  try {
    const value = JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}")
    return typeof value === "object" && value !== null ? value : {}
  } catch {
    return {}
  }
}

function end(response: ServerResponse, status: number, headers: Record<string, string> = {}, body?: unknown) {
  if (body !== undefined) headers["Content-Type"] = "application/json"
  response.writeHead(status, { "Cache-Control": "no-store", ...headers })
  response.end(body === undefined ? undefined : JSON.stringify(body))
}

export function startAccess(options: AccessOptions): Promise<Server> {
  const key = sessionKey(options.secret)
  const guesses = new GuessLimit()
  const allowedHosts = options.allowedHosts
    .split(",")
    .map((host) => hostName(host))
    .filter(Boolean)

  const signedIn = (request: Request) => {
    const record = readPassword(options.dataDir)
    return record !== null && valid(key, request.token, record.version, Date.now())
  }

  async function signIn(raw: IncomingMessage, response: ServerResponse, request: Request) {
    const record = readPassword(options.dataDir)
    if (record === null) return end(response, 409)
    const now = Date.now()
    const wait = guesses.waitSeconds(request.client, now)
    if (wait > 0) return end(response, 429, { "Retry-After": String(wait) })
    // Counted before the hash, or guesses sent at once all pass the check above.
    guesses.failed(request.client, now)
    const { password } = await readJson(raw)
    if (typeof password !== "string" || !(await checkPassword(record, password))) return end(response, 401) // pragma: allowlist secret
    guesses.succeeded(request.client)
    end(response, 204, { "Set-Cookie": cookieHeader(issue(key, record.version, now), request.secure) })
  }

  // One change at a time, each reading the record afresh: otherwise two first
  // setups both find none, and a change can overwrite one made during its hash.
  let changing: Promise<unknown> = Promise.resolve()

  async function changePassword(raw: IncomingMessage, response: ServerResponse, request: Request) {
    const body = await readJson(raw)
    const turn = changing.then(() => changeInTurn(body, response, request))
    changing = turn.catch(() => {})
    return turn
  }

  async function changeInTurn(body: Record<string, unknown>, response: ServerResponse, request: Request) {
    const record = readPassword(options.dataDir)
    // SURFSENSE_PASSWORD would set it back at the next start.
    if (record?.source === "setup") return end(response, 409)
    // Changing it needs the current one. The first is whoever opens SurfSense
    // first, as Immich and Open WebUI have it; one reachable from the internet
    // presets SURFSENSE_PASSWORD instead.
    if (record !== null) {
      const now = Date.now()
      const wait = guesses.waitSeconds(request.client, now)
      if (wait > 0) return end(response, 429, { "Retry-After": String(wait) })
      guesses.failed(request.client, now)
      const current = typeof body.current === "string" ? body.current : ""
      if (!signedIn(request) || !(await checkPassword(record, current))) return end(response, 403)
      guesses.succeeded(request.client)
    }
    const password = body.password
    if (typeof password !== "string" || password.length < MIN_LENGTH) return end(response, 422) // pragma: allowlist secret
    const changed = await setPassword(options.dataDir, password)
    end(response, 204, { "Set-Cookie": cookieHeader(issue(key, changed.version, Date.now()), request.secure) })
  }

  const server = createServer(async (raw, response) => {
    const request = describe(raw)
    const url = new URL(raw.url ?? "/", "http://access")
    try {
      if (url.pathname === "/verify") {
        const verdict = verify({
          uri: raw.headers["x-forwarded-uri"]?.toString() ?? "/",
          host: request.host,
          client: request.client,
          gateway: options.gateway(),
          allowedHosts,
          signedIn: signedIn(request),
          signInOff: options.signInOff,
        })
        if (verdict !== 403) return end(response, verdict)
        // Caddy hands this answer to the browser as it is.
        response.writeHead(403, { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store" })
        return response.end("SurfSense does not answer on this address. Add it to SURFSENSE_ALLOWED_HOSTS.\n")
      }
      if (url.pathname === "/access/state" && raw.method === "GET") {
        const record = readPassword(options.dataDir)
        return end(response, 200, {}, {
          password: record !== null,
          signedIn: signedIn(request),
          host: isHostRequest(request.host, request.client, options.gateway()),
          // Who may change it: "setup" means only the server's setup.
          source: record?.source ?? null,
          signInOff: options.signInOff,
        })
      }
      if (raw.method !== "POST") return end(response, 405)
      if (!sameOrigin(raw, request.host)) return end(response, 403)
      const fromHost = isHostRequest(request.host, request.client, options.gateway())
      if (!fromHost && !allowedHost(request.host, allowedHosts)) return end(response, 403)
      if (url.pathname === "/access/sign-in") return await signIn(raw, response, request)
      if (url.pathname === "/access/sign-out") {
        return end(response, 204, { "Set-Cookie": clearedCookieHeader(request.secure) })
      }
      if (url.pathname === "/access/password") return await changePassword(raw, response, request)
      end(response, 404)
    } catch (error) {
      console.error(`[access] ${String(error)}`)
      if (!response.headersSent) end(response, 400)
    }
  })

  return new Promise((resolve) => server.listen(options.port ?? 0, "127.0.0.1", () => resolve(server)))
}
