import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { AssistantRuntimeProvider, useLocalRuntime } from "@assistant-ui/react"

import type { ChatMode, ChatModes } from "@/features/models/capability/api"
import type { ModelSelection } from "@/features/models/selection/api"
import { render } from "@/test-utils"

import { ChatComposer } from "../chat-composer"
import { useNewChatMode } from "./new-chat-mode"
import { NewChatModeProvider } from "./new-chat-mode-provider"

const PASSED: ChatModes = {
  agentic_allowed: true,
  blocked: null,
  default_mode: "agentic",
  reason: { code: "measured_pass", values: { passed: 8, counted: 8 } },
  remembered_mode: null,
}
const UNTESTED: ChatModes = {
  ...PASSED,
  default_mode: "basic",
  reason: { code: "untested", values: {} },
}

function model(name: string, modes: ChatModes): ModelSelection {
  return {
    model_type: "text_gen",
    provider: "openai_compatible",
    connection_id: 1,
    name,
    updated_at: "2026-10-07T00:00:00Z",
    capability: {
      level: "not_measured",
      label_key: "not_measured",
      reason: { code: "no_row", values: {} },
      note: null,
      measured: null,
      modes,
    },
  }
}

const KIMI = model("moonshotai/kimi-k3", PASSED)
const SONNET_99 = model("anthropic/claude-sonnet-99", UNTESTED)

/** What the send path would open the next chat in, beside the composer. */
function NextChat({ model }: { model: ModelSelection }) {
  return <output aria-label="Next chat">{useNewChatMode(model)}</output>
}

function Composer({
  model,
  threadMode = null,
  onNewChat,
}: {
  model: ModelSelection
  threadMode?: ChatMode | null
  onNewChat?: () => void
}) {
  const runtime = useLocalRuntime({ run: async () => ({ content: [] }) })
  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <ChatComposer
        placement={threadMode === null ? "center" : "bottom"}
        model={model}
        sourceCount={0}
        isRunning={false}
        providerAvailable
        onModelSetup={() => undefined}
        onModelSelected={() => undefined}
        readsImages={false}
        threadMode={threadMode}
        onNewChat={onNewChat}
      />
      <NextChat model={model} />
    </AssistantRuntimeProvider>
  )
}

function renderComposer(props: Parameters<typeof Composer>[0]) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => Response.json([]))
  )
  const result = render(
    <NewChatModeProvider>
      <Composer {...props} />
    </NewChatModeProvider>
  )
  return {
    ...result,
    rerenderWith: (next: Parameters<typeof Composer>[0]) =>
      result.rerender(
        <NewChatModeProvider>
          <Composer {...next} />
        </NewChatModeProvider>
      ),
  }
}

function trigger() {
  return screen.getByRole("button", { name: /^Chat mode / })
}

function nextChat() {
  return screen.getByRole("status", { name: "Next chat" }).textContent
}

