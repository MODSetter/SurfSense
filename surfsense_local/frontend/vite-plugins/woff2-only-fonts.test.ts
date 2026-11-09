import path from "node:path"
import { resolveConfig } from "vite"
import { describe, expect, it } from "vitest"

import { woff2OnlyFonts } from "./woff2-only-fonts"

const KATEX = "/app/node_modules/katex/dist/katex.min.css"
const TAILWIND = "@tailwindcss/vite:generate:build"

/** What the build makes of a module: its new text, or null to leave it be. */
function built(code: string, id = KATEX) {
  const { transform } = woff2OnlyFonts()
  return (transform as (code: string, id: string) => string | null)(code, id)
}

describe("woff2OnlyFonts", () => {
  it("keeps only the WOFF2 of a KaTeX font", () => {
    const css =
      '@font-face{font-family:KaTeX_AMS;font-weight:400;src:url(fonts/KaTeX_AMS-Regular.woff2) format("woff2"),url(fonts/KaTeX_AMS-Regular.woff) format("woff"),url(fonts/KaTeX_AMS-Regular.ttf) format("truetype")}'

    expect(built(css)).toBe(
      '@font-face{font-family:KaTeX_AMS;font-weight:400;src:url(fonts/KaTeX_AMS-Regular.woff2) format("woff2")}'
    )
  })

  it("keeps only the WOFF2 of a Fontsource subset, and its unicode-range", () => {
    const css = `@font-face {
  font-family: 'IBM Plex Mono';
  src: url(./files/ibm-plex-mono-latin-400-normal.woff2) format('woff2'), url(./files/ibm-plex-mono-latin-400-normal.woff) format('woff');
  unicode-range: U+0000-00FF;
}`

    expect(built(css, "/app/node_modules/@fontsource/ibm-plex-mono/400.css"))
      .toBe(`@font-face {
  font-family: 'IBM Plex Mono';
  src: url(./files/ibm-plex-mono-latin-400-normal.woff2) format('woff2');
  unicode-range: U+0000-00FF;
}`)
  })

  it("keeps the local() sources tried before the WOFF2", () => {
    const css =
      '@font-face{font-family:Body;src:local("Calibri"),url("a,b.woff2") format(woff2),url(a.woff) format("woff")}'

    expect(built(css, "/app/src/index.css?direct")).toBe(
      '@font-face{font-family:Body;src:local("Calibri"),url("a,b.woff2") format(woff2)}'
    )
  })

  it("leaves a font with no WOFF2 source as it is", () => {
    const css =
      '@font-face{font-family:Old;src:url(old.woff) format("woff"),url(old.ttf) format("truetype")}'

    expect(built(css)).toBeNull()
  })

  it("leaves everything outside @font-face as it is", () => {
    const css =
      '.logo{background:url(a.woff2) format("woff2"),url(b.png)}@font-face{src:url(x.woff2) format("woff2"),url(x.woff) format("woff")}'

    expect(built(css)).toBe(
      '.logo{background:url(a.woff2) format("woff2"),url(b.png)}@font-face{src:url(x.woff2) format("woff2")}'
    )
  })

  it("leaves a module that is not a stylesheet alone", () => {
    const js =
      'export default `@font-face{src:url(x.woff2) format("woff2"),url(x.woff) format("woff")}`'

    expect(built(js, "/app/src/fonts.ts")).toBeNull()
  })

  // index.css imports KaTeX's and IBM Plex Mono's stylesheets; Tailwind inlines
  // them, so only a transform after it sees their @font-face rules.
  it("runs after Tailwind in the build", async () => {
    const { plugins } = await resolveConfig(
      { configFile: path.join(import.meta.dirname, "..", "vite.config.ts") },
      "build"
    )
    const order = plugins
      .map((plugin) => plugin.name)
      .filter((name) => name === TAILWIND || name === "woff2-only-fonts")

    expect(order).toEqual([TAILWIND, "woff2-only-fonts"])
  }, 30_000)
})
