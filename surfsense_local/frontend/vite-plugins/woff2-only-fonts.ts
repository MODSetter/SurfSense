import type { Plugin } from "vite"

const FONT_FACE = /@font-face\s*\{[^}]*\}/g
const SRC = /(\bsrc\s*:)([^;}]*)/
const WOFF2 = /^url\(.*\)\s*format\(\s*(["']?)woff2\1\s*\)$/s

/** A src list's entries, split at the commas outside url() and quotes. */
function sources(list: string): string[] {
  const entries: string[] = []
  let depth = 0
  let quote = ""
  let start = 0
  for (let index = 0; index < list.length; index += 1) {
    const char = list[index]
    if (quote) {
      if (char === quote) quote = ""
    } else if (char === '"' || char === "'") quote = char
    else if (char === "(") depth += 1
    else if (char === ")") depth -= 1
    else if (char === "," && depth === 0) {
      entries.push(list.slice(start, index))
      start = index + 1
    }
  }
  entries.push(list.slice(start))
  return entries
}

/** Each @font-face's src, cut after its first WOFF2: a browser requests what
 *  follows only when that file fails to load, and the build ships it. */
function dropFallbacksBehindWoff2(css: string): string {
  return css.replace(FONT_FACE, (rule) =>
    rule.replace(SRC, (declaration, property: string, list: string) => {
      const entries = sources(list)
      const woff2 = entries.findIndex((entry) => WOFF2.test(entry.trim()))
      if (woff2 === -1) return declaration
      return property + entries.slice(0, woff2 + 1).join(",")
    })
  )
}

/** Keeps the WOFF and TrueType copies of KaTeX's and IBM Plex Mono's fonts out
 *  of the build: Chromium, the only engine the SPA runs in, reads WOFF2.
 *  Listed after Tailwind, which inlines the stylesheets index.css imports. */
export function woff2OnlyFonts(): Plugin {
  return {
    name: "woff2-only-fonts",
    enforce: "pre",
    transform(code, id) {
      if (!/\.css(\?|$)/.test(id) || !code.includes("@font-face")) return null
      const trimmed = dropFallbacksBehindWoff2(code)
      return trimmed === code ? null : trimmed
    },
  }
}
