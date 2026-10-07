/** The part of Electron's Session the snapshot windows' request filter needs. */
export type SnapshotSession = {
  webRequest: {
    onBeforeRequest(
      listener: (
        details: { url: string },
        callback: (response: { cancel: boolean }) => void,
      ) => void,
    ): void
  }
}

/**
 * Let the snapshot windows load only the snapshot page's own files and the
 * documents being printed. The document is untrusted, and a script that got into
 * the page would otherwise read local files and the whole API: a file:// page
 * sends no Origin, so the API cannot tell it from Electron's main process.
 *
 * Returns `allow(fileUrl)`, which lets that file through until its release is called.
 */
export function confineSnapshotSession(
  session: SnapshotSession,
  page: URL,
): (fileUrl: string) => () => void {
  const ownFiles = new URL(".", page).href
  // In development Vite's client keeps a websocket to its dev server.
  const devServerSocket =
    page.protocol === "http:" ? `ws://${page.host}/` : undefined
  const printing: string[] = []

  const allowed = (url: string): boolean =>
    url.startsWith(ownFiles) ||
    // The page's own object URLs: a deck's pictures, made from the file it prints.
    url.startsWith("blob:") ||
    (devServerSocket !== undefined && url.startsWith(devServerSocket)) ||
    printing.includes(url)

  session.webRequest.onBeforeRequest((details, callback) =>
    callback({ cancel: !allowed(details.url) }),
  )

  return (fileUrl) => {
    printing.push(fileUrl)
    let released = false
    return () => {
      if (released) return
      released = true
      printing.splice(printing.indexOf(fileUrl), 1)
    }
  }
}
