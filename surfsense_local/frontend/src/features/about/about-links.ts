// Each must pass electron/src/main/external-url.ts, or the click does nothing.
const REPO_URL = "https://github.com/MODSetter/SurfSense"

export const DOCS_URL = "https://www.surfsense.com/docs"
export const GITHUB_URL = REPO_URL
export const DISCORD_URL = "https://discord.gg/ejRNvftDp9"
export const LICENSE_URL = `${REPO_URL}/blob/main/LICENSE`

export function releaseNotesUrl(version: string): string {
  return `${REPO_URL}/releases/tag/v${version}`
}

// `what` is a field id in .github/ISSUE_TEMPLATE/bug.yml; GitHub prefills it, and `title`.
export function bugReportUrl(what: string, title?: string): string {
  const params = new URLSearchParams({ template: "bug.yml", what })
  if (title) params.set("title", title)
  return `${REPO_URL}/issues/new?${params}`
}
