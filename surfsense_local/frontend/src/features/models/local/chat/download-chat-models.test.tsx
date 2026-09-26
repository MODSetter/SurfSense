import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { toast } from "sonner"

import { EgressPrompt } from "@/features/egress/egress-prompt"
import { render } from "@/test-utils"
import { fakeInstallApi } from "../installs/fake-install-api"
import { parseNdjson } from "../read-ndjson"
import {
  type Fit,
  type LocalBuild,
  type LocalRow,
  type ModelCatalog,
} from "./api"
import { DownloadChatModels } from "./download-chat-models"

vi.mock("sonner", () => ({
  toast: { error: vi.fn(), info: vi.fn() },
}))

const fit = (overrides: Partial<Fit> = {}): Fit => ({
  state: "fits",
  need_bytes: 7_000_000_000,
  budget_bytes: 16_000_000_000,
  offload_fraction: 0,
  approximate: false,
  ...overrides,
})

const build = (overrides: Partial<LocalBuild> = {}): LocalBuild => ({
  catalog_id: "opaque-qwen",
  quantization: "Q4_K_M",
  footprint_bytes: 5_027_784_512,
  files: [
    {
      role: "weights",
      path: "Qwen3-8B-Q4_K_M.gguf",
      size_bytes: 5_027_784_512,
    },
  ],
  fit: fit(),
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

const row = (
  overrides: Partial<LocalRow> = {},
  builds: LocalBuild[] = [build()]
): LocalRow => ({
  id: "qwen3-8b",
  source: "local",
  origin: "curated",
  name: "Qwen3 8B",
  family: "Qwen3",
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
  default_quantization: "Q4_K_M",
  recommended: false,
  engine: "llamacpp",
  lead: { quantization: builds[0]?.quantization ?? "", why: "recommended" },
  ...overrides,
})

const catalog = (overrides: Partial<ModelCatalog> = {}): ModelCatalog => ({
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
  rows: [row()],
  recommended_id: null,
  ...overrides,
})

function stream(chunks: string[]) {
  const encoder = new TextEncoder()
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk))
      controller.close()
    },
  })
}

/** Routes the catalog GET and leaves everything else a 404. */
function serving(
  data: ModelCatalog,
  extra: (path: string, init?: RequestInit) => Response | null = () => null
) {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    if (path === "/llm/catalog/local") return Response.json(data)
    return (
      extra(path, init) ??
      Response.json({ detail: "not found" }, { status: 404 })
    )
  })
}

/** A download outlives its view, so one left running would leak into the next test. */
async function waitForInstallToSettle() {
  await waitFor(() => expect(screen.queryByRole("progressbar")).toBeNull())
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  vi.unstubAllGlobals()
})

