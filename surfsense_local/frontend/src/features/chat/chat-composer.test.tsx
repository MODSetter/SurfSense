import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { AssistantRuntimeProvider, useLocalRuntime } from "@assistant-ui/react"

import { TooltipProvider } from "@/components/ui/tooltip"
import type { ModelSelection } from "@/features/models/selection/api"
import type { Plugin } from "@/features/plugins/api"
import { render } from "@/test-utils"

import { ChatComposer } from "./chat-composer"
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

function Harness({
  model = MODEL,
  onUploadSources,
  threadMode,
  onOpenPlugins,
}: {
  model?: ModelSelection
  onUploadSources?: (files: File[]) => void
  threadMode?: "agentic" | "basic"
  onOpenPlugins?: () => void
}) {
  const runtime = useLocalRuntime({ run: async () => ({ content: [] }) })
  return (
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
      />
    </AssistantRuntimeProvider>
  )
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
