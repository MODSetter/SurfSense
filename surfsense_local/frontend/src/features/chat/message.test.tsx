import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { act, cleanup, screen, waitFor } from "@testing-library/react"
import { useCallback, useSyncExternalStore, type ReactNode } from "react"
import {
  AssistantRuntimeProvider,
  ThreadPrimitive,
  useExternalStoreRuntime,
  type ThreadMessageLike,
} from "@assistant-ui/react"

import type { AgentStep, TurnSources } from "@/features/agent/api"
import {
  OfficeOfferContext,
  type OfficeOffer,
} from "@/features/office-support/office-offer"
import { codeHighlighter } from "@/features/studio/viewers/code-highlighter"
import { render } from "@/test-utils"

import { AssistantMessage, UserMessage } from "./message"
import type { Citation } from "./sse"

const seen = vi.hoisted(() => ({
  markdown: [] as Record<string, unknown>[],
  blockParses: 0,
}))

// Records what each reply's markdown is given, and counts every block run
// through the markdown pipeline.
vi.mock("@assistant-ui/react-streamdown", async (original) => {
  const actual = (await original()) as Record<string, unknown>
  const React = await import("react")
  const Real = actual.StreamdownTextPrimitive as React.ComponentType<
    Record<string, unknown>
  >
  const counting = [
    () => () => {
      seen.blockParses += 1
    },
  ]
  return {
    ...actual,
    StreamdownTextPrimitive: (props: Record<string, unknown>) => {
      seen.markdown.push(props)
      return React.createElement(Real, { ...props, rehypePlugins: counting })
    },
  }
})

vi.mock("@/features/studio/viewers/code-highlighter", async (original) => {
  const { codeHighlighter: real } = (await original()) as {
    codeHighlighter: typeof codeHighlighter
  }
  return {
    codeHighlighter: { ...real, highlight: vi.fn(real.highlight) },
  }
})

// The banner itself is office-offer-banner.test.tsx's; here, only where it shows.
vi.mock("@/features/office-support/office-offer-banner", () => ({
  OfficeOfferBanner: () => <p>Office offer</p>,
}))

type Turn = {
  id: string
  role: "user" | "assistant"
  text: string
  custom?: Record<string, unknown>
}

const NONE: Citation[] = []
const noop = () => {}

// The page's state, held outside React the way the run store holds a reply.
type Page = {
  turns: Turn[]
  running: boolean
  citations: Citation[]
  renders: number
}
let page: Page = { turns: [], running: false, citations: NONE, renders: 0 }
const listeners = new Set<() => void>()
const pageStore = {
  subscribe(listener: () => void) {
    listeners.add(listener)
    return () => listeners.delete(listener)
  },
  get: () => page,
}

function update(next: Partial<Page>) {
  page = { ...page, ...next }
  for (const listener of listeners) listener()
}

function push(chunk: string) {
  const last = page.turns[page.turns.length - 1]
  update({
    turns: [...page.turns.slice(0, -1), { ...last, text: last.text + chunk }],
  })
}
const append = (...more: Turn[]) => update({ turns: [...page.turns, ...more] })
const finish = () => update({ running: false })
const cite = (citations: Citation[]) => update({ citations })
const rerenderPage = () => update({ renders: page.renders + 1 })

function renderThread(
  turns: Turn[],
  {
    running = false,
    offer = null,
  }: { running?: boolean; offer?: OfficeOffer | null } = {}
) {
  page = { turns, running, citations: NONE, renders: 0 }
  return render(<Thread offer={offer} />)
}

function Thread({ offer }: { offer: OfficeOffer | null }) {
  const { turns, running, citations } = useSyncExternalStore(
    pageStore.subscribe,
    pageStore.get
  )
  const convertMessage = useCallback(
    (turn: Turn): ThreadMessageLike => ({
      id: turn.id,
      role: turn.role,
      content: [{ type: "text", text: turn.text }],
      metadata: { custom: turn.custom ?? { steps: [] } },
    }),
    []
  )
  const runtime = useExternalStoreRuntime<Turn>({
    messages: turns,
    convertMessage,
    isRunning: running,
    onNew: async () => {},
  })
  // As the dashboard does: a new handler on every render of the page.
  const onCitation = () => {}
  return (
    <OfficeOfferContext.Provider value={offer}>
      <AssistantRuntimeProvider runtime={runtime}>
        <ThreadPrimitive.Root>
          <ThreadPrimitive.Messages>
            {({ message }): ReactNode =>
              message.role === "user" ? (
                <UserMessage />
              ) : (
                <AssistantMessage
                  citations={citations}
                  onCitation={onCitation}
                  onModelSetup={noop}
                  onRetry={noop}
                  onNewChat={noop}
                />
              )
            }
          </ThreadPrimitive.Messages>
        </ThreadPrimitive.Root>
      </AssistantRuntimeProvider>
    </OfficeOfferContext.Provider>
  )
}

