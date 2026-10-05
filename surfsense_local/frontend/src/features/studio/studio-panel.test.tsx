import { useState } from "react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { TooltipProvider } from "@/components/ui/tooltip"
import { render } from "@/test-utils"

import { ArtifactList } from "./artifact-list"
import { StudioPanel } from "./studio-panel"
import { useStudio } from "./use-studio"

const readyDocument = {
  id: 4,
  title: "Saturn facts",
  document_type: "NOTE" as const,
  mime_type: null,
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
  onSetUpVoices = () => undefined,
}: {
  documents?: (typeof readyDocument)[]
  onSetUpVoices?: () => void
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
        onSetUpVoices={onSetUpVoices}
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

function renderStudio(
  documents: (typeof readyDocument)[] = [readyDocument],
  onSetUpVoices?: () => void
) {
  return render(
    <TooltipProvider>
      <StudioHarness documents={documents} onSetUpVoices={onSetUpVoices} />
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
  it("sends the ticked folders as the job's source scope", async () => {
    const onGenerate = vi.fn(async () => true)
    const scope = {
      all: false,
      folder_ids: [2],
      excluded_folder_ids: [],
      document_ids: [],
      excluded_document_ids: [],
    }
    const user = userEvent.setup()
    render(
      <TooltipProvider>
        <StudioPanel
          workspaceId={1}
          documents={[readyDocument]}
          selectedDocumentIds={[4]}
          sourceScope={scope}
          onSelectionChange={vi.fn()}
          onToggleAll={vi.fn()}
          formats={[
            {
              key: "summary",
              label: "Summary",
              requires_model_types: ["text_gen"],
              available: true,
              unavailable_reason: null,
            },
          ]}
          isCreating={false}
          error={null}
          onGenerate={onGenerate}
          onSetUpVoices={vi.fn()}
        />
      </TooltipProvider>
    )

    await user.click(await screen.findByRole("button", { name: "Summary" }))
    await user.click(screen.getByRole("button", { name: /Generate/ }))

    expect(onGenerate).toHaveBeenCalledWith({
      format: "summary",
      document_ids: [4],
      source_scope: scope,
    })
  })

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
          onSetUpVoices={() => undefined}
        />
      </TooltipProvider>
    )

    expect(screen.getByRole("button", { name: "Summary" })).toBeTruthy()
    expect(screen.getByRole("button", { name: "Infographic" })).toBeTruthy()
    expect(document.querySelector("[data-slot=skeleton]")).toBeNull()
  })

  it("uses the server catalog after it loads, including unknown formats", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input)
        if (path === "/workspaces/1/studio/formats") {
          return Response.json([
            {
              key: "timeline",
              label: "Timeline",
              requires_model_types: ["text_gen"],
              available: false,
              unavailable_reason: "Timeline renderer is unavailable",
            },
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

    renderStudio()
    const user = userEvent.setup()

    const formats = screen.getByRole("region", { name: "Studio formats" })
    const timeline = await within(formats).findByRole("button", {
      name: "Timeline",
    })
    expect(timeline.getAttribute("aria-disabled")).toBe("true")
    await user.hover(timeline)
    expect(
      await screen.findByText("Timeline renderer is unavailable")
    ).toBeTruthy()
    expect(
      within(formats)
        .getAllByRole("button")
        .map((button) => button.textContent)
    ).toEqual(["Timeline", "Quiz"])
    expect(
      within(formats).queryByRole("button", { name: "Summary" })
    ).toBeNull()
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
          return Response.json({
            brief,
            voices,
            voices_source: "local",
            voiced_by: null,
            languages: ["en-US"],
          })
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
    const titan = screen.getByRole("checkbox", { name: "Titan notes" })
    expect(titan.getAttribute("aria-checked")).toBe("true")
    await user.click(screen.getByText("Titan notes"))
    expect(titan.getAttribute("aria-checked")).toBe("false")
    expect(screen.getByText("Sources (1 selected)")).toBeTruthy()
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

    // The catalog card shows first; the server's answer disables it.
    await waitFor(() =>
      expect(
        screen
          .getByRole("button", { name: "Image" })
          .getAttribute("aria-disabled")
      ).toBe("true")
    )
    await user.hover(screen.getByRole("button", { name: "Image" }))
    expect(await screen.findByText("Needs an image model")).toBeTruthy()
  })

  it("shows its own text for a reason code, not the backend's English", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input)
        if (path === "/workspaces/1/studio/formats") {
          return Response.json([
            {
              key: "podcast",
              label: "Podcast",
              requires_model_types: ["text_gen", "audio_gen"],
              available: false,
              unavailable_reason: "backend prose, never shown",
              unavailable_code: "needs_chat_audio",
            },
          ])
        }
        if (path === "/workspaces/1/artifacts") return Response.json([])
        return Response.json({ detail: "not found" }, { status: 404 })
      })
    )
    const user = userEvent.setup()

    renderStudio()

    await user.hover(await screen.findByRole("button", { name: "Podcast" }))
    expect(
      await screen.findByText("Needs a chat model and an audio model.")
    ).toBeTruthy()
    expect(screen.queryByText("backend prose, never shown")).toBeNull()
  })

  it("falls back to the backend's reason for a code it has no text for", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input)
        if (path === "/workspaces/1/studio/formats") {
          return Response.json([
            {
              key: "podcast",
              label: "Podcast",
              requires_model_types: ["text_gen", "audio_gen"],
              available: false,
              unavailable_reason: "Needs a newer audio runtime",
              unavailable_code: "needs_runtime_upgrade",
            },
          ])
        }
        if (path === "/workspaces/1/artifacts") return Response.json([])
        return Response.json({ detail: "not found" }, { status: 404 })
      })
    )
    const user = userEvent.setup()

    renderStudio()

    await user.hover(await screen.findByRole("button", { name: "Podcast" }))
    expect(await screen.findByText("Needs a newer audio runtime")).toBeTruthy()
  })

  it("shows its own text when a regenerate is refused with a reason code", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input)
        if (path === "/workspaces/1/studio/formats") return Response.json([])
        if (path === "/workspaces/1/artifacts") {
          return Response.json([{ ...pendingArtifact, status: "failed" }])
        }
        if (path === "/artifacts/9/regenerate" && init?.method === "POST") {
          return Response.json(
            {
              detail: {
                message: "backend prose, never shown",
                code: "needs_image",
              },
            },
            { status: 409 }
          )
        }
        return Response.json({ detail: "not found" }, { status: 404 })
      })
    )
    const user = userEvent.setup()

    renderStudio()

    await user.click(
      await screen.findByRole("button", {
        name: "Generation failed. Retry Summary",
      })
    )
    const alert = await screen.findByRole("alert")
    expect(within(alert).getByText("Needs an image model.")).toBeTruthy()
    expect(screen.queryByText("backend prose, never shown")).toBeNull()
  })

  it("shows the backend's message for a refusal code it has no text for", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input)
        if (path === "/workspaces/1/studio/formats") return Response.json([])
        if (path === "/workspaces/1/artifacts") {
          return Response.json([{ ...pendingArtifact, status: "failed" }])
        }
        if (path === "/artifacts/9/regenerate" && init?.method === "POST") {
          return Response.json(
            {
              detail: {
                message: "Needs a newer audio runtime",
                code: "needs_runtime_upgrade",
              },
            },
            { status: 409 }
          )
        }
        return Response.json({ detail: "not found" }, { status: 404 })
      })
    )
    const user = userEvent.setup()

    renderStudio()

    await user.click(
      await screen.findByRole("button", {
        name: "Generation failed. Retry Summary",
      })
    )
    const alert = await screen.findByRole("alert")
    expect(within(alert).getByText("Needs a newer audio runtime")).toBeTruthy()
  })

  it("shows its own text when the podcast brief is refused with a reason code", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input)
        if (path === "/workspaces/1/studio/formats") {
          return Response.json([
            {
              key: "podcast",
              label: "Podcast",
              requires_model_types: ["text_gen", "audio_gen"],
              available: true,
              unavailable_reason: null,
            },
          ])
        }
        if (path === "/workspaces/1/studio/podcast/brief") {
          return Response.json(
            {
              detail: {
                message: "backend prose, never shown",
                code: "needs_audio",
              },
            },
            { status: 409 }
          )
        }
        if (path === "/workspaces/1/artifacts") return Response.json([])
        return Response.json({ detail: "not found" }, { status: 404 })
      })
    )
    const user = userEvent.setup()

    renderStudio()

    await user.click(await screen.findByRole("button", { name: "Podcast" }))
    const dialog = await screen.findByRole("dialog", { name: "Podcast" })
    expect(
      await within(dialog).findByText("Needs an audio model.")
    ).toBeTruthy()
    expect(screen.queryByText("backend prose, never shown")).toBeNull()
  })

  it("uses complete messages for both model fallback shapes", async () => {
    const user = userEvent.setup()

    render(
      <TooltipProvider>
        <StudioPanel
          workspaceId={1}
          documents={[]}
          selectedDocumentIds={[]}
          onSelectionChange={vi.fn()}
          onToggleAll={vi.fn()}
          formats={[
            {
              key: "summary",
              label: "Summary",
              requires_model_types: ["text_gen"],
              available: false,
              unavailable_reason: null,
            },
            {
              key: "image",
              label: "Image",
              requires_model_types: ["image_gen", "text_gen"],
              available: false,
              unavailable_reason: null,
            },
          ]}
          isCreating={false}
          error={null}
          onGenerate={async () => false}
          onSetUpVoices={() => undefined}
        />
      </TooltipProvider>
    )

    const image = screen.getByRole("button", { name: "Image" })
    await user.hover(image)
    expect(
      await screen.findByText("Needs a chat model and an image model.")
    ).toBeTruthy()
    await user.unhover(image)
    const summary = screen.getByRole("button", { name: "Summary" })
    await user.hover(summary)
    expect(await screen.findByText("Needs a chat model.")).toBeTruthy()
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

  it("holds a podcast on a server model with no voices, and points to setting them up", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input)
        if (path === "/workspaces/1/studio/formats") {
          return Response.json([
            {
              key: "podcast",
              label: "Podcast",
              requires_model_types: ["text_gen", "audio_gen"],
              available: true,
              unavailable_reason: null,
            },
          ])
        }
        if (path === "/workspaces/1/studio/podcast/brief") {
          return Response.json({
            brief: {
              language: "en",
              style: "conversational",
              duration: "standard",
              speakers: [{ name: "Host", role: "host", voice: "" }],
            },
            voices: [],
            voices_source: "saved",
            voiced_by: { server: "OpenRouter", model: "seed-audio-1-0" },
            languages: ["en"],
          })
        }
        if (path === "/workspaces/1/artifacts") return Response.json([])
        return Response.json({ detail: "not found" }, { status: 404 })
      })
    )
    const setUp = vi.fn()
    const user = userEvent.setup()

    renderStudio([readyDocument], setUp)
    await user.click(await screen.findByRole("button", { name: "Podcast" }))

    await user.click(
      await screen.findByRole("button", { name: "Set up voices" })
    )
    expect(setUp).toHaveBeenCalledOnce()
  })
})
