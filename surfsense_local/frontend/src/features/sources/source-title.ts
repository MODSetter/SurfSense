// The server's rule (DocumentTitle), mirrored so a bad name is caught before
// the request; the server stays authoritative.
export const MAX_SOURCE_TITLE = 500

/** The title to send, or null when trimming leaves nothing. */
export function cleanSourceTitle(raw: string): string | null {
  const title = raw.trim()
  return title.length > 0 && title.length <= MAX_SOURCE_TITLE ? title : null
}
