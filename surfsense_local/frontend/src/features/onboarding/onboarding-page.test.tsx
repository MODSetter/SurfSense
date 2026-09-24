import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { render } from "@/test-utils"
import { OnboardingPage } from "./onboarding-page"

vi.mock("sonner", () => ({
  toast: { error: vi.fn(), info: vi.fn() },
}))

const budget = {
  device_total_bytes: 16_000_000_000,
  device_free_bytes: 14_000_000_000,
  usable_vram_bytes: 12_900_000_000,
  fit_reserve_bytes: 1_073_741_824,
  ram_available_bytes: 16_000_000_000,
  uma: true,
  has_gpu: true,
}

type Engine = "llamacpp" | "sdcpp" | "audiocpp"

const SLOT: Record<Engine, string> = {
  llamacpp: "text_gen",
  sdcpp: "image_gen",
  audiocpp: "audio_gen",
}

function row(
  engine: Engine,
  name: string,
  file: string,
  overrides: Record<string, unknown> = {}
) {
  return {
    id: file,
    source: "local",
    origin: "curated",
    name,
    family: name.split(" ")[0],
    types: [SLOT[engine]],
    known: true,
    approximate: false,
    selectable_for: [SLOT[engine]],
    support: {
      context: null,
      reads_images: false,
      tools: null,
      reasoning: null,
    },
    runnable: true,
    not_runnable_reason: null,
    default_quantization: "Q4_K_M",
    recommended: false,
    engine,
    voicing:
      engine === "audiocpp"
        ? { peak_mb: 1421, voice_count: 46, languages: ["en-US"] }
        : null,
    lead: { quantization: "Q4_K_M", why: "recommended" },
    builds: [
      {
        catalog_id: `opaque-${file}`,
        quantization: "Q4_K_M",
        footprint_bytes: 2_500_000_000,
        files: [],
        fit: null,
        badge: null,
        can_install: true,
        installed_as: null,
        selected: false,
        recommended: false,
        reads_images: false,
        projector_checked: true,
      },
    ],
    ...overrides,
  }
}

/**
 * A backend with state: installing a build puts it on disk and, when asked to,
 * makes it the slot's model, so the catalog and selection answer accordingly.
 */
