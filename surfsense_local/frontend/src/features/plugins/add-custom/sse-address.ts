// A path ending in /sse, before any query or fragment. Read from the text as typed,
// since an address is rarely a valid URL until it is finished.
const SSE_PATH = /\/sse\/*(?:[?#].*)?$/i

/** An address on the older SSE transport, as providers' docs still give it: SurfSense
 *  speaks Streamable HTTP alone, and the server refuses the same rule. */
export function isSseAddress(url: string): boolean {
  return SSE_PATH.test(url.trim())
}
