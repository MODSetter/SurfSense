import {
  CheckIcon,
  CopyIcon,
  DownloadIcon,
  FileTextIcon,
} from "@/components/ui/icons"
import {
  ActionBarPrimitive,
  AuiIf,
  MessagePrimitive,
  useAuiState,
} from "@assistant-ui/react"
import { StreamdownTextPrimitive } from "@assistant-ui/react-streamdown"
import { code } from "@streamdown/code"
import { createMathPlugin } from "@streamdown/math"

import { RelativeTime } from "@/components/relative-time"
import { Button } from "@/components/ui/button"
import type { WorkspaceDocument } from "@/features/sources/api"
import { cn } from "@/lib/utils"

import type { Citation } from "./sse"

const streamdownPlugins = {
  code,
  math: createMathPlugin({ singleDollarTextMath: true }),
}
const streamdownIcons = { CheckIcon, CopyIcon, DownloadIcon }

function MarkdownText() {
  return (
    <StreamdownTextPrimitive
      defer
      icons={streamdownIcons}
      plugins={streamdownPlugins}
      linkSafety={{ enabled: true }}
      security={{
        allowedProtocols: ["http", "https", "mailto"],
        allowedImagePrefixes: [],
        allowDataImages: false,
      }}
    />
  )
}

const assistantMessageParts = { Text: MarkdownText }

function MessageTimestamp() {
  const createdAt = useAuiState(({ message }) => message.createdAt)

  if (!createdAt) {
    return null
  }

  return <RelativeTime date={createdAt} />
}

function MessageActions({
  hideWhenRunning = false,
  timestampRight = false,
  className,
}: {
  hideWhenRunning?: boolean
  timestampRight?: boolean
  className?: string
}) {
  const timestamp = <MessageTimestamp />
  return (
    <div
      className={cn(
        "relative flex h-7 items-center gap-2 text-muted-foreground",
        className
      )}
    >
      {timestampRight ? null : timestamp}
      <ActionBarPrimitive.Root hideWhenRunning={hideWhenRunning}>
        <ActionBarPrimitive.Copy copiedDuration={2_000} asChild>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label="Copy message"
            title="Copy message"
          >
            <AuiIf condition={({ message }) => message.isCopied}>
              <CheckIcon />
            </AuiIf>
            <AuiIf condition={({ message }) => !message.isCopied}>
              <CopyIcon />
            </AuiIf>
          </Button>
        </ActionBarPrimitive.Copy>
      </ActionBarPrimitive.Root>
      {timestampRight ? timestamp : null}
    </div>
  )
}

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
    <ul className="mt-3 flex flex-wrap gap-1.5" aria-label="Citations">
      {citations.map((citation, index) => {
        const title =
          titleById.get(citation.document_id) ??
          `Document ${citation.document_id}`
        return (
          <li key={citation.chunk_id}>
            <Button
              variant="outline"
              size="xs"
              aria-label={`Source ${index + 1}: ${title}`}
              onClick={() => onCitation(citation)}
            >
              <FileTextIcon />
              {index + 1}
            </Button>
          </li>
        )
      })}
    </ul>
  )
}

export function UserMessage() {
  return (
    <MessagePrimitive.Root className="mx-auto flex w-full max-w-xl flex-col items-end px-6 py-3">
      <div className="max-w-[78%] rounded-2xl rounded-br-md bg-primary px-4 py-2.5 text-sm leading-6 whitespace-pre-wrap text-primary-foreground">
        <MessagePrimitive.Parts />
      </div>
      <MessageActions className="top-1" />
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
    <MessagePrimitive.Root className="mx-auto flex w-full max-w-xl min-w-0 flex-col items-start px-6 py-4">
      <div className="w-full max-w-full min-w-0 text-sm leading-7">
        <MessagePrimitive.Parts components={assistantMessageParts} />
      </div>
      <CitationLinks
        citations={citations}
        documents={documents}
        onCitation={onCitation}
      />
      <MessageActions hideWhenRunning timestampRight className="top-0.5" />
    </MessagePrimitive.Root>
  )
}
