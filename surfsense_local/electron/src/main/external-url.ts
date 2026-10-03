// The only links the app hands to the OS browser: the SurfSense site, the
// project's own GitHub repository, its Discord invite, an OpenRouter model's
// page, where OpenRouter names a speech model's voices, and OpenAI's sign-in
// page for a ChatGPT subscription. Anything else is dropped so a crafted link
// in content cannot open arbitrary pages.
const SITE_HOSTS = new Set(["surfsense.com", "www.surfsense.com"])
const REPO_PATH = "/MODSetter/SurfSense"
const DISCORD_INVITE = "/ejRNvftDp9"
// `/<author>/<model>`'s shape. A few site pages share it, which only ever
// opens OpenRouter's own site; no other host or deeper path gets through.
const OPENROUTER_MODEL = /^\/[\w.-]+\/[\w.:-]+$/
const OPENAI_AUTHORIZE = "/api/accounts/authorize"

// Only a sign-in that returns its code to the API's own loopback listener;
// one naming any other redirect would hand the code to someone else.
function isLoopbackSignIn(parsed: URL): boolean {
  if (parsed.hostname !== "auth.openai.com") return false
  if (parsed.pathname !== OPENAI_AUTHORIZE) return false
  let redirect: URL
  try {
    redirect = new URL(parsed.searchParams.get("redirect_uri") ?? "")
  } catch {
    return false
  }
  return (
    redirect.protocol === "http:" &&
    redirect.hostname === "127.0.0.1" &&
    redirect.pathname === "/callback"
  )
}

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
  if (isLoopbackSignIn(parsed)) return parsed.href
  return null
}
