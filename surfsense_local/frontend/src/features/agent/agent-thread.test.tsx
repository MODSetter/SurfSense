import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { DashboardPage } from "@/features/dashboard/dashboard-page"
import type { ModelSelection } from "@/features/models/selection/api"
import { render } from "@/test-utils"

const workspace = {
  id: 1,
  name: "My Workspace",
  created_at: "2026-10-01T00:00:00Z",
  updated_at: "2026-10-01T00:00:00Z",
}
const thread = {
  ...workspace,
  id: 10,
  workspace_id: 1,
  title: "Contracts",
  uses_agent: true,
}
const selection: ModelSelection = {
  model_type: "text_gen",
  provider: "openai_compatible",
  connection_id: 1,
  name: "remote-model",
  updated_at: "2026-10-01T00:00:00Z",
  reads_images: false,
}

const ACCEPTED = {
  type: "accepted",
  user_message_id: "msg_u1",
  assistant_message_id: "msg_u1:reply",
  user_created_at: "2026-10-01T00:00:00Z",
}

function step(status: string, extra: Record<string, unknown> = {}) {
  return {
    type: "agent-step",
    id: "prt_1",
    tool: "bash",
    status,
    title: null,
    input: { command: "echo hi", description: "Print" },
    ...extra,
  }
}

function asked(id: string, command = "echo hi") {
  return {
    type: "permission-request",
    id,
    permission: "bash",
    patterns: [command],
    command,
  }
}

const sse = (frames: unknown[]) =>
  frames.map((frame) => `data: ${JSON.stringify(frame)}\n\n`).join("")

/** A stream that sends `first`, waits for `gate`, then sends `rest` and ends. */
function pausedStream(first: unknown[], gate: Promise<void>, rest: unknown[]) {
  const encoder = new TextEncoder()
  return new ReadableStream<Uint8Array>({
    async start(controller) {
      controller.enqueue(encoder.encode(sse(first)))
      await gate
      controller.enqueue(encoder.encode(sse(rest) + "data: [DONE]\n\n"))
      controller.close()
    },
  })
}

type Backend = {
  answers: { requestId: string; reply: string }[]
}

// The version a completed render made, as the API reads it back.
const PROPOSAL = {
  id: 40,
  document_id: 140,
  format: "summary",
  generation: 1,
  title: "Client proposal",
  status: "ready",
  error_message: null,
  content: "The proposal body.",
  files: [],
  created_at: "2026-10-04T00:00:00Z",
  updated_at: "2026-10-04T00:00:00Z",
  version: { root_id: 40, number: 1, parent_id: null },
  spec_kind: "python",
}

/**
 * An agent thread whose next turn streams `first`, then waits for every
 * approval in `waitFor` to be answered before it streams `rest`. Listing the
 * thread returns `stored`, or `storedAfter` once a turn has been sent.
 */
function backend({
  first = [] as unknown[],
  rest = [] as unknown[],
  waitFor: waiting = [] as string[],
  stored = [] as unknown[],
  storedAfter = null as unknown[] | null,
} = {}): Backend {
  const state: Backend = { answers: [] }
  let sent = false
  let release: () => void = () => {}
  const gate = new Promise<void>((resolve) => {
    release = resolve
  })
  if (waiting.length === 0) release()
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input)
      if (path === "/llm/providers") {
        return Response.json([
          { name: "llamacpp", healthy: true, can_download: true },
        ])
      }
      if (path.startsWith("/workspaces/1/documents")) return Response.json([])
      if (path === "/workspaces/1/chat/threads") return Response.json([thread])
      if (path === "/artifacts/40") return Response.json(PROPOSAL)
      const answer = path.match(/^\/chat\/threads\/10\/permissions\/(.+)$/)
      if (answer && init?.method === "POST") {
        const { reply } = JSON.parse(String(init.body)) as { reply: string }
        state.answers.push({ requestId: answer[1], reply })
        if (
          waiting.every((id) => state.answers.some((a) => a.requestId === id))
        ) {
          release()
        }
        return new Response(null, { status: 204 })
      }
      if (path === "/chat/threads/10/messages" && init?.method === "POST") {
        sent = true
        return new Response(pausedStream(first, gate, rest), {
          headers: { "Content-Type": "text/event-stream" },
        })
      }
      if (path === "/chat/threads/10/messages") {
        return Response.json(
          sent && storedAfter !== null ? storedAfter : stored
        )
      }
      return Response.json({ detail: "not found" }, { status: 404 })
    })
  )
  return state
}

function renderAgentThread() {
  localStorage.setItem("surfsense:last-thread:1:v1", "10")
  render(
    <DashboardPage
      initialProviderAvailable={true}
      selection={selection}
      initialWorkspaces={[workspace]}
      onModelSelected={vi.fn()}
    />
  )
}

