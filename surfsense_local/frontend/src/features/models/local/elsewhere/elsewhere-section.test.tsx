import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { toast } from "sonner"

import { render } from "@/test-utils"

import type { LocalBuild, LocalRow } from "../chat/api"
import { fakeInstallApi } from "../installs/fake-install-api"
import type { Elsewhere } from "./api"
import { ElsewhereSection } from "./elsewhere-section"

vi.mock("sonner", () => ({
  toast: { error: vi.fn(), info: vi.fn() },
}))

const ELSEWHERE = "/llm/catalog/local/elsewhere"
const BLOB = "/home/ana/.ollama/models/blobs/sha256-ab12"

const build = (overrides: Partial<LocalBuild> = {}): LocalBuild => ({
  catalog_id: "opaque-found",
  quantization: "Q4_K_M",
  footprint_bytes: 5_027_784_512,
  files: [{ role: "weights", path: "sha256-ab12", size_bytes: 5_027_784_512 }],
  fit: {
    state: "fits",
    need_bytes: 7_000_000_000,
    budget_bytes: 16_000_000_000,
    offload_fraction: 0,
    approximate: false,
  },
  badge: { level: "none", verdict: "", reason: "" },
  can_install: true,
  installed_as: null,
  selected: false,
  recommended: false,
  reads_images: false,
  projector_checked: true,
  bundled: false,
  ...overrides,
})

const found = (
  overrides: Partial<LocalRow> = {},
  builds: LocalBuild[] = [build()]
): LocalRow => ({
  id: "opaque-found",
  source: "local",
  origin: "elsewhere",
  name: "qwen3:8b",
  family: "",
  types: ["text_gen"],
  known: true,
  approximate: false,
  selectable_for: ["text_gen"],
  support: {
    context: 40960,
    reads_images: false,
    tools: true,
    reasoning: true,
  },
  runnable: true,
  not_runnable_reason: null,
  builds,
  default_quantization: null,
  recommended: false,
  engine: "llamacpp",
  lead: { quantization: "Q4_K_M", why: "default" },
  found_in: {
    app: "ollama",
    path: BLOB,
    source: "qwen3:8b",
    architecture: "qwen3",
    parameters: 8_190_735_360,
    quantization: "Q4_K_M",
  },
  ...overrides,
})

const elsewhere = (overrides: Partial<Elsewhere> = {}): Elsewhere => ({
  available: true,
  look: true,
  looked_in: ["ollama"],
  folders: [],
  rows: [found()],
  skipped: [],
  budget: {
    device_total_bytes: 16_000_000_000,
    device_free_bytes: 14_000_000_000,
    usable_vram_bytes: 12_900_000_000,
    fit_reserve_bytes: 1_073_741_824,
    ram_available_bytes: 16_000_000_000,
    uma: true,
    has_gpu: true,
  },
  gpu_status: "present",
  ...overrides,
})

/** The list answers GETs; `extra` answers anything else, or it is a 404. */
function serving(
  data: Elsewhere,
  extra: (path: string, init?: RequestInit) => Response | null = () => null
) {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    if (path === ELSEWHERE && (init?.method ?? "GET") === "GET") {
      return Response.json(data)
    }
    return (
      extra(path, init) ??
      Response.json({ detail: "not found" }, { status: 404 })
    )
  })
}

/** The Electron bridge's picker, answering with `answer` (null: closed). */
function withPicker(answer: string | null) {
  const pick = vi.fn(async () => answer)
  vi.stubGlobal("surfsense", { models: { pick } })
  return pick
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  vi.unstubAllGlobals()
})

