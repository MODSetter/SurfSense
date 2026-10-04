// @vitest-environment jsdom
import { describe, expect, it } from "vitest"

// The page itself, which Vite builds into dist/ for Electron's hidden window.
import page from "../../../docx-snapshot.html?raw"

function directives(): Map<string, string[]> {
  const html = new DOMParser().parseFromString(page, "text/html")
  const policy = html
    .querySelector('meta[http-equiv="Content-Security-Policy"]')
    ?.getAttribute("content")
  expect(policy).toBeTruthy()
  return new Map(
    (policy ?? "")
      .split(";")
      .map((directive) => directive.trim().split(/\s+/))
      .filter(([name]) => name)
      .map(([name, ...sources]) => [name, sources])
  )
}

describe("the snapshot page's content security policy", () => {
  it("runs no script but the page's own bundle and opens no frame", () => {
    const policy = directives()

    expect(policy.get("default-src")).toEqual(["'none'"])
    expect(policy.get("script-src")).toEqual(["'self'"])
    expect(policy.get("frame-src")).toEqual(["'none'"])
    expect(policy.get("object-src")).toEqual(["'none'"])
    expect(policy.get("base-uri")).toEqual(["'none'"])
    expect(policy.get("form-action")).toEqual(["'none'"])
  })

  it("reaches only the API on loopback, never the disk the packaged page is on", () => {
    const policy = directives()

    // Packaged, 'self' is file://, which would let a script read any local file.
    expect(policy.get("connect-src")).toEqual(["http://127.0.0.1:*"])
    expect(policy.get("img-src")).toEqual(["data:"])
    expect(policy.get("font-src")).toEqual(["data:"])
  })
})