/** What the composer says under itself, apart from the probe. */
function composerNote() {
  return screen
    .getAllByRole("status")
    .filter((region) => region.getAttribute("aria-label") !== "Next chat")
    .map((region) => region.textContent)
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("the composer's mode switch", () => {
  it("starts a model that passed in Agentic, and says nothing more", () => {
    renderComposer({ model: KIMI })

    expect(trigger().textContent).toContain("Agentic")
    expect(nextChat()).toBe("agentic")
    expect(composerNote()).toEqual([])
  })

  it("starts an untested model in Basic, and warns once Agentic is picked", async () => {
    const user = userEvent.setup()
    renderComposer({ model: SONNET_99 })

    expect(trigger().textContent).toContain("Basic (Q&A)")
    expect(nextChat()).toBe("basic")
    await user.click(trigger())
    const agentic = await screen.findByRole("menuitemradio", {
      name: /^Agentic/,
    })
    expect(agentic.textContent).toContain("Not tested with this model yet")
    await user.click(agentic)

    expect(trigger().textContent).toContain("Agentic")
    expect(nextChat()).toBe("agentic")
    expect(composerNote()).toEqual([
      "Not tested with this model yet, so it may stop early or make mistakes.",
    ])
  })

  it("offers a low scorer Agentic with its score", async () => {
    const user = userEvent.setup()
    renderComposer({
      model: model("google/gemma-4-31b-it", {
        ...UNTESTED,
        reason: { code: "measured_below", values: { passed: 2, counted: 8 } },
      }),
    })

    await user.click(trigger())
    const agentic = await screen.findByRole("menuitemradio", {
      name: /^Agentic/,
    })

    expect(agentic.getAttribute("aria-disabled")).not.toBe("true")
    expect(agentic.textContent).toContain("Passed 2 of 8 Agentic tests")
  })

  it("notes that a local copy passed only on its full-size version", async () => {
    const user = userEvent.setup()
    renderComposer({
      model: model("qwen3.8:27b", {
        ...UNTESTED,
        reason: { code: "local_copy", values: { host: "openrouter.ai" } },
      }),
    })

    await user.click(trigger())
    await user.click(
      await screen.findByRole("menuitemradio", { name: /^Agentic/ })
    )

    expect(composerNote()).toEqual([
      "Passed on its full-size version. A local copy may do worse.",
    ])
  })

  it("holds Agentic out with the reason when a gate blocks it", async () => {
    const user = userEvent.setup()
    renderComposer({
      model: model("gpt-3.5-turbo", {
        ...PASSED,
        agentic_allowed: false,
        blocked: "tool_calls_unsupported",
        default_mode: "basic",
      }),
    })

    await user.click(trigger())
    const agentic = await screen.findByRole("menuitemradio", {
      name: /^Agentic/,
    })
    expect(agentic.getAttribute("aria-disabled")).toBe("true")
    expect(agentic.textContent).toContain("This model can’t use tools.")
    await user.click(agentic)

    expect(nextChat()).toBe("basic")
  })

  it("follows the model: each takes its own pick, else its default", async () => {
    const user = userEvent.setup()
    const { rerenderWith } = renderComposer({ model: KIMI })

    await user.click(trigger())
    await user.click(
      await screen.findByRole("menuitemradio", { name: /^Basic \(Q&A\)/ })
    )
    expect(nextChat()).toBe("basic")

    rerenderWith({ model: SONNET_99 })
    expect(nextChat()).toBe("basic")
    rerenderWith({ model: model("z-ai/glm-5.3", PASSED) })
    expect(nextChat()).toBe("agentic")
    rerenderWith({ model: KIMI })
    expect(nextChat()).toBe("basic")
  })

  it("is picked from the keyboard", async () => {
    const user = userEvent.setup()
    renderComposer({ model: SONNET_99 })

    trigger().focus()
    await user.keyboard("{Enter}")
    const menu = await screen.findByRole("menu")
    expect(
      within(menu)
        .getByRole("menuitemradio", { name: /^Basic \(Q&A\)/ })
        .getAttribute("aria-checked")
    ).toBe("true")
    await user.keyboard("{ArrowDown}")
    await user.keyboard("{Enter}")

    expect(nextChat()).toBe("agentic")
  })

  it("shows an open chat's mode and offers the other only as a new chat", async () => {
    const user = userEvent.setup()
    const onNewChat = vi.fn()
    renderComposer({ model: KIMI, threadMode: "agentic", onNewChat })

    expect(trigger().textContent).toContain("Agentic")
    await user.click(trigger())
    expect(
      await screen.findByText("This chat runs in Agentic mode")
    ).toBeTruthy()
    expect(screen.queryByRole("menuitemradio")).toBeNull()
    await user.click(
      screen.getByRole("menuitem", {
        name: /^Start a new chat in Basic \(Q&A\) mode/,
      })
    )

    expect(onNewChat).toHaveBeenCalledOnce()
    expect(nextChat()).toBe("basic")
  })

  it("does not offer an open chat's other mode when a gate blocks Agentic", async () => {
    const user = userEvent.setup()
    const onNewChat = vi.fn()
    renderComposer({
      model: model("gpt-3.5-turbo", {
        ...UNTESTED,
        agentic_allowed: false,
        blocked: "agent_not_installed",
      }),
      threadMode: "basic",
      onNewChat,
    })

    await user.click(trigger())
    const offer = await screen.findByRole("menuitem", {
      name: /^Start a new chat in Agentic mode/,
    })
    expect(offer.textContent).toContain(
      "This install doesn’t include the agent."
    )
    await user.click(offer)

    expect(onNewChat).not.toHaveBeenCalled()
  })
})