describe("model catalog", () => {
  it("parses NDJSON split across arbitrary chunks", async () => {
    const values = []
    for await (const value of parseNdjson<{ type: string }>(
      stream(['{"type":"start', 'ing"}\n{"type":"complete"}'])
    )) {
      values.push(value)
    }
    expect(values).toEqual([{ type: "starting" }, { type: "complete" }])
  })

  it("renders a hardware line and quiet rows with no scan button", async () => {
    // There is no scan: the budget comes from the runtime's own allocator. A
    // build that runs fully carries no badge; a badge is only ever a warning.
    vi.stubGlobal("fetch", serving(catalog()))

    render(<DownloadChatModels />)

    expect(await screen.findByText("Qwen3 8B")).toBeTruthy()
    expect(screen.queryByText("Full speed")).toBeNull()
    expect(screen.queryByRole("button", { name: /scan/i })).toBeNull()
  })

  it("leaves sd.cpp's image models to the image page", async () => {
    // The catalog carries both engines' rows; this page offers chat models.
    vi.stubGlobal(
      "fetch",
      serving(
        catalog({
          rows: [
            row(),
            row(
              {
                id: "stable-diffusion-1.5",
                name: "Stable Diffusion 1.5",
                family: "Stable Diffusion",
                types: ["image_gen"],
                selectable_for: ["image_gen"],
                engine: "sdcpp",
                default_quantization: "Q4_0",
                lead: { quantization: "Q4_0", why: "default" },
              },
              [build({ quantization: "Q4_0", fit: null, badge: null })]
            ),
          ],
        })
      )
    )

    render(<DownloadChatModels />)

    expect(await screen.findByText("Qwen3 8B")).toBeTruthy()
    expect(screen.queryByText("Stable Diffusion 1.5")).toBeNull()
  })

  it("explains a light spill without flagging it", async () => {
    // Recommended on purpose, so it must not wear a warning beside the star.
    vi.stubGlobal(
      "fetch",
      serving(
        catalog({
          rows: [
            row({ recommended: true }, [
              build({
                recommended: true,
                fit: fit({ state: "partial", offload_fraction: 0.2 }),
                badge: {
                  level: "none",
                  verdict: "",
                  reason: "Most of it runs on the GPU.",
                },
              }),
            ]),
          ],
        })
      )
    )

    const user = userEvent.setup()
    render(<DownloadChatModels />)

    expect(await screen.findByText("Most of it runs on the GPU.")).toBeTruthy()
    expect(screen.queryByText("Reduced speed")).toBeNull()
    // The star says why on hover, not only to a screen reader.
    await user.hover(screen.getByLabelText("Recommended for your computer"))
    expect(
      await screen.findByText("Recommended for your computer")
    ).toBeTruthy()
  })

  it("says the card was not detected rather than calling the machine CPU only", async () => {
    // A missing backend library makes the runtime report no devices, silently,
    // with exit 0, on a machine with a working card. Priced against the
    // processor it would otherwise read as a machine that has no card, which is
    // a sentence about the user's hardware and it would be wrong.
    vi.stubGlobal(
      "fetch",
      serving(
        catalog({
          gpu_status: "broken_install",
          budget: { ...catalog().budget, has_gpu: false },
        })
      )
    )

    render(<DownloadChatModels />)

    expect(
      await screen.findByText(/Graphics card not detected by the runtime/)
    ).toBeTruthy()
    expect(screen.queryByText("Runs on your processor")).toBeNull()
  })

  it("installs with only the opaque id, and does not select", async () => {
    // The renderer never sends a repo, file, URL, path or quantization. A
    // download does not choose the model either: Use does, same as image.
    const onSelected = vi.fn()
    const installs = fakeInstallApi()
    vi.stubGlobal("fetch", serving(catalog(), installs.handle))
    const user = userEvent.setup()

    render(<DownloadChatModels onSelected={onSelected} />)
    await user.click(
      await screen.findByRole("button", { name: "Download Qwen3 8B Q4_K_M" })
    )
    expect(await screen.findByRole("progressbar")).toBeTruthy()
    installs.complete()
    await waitForInstallToSettle()

    expect(installs.started).toEqual([
      { catalog_id: "opaque-qwen", select: false },
    ])
    expect(onSelected).not.toHaveBeenCalled()
  })

  it("selects a downloaded chat model when Use is clicked, like image", async () => {
    const onSelected = vi.fn()
    const fetchMock = serving(
      catalog({
        rows: [row({}, [build({ installed_as: "Qwen3-8B-Q4_K_M" })])],
      }),
      (path, init) =>
        path === "/llm/selection/text_gen" && init?.method === "PUT"
          ? Response.json({
              model_type: "text_gen",
              ...JSON.parse(String(init.body)),
              updated_at: "2026-09-24T00:00:00Z",
            })
          : null
    )
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()

    render(<DownloadChatModels onSelected={onSelected} />)
    await user.click(
      await screen.findByRole("button", { name: "Use Qwen3 8B Q4_K_M" })
    )

    await waitFor(() => expect(onSelected).toHaveBeenCalledOnce())
    const call = fetchMock.mock.calls.find(
      ([path, init]) =>
        path === "/llm/selection/text_gen" && init?.method === "PUT"
    )
    expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({
      provider: "llamacpp",
      connection_id: null,
      name: "Qwen3-8B-Q4_K_M",
    })
  })

  it("installs a reduced speed model with no confirmation step", async () => {
    // It runs, slower, and llama.cpp places the layers. Measured: an RTX 3050
    // runs an 8B at roughly 28% on the processor without noticeable lag, so
    // asking the user to confirm would discourage a setup that works.
    vi.stubGlobal(
      "fetch",
      serving(
        catalog({
          rows: [
            row({}, [
              build({
                fit: fit({ state: "partial", offload_fraction: 0.28 }),
                badge: {
                  level: "notice",
                  verdict: "Reduced speed",
                  reason: "Too big for the GPU, so part runs on the CPU.",
                },
              }),
            ]),
          ],
        })
      )
    )

    render(<DownloadChatModels />)

    const action = await screen.findByRole("button", {
      name: "Download Qwen3 8B Q4_K_M",
    })
    expect(action.hasAttribute("disabled")).toBe(false)
    expect(screen.getByText("Reduced speed")).toBeTruthy()
    expect(screen.queryByRole("alertdialog")).toBeNull()
  })

  it("grades the reason line by how much spills", async () => {
    // One sentence is wrong at both ends of a range that runs from barely
    // noticeable to unusable, and the API already knows the fraction.
    vi.stubGlobal(
      "fetch",
      serving(
        catalog({
          rows: [
            row({}, [
              build({
                fit: fit({ state: "partial", offload_fraction: 0.7 }),
                badge: {
                  level: "notice",
                  verdict: "Reduced speed",
                  reason: "Well over the GPU's memory. Expect it to be slow.",
                },
              }),
            ]),
          ],
        })
      )
    )

    render(<DownloadChatModels />)

    expect(
      await screen.findByText(
        "Well over the GPU's memory. Expect it to be slow."
      )
    ).toBeTruthy()
  })

  it("blocks install only when physics refuses", async () => {
    vi.stubGlobal(
      "fetch",
      serving(
        catalog({
          rows: [
            row({}, [
              build({
                fit: fit({ state: "too_big", offload_fraction: 1 }),
                badge: {
                  level: "refuse",
                  verdict: "Won't fit",
                  reason: "Needs about 21 GB. This Mac has 13.6 GB",
                },
                can_install: false,
              }),
            ]),
          ],
        })
      )
    )

    render(<DownloadChatModels />)

    const action = await screen.findByRole("button", {
      name: "Download Qwen3 8B Q4_K_M",
    })
    expect(action.hasAttribute("disabled")).toBe(true)
    expect(
      screen.getByText("Needs about 21 GB. This Mac has 13.6 GB")
    ).toBeTruthy()
  })

  it("marks the recommendation without displaying any rank", async () => {
    // Rank orders the list and selects the star. It is never shown, and the
    // surest way to keep that true is for the row never to carry it.
    vi.stubGlobal(
      "fetch",
      serving(
        catalog({
          rows: [row({ recommended: true }, [build({ recommended: true })])],
          recommended_id: "qwen3-8b",
        })
      )
    )

    render(<DownloadChatModels />)

    expect(
      await screen.findByLabelText("Recommended for your computer")
    ).toBeTruthy()
    expect(screen.queryByText(/rank/i)).toBeNull()
  })

  it("asks to allow huggingface.co the moment the search box is clicked", async () => {
    // Nothing can be searched until that question is answered, so it is asked
    // when the user reaches for the box rather than after a silent refusal.
    const calls: string[] = []
    vi.stubGlobal(
      "fetch",
      serving(catalog(), (path, init) => {
        calls.push(`${init?.method ?? "GET"} ${path}`)
        if (path === "/egress") {
          return Response.json([
            {
              destination: "host:huggingface.co",
              host: "huggingface.co",
              enabled: false,
              last_call_at: null,
            },
          ])
        }
        if (path.startsWith("/egress/")) return Response.json({})
        return null
      })
    )
    const user = userEvent.setup()

    render(
      <>
        <EgressPrompt />
        <DownloadChatModels />
      </>
    )
    await user.click(
      await screen.findByRole("searchbox", { name: "Search all models" })
    )

    await screen.findByRole("alertdialog")
    await user.click(screen.getByRole("button", { name: "Allow" }))

    await waitFor(() =>
      expect(calls).toContain("PUT /egress/host:huggingface.co")
    )
  })

  it("still asks when the box is reached before the answer has loaded", async () => {
    // The panel of destinations is a fetch like any other. Losing that race
    // must not cost the user the question, or they are back to a silent 403.
    let release = () => {}
    const loaded = new Promise<void>((resolve) => {
      release = resolve
    })
    vi.stubGlobal(
      "fetch",
      serving(catalog(), (path) => {
        if (path === "/egress") return null
        if (path.startsWith("/egress/")) return Response.json({})
        return null
      })
    )
    const served = vi.mocked(globalThis.fetch)
    const base = served.getMockImplementation()!
    served.mockImplementation(async (input, init) => {
      if (String(input) === "/egress") {
        await loaded
        return Response.json([
          {
            destination: "host:huggingface.co",
            host: "huggingface.co",
            enabled: false,
            last_call_at: null,
          },
        ])
      }
      return base(input, init)
    })
    const user = userEvent.setup()

    render(
      <>
        <EgressPrompt />
        <DownloadChatModels />
      </>
    )
    await user.click(
      await screen.findByRole("searchbox", { name: "Search all models" })
    )
    expect(screen.queryByRole("alertdialog")).toBeNull()

    release()

    expect(await screen.findByRole("alertdialog")).toBeTruthy()
  })

  it("holds the same height whether or not anything has been searched", async () => {
    // The search section is the last thing in the scroll region, so a region
    // that grows and collapses with the result count drags the page under the
    // user. The space is reserved once and every state renders into it.
    vi.stubGlobal("fetch", serving(catalog()))
    const user = userEvent.setup()

    render(<DownloadChatModels />)

    await screen.findByText(/Type to find a model on Hugging Face/)
    const idle = document.querySelector("[data-slot=search-results]")
    const reserved = idle?.className ?? ""
    expect(reserved).toMatch(/min-h-/)

    await user.type(
      await screen.findByRole("searchbox", { name: "Search all models" }),
      "qwen"
    )
    await screen.findByText(/needs access to huggingface\.co/i)

    expect(
      document.querySelector("[data-slot=search-results]")?.className
    ).toBe(reserved)
  })

  it("clears the search from its own button and keeps focus in the box", async () => {
    vi.stubGlobal("fetch", serving(catalog()))
    const user = userEvent.setup()

    render(<DownloadChatModels />)
    const search = await screen.findByRole<HTMLInputElement>("searchbox", {
      name: "Search all models",
    })
    expect(screen.queryByRole("button", { name: "Clear search" })).toBeNull()

    await user.type(search, "qwen")
    await user.click(screen.getByRole("button", { name: "Clear search" }))

    expect(search.value).toBe("")
    expect(document.activeElement).toBe(search)
    expect(screen.queryByRole("button", { name: "Clear search" })).toBeNull()
  })

  it("explains that search is unavailable rather than erroring", async () => {
    // With egress off, curated and installed still work. That is the airgapped
    // product, not a degraded one.
    vi.stubGlobal("fetch", serving(catalog()))
    const user = userEvent.setup()

    render(<DownloadChatModels />)
    await user.type(
      await screen.findByRole("searchbox", { name: "Search all models" }),
      "qwen"
    )

    expect(
      await screen.findByText(/needs access to huggingface\.co/i)
    ).toBeTruthy()
  })

  it("lists search results and a repo's builds from its listing", async () => {
    // Opening a repo reads its listing only. No header is read to draw the
    // list, so each fit is an estimate and says so.
    vi.stubGlobal(
      "fetch",
      serving(catalog(), (path) => {
        if (path.startsWith("/llm/catalog/local/search?")) {
          return Response.json({
            results: [
              {
                repo: "unsloth/Qwen3-8B-GGUF",
                downloads: 412000,
                likes: 91,
                license: "apache-2.0",
                gated: false,
                quantized_from: "Qwen/Qwen3-8B",
                last_modified: null,
                reads_images: true,
              },
            ],
          })
        }
        if (path.startsWith("/llm/catalog/local/search/")) {
          return Response.json({
            repo: "unsloth/Qwen3-8B-GGUF",
            gated: false,
            row: row(
              {
                id: "unsloth/Qwen3-8B-GGUF",
                origin: "search",
                name: "unsloth/Qwen3-8B-GGUF",
                approximate: true,
                default_quantization: null,
                support: {
                  context: null,
                  reads_images: true,
                  tools: null,
                  reasoning: null,
                },
              },
              [
                build({
                  catalog_id: "ticket-1",
                  fit: fit({ approximate: true }),
                  reads_images: true,
                  projector_checked: false,
                  bundled: false,
                }),
              ]
            ),
          })
        }
        return null
      })
    )
    const user = userEvent.setup()

    render(<DownloadChatModels />)
    await user.type(
      await screen.findByRole("searchbox", { name: "Search all models" }),
      "qwen"
    )

    const hit = await screen.findByText("unsloth/Qwen3-8B-GGUF")
    // Provenance stays in the API, off the row.
    expect(screen.queryByText(/quantized from/)).toBeNull()
    // Said beside the name, before the repo is opened.
    expect(screen.getByText("Vision")).toBeTruthy()
    await user.click(hit)

    const builds = await screen.findByRole("list", {
      name: "Builds in unsloth/Qwen3-8B-GGUF",
    })
    expect(within(builds).getByText("Q4_K_M")).toBeTruthy()
    expect(
      screen.getByText(/Fit is estimated and checked before download/)
    ).toBeTruthy()
    expect(
      within(builds).queryByText("Recommended for your computer")
    ).toBeNull()
  })

  it("shows install failures as a toast instead of inside the model row", async () => {
    const installs = fakeInstallApi()
    vi.stubGlobal("fetch", serving(catalog(), installs.handle))
    const user = userEvent.setup()

    render(<DownloadChatModels />)
    await user.click(
      await screen.findByRole("button", { name: "Download Qwen3 8B Q4_K_M" })
    )
    await screen.findByRole("progressbar")
    installs.move({ type: "error", message: "Download interrupted" })

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith(
        "Download interrupted",
        expect.objectContaining({ id: "model-install-error" })
      )
    )
  })
})

