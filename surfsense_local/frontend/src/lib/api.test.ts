import { afterEach, describe, expect, it, vi } from "vitest"

afterEach(() => {
  vi.unstubAllGlobals()
  vi.resetModules()
})

async function callHealthWith(surfsense: unknown) {
  vi.stubGlobal("window", { surfsense })
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    void input
    return Response.json({ status: "ok" })
  })
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

describe("api errors", () => {
  it("preserves structured disk-space details", async () => {
    vi.stubGlobal("window", {})
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        Response.json(
          {
            detail: {
              message: "insufficient disk space",
              required: 5_000_000_000,
              available: 2_000_000_000,
            },
          },
          { status: 507 }
        )
      )
    )
    vi.resetModules()
    const { request } = await import("./api")

    await expect(request("/llm/install")).rejects.toThrow(
      "insufficient disk space (5.0 GB required, 2.0 GB available)"
    )
  })
})
