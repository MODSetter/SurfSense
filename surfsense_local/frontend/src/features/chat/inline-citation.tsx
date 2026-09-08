import { createContext, useContext, useMemo, type ReactNode } from "react"

import { Button } from "@/components/ui/button"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import type { WorkspaceDocument } from "@/features/sources/api"

import type { Citation } from "./sse"

type CitationContextValue = {
  citationBySourceId: Map<number, Citation>
  titleByDocumentId: Map<number, string>
  onCitation: (citation: Citation) => void
}

const CitationContext = createContext<CitationContextValue | null>(null)

export function CitationProvider({
  citations,
  documents,
  onCitation,
  children,
}: {
  citations: Citation[]
  documents: WorkspaceDocument[]
  onCitation: (citation: Citation) => void
  children: ReactNode
}) {
  const value = useMemo(
    () => ({
      citationBySourceId: new Map(
        citations.map((citation) => [citation.source_id, citation])
      ),
      titleByDocumentId: new Map(
        documents.map((document) => [document.id, document.title])
      ),
      onCitation,
    }),
    [citations, documents, onCitation]
  )

  return (
    <CitationContext.Provider value={value}>
      {children}
    </CitationContext.Provider>
  )
}

export function InlineCitation(props: Record<string, unknown>) {
  const context = useContext(CitationContext)
  const sourceId = Number(props["data-source-id"] ?? props.children)
  const citation = context?.citationBySourceId.get(sourceId)

  if (!context || !citation) {
    return null
  }

  const title =
    context.titleByDocumentId.get(citation.document_id) ??
    `Document ${citation.document_id}`

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="xs"
          className="mx-0.5 inline-flex h-5 min-w-5 rounded-md bg-popover px-1.5 align-baseline text-[11px] text-popover-foreground hover:bg-popover hover:text-popover-foreground"
          aria-label={`Open source ${sourceId}: ${title}`}
          onClick={() => context.onCitation(citation)}
        >
          {sourceId}
        </Button>
      </TooltipTrigger>
      <TooltipContent>{title}</TooltipContent>
    </Tooltip>
  )
}
