import { strFromU8, strToU8, unzipSync, zipSync } from "fflate"

import { drawablePictureWatermarks } from "./picture-watermark"
import { drawableTextWatermarks } from "./text-watermark"

const HEADER_PART = /^word\/header\d*\.xml$/
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
    const headers = unzipSync(bytes, {
      filter: ({ name, originalSize }) =>
        HEADER_PART.test(name) && originalSize <= MAX_HEADER_BYTES,
    })
    const rewritten = new Map<string, Uint8Array>()
    for (const [name, part] of Object.entries(headers)) {
      const before = strFromU8(part)
      const after = drawableInHeader(before)
      if (after !== before) rewritten.set(name, new Uint8Array(strToU8(after)))
    }
    if (rewritten.size === 0) return file

    let total = 0
    const parts = unzipSync(bytes, {
      filter: ({ originalSize }) => {
        total += originalSize
        return true
      },
    })
    if (total > MAX_FILE_BYTES) return file
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

function drawableInHeader(xml: string): string {
  if (!/<v:(textpath|imagedata)\b/.test(xml)) return xml
  const header = new DOMParser().parseFromString(xml, "application/xml")
  if (header.querySelector("parsererror")) return xml
  const changed = [
    drawableTextWatermarks(header),
    drawablePictureWatermarks(header),
  ].some(Boolean)
  return changed ? new XMLSerializer().serializeToString(header) : xml
}
