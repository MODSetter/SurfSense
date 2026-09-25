// The only links the app hands to the OS browser: the SurfSense site, the
// project's own GitHub repository, and its Discord invite. Anything else is
// dropped so a crafted link in content cannot open arbitrary pages.
const SITE_HOSTS = new Set(["surfsense.com", "www.surfsense.com"])
const REPO_PATH = "/MODSetter/SurfSense"
const DISCORD_INVITE = "/ejRNvftDp9"

export function allowedExternalUrl(url: string): string | null {
  let parsed: URL
  try {
    parsed = new URL(url)
  } catch {
    return null
  }
  if (parsed.protocol !== "https:") return null
  if (SITE_HOSTS.has(parsed.hostname)) return parsed.href
  if (
    parsed.hostname === "github.com" &&
    (parsed.pathname === REPO_PATH ||
      parsed.pathname.startsWith(`${REPO_PATH}/`))
  ) {
    return parsed.href
  }
  if (parsed.hostname === "discord.gg" && parsed.pathname === DISCORD_INVITE) {
    return parsed.href
  }
  return null
}
