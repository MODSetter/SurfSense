import type { MenuItemConstructorOptions } from "electron"

// Each must pass external-url.ts. Mirrors frontend/src/features/about/about-links.ts.
const DOCS_URL = "https://www.surfsense.com/docs"
const GITHUB_URL = "https://github.com/MODSetter/SurfSense"
const RELEASES_URL = `${GITHUB_URL}/releases/tag`

// Says which app version a docs visit came from; surfsense.com only, never GitHub.
function fromHelpMenu(url: string, version: string): string {
  const tagged = new URL(url)
  tagged.searchParams.set("utm_source", "desktop")
  tagged.searchParams.set("utm_medium", "app")
  tagged.searchParams.set("utm_content", "help_menu")
  tagged.searchParams.set("app_version", version)
  return tagged.href
}

// English in every language: Electron has no role for these, and main translates nothing.
export function helpMenu(actions: {
  version: string
  openExternal: (url: string) => void
  reportIssue: () => void
}): MenuItemConstructorOptions {
  return {
    role: "help",
    submenu: [
      { label: "Report Issue…", click: () => actions.reportIssue() },
      { type: "separator" },
      {
        label: "Documentation",
        click: () => actions.openExternal(fromHelpMenu(DOCS_URL, actions.version)),
      },
      {
        label: "Source Code on GitHub",
        click: () => actions.openExternal(GITHUB_URL),
      },
      {
        label: "Release Notes",
        click: () => actions.openExternal(`${RELEASES_URL}/v${actions.version}`),
      },
    ],
  }
}
