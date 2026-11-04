import { afterEach, describe, expect, it, vi } from "vitest"
import {
  cleanup,
  fireEvent,
  screen,
  waitFor,
  within,
} from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import {
  AssistantRuntimeProvider,
  useLocalRuntime,
  type AppendMessage,
} from "@assistant-ui/react"

import { TooltipProvider } from "@/components/ui/tooltip"
import type { ModelSelection } from "@/features/models/selection/api"
import type { Plugin } from "@/features/plugins/api"
import {
  createStartupInput,
  type StartupInput,
} from "@/features/startup/startup-input"
import { StartupInputContext } from "@/features/startup/startup-input-context"
import type { WorkspaceDocument } from "@/features/sources/api"
import type { SourceFolder } from "@/features/sources/tree/folders-api"
import { indexSources } from "@/features/sources/tree/source-index"
import type { Artifact } from "@/features/studio/api"
import { render } from "@/test-utils"

import { ChatComposer } from "./chat-composer"
import type { Mentionables } from "./mentions/mention-items"
import { namedSources, picksOf } from "./mentions/named-sources"
import { QUESTION_MAX_CHARS } from "./question-limit"
import { readThinkingOn } from "./thinking-preference"

const MODEL: ModelSelection = {
  model_type: "text_gen" as const,
  provider: "llamacpp" as const,
  connection_id: null,
  name: "Qwen3-1.7B-Q4_K_M",
  updated_at: "2026-09-05T00:00:00Z",
}

function plugin(extra: Partial<Plugin>): Plugin {
  return {
    id: "notes",
    name: "Notes",
    source: "first_party",
    url: "https://notes.example/mcp",
    hosts: ["notes.example"],
    auth_type: "none",
    header_names: [],
    transport: "streamable_http",
    needs_scopes: [],
    own_app: false,
    needs_own_app: null,
    never_signed_in: false,
    enabled: true,
    disconnected: false,
    connected_at: "2026-10-01T00:00:00Z",
    checked_at: "2026-10-01T00:00:00Z",
    check_failure: null,
    removed_reason: null,
    tools: [],
    ...extra,
  }
}

type RunConfig = AppendMessage["runConfig"]

const FOLDERS = [
  { id: 1, name: "Library", parent_id: null },
  { id: 2, name: "Contracts", parent_id: 1 },
] as SourceFolder[]
const DOCUMENTS = [
  { id: 3, title: "Plan Q3.pdf", status: "ready", folder_id: 2 },
  { id: 4, title: "Memo", status: "ready", folder_id: 1 },
] as WorkspaceDocument[]
const LIBRARY: Mentionables = {
  documents: DOCUMENTS,
  index: indexSources(FOLDERS, DOCUMENTS),
  artifacts: [
    {
      id: 9,
      document_id: 109,
      format: "pptx",
      title: "Board deck",
      status: "ready",
      version: null,
    } as Artifact,
  ],
}

function Harness({
  model = MODEL,
  onUploadSources,
  threadMode,
  onOpenPlugins,
  startup = null,
  mentionables,
  onRun,
}: {
  model?: ModelSelection
  onUploadSources?: (files: File[]) => void
  threadMode?: "agentic" | "basic"
  onOpenPlugins?: () => void
  startup?: StartupInput | null
  mentionables?: Mentionables
  onRun?: (runConfig: RunConfig) => void
}) {
  const runtime = useLocalRuntime({
    run: async ({ runConfig }) => {
      onRun?.(runConfig)
      return { content: [] }
    },
  })
  return (
    <StartupInputContext.Provider value={startup}>
      <AssistantRuntimeProvider runtime={runtime}>
        <ChatComposer
          placement="center"
          model={model}
          sourceCount={0}
          isRunning={false}
          providerAvailable
          onModelSetup={() => undefined}
          onModelSelected={() => undefined}
          readsImages={false}
          onUploadSources={onUploadSources}
          threadMode={threadMode}
          onOpenPlugins={onOpenPlugins}
          mentionables={mentionables}
        />
      </AssistantRuntimeProvider>
    </StartupInputContext.Provider>
  )
}

// What the startup frame's box held when the dashboard took over.
function typedDuringStartup(text: string, caret: number) {
  const startup = createStartupInput()
  startup.keep(text, caret)
  return startup
}

