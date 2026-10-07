import { CheckIcon, CopyIcon, DownloadIcon } from "@/components/ui/icons"
import {
  ActionBarPrimitive,
  AuiIf,
  MessagePrimitive,
  useAuiState,
} from "@assistant-ui/react"
import { StreamdownTextPrimitive } from "@assistant-ui/react-streamdown"
import { useCallback, type ComponentType } from "react"
import type { Components, ExtraProps } from "streamdown"

import { RelativeTime } from "@/components/relative-time"
import { AgentSteps } from "@/features/agent/agent-steps"
import type { AgentStep, TurnSources } from "@/features/agent/api"
import { WorkingFrom } from "@/features/agent/working-from"
import { OfficeOfferBanner } from "@/features/office-support/office-offer-banner"
import { useOfficeOffer } from "@/features/office-support/office-offer"
import {
  STREAMDOWN_LINK_SAFETY,
  streamdownPlugins,
  streamingStreamdownPlugins,
} from "@/features/studio/viewers/streamdown-config"
import { Button } from "@/components/ui/button"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"
import { intl } from "@/i18n/intl"

import { MessageImage } from "./attached-image"
import { ChatErrorNotice } from "./chat-error-notice"
import { preprocessCitationMarkdown } from "./citation-markdown"
import { useCitationContext } from "./citation-context"
import { CitationProvider, InlineCitation } from "./inline-citation"
import { ReplyAnnouncer } from "./reply-announcer"
import {
  ReplyThinking,
  type ReplyProgress,
  type ReplyReasoning,
} from "./reply-thinking"
import type { Citation } from "./sse"

const streamdownIcons = { CheckIcon, CopyIcon, DownloadIcon }
const citationComponents: Components = {
  citation: InlineCitation as ComponentType<
    Record<string, unknown> & ExtraProps
  >,
}
const citationAllowedTags = {
  citation: ["data-chunk-id"],
}
// Every prop below keeps its identity between renders: a new security object
// rebuilds the rehype plugins, and then every block of the reply is parsed
// again on every token instead of the one block that changed.
const markdownSecurity = {
  allowedProtocols: ["http", "https", "mailto"],
  allowedImagePrefixes: [],
  allowDataImages: false,
}
const NO_CITATIONS: Citation[] = []

