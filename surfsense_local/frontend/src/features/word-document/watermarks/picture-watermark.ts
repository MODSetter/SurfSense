const VML = "urn:schemas-microsoft-com:vml"
const WORD = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
const R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
const EMU_PER_PT = 12700

/** A VML fraction: "19661f" is 19661/65536, "30%" a percent, "0.3" as written. */
function fractionOf(value: string | null): number | null {
  if (!value) return null
  const number = Number.parseFloat(value)
  if (!Number.isFinite(number)) return null
  if (value.endsWith("f")) return number / 65536
  if (value.endsWith("%")) return number / 100
  return number
}

function pointsOf(length: string | undefined): number {
  const value = Number.parseFloat(length ?? "")
  if (!Number.isFinite(value)) return 0
  if (length?.endsWith("in")) return value * 72
  if (length?.endsWith("cm")) return (value * 72) / 2.54
  if (length?.endsWith("mm")) return (value * 72) / 25.4
  if (length?.endsWith("px")) return value * 0.75
  return value
}

function parseStyle(style: string): Map<string, string> {
  return new Map(
    style
      .split(";")
      .map((rule) => rule.split(":").map((part) => part.trim()))
      .filter((rule) => rule.length === 2) as [string, string][]
  )
}

function position(
  tag: "positionH" | "positionV",
  style: Map<string, string>,
  axis: "horizontal" | "vertical",
  offset: string
): string {
  const relative =
    style.get(`mso-position-${axis}-relative`) === "page" ? "page" : "margin"
  const align = style.get(`mso-position-${axis}`)
  const placed =
    align && align !== "absolute"
      ? `<wp:align>${align}</wp:align>`
      : `<wp:posOffset>${Math.round(pointsOf(style.get(offset)) * EMU_PER_PT)}</wp:posOffset>`
  return `<wp:${tag} relativeFrom="${relative}">${placed}</wp:${tag}>`
}

/**
 * Word's Washout is gain and black level on VML's imagedata, which the renderer
 * ignores; DrawingML's lum it applies. Word itself writes 0.3 and 0.35 for
 * contrast -70% and brightness 70%, which fixes the two mappings.
 */
function drawingOf(shape: Element, id: number, gain: number, black: number) {
  const data = shape.getElementsByTagNameNS(VML, "imagedata")[0]
  const relationship = data.getAttributeNS(R, "id")
  const style = parseStyle(shape.getAttribute("style") ?? "")
  const width = Math.round(pointsOf(style.get("width")) * EMU_PER_PT)
  const height = Math.round(pointsOf(style.get("height")) * EMU_PER_PT)
  if (!relationship || !width || !height) return null

  const contrast = gain <= 1 ? gain - 1 : 1 - 1 / gain
  const rotation = Number.parseFloat(style.get("rotation") ?? "0") || 0
  const behind = style.get("z-index")?.startsWith("-") ? "1" : "0"
  const xml = `<w:drawing xmlns:w="${WORD}" xmlns:r="${R}" xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"><wp:anchor distT="0" distB="0" distL="0" distR="0" simplePos="0" relativeHeight="1" behindDoc="${behind}" locked="0" layoutInCell="1" allowOverlap="1"><wp:simplePos x="0" y="0"/>${position("positionH", style, "horizontal", "margin-left")}${position("positionV", style, "vertical", "margin-top")}<wp:extent cx="${width}" cy="${height}"/><wp:wrapNone/><wp:docPr id="${id}" name="Watermark"/><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic><pic:nvPicPr><pic:cNvPr id="${id}" name="Watermark"/><pic:cNvPicPr/></pic:nvPicPr><pic:blipFill><a:blip r:embed="${relationship}"><a:lum bright="${Math.round(black * 200000)}" contrast="${Math.round(contrast * 100000)}"/></a:blip><a:stretch><a:fillRect/></a:stretch></pic:blipFill><pic:spPr><a:xfrm rot="${Math.round(rotation * 60000)}"><a:off x="0" y="0"/><a:ext cx="${width}" cy="${height}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic></wp:anchor></w:drawing>`
  return new DOMParser().parseFromString(xml, "application/xml").documentElement
}

/** Redraw every faded VML picture in a header as DrawingML; true if any changed. */
export function drawablePictureWatermarks(header: Document): boolean {
  let changed = false
  const pictures = [...header.getElementsByTagNameNS(WORD, "pict")]
  for (const [index, picture] of pictures.entries()) {
    const shape = picture.getElementsByTagNameNS(VML, "shape")[0]
    const data = shape?.getElementsByTagNameNS(VML, "imagedata")[0]
    if (!data) continue
    const gain = fractionOf(data.getAttribute("gain"))
    const black = fractionOf(data.getAttribute("blacklevel"))
    if (gain === null && black === null) continue
    const drawing = drawingOf(shape, 9000 + index, gain ?? 1, black ?? 0)
    if (!drawing) continue
    picture.replaceWith(header.importNode(drawing, true))
    changed = true
  }
  return changed
}
