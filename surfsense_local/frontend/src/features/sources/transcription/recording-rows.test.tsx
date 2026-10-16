import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { act, cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import {
  fakeSpeechRow,
  NEMOTRON_LANGUAGES,
} from "@/features/models/local/transcription/fake-speech-rows"
import { render } from "@/test-utils"

import type { DocumentTranscription, WorkspaceDocument } from "../api"
import { SourcesPanel } from "../sources-panel"
import { useSources } from "../use-sources"

vi.mock("sonner", () => ({
  toast: { error: vi.fn(), info: vi.fn(), success: vi.fn() },
}))

const LIST =
  "/workspaces/1/documents?document_type=FILE&document_type=NOTE&limit=200&offset=0"

function recording(
  status: WorkspaceDocument["status"],
  transcription: Partial<DocumentTranscription>,
  overrides: Partial<WorkspaceDocument> = {}
): WorkspaceDocument {
  return {
    id: 5,
    title: "meeting.mp3",
    document_type: "FILE",
    mime_type: "audio/mpeg",
    status,
    error_message: null,
    created_at: "2026-10-14T00:00:00Z",
    updated_at: "2026-10-14T00:00:00Z",
    folder_id: null,
    transcription: {
      language: null,
      progress: null,
      awaiting: false,
      ...transcription,
    },
    ...overrides,
  }
}

const BGE_SMALL = {
  active: {
    name: "bge-small-en-v1.5",
    spec: {
      id: "bge-small-en-v1.5",
      source: "curated",
      identified: "measured",
      dimension: 384,
    },
  },
  building: null,
}

const MULTILINGUAL = {
  active: {
    name: "multilingual-e5-small",
    spec: {
      id: "intfloat/multilingual-e5-small",
      source: "huggingface",
      identified: "declared",
      dimension: 384,
    },
  },
  building: null,
}

/** The workspace's event stream, fed by the test as the worker would feed it. */
let feed: ReadableStreamDefaultController<Uint8Array> | null = null
const encoder = new TextEncoder()
const connected = () => feed?.enqueue(encoder.encode(": connected\n\n"))
const transcribed = (done_s: number, total_s = 3480) =>
  feed?.enqueue(
    encoder.encode(
      `event: documents\ndata: ${JSON.stringify({
        ids: [5],
        status: "processing",
        progress: { done_s, total_s },
      })}\n\n`
    )
  )
const changed = (status: WorkspaceDocument["status"]) =>
  feed?.enqueue(
    encoder.encode(
      `event: documents\ndata: ${JSON.stringify({ ids: [5], status })}\n\n`
    )
  )

/** The API: the listing the test sets, the event stream, and what rows read. */
function serving(
  documents: WorkspaceDocument[],
  { embedding = BGE_SMALL }: { embedding?: unknown } = {}
) {
  const calls: string[] = []
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input)
      calls.push(`${init?.method ?? "GET"} ${path}`)
      if (path.endsWith("/events")) {
        // The set-up popover follows downloads on a stream of its own.
        const workspace = path === "/workspaces/1/events"
        return new Response(
          new ReadableStream<Uint8Array>({
            start(controller) {
              if (workspace) feed = controller
            },
          }),
          { headers: { "Content-Type": "text/event-stream" } }
        )
      }
      if (path === LIST) return Response.json(documents)
      if (path === "/embedding/index") return Response.json(embedding)
      if (path === "/llm/catalog/local") {
        return Response.json({ rows: [fakeSpeechRow()], recommended_id: null })
      }
      if (path === "/llm/selection/speech_to_text/language") {
        return Response.json({
          language: "auto",
          languages: NEMOTRON_LANGUAGES,
          detects_language: true,
        })
      }
      return Response.json({ detail: "not found" }, { status: 404 })
    })
  )
  return { listings: () => calls.filter((call) => call === `GET ${LIST}`) }
}

