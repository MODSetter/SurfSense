import { afterEach, describe, expect, it, vi } from "vitest"

import type { ApiError } from "./api"

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

describe("egress prompt", () => {
  const refused = () =>
    Response.json(
      {
        detail: {
          code: "egress_disabled",
          message: "off",
          destination: "model_download",
          host: "huggingface.co",
        },
      },
      { status: 403 }
    )

  async function load() {
    vi.stubGlobal("window", {})
    vi.resetModules()
    return import("./api")
  }

  it("asks once on a refused write and retries when allowed", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(refused())
      .mockResolvedValueOnce(Response.json({ ok: true }))
    vi.stubGlobal("fetch", fetchMock)
    const { request, setEgressPrompt } = await load()
    const prompt = vi.fn<(error: ApiError) => Promise<boolean>>(
      async () => true
    )
    setEgressPrompt(prompt)

    const response = await request("/llm/install", {
      method: "POST",
    })

    expect(response.ok).toBe(true)
    expect(prompt).toHaveBeenCalledTimes(1)
    expect(prompt.mock.calls[0]?.[0]).toMatchObject({
      code: "egress_disabled",
      detail: { destination: "model_download", host: "huggingface.co" },
    })
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it("throws without retrying when the user cancels", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockResolvedValue(refused()))
    const { request, setEgressPrompt } = await load()
    setEgressPrompt(async () => false)

    await expect(
      request("/llm/install", { method: "POST" })
    ).rejects.toMatchObject({ code: "egress_disabled" })
    expect(fetch).toHaveBeenCalledTimes(1)
  })

  it("never prompts for a background read", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockResolvedValue(refused()))
    const { request, setEgressPrompt } = await load()
    const prompt = vi.fn(async () => true)
    setEgressPrompt(prompt)

    await expect(request("/llm/connections/1/models")).rejects.toMatchObject({
      code: "egress_disabled",
    })
    expect(prompt).not.toHaveBeenCalled()
  })
})
