// A dotted host, then a path: `youtube.com/@seaschool`, as a copied link often is.
const BARE_WITH_PATH = /^[a-z0-9-]+(\.[a-z0-9-]+)+\/\S*$/i

/**
 * Links pasted one per line, or several on a line; a line with no link is named
 * back whole, as the user wrote it. A link without `https://` counts only when it
 * starts with `www.` or has a path, and its whole line is links, so a search such
 * as "node.js tutorial" stays a search.
 */
export function pastedLinks(text: string): {
  links: string[]
  notLinks: string[]
} {
  const links: string[] = []
  const notLinks: string[] = []
  for (const line of text.split("\n")) {
    const words = line.trim().split(/\s+/).filter(Boolean)
    if (words.length === 0) continue
    const full = words.map(fullLink)
    const lineLinks = full.every((link) => link !== null)
      ? (full as string[])
      : words.filter(isWebLink)
    const others = lineLinks.length === 0 ? [words.join(" ")] : []
    for (const link of lineLinks) if (!links.includes(link)) links.push(link)
    for (const other of others)
      if (!notLinks.includes(other)) notLinks.push(other)
  }
  return { links, notLinks }
}

/** The word as a full link, `https://` added to a bare one; null when it is no link. */
function fullLink(word: string): string | null {
  if (isWebLink(word)) return word
  const bare =
    word.toLowerCase().startsWith("www.") || BARE_WITH_PATH.test(word)
  return bare && isWebLink(`https://${word}`) ? `https://${word}` : null
}

function isWebLink(word: string): boolean {
  try {
    const url = new URL(word)
    return (
      (url.protocol === "http:" || url.protocol === "https:") &&
      url.hostname.includes(".")
    )
  } catch {
    return false
  }
}