async function ask(text: string) {
  const user = userEvent.setup()
  const composer = await screen.findByRole("textbox", { name: "Message" })
  await user.type(composer, `${text}{Enter}`)
  return user
}

beforeEach(() => {
  localStorage.clear()
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    value: vi.fn().mockReturnValue({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  })
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  )
  for (const method of ["scrollTo", "scrollIntoView"]) {
    Object.defineProperty(HTMLElement.prototype, method, {
      configurable: true,
      value: vi.fn(),
    })
  }
  vi.stubGlobal("surfsense", { apiUrl: "", platform: "darwin" })
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe("an agent thread", () => {
  it("shows each step the agent takes as it takes it", async () => {
    backend({
      first: [ACCEPTED, step("running")],
      rest: [
        step("completed", { output: "hi\n" }),
        { type: "delta", text: "It printed hi." },
        {
          type: "completed",
          assistant_completed_at: null,
          text: "It printed hi.",
        },
      ],
    })
    renderAgentThread()
    await ask("Run it")

    expect(await screen.findByText("Ran")).toBeTruthy()
    expect(await screen.findByText("echo hi")).toBeTruthy()
    expect(await screen.findByText("It printed hi.")).toBeTruthy()
  })

  it("runs a shell command only once the user allows it", async () => {
    const state = backend({
      first: [ACCEPTED, step("running"), asked("per_1")],
      rest: [
        { type: "permission-replied", id: "per_1", reply: "once" },
        step("completed", { output: "hi\n" }),
        { type: "completed", assistant_completed_at: null, text: "Done." },
      ],
      waitFor: ["per_1"],
    })
    renderAgentThread()
    const user = await ask("Run it")

    const dialog = await screen.findByRole("alertdialog", {
      name: "Run a shell command?",
    })
    expect(within(dialog).getByText("echo hi")).toBeTruthy()
    await user.click(within(dialog).getByRole("button", { name: "Allow once" }))

    await waitFor(() => {
      expect(state.answers).toEqual([{ requestId: "per_1", reply: "once" }])
    })
    await waitFor(() => {
      expect(screen.queryByRole("alertdialog")).toBeNull()
    })
  })

  it("denies the command when the user says no or closes the prompt", async () => {
    const state = backend({
      first: [ACCEPTED, step("running"), asked("per_1")],
      rest: [
        { type: "permission-replied", id: "per_1", reply: "reject" },
        step("error", { error: "The user rejected permission" }),
        { type: "completed", assistant_completed_at: null, text: "" },
      ],
      waitFor: ["per_1"],
    })
    renderAgentThread()
    const user = await ask("Run it")

    await screen.findByRole("alertdialog", { name: "Run a shell command?" })
    await user.keyboard("{Escape}")

    await waitFor(() => {
      expect(state.answers).toEqual([{ requestId: "per_1", reply: "reject" }])
    })
  })

  it("says that denying one request denies the others waiting", async () => {
    backend({
      first: [ACCEPTED, asked("per_1", "echo one"), asked("per_2", "echo two")],
      waitFor: ["per_1", "per_2"],
    })
    renderAgentThread()
    await ask("Run both")

    const dialog = await screen.findByRole("alertdialog", {
      name: "Run a shell command?",
    })
    expect(
      within(dialog).getByText(
        "Denying also denies 1 other request waiting in this chat."
      )
    ).toBeTruthy()
  })

  it("shows the steps a stored reply took", async () => {
    backend({
      stored: [
        {
          id: "msg_u1",
          role: "user",
          content: { text: "List the sources" },
          created_at: "2026-10-01T00:00:00Z",
          completed_at: "2026-10-01T00:00:00Z",
        },
        {
          id: "msg_u1:reply",
          role: "assistant",
          content: {
            text: "There are two.",
            steps: [
              {
                id: "prt_9",
                tool: "bash",
                status: "completed",
                title: "ls sources",
                input: { command: "ls sources" },
                output: "a.md\nb.md",
              },
            ],
          },
          created_at: "2026-10-01T00:00:01Z",
          completed_at: "2026-10-01T00:00:02Z",
        },
      ],
    })
    renderAgentThread()

    expect(await screen.findByText("ls sources")).toBeTruthy()
    expect(await screen.findByText("There are two.")).toBeTruthy()
  })

  it("names SurfSense's own tools in words, not by their tool names", async () => {
    backend({
      stored: [
        {
          id: "msg_u1",
          role: "user",
          content: { text: "Make slides about the launch" },
          created_at: "2026-10-01T00:00:00Z",
          completed_at: "2026-10-01T00:00:00Z",
        },
        {
          id: "msg_u1:reply",
          role: "assistant",
          content: {
            text: "Studio is making them.",
            steps: [
              {
                id: "prt_1",
                tool: "surfsense_search_sources",
                status: "completed",
                title: "",
                input: { query: "launch plan" },
                output: "",
              },
              {
                id: "prt_2",
                tool: "surfsense_create_artifact",
                status: "completed",
                title: "",
                input: { format: "pptx", source_ids: [12] },
                output: "",
              },
            ],
          },
          created_at: "2026-10-01T00:00:01Z",
          completed_at: "2026-10-01T00:00:02Z",
        },
      ],
    })
    renderAgentThread()

    expect(await screen.findByText("launch plan")).toBeTruthy()
    expect(await screen.findByText("Started Slides in Studio")).toBeTruthy()
    expect(screen.queryByText("surfsense_create_artifact")).toBeNull()
  })

  it("keeps one copy of a reply once opencode has stored it", async () => {
    const reply = {
      id: "msg_u1:reply",
      role: "assistant",
      content: { text: "Stored once.", steps: [] },
      created_at: "2026-10-01T00:00:01Z",
      completed_at: "2026-10-01T00:00:02Z",
    }
    backend({
      first: [ACCEPTED],
      rest: [
        { type: "delta", text: "Stored once." },
        {
          type: "completed",
          assistant_completed_at: "2026-10-01T00:00:02Z",
          text: "Stored once.",
        },
      ],
      storedAfter: [
        {
          id: "msg_u1",
          role: "user",
          content: { text: "Say it" },
          created_at: "2026-10-01T00:00:00Z",
          completed_at: "2026-10-01T00:00:00Z",
        },
        reply,
      ],
    })
    renderAgentThread()
    await ask("Say it")

    await screen.findByText("Stored once.")
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(screen.getAllByText("Stored once.")).toHaveLength(1)
  })

  it("opens the document a render made in Studio from its step", async () => {
    const renderStep = {
      id: "prt_5",
      tool: "surfsense_render_document",
      title: null,
      input: { title: "Client proposal", format: "docx", script: "..." },
    }
    backend({
      first: [
        ACCEPTED,
        { type: "agent-step", status: "running", ...renderStep },
      ],
      rest: [
        {
          type: "agent-step",
          status: "completed",
          ...renderStep,
          output: "Rendered artifact 40, version 1.",
          artifact: { id: 40, title: "Client proposal", version: 1 },
        },
        { type: "completed", assistant_completed_at: null, text: "Done." },
      ],
    })
    renderAgentThread()
    const user = await ask("Draft the proposal")

    await user.click(
      await screen.findByRole("button", { name: "Created Client proposal v1" })
    )
    expect(await screen.findByText("The proposal body.")).toBeTruthy()
    expect(screen.getByRole("complementary", { name: "Artifact" })).toBeTruthy()
  })

  it("says which version a stored reply’s render updated", async () => {
    backend({
      stored: [
        {
          id: "msg_u1",
          role: "user",
          content: { text: "Make it shorter" },
          created_at: "2026-10-01T00:00:00Z",
          completed_at: "2026-10-01T00:00:00Z",
        },
        {
          id: "msg_u1:reply",
          role: "assistant",
          content: {
            text: "Shorter now.",
            steps: [
              {
                id: "prt_6",
                tool: "surfsense_render_document",
                status: "completed",
                title: "",
                input: { title: "Client proposal", format: "docx" },
                output: "Rendered artifact 41, version 2.",
                artifact: { id: 41, title: "Client proposal", version: 2 },
              },
            ],
          },
          created_at: "2026-10-01T00:00:01Z",
          completed_at: "2026-10-01T00:00:02Z",
        },
      ],
    })
    renderAgentThread()

    expect(
      await screen.findByRole("button", {
        name: "Updated Client proposal to v2",
      })
    ).toBeTruthy()
  })

  it("shows why a render failed instead of a document to open", async () => {
    const failure =
      "The script failed: AttributeError: 'Document' object has no attribute 'add_tabel'"
    backend({
      stored: [
        {
          id: "msg_u1",
          role: "user",
          content: { text: "Draft the proposal" },
          created_at: "2026-10-01T00:00:00Z",
          completed_at: "2026-10-01T00:00:00Z",
        },
        {
          id: "msg_u1:reply",
          role: "assistant",
          content: {
            text: "Fixing the script.",
            steps: [
              {
                id: "prt_7",
                tool: "surfsense_render_document",
                // The tool hands the error back to the model as its result.
                status: "completed",
                title: "",
                input: { title: "Client proposal", format: "docx" },
                output: failure,
                artifact: null,
              },
            ],
          },
          created_at: "2026-10-01T00:00:01Z",
          completed_at: "2026-10-01T00:00:02Z",
        },
      ],
    })
    renderAgentThread()
    const user = userEvent.setup()

    await user.click(
      await screen.findByText("Ran the document script for", { exact: false })
    )
    expect(screen.getByText(failure)).toBeTruthy()
    expect(screen.queryByRole("button", { name: /Created|Updated/ })).toBeNull()
  })
})