describe("builds of a curated model", () => {
  it("leads with the build the server chose and lists the others on request", async () => {
    vi.stubGlobal(
      "fetch",
      serving(
        catalog({
          rows: [
            row(
              {
                default_quantization: "UD-Q4_K_XL",
                lead: { quantization: "Q4_K_M", why: "recommended" },
              },
              [
                build({ catalog_id: "q3", quantization: "Q3_K_M" }),
                build({
                  catalog_id: "q4",
                  quantization: "Q4_K_M",
                  recommended: true,
                }),
                build({ catalog_id: "ud", quantization: "UD-Q4_K_XL" }),
              ]
            ),
          ],
        })
      )
    )
    const user = userEvent.setup()

    render(<DownloadChatModels />)

    expect(
      await screen.findByRole("button", { name: "Download Qwen3 8B Q4_K_M" })
    ).toBeTruthy()
    expect(
      screen.queryByRole("button", { name: "Download Qwen3 8B Q3_K_M" })
    ).toBeNull()

    await user.click(screen.getByRole("button", { name: "2 other builds" }))

    expect(
      screen.getByRole("button", { name: "Download Qwen3 8B Q3_K_M" })
    ).toBeTruthy()
    expect(
      screen.getByRole("button", { name: "Download Qwen3 8B UD-Q4_K_XL" })
    ).toBeTruthy()
  })

  it("says a model reads images when its build carries a projector", async () => {
    vi.stubGlobal(
      "fetch",
      serving(
        catalog({
          rows: [
            row(
              {
                support: {
                  context: 131072,
                  reads_images: true,
                  tools: null,
                  reasoning: null,
                },
              },
              [build({ reads_images: true })]
            ),
          ],
        })
      )
    )

    render(<DownloadChatModels />)

    expect(await screen.findByText("Vision")).toBeTruthy()
  })
})

