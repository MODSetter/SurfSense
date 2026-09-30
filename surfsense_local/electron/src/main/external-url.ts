// The only links the app hands to the OS browser: the SurfSense site, the
// project's own GitHub repository, its Discord invite, and an OpenRouter
// model's page, where OpenRouter names a speech model's voices. Anything else
// is dropped so a crafted link in content cannot open arbitrary pages.
const SITE_HOSTS = new Set(["surfsense.com", "www.surfsense.com"])
const REPO_PATH = "/MODSetter/SurfSense"
const DISCORD_INVITE = "/ejRNvftDp9"
// `/<author>/<model>`'s shape. A few site pages share it, which only ever
// opens OpenRouter's own site; no other host or deeper path gets through.
const OPENROUTER_MODEL = /^\/[\w.-]+\/[\w.:-]+$/

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
  if (
    parsed.hostname === "openrouter.ai" &&
    OPENROUTER_MODEL.test(parsed.pathname) &&
    !parsed.search &&
    !parsed.hash
  ) {
    return parsed.href
  }
  return null
}
