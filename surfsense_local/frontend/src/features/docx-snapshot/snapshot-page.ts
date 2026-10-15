import { drawn } from "./drawn"

// What each format is called in a reason, and the module that lays it out,
// loaded on demand so a print parses only its own format's library.
const FORMATS = {
  docx: {
    name: "Word file",
    layOut: async (file: ArrayBuffer, page: Document) =>
      (await import("./lay-out-word")).layOutWord(file, page),
  },
  pptx: {
    name: "PowerPoint file",
    layOut: async (file: ArrayBuffer, page: Document) =>
      (await import("./lay-out-deck")).layOutDeck(file, page),
  },
} as const

/**
 * Lay out the file named by `?file=` for Electron to print to PDF: a Word file
 * as its pages, or with `?format=pptx` a deck as one slide per page.
 *
 * Resolves to null once the pages, their images and fonts are in place, or to
 * the reason it could not, in English for the agent: Electron cannot read a
 * rejected promise's message from a page.
 */
export async function layOutSnapshot(
  search: string,
  page: Document
): Promise<string | null> {
  const params = new URLSearchParams(search)
  const fileUrl = params.get("file")
  if (!fileUrl) return "the snapshot page was opened without a file to lay out"
  const formatName = params.get("format") ?? "docx"
  if (!Object.hasOwn(FORMATS, formatName)) {
    return `the snapshot page cannot lay out a ${formatName} file`
  }
  const format = FORMATS[formatName as keyof typeof FORMATS]

  let response: Response
  try {
    response = await fetch(fileUrl)
  } catch (error) {
    return `the ${format.name} could not be fetched: ${messageOf(error)}`
  }
  if (!response.ok) {
    return `the ${format.name} could not be fetched (HTTP ${response.status})`
  }
  try {
    await format.layOut(await response.arrayBuffer(), page)
  } catch (error) {
    return `the ${format.name} could not be laid out: ${messageOf(error)}`
  }

  await Promise.all([...page.images].map(drawn))
  await page.fonts?.ready
  return null
}

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}
