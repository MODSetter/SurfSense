type HtmlNode = {
  type: string
  tagName?: string
  value?: string
  properties?: { alt?: unknown }
  children?: HtmlNode[]
}

const isBlank = (node: HtmlNode) =>
  node.type === "text" && (node.value ?? "").trim() === ""

function withoutImages(parent: HtmlNode) {
  parent.children = parent.children?.flatMap((child): HtmlNode[] => {
    if (child.tagName === "img") {
      const alt = String(child.properties?.alt ?? "").trim()
      return alt ? [{ type: "text", value: alt }] : []
    }
    withoutImages(child)
    // A paragraph that only held an image would leave a gap.
    const emptied =
      child.tagName === "p" && (child.children ?? []).every(isBlank)
    return emptied ? [] : [child]
  })
}

/** A rehype pass: a chunk's image reads as its description, or goes. It is never
 *  loaded, and harden's "[Image blocked: …]" would be noise on most web pages. */
export function imagesAsTheirDescriptions() {
  return withoutImages
}
