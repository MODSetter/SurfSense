// What Caddy's forward_auth asks of every request: let it through (200), send it
// to the sign-in (401), or refuse it (403).
import { hostName, isHostRequest } from "./host-request.ts"

export type Verdict = 200 | 401 | 403

// Where the API's data passes. Everything else needs no session: the app's own
// files, which must load for the sign-in screen to show, and the sign-in
// callbacks, guarded by their own state and PKCE, where a browser can return on
// another name than its cookie's, as 127.0.0.1 after localhost (ADR 0074).
const PRIVATE = /^\/api\//
const INTERNAL = /^\/api\/internal(\/|$)/

// Caddy routes /api/* on the decoded path, case-blind, with slashes merged and
// dot segments resolved; a raw /%61pi/… must not read as public here.
function routedPath(uri: string): string | null {
  let decoded: string
  try {
    decoded = decodeURIComponent(uri.split("?")[0])
  } catch {
    return null
  }
  return new URL(decoded.replace(/\/+/g, "/"), "http://route").pathname.toLowerCase()
}

export function isPublicPath(uri: string): boolean {
  const path = routedPath(uri)
  return path !== null && (path === "/api/health" || !PRIVATE.test(path))
}

export function allowedHost(host: string | undefined, allowedHosts: string[]): boolean {
  return allowedHosts.length === 0 || allowedHosts.includes(hostName(host))
}

export function verify(request: {
  uri: string
  host: string | undefined
  client: string
  gateway: string | null
  allowedHosts: string[]
  signedIn: boolean
  /** The server's setup turned sign-in off: its own proxy or VPN guards it. */
  signInOff: boolean
}): Verdict {
  // The workers' routes are on loopback only; no session ever reaches them.
  if (INTERNAL.test(routedPath(request.uri) ?? "")) return 403
  const fromHost = isHostRequest(request.host, request.client, request.gateway)
  // Even with sign-in off, a name not ours is a rebinding page's.
  if (!fromHost && !allowedHost(request.host, request.allowedHosts)) return 403
  if (request.signInOff || isPublicPath(request.uri)) return 200
  // No password yet is a 401 too: the app's files load and show its setup.
  return request.signedIn ? 200 : 401
}
