import { createContext, useContext, useMemo, type ReactNode } from "react"

import { Button } from "@/components/ui/button"
import type { Citation } from "./sse"

type CitationContextValue = {
  citations: Citation[]
  onCitation: (chunkId: number) => void
}

const CitationContext = createContext<CitationContextValue | null>(null)

export function useCitationContext() {
  return useContext(CitationContext)
}

export function CitationProvider({
  citations,
  onCitation,
  children,
}: {
  citations: Citation[]
  onCitation: (chunkId: number) => void
  children: ReactNode
}) {
  const value = useMemo(
    () => ({ citations, onCitation }),
    [citations, onCitation]
  )

  return (
    <CitationContext.Provider value={value}>{children}</CitationContext.Provider>
  )
}

export function InlineCitation(props: Record<string, unknown>) {
  const context = useContext(CitationContext)
  const chunkId = Number(props["data-chunk-id"] ?? props.children)

  if (!context || !Number.isFinite(chunkId) || chunkId <= 0) {
    return null
  }

  return (
    <Button
      type="button"
      variant="ghost"
      size="xs"
      className="mx-0.5 inline-flex h-5 min-w-5 rounded-md bg-popover px-1.5 align-baseline text-[11px] font-medium text-popover-foreground/80 hover:bg-popover hover:text-popover-foreground"
      title={`View source chunk #${chunkId}`}
      aria-label={`View cited chunk ${chunkId}`}
      onClick={() => context.onCitation(chunkId)}
    >
      {chunkId}
    </Button>
  )
}
