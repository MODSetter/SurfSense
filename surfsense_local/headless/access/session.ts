// Sessions are signed cookies, keyed from the instance secret: nothing to store,
// and a password change, which bumps its version, ends every one (ADR 0074).
import { createHmac, hkdfSync, timingSafeEqual } from "node:crypto"

export const COOKIE = "surfsense_session"
export const MAX_AGE_SECONDS = 30 * 24 * 60 * 60

export function sessionKey(secret: string): Buffer {
  // A key of its own, so a session can never stand in for anything else the secret protects.
  return Buffer.from(hkdfSync("sha256", secret, "", "surfsense-docker-session", 32))
}

function sign(key: Buffer, payload: string): string {
  return createHmac("sha256", key).update(payload).digest("base64url")
}

export function issue(key: Buffer, version: number, now: number): string {
  const payload = `${version}.${Math.floor(now / 1000)}`
  return `${payload}.${sign(key, payload)}`
}

export function valid(key: Buffer, token: string | undefined, version: number, now: number): boolean {
  const parts = token?.split(".") ?? []
  if (parts.length !== 3) return false
  const [tokenVersion, issued, signature] = parts
  const expected = Buffer.from(sign(key, `${tokenVersion}.${issued}`))
  const given = Buffer.from(signature)
  if (given.length !== expected.length || !timingSafeEqual(given, expected)) return false
  const age = now / 1000 - Number(issued)
  return Number(tokenVersion) === version && age >= 0 && age < MAX_AGE_SECONDS
}

export function cookieHeader(token: string, secure: boolean): string {
  return [
    `${COOKIE}=${token}`,
    "Path=/",
    "HttpOnly",
    "SameSite=Strict",
    `Max-Age=${MAX_AGE_SECONDS}`,
    ...(secure ? ["Secure"] : []),
  ].join("; ")
}

export function clearedCookieHeader(secure: boolean): string {
  return [`${COOKIE}=`, "Path=/", "HttpOnly", "SameSite=Strict", "Max-Age=0", ...(secure ? ["Secure"] : [])].join(
    "; ",
  )
}

export function readCookie(header: string | undefined): string | undefined {
  for (const part of header?.split(";") ?? []) {
    const [name, ...value] = part.trim().split("=")
    if (name === COOKIE) return value.join("=")
  }
  return undefined
}