async function openThinking(user: ReturnType<typeof userEvent.setup>) {
  await user.click(
    screen.getByRole("button", { name: "Add images, sources, and more" })
  )
  return screen.findByRole("menuitemcheckbox", { name: /^Thinking/ })
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe("chat composer after startup", () => {
  it("takes what was typed while the app loaded, with its caret, and keeps focus", async () => {
    render(
      <TooltipProvider>
        <Harness startup={typedDuringStartup("find jobs today", 9)} />
      </TooltipProvider>
    )

    const box = screen.getByRole<HTMLTextAreaElement>("textbox", {
      name: "Message",
    })
    await waitFor(() => expect(box.value).toBe("find jobs today"))
    expect(box.selectionStart).toBe(9)
    expect(document.activeElement).toBe(box)
  })

  it("opens the list on a mention typed while the app loaded", async () => {
    render(
      <TooltipProvider>
        <Harness
          threadMode="agentic"
          mentionables={LIBRARY}
          startup={typedDuringStartup("compare with @pla", 17)}
        />
      </TooltipProvider>
    )

    const list = await screen.findByRole("listbox", {
      name: "Sources and artifacts",
    })
    await waitFor(() => expect(list.textContent).toContain("Plan Q3.pdf"))
    expect(list.textContent).not.toContain("Memo")
  })

  it("opens the list on a mention the caret was left inside", async () => {
    render(
      <TooltipProvider>
        <Harness
          threadMode="agentic"
          mentionables={LIBRARY}
          startup={typedDuringStartup("ask @pla about jobs", 8)}
        />
      </TooltipProvider>
    )

    const list = await screen.findByRole("listbox", {
      name: "Sources and artifacts",
    })
    await waitFor(() => expect(list.textContent).toContain("Plan Q3.pdf"))
    expect(
      screen.getByRole<HTMLTextAreaElement>("textbox", { name: "Message" })
        .selectionStart
    ).toBe(8)
  })

  it("starts empty when another composer took the text already", async () => {
    const startup = typedDuringStartup("find jobs", 9)
    const first = render(
      <TooltipProvider>
        <Harness startup={startup} />
      </TooltipProvider>
    )
    await waitFor(() =>
      expect(
        screen.getByRole<HTMLTextAreaElement>("textbox", { name: "Message" })
          .value
      ).toBe("find jobs")
    )
    first.unmount()
    render(
      <TooltipProvider>
        <Harness startup={startup} />
      </TooltipProvider>
    )

    expect(
      screen.getByRole<HTMLTextAreaElement>("textbox", { name: "Message" })
        .value
    ).toBe("")
  })
})

const MANY: Mentionables = (() => {
  const documents = Array.from(
    { length: 70 },
    (_, n) =>
      ({
        id: n + 3,
        title: `Report ${n}`,
        status: "ready",
        folder_id: 1,
      }) as WorkspaceDocument
  )
  return {
    documents,
    index: indexSources(FOLDERS.slice(0, 1), documents),
    artifacts: [],
  }
})()

function rowNames(list: HTMLElement) {
  return within(list)
    .getAllByRole("option")
    .map((row) => row.textContent)
}

describe("naming a source with @", () => {
  function box() {
    return screen.getByRole<HTMLTextAreaElement>("textbox", { name: "Message" })
  }

  async function openList(user: ReturnType<typeof userEvent.setup>) {
    await user.type(box(), "compare @")
    return screen.findByRole("listbox", { name: "Sources and artifacts" })
  }

  function renderHarness(props: Parameters<typeof Harness>[0]) {
    render(
      <TooltipProvider>
        <Harness threadMode="agentic" {...props} />
      </TooltipProvider>
    )
  }

  it("asks first for Sources or Artifacts, with how many of each", async () => {
    const user = userEvent.setup()
    renderHarness({ mentionables: LIBRARY })

    const list = await openList(user)

    expect(rowNames(list)).toEqual(["Sources3", "Artifacts1"])
    expect(list.querySelectorAll("[role=option] svg").length).toBeGreaterThan(1)
  })

  it("lists a group, one line and an icon each, and goes back", async () => {
    const user = userEvent.setup()
    renderHarness({ mentionables: LIBRARY })
    const list = await openList(user)

    await user.click(within(list).getByRole("option", { name: /^Sources/ }))

    await waitFor(() =>
      expect(rowNames(list)).toEqual([
        "Contracts1 file",
        "Plan Q3.pdfContracts",
        "Memo",
      ])
    )
    expect(list.querySelectorAll("[role=option] svg")).toHaveLength(3)
    expect(document.activeElement).toBe(box())

    await user.click(within(list).getByRole("button", { name: "Back" }))

    await waitFor(() =>
      expect(rowNames(list)).toEqual(["Sources3", "Artifacts1"])
    )
  })

  it("opens a group from the keyboard, and Backspace goes back", async () => {
    const user = userEvent.setup()
    renderHarness({ mentionables: LIBRARY })
    const list = await openList(user)

    await user.keyboard("{ArrowDown}{Enter}")
    await waitFor(() => expect(rowNames(list)).toEqual(["Board deckSlides"]))

    await user.keyboard("{Backspace}")
    await waitFor(() =>
      expect(rowNames(list)).toEqual(["Sources3", "Artifacts1"])
    )
    expect(box().value).toBe("compare @")
  })

  it("searches both groups as soon as a name is typed", async () => {
    const user = userEvent.setup()
    renderHarness({
      mentionables: {
        ...LIBRARY,
        artifacts: [{ ...LIBRARY.artifacts[0], title: "Plan deck" }],
      },
    })

    await user.type(box(), "@pla")

    const list = await screen.findByRole("listbox")
    await waitFor(() =>
      expect(rowNames(list)).toEqual([
        "Plan Q3.pdfContracts",
        "Plan deckSlides",
      ])
    )
    expect(within(list).getByText("Sources")).toBeTruthy()
    expect(within(list).getByText("Artifacts")).toBeTruthy()
  })

  it("searches both groups when a name is typed inside one", async () => {
    const user = userEvent.setup()
    renderHarness({ mentionables: LIBRARY })
    const list = await openList(user)
    await user.click(within(list).getByRole("option", { name: /^Artifacts/ }))
    await waitFor(() => expect(rowNames(list)).toEqual(["Board deckSlides"]))

    await user.type(box(), "mem")

    await waitFor(() => expect(rowNames(list)).toEqual(["Memo"]))
  })

  it("puts the name in the box and sends its id with the message", async () => {
    const user = userEvent.setup()
    const onRun = vi.fn<(runConfig: RunConfig) => void>()
    renderHarness({ mentionables: LIBRARY, onRun })
    const list = await openList(user)
    await user.click(within(list).getByRole("option", { name: /^Sources/ }))

    await user.click(
      await within(list).findByRole("option", { name: /Plan Q3/ })
    )
    await waitFor(() => expect(box().value).toBe("compare @Plan Q3.pdf "))
    await user.click(screen.getByRole("button", { name: "Send message" }))

    await waitFor(() => expect(onRun).toHaveBeenCalled())
    expect(
      namedSources(picksOf(onRun.mock.calls[0][0]), "compare @Plan Q3.pdf")
    ).toEqual({ document_ids: [3], folder_ids: [] })
  })

  describe("with more than fit", () => {
    async function openSources(user: ReturnType<typeof userEvent.setup>) {
      const list = await openList(user)
      await user.click(within(list).getByRole("option", { name: /^Sources/ }))
      await within(list).findByRole("option", { name: "Report 0" })
      return list
    }

    function scrolled(list: HTMLElement, scrollTop: number) {
      Object.defineProperties(list, {
        scrollHeight: { configurable: true, value: 1000 },
        clientHeight: { configurable: true, value: 256 },
        scrollTop: { configurable: true, writable: true, value: scrollTop },
      })
      fireEvent.scroll(list)
    }

    it("shows the first rows, and more only when scrolled near the end", async () => {
      const user = userEvent.setup()
      renderHarness({ mentionables: MANY })
      const list = await openSources(user)
      expect(within(list).getAllByRole("option")).toHaveLength(30)

      scrolled(list, 100)
      expect(within(list).getAllByRole("option")).toHaveLength(30)

      scrolled(list, 700)
      await waitFor(() =>
        expect(within(list).getAllByRole("option")).toHaveLength(60)
      )
    })

    it("loads more as the arrow keys near the end, keeping the highlight", async () => {
      const user = userEvent.setup()
      renderHarness({ mentionables: MANY })
      const list = await openSources(user)

      await user.keyboard("{ArrowDown>26/}")

      await waitFor(() =>
        expect(within(list).getAllByRole("option")).toHaveLength(60)
      )
      expect(list.querySelector("[data-highlighted]")?.textContent).toBe(
        "Report 26"
      )
    })

    it("wraps up to the last row loaded, never to one not loaded", async () => {
      const scroll = vi.fn()
      Element.prototype.scrollIntoView = scroll
      const user = userEvent.setup()
      renderHarness({ mentionables: MANY })
      const list = await openSources(user)

      await user.keyboard("{ArrowUp}")

      await waitFor(() =>
        expect(list.querySelector("[data-highlighted]")?.textContent).toBe(
          "Report 29"
        )
      )
      expect(within(list).getAllByRole("option")).toHaveLength(30)
      expect(scroll).toHaveBeenCalled()
    })

    it("loads search results as it scrolls too", async () => {
      const user = userEvent.setup()
      renderHarness({ mentionables: MANY })

      await user.type(box(), "@report")
      const list = await screen.findByRole("listbox")
      await waitFor(() =>
        expect(within(list).getAllByRole("option")).toHaveLength(30)
      )

      scrolled(list, 700)
      await waitFor(() =>
        expect(within(list).getAllByRole("option")).toHaveLength(60)
      )
    })
  })

  it("says so when a group is empty", async () => {
    const user = userEvent.setup()
    renderHarness({
      mentionables: {
        documents: [],
        index: indexSources([], []),
        artifacts: [],
      },
    })
    const list = await openList(user)

    await user.click(within(list).getByRole("option", { name: /^Artifacts/ }))

    await screen.findByText("No artifacts yet.")
  })

  it("says so when nothing matches", async () => {
    const user = userEvent.setup()
    renderHarness({ mentionables: LIBRARY })

    await user.type(box(), "@zzz")

    await screen.findByText("Nothing matches")
  })

  it("shows no list in a Basic chat", async () => {
    const user = userEvent.setup()
    renderHarness({ threadMode: "basic", mentionables: LIBRARY })

    await user.type(box(), "@")

    expect(screen.queryByRole("listbox")).toBeNull()
  })
})

describe("chat composer", () => {
  it("stops a question at its share of the window and says so", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Response.json([]))
    )
    const user = userEvent.setup()
    render(<Harness />)

    const input = screen.getByRole<HTMLTextAreaElement>("textbox", {
      name: "Message",
    })
    expect(screen.queryByRole("status")).toBeNull()
    await user.click(input)
    await user.paste("x".repeat(QUESTION_MAX_CHARS + 1))

    expect(input.value).toHaveLength(QUESTION_MAX_CHARS)
    expect(screen.getByRole("status").textContent).toContain("4,096")
  })

  it("turns thinking off for a local model and remembers it", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Response.json([]))
    )
    const user = userEvent.setup()
    const first = render(
      <TooltipProvider>
        <Harness />
      </TooltipProvider>
    )

    const toggle = await openThinking(user)
    expect(toggle.getAttribute("aria-checked")).toBe("true")
    expect(readThinkingOn()).toBe(true)
    await user.click(toggle)

    expect(toggle.getAttribute("aria-checked")).toBe("false")
    expect(readThinkingOn()).toBe(false)

    first.unmount()
    render(
      <TooltipProvider>
        <Harness />
      </TooltipProvider>
    )
    expect((await openThinking(user)).getAttribute("aria-checked")).toBe(
      "false"
    )
  })

  it("sends what the switch shows when the choice cannot be stored", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Response.json([]))
    )
    const setItem = vi
      .spyOn(Storage.prototype, "setItem")
      .mockImplementation(() => {
        throw new DOMException("full", "QuotaExceededError")
      })
    const user = userEvent.setup()
    render(
      <TooltipProvider>
        <Harness />
      </TooltipProvider>
    )

    const toggle = await openThinking(user)
    await user.click(toggle)

    expect(toggle.getAttribute("aria-checked")).toBe("false")
    expect(readThinkingOn()).toBe(false)

    setItem.mockRestore()
    await user.click(toggle)
    expect(readThinkingOn()).toBe(true)
  })

  it("holds the thinking switch on for a model that cannot be told to stop", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Response.json([]))
    )
    const user = userEvent.setup()
    render(
      <TooltipProvider>
        <Harness
          model={{ ...MODEL, provider: "openai_compatible", connection_id: 3 }}
        />
      </TooltipProvider>
    )

    const toggle = await openThinking(user)
    expect(toggle.getAttribute("aria-disabled")).toBe("true")
    expect(toggle.getAttribute("aria-checked")).toBe("true")
    await user.hover(toggle)
    await waitFor(() =>
      expect(
        screen.getAllByText("Only a local model can answer without thinking")
      ).toHaveLength(2)
    )
    await user.click(toggle)

    expect(readThinkingOn()).toBe(true)
  })

  it("uploads sources picked from the add menu", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Response.json([]))
    )
    const opened: HTMLInputElement[] = []
    vi.spyOn(HTMLInputElement.prototype, "click").mockImplementation(function (
      this: HTMLInputElement
    ) {
      opened.push(this)
    })
    const onUploadSources = vi.fn()
    const user = userEvent.setup()
    render(
      <TooltipProvider>
        <Harness onUploadSources={onUploadSources} />
      </TooltipProvider>
    )

    await user.click(
      screen.getByRole("button", { name: "Add images, sources, and more" })
    )
    await user.click(
      await screen.findByRole("menuitem", { name: /^Upload sources/ })
    )

    expect(opened).toHaveLength(1)
    const file = new File(["notes"], "notes.md", { type: "text/markdown" })
    fireEvent.change(opened[0]!, { target: { files: [file] } })
    expect(onUploadSources).toHaveBeenCalledWith([file])
  })

  it("switches an Agentic chat's plugins from the add menu, for every chat", async () => {
    const calls: { method: string; path: string; body: unknown }[] = []
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = new URL(String(input), "http://api.test")
        const method = (init?.method ?? "GET").toUpperCase()
        const body = init?.body ? JSON.parse(String(init.body)) : null
        if (method !== "GET") calls.push({ method, path: url.pathname, body })
        if (url.pathname === "/plugins/third-party") {
          return Response.json({ allowed: false })
        }
        if (url.pathname === "/plugins") {
          return Response.json([
            plugin({}),
            plugin({ id: "wiki", name: "Wiki", source: "registry" }),
            plugin({ id: "gone", name: "Gone", disconnected: true }),
          ])
        }
        if (url.pathname === "/plugins/notes") {
          return Response.json(plugin({ ...body }))
        }
        return Response.json([])
      })
    )
    const onOpenPlugins = vi.fn()
    const user = userEvent.setup()
    render(
      <TooltipProvider>
        <Harness threadMode="agentic" onOpenPlugins={onOpenPlugins} />
      </TooltipProvider>
    )

    await user.click(
      screen.getByRole("button", { name: "Add images, sources, and more" })
    )
    // By keyboard: jsdom has no pointer path, so a pointer would leave the submenu.
    ;(await screen.findByRole("menuitem", { name: "Plugins" })).focus()
    await user.keyboard("{ArrowRight}")
    const notes = await screen.findByRole("menuitemcheckbox", { name: "Notes" })

    expect(screen.getByText("Applies to all Agentic chats")).toBeTruthy()
    expect(notes.getAttribute("aria-checked")).toBe("true")
    const wiki = screen.getByRole("menuitemcheckbox", { name: /^Wiki/ })
    expect(wiki.getAttribute("aria-disabled")).toBe("true")
    expect(screen.queryByRole("menuitemcheckbox", { name: /Gone/ })).toBeNull()
    notes.focus()
    await user.keyboard("{Enter}")
    await waitFor(() =>
      expect(calls).toEqual([
        { method: "PUT", path: "/plugins/notes", body: { enabled: false } },
      ])
    )
    screen.getByRole("menuitem", { name: "Manage plugins" }).focus()
    await user.keyboard("{Enter}")
    expect(onOpenPlugins).toHaveBeenCalledOnce()
  })

  it("opens Settings › Plugins on Browse or Add custom plugin from the add menu", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Response.json([]))
    )
    const onOpenPlugins = vi.fn()
    const user = userEvent.setup()
    render(
      <TooltipProvider>
        <Harness threadMode="agentic" onOpenPlugins={onOpenPlugins} />
      </TooltipProvider>
    )
    const add = async () => {
      await user.click(
        screen.getByRole("button", { name: "Add images, sources, and more" })
      )
      ;(await screen.findByRole("menuitem", { name: "Plugins" })).focus()
      await user.keyboard("{ArrowRight}")
      ;(await screen.findByRole("menuitem", { name: "Add plugin" })).focus()
      await user.keyboard("{ArrowRight}")
    }

    await add()
    ;(await screen.findByRole("menuitem", { name: "Browse plugins" })).focus()
    await user.keyboard("{Enter}")
    await add()
    ;(
      await screen.findByRole("menuitem", { name: "Add custom plugin" })
    ).focus()
    await user.keyboard("{Enter}")

    expect(onOpenPlugins.mock.calls).toEqual([["browse"], ["add"]])
  })

  it("holds Plugins in a Basic chat, saying they work in Agentic chats", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Response.json([]))
    )
    const user = userEvent.setup()
    render(
      <TooltipProvider>
        <Harness threadMode="basic" onOpenPlugins={() => undefined} />
      </TooltipProvider>
    )

    await user.click(
      screen.getByRole("button", { name: "Add images, sources, and more" })
    )
    const plugins = await screen.findByRole("menuitem", { name: /^Plugins/ })

    expect(plugins.getAttribute("aria-disabled")).toBe("true")
    expect(plugins.textContent).toContain("Plugins work in Agentic chats")
  })
})
