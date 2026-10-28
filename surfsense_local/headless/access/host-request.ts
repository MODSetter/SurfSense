// Whether a request comes from the Docker host itself. The Host header alone is
// the sender's to choose, so the client address Caddy saw backs it: a port
// published on 127.0.0.1 arrives from loopback or the bridge's gateway (ADR 0074).
import { readFileSync } from "node:fs"

const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]", "::1"])
const LOOPBACK = /^(127\.\d+\.\d+\.\d+|::1|::ffff:127\.\d+\.\d+\.\d+)$/

export function hostName(host: string | undefined): string {
  const value = (host ?? "").trim().toLowerCase()
  if (value.startsWith("[")) return value.slice(0, value.indexOf("]") + 1)
  return value.split(":")[0]
}

export function isLocalHostName(host: string | undefined): boolean {
  return LOCAL_HOSTS.has(hostName(host))
}

export function isHostRequest(host: string | undefined, client: string, gateway: string | null): boolean {
  return isLocalHostName(host) && (LOOPBACK.test(client) || (gateway !== null && client === gateway))
}

/** The container's default gateway, from the kernel's routing table. */
export function defaultGateway(): string | null {
  try {
    for (const line of readFileSync("/proc/net/route", "utf8").split("\n").slice(1)) {
      const [, destination, gateway] = line.trim().split(/\s+/)
      if (destination !== "00000000" || !gateway) continue
      // Little-endian hex, as /proc writes it.
      const bytes = gateway.match(/../g)?.map((byte) => parseInt(byte, 16)).reverse()
      return bytes?.join(".") ?? null
    }
  } catch {
    // Not Linux, as on a checkout on macOS: only loopback counts.
  }
  return null
}
