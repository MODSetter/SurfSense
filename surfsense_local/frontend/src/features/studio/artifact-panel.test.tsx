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
        onRefine={vi.fn()}
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
        onRefine={vi.fn()}
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
      refinable: false,
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
        onRefine={vi.fn()}
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
        onRefine={vi.fn()}
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
        onRefine={vi.fn()}
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
          refinable: false,
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
            refinable: false,
          },
        ]}
        onOpenVersion={vi.fn()}
        onRefine={vi.fn()}
        onClose={vi.fn()}
      />
    )

    expect(await screen.findByText("Saturn is a gas giant.")).toBeTruthy()
    expect(
      screen.queryByRole("button", { name: /Choose a version/ })
    ).toBeNull()
  })
})

describe("artifact panel refine", () => {
  function report(id: number, number: number, extra: Partial<Artifact> = {}) {
    return {
      id,
      document_id: id + 100,
      format: "docx",
      generation: 1,
      title: "Quarterly report",
      status: "ready",
      error_message: null,
      created_at: `2026-10-0${number}T00:00:00Z`,
      updated_at: `2026-10-0${number}T00:00:00Z`,
      version: { root_id: 40, number, parent_id: number > 1 ? id - 1 : null },
      spec_kind: "markdown",
      refinable: true,
      ...extra,
    } satisfies Artifact
  }

  // The body is served as a summary so the test needs no Word renderer; the
  // list entry is what says the document is Word.
  function serveDetail(artifact: Artifact) {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        Response.json({
          ...artifact,
          format: "summary",
          content: "Body of the report",
          files: [],
          quiz_state: null,
          flashcard_state: null,
        })
      )
    )
  }

  function panel(
    artifacts: Artifact[],
    onRefine: (artifactId: number, instruction: string) => Promise<void>,
    artifactId = 40
  ) {
    return (
      <ArtifactPanel
        artifactId={artifactId}
        artifacts={artifacts}
        onOpenVersion={vi.fn()}
        onRefine={onRefine}
        onClose={vi.fn()}
      />
    )
  }

  const OPEN = { name: "Refine this document" }
  const INSTRUCTION = { name: "How to change this document" }

  // A detail read that answers only when the test lets it.
  function serveDetailLater(artifact: Artifact, content: string) {
    let answer = () => {}
    vi.stubGlobal(
      "fetch",
      vi.fn(
        () =>
          new Promise<Response>((resolve) => {
            answer = () =>
              resolve(
                Response.json({
                  ...artifact,
                  format: "summary",
                  content,
                  files: [],
                  quiz_state: null,
                  flashcard_state: null,
                })
              )
          })
      )
    )
    return () => answer()
  }

  it("keeps the box and its draft through a switch of version, and sends once the version shows", async () => {
    const v1 = report(40, 1)
    const v2 = report(41, 2)
    serveDetail(v1)
    const onRefine = vi.fn(async () => {})
    const user = userEvent.setup()

    const { rerender } = render(panel([v1, v2], onRefine))

    await user.click(await screen.findByRole("button", OPEN))
    const field = screen.getByRole("textbox", INSTRUCTION)
    const box = field.closest("form")
    await user.type(field, "Shorter")

    const answer = serveDetailLater(v2, "Body of v2")
    rerender(panel([v1, v2], onRefine, 41))

    expect(box?.isConnected).toBe(true)
    expect((field as HTMLTextAreaElement).value).toBe("Shorter")
    const send = screen.getByRole("button", { name: "Refine" })
    expect(send.hasAttribute("disabled")).toBe(true)

    answer()
    expect(await screen.findByText("Body of v2")).toBeTruthy()
    expect(send.hasAttribute("disabled")).toBe(false)
  })

  it("names the version from the list while its body loads", async () => {
    serveDetailLater(report(41, 2), "Body of v2")

    render(panel([report(40, 1), report(41, 2)], vi.fn(), 41))

    expect(await screen.findAllByText("Quarterly report")).not.toHaveLength(0)
    expect(screen.queryByText("Loading…")).toBeNull()
  })

  it("forgets a refusal when another version opens", async () => {
    const v1 = report(40, 1)
    const v2 = report(41, 2)
    serveDetail(v1)
    const onRefine = vi.fn(async () => {
      throw new Error("This document is too long for the selected model.")
    })
    const user = userEvent.setup()

    const { rerender } = render(panel([v1, v2], onRefine))

    await user.click(await screen.findByRole("button", OPEN))
    await user.type(screen.getByRole("textbox", INSTRUCTION), "Translate it")
    await user.click(screen.getByRole("button", { name: "Refine" }))
    expect(
      await screen.findByText(
        "This document is too long for the selected model."
      )
    ).toBeTruthy()

    serveDetail(v2)
    rerender(panel([v1, v2], onRefine, 41))

    expect(
      screen.queryByText("This document is too long for the selected model.")
    ).toBeNull()
  })

  it("opens from its button with the cursor in the instruction", async () => {
    const v1 = report(40, 1)
    serveDetail(v1)
    const user = userEvent.setup()

    render(
      panel(
        [v1],
        vi.fn(async () => {})
      )
    )

    expect(screen.queryByRole("textbox", INSTRUCTION)).toBeNull()
    await user.click(await screen.findByRole("button", OPEN))

    expect(document.activeElement).toBe(
      screen.getByRole("textbox", INSTRUCTION)
    )
  })

  it("sends the instruction to make the next version, then folds away", async () => {
    const v1 = report(40, 1)
    serveDetail(v1)
    const onRefine = vi.fn(async () => {})
    const user = userEvent.setup()

    render(panel([v1], onRefine))

    await user.click(await screen.findByRole("button", OPEN))
    const button = screen.getByRole("button", { name: "Refine" })
    expect(button.hasAttribute("disabled")).toBe(true)
    await user.type(
      screen.getByRole("textbox", INSTRUCTION),
      "Add a chart of the revenue"
    )
    await user.click(button)

    expect(onRefine).toHaveBeenCalledExactlyOnceWith(
      40,
      "Add a chart of the revenue"
    )
    expect(screen.queryByRole("textbox", INSTRUCTION)).toBeNull()
  })

  it("sends on Enter and keeps Shift+Enter for a new line", async () => {
    const v1 = report(40, 1)
    serveDetail(v1)
    const onRefine = vi.fn(async () => {})
    const user = userEvent.setup()

    render(panel([v1], onRefine))

    await user.click(await screen.findByRole("button", OPEN))
    const box = screen.getByRole("textbox", INSTRUCTION)
    await user.type(box, "Shorter{Shift>}{Enter}{/Shift}Plainer")
    expect(onRefine).not.toHaveBeenCalled()
    await user.type(box, "{Enter}")

    expect(onRefine).toHaveBeenCalledExactlyOnceWith(40, "Shorter\nPlainer")
  })

  it("folds away on Escape and keeps what was typed", async () => {
    const v1 = report(40, 1)
    serveDetail(v1)
    const user = userEvent.setup()

    render(
      panel(
        [v1],
        vi.fn(async () => {})
      )
    )

    await user.click(await screen.findByRole("button", OPEN))
    await user.type(screen.getByRole("textbox", INSTRUCTION), "Shorter")
    await user.keyboard("{Escape}")

    expect(screen.queryByRole("textbox", INSTRUCTION)).toBeNull()
    expect(document.activeElement).toBe(screen.getByRole("button", OPEN))
    await user.click(screen.getByRole("button", OPEN))
    expect(
      (screen.getByRole("textbox", INSTRUCTION) as HTMLTextAreaElement).value
    ).toBe("Shorter")
  })

  it("offers Refine on a PDF Studio wrote as a script too", async () => {
    const v1 = report(40, 1, { format: "pdf", spec_kind: "python" })
    serveDetail(v1)

    render(
      panel(
        [v1],
        vi.fn(async () => {})
      )
    )

    expect(await screen.findByRole("button", OPEN)).toBeTruthy()
  })

  it("holds the instruction to the 2,000 characters the API takes", async () => {
    const v1 = report(40, 1)
    serveDetail(v1)
    const user = userEvent.setup()

    render(panel([v1], vi.fn()))

    await user.click(await screen.findByRole("button", OPEN))
    expect(
      screen.getByRole("textbox", INSTRUCTION).getAttribute("maxlength")
    ).toBe("2000")
  })

  it("shows the version being written in the button’s place, and keeps the open one", async () => {
    const v1 = report(40, 1)
    serveDetail(v1)

    render(panel([v1, report(41, 2, { status: "processing" })], vi.fn()))

    expect(await screen.findByText("Body of the report")).toBeTruthy()
    expect(screen.getByRole("status").textContent).toBe("Making version 2…")
    expect(screen.queryByRole("button", OPEN)).toBeNull()
  })

  it("turns into the version being made and back in place, so it can animate", async () => {
    const v1 = report(40, 1)
    serveDetail(v1)
    const onRefine = vi.fn(async () => {})
    const user = userEvent.setup()

    const { rerender } = render(panel([v1], onRefine))

    await user.click(await screen.findByRole("button", OPEN))
    const box = screen.getByRole("textbox", INSTRUCTION).closest("form")
    await user.type(screen.getByRole("textbox", INSTRUCTION), "Shorter")
    await user.click(screen.getByRole("button", { name: "Refine" }))

    const v2 = report(41, 2)
    rerender(panel([v1, { ...v2, status: "processing" }], onRefine))
    const status = screen.getByRole("status")
    expect(status.textContent).toBe("Making version 2…")
    expect(box?.contains(status)).toBe(true)

    // v1 stays open, so the box is the same one when v2 is ready.
    rerender(panel([v1, v2], onRefine))
    expect(box?.contains(screen.getByRole("button", OPEN))).toBe(true)
    expect(status.textContent).toBe("")
  })

  it("shows why the API refused, and keeps the instruction", async () => {
    const v1 = report(40, 1)
    serveDetail(v1)
    const onRefine = vi.fn(async () => {
      throw new Error("This document is too long for the selected model.")
    })
    const user = userEvent.setup()

    render(panel([v1], onRefine))

    await user.click(await screen.findByRole("button", OPEN))
    const box = screen.getByRole("textbox", INSTRUCTION)
    await user.type(box, "Translate it to French")
    await user.click(screen.getByRole("button", { name: "Refine" }))

    expect(
      await screen.findByText(
        "This document is too long for the selected model."
      )
    ).toBeTruthy()
    expect((box as HTMLTextAreaElement).value).toBe("Translate it to French")
  })

  it("offers no Refine on a summary, or on a document kept without a spec", async () => {
    const summary = report(40, 1, {
      format: "summary",
      spec_kind: null,
      refinable: false,
    })
    serveDetail(summary)

    const { unmount } = render(panel([summary], vi.fn()))
    expect(await screen.findByText("Body of the report")).toBeTruthy()
    expect(screen.queryByRole("button", OPEN)).toBeNull()
    unmount()

    const drafted = report(40, 1, {
      spec_kind: null,
      version: null,
      refinable: false,
    })
    serveDetail(drafted)
    render(panel([drafted], vi.fn()))
    expect(await screen.findByText("Body of the report")).toBeTruthy()
    expect(screen.queryByRole("button", OPEN)).toBeNull()
  })

  it("offers no Refine on a document the agent wrote, which it edits in chat", async () => {
    const script = report(40, 1, { spec_kind: "python", refinable: false })
    serveDetail(script)

    render(panel([script], vi.fn()))

    expect(await screen.findByText("Body of the report")).toBeTruthy()
    expect(screen.queryByRole("button", OPEN)).toBeNull()
  })

  it("offers no Refine until the open version is ready", async () => {
    const failed = report(40, 1, { status: "failed", refinable: false })
    serveDetail(failed)

    render(panel([failed], vi.fn()))

    expect(await screen.findByText("Body of the report")).toBeTruthy()
    expect(screen.queryByRole("button", OPEN)).toBeNull()
  })
})
