import { beforeEach, describe, expect, it, vi } from "vitest"
import { DEFAULT_SHIKI_THEME } from "@assistant-ui/react-streamdown"
import { createCodePlugin } from "@streamdown/code"
import { bundledLanguages } from "shiki"

import { codeHighlighter } from "./code-highlighter"

const tokenized = vi.hoisted(() => ({ count: 0 }))

// Counts each run of our tokenizer; @streamdown/code's comes from "shiki".
vi.mock("shiki/core", async (original) => {
  const actual = await original<typeof import("shiki/core")>()
  return {
    ...actual,
    createBundledHighlighter: (
      ...bundle: Parameters<typeof actual.createBundledHighlighter>
    ) => {
      const create = actual.createBundledHighlighter(...bundle)
      return async (...args: Parameters<typeof create>) => {
        const highlighter = await create(...args)
        const codeToTokens = highlighter.codeToTokens.bind(highlighter)
        highlighter.codeToTokens = (...call) => {
          tokenized.count += 1
          return codeToTokens(...call)
        }
        return highlighter
      }
    },
  }
})

type Result = NonNullable<ReturnType<typeof codeHighlighter.highlight>>
const themes = codeHighlighter.getThemes()

// Plain text is one uncoloured token a line; tokens carry a theme's colours.
const coloured = (result: Result | null) =>
  result?.tokens.flat().some((token) => token.color !== "inherit") ?? false

/** The tokens a plugin gives for a block, at once or once it has them. */
function tokensFrom(
  plugin: Pick<typeof codeHighlighter, "highlight">,
  code: string,
  language: string,
  asked = themes
) {
  return new Promise<Result>((resolve) => {
    const now = plugin.highlight({ code, language, themes: asked }, resolve)
    if (now && coloured(now)) resolve(now)
  })
}

beforeEach(() => {
  tokenized.count = 0
})

describe("the code highlighter", () => {
  it.each([
    ["ts", "export const total = (a: number) => a * 1.07"],
    ["python", "def total(a):\n    return a * 1.07"],
    ["js", "const answer = 42 // an alias of javascript"],
    ["not-a-language", "plain words"],
    ["", "no language at all"],
    // Grammars that embed others, aliases, and a rarely used grammar.
    ["md", "# Total\n\n```python\nprint(1.07)\n```"],
    ["html", "<style>p{color:red}</style><script>let a = 1</script><b>hi</b>"],
    ["vue", "<template><b>{{ a }}</b></template><script>let a = 1</script>"],
    ["bash", 'for f in *.md; do echo "$f"; done'],
    ["c++", "int main() { return 0; }"],
    ["yml", "key: value\nlist:\n  - 1"],
    ["sql", "SELECT id FROM users WHERE id = 1;"],
    ["latex", "\\frac{a}{b} \\alpha"],
    ["lisp", '(defun hi () (format t "hi"))'],
  ])("colours %s exactly as @streamdown/code did", async (language, code) => {
    const theirPlugin = createCodePlugin()
    // Shiki stops colouring a line after 500 ms, which a busy machine can
    // spend compiling a grammar's patterns the first time; each highlighter
    // compiles them once here, on other text.
    for (const plugin of [codeHighlighter, theirPlugin]) {
      await tokensFrom(plugin, `${code}\n${code}`, language)
    }

    const ours = await tokensFrom(codeHighlighter, code, language)
    const theirs = await tokensFrom(theirPlugin, code, language)

    expect(JSON.stringify(ours)).toBe(JSON.stringify(theirs))
  })

  // Chat replies render through assistant-ui, which asks for its own default
  // rather than getThemes(); a theme the highlighter does not ship stays plain.
  it("colours chat replies in the themes assistant-ui asks for", async () => {
    expect(DEFAULT_SHIKI_THEME).toEqual(themes)

    const reply = await tokensFrom(
      codeHighlighter,
      "const reply = 1",
      "ts",
      DEFAULT_SHIKI_THEME
    )

    expect(coloured(reply)).toBe(true)
  })

  it("offers every language Shiki bundles", () => {
    expect(codeHighlighter.getSupportedLanguages().sort()).toEqual(
      Object.keys(bundledLanguages).sort()
    )
  })

  it("answers a block it has no tokens for at once, with its plain text", () => {
    const code = "let first = 1\nlet second = 2"

    const now = codeHighlighter.highlight(
      { code, language: "ts", themes },
      () => {}
    )

    expect(now?.tokens.map((line) => line.map((t) => t.content))).toEqual([
      ["let first = 1"],
      ["let second = 2"],
    ])
  })

  it("tokenizes a block once, however often it is asked for", async () => {
    const code = "const asked = 'often'"
    const callbacks = Array.from({ length: 4 }, () => vi.fn())

    for (const callback of callbacks) {
      codeHighlighter.highlight({ code, language: "ts", themes }, callback)
    }
    await vi.waitFor(() =>
      expect(
        callbacks.every((callback) => callback.mock.calls.length === 1)
      ).toBe(true)
    )
    const again = codeHighlighter.highlight({ code, language: "ts", themes })

    expect(tokenized.count).toBe(1)
    expect(again).toBe(callbacks[0].mock.calls[0][0])
  })

  it("keeps a bounded number of blocks", async () => {
    const block = (index: number) => `const value${index} = ${index}`
    for (let index = 0; index < 150; index += 1) {
      await tokensFrom(codeHighlighter, block(index), "ts")
    }
    const kept = (index: number) =>
      coloured(
        codeHighlighter.highlight({
          code: block(index),
          language: "ts",
          themes,
        })
      )

    expect(kept(149)).toBe(true)
    expect(kept(0)).toBe(false)
  })
})