function backend({
  rows = [
    row("llamacpp", "Qwen3 4B", "qwen3-4b", { recommended: true }),
    row("llamacpp", "Gemma 3 4B", "gemma-3-4b"),
  ],
  selections = {} as Record<string, Record<string, unknown>>,
  connections = [] as unknown[],
  onDisk = [] as string[],
} = {}) {
  const installed = new Set<string>(onDisk)
  const slotOf = (engine: Engine) => SLOT[engine]

  const catalogRows = () =>
    rows.map((entry) => ({
      ...entry,
      builds: entry.builds.map((build) => {
        const file = build.catalog_id.replace("opaque-", "")
        const onDisk = installed.has(file)
        const selection = selections[slotOf(entry.engine as Engine)]
        return {
          ...build,
          installed_as: onDisk ? file : null,
          selected: onDisk && selection?.name === file,
        }
      }),
    }))

  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    if (path === "/llm/catalog/local") {
      return Response.json({
        budget,
        gpu_status: "present",
        rows: catalogRows(),
        recommended_id: null,
      })
    }
    if (path.startsWith("/llm/selection/")) {
      const slot = path.split("/").at(-1) ?? ""
      if (init?.method === "PUT") {
        selections[slot] = {
          model_type: slot,
          ...JSON.parse(String(init.body)),
          updated_at: "2026-09-24T00:00:00Z",
        }
      }
      return selections[slot]
        ? Response.json(selections[slot])
        : Response.json({ detail: "not selected" }, { status: 404 })
    }
    if (path === "/llm/install" && init?.method === "POST") {
      const body = JSON.parse(String(init.body))
      const file = String(body.catalog_id).replace("opaque-", "")
      const entry = rows.find((candidate) => candidate.id === file)
      const engine = (entry?.engine ?? "llamacpp") as Engine
      installed.add(file)
      const selection = body.select
        ? {
            model_type: slotOf(engine),
            provider: engine,
            connection_id: null,
            name: file,
            updated_at: "2026-09-24T00:00:00Z",
          }
        : null
      if (selection) selections[slotOf(engine)] = selection
      return new Response(
        [
          JSON.stringify({ type: "downloading", completed: 1, total: 2 }),
          JSON.stringify({ type: "complete", selection }),
          "",
        ].join("\n")
      )
    }
    if (path.startsWith("/llm/models/") && init?.method === "DELETE") {
      const file = decodeURIComponent(path.split("/").at(-1) ?? "")
      installed.delete(file)
      let cleared = false
      for (const slot of Object.keys(selections)) {
        if (selections[slot]?.name === file) {
          delete selections[slot]
          cleared = true
        }
      }
      return Response.json({ name: file, selection_cleared: cleared })
    }
    if (
      path.startsWith("/llm/connections/") &&
      !path.endsWith("/models") &&
      init?.method === "DELETE"
    ) {
      const id = Number(path.split("/").at(-1))
      connections = connections.filter(
        (connection) => (connection as { id: number }).id !== id
      )
      return new Response(null, { status: 204 })
    }
    if (path === "/llm/connections" && init?.method === "POST") {
      const created = {
        ...openRouter,
        ...JSON.parse(String(init.body)),
        id: 9,
        has_api_key: false,
      }
      connections = [...connections, created]
      return Response.json(created)
    }
    if (/^\/llm\/connections\/\d+\/models$/.test(path)) {
      return Response.json([])
    }
    if (path === "/llm/connections") return Response.json(connections)
    if (path === "/llm/catalog/remote") return Response.json([])
    if (path.startsWith("/llm/catalog/local/search?")) {
      return Response.json({
        results: [
          {
            repo: "unsloth/Qwen3-14B-GGUF",
            downloads: 1000,
            likes: 1,
            license: "apache-2.0",
            gated: false,
            quantized_from: null,
            last_modified: null,
            reads_images: false,
          },
        ],
      })
    }
    if (path.startsWith("/llm/catalog/local/search/")) {
      return Response.json({
        repo: "unsloth/Qwen3-14B-GGUF",
        gated: false,
        row: row("llamacpp", "unsloth/Qwen3-14B-GGUF", "qwen3-14b", {
          origin: "search",
          lead: null,
        }),
      })
    }
    if (path === "/llm/onboarding" && init?.method === "POST") {
      return Response.json({ completed: true })
    }
    return Response.json({ detail: "not found" }, { status: 404 })
  })
}

const chatChosen = {
  text_gen: {
    model_type: "text_gen",
    provider: "llamacpp",
    connection_id: null,
    name: "qwen3-4b",
    updated_at: "2026-09-24T00:00:00Z",
  },
}

beforeEach(() => {
  // The welcome step mounts OnboardingDither, which reads matchMedia.
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    value: vi.fn().mockReturnValue({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  })
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

/** The footer's status names the slot's model once it is set. */
async function expectReady(name: string) {
  await waitFor(() =>
    expect(
      screen.getByRole("region", { name: "Model ready" }).textContent
    ).toContain(name)
  )
}

async function toChatStep(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: "Start setting up" }))
  await screen.findByRole("heading", { name: "Choose a chat model" })
}

async function toImageStep(user: ReturnType<typeof userEvent.setup>) {
  await toChatStep(user)
  await user.click(await screen.findByRole("button", { name: "Continue" }))
  await screen.findByRole("heading", { name: "Choose an image model" })
}

async function toAudioStep(user: ReturnType<typeof userEvent.setup>) {
  await toImageStep(user)
  await user.click(screen.getByRole("button", { name: "Skip" }))
  await screen.findByRole("heading", { name: "Choose an audio model" })
}

const openRouter = {
  id: 4,
  label: "OpenRouter",
  provider: "openai_compatible",
  base_url: "https://openrouter.ai/api/v1",
  catalog_provider: "openrouter",
  has_api_key: true,
  created_at: "2026-09-24T00:00:00Z",
  updated_at: "2026-09-24T00:00:00Z",
}