function answer(paragraphs: number) {
  return Array.from(
    { length: paragraphs },
    (_, index) => `Paragraph ${index} has **bold** words and a \`span\`.`
  ).join("\n\n")
}

function lastMarkdownProps() {
  return seen.markdown[seen.markdown.length - 1]
}

const highlight = vi.mocked(codeHighlighter.highlight)

beforeEach(() => {
  seen.markdown = []
  seen.blockParses = 0
  highlight.mockClear()
  Element.prototype.scrollTo ??= noop
})

afterEach(cleanup)

describe("a reply's markdown", () => {
  it("keeps its options across tokens, so they never force a reparse", async () => {
    renderThread(
      [
        { id: "u", role: "user", text: "Go on" },
        { id: "a", role: "assistant", text: "Start" },
      ],
      { running: true }
    )
    const first = lastMarkdownProps()

    for (let frame = 0; frame < 5; frame += 1) {
      await act(async () => push(" word"))
    }
    const last = lastMarkdownProps()

    expect(last.security).toBe(first.security)
    expect(last.linkSafety).toBe(first.linkSafety)
    expect(last.preprocess).toBe(first.preprocess)
    expect(last.plugins).toBe(first.plugins)
  })

  it("reads citations afresh when they arrive", async () => {
    renderThread([
      { id: "u", role: "user", text: "Go on" },
      { id: "a", role: "assistant", text: "Revenue rose [citation:7]." },
    ])
    const before = lastMarkdownProps().preprocess

    await act(async () =>
      cite([
        {
          source_id: 7,
          chunk_id: 70,
          document_id: 1,
          start_line: null,
          end_line: null,
        } as Citation,
      ])
    )

    expect(lastMarkdownProps().preprocess).not.toBe(before)
    expect(screen.getByRole("button", { name: /70/ })).toBeTruthy()
  })

  it("parses only the block a token changed, even as the page re-renders around it", async () => {
    const finished = (index: number): Turn[] => [
      { id: `u${index}`, role: "user", text: `Question ${index}` },
      { id: `a${index}`, role: "assistant", text: answer(8) },
    ]
    renderThread(
      [
        ...finished(0),
        ...finished(1),
        ...finished(2),
        { id: "u", role: "user", text: "Go on" },
        { id: "a", role: "assistant", text: answer(8) },
      ],
      { running: true }
    )
    seen.blockParses = 0

    for (let frame = 0; frame < 10; frame += 1) {
      await act(async () => {
        push(" word")
        rerenderPage()
      })
    }

    // 32 blocks on the page; each token touches the live reply's last one.
    expect(seen.blockParses / 10).toBeLessThanOrEqual(2)
  })
})

describe("code in a reply", () => {
  const code = [
    "export function total(items: number[]) {",
    "  let sum = 0",
    "  for (const item of items) sum += item",
    "  return sum",
    "}",
  ].join("\n")

  it("stays plain and current while the reply streams, and is coloured once when it ends", async () => {
    const { container } = renderThread(
      [
        { id: "u", role: "user", text: "Show me" },
        { id: "a", role: "assistant", text: "Here:\n\n```ts\n" },
      ],
      { running: true }
    )
    const body = () =>
      container.querySelector('[data-streamdown="code-block-body"]')
    // One span per line; the parser drops a block's trailing blank lines.
    const shown = () =>
      [...(body()?.querySelectorAll("code > span") ?? [])].map(
        (line) => line.textContent
      )
    const linesOf = (text: string) => text.trimEnd().split("\n")

    for (let at = 0; at < code.length; at += 12) {
      await act(async () => push(code.slice(at, at + 12)))
      expect(shown()).toEqual(linesOf(code.slice(0, at + 12)))
    }
    await act(async () => push("\n```\n\nDone."))
    expect(highlight).not.toHaveBeenCalled()

    await act(async () => finish())

    expect(highlight).toHaveBeenCalled()
    for (const [options] of highlight.mock.calls) {
      expect(options.code).toBe(code)
    }
    await waitFor(() =>
      expect(body()?.querySelector('span[style*="--shiki-dark"]')).toBeTruthy()
    )
    expect(shown()).toEqual(linesOf(code))
  })

  it("does not parse the reply again when it ends", async () => {
    renderThread(
      [
        { id: "u", role: "user", text: "Go on" },
        {
          id: "a",
          role: "assistant",
          text: `${answer(6)}\n\n$$x^2$$\n\n\`\`\`ts\n${code}\n\`\`\``,
        },
      ],
      { running: true }
    )
    await act(async () => {})
    seen.blockParses = 0

    await act(async () => finish())

    expect(seen.blockParses).toBe(0)
  })
})

