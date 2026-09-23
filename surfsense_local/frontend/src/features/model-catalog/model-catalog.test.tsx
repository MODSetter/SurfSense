import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { toast } from "sonner"

import { EgressPrompt } from "@/features/egress/egress-prompt"
import { render } from "@/test-utils"
import { ModelCatalogPage } from "./model-catalog-page"
import {
  parseNdjson,
  type Fit,
  type LocalBuild,
  type LocalRow,
  type ModelCatalog,
} from "./api"

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

    render(<ModelCatalogPage />)

    expect(await screen.findByText("Qwen3 8B")).toBeTruthy()
    expect(screen.queryByText("Full speed")).toBeNull()
    expect(screen.queryByRole("button", { name: /scan/i })).toBeNull()
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

    render(<ModelCatalogPage />)

    expect(await screen.findByText("Most of it runs on the GPU.")).toBeTruthy()
    expect(screen.getByLabelText("Recommended for this computer")).toBeTruthy()
    expect(screen.queryByText("Reduced speed")).toBeNull()
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

    render(<ModelCatalogPage />)

    expect(
      await screen.findByText(/Graphics card not detected by the runtime/)
    ).toBeTruthy()
    expect(screen.queryByText("Runs on your processor")).toBeNull()
  })

  it("installs with only the opaque id", async () => {
    // The renderer never sends a repo, file, URL, path or quantization.
    const onSelected = vi.fn()
    const fetchMock = serving(catalog(), (path) =>
      path === "/llm/install"
        ? new Response(
            stream([
              '{"type":"downloading","completed":5,"total":10}\n',
              '{"type":"complete","selection":{"role":"generation","provider":"llamacpp","name":"Qwen3-8B-Q4_K_M","updated_at":"2026-09-07T00:00:00Z"}}\n',
            ])
          )
        : null
    )
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()

    render(<ModelCatalogPage onSelected={onSelected} />)
    await user.click(
      await screen.findByRole("button", { name: "Download Qwen3 8B Q4_K_M" })
    )

    await waitFor(() => expect(onSelected).toHaveBeenCalledOnce())
    const call = fetchMock.mock.calls.find(([path]) => path === "/llm/install")
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({
      catalog_id: "opaque-qwen",
      select: true,
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

    render(<ModelCatalogPage />)

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

    render(<ModelCatalogPage />)

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

    render(<ModelCatalogPage />)

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

    render(<ModelCatalogPage />)

    expect(
      await screen.findByLabelText("Recommended for this computer")
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
        <ModelCatalogPage />
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
        <ModelCatalogPage />
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

    render(<ModelCatalogPage />)

    await screen.findByText(/Type to search every model/)
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

  it("explains that search is unavailable rather than erroring", async () => {
    // With egress off, curated and installed still work. That is the airgapped
    // product, not a degraded one.
    vi.stubGlobal("fetch", serving(catalog()))
    const user = userEvent.setup()

    render(<ModelCatalogPage />)
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
                }),
              ]
            ),
          })
        }
        return null
      })
    )
    const user = userEvent.setup()

    render(<ModelCatalogPage />)
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
      within(builds).queryByText("Recommended for this computer")
    ).toBeNull()
  })

  it("shows install failures as a toast instead of inside the model row", async () => {
    vi.stubGlobal(
      "fetch",
      serving(catalog(), (path) =>
        path === "/llm/install"
          ? new Response(
              stream(['{"type":"error","message":"Download interrupted"}\n'])
            )
          : null
      )
    )
    const user = userEvent.setup()

    render(<ModelCatalogPage />)
    await user.click(
      await screen.findByRole("button", { name: "Download Qwen3 8B Q4_K_M" })
    )

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith("Download interrupted", {
        id: "model-install-error",
      })
    )
  })

  it("can use a model on disk that no curated row covers", async () => {
    // A model installed from search is in the directory and not in the
    // manifest, so the curated list has no row to select it from. Without a
    // button here it downloads, lists, deletes — and can never be chosen.
    const fetchMock = serving(
      catalog({
        rows: [
          row(
            {
              id: "some-searched-model",
              origin: "downloaded",
              name: "some-searched-model",
              family: "",
              default_quantization: null,
            },
            [build({ catalog_id: "", installed_as: "some-searched-model" })]
          ),
        ],
      })
    )
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()

    render(<ModelCatalogPage />)
    await user.click(
      await screen.findByRole("button", { name: "Use some-searched-model" })
    )

    await waitFor(() => {
      const selection = fetchMock.mock.calls.find(
        ([path, init]) =>
          String(path).includes("/llm/selection/") && init?.method === "PUT"
      )
      expect(selection).toBeTruthy()
      expect(JSON.parse(String(selection?.[1]?.body)).name).toBe(
        "some-searched-model"
      )
    })
  })

  it("confirms deletion of an installed model", async () => {
    vi.stubGlobal(
      "fetch",
      serving(
        catalog({
          rows: [row({}, [build({ installed_as: "Qwen3-8B-Q4_K_M" })])],
        })
      )
    )
    const user = userEvent.setup()

    render(<ModelCatalogPage allowDelete />)
    await user.click(
      await screen.findByRole("button", { name: "Delete Qwen3 8B" })
    )

    expect(await screen.findByRole("alertdialog")).toBeTruthy()
    expect(screen.getByText("Delete Qwen3 8B?")).toBeTruthy()
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

    render(<ModelCatalogPage />)

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

    render(<ModelCatalogPage />)

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

    render(<ModelCatalogPage />)

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
    let release = () => {}
    const held = new Promise<void>((resolve) => {
      release = resolve
    })
    vi.stubGlobal(
      "fetch",
      serving(catalog({ rows: [] }), (path) => {
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
        if (path === "/llm/install") {
          // Starts downloading, then holds, so the in-flight state is visible.
          const encoder = new TextEncoder()
          return new Response(
            new ReadableStream<Uint8Array>({
              async start(controller) {
                controller.enqueue(
                  encoder.encode(
                    '{"type":"downloading","completed":5,"total":10}\n'
                  )
                )
                await held
                controller.close()
              },
            })
          )
        }
        return null
      })
    )
    const user = userEvent.setup()

    render(<ModelCatalogPage />)
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

    expect(await screen.findByText("Downloading…")).toBeTruthy()
    expect(await screen.findByRole("progressbar")).toBeTruthy()
    release()
  })
})