describe("a model with no recommended build", () => {
  it("offers the largest build that installs rather than one that cannot", async () => {
    // Step two found nothing that runs well, but a smaller four bit build still
    // installs. The row leads with it, so Download is never needlessly disabled.
    vi.stubGlobal(
      "fetch",
      serving(
        catalog({
          rows: [
            row(
              {
                default_quantization: "UD-Q4_K_XL",
                lead: { quantization: "Q4_K_M", why: "fits_slower" },
              },
              [
                build({
                  catalog_id: "q4",
                  quantization: "Q4_K_M",
                  fit: fit({ state: "partial", offload_fraction: 0.4 }),
                  badge: {
                    level: "notice",
                    verdict: "Reduced speed",
                    reason: "Too big for the GPU, so part runs on the CPU.",
                  },
                }),
                build({
                  catalog_id: "ud",
                  quantization: "UD-Q4_K_XL",
                  can_install: false,
                  fit: fit({ state: "too_big", offload_fraction: 1 }),
                  badge: {
                    level: "refuse",
                    verdict: "Won't fit",
                    reason: "Needs about 6.5 GB. This Mac has 6.4 GB",
                  },
                }),
              ]
            ),
          ],
        })
      )
    )

    render(<DownloadChatModels />)

    const download = await screen.findByRole("button", {
      name: "Download Qwen3 8B Q4_K_M",
    })
    expect(download.hasAttribute("disabled")).toBe(false)
    expect(screen.getByText("Reduced speed")).toBeTruthy()
    expect(screen.queryByText("Won't fit")).toBeNull()
  })
})