function MarkdownText() {
  const citations = useCitationContext()?.citations ?? NO_CITATIONS
  const running = useAuiState(
    ({ message }) => message.status?.type === "running"
  )
  const preprocess = useCallback(
    (content: string) => preprocessCitationMarkdown(content, citations),
    [citations]
  )
  return (
    <StreamdownTextPrimitive
      defer
      allowedTags={citationAllowedTags}
      components={citationComponents}
      icons={streamdownIcons}
      plugins={running ? streamingStreamdownPlugins : streamdownPlugins}
      preprocess={preprocess}
      linkSafety={STREAMDOWN_LINK_SAFETY}
      security={markdownSecurity}
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

function progressFrom(custom: unknown): ReplyProgress | null {
  if (typeof custom === "object" && custom !== null && "progress" in custom) {
    return (custom.progress as ReplyProgress | null) ?? null
  }
  return null
}

function queueFrom(custom: unknown): { position: number } | null {
  if (typeof custom === "object" && custom !== null && "queue" in custom) {
    return (custom.queue as { position: number } | null) ?? null
  }
  return null
}

function preparingFrom(custom: unknown): number | null {
  if (typeof custom === "object" && custom !== null && "preparing" in custom) {
    return (custom.preparing as number | null) ?? null
  }
  return null
}

function MessageThinking() {
  const messageId = useAuiState(({ message }) => message.id)
  const completed = useAuiState(
    ({ message }) => message.status?.type === "complete"
  )
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
  const progress = useAuiState(({ message }) =>
    progressFrom(message.metadata.custom)
  )
  const queue = useAuiState(({ message }) => queueFrom(message.metadata.custom))
  const preparing = useAuiState(({ message }) =>
    preparingFrom(message.metadata.custom)
  )

  return (
    <>
      {/* Keyed by message: messages render by index, so an instance would
          otherwise watch one thread's reply and announce another's. */}
      <ReplyAnnouncer
        key={messageId}
        running={running}
        answerStarted={answerStarted}
        completed={completed}
      />
      <ReplyThinking
        running={running}
        answerStarted={answerStarted}
        reasoning={reasoning}
        progress={progress}
        queue={queue}
        preparing={preparing}
      />
    </>
  )
}

function stepsFrom(custom: unknown): AgentStep[] {
  if (
    typeof custom === "object" &&
    custom !== null &&
    "steps" in custom &&
    Array.isArray(custom.steps)
  ) {
    return custom.steps as AgentStep[]
  }
  return []
}

function MessageSteps() {
  const steps = useAuiState(({ message }) => stepsFrom(message.metadata.custom))
  // The turn's sources are kept on the user's message this reply answers.
  const scope = useAuiState(({ thread, message }) => {
    const asked = thread.messages
      .slice(0, message.index)
      .findLast((candidate) => candidate.role === "user")
    return asked ? scopeFrom(asked.metadata.custom) : null
  })
  return <AgentSteps steps={steps} scope={scope} />
}

/** The offer shows once per thread: under the latest reply that made an Office file. */
function MessageOfficeOffer() {
  const offer = useOfficeOffer()
  const shown = useAuiState(({ thread, message }) => {
    if (!offer) return false
    const madeOffice = (custom: unknown) =>
      stepsFrom(custom).some(
        (step) => step.artifact != null && offer.isOfficeFile(step.artifact.id)
      )
    const latest = thread.messages.findLast(
      (candidate) =>
        candidate.role === "assistant" && madeOffice(candidate.metadata.custom)
    )
    return latest?.id === message.id
  })
  return shown ? <OfficeOfferBanner /> : null
}

function scopeFrom(custom: unknown): TurnSources | null {
  if (typeof custom === "object" && custom !== null && "scope" in custom) {
    return (custom.scope as TurnSources | null) ?? null
  }
  return null
}

function MessageScope() {
  const scope = useAuiState(({ message }) => scopeFrom(message.metadata.custom))
  return <WorkingFrom scope={scope} />
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
            <TooltipTrigger
              render={
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
              }
            />
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
      <div className="mb-2 flex max-w-[78%] flex-wrap justify-end gap-2 empty:hidden">
        <MessagePrimitive.Attachments
          components={{ Image: MessageImage, Attachment: MessageImage }}
        />
      </div>
      <div className="max-w-[78%] rounded-2xl rounded-br-md bg-primary px-4 py-2.5 text-sm leading-6 whitespace-pre-wrap text-primary-foreground">
        <MessagePrimitive.Parts />
      </div>
      <div className="mt-1.5 flex w-full justify-end empty:hidden">
        <MessageScope />
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
  onNewChat,
}: {
  citations: Citation[]
  onCitation: (chunkId: number) => void
  onModelSetup: () => void
  onRetry: (assistantId: string) => void
  onNewChat: () => void
}) {
  return (
    <MessagePrimitive.Root className="mx-auto flex w-full max-w-xl min-w-0 flex-col items-start px-6 py-4">
      <CitationProvider citations={citations} onCitation={onCitation}>
        <div className="w-full max-w-full min-w-0 text-sm leading-7">
          <MessageThinking />
          <MessageSteps />
          <MessagePrimitive.Parts components={assistantMessageParts} />
          <MessageOfficeOffer />
        </div>
      </CitationProvider>
      <ChatErrorNotice
        onModelSetup={onModelSetup}
        onRetry={onRetry}
        onNewChat={onNewChat}
      />
      <MessageActions hideWhenRunning timestampRight className="top-0.5" />
    </MessagePrimitive.Root>
  )
}
