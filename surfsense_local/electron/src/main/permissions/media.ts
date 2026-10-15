/** A page's ask to capture media, as either of a session's permission handlers sees it. */
export type MediaAsk = {
  fromMainWindow: boolean
  isMainFrame: boolean
  requestingUrl: string | undefined
  // Empty for a capture that names no device, such as a desktop or tab capture.
  mediaTypes: readonly string[]
}

/** The microphone, for the main window's own page alone; never a camera or a screen. */
export function mayCaptureMedia(ask: MediaAsk, appPage: URL): boolean {
  return (
    ask.fromMainWindow &&
    ask.isMainFrame &&
    isAppPage(ask.requestingUrl, appPage) &&
    ask.mediaTypes.length > 0 &&
    ask.mediaTypes.every((type) => type === "audio")
  )
}

// Packaged, the app's page is a file in its own folder; in development, Vite's origin.
function isAppPage(url: string | undefined, appPage: URL): boolean {
  if (url === undefined) return false
  let parsed: URL
  try {
    parsed = new URL(url)
  } catch {
    return false
  }
  if (appPage.protocol !== "file:") return parsed.origin === appPage.origin
  if (parsed.protocol !== "file:" || parsed.host !== appPage.host) return false
  const folder = pathSegments(new URL(".", appPage))?.slice(0, -1)
  const path = pathSegments(parsed)
  return (
    folder !== undefined &&
    path !== undefined &&
    path.length > folder.length &&
    folder.every((segment, index) => path[index] === segment)
  )
}

// Compared by decoded segment: Chromium and Node percent-encode a path
// differently (`;` for one), an escaped slash stays inside its segment, and
// Windows paths ignore case.
function pathSegments(url: URL): string[] | undefined {
  let segments: string[]
  try {
    segments = url.pathname.split("/").map(decodeURIComponent)
  } catch {
    return undefined
  }
  const windows = /^[A-Za-z]:$/.test(segments[1] ?? "")
  return windows ? segments.map((segment) => segment.toLowerCase()) : segments
}