function Harness({
  onOpenSpeechSettings = vi.fn(),
}: {
  onOpenSpeechSettings?: () => void
}) {
  const sources = useSources(1)
  return (
    <SourcesPanel
      documents={sources.documents}
      selectedDocumentIds={sources.includedDocumentIds}
      transcriptionPaces={sources.transcriptionPaces}
      highlightedDocumentId={null}
      isLoading={sources.isLoading}
      isDeleting={sources.isDeleting}
      error={sources.error}
      onOpen={vi.fn()}
      onReveal={vi.fn()}
      onRetry={vi.fn()}
      onCancel={vi.fn()}
      onDelete={vi.fn()}
      onDeleteSelected={vi.fn()}
      onSelectionChange={vi.fn()}
      onToggleAll={vi.fn()}
      onOpenSpeechSettings={onOpenSpeechSettings}
    />
  )
}

const row = () => screen.getByRole("treeitem", { name: "meeting.mp3" })

beforeEach(() => {
  feed = null
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  )
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe("recordings in the sources panel", () => {
  it("shows how much of a recording is transcribed, and how long is left", async () => {
    const api = serving([
      recording("processing", { progress: { done_s: 1380, total_s: 3480 } }),
    ])
    const now = vi.spyOn(Date, "now").mockReturnValue(1_000_000)
    render(<Harness />)

    expect(await screen.findByText("Transcribing · 23 of 58 min")).toBeTruthy()
    expect(row().getAttribute("aria-describedby")).toBeTruthy()

    await waitFor(() => expect(feed).not.toBeNull())
    connected()
    transcribed(1400)
    expect(await screen.findByText("Transcribing · 23 of 58 min")).toBeTruthy()
    // 140 s of audio in 10 s: 14 times real time, so 1,940 s take about 2 min.
    now.mockReturnValue(1_010_000)
    transcribed(1540)

    expect(
      await screen.findByText("Transcribing · 25 of 58 min · about 2 min left")
    ).toBeTruthy()
    // A window's progress is not a change of the row: nothing is read again.
    expect(api.listings()).toHaveLength(1)
  })

  it("says less than a minute is left near the end", async () => {
    serving([
      recording("processing", { progress: { done_s: 3000, total_s: 3480 } }),
    ])
    const now = vi.spyOn(Date, "now").mockReturnValue(1_000_000)
    render(<Harness />)
    await screen.findByText("Transcribing · 50 of 58 min")
    await waitFor(() => expect(feed).not.toBeNull())
    connected()

    transcribed(3100)
    await screen.findByText("Transcribing · 51 of 58 min")
    now.mockReturnValue(1_010_000)
    transcribed(3400)

    expect(
      await screen.findByText(
        "Transcribing · 56 of 58 min · less than a minute left"
      )
    ).toBeTruthy()
  })

  it("reads a recording again when it resumes after making way, and times it afresh", async () => {
    const documents = [
      recording("processing", { progress: { done_s: 1380, total_s: 3480 } }),
    ]
    const api = serving(documents)
    const now = vi.spyOn(Date, "now").mockReturnValue(1_000_000)
    render(<Harness />)
    await screen.findByText("Transcribing · 23 of 58 min")
    await waitFor(() => expect(feed).not.toBeNull())
    connected()
    transcribed(1440)
    await screen.findByText("Transcribing · 24 of 58 min")
    now.mockReturnValue(1_010_000)
    transcribed(1580)
    await screen.findByText("Transcribing · 26 of 58 min · about 2 min left")

    // A PDF takes the queue; ten minutes later the recording resumes.
    documents[0] = recording("pending", {
      progress: { done_s: 1580, total_s: 3480 },
    })
    changed("pending")
    await screen.findByText("Queued · 45% transcribed")
    now.mockReturnValue(1_600_000)
    documents[0] = recording("processing", {
      progress: { done_s: 1680, total_s: 3480 },
    })
    transcribed(1680)

    // The row was queued, so the event's status is new to it: read again.
    expect(await screen.findByText("Transcribing · 28 of 58 min")).toBeTruthy()
    expect(api.listings()).toHaveLength(3)
    now.mockReturnValue(1_610_000)
    transcribed(1820)
    // 140 s in 10 s again; the queued ten minutes are not in the speed.
    expect(
      await screen.findByText("Transcribing · 30 of 58 min · about 2 min left")
    ).toBeTruthy()
  })

  it("shows a recording that made way for other sources as queued", async () => {
    serving([
      recording("pending", { progress: { done_s: 1392, total_s: 3480 } }),
    ])
    render(<Harness />)

    expect(await screen.findByText("Queued · 40% transcribed")).toBeTruthy()
  })

  it("says a recording waits for speech recognition, not that it failed, and sets it up from the row", async () => {
    serving([
      recording(
        "failed",
        { awaiting: true },
        { error_message: "no speech recognition model has been chosen yet" }
      ),
    ])
    const onOpenSpeechSettings = vi.fn()
    const user = userEvent.setup()
    render(<Harness onOpenSpeechSettings={onOpenSpeechSettings} />)

    expect(
      await screen.findByText("Waiting for speech recognition")
    ).toBeTruthy()
    expect(
      screen.queryByRole("button", { name: /Ingestion failed/ })
    ).toBeNull()

    await user.click(within(row()).getByRole("button", { name: "Set up" }))
    const popover = await screen.findByRole("dialog", {
      name: "Set up speech recognition",
    })
    expect(
      await within(popover).findByRole("button", {
        name: "Download and set up",
      })
    ).toBeTruthy()

    await user.click(
      within(popover).getByRole("button", { name: "More choices" })
    )
    expect(onOpenSpeechSettings).toHaveBeenCalledOnce()
  })

  it("keeps the set-up open while choosing a model queues the recording again", async () => {
    const documents = [recording("failed", { awaiting: true })]
    serving(documents)
    const user = userEvent.setup()
    render(<Harness />)
    await user.click(
      within(
        await screen.findByRole("treeitem", { name: "meeting.mp3" })
      ).getByRole("button", { name: "Set up" })
    )
    await screen.findByRole("dialog", { name: "Set up speech recognition" })
    await waitFor(() => expect(feed).not.toBeNull())
    connected()

    // The download chose the model, and the API queued the recording again.
    documents[0] = recording("pending", {})
    changed("pending")
    await screen.findByRole("status", { name: "Processing meeting.mp3" })

    expect(
      screen.getByRole("dialog", { name: "Set up speech recognition" })
    ).toBeTruthy()
    await user.keyboard("{Escape}")
    await waitFor(() =>
      expect(screen.queryByText("Waiting for speech recognition")).toBeNull()
    )
  })

  it("says search finds a recording best in its own language while the index is English-only", async () => {
    serving([
      recording("ready", { language: "ja" }),
      recording(
        "ready",
        { language: null },
        { id: 6, title: "interview.wav", mime_type: "audio/wav" }
      ),
      recording(
        "ready",
        { language: "en" },
        { id: 7, title: "standup.flac", mime_type: "audio/flac" }
      ),
    ])
    render(<Harness />)

    expect(
      await screen.findByText(
        "This recording is in Japanese. Search finds it best with questions in Japanese; add it to a chat to have all of it read."
      )
    ).toBeTruthy()
    expect(
      screen.getByText(
        "This recording’s language wasn’t identified. Search finds it best with questions in its language; add it to a chat to have all of it read."
      )
    ).toBeTruthy()
    // English is what the index reads best.
    expect(screen.getAllByText(/Search finds it best/)).toHaveLength(2)
  })

  it("says a transcript may be less accurate in a language the model is not listed for", async () => {
    serving(
      [
        recording("ready", { language: "et" }),
        recording(
          "ready",
          { language: "ja" },
          { id: 6, title: "interview.wav", mime_type: "audio/wav" }
        ),
      ],
      { embedding: MULTILINGUAL }
    )
    render(<Harness />)

    expect(
      await screen.findByText(
        "Estonian (detected) · the transcript may be less accurate"
      )
    ).toBeTruthy()
    // Japanese is one the model is listed for.
    expect(screen.getAllByText(/may be less accurate/)).toHaveLength(1)
  })

  it("says nothing of search once the index reads every language", async () => {
    serving([recording("ready", { language: "ja" })], {
      embedding: MULTILINGUAL,
    })
    render(<Harness />)
    await screen.findByRole("treeitem", { name: "meeting.mp3" })
    await waitFor(() =>
      expect(
        vi
          .mocked(fetch)
          .mock.calls.some(([input]) => String(input) === "/embedding/index")
      ).toBe(true)
    )
    // Long enough for the index's answer to render.
    await act(() => new Promise((resolve) => setTimeout(resolve, 50)))

    expect(screen.queryByText(/Search finds it best/)).toBeNull()
  })
})
