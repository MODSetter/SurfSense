import { describe, expect, it } from "vitest"

import { prefilledIssue } from "./prefilled-issue"

const SYSTEM = [
  "SurfSense 2.0.2",
  "Windows 10.0.26100 (x64)",
  "Electron 44.2.0 · Chromium 146.0.1 · Node 24.1.0",
].join("\n")

const fields = (url: string) => new URL(url).searchParams

describe("prefilledIssue", () => {
  it("fills the bug form's title and What happened?, and copies the log for its Logs field", () => {
    const issue = prefilledIssue({
      description: "Chat never answers\nIt spins forever.",
      error: "Couldn’t load this chat: Request failed with status 500",
      system: SYSTEM,
      log: [
        "18:21:03 [api] Traceback (most recent call last):",
        "18:21:03 [api] KeyError: 'model'",
      ],
    })

    expect(issue.url).toMatch(
      /^https:\/\/github\.com\/MODSetter\/SurfSense\/issues\/new\?/
    )
    expect(fields(issue.url).get("template")).toBe("bug.yml")
    expect(fields(issue.url).get("title")).toBe("[bug] Chat never answers")
    expect(fields(issue.url).get("what")).toBe(
      "Chat never answers\nIt spins forever.\n\n" +
        "Error: Couldn’t load this chat: Request failed with status 500\n\n" +
        `---\n${SYSTEM}`
    )
    expect(issue.paste).toEqual({
      into: "logs",
      text: "18:21:03 [api] Traceback (most recent call last):\n18:21:03 [api] KeyError: 'model'",
    })
  })

  it("stays within the 2081 characters Windows can open, moving a long description to the clipboard", () => {
    const description = "チャットが応答しません。".repeat(40)

    const issue = prefilledIssue({
      description,
      system: SYSTEM,
      log: ["18:21:03 [api] boom"],
    })

    expect(issue.url.length).toBeLessThanOrEqual(2081)
    expect(fields(issue.url).get("what")).toBe("")
    expect(issue.paste?.into).toBe("what")
    expect(issue.paste?.text).toContain(description)
    expect(issue.paste?.text).toContain("```text\n18:21:03 [api] boom\n```")
  })

  it("copies the newest log lines that fit an issue, and says how many were left out", () => {
    // 100 characters a line with its newline, so 500 fill the 50,000 allowed.
    const log = Array.from(
      { length: 1000 },
      (_, n) => `line ${String(n).padStart(4, "0")} ${"x".repeat(89)}`
    )

    const lines = prefilledIssue({
      description: "Slow",
      log,
    }).paste!.text.split("\n")

    expect(lines[0]).toBe("… 500 earlier lines left out")
    expect(lines[1]).toBe(log[500])
    expect(lines.at(-1)).toBe(log[999])
  })

  it("puts nothing on the clipboard when the log is left out", () => {
    expect(prefilledIssue({ description: "Slow", log: [] }).paste).toBeNull()
  })
})
