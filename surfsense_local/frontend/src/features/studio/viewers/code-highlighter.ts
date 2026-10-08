import {
  bundledLanguages,
  bundledLanguagesInfo,
  createHighlighter,
  type BundledLanguage,
  type BundledTheme,
  type Highlighter,
  type ThemeRegistrationAny,
} from "shiki"
import { createJavaScriptRegexEngine } from "shiki/engine/javascript"
import type { CodeHighlighterPlugin, ThemeInput } from "streamdown"

// @streamdown/code's highlighter, with the same engine, themes, languages and
// tokens, but a bounded cache: that one kept the tokens of every string it was
// given until reload, every partial state of a streamed block among them.
const CACHED_BLOCKS = 100

const THEMES: [ThemeInput, ThemeInput] = ["github-light", "github-dark"]

const engine = createJavaScriptRegexEngine({ forgiving: true })
const aliases: Record<string, string> = Object.fromEntries(
  bundledLanguagesInfo.flatMap((info) =>
    (info.aliases ?? []).map((alias) => [alias, info.id])
  )
)
const bundled = new Set(Object.keys(bundledLanguages))

type HighlightResult = NonNullable<
  ReturnType<CodeHighlighterPlugin["highlight"]>
>
type Delivery = (result: HighlightResult) => void
type ShikiTheme = BundledTheme | ThemeRegistrationAny

// One per language, as @streamdown/code: a highlighter shared across languages
// would colour a markdown block's embedded fences differently.
const highlighters = new Map<string, Promise<Highlighter>>()
// Least recently used first: Map keeps insertion order.
const cached = new Map<string, HighlightResult>()
const waiting = new Map<string, Set<Delivery>>()

function languageId(language: string) {
  const name = language.trim().toLowerCase()
  return aliases[name] ?? name
}

function themeName(theme: ThemeInput) {
  return typeof theme === "string" ? theme : (theme.name ?? "custom")
}

function highlighterFor(language: string, themes: [ThemeInput, ThemeInput]) {
  const key = `${language}-${themeName(themes[0])}-${themeName(themes[1])}`
  let highlighter = highlighters.get(key)
  if (!highlighter) {
    highlighter = createHighlighter({
      themes: themes as ShikiTheme[],
      langs: [language],
      engine,
    })
    highlighters.set(key, highlighter)
  }
  return highlighter
}

function remember(key: string, result: HighlightResult) {
  cached.set(key, result)
  if (cached.size > CACHED_BLOCKS) {
    cached.delete(cached.keys().next().value as string)
  }
}

/** The code as Streamdown shows it before any tokens: each line one uncoloured token. */
function plain(code: string): HighlightResult {
  return {
    bg: "transparent",
    fg: "inherit",
    tokens: code.split("\n").map((line) => [
      {
        content: line,
        color: "inherit",
        bgColor: "transparent",
        htmlStyle: {},
        offset: 0,
      },
    ]),
  }
}

function tokenize(
  key: string,
  code: string,
  language: string,
  themes: [ThemeInput, ThemeInput]
) {
  const [light, dark] = [themeName(themes[0]), themeName(themes[1])]
  highlighterFor(bundled.has(language) ? language : "text", themes)
    .then((highlighter) => {
      const result = highlighter.codeToTokens(code, {
        lang: highlighter.getLoadedLanguages().includes(language)
          ? (language as BundledLanguage)
          : "text",
        themes: { light, dark },
      })
      remember(key, result)
      const deliveries = waiting.get(key)
      waiting.delete(key)
      for (const deliver of deliveries ?? []) deliver(result)
    })
    .catch((error: unknown) => {
      waiting.delete(key)
      console.error("[code-highlighter] Failed to highlight code:", error)
    })
}

/** Streamdown's code plugin. A miss answers at once with the plain code, never
 *  null: Streamdown keeps showing its last result on null, which for a block
 *  whose text just changed is older text. */
export const codeHighlighter: CodeHighlighterPlugin = {
  name: "shiki",
  type: "code-highlighter",
  supportsLanguage: (language) => bundled.has(languageId(language)),
  getSupportedLanguages: () => Array.from(bundled),
  getThemes: () => THEMES,
  highlight({ code, language, themes }, callback) {
    const id = languageId(language)
    const key = `${id}:${themeName(themes[0])}:${themeName(themes[1])}:${code}`
    const hit = cached.get(key)
    if (hit) {
      cached.delete(key)
      cached.set(key, hit)
      return hit
    }
    let deliveries = waiting.get(key)
    if (!deliveries) {
      deliveries = new Set()
      waiting.set(key, deliveries)
      tokenize(key, code, id, themes)
    }
    if (callback) deliveries.add(callback)
    return plain(code)
  },
}
