// Whether the access service asks for a password: always, unless the server's
// setup says its own proxy or VPN signs people in (SURFSENSE_AUTH=none).
type Env = Record<string, string | undefined>

export function signInOff(env: Env): boolean {
  const auth = env.SURFSENSE_AUTH?.trim()
  if (!auth) return false
  if (auth === "none") return true
  throw new Error(`SURFSENSE_AUTH is "${auth}"; leave it empty for sign-in, or set "none" to turn it off`)
}