describe("installing a searched build", () => {
  it("shows the phase and a progress bar, as a curated build does", async () => {
    const installs = fakeInstallApi()
    vi.stubGlobal(
      "fetch",
      serving(catalog({ rows: [] }), (path, init) => {
        if (path.startsWith("/llm/catalog/local/search?")) {
          return Response.json({
            results: [
              {
                repo: "unsloth/gemma-3-4b-it-GGUF",
                downloads: 1,
                likes: 1,
                license: null,
                gated: false,
                quantized_from: null,
                last_modified: null,
                reads_images: true,
              },
            ],
          })
        }
        if (path.startsWith("/llm/catalog/local/search/")) {
          return Response.json({
            repo: "unsloth/gemma-3-4b-it-GGUF",
            gated: false,
            row: row({ origin: "search", lead: null }, [
              build({
                catalog_id: "ticket-1",
                fit: fit({ approximate: true }),
              }),
            ]),
          })
        }
        return installs.handle(path, init)
      })
    )
    const user = userEvent.setup()

    render(<DownloadChatModels />)
    await user.type(
      await screen.findByRole("searchbox", { name: "Search all models" }),
      "gemma"
    )
    await user.click(await screen.findByText("unsloth/gemma-3-4b-it-GGUF"))
    await user.click(
      await screen.findByRole("button", {
        name: "Download unsloth/gemma-3-4b-it-GGUF Q4_K_M",
      })
    )

    installs.move({ type: "downloading", completed: 5, total: 10 })
    expect(await screen.findByText("Downloading…")).toBeTruthy()
    expect(await screen.findByRole("progressbar")).toBeTruthy()
    installs.complete()
    await waitForInstallToSettle()
  })
})

