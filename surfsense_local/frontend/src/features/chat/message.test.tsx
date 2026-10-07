import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { act, cleanup, screen } from "@testing-library/react"
import { useCallback, useSyncExternalStore, type ReactNode } from "react"
import {
  AssistantRuntimeProvider,
  ThreadPrimitive,
  useExternalStoreRuntime,
  type ThreadMessageLike,
} from "@assistant-ui/react"

import {
  OfficeOfferContext,
  type OfficeOffer,
} from "@/features/office-support/office-offer"
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

beforeEach(() => {
  seen.markdown = []
  seen.blockParses = 0
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
