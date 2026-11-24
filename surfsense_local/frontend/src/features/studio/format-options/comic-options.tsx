import { useState } from "react"

import { type ComicKind, startingPages } from "./comic-kinds"
import { ComicOptionsForm } from "./comic-options-form"
import type { FormatOptions } from "./format-options"

/** A comic starts as a four-page Western comic; a new kind starts at its own length. */
export function useComicOptions(format: string): FormatOptions | null {
  const [kind, setKind] = useState<ComicKind>("western")
  const [pages, setPages] = useState(startingPages("western"))
  if (format !== "comic") return null

  return {
    panel: (
      <ComicOptionsForm
        kind={kind}
        pages={pages}
        onKindChange={(next) => {
          setKind(next)
          setPages(startingPages(next))
        }}
        onPagesChange={setPages}
      />
    ),
    job: { format, options: { kind, pages } },
    ready: true,
  }
}