describe("onboarding", () => {
  it("walks the welcome, then three steps: chat, image and audio models", async () => {
    vi.stubGlobal("fetch", backend({ selections: { ...chatChosen } }))
    const user = userEvent.setup()
    render(<OnboardingPage onComplete={() => undefined} />)

    // The welcome introduces onboarding; it is not one of its steps.
    expect(screen.queryByLabelText(/Onboarding step/)).toBeNull()
    await toChatStep(user)
    expect(screen.getByLabelText("Onboarding step 1 of 3")).toBeTruthy()
    // The welcome is not somewhere to go back to.
    expect(screen.queryByRole("button", { name: "Back" })).toBeNull()

    await user.click(await screen.findByRole("button", { name: "Continue" }))
    expect(
      await screen.findByRole("heading", { name: "Choose an image model" })
    ).toBeTruthy()
    expect(screen.getByLabelText("Onboarding step 2 of 3")).toBeTruthy()
    expect(screen.getByText("Optional")).toBeTruthy()

    // Skipping the image model moves on; it does not end onboarding.
    await user.click(screen.getByRole("button", { name: "Skip" }))
    expect(
      await screen.findByRole("heading", { name: "Choose an audio model" })
    ).toBeTruthy()
    expect(screen.getByLabelText("Onboarding step 3 of 3")).toBeTruthy()
    expect(screen.getByText("Optional")).toBeTruthy()
    expect(screen.getByRole("button", { name: "Finish" })).toBeTruthy()

    await user.click(screen.getByRole("button", { name: "Back" }))
    expect(
      await screen.findByRole("heading", { name: "Choose an image model" })
    ).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Back" }))
    expect(
      await screen.findByRole("heading", { name: "Choose a chat model" })
    ).toBeTruthy()
  })

  it("lists every model at once, the recommended one first", async () => {
    vi.stubGlobal(
      "fetch",
      backend({
        rows: [
          row("llamacpp", "Qwen3 4B", "qwen3-4b", { recommended: true }),
          row("llamacpp", "Gemma 3 4B", "gemma-3-4b"),
          // The catalog carries every engine's rows; the chat step lists chat's.
          row("sdcpp", "SDXL Turbo", "sdxl-turbo"),
          row("audiocpp", "Kokoro 82M", "kokoro-82m"),
        ],
      })
    )
    const user = userEvent.setup()
    render(<OnboardingPage onComplete={() => undefined} />)
    await toChatStep(user)

    const list = await screen.findByRole("list", {
      name: "Models for this computer",
    })
    const rows = within(list).getAllByRole("listitem")
    expect(rows[0]?.textContent).toContain("Qwen3 4B")
    expect(rows[0]?.textContent).toContain("Recommended")
    expect(rows[1]?.textContent).toContain("Gemma 3 4B")
    expect(rows).toHaveLength(2)
    expect(screen.getByText("Apple Silicon GPU")).toBeTruthy()
    expect(screen.getByText("16 GB memory")).toBeTruthy()
    expect(
      screen.getByRole("region", { name: "Use a server" }).textContent
    ).toContain("Use a server")
  })

  it("holds Continue until the downloaded model is ready", async () => {
    const fetchMock = backend()
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()
    render(<OnboardingPage onComplete={() => undefined} />)
    await toChatStep(user)

    expect(
      screen.getByRole("button", { name: "Continue" }).hasAttribute("disabled")
    ).toBe(true)
    await user.click(
      await screen.findByRole("button", { name: "Download Qwen3 4B Q4_K_M" })
    )

    await expectReady("Qwen3 4B Q4_K_M")
    const install = fetchMock.mock.calls.find(
      ([path]) => path === "/llm/install"
    )
    // Onboarding's download is also the choice: no second click to use it.
    expect(JSON.parse(String(install?.[1]?.body))).toEqual({
      catalog_id: "opaque-qwen3-4b",
      select: true,
    })
    await waitFor(() =>
      expect(
        screen
          .getByRole("button", { name: "Continue" })
          .hasAttribute("disabled")
      ).toBe(false)
    )
    // The list stays: changing the model is picking another row.
    expect(
      screen.getByRole("list", { name: "Models for this computer" })
    ).toBeTruthy()
  })

  it("switches to another downloaded model in place", async () => {
    const fetchMock = backend({
      selections: { ...chatChosen },
      onDisk: ["qwen3-4b", "gemma-3-4b"],
    })
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()
    render(<OnboardingPage onComplete={() => undefined} />)
    await toChatStep(user)

    await expectReady("Qwen3 4B Q4_K_M")
    await user.click(
      screen.getByRole("button", { name: "Use Gemma 3 4B Q4_K_M" })
    )

    await expectReady("Gemma 3 4B Q4_K_M")
    const write = fetchMock.mock.calls.find(
      ([path, init]) =>
        path === "/llm/selection/text_gen" && init?.method === "PUT"
    )
    expect(JSON.parse(String(write?.[1]?.body))).toMatchObject({
      provider: "llamacpp",
      name: "gemma-3-4b",
    })
  })

  it("shows a download under its row and stays put", async () => {
    let release = () => {}
    const held = new Promise<void>((resolve) => {
      release = resolve
    })
    const base = backend()
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        if (String(input) !== "/llm/install") return base(input, init)
        // Let the backend record the install, then hold the stream open.
        const finished = await base(input, init)
        const text = await finished.text()
        const encoder = new TextEncoder()
        return new Response(
          new ReadableStream<Uint8Array>({
            async start(controller) {
              const [progress, complete] = text.split("\n")
              controller.enqueue(encoder.encode(`${progress}\n`))
              await held
              controller.enqueue(encoder.encode(`${complete}\n`))
              controller.close()
            },
          })
        )
      })
    )
    const user = userEvent.setup()
    render(<OnboardingPage onComplete={() => undefined} />)
    await toChatStep(user)

    await user.click(
      await screen.findByRole("button", { name: "Download Gemma 3 4B Q4_K_M" })
    )

    const list = screen.getByRole("list", { name: "Models for this computer" })
    const row = within(list).getByText("Gemma 3 4B").closest("li")
    expect(
      await within(row as HTMLElement).findByRole("progressbar")
    ).toBeTruthy()

    release()
    await waitFor(() =>
      expect(within(row as HTMLElement).getByText("In use")).toBeTruthy()
    )
  })

  it("deletes a downloaded model after confirming, as Settings does", async () => {
    const fetchMock = backend({ onDisk: ["gemma-3-4b"] })
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()
    render(<OnboardingPage onComplete={() => undefined} />)
    await toChatStep(user)

    await user.click(
      await screen.findByRole("button", { name: "Delete Gemma 3 4B" })
    )
    expect(await screen.findByText("Delete Gemma 3 4B?")).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Delete model" }))

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([path, init]) =>
            path === "/llm/models/gemma-3-4b" && init?.method === "DELETE"
        )
      ).toBe(true)
    )
  })

  it("searches Hugging Face on the chat step and installs as the choice", async () => {
    const fetchMock = backend()
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()
    render(<OnboardingPage onComplete={() => undefined} />)
    await toChatStep(user)

    // Closed until asked for: typing reaches a third party.
    expect(
      screen.queryByRole("searchbox", { name: "Search all models" })
    ).toBeNull()
    await user.click(
      await screen.findByRole("button", {
        name: "Not listed? Search Hugging Face",
      })
    )
    // Asked for, so the box takes focus, as a server's search does.
    const search = screen.getByRole("searchbox", { name: "Search all models" })
    expect(search).toBe(document.activeElement)
    await user.type(search, "qwen")
    await user.click(await screen.findByText("unsloth/Qwen3-14B-GGUF"))
    await user.click(
      await screen.findByRole("button", {
        name: "Download unsloth/Qwen3-14B-GGUF Q4_K_M",
      })
    )

    await waitFor(() => {
      const install = fetchMock.mock.calls.find(
        ([path]) => path === "/llm/install"
      )
      expect(JSON.parse(String(install?.[1]?.body))).toEqual({
        catalog_id: "opaque-qwen3-14b",
        select: true,
      })
    })
  })

  it("offers no search on the image or audio step", async () => {
    vi.stubGlobal("fetch", backend({ selections: { ...chatChosen } }))
    const user = userEvent.setup()
    render(<OnboardingPage onComplete={() => undefined} />)
    const search = () =>
      screen.queryByRole("button", { name: "Not listed? Search Hugging Face" })

    await toImageStep(user)
    expect(search()).toBeNull()
    await user.click(screen.getByRole("button", { name: "Skip" }))
    await screen.findByRole("heading", { name: "Choose an audio model" })
    expect(search()).toBeNull()
  })

  it("connects a server when there is none", async () => {
    vi.stubGlobal("fetch", backend())
    const user = userEvent.setup()
    render(<OnboardingPage onComplete={() => undefined} />)
    await toChatStep(user)

    const server = screen.getByRole("region", { name: "Use a server" })
    await user.click(within(server).getByRole("button", { name: "Connect" }))
    // A dialog over the step, not a page: the list stays behind it.
    const dialog = screen.getByRole("dialog", { name: "Connect a server" })
    expect(within(dialog).getByLabelText("Base URL")).toBeTruthy()

    await user.click(within(dialog).getByRole("button", { name: "Cancel" }))
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull())
    expect(
      screen.getByRole("list", { name: "Models for this computer" })
    ).toBeTruthy()
  })

  it("opens a new server's models once it is saved", async () => {
    vi.stubGlobal("fetch", backend())
    const user = userEvent.setup()
    render(<OnboardingPage onComplete={() => undefined} />)
    await toChatStep(user)

    const server = screen.getByRole("region", { name: "Use a server" })
    await user.click(within(server).getByRole("button", { name: "Connect" }))
    const dialog = screen.getByRole("dialog", { name: "Connect a server" })
    await user.type(within(dialog).getByLabelText("Name"), "My vLLM")
    await user.type(
      within(dialog).getByLabelText("Base URL"),
      "http://10.0.0.4:8000/v1"
    )
    await user.click(
      within(dialog).getByRole("button", { name: "Save server" })
    )

    // The server page, with the new server already open on its models.
    expect(
      await screen.findByLabelText("Search models from My vLLM")
    ).toBeTruthy()
  })

  it("names a server connected earlier instead of asking again", async () => {
    vi.stubGlobal(
      "fetch",
      backend({ selections: { ...chatChosen }, connections: [openRouter] })
    )
    const user = userEvent.setup()
    render(<OnboardingPage onComplete={() => undefined} />)
    await toChatStep(user)
    await user.click(await screen.findByRole("button", { name: "Continue" }))

    const server = await screen.findByRole("region", { name: "Use a server" })
    expect(server.textContent).toContain("Connected: OpenRouter")
    expect(
      within(server).getByRole("button", { name: "Show servers" })
    ).toBeTruthy()
  })

  it("edits and disconnects a server with Settings' own actions", async () => {
    const fetchMock = backend({
      selections: { ...chatChosen },
      connections: [openRouter],
    })
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()
    render(<OnboardingPage onComplete={() => undefined} />)
    await toChatStep(user)

    await user.click(
      await screen.findByRole("button", { name: "Show servers" })
    )
    await user.click(screen.getByRole("button", { name: "Edit OpenRouter" }))
    const form = screen.getByRole("dialog", { name: "Edit OpenRouter" })
    expect(
      (within(form).getByLabelText("Name") as HTMLInputElement).value
    ).toBe("OpenRouter")
    await user.click(within(form).getByRole("button", { name: "Cancel" }))
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull())

    await user.click(
      screen.getByRole("button", { name: "Disconnect OpenRouter" })
    )
    expect(
      await screen.findByText("No model in use comes from OpenRouter.")
    ).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Disconnect" }))

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([path, init]) =>
            path === "/llm/connections/4" && init?.method === "DELETE"
        )
      ).toBe(true)
    )
  })

  it("says which model it will use, and from where", async () => {
    vi.stubGlobal(
      "fetch",
      backend({
        connections: [openRouter],
        selections: {
          text_gen: {
            model_type: "text_gen",
            provider: "openai_compatible",
            connection_id: 4,
            name: "aion-labs/aion-2.0",
            updated_at: "2026-09-24T00:00:00Z",
          },
        },
      })
    )
    const user = userEvent.setup()
    render(<OnboardingPage onComplete={() => undefined} />)
    await toChatStep(user)

    // The maker prefix is dropped: the server already says whose it is.
    await waitFor(() =>
      expect(
        screen.getByRole("region", { name: "Model ready" }).textContent
      ).toBe("Using aion-2.0 via OpenRouter")
    )
  })

  it("says when image models cannot run here", async () => {
    vi.stubGlobal("fetch", backend({ selections: { ...chatChosen } }))
    const user = userEvent.setup()
    render(<OnboardingPage onComplete={() => undefined} />)
    await toImageStep(user)

    expect(
      await screen.findByText(/Image models cannot run on this computer/)
    ).toBeTruthy()
    expect(
      screen.getByRole("button", { name: "Continue" }).hasAttribute("disabled")
    ).toBe(true)
  })

  it("says when audio models cannot run here", async () => {
    vi.stubGlobal("fetch", backend({ selections: { ...chatChosen } }))
    const user = userEvent.setup()
    render(<OnboardingPage onComplete={() => undefined} />)
    await toAudioStep(user)

    expect(
      await screen.findByText(/Audio models cannot run on this computer/)
    ).toBeTruthy()
    expect(
      screen.getByRole("button", { name: "Finish" }).hasAttribute("disabled")
    ).toBe(true)
  })

  it("finishes without an image or audio model when both are skipped", async () => {
    const fetchMock = backend({ selections: { ...chatChosen } })
    vi.stubGlobal("fetch", fetchMock)
    const onComplete = vi.fn()
    const user = userEvent.setup()
    render(<OnboardingPage onComplete={onComplete} />)
    await toAudioStep(user)
    expect(onComplete).not.toHaveBeenCalled()

    await user.click(screen.getByRole("button", { name: "Skip" }))

    await waitFor(() => expect(onComplete).toHaveBeenCalledOnce())
    expect(onComplete.mock.calls[0]?.[0]).toMatchObject({ name: "qwen3-4b" })
    expect(
      fetchMock.mock.calls.some(
        ([path, init]) => path === "/llm/onboarding" && init?.method === "POST"
      )
    ).toBe(true)
  })

  it("moves on once an image model is downloaded", async () => {
    const fetchMock = backend({
      selections: { ...chatChosen },
      rows: [
        row("llamacpp", "Qwen3 4B", "qwen3-4b", { recommended: true }),
        row("sdcpp", "SDXL Turbo", "sdxl-turbo"),
      ],
    })
    vi.stubGlobal("fetch", fetchMock)
    const onComplete = vi.fn()
    const user = userEvent.setup()
    render(<OnboardingPage onComplete={onComplete} />)
    await toImageStep(user)

    await user.click(
      await screen.findByRole("button", { name: "Download SDXL Turbo Q4_K_M" })
    )
    await expectReady("SDXL Turbo")
    const next = screen.getByRole("button", { name: "Continue" })
    await waitFor(() => expect(next.hasAttribute("disabled")).toBe(false))
    await user.click(next)

    expect(
      await screen.findByRole("heading", { name: "Choose an audio model" })
    ).toBeTruthy()
    expect(onComplete).not.toHaveBeenCalled()
  })

  it("finishes once an audio model is downloaded", async () => {
    const fetchMock = backend({
      selections: { ...chatChosen },
      rows: [
        row("llamacpp", "Qwen3 4B", "qwen3-4b", { recommended: true }),
        row("audiocpp", "Kokoro 82M", "kokoro-82m"),
      ],
    })
    vi.stubGlobal("fetch", fetchMock)
    const onComplete = vi.fn()
    const user = userEvent.setup()
    render(<OnboardingPage onComplete={onComplete} />)
    await toAudioStep(user)

    await user.click(
      await screen.findByRole("button", { name: "Download Kokoro 82M Q4_K_M" })
    )
    await expectReady("Kokoro 82M")
    const finish = screen.getByRole("button", { name: "Finish" })
    await waitFor(() => expect(finish.hasAttribute("disabled")).toBe(false))
    await user.click(finish)

    await waitFor(() => expect(onComplete).toHaveBeenCalledOnce())
    // Finishing hands the app its chat model, whichever step ends onboarding.
    expect(onComplete.mock.calls[0]?.[0]).toMatchObject({ name: "qwen3-4b" })
  })

  it("never finishes onboarding from the chat or image step", async () => {
    const fetchMock = backend({ selections: { ...chatChosen } })
    vi.stubGlobal("fetch", fetchMock)
    const onComplete = vi.fn()
    const user = userEvent.setup()
    render(<OnboardingPage onComplete={onComplete} />)
    await toAudioStep(user)

    expect(onComplete).not.toHaveBeenCalled()
    expect(
      fetchMock.mock.calls.some(
        ([path, init]) => path === "/llm/onboarding" && init?.method === "POST"
      )
    ).toBe(false)
  })
})