describe("installing a curated build", () => {
  function holdingInstall() {
    let release = () => {}
    const held = new Promise<void>((resolve) => {
      release = resolve
    })
    const encoder = new TextEncoder()
    const reply = () =>
      new Response(
        new ReadableStream<Uint8Array>({
          async start(controller) {
            controller.enqueue(
              encoder.encode(
                '{"type":"downloading","completed":5,"total":10}\n'
              )
            )
            await held
            controller.close()
          },
        })
      )
    return { reply, release: () => release() }
  }

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
    const install = holdingInstall()
    vi.stubGlobal(
      "fetch",
      serving(twoBuilds(), (path) =>
        path === "/llm/install" ? install.reply() : null
      )
    )
    const user = userEvent.setup()

    render(<ModelCatalogPage />)
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
    install.release()
  })

  it("shows the bar under an other build when it is the one downloading", async () => {
    const install = holdingInstall()
    vi.stubGlobal(
      "fetch",
      serving(twoBuilds(), (path) =>
        path === "/llm/install" ? install.reply() : null
      )
    )
    const user = userEvent.setup()

    render(<ModelCatalogPage />)
    await user.click(
      await screen.findByRole("button", { name: "1 other builds" })
    )
    await user.click(
      screen.getByRole("button", { name: "Download Qwen3 8B Q4_K_M" })
    )

    const list = await screen.findByRole("list", { name: "Builds of Qwen3 8B" })
    expect(await within(list).findByRole("progressbar")).toBeTruthy()
    install.release()
  })
})