describe("models other apps downloaded", () => {
  it("offers one with whose file it is, what its header says, and that nothing is changed", async () => {
    vi.stubGlobal("fetch", serving(elsewhere()))

    render(<ElsewhereSection onUse={vi.fn()} />)

    expect(await screen.findByText("qwen3:8b")).toBeTruthy()
    expect(screen.getByText("Ollama")).toBeTruthy()
    expect(screen.getByText("8.2B parameters")).toBeTruthy()
    expect(screen.getByText("41K context")).toBeTruthy()
    expect(
      screen.getByText(
        "Found in Ollama. SurfSense uses each file where it is and never changes it, and nothing leaves this computer."
      )
    ).toBeTruthy()
    // Nothing to download, so nothing says so.
    expect(
      screen.getByRole("button", { name: "Use qwen3:8b Q4_K_M" })
    ).toBeTruthy()
    expect(screen.queryByRole("button", { name: /Download/ })).toBeNull()
  })

  it("uses one in place with one click: recorded, loaded and chosen", async () => {
    const installs = fakeInstallApi()
    vi.stubGlobal("fetch", serving(elsewhere(), installs.handle))
    const user = userEvent.setup()

    render(<ElsewhereSection onUse={vi.fn()} />)
    await user.click(
      await screen.findByRole("button", { name: "Use qwen3:8b Q4_K_M" })
    )
    expect(await screen.findByRole("progressbar")).toBeTruthy()
    installs.complete()
    await waitFor(() => expect(screen.queryByRole("progressbar")).toBeNull())

    expect(installs.started).toEqual([
      { catalog_id: "opaque-found", select: true, model_type: "text_gen" },
    ])
  })

  it("chooses one already used in place by the name the runtime knows it by", async () => {
    vi.stubGlobal(
      "fetch",
      serving(
        elsewhere({
          rows: [
            found({}, [
              build({ catalog_id: "", installed_as: "ollama-qwen3-8b" }),
            ]),
          ],
        })
      )
    )
    const onUse = vi.fn()
    const user = userEvent.setup()

    render(<ElsewhereSection onUse={onUse} />)
    await user.click(
      await screen.findByRole("button", { name: "Use qwen3:8b Q4_K_M" })
    )

    expect(onUse).toHaveBeenCalledWith("ollama-qwen3-8b")
  })

  it("shows nothing where nothing outside SurfSense can be read", async () => {
    const fetch = serving(elsewhere({ available: false, rows: [] }))
    vi.stubGlobal("fetch", fetch)
    withPicker("/x.gguf")

    const { container } = render(<ElsewhereSection onUse={vi.fn()} />)

    await waitFor(() => expect(fetch).toHaveBeenCalled())
    await waitFor(() => expect(container.textContent).toBe(""))
  })

  it("with nothing found, offers only to pick a file, and only in the app", async () => {
    vi.stubGlobal("fetch", serving(elsewhere({ rows: [], looked_in: [] })))

    const first = render(<ElsewhereSection onUse={vi.fn()} />)
    await waitFor(() => expect(screen.queryByRole("status")).toBeNull())
    expect(first.container.textContent).toBe("")
    first.unmount()

    withPicker(null)
    render(<ElsewhereSection onUse={vi.fn()} />)

    expect(
      await screen.findByText("Already have a GGUF model on this computer?")
    ).toBeTruthy()
    expect(screen.getByRole("button", { name: "Choose a file…" })).toBeTruthy()
    expect(screen.getByRole("button", { name: "Add a folder…" })).toBeTruthy()
  })

  it("installs a picked file in place at once", async () => {
    const installs = fakeInstallApi()
    const picked = found(
      {
        id: "opaque-picked",
        name: "Qwen3 4B",
        found_in: {
          app: "folder",
          path: "/home/ana/Downloads/Qwen3-4B-Q5_K_M.gguf",
          source: null,
          architecture: "qwen3",
          parameters: 4_022_468_096,
          quantization: "Q5_K_M",
        },
      },
      [build({ catalog_id: "opaque-picked", quantization: "Q5_K_M" })]
    )
    const offered: unknown[] = []
    vi.stubGlobal(
      "fetch",
      serving(elsewhere({ rows: [], looked_in: [] }), (path, init) => {
        if (path === `${ELSEWHERE}/file`) {
          offered.push(JSON.parse(String(init?.body)))
          return Response.json({ row: picked })
        }
        return installs.handle(path, init)
      })
    )
    const pick = withPicker("/home/ana/Downloads/Qwen3-4B-Q5_K_M.gguf")
    const user = userEvent.setup()

    render(<ElsewhereSection onUse={vi.fn()} />)
    await user.click(
      await screen.findByRole("button", { name: "Choose a file…" })
    )

    expect(await screen.findByText("Qwen3 4B")).toBeTruthy()
    expect(pick).toHaveBeenCalledWith("file")
    expect(offered).toEqual([
      { path: "/home/ana/Downloads/Qwen3-4B-Q5_K_M.gguf" },
    ])
    await waitFor(() =>
      expect(installs.started).toEqual([
        { catalog_id: "opaque-picked", select: true, model_type: "text_gen" },
      ])
    )
    installs.complete()
    await waitFor(() => expect(screen.queryByRole("progressbar")).toBeNull())
  })

  it("says why a picked file cannot chat, in the interface's words", async () => {
    vi.stubGlobal(
      "fetch",
      serving(elsewhere({ rows: [], looked_in: [] }), (path) =>
        path === `${ELSEWHERE}/file`
          ? Response.json(
              { detail: { code: "embedder", message: "backend prose" } },
              { status: 422 }
            )
          : null
      )
    )
    withPicker("/home/ana/all-MiniLM-L6-v2.gguf")
    const user = userEvent.setup()

    render(<ElsewhereSection onUse={vi.fn()} />)
    await user.click(
      await screen.findByRole("button", { name: "Choose a file…" })
    )

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith(
        "Can’t use this file",
        expect.objectContaining({
          description:
            "This model turns text into numbers for search. It cannot answer questions, and SurfSense already has its own.",
        })
      )
    )
  })

  it("counts the models it cannot run and says why on request", async () => {
    vi.stubGlobal(
      "fetch",
      serving(
        elsewhere({
          skipped: [
            {
              app: "ollama",
              name: "gpt-oss:20b",
              path: "/home/ana/.ollama/models/blobs/sha256-cd34",
              code: "unknown_architecture",
              reason: "backend prose",
            },
          ],
        })
      )
    )
    const user = userEvent.setup()

    render(<ElsewhereSection onUse={vi.fn()} />)
    await user.click(
      await screen.findByRole("button", {
        name: "1 more model SurfSense can’t run",
      })
    )

    expect(
      screen.getByText(
        "gpt-oss:20b (Ollama): This model is in a format SurfSense’s runtime cannot load."
      )
    ).toBeTruthy()
  })

  it("lets Settings turn looking off and stop reading an added folder", async () => {
    const calls: { path: string; method: string; body: unknown }[] = []
    const data = elsewhere({ folders: ["D:\\AI\\models"] })
    vi.stubGlobal(
      "fetch",
      serving(data, (path, init) => {
        if (!path.startsWith(ELSEWHERE)) return null
        calls.push({
          path,
          method: init?.method ?? "GET",
          body: init?.body ? JSON.parse(String(init.body)) : null,
        })
        return Response.json({ ...data, folders: [] })
      })
    )
    const user = userEvent.setup()

    render(<ElsewhereSection onUse={vi.fn()} manage />)
    await user.click(
      await screen.findByRole("button", {
        name: "Stop looking in D:\\AI\\models",
      })
    )
    await user.click(
      screen.getByRole("switch", { name: "Look in other apps’ model folders" })
    )

    await waitFor(() =>
      expect(calls).toEqual([
        {
          path: `${ELSEWHERE}/folders`,
          method: "DELETE",
          body: { path: "D:\\AI\\models" },
        },
        { path: `${ELSEWHERE}/look`, method: "PUT", body: { look: false } },
      ])
    )
  })

  it("keeps the pickers off while the step is busy", async () => {
    vi.stubGlobal("fetch", serving(elsewhere({ rows: [], looked_in: [] })))
    const pick = withPicker("/home/ana/Downloads/Qwen3-4B-Q5_K_M.gguf")
    const user = userEvent.setup()

    render(<ElsewhereSection onUse={vi.fn()} disabled />)
    const file = await screen.findByRole("button", { name: "Choose a file…" })
    const folder = screen.getByRole("button", { name: "Add a folder…" })
    await user.click(file)

    expect((file as HTMLButtonElement).disabled).toBe(true)
    expect((folder as HTMLButtonElement).disabled).toBe(true)
    expect(pick).not.toHaveBeenCalled()
  })

  it("shows a file picked as the step turned busy, and leaves it to Use", async () => {
    // The dialog is open while something else starts: what it returns must
    // not choose a model or start a second install behind that.
    const installs = fakeInstallApi()
    const picked = found(
      {
        id: "opaque-picked",
        name: "Qwen3 4B",
        found_in: {
          app: "folder",
          path: "/home/ana/Downloads/Qwen3-4B-Q5_K_M.gguf",
          source: null,
          architecture: "qwen3",
          parameters: 4_022_468_096,
          quantization: "Q5_K_M",
        },
      },
      [build({ catalog_id: "opaque-picked", quantization: "Q5_K_M" })]
    )
    vi.stubGlobal(
      "fetch",
      serving(elsewhere({ rows: [], looked_in: [] }), (path, init) =>
        path === `${ELSEWHERE}/file`
          ? Response.json({ row: picked })
          : installs.handle(path, init)
      )
    )
    let answer: (path: string | null) => void = () => undefined
    const pick = vi.fn(
      () =>
        new Promise<string | null>((resolve) => {
          answer = resolve
        })
    )
    vi.stubGlobal("surfsense", { models: { pick } })
    const onUse = vi.fn()
    const user = userEvent.setup()

    const view = render(<ElsewhereSection onUse={onUse} />)
    await user.click(
      await screen.findByRole("button", { name: "Choose a file…" })
    )
    view.rerender(<ElsewhereSection onUse={onUse} disabled />)
    answer("/home/ana/Downloads/Qwen3-4B-Q5_K_M.gguf")

    expect(await screen.findByText("Qwen3 4B")).toBeTruthy()
    expect(installs.started).toEqual([])
    expect(onUse).not.toHaveBeenCalled()
  })
})
