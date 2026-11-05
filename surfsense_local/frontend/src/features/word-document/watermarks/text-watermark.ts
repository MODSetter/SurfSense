const VML = "urn:schemas-microsoft-com:vml"
// Word writes 1pt and relies on fitting the text to the shape. The renderer
// measures at the written size, where rounded advances overlap the letters, so
// anything this small is measured at a size that keeps them.
const SMALLEST_MEASURED_PT = 12
const MEASURED_AT = "96pt"

function pointsOf(size: string): number {
  const value = Number.parseFloat(size)
  if (size.endsWith("in")) return value * 72
  if (size.endsWith("cm")) return (value * 72) / 2.54
  if (size.endsWith("mm")) return (value * 72) / 25.4
  if (size.endsWith("px")) return value * 0.75
  return value
}

/** Fix every text watermark in a header; true if any changed. */
export function drawableTextWatermarks(header: Document): boolean {
  let changed = false
  const set = (element: Element, name: string, value: string) => {
    if (element.getAttribute(name) === value) return
    element.setAttribute(name, value)
    changed = true
  }

  // Without both, the renderer takes the text as switched off.
  for (const type of header.getElementsByTagNameNS(VML, "shapetype")) {
    const typeTextPath = type.getElementsByTagNameNS(VML, "textpath")[0]
    if (!typeTextPath) continue
    let path = type.getElementsByTagNameNS(VML, "path")[0]
    if (!path) {
      path = header.createElementNS(VML, "v:path")
      typeTextPath.before(path)
      changed = true
    }
    set(path, "textpathok", "t")
    if (!typeTextPath.getAttribute("on")) set(typeTextPath, "on", "t")
  }

  for (const textPath of header.getElementsByTagNameNS(VML, "textpath")) {
    const owner = textPath.parentElement
    if (owner?.localName !== "shape") continue

    // Word adds the theme slot after the colour ("#1f497d [3215]"), which the
    // renderer reads as no fill at all.
    const fill = owner.getAttribute("fillcolor")
    if (fill?.includes("[")) set(owner, "fillcolor", fill.split("[")[0].trim())

    const style = textPath.getAttribute("style") ?? ""
    const size = /font-size:\s*([^;]+)/.exec(style)?.[1]?.trim()
    if (
      size &&
      textPath.getAttribute("fitshape") !== "f" &&
      pointsOf(size) < SMALLEST_MEASURED_PT
    ) {
      set(
        textPath,
        "style",
        style.replace(/font-size:\s*[^;]+/, `font-size:${MEASURED_AT}`)
      )
    }
  }
  return changed
}
