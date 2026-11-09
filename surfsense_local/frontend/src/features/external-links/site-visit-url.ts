/**
 * A surfsense.com link that says the visit came from the app, from which place
 * in it, and from which version: never an ID, and never on another site's links.
 * The external-link allowlist passes surfsense.com with any query.
 */
export function siteVisitUrl(
  url: string,
  surface: string,
  version: string | undefined
): string {
  const tagged = new URL(url)
  tagged.searchParams.set("utm_source", "desktop")
  tagged.searchParams.set("utm_medium", "app")
  tagged.searchParams.set("utm_content", surface)
  if (version) tagged.searchParams.set("app_version", version)
  return tagged.href
}