describe("installing a curated build", () => {
  const twoBuilds = () =>
    catalog({
      rows: [
        row({ lead: { quantization: "UD-Q4_K_XL", why: "recommended" } }, [
          build({
            catalog_id: "ud",
            quantization: "UD-Q4_K_XL",
            recommended: true,
          }),
          build({ catalog_id: "q4", quantization: "Q4_K_M" }),
        ]),
      ],
    })

  it("shows the bar under the lead build when it is the one downloading", async () => {
    const installs = fakeInstallApi()
    vi.stubGlobal("fetch", serving(twoBuilds(), installs.handle))
    const user = userEvent.setup()

    render(<DownloadChatModels />)
    await user.click(
      await screen.findByRole("button", {
        name: "Download Qwen3 8B UD-Q4_K_XL",
      })
    )

    expect(await screen.findByRole("progressbar")).toBeTruthy()
    // Not inside the other builds, which stay collapsed.
    expect(
      screen.queryByRole("list", { name: "Builds of Qwen3 8B" })
    ).toBeNull()
    installs.complete()
    await waitForInstallToSettle()
  })

  it("shows the bar under an other build when it is the one downloading", async () => {
    const installs = fakeInstallApi()
    vi.stubGlobal("fetch", serving(twoBuilds(), installs.handle))
    const user = userEvent.setup()

    render(<DownloadChatModels />)
    await user.click(
      await screen.findByRole("button", { name: "1 other build" })
    )
    await user.click(
      screen.getByRole("button", { name: "Download Qwen3 8B Q4_K_M" })
    )

    const list = await screen.findByRole("list", { name: "Builds of Qwen3 8B" })
    expect(await within(list).findByRole("progressbar")).toBeTruthy()
    installs.complete()
    await waitForInstallToSettle()
  })

  it("queues a second download behind the first instead of blocking it", async () => {
    const installs = fakeInstallApi()
    vi.stubGlobal("fetch", serving(twoBuilds(), installs.handle))
    const user = userEvent.setup()

    render(<DownloadChatModels />)
    await user.click(
      await screen.findByRole("button", {
        name: "Download Qwen3 8B UD-Q4_K_XL",
      })
    )
    await screen.findByRole("progressbar")
    await user.click(screen.getByRole("button", { name: "1 other build" }))
    await user.click(
      screen.getByRole("button", { name: "Download Qwen3 8B Q4_K_M" })
    )
    installs.move({ type: "queued", message: "Waiting" })

    const list = await screen.findByRole("list", { name: "Builds of Qwen3 8B" })
    expect(await within(list).findByText("Waiting…")).toBeTruthy()
    expect(installs.started.map((body) => body.catalog_id)).toEqual([
      "ud",
      "q4",
    ])
    installs.complete("job-1")
    installs.complete("job-2")
    await waitForInstallToSettle()
  })

  it("reports how a download ended though another page started it", async () => {
    // Started before this page opened, as from onboarding or another section.
    const installs = fakeInstallApi({
      running: [
        {
          id: "job-elsewhere",
          catalog_id: "q4",
          label: "Qwen3 8B Q4_K_M",
          model_types: ["text_gen"],
          select: false,
          model_type: null,
          event: { type: "downloading", completed: 1, total: 2 },
        },
      ],
    })
    vi.stubGlobal("fetch", serving(twoBuilds(), installs.handle))

    render(<DownloadChatModels />)
    const list = await screen.findByRole("list", { name: "Builds of Qwen3 8B" })
    expect(await within(list).findByRole("progressbar")).toBeTruthy()
    installs.move(
      { type: "error", message: "Download interrupted" },
      "job-elsewhere"
    )

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith(
        "Download interrupted",
        expect.objectContaining({ id: "model-install-error" })
      )
    )
    await waitForInstallToSettle()
  })

  it("deletes a downloaded model from the Add model page, like the settings list", async () => {
    const fetchMock = serving(
      catalog({
        rows: [row({}, [build({ installed_as: "Qwen3-8B-Q4_K_M" })])],
      }),
      (path, init) =>
        path === "/llm/models/Qwen3-8B-Q4_K_M" && init?.method === "DELETE"
          ? Response.json({ name: "Qwen3-8B-Q4_K_M", selection_cleared: false })
          : null
    )
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()

    render(<DownloadChatModels />)
    await user.click(
      await screen.findByRole("button", { name: "Delete Qwen3 8B" })
    )
    await user.click(
      await screen.findByRole("button", { name: "Delete model" })
    )

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([path, init]) =>
            path === "/llm/models/Qwen3-8B-Q4_K_M" && init?.method === "DELETE"
        )
      ).toBe(true)
    )
  })

  it("reports the model in use becoming unavailable when its deletion clears the slot", async () => {
    const onModelUnavailable = vi.fn()
    vi.stubGlobal(
      "fetch",
      serving(
        catalog({
          rows: [
            row({}, [
              build({ installed_as: "Qwen3-8B-Q4_K_M", selected: true }),
            ]),
          ],
        }),
        (path, init) =>
          path === "/llm/models/Qwen3-8B-Q4_K_M" && init?.method === "DELETE"
            ? Response.json({
                name: "Qwen3-8B-Q4_K_M",
                selection_cleared: true,
              })
            : null
      )
    )
    const user = userEvent.setup()

    render(<DownloadChatModels onModelUnavailable={onModelUnavailable} />)
    await user.click(
      await screen.findByRole("button", { name: "Delete Qwen3 8B" })
    )
    await user.click(
      await screen.findByRole("button", { name: "Delete model" })
    )

    await waitFor(() => expect(onModelUnavailable).toHaveBeenCalled())
  })
})
