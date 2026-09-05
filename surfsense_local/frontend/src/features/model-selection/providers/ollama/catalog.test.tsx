import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { ModelSelectionPage } from "../../model-selection-page"

type InstalledModel = {
  name: string
  installed: boolean
  capabilities: string[]
}

function ndjsonResponse(lines: object[]) {
  const encoder = new TextEncoder()
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const line of lines) {
        controller.enqueue(encoder.encode(JSON.stringify(line) + "\n"))
      }
      controller.close()
    },
  })
  return new Response(stream, {
    headers: { "Content-Type": "application/x-ndjson" },
  })
}

function installApi() {
  const models: InstalledModel[] = []

  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input)

      if (path === "/llm/providers") {
        return Response.json([
          {
            name: "ollama",
            healthy: true,
            can_download: true,
            requires_key: false,
            configured: true,
          },
        ])
      }
      if (path === "/llm/providers/ollama/models") {
        return Response.json(models)
      }
      if (path === "/llm/providers/ollama/catalog") {
        return Response.json([
          {
            name: "qwen3:1.7b",
            label: "Qwen3 1.7B",
            size_gb: 1.4,
            installed: false,
          },
          {
            name: "qwen3:4b",
            label: "Qwen3 4B",
            size_gb: 2.6,
            installed: false,
          },
        ])
      }
      if (path === "/llm/providers/ollama/pull" && init?.method === "POST") {
        const { name } = JSON.parse(String(init.body)) as { name: string }
        models.push({ name, installed: true, capabilities: ["completion"] })
        return ndjsonResponse([
          { status: "pulling manifest", completed: 0, total: 0 },
          { status: "downloading", completed: 100, total: 100 },
          { status: "success", completed: 100, total: 100 },
        ])
      }
      if (path === "/llm/selection/generation") {
        return Response.json({ detail: "no model chosen" }, { status: 404 })
      }

      return Response.json({ detail: "not found" }, { status: 404 })
    }
  )

  return fetchMock
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

beforeEach(() => {
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  )
})

describe("model catalog", () => {
  it("downloads a catalog model in-app and promotes it to a choice", async () => {
    const fetchMock = installApi()
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()

    render(<ModelSelectionPage />)

    const downloads = await screen.findAllByRole("button", {
      name: /download/i,
    })
    expect(screen.getByText("Qwen3 1.7B")).toBeTruthy()

    await user.click(downloads[0])

    expect(
      await screen.findByRole("radio", { name: /qwen3:1\.7b/i })
    ).toBeTruthy()

    const pull = fetchMock.mock.calls.find(
      ([path, init]) =>
        path === "/llm/providers/ollama/pull" && init?.method === "POST"
    )
    expect(JSON.parse(String(pull?.[1]?.body))).toEqual({ name: "qwen3:1.7b" })
  })
})
