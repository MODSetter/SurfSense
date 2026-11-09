import { strToU8, zipSync } from "fflate"

// Under jsdom TextEncoder's bytes are another realm's Uint8Array, which fflate
// would take for a folder.
const utf8 = (text: string) => new Uint8Array(strToU8(text))

const namespaces = (vmlPrefix: string) =>
  [
    'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"',
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"',
    `xmlns:${vmlPrefix}="urn:schemas-microsoft-com:vml"`,
    'xmlns:o="urn:schemas-microsoft-com:office:office"',
  ].join(" ")

/** Word's own shape type for a text watermark, as Design > Watermark writes it. */
export const WORD_TEXT_SHAPE_TYPE = `<v:shapetype id="_x0000_t136" coordsize="21600,21600" o:spt="136" adj="10800" path="m@7,l@8,m@5,21600l@6,21600e"><v:formulas><v:f eqn="sum #0 0 10800"/><v:f eqn="prod #0 2 1"/><v:f eqn="sum 21600 0 @1"/><v:f eqn="sum 0 0 @2"/><v:f eqn="sum 21600 0 @3"/><v:f eqn="if @0 @3 0"/><v:f eqn="if @0 21600 @1"/><v:f eqn="if @0 0 @2"/><v:f eqn="if @0 @4 21600"/><v:f eqn="mid @5 @6"/><v:f eqn="mid @8 @5"/><v:f eqn="mid @7 @8"/><v:f eqn="mid @6 @7"/><v:f eqn="sum @6 0 @5"/></v:formulas><v:path textpathok="t" o:connecttype="custom" o:connectlocs="@9,0;@10,10800;@11,21600;@12,10800" o:connectangles="270,180,90,0"/><v:textpath on="t" fitshape="t"/></v:shapetype>`

/** A text watermark shape, on Word's defaults unless a test says otherwise. */
export function textWatermark({
  text = "DRAFT",
  fillcolor = "silver",
  fontSize = "1pt",
} = {}): string {
  return `<v:shape id="PowerPlusWaterMarkObject1" o:spid="_x0000_s2049" type="#_x0000_t136" style="position:absolute;margin-left:0;margin-top:0;width:412pt;height:165pt;rotation:315;z-index:-251658752;mso-position-horizontal:center;mso-position-horizontal-relative:margin;mso-position-vertical:center;mso-position-vertical-relative:margin" o:allowincell="f" fillcolor="${fillcolor}" stroked="f"><v:fill opacity=".5"/><v:textpath style="font-family:&quot;Calibri&quot;;font-size:${fontSize}" string="${text}"/></v:shape>`
}

/** A picture watermark with Word's Washout on. */
export const WASHED_OUT_PICTURE = `<v:shape id="WordPictureWatermark1" o:spid="_x0000_s2050" type="#_x0000_t75" style="position:absolute;margin-left:0;margin-top:0;width:100pt;height:100pt;z-index:-251658240;mso-position-horizontal:center;mso-position-horizontal-relative:margin;mso-position-vertical:center;mso-position-vertical-relative:margin" o:allowincell="f"><v:imagedata r:id="rId1" o:title="Logo" gain="19661f" blacklevel="22938f"/></v:shape>`

/** One solid black pixel. */
const BLACK_PIXEL = Uint8Array.from(
  atob(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAAAAAA6fptVAAAACklEQVR4nGNgAAAAAgABc3UBGAAAAABJRU5ErkJggg=="
  ),
  (char) => char.charCodeAt(0)
)

/**
 * A one-page Word file whose header holds `vml`: at `word/<headerPart>`, with
 * VML under `vmlPrefix`, which `vml` must use too.
 */
export function wordFileWithHeader(
  vml: string,
  { headerPart = "header1.xml", vmlPrefix = "v" } = {}
): ArrayBuffer {
  const NAMESPACES = namespaces(vmlPrefix)
  const slash = headerPart.lastIndexOf("/")
  const headerRels = `word/${headerPart.slice(0, slash + 1)}_rels/${headerPart.slice(slash + 1)}.rels`
  const toMedia =
    "../".repeat(headerPart.split("/").length - 1) + "media/logo.png"
  const zipped = zipSync({
    "[Content_Types].xml": utf8(
      `<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/${headerPart}" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/></Types>`
    ),
    "_rels/.rels": utf8(
      `<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>`
    ),
    "word/document.xml": utf8(
      `<?xml version="1.0" encoding="UTF-8"?><w:document ${NAMESPACES}><w:body><w:p><w:r><w:t>Body text</w:t></w:r></w:p><w:sectPr><w:headerReference w:type="default" r:id="rId1"/><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/></w:sectPr></w:body></w:document>`
    ),
    "word/_rels/document.xml.rels": utf8(
      `<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header" Target="${headerPart}"/></Relationships>`
    ),
    [`word/${headerPart}`]: utf8(
      `<?xml version="1.0" encoding="UTF-8"?><w:hdr ${NAMESPACES}><w:p><w:r><w:pict>${vml}</w:pict></w:r></w:p></w:hdr>`
    ),
    [headerRels]: utf8(
      `<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="${toMedia}"/></Relationships>`
    ),
    "word/media/logo.png": BLACK_PIXEL,
  })
  return zipped.buffer.slice(
    zipped.byteOffset,
    zipped.byteOffset + zipped.byteLength
  ) as ArrayBuffer
}
