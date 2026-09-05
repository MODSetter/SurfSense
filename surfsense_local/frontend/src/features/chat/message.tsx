import { FileTextIcon } from "lucide-react"
import { MessagePrimitive } from "@assistant-ui/react"

import { Button } from "@/components/ui/button"
import type { WorkspaceDocument } from "@/features/sources/api"

import type { Citation } from "./sse"

function CitationLinks({
  citations,
  documents,
  onCitation,
}: {
  citations: Citation[]
  documents: WorkspaceDocument[]
  onCitation: (citation: Citation) => void
}) {
  if (citations.length === 0) {
    return null
  }
  const titleById = new Map(
    documents.map((document) => [document.id, document.title])
  )
  return (
    <div className="mt-3 flex flex-wrap gap-1.5" aria-label="Citations">
      {citations.map((citation, index) => {
        const title =
          titleById.get(citation.document_id) ??
          `Document ${citation.document_id}`
        return (
          <Button
            key={`${citation.chunk_id}-${index}`}
            variant="outline"
            size="xs"
            aria-label={`Source ${index + 1}: ${title}`}
            onClick={() => onCitation(citation)}
          >
            <FileTextIcon />
            {index + 1}
          </Button>
        )
      })}
    </div>
  )
}

export function UserMessage() {
  return (
    <MessagePrimitive.Root className="mx-auto flex w-full max-w-3xl justify-end px-6 py-3">
      <div className="max-w-[78%] rounded-2xl rounded-br-md bg-primary px-4 py-2.5 text-sm leading-6 whitespace-pre-wrap text-primary-foreground">
        <MessagePrimitive.Parts />
      </div>
    </MessagePrimitive.Root>
  )
}

export function AssistantMessage({
  citations,
  documents,
  onCitation,
}: {
  citations: Citation[]
  documents: WorkspaceDocument[]
  onCitation: (citation: Citation) => void
}) {
  return (
    <MessagePrimitive.Root className="mx-auto w-full max-w-3xl px-6 py-4">
      <div className="text-sm leading-7 whitespace-pre-wrap">
        <MessagePrimitive.Parts />
      </div>
      <CitationLinks
        citations={citations}
        documents={documents}
        onCitation={onCitation}
      />
    </MessagePrimitive.Root>
  )
}
