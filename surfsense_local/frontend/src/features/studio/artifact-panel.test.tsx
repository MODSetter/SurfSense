import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { render } from "@/test-utils"

import type { Artifact } from "./api"
import { ArtifactPanel } from "./artifact-panel"

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("artifact panel", () => {
  it("loads an artifact into the detail rail", async () => {
    const onClose = vi.fn()
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        if (String(input) === "/artifacts/12") {
          return Response.json({
            id: 12,
            document_id: 4,
            format: "summary",
            generation: 1,
            title: "Weekly summary",
            status: "ready",
            error_message: null,
            content: "Saturn is a gas giant.",
            files: [
              {
                role: "primary",
                mime_type: "text/markdown",
                size_bytes: 24,
                original_filename: "summary.md",
              },
            ],
            created_at: "2026-09-06T00:00:00Z",
            updated_at: "2026-09-06T00:00:00Z",
          })
        }
        return Response.json({ detail: "not found" }, { status: 404 })
      })
    )
    const user = userEvent.setup()

    render(
      <ArtifactPanel
        artifactId={12}
        artifacts={[]}
        onOpenVersion={vi.fn()}
        onClose={onClose}
      />
    )

    expect(
      await screen.findByRole("complementary", { name: "Artifact" })
    ).toBeTruthy()
    expect(await screen.findByText("Weekly summary")).toBeTruthy()
    expect(screen.getByText("Saturn is a gas giant.")).toBeTruthy()
    // The API is another origin, where `download` is ignored: the server
    // itself must say attachment, or the file opens in a window.
    expect(
      screen.getByRole("link", { name: "Download" }).getAttribute("href")
    ).toMatch(/\/artifacts\/12\/files\/primary\?download=1$/)
    await user.click(screen.getByRole("button", { name: "Close artifact" }))
    expect(onClose).toHaveBeenCalled()
  })

  it("opens flashcards in the study viewer from the deck file", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input)
        if (path === "/artifacts/13") {
          return Response.json({
            id: 13,
            document_id: 5,
            format: "flashcards",
            generation: 1,
            title: "Cassini",
            status: "ready",
            error_message: null,
            content: "# Cassini\n\n**1. Arrival?**\n\n2004",
            files: [
              {
                role: "primary",
                mime_type: "application/json",
                size_bytes: 90,
                original_filename: "cassini.json",
              },
            ],
            created_at: "2026-09-06T00:00:00Z",
            updated_at: "2026-09-06T00:00:00Z",
          })
        }
        if (path === "/artifacts/13/files/primary") {
          return Response.json({
            schema_version: 1,
            title: "Cassini",
            cards: [{ front_text: "Arrival?", back_text: "2004" }],
          })
        }
        return Response.json({ detail: "not found" }, { status: 404 })
      })
    )

    render(
      <ArtifactPanel
        artifactId={13}
        artifacts={[]}
        onOpenVersion={vi.fn()}
        onClose={vi.fn()}
      />
    )

    expect(
      await screen.findByRole("button", { name: "Reveal answer" })
    ).toBeTruthy()
    expect(screen.getByText("Arrival?")).toBeTruthy()
    // The markdown body is for search, not for the study screen.
    expect(screen.queryByText(/\*\*1\. Arrival\?\*\*/)).toBeNull()
  })
})

