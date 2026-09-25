import { CheckIcon, CopyIcon, DownloadIcon } from "@/components/ui/icons"
import {
  ActionBarPrimitive,
  AuiIf,
  MessagePrimitive,
  useAuiState,
} from "@assistant-ui/react"
import { StreamdownTextPrimitive } from "@assistant-ui/react-streamdown"
import { code } from "@streamdown/code"
import { createMathPlugin } from "@streamdown/math"
import type { ComponentType } from "react"
import type { Components, ExtraProps } from "streamdown"

import { RelativeTime } from "@/components/relative-time"
import { Button } from "@/components/ui/button"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"
import { intl } from "@/i18n/intl"

import { ChatErrorNotice } from "./chat-error-notice"
import { preprocessCitationMarkdown } from "./citation-markdown"
import { useCitationContext } from "./citation-context"
import { CitationProvider, InlineCitation } from "./inline-citation"
import { ReplyThinking, type ReplyReasoning } from "./reply-thinking"
import type { Citation } from "./sse"

const streamdownPlugins = {
  code,
  math: createMathPlugin({ singleDollarTextMath: true }),
}
const streamdownIcons = { CheckIcon, CopyIcon, DownloadIcon }
const citationComponents: Components = {
  citation: InlineCitation as ComponentType<
    Record<string, unknown> & ExtraProps
  >,
}
const citationAllowedTags = {
  citation: ["data-chunk-id"],
}

function MarkdownText() {
  const citations = useCitationContext()?.citations ?? []
  return (
    <StreamdownTextPrimitive
      defer
      allowedTags={citationAllowedTags}
      components={citationComponents}
      icons={streamdownIcons}
      plugins={streamdownPlugins}
      preprocess={(content) => preprocessCitationMarkdown(content, citations)}
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

function reasoningFrom(custom: unknown): ReplyReasoning | null {
  if (typeof custom === "object" && custom !== null && "reasoning" in custom) {
    return (custom.reasoning as ReplyReasoning | null) ?? null
  }
  return null
}

function MessageThinking() {
  const running = useAuiState(
    ({ message }) => message.status?.type === "running"
  )
  const answerStarted = useAuiState(({ message }) =>
    message.content.some(
      (part) => part.type === "text" && part.text.trim().length > 0
    )
  )
  const reasoning = useAuiState(({ message }) =>
    reasoningFrom(message.metadata.custom)
  )

  return (
    <ReplyThinking
      running={running}
      answerStarted={answerStarted}
      reasoning={reasoning}
    />
  )
}

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
  const isCopied = useAuiState(({ message }) => message.isCopied)
  const isRunning = useAuiState(
    ({ message }) => message.status?.type === "running"
  )
  const hasText = useAuiState(({ message }) =>
    message.content.some(
      (part) => part.type === "text" && part.text.trim().length > 0
    )
  )

  if (hideWhenRunning && (isRunning || !hasText)) {
    return null
  }

  return (
    <div
      className={cn(
        "relative flex h-7 items-center gap-2 text-muted-foreground select-none",
        className
      )}
    >
      {timestampRight ? null : timestamp}
      <ActionBarPrimitive.Root hideWhenRunning={hideWhenRunning}>
        <Tooltip>
          <ActionBarPrimitive.Copy copiedDuration={2_000} asChild>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                aria-label={
                  isCopied
                    ? intl.formatMessage({
                        id: "chat_message_copied_aria",
                        defaultMessage: "Copied",
                      })
                    : intl.formatMessage({
                        id: "chat_message_copy_aria",
                        defaultMessage: "Copy message",
                      })
                }
              >
                <AuiIf condition={({ message }) => message.isCopied}>
                  <CheckIcon />
                </AuiIf>
                <AuiIf condition={({ message }) => !message.isCopied}>
                  <CopyIcon />
                </AuiIf>
              </Button>
            </TooltipTrigger>
          </ActionBarPrimitive.Copy>
          <TooltipContent>
            {isCopied
              ? intl.formatMessage({
                  id: "chat_message_copied_tooltip",
                  defaultMessage: "Copied",
                })
              : intl.formatMessage({
                  id: "chat_message_copy_tooltip",
                  defaultMessage: "Copy",
                })}
          </TooltipContent>
        </Tooltip>
      </ActionBarPrimitive.Root>
      {timestampRight ? timestamp : null}
    </div>
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
  onCitation,
  onModelSetup,
  onRetry,
}: {
  citations: Citation[]
  onCitation: (chunkId: number) => void
  onModelSetup: () => void
  onRetry: (assistantId: string) => void
}) {
  return (
    <MessagePrimitive.Root className="mx-auto flex w-full max-w-xl min-w-0 flex-col items-start px-6 py-4">
      <CitationProvider citations={citations} onCitation={onCitation}>
        <div className="w-full max-w-full min-w-0 text-sm leading-7">
          <MessageThinking />
          <MessagePrimitive.Parts components={assistantMessageParts} />
        </div>
      </CitationProvider>
      <ChatErrorNotice onModelSetup={onModelSetup} onRetry={onRetry} />
      <MessageActions hideWhenRunning timestampRight className="top-0.5" />
    </MessagePrimitive.Root>
  )
}
