import { beforeEach, describe, expect, it, vi } from "vitest"
import { createCodePlugin } from "@streamdown/code"

import { codeHighlighter } from "./code-highlighter"

const tokenized = vi.hoisted(() => ({ count: 0 }))

// Counts each run of the tokenizer.
vi.mock("shiki", async (original) => {
  const actual = await original<typeof import("shiki")>()
  return {
    ...actual,
    createHighlighter: async (
      ...args: Parameters<typeof actual.createHighlighter>
    ) => {
      const highlighter = await actual.createHighlighter(...args)
      const codeToTokens = highlighter.codeToTokens.bind(highlighter)
      highlighter.codeToTokens = (...call) => {
        tokenized.count += 1
        return codeToTokens(...call)
      }
      return highlighter
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
  language: string
) {
  return new Promise<Result>((resolve) => {
    const now = plugin.highlight({ code, language, themes }, resolve)
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
  ])("colours %s exactly as @streamdown/code did", async (language, code) => {
    const ours = await tokensFrom(codeHighlighter, code, language)
    const theirs = await tokensFrom(createCodePlugin(), code, language)

    expect(ours).toEqual(theirs)
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
