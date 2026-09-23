import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { render } from "@/test-utils"

import { ConnectionForm } from "./connection-form"

const connect = (fields: Record<string, unknown>) => ({
  status: "ready",
  base_url: null,
  base_url_origin: null,
  account_fields: [],
  key: "required",
  local: false,
  reason: null,
  ...fields,
})

const provider = (
  id: string,
  name: string,
  fields: Record<string, unknown>
) => ({
  id,
  name,
  doc: null,
  connect: connect(fields),
  type_counts: { text_gen: 1 },
  connections: 0,
})

const PROVIDERS = [
  provider("openai", "OpenAI", {
    base_url: "https://api.openai.com/v1",
    base_url_origin: "reviewed",
  }),
  provider("databricks", "Databricks", {
    status: "needs_account_details",
    base_url: "https://${DATABRICKS_HOST}/ai-gateway/mlflow/v1",
    base_url_origin: "models.dev",
    account_fields: [{ name: "DATABRICKS_HOST", label: "Databricks host" }],
  }),
  provider("amazon-bedrock", "Amazon Bedrock", {
    status: "unreachable",
    reason: "Signs requests with AWS credentials, not an API key",
  }),
  provider("lmstudio", "LM Studio", {
    base_url: "http://127.0.0.1:1234/v1",
    base_url_origin: "models.dev",
    key: "none",
    local: true,
  }),
]

function serve() {
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input)
      if (path === "/llm/catalog/remote") return Response.json(PROVIDERS)
      if (path === "/llm/connections" && init?.method === "POST") {
        return Response.json({ id: 9, ...JSON.parse(String(init.body)) })
      }
      return Response.json({ detail: "not found" }, { status: 404 })
    }
  )
  vi.stubGlobal("fetch", fetchMock)
  return fetchMock
}

function sentBody(fetchMock: ReturnType<typeof serve>) {
  const call = fetchMock.mock.calls.find(
    ([path, init]) => path === "/llm/connections" && init?.method === "POST"
  )
  return JSON.parse(String(call?.[1]?.body))
}

async function pick(user: ReturnType<typeof userEvent.setup>, name: string) {
  await user.click(screen.getByLabelText("Provider"))
  await user.click(
    await screen.findByRole("option", { name: new RegExp(`^${name}`) })
  )
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("connection form", () => {
  it("fills a hosted provider's URL, keeps it editable, and names the provider", async () => {
    const fetchMock = serve()
    const user = userEvent.setup()
    render(<ConnectionForm open onOpenChange={vi.fn()} onSaved={vi.fn()} />)

    await pick(user, "OpenAI")
    const url = screen.getByLabelText("Base URL") as HTMLInputElement
    expect(url.value).toBe("https://api.openai.com/v1")
    expect(
      (screen.getByLabelText("Connection label") as HTMLInputElement).value
    ).toBe("OpenAI")

    // A company proxy in front of OpenAI is still an OpenAI connection.
    await user.clear(url)
    await user.type(url, "https://proxy.example/openai/v1")
    await user.click(screen.getByRole("button", { name: "Save connection" }))

    await waitFor(() =>
      expect(sentBody(fetchMock)).toMatchObject({
        base_url: "https://proxy.example/openai/v1",
        catalog_provider: "openai",
      })
    )
  })

  it("builds the URL from the account details a provider asks for", async () => {
    serve()
    const user = userEvent.setup()
    render(<ConnectionForm open onOpenChange={vi.fn()} onSaved={vi.fn()} />)

    await pick(user, "Databricks")
    await user.type(
      screen.getByLabelText("Databricks host"),
      "dbc-1.cloud.databricks.com"
    )

    expect((screen.getByLabelText("Base URL") as HTMLInputElement).value).toBe(
      "https://dbc-1.cloud.databricks.com/ai-gateway/mlflow/v1"
    )
  })

  it("shows why a provider cannot be reached and does not pick it", async () => {
    serve()
    const user = userEvent.setup()
    render(<ConnectionForm open onOpenChange={vi.fn()} onSaved={vi.fn()} />)

    await user.click(screen.getByLabelText("Provider"))
    const bedrock = await screen.findByRole("option", {
      name: /Amazon Bedrock/,
    })
    expect(bedrock.textContent).toContain("Signs requests with AWS credentials")
    expect(bedrock.getAttribute("aria-disabled")).toBe("true")
    await user.click(bedrock)

    expect(
      (screen.getByLabelText("Provider") as HTMLInputElement).value
    ).not.toBe("Amazon Bedrock")
  })

  it("asks for no key on a local server", async () => {
    serve()
    const user = userEvent.setup()
    render(<ConnectionForm open onOpenChange={vi.fn()} onSaved={vi.fn()} />)

    await pick(user, "LM Studio")

    expect(screen.queryByLabelText("API key")).toBeNull()
  })

  it("saves a typed URL as a custom connection", async () => {
    const fetchMock = serve()
    const user = userEvent.setup()
    render(<ConnectionForm open onOpenChange={vi.fn()} onSaved={vi.fn()} />)

    await user.type(screen.getByLabelText("Connection label"), "Ollama")
    await user.type(
      screen.getByLabelText("Base URL"),
      "http://localhost:11500/v1"
    )
    await user.click(screen.getByRole("button", { name: "Save connection" }))

    await waitFor(() =>
      expect(sentBody(fetchMock)).toMatchObject({
        base_url: "http://localhost:11500/v1",
        catalog_provider: "custom",
      })
    )
  })
})
