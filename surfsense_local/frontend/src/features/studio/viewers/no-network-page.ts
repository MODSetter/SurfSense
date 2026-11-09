// The same policy the API stores in a model-written page (modules/artifacts/
// web_pages/no_network.py, ADR 0066). The viewer adds it too, so a page stored
// before the policy, or edited since, still reaches no host: a request's URL can
// carry what the page read from the user's sources.
export const NO_NETWORK_POLICY =
  "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; " +
  "img-src data: blob:; font-src data:; media-src data: blob:; " +
  "form-action 'none'; base-uri 'none'"

const META = `<meta http-equiv="Content-Security-Policy" content="${NO_NETWORK_POLICY}">`
// Only what may precede a doctype: a byte order mark, whitespace and comments.
const LEADING_DOCTYPE = /^\uFEFF?\s*(?:<!--[\s\S]*?-->\s*)*<!doctype[^>]*>/i

/** The page with the policy first, so no script it wrote runs before it. */
export function withoutNetwork(page: string): string {
  const at = LEADING_DOCTYPE.exec(page)?.[0].length ?? 0
  return page.slice(0, at) + META + page.slice(at)
}
