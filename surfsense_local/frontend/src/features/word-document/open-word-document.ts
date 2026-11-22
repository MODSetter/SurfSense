import type { DocxDocument } from "@silurus/ooxml/docx"
// Inlined: packaged, the app is on file://, where the library cannot fetch a
// .wasm beside it and the snapshot page's policy keeps the disk out of reach.
import wasmUrl from "../../../node_modules/@silurus/ooxml/dist/docx_parser_bg.wasm?data-url"

import { withDrawableWatermarks } from "./watermarks/with-drawable-watermarks"

/**
 * A Word file parsed for display, by the viewer and the agent's snapshot alike,
 * so both see the same pages: tracked changes show, as a revised copy is
 * reviewed by them. Web fonts stay off: a document never reaches the network.
 * The caller destroys the document.
 */
export async function openWordDocument(
  file: ArrayBuffer
): Promise<DocxDocument> {
  const [{ DocxDocument }, { math }] = await Promise.all([
    import("@silurus/ooxml/docx"),
    import("@silurus/ooxml/math"),
  ])
  return DocxDocument.load(withDrawableWatermarks(file), {
    wasmUrl,
    math,
    useGoogleFonts: false,
    showTrackedChanges: true,
  })
}
