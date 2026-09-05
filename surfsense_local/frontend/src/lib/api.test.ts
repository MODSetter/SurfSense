import { afterEach, describe, expect, it, vi } from "vitest"

afterEach(() => {
  vi.unstubAllGlobals()
  vi.resetModules()
})

async function callHealthWith(surfsense: unknown) {
  vi.stubGlobal("window", { surfsense })
  const fetchMock = vi.fn(async (_input: RequestInfo | URL) =>
    Response.json({ status: "ok" })
  )
  vi.stubGlobal("fetch", fetchMock)
  vi.resetModules()
  const { getHealth } = await import("./api")
  await getHealth()
  return String(fetchMock.mock.calls[0]?.[0])
}

describe("api base url", () => {
  it("prefixes root-relative paths with the packaged apiUrl", async () => {
    expect(await callHealthWith({ apiUrl: "http://127.0.0.1:9999" })).toBe(
      "http://127.0.0.1:9999/health"
    )
  })

  it("stays relative in a bare browser so the dev proxy applies", async () => {
    expect(await callHealthWith(undefined)).toBe("/health")
  })
})
