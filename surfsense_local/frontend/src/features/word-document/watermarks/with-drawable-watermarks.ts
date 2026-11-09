import { strFromU8, strToU8, unzipSync, zipSync } from "fflate"

import { drawablePictureWatermarks } from "./picture-watermark"
import { drawableTextWatermarks } from "./text-watermark"

// Word's own names, for a file whose relationships cannot be read.
const HEADER_PART = /^word\/header\d*\.xml$/
const DOCUMENT_RELS = "word/_rels/document.xml.rels"
const HEADER_TYPE =
  "http://schemas.openxmlformats.org/officeDocument/2006/relationships/header"
// Beyond these a file is not worth inflating here: it opens with its watermarks
// as written. The viewers already refuse files over 15 MB on disk.
const MAX_HEADER_BYTES = 8 * 1024 * 1024
const MAX_FILE_BYTES = 512 * 1024 * 1024

/**
 * The file with its watermarks in the form the renderer draws as Word does.
 * Only for display: the file a user downloads is never this one. A file with
 * none, or one this cannot read, comes back untouched, for the renderer to judge.
 */
export function withDrawableWatermarks(file: ArrayBuffer): ArrayBuffer {
  try {
    const bytes = new Uint8Array(file)
    // Sized from the zip's own directory before anything is inflated.
    let total = 0
    const rels = unzipSync(bytes, {
      filter: ({ name, originalSize }) => {
        total += originalSize
        return name === DOCUMENT_RELS && originalSize <= MAX_HEADER_BYTES
      },
    })
    if (total > MAX_FILE_BYTES) return file
    const headerParts = headerPartsOf(rels[DOCUMENT_RELS])
    const headers = unzipSync(bytes, {
      filter: ({ name, originalSize }) =>
        (headerParts ? headerParts.has(name) : HEADER_PART.test(name)) &&
        originalSize <= MAX_HEADER_BYTES,
    })
    const rewritten = new Map<string, Uint8Array>()
    for (const [name, part] of Object.entries(headers)) {
      const before = strFromU8(part)
      const after = drawableInHeader(before)
      if (after !== before) rewritten.set(name, new Uint8Array(strToU8(after)))
    }
    if (rewritten.size === 0) return file

    const parts = unzipSync(bytes)
    for (const [name, part] of rewritten) parts[name] = part
    const zipped = zipSync(
      Object.fromEntries(
        Object.entries(parts).map(([name, part]) => [
          name,
          [new Uint8Array(part), { level: 0 }] as const,
        ])
      )
    )
    return zipped.buffer.slice(
      zipped.byteOffset,
      zipped.byteOffset + zipped.byteLength
    ) as ArrayBuffer
  } catch {
    return file
  }
}

/** The parts the document names as headers, or null when its relationships cannot say. */
function headerPartsOf(rels: Uint8Array | undefined): Set<string> | null {
  if (!rels) return null
  const parsed = new DOMParser().parseFromString(
    strFromU8(rels),
    "application/xml"
  )
  if (parsed.querySelector("parsererror")) return null
  const parts = new Set<string>()
  for (const relationship of parsed.getElementsByTagName("Relationship")) {
    const target = relationship.getAttribute("Target")
    if (relationship.getAttribute("Type") !== HEADER_TYPE || !target) continue
    if (relationship.getAttribute("TargetMode") === "External") continue
    parts.add(partName(target))
  }
  return parts
}

/** A relationship's target as a part name: from the package root, or from word/. */
function partName(target: string): string {
  const path = target.startsWith("/") ? target.slice(1) : `word/${target}`
  const resolved: string[] = []
  for (const segment of path.split("/")) {
    if (segment === "..") resolved.pop()
    else if (segment !== "." && segment !== "") resolved.push(segment)
  }
  return resolved.join("/")
}

function drawableInHeader(xml: string): string {
  // Any prefix: the parts below find VML by its namespace.
  if (!/<(?:[\w.-]+:)?(?:textpath|imagedata)\b/.test(xml)) return xml
  const header = new DOMParser().parseFromString(xml, "application/xml")
  if (header.querySelector("parsererror")) return xml
  const changed = [
    drawableTextWatermarks(header),
    drawablePictureWatermarks(header),
  ].some(Boolean)
  return changed ? new XMLSerializer().serializeToString(header) : xml
}
