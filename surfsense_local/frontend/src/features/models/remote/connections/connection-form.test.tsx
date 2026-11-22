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
  provider("opencode", "OpenCode Zen", {
    base_url: "https://opencode.ai/inference/openai/v1",
    base_url_origin: "models.dev",
  }),
  provider("opencode-go", "OpenCode Go", {
    base_url: "https://opencode.ai/inference/go/openai/v1",
    base_url_origin: "models.dev",
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
      if (path === "/llm/connections/chatgpt")
        return Response.json({ serves: ["text_gen"], hosts: [] })
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
    render(<ConnectionForm onCancel={vi.fn()} onSaved={vi.fn()} />)

    await pick(user, "OpenAI")
    const url = screen.getByLabelText("Base URL") as HTMLInputElement
    expect(url.value).toBe("https://api.openai.com/v1")
    expect((screen.getByLabelText("Name") as HTMLInputElement).value).toBe(
      "OpenAI"
    )

    // A company proxy in front of OpenAI is still an OpenAI connection.
    await user.clear(url)
    await user.type(url, "https://proxy.example/openai/v1")
    await user.click(screen.getByRole("button", { name: "Save server" }))

    await waitFor(() =>
      expect(sentBody(fetchMock)).toMatchObject({
        base_url: "https://proxy.example/openai/v1",
        catalog_provider: "openai",
      })
    )
  })

  it("points OpenCode at the Console for its key", async () => {
    serve()
    const user = userEvent.setup()
    render(<ConnectionForm onCancel={vi.fn()} onSaved={vi.fn()} />)

    await pick(user, "OpenCode Zen")

    expect(
      screen
        .getByRole("link", { name: /OpenCode Console/ })
        .getAttribute("href")
    ).toBe("https://opencode.ai/console")
    expect(screen.queryByText(/Go subscription/)).toBeNull()
  })

  it("says OpenCode Go needs its own subscription", async () => {
    serve()
    const user = userEvent.setup()
    render(<ConnectionForm onCancel={vi.fn()} onSaved={vi.fn()} />)

    await pick(user, "OpenCode Go")

    expect(screen.getByRole("link", { name: /OpenCode Console/ })).toBeTruthy()
    expect(screen.getByText(/Go subscription/)).toBeTruthy()
  })

  it("adds no Console link to another provider", async () => {
    serve()
    const user = userEvent.setup()
    render(<ConnectionForm onCancel={vi.fn()} onSaved={vi.fn()} />)

    await pick(user, "OpenAI")

    expect(screen.queryByRole("link", { name: /OpenCode Console/ })).toBeNull()
  })

  it("builds the URL from the account details a provider asks for", async () => {
    serve()
    const user = userEvent.setup()
    render(<ConnectionForm onCancel={vi.fn()} onSaved={vi.fn()} />)

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
    render(<ConnectionForm onCancel={vi.fn()} onSaved={vi.fn()} />)

    await user.click(screen.getByLabelText("Provider"))
    const bedrock = await screen.findByRole("option", {
      name: /Amazon Bedrock/,
    })
    expect(bedrock.textContent).toContain("Signs requests with AWS credentials")
    expect(bedrock.getAttribute("aria-disabled")).toBe("true")
    await user.click(bedrock)

    expect(
      screen.getByRole("combobox", { name: "Provider" }).textContent
    ).not.toContain("Amazon Bedrock")
  })

  it("asks for no key on a local server", async () => {
    serve()
    const user = userEvent.setup()
    render(<ConnectionForm onCancel={vi.fn()} onSaved={vi.fn()} />)

    await pick(user, "LM Studio")

    expect(screen.queryByLabelText("API key")).toBeNull()
  })

  it("saves a typed URL as a custom connection", async () => {
    const fetchMock = serve()
    const user = userEvent.setup()
    render(<ConnectionForm onCancel={vi.fn()} onSaved={vi.fn()} />)

    await user.type(screen.getByLabelText("Name"), "Ollama")
    await user.type(
      screen.getByLabelText("Base URL"),
      "http://localhost:11500/v1"
    )
    await user.click(screen.getByRole("button", { name: "Save server" }))

    await waitFor(() =>
      expect(sentBody(fetchMock)).toMatchObject({
        base_url: "http://localhost:11500/v1",
        catalog_provider: "custom",
      })
    )
  })

  it("searches from an empty box, not after the chosen provider's name", async () => {
    serve()
    const user = userEvent.setup()
    render(<ConnectionForm onCancel={vi.fn()} onSaved={vi.fn()} />)

    await user.click(screen.getByLabelText("Provider"))
    const search = await screen.findByPlaceholderText("Search providers")
    expect((search as HTMLInputElement).value).toBe("")
    await user.type(search, "openai")

    expect(await screen.findByRole("option", { name: /^OpenAI/ })).toBeTruthy()
    expect(screen.queryByRole("option", { name: /^LM Studio/ })).toBeNull()
  })

  it("keeps what is typed in the search when the form renders again", async () => {
    serve()
    const user = userEvent.setup()
    const form = <ConnectionForm onCancel={vi.fn()} onSaved={vi.fn()} />
    const { rerender } = render(form)

    await user.click(screen.getByLabelText("Provider"))
    const search = await screen.findByPlaceholderText("Search providers")
    await user.type(search, "lm")
    rerender(<ConnectionForm onCancel={vi.fn()} onSaved={vi.fn()} />)

    expect((search as HTMLInputElement).value).toBe("lm")
  })

  it("clears the search with a button that appears once something is typed", async () => {
    serve()
    const user = userEvent.setup()
    render(<ConnectionForm onCancel={vi.fn()} onSaved={vi.fn()} />)

    await user.click(screen.getByLabelText("Provider"))
    const search = await screen.findByPlaceholderText("Search providers")
    expect(screen.queryByRole("button", { name: "Clear search" })).toBeNull()

    await user.type(search, "lm")
    expect(screen.queryByRole("option", { name: /^OpenAI/ })).toBeNull()
    await user.click(screen.getByRole("button", { name: "Clear search" }))

    expect((search as HTMLInputElement).value).toBe("")
    expect(document.activeElement).toBe(search)
    expect(await screen.findByRole("option", { name: /^OpenAI/ })).toBeTruthy()
    expect(screen.queryByRole("button", { name: "Clear search" })).toBeNull()
  })

  it("leaves a new ChatGPT sign-in to its own option beside Use a server", async () => {
    serve()
    const user = userEvent.setup()
    render(<ConnectionForm onCancel={vi.fn()} onSaved={vi.fn()} />)
    await user.click(screen.getByLabelText("Provider"))
    await screen.findByRole("option", { name: /^Local or custom server/ })
    expect(
      screen.queryByRole("option", { name: /^ChatGPT subscription/ })
    ).toBeNull()
  })
})
