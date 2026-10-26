import { siteVisitUrl } from "@/features/external-links/site-visit-url"

// Each must pass electron/src/main/external-url.ts, or the click does nothing.
const REPO_URL = "https://github.com/MODSetter/SurfSense"

export const GITHUB_URL = REPO_URL
export const DISCORD_URL = "https://discord.gg/ejRNvftDp9"
export const LICENSE_URL = `${REPO_URL}/blob/main/LICENSE`

// surfsense.com's links say where the visit came from; GitHub's and Discord's stay plain.
export function docsUrl(version: string | undefined): string {
  return siteVisitUrl("https://www.surfsense.com/docs", "about_docs", version)
}

export function releaseNotesUrl(version: string): string {
  return `${REPO_URL}/releases/tag/v${version}`
}

// `what` is a field id in .github/ISSUE_TEMPLATE/bug.yml; GitHub prefills it, and `title`.
export function bugReportUrl(what: string, title?: string): string {
  const params = new URLSearchParams({ template: "bug.yml", what })
  if (title) params.set("title", title)
  return `${REPO_URL}/issues/new?${params}`
}
