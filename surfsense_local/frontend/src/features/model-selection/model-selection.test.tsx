import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { ModelSelectionPage } from "./model-selection-page"

type InstalledModel = {
  name: string
  installed: boolean
  capabilities: string[]
}

const completionModel = (name: string): InstalledModel => ({
  name,
  installed: true,
  capabilities: ["completion"],
})

function installApi({
  models,
  selected = null,
}: {
  models: InstalledModel[]
  selected?: { provider: string; name: string } | null
}) {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)

    if (path === "/llm/providers") {
      return Response.json([
        { name: "ollama", healthy: true, can_download: true },
      ])
    }
    if (path === "/llm/providers/ollama/models") {
      return Response.json(models)
    }
    if (path === "/llm/selection/generation" && init?.method === "PUT") {
      const payload = JSON.parse(String(init.body)) as {
        provider: string
        name: string
      }
      return Response.json({
        role: "generation",
        ...payload,
        updated_at: "2026-09-05T00:00:00Z",
      })
    }
    if (path === "/llm/selection/generation") {
      return selected
        ? Response.json({
            role: "generation",
            ...selected,
            updated_at: "2026-09-05T00:00:00Z",
          })
        : Response.json({ detail: "no model chosen" }, { status: 404 })
    }

    return Response.json({ detail: "not found" }, { status: 404 })
  })
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("model selection", () => {
  it("offers only installed completion models and saves the explicit choice", async () => {
    const fetchMock = installApi({
      models: [
        completionModel("llama3.2:1b"),
        {
          name: "nomic-embed-text",
          installed: true,
          capabilities: ["embedding"],
        },
      ],
    })
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()

    render(<ModelSelectionPage />)

    const model = await screen.findByRole("radio", {
      name: /llama3\.2:1b/i,
    })
    expect(screen.queryByText("nomic-embed-text")).toBeNull()

    await user.click(model)
    await user.click(screen.getByRole("button", { name: "Use this model" }))

    await screen.findByText("Model selection saved.")
    const write = fetchMock.mock.calls.find(
      ([path, init]) =>
        path === "/llm/selection/generation" && init?.method === "PUT"
    )
    expect(JSON.parse(String(write?.[1]?.body))).toEqual({
      provider: "ollama",
      name: "llama3.2:1b",
    })
  })

  it("finds a model installed after the page was opened", async () => {
    const models = [completionModel("llama3.2:1b")]
    vi.stubGlobal("fetch", installApi({ models }))
    const user = userEvent.setup()

    render(<ModelSelectionPage />)
    await screen.findByText("llama3.2:1b")

    models.push(completionModel("gemma4:12b"))
    await user.click(screen.getByRole("button", { name: "Refresh" }))

    expect(await screen.findByText("gemma4:12b")).toBeTruthy()
  })

  it("supports keyboard model selection", async () => {
    vi.stubGlobal(
      "fetch",
      installApi({
        models: [completionModel("alpha"), completionModel("beta")],
      })
    )
    const user = userEvent.setup()

    render(<ModelSelectionPage />)

    const alpha = await screen.findByRole("radio", { name: /alpha/i })
    const beta = screen.getByRole("radio", { name: /beta/i })
    alpha.focus()
    await user.keyboard(" ")
    expect(alpha.getAttribute("aria-checked")).toBe("true")

    await user.keyboard("{ArrowDown}")
    expect(document.activeElement).toBe(beta)
    await user.keyboard(" ")

    expect(beta.getAttribute("aria-checked")).toBe("true")
  })

  it("continues with an already selected model without writing it again", async () => {
    const fetchMock = installApi({
      models: [completionModel("llama3.2:1b")],
      selected: { provider: "ollama", name: "llama3.2:1b" },
    })
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()
    const onSelected = vi.fn()

    render(<ModelSelectionPage onSelected={onSelected} />)

    await user.click(await screen.findByRole("button", { name: "Continue" }))

    expect(onSelected).toHaveBeenCalledWith(
      expect.objectContaining({ provider: "ollama", name: "llama3.2:1b" })
    )
    expect(
      fetchMock.mock.calls.some(
        ([path, init]) =>
          path === "/llm/selection/generation" && init?.method === "PUT"
      )
    ).toBe(false)
  })

  it("reports a persisted model that is no longer installed", async () => {
    vi.stubGlobal(
      "fetch",
      installApi({
        models: [completionModel("llama3.2:1b")],
        selected: { provider: "ollama", name: "removed:latest" },
      })
    )

    render(<ModelSelectionPage />)

    expect(
      await screen.findByText("Your previous model is no longer available")
    ).toBeTruthy()
    expect(
      (
        screen.getByRole("button", {
          name: "Continue",
        }) as HTMLButtonElement
      ).disabled
    ).toBe(true)
  })
})
