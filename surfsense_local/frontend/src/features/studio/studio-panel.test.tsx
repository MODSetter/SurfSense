import { useState } from "react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { cleanup, render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { TooltipProvider } from "@/components/ui/tooltip"

import { ArtifactList } from "./artifact-list"
import { StudioPanel } from "./studio-panel"
import { useStudio } from "./use-studio"

const readyDocument = {
  id: 4,
  title: "Saturn facts",
  document_type: "NOTE" as const,
  status: "ready" as const,
  error_message: null,
  created_at: "2026-09-05T00:00:00Z",
  updated_at: "2026-09-05T00:00:00Z",
}

const pendingArtifact = {
  id: 9,
  document_id: 20,
  format: "summary",
  generation: 1,
  title: "Summary",
  status: "pending" as const,
  error_message: null,
  created_at: "2026-09-06T00:00:00Z",
  updated_at: "2026-09-06T00:00:00Z",
}

function StudioHarness({
  documents = [readyDocument],
}: {
  documents?: (typeof readyDocument)[]
}) {
  const studio = useStudio(1)
  // The panel is told what is selected; the page owns it. Mirror useSources,
  // which tracks the excluded ids so a ready source starts out included.
  const [excluded, setExcluded] = useState<ReadonlySet<number>>(new Set())
  const readyIds = documents
    .filter((document) => document.status === "ready")
    .map((document) => document.id)
  const includedIds = readyIds.filter((id) => !excluded.has(id))
  return (
    <>
      <StudioPanel
        workspaceId={1}
        documents={documents}
        selectedDocumentIds={includedIds}
        onSelectionChange={(id, included) =>
          setExcluded((current) => {
            const next = new Set(current)
            if (included) next.delete(id)
            else next.add(id)
            return next
          })
        }
        onToggleAll={() =>
          setExcluded(
            readyIds.length > 0 && includedIds.length === readyIds.length
              ? new Set(readyIds)
              : new Set()
          )
        }
        formats={studio.formats}
        isCreating={studio.isCreating}
        error={studio.error}
        onGenerate={studio.create}
      />
      <ArtifactList
        workspaceId={1}
        artifacts={studio.artifacts}
        isLoading={studio.isLoading}
        onOpen={vi.fn()}
        onRegenerate={(id) => void studio.regenerate(id)}
        onCancel={(id) => void studio.cancel(id)}
        onDelete={(id) => void studio.remove(id)}
      />
    </>
  )
}

function renderStudio(documents: (typeof readyDocument)[] = [readyDocument]) {
  return render(
    <TooltipProvider>
      <StudioHarness documents={documents} />
    </TooltipProvider>
  )
}

beforeEach(() => {
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
  vi.unstubAllGlobals()
})

