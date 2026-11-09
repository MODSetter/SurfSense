import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import type { ArtifactDetail } from "../api"
import { HtmlViewer } from "./html-viewer"
import { NO_NETWORK_POLICY, withoutNetwork } from "./no-network-page"

const META = `<meta http-equiv="Content-Security-Policy" content="${NO_NETWORK_POLICY}">`

const page = {
  id: 7,
  title: "Q3 report",
  generation: 1,
  files: [{ role: "primary" }],
} as unknown as ArtifactDetail

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

function open(html: string): HTMLIFrameElement {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(html))
  )
  const queries = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  const { container } = render(
    <QueryClientProvider client={queries}>
      <HtmlViewer artifact={page} />
    </QueryClientProvider>
  )
  return container.querySelector("iframe") ?? (null as never)
}

describe("html viewer", () => {
  it("runs the page's scripts but opens no popups and keeps its own origin", async () => {
    open("<p>hi</p>")
    const frame = await waitFor(() => {
      const found = document.querySelector("iframe")
      if (!found) throw new Error("no frame yet")
      return found
    })
    expect(frame.getAttribute("sandbox")).toBe("allow-scripts")
  })

  it("gives the page no network, even a page stored before the policy", async () => {
    open("<!doctype html><script>fetch('https://x')</script><p>hi</p>")
    const frame = await waitFor(() => {
      const found = document.querySelector("iframe")
      if (!found) throw new Error("no frame yet")
      return found
    })
    const shown = frame.getAttribute("srcdoc") ?? ""
    expect(shown.startsWith(`<!doctype html>${META}`)).toBe(true)
  })
})

describe("withoutNetwork", () => {
  it("puts the policy after the doctype and before anything the page wrote", () => {
    expect(withoutNetwork("<!DOCTYPE html>\n<html><head></head></html>")).toBe(
      `<!DOCTYPE html>${META}\n<html><head></head></html>`
    )
  })

  it("starts a page without a doctype with it", () => {
    expect(withoutNetwork("<p>x</p>")).toBe(`${META}<p>x</p>`)
  })

  it("keeps comments before the doctype first", () => {
    expect(withoutNetwork("<!-- a -->\n<!doctype html><p>x</p>")).toBe(
      `<!-- a -->\n<!doctype html>${META}<p>x</p>`
    )
  })

  it("allows no host at all", () => {
    expect(NO_NETWORK_POLICY).toContain("default-src 'none'")
    expect(NO_NETWORK_POLICY).not.toMatch(/https?:|fonts\./)
  })
})
