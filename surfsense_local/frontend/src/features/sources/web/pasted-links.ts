/**
 * Links pasted one per line, or several on a line; a line with no link is named
 * back whole, as the user wrote it.
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
    const lineLinks = words.filter(isWebLink)
    const others = lineLinks.length === 0 ? [words.join(" ")] : []
    for (const link of lineLinks) if (!links.includes(link)) links.push(link)
    for (const other of others)
      if (!notLinks.includes(other)) notLinks.push(other)
  }
  return { links, notLinks }
}

function isWebLink(word: string): boolean {
  try {
    const url = new URL(word)
    return (
      (url.protocol === "http:" || url.protocol === "https:") && !!url.hostname
    )
  } catch {
    return false
  }
}
