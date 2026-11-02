// Which of Caddy's configurations this run serves: plain HTTP for the host
// itself, Caddy's own certificates on a LAN, or a public domain's.
type Env = Record<string, string | undefined>

export type TlsMode = {
  /** Beside the Caddyfile the image names in SURFSENSE_LOCAL_CADDYFILE. */
  caddyfile: string
  env: Record<string, string>
}

export function tlsMode(env: Env): TlsMode {
  const domain = env.SURFSENSE_DOMAIN?.trim()
  if (domain) return { caddyfile: "Caddyfile.domain", env: { SURFSENSE_DOMAIN: domain } }

  const tls = env.SURFSENSE_TLS?.trim()
  if (!tls) return { caddyfile: "Caddyfile", env: {} }
  if (tls !== "internal") {
    throw new Error(`SURFSENSE_TLS is "${tls}"; the one value it takes is "internal"`)
  }
  const hosts = (env.SURFSENSE_ALLOWED_HOSTS ?? "")
    .split(",")
    .map((host) => host.trim())
    .filter(Boolean)
  if (hosts.length === 0) {
    throw new Error("SURFSENSE_TLS=internal needs SURFSENSE_ALLOWED_HOSTS: the names to issue certificates for")
  }
  return {
    caddyfile: "Caddyfile.lan",
    env: {
      SURFSENSE_TLS_SITES: hosts.map((host) => `https://${host}`).join(", "),
      SURFSENSE_HTTPS_PORT: env.SURFSENSE_HTTPS_PORT || "443",
    },
  }
}