describe("artifact panel versions", () => {
  function proposal(
    id: number,
    number: number,
    extra: Partial<Omit<Artifact, "version">> = {}
  ) {
    return {
      id,
      document_id: id + 100,
      format: "pdf",
      generation: 1,
      title: "Client proposal",
      status: "ready",
      error_message: null,
      created_at: `2026-10-0${number}T00:00:00Z`,
      updated_at: `2026-10-0${number}T00:00:00Z`,
      version: { root_id: 30, number, parent_id: number > 1 ? id - 1 : null },
      spec_kind: "python",
      ...extra,
    } satisfies Artifact
  }
  const [v1, v2, v3] = [proposal(30, 1), proposal(31, 2), proposal(32, 3)]

  // Each version's body names it, so the test can tell which one is shown.
  function serveDetails() {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const id = Number(String(input).match(/^\/artifacts\/(\d+)$/)?.[1])
        const version = [v1, v2, v3].find((candidate) => candidate.id === id)
        if (!version) {
          return Response.json({ detail: "not found" }, { status: 404 })
        }
        return Response.json({
          ...version,
          format: "summary",
          content: `Body of v${version.version.number}`,
          files: [],
          quiz_state: null,
          flashcard_state: null,
        })
      })
    )
  }

  it("lists the document’s versions and opens the one chosen", async () => {
    serveDetails()
    const onOpenVersion = vi.fn()
    const user = userEvent.setup()

    render(
      <ArtifactPanel
        artifactId={31}
        artifacts={[proposal(33, 4, { status: "failed" }), v3, v2, v1]}
        onOpenVersion={onOpenVersion}
        onClose={vi.fn()}
      />
    )

    expect(await screen.findByText("Body of v2")).toBeTruthy()
    await user.click(
      screen.getByRole("button", { name: "Showing v2. Choose a version" })
    )
    expect(
      (await screen.findAllByRole("menuitemradio")).map((item) =>
        item.textContent?.trim()
      )
    ).toEqual(["v1", "v2", "v3", "v4 Failed"])
    expect(
      screen
        .getByRole("menuitemradio", { name: "v4 Failed" })
        .getAttribute("aria-disabled")
    ).toBe("true")
    await user.click(screen.getByRole("menuitemradio", { name: "v1" }))
    expect(onOpenVersion).toHaveBeenCalledExactlyOnceWith(30)
  })

  it("opens a newer version of the document once it is ready", async () => {
    serveDetails()
    const onOpenVersion = vi.fn()
    const panel = (artifacts: Artifact[]) => (
      <ArtifactPanel
        artifactId={30}
        artifacts={artifacts}
        onOpenVersion={onOpenVersion}
        onClose={vi.fn()}
      />
    )

    // Opening an older version on purpose does not jump to the newest.
    const { rerender } = render(panel([v2, v1]))
    expect(await screen.findByText("Body of v1")).toBeTruthy()
    expect(onOpenVersion).not.toHaveBeenCalled()

    rerender(panel([{ ...v3, status: "processing" }, v2, v1]))
    expect(onOpenVersion).not.toHaveBeenCalled()

    rerender(panel([v3, v2, v1]))
    expect(onOpenVersion).toHaveBeenCalledExactlyOnceWith(32)
  })

  it("stays on an older version while the newest one is run again", async () => {
    serveDetails()
    const onOpenVersion = vi.fn()
    const panel = (artifacts: Artifact[]) => (
      <ArtifactPanel
        artifactId={30}
        artifacts={artifacts}
        onOpenVersion={onOpenVersion}
        onClose={vi.fn()}
      />
    )

    const { rerender } = render(panel([v3, v2, v1]))
    expect(await screen.findByText("Body of v1")).toBeTruthy()

    // Regenerate acts on the newest version; it is not a new one.
    rerender(panel([{ ...v3, status: "pending" }, v2, v1]))
    rerender(panel([v3, v2, v1]))
    expect(onOpenVersion).not.toHaveBeenCalled()
  })

  it("shows no version switcher for an artifact without versions", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        Response.json({
          id: 12,
          document_id: 4,
          format: "summary",
          generation: 1,
          title: "Weekly summary",
          status: "ready",
          error_message: null,
          content: "Saturn is a gas giant.",
          files: [],
          created_at: "2026-09-06T00:00:00Z",
          updated_at: "2026-09-06T00:00:00Z",
          version: null,
          spec_kind: null,
        })
      )
    )

    render(
      <ArtifactPanel
        artifactId={12}
        artifacts={[
          {
            id: 12,
            document_id: 4,
            format: "summary",
            generation: 1,
            title: "Weekly summary",
            status: "ready",
            error_message: null,
            created_at: "2026-09-06T00:00:00Z",
            updated_at: "2026-09-06T00:00:00Z",
            version: null,
            spec_kind: null,
          },
        ]}
        onOpenVersion={vi.fn()}
        onClose={vi.fn()}
      />
    )

    expect(await screen.findByText("Saturn is a gas giant.")).toBeTruthy()
    expect(
      screen.queryByRole("button", { name: /Choose a version/ })
    ).toBeNull()
  })
})
