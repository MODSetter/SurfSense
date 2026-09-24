import { createContext, useContext } from "react"

import type { Citation } from "./sse"

export type CitationContextValue = {
  citations: Citation[]
  onCitation: (chunkId: number) => void
}

export const CitationContext = createContext<CitationContextValue | null>(null)

export function useCitationContext() {
  return useContext(CitationContext)
}
