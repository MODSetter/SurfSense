import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { cleanup, render, screen } from "@testing-library/react"
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
  return (
    <>
      <StudioPanel
        documents={documents}
        formats={studio.formats}
        isCreating={studio.isCreating}
        error={studio.error}
        onGenerate={studio.create}
      />
      <ArtifactList
        artifacts={studio.artifacts}
        isLoading={studio.isLoading}
        onOpen={vi.fn()}
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
          documents={[]}
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
              requires_role: "generation",
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
    expect(screen.getByText("Sources (1 selected)")).toBeTruthy()
    expect(screen.getByRole("button", { name: "Deselect all" })).toBeTruthy()
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
    expect(
      screen.getByRole("heading", { name: "All generated artifacts" })
    ).toBeTruthy()
    expect(
      screen.getByRole("status", { name: "Processing Summary" })
    ).toBeTruthy()
  })

  it("selects every ready source and can clear them from the header", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input)
      if (path === "/workspaces/1/studio/formats") {
        return Response.json([
          {
            key: "summary",
            label: "Summary",
            requires_role: "generation",
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
              requires_role: "image_generation",
              available: false,
              unavailable_reason: "Image model required",
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
    expect(
      await screen.findByRole("tooltip", {
        name: "Image model required",
      })
    ).toBeTruthy()
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
              requires_role: "generation",
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
      await screen.findByRole("tooltip", {
        name: "Generate an AI interactive quiz based on your sources",
      })
    ).toBeTruthy()
  })
})
