// What Caddy's forward_auth asks of every request: let it through (200), send it
// to the sign-in (401), or refuse it (403).
import { hostName, isHostRequest } from "./host-request.ts"

export type Verdict = 200 | 401 | 403

// Where the API's data or a sign-in's tokens pass; everything else is the app's
// own files, which carry no data and must load for the sign-in screen to show.
const PRIVATE = /^\/(api\/|callback(\?|$)|plugins\/oauth\/callback(\?|$))/

export function isPublicPath(uri: string): boolean {
  return uri === "/api/health" || uri.startsWith("/api/health?") || !PRIVATE.test(uri)
}

export function allowedHost(host: string | undefined, allowedHosts: string[]): boolean {
  return allowedHosts.length === 0 || allowedHosts.includes(hostName(host))
}

export function verify(request: {
  uri: string
  host: string | undefined
  client: string
  gateway: string | null
  hasPassword: boolean
  allowedHosts: string[]
  signedIn: boolean
}): Verdict {
  const fromHost = isHostRequest(request.host, request.client, request.gateway)
  // Without a password, as on the desktop: the host alone, and no sign-in.
  if (!request.hasPassword) return fromHost ? 200 : 403
  if (!fromHost && !allowedHost(request.host, request.allowedHosts)) return 403
  if (isPublicPath(request.uri)) return 200
  return request.signedIn ? 200 : 401
}
