export const RIGHT_PANEL_KEY = "surfsense:right-panel:v1"
export const SOURCE_PREVIEW_KEY = "surfsense:source-preview:v1"

function readSourcePreviews(): Record<string, number> {
  try {
    const value: unknown = JSON.parse(
      localStorage.getItem(SOURCE_PREVIEW_KEY) ?? "{}"
    )
    if (typeof value !== "object" || value === null || Array.isArray(value)) {
      return {}
    }
    return Object.fromEntries(
      Object.entries(value).filter(
        ([, documentId]) =>
          Number.isInteger(documentId) && (documentId as number) > 0
      )
    ) as Record<string, number>
  } catch {
    return {}
  }
}

export function readSourcePreview(workspaceId: number): number | null {
  return readSourcePreviews()[String(workspaceId)] ?? null
}

export function writeSourcePreview(
  workspaceId: number,
  documentId: number | null
) {
  const previews = readSourcePreviews()
  if (documentId === null) delete previews[String(workspaceId)]
  else previews[String(workspaceId)] = documentId
  try {
    localStorage.setItem(SOURCE_PREVIEW_KEY, JSON.stringify(previews))
  } catch {
    // Private browsing and full disks throw.
  }
}

export function readRightPanelOpen() {
  try {
    return localStorage.getItem(RIGHT_PANEL_KEY) !== "collapsed"
  } catch {
    return true
  }
}

export function writeRightPanelOpen(open: boolean) {
  try {
    localStorage.setItem(RIGHT_PANEL_KEY, open ? "open" : "collapsed")
  } catch {
    // Private browsing and full disks throw.
  }
}
