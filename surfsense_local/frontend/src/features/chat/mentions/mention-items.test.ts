import { describe, expect, it } from "vitest"

import type { WorkspaceDocument } from "@/features/sources/api"
import type { SourceFolder } from "@/features/sources/tree/folders-api"
import { indexSources } from "@/features/sources/tree/source-index"
import type { Artifact } from "@/features/studio/api"

import { mentionItems, mentionsOfGroup, searchMentions } from "./mention-items"

function folder(id: number, name: string, parent_id: number | null = 1) {
  return { id, name, parent_id } as SourceFolder
}

function source(id: number, title: string, extra = {}) {
  return {
    id,
    title,
    document_type: "FILE",
    mime_type: null,
    status: "ready",
    folder_id: 1,
    ...extra,
  } as WorkspaceDocument
}

function artifact(id: number, title: string, extra = {}) {
  return {
    id,
    document_id: id + 100,
    format: "pptx",
    title,
    status: "ready",
    version: null,
    ...extra,
  } as Artifact
}

function items(
  documents: WorkspaceDocument[],
  folders: SourceFolder[] = [folder(1, "Library", null)],
  artifacts: Artifact[] = []
) {
  return mentionItems({
    documents,
    index: indexSources(folders, documents),
    artifacts,
  })
}

describe("what `@` can name", () => {
  it("lists ready sources with their folder, and folders with what they hold", () => {
    const listed = items(
      [source(3, "Plan.pdf", { folder_id: 2 }), source(4, "Notes")],
      [folder(1, "Library", null), folder(2, "Contracts")]
    )

    expect(
      listed.map(({ id, type, label, description }) => ({
        id,
        type,
        label,
        description,
      }))
    ).toEqual([
      {
        id: "folder:2",
        type: "source",
        label: "Contracts",
        description: "1 file",
      },
      {
        id: "document:3",
        type: "source",
        label: "Plan.pdf",
        description: "Contracts",
      },
      {
        id: "document:4",
        type: "source",
        label: "Notes",
        description: undefined,
      },
    ])
  })

  it("leaves out a source not ready and a folder with nothing ready", () => {
    const listed = items(
      [source(3, "Reading", { folder_id: 2, status: "processing" })],
      [folder(1, "Library", null), folder(2, "Contracts")]
    )

    expect(listed).toEqual([])
  })

  it("names a document once, by its newest ready version's document", () => {
    const version = (number: number) => ({ root_id: 1, number })
    const listed = items([], undefined, [
      artifact(1, "Deck", { version: version(1) }),
      artifact(2, "Deck", { version: version(2) }),
      artifact(3, "Deck", { version: version(3), status: "failed" }),
    ])

    expect(
      listed.map((item) => [item.id, item.type, item.description])
    ).toEqual([["document:102", "artifact-pptx", "Slides"]])
  })

  it("leaves out an artifact with no ready version", () => {
    expect(
      items([], undefined, [artifact(1, "Deck", { status: "processing" })])
    ).toEqual([])
  })
})

describe("searching what `@` can name", () => {
  it("matches a name anywhere, a name that starts with the words first", () => {
    const found = searchMentions(
      items([source(2, "Old plan"), source(3, "Plan B"), source(4, "Memo")]),
      "PLAN"
    )

    expect(found.map((item) => item.label)).toEqual(["Plan B", "Old plan"])
  })

  it("keeps sources before artifacts", () => {
    const found = searchMentions(
      items([source(2, "Old plan")], undefined, [artifact(1, "Plan deck")]),
      "plan"
    )

    expect(found.map((item) => item.type)).toEqual(["source", "artifact-pptx"])
  })

  it("finds every match, however many, for the list to load as it scrolls", () => {
    const found = searchMentions(
      items(
        Array.from({ length: 100 }, (_, n) => source(n + 2, `Report ${n}`))
      ),
      "report"
    )

    expect(found).toHaveLength(100)
  })
})

describe("one group of what `@` can name", () => {
  it("holds folders first, then files newest first, and all of them", () => {
    const listed = items(
      Array.from({ length: 40 }, (_, n) =>
        source(n + 3, `Report ${n}`, { folder_id: 2 })
      ),
      [folder(1, "Library", null), folder(2, "Contracts")],
      [artifact(1, "Deck")]
    )

    const sources = mentionsOfGroup(listed, "source")

    expect(sources).toHaveLength(41)
    expect(sources[0]?.id).toBe("folder:2")
    expect(sources[1]?.label).toBe("Report 0")
    expect(mentionsOfGroup(listed, "artifact").map((i) => i.label)).toEqual([
      "Deck",
    ])
  })
})
