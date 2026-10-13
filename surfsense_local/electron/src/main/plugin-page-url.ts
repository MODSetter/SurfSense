// A listed plugin's own pages, opened on a click with no link popup: the page names
// the plugin and which page, never an address, and the address is the reviewed one
// in the signed registry, read from the app's API. SurfSense's own plugins list none.

export type PluginPage = "homepage" | "privacy_policy"

const PAGES: ReadonlySet<string> = new Set(["homepage", "privacy_policy"])

type ListedPages = { id?: unknown; homepage?: unknown; privacy_policy?: unknown }

export async function pluginPageUrl(
  apiUrl: string,
  pluginId: string,
  page: PluginPage,
  fetchFrom: typeof fetch = fetch
): Promise<string | null> {
  if (!PAGES.has(page)) return null
  let listed: { third_party_off?: unknown; plugins?: unknown }
  try {
    const reply = await fetchFrom(`${apiUrl}/plugins/registry`, {
      signal: AbortSignal.timeout(5_000),
    })
    if (!reply.ok) return null
    listed = (await reply.json()) as typeof listed
  } catch {
    return null
  }
  if (listed.third_party_off !== false || !Array.isArray(listed.plugins)) {
    return null
  }
  const entry = (listed.plugins as ListedPages[]).find(
    (plugin) => plugin.id === pluginId
  )
  const address = entry?.[page]
  if (typeof address !== "string") return null
  try {
    const parsed = new URL(address)
    if (parsed.protocol !== "https:" || parsed.username || parsed.password) {
      return null
    }
    return parsed.href
  } catch {
    return null
  }
}