describe("studio panel", () => {
  it("shows the catalog cards before formats load", () => {
    render(
      <TooltipProvider>
        <StudioPanel
          workspaceId={1}
          documents={[]}
          selectedDocumentIds={[]}
          onSelectionChange={vi.fn()}
          onToggleAll={vi.fn()}
          formats={[]}
          isCreating={false}
          error={null}
          onGenerate={async () => false}
        />
      </TooltipProvider>
    )

    expect(screen.getByRole("button", { name: "Summary" })).toBeTruthy()
    expect(screen.getByRole("button", { name: "Infographic" })).toBeTruthy()
    expect(document.querySelector("[data-slot=skeleton]")).toBeNull()
  })

  it("submits a job for the chosen format and sources", async () => {
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input)
        if (path === "/workspaces/1/studio/formats") {
          return Response.json([
            {
              key: "summary",
              label: "Summary",
              requires_model_types: ["text_gen"],
              available: true,
              unavailable_reason: null,
            },
          ])
        }
        if (path === "/workspaces/1/studio/jobs" && init?.method === "POST") {
          return Response.json(pendingArtifact, { status: 201 })
        }
        if (path === "/workspaces/1/artifacts") {
          return Response.json([])
        }
        return Response.json({ detail: "not found" }, { status: 404 })
      }
    )
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()

    renderStudio()

    await user.click(await screen.findByRole("button", { name: "Summary" }))
    expect(screen.getByRole("dialog", { name: "Summary" })).toBeTruthy()
    // The one ready source is picked for you, so Generate works on open.
    expect(screen.getByRole("button", { name: "1 source" })).toBeTruthy()
    expect(screen.getByText("Prompt (optional)")).toBeTruthy()
    await user.click(screen.getByRole("button", { name: /Generate/ }))

    const jobCall = await vi.waitFor(() =>
      fetchMock.mock.calls.find(
        ([path, init]) =>
          path === "/workspaces/1/studio/jobs" && init?.method === "POST"
      )
    )
    expect(JSON.parse(String(jobCall?.[1]?.body))).toEqual({
      format: "summary",
      document_ids: [4],
    })
    await vi.waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "Summary" })).toBeNull()
    )
    expect(screen.getByRole("heading", { name: "Artifacts" })).toBeTruthy()
    expect(
      screen.getByRole("status", { name: "Processing Summary" })
    ).toBeTruthy()
  })

  it("opens the podcast brief for review and sends it with the job", async () => {
    const brief = {
      language: "en-US",
      style: "conversational",
      duration: "standard",
      speakers: [
        { name: "Host", role: "host", voice: "af_heart" },
        { name: "Guest", role: "guest", voice: "am_adam" },
      ],
    }
    const voices = [
      { id: "af_heart", label: "Heart", languages: ["en-US"] },
      { id: "am_adam", label: "Adam", languages: ["en-US"] },
    ]
    let openBrief = () => {}
    const briefGate = new Promise<void>((resolve) => {
      openBrief = resolve
    })
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input)
        if (path === "/workspaces/1/studio/formats") {
          return Response.json([
            {
              key: "podcast",
              label: "Podcast",
              requires_model_types: ["text_gen"],
              available: true,
              unavailable_reason: null,
            },
          ])
        }
        if (path === "/workspaces/1/studio/podcast/brief") {
          await briefGate
          return Response.json({ brief, voices })
        }
        if (path === "/workspaces/1/studio/jobs" && init?.method === "POST") {
          return Response.json(
            { ...pendingArtifact, format: "podcast", title: "Podcast" },
            { status: 201 }
          )
        }
        if (path === "/workspaces/1/artifacts") return Response.json([])
        return Response.json({ detail: "not found" }, { status: 404 })
      }
    )
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()

    renderStudio()

    await user.click(await screen.findByRole("button", { name: "Podcast" }))
    const generate = screen.getByRole("button", { name: /Generate/ })
    expect(generate.hasAttribute("disabled")).toBe(true) // until the brief loads
    openBrief()

    const name = within(
      await screen.findByRole("group", { name: "Speaker 1" })
    ).getByLabelText("Name")
    await user.clear(name)
    await user.type(name, "Ada")
    await user.click(screen.getByRole("button", { name: /Long/ }))
    await user.click(generate)

    const jobCall = await vi.waitFor(() =>
      fetchMock.mock.calls.find(
        ([path, init]) =>
          path === "/workspaces/1/studio/jobs" && init?.method === "POST"
      )
    )
    expect(JSON.parse(String(jobCall?.[1]?.body))).toEqual({
      format: "podcast",
      document_ids: [4],
      options: {
        ...brief,
        duration: "long",
        speakers: [{ ...brief.speakers[0], name: "Ada" }, brief.speakers[1]],
      },
    })
  })

  it("selects every ready source and can clear them from the header", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input)
      if (path === "/workspaces/1/studio/formats") {
        return Response.json([
          {
            key: "summary",
            label: "Summary",
            requires_model_types: ["text_gen"],
            available: true,
            unavailable_reason: null,
          },
        ])
      }
      if (path === "/workspaces/1/artifacts") return Response.json([])
      return Response.json({ detail: "not found" }, { status: 404 })
    })
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()

    renderStudio([
      readyDocument,
      { ...readyDocument, id: 5, title: "Titan notes" },
    ])

    await user.click(await screen.findByRole("button", { name: "Summary" }))
    // The list lives in the second pane, which the count opens.
    await user.click(screen.getByRole("button", { name: "2 sources" }))
    expect(screen.getByText("Sources (2 selected)")).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Deselect all" }))
    expect(screen.getByText("Sources (0 selected)")).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Select all" }))
    expect(screen.getByText("Sources (2 selected)")).toBeTruthy()
  })

  it("explains why an unavailable image format is disabled", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input)
        if (path === "/workspaces/1/studio/formats") {
          return Response.json([
            {
              key: "image",
              label: "Image",
              requires_model_types: ["image_gen", "text_gen"],
              available: false,
              unavailable_reason: "Needs an image model",
            },
          ])
        }
        if (path === "/workspaces/1/artifacts") return Response.json([])
        return Response.json({ detail: "not found" }, { status: 404 })
      })
    )
    const user = userEvent.setup()

    renderStudio()

    const image = await screen.findByRole("button", { name: "Image" })
    expect(image.getAttribute("aria-disabled")).toBe("true")
    await user.hover(image)
    expect(await screen.findByText("Needs an image model")).toBeTruthy()
  })

  it("shows an explanation tooltip on an available artifact", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input)
        if (path === "/workspaces/1/studio/formats") {
          return Response.json([
            {
              key: "quiz",
              label: "Quiz",
              requires_model_types: ["text_gen"],
              available: true,
              unavailable_reason: null,
            },
          ])
        }
        if (path === "/workspaces/1/artifacts") return Response.json([])
        return Response.json({ detail: "not found" }, { status: 404 })
      })
    )
    const user = userEvent.setup()

    renderStudio()

    const quiz = await screen.findByRole("button", { name: "Quiz" })
    await user.hover(quiz)
    expect(
      await screen.findByText(
        "Generate an AI interactive quiz based on your sources"
      )
    ).toBeTruthy()
  })
})