describe("an agent reply's steps", () => {
  const pages = (id: string, documentId: number): AgentStep => ({
    id,
    tool: "surfsense_source_pages",
    status: "completed",
    title: null,
    input: { document_id: documentId },
    artifact: null,
  })
  const scope = (ids: number[], titles: string[]): TurnSources => ({
    document_ids: ids,
    titles,
  })

  it("names a source by the scope of the question each reply answers", () => {
    renderThread([
      {
        id: "u1",
        role: "user",
        text: "First",
        custom: { scope: scope([1], ["Lease"]) },
      },
      {
        id: "a1",
        role: "assistant",
        text: "One.",
        custom: { steps: [pages("s1", 1)] },
      },
      {
        id: "u2",
        role: "user",
        text: "Second",
        custom: { scope: scope([1], ["Invoice"]) },
      },
      {
        id: "a2",
        role: "assistant",
        text: "Two.",
        custom: { steps: [pages("s2", 1)] },
      },
    ])

    const lines = screen.getAllByRole("listitem").map((li) => li.textContent)
    expect(lines).toEqual([
      "Looked at pages of Lease",
      "Looked at pages of Invoice",
    ])
  })

  it("reads a reply with no steps without an unstable store answer", () => {
    const error = vi.spyOn(console, "error").mockImplementation(noop)

    renderThread([
      { id: "u", role: "user", text: "Hi" },
      { id: "a", role: "assistant", text: "Hello.", custom: {} },
    ])

    expect(screen.getByText("Hello.")).toBeTruthy()
    expect(
      error.mock.calls.filter((call) => String(call[0]).includes("getSnapshot"))
    ).toEqual([])
    error.mockRestore()
  })
})

describe("the Office support offer", () => {
  const made = (id: string, artifactId: number): AgentStep => ({
    id,
    tool: "surfsense_render_document",
    status: "completed",
    title: null,
    input: { title: "Proposal", format: "docx" },
    artifact: { id: artifactId, title: "Proposal", version: 1 },
  })
  const offer: OfficeOffer = {
    isOfficeFile: (artifactId) => artifactId >= 40,
    openOfficeSupport: noop,
  }
  const reply = (id: string, steps: AgentStep[]): Turn => ({
    id,
    role: "assistant",
    text: `Reply ${id}.`,
    custom: { steps },
  })
  const question = (id: string): Turn => ({ id, role: "user", text: "Make" })

  it("shows only under the latest reply that made an Office file, and moves with a newer one", async () => {
    const { container } = renderThread(
      [
        question("u1"),
        reply("a1", [made("s1", 40)]),
        question("u2"),
        reply("a2", [made("s2", 41)]),
        question("u3"),
        reply("a3", [made("s3", 7)]),
      ],
      { offer }
    )
    const offeredUnder = () =>
      [...container.querySelectorAll("p")]
        .filter((p) => p.textContent === "Office offer")
        .map(
          (p) =>
            p.parentElement?.textContent?.match(/Reply (a\d)\./)?.[1] ?? null
        )

    expect(offeredUnder()).toEqual(["a2"])

    await act(async () => append(question("u4"), reply("a4", [made("s4", 42)])))

    expect(offeredUnder()).toEqual(["a4"])
  })

  it("scans the thread once per update, not once per message", async () => {
    const isOfficeFile = vi.fn(() => false)
    const turns = Array.from({ length: 6 }, (_, index) => [
      question(`u${index}`),
      reply(`a${index}`, [
        made(`s${index}a`, 1),
        made(`s${index}b`, 2),
        made(`s${index}c`, 3),
      ]),
    ]).flat()
    renderThread([...turns, question("u"), reply("a", [])], {
      running: true,
      offer: { isOfficeFile, openOfficeSupport: noop },
    })
    isOfficeFile.mockClear()

    await act(async () => push(" More."))

    // 18 steps in the thread: one scan for the new messages, not one a reply.
    expect(isOfficeFile.mock.calls.length).toBeLessThanOrEqual(2 * 18)
  })
})
