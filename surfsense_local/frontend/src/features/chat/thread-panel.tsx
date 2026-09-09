import { useEffect, useRef, type ReactNode } from "react"
import { BotIcon, Settings2Icon } from "@/components/ui/icons"

import {
  AssistantRuntimeProvider,
  ThreadPrimitive,
  type AssistantRuntime,
  useAui,
} from "@assistant-ui/react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { TypewriterText } from "@/components/typewriter-text"
import type { ModelSelection } from "@/features/model-selection/api"
import type { WorkspaceDocument } from "@/features/sources/api"

import type { ChatThread } from "./api"
import { ChatComposer } from "./chat-composer"
import { ChatViewport } from "./chat-viewport"
import { AssistantMessage, UserMessage } from "./message"
import type { Citation } from "./sse"
import type { ConversationView } from "./use-chat-runtime"

function citationsFrom(message: {
  metadata?: { custom?: unknown }
}): Citation[] {
  const custom = message.metadata?.custom
  if (
    typeof custom === "object" &&
    custom !== null &&
    "citations" in custom &&
    Array.isArray(custom.citations)
  ) {
    return custom.citations as Citation[]
  }
  return []
}

function ThreadWelcome({ composer }: { composer: ReactNode }) {
  return (
    <div className="flex min-h-0 flex-1">
      <div className="mx-auto grid h-full w-full max-w-2xl grid-rows-[minmax(0,1fr)_auto_minmax(0,1fr)]">
        <div />
        {composer}
      </div>
    </div>
  )
}

function ComposerDraftLifecycle({ view }: { view: ConversationView }) {
  const aui = useAui()
  const conversationId =
    view.status === "active" ? `thread:${view.threadId}` : view.status

  useEffect(() => {
    if (conversationId === "initializing" || conversationId === "creating") {
      return
    }
    void aui.thread.composer().reset()
  }, [aui, conversationId])

  return null
}

export function ThreadPanel({
  runtime,
  thread,
  view,
  model,
  documents,
  error,
  isLoading,
  isRunning,
  isUploading,
  animateTitle,
  providerAvailable,
  onCitation,
  onModelSetup,
  onModelSelected,
  onUpload,
  onTitleAnimationComplete,
}: {
  runtime: AssistantRuntime
  thread: ChatThread | null
  view: ConversationView
  model: ModelSelection
  documents: WorkspaceDocument[]
  error: string | null
  isLoading: boolean
  isRunning: boolean
  isUploading: boolean
  animateTitle: boolean
  providerAvailable: boolean
  onCitation: (citation: Citation) => void
  onModelSetup: () => void
  onModelSelected: (selection: ModelSelection) => void
  onUpload: (files: File[]) => void
  onTitleAnimationComplete: () => void
}) {
  const headingRef = useRef<HTMLHeadingElement>(null)
  const threadId = thread?.id
  const title =
    view.status === "initializing" ? null : thread?.title || "New chat"
  const bottomComposer = view.status === "creating" || view.status === "active"
  const composer = (placement: "center" | "bottom") => (
    <ChatComposer
      placement={placement}
      model={model}
      isRunning={isRunning}
      isUploading={isUploading}
      providerAvailable={providerAvailable}
      onModelSetup={onModelSetup}
      onModelSelected={onModelSelected}
      onUpload={onUpload}
    />
  )

  useEffect(() => {
    if (threadId !== undefined) {
      headingRef.current?.focus()
    }
  }, [threadId])

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <ComposerDraftLifecycle view={view} />
      <section
        className="flex h-full min-w-0 flex-col bg-background"
        aria-label="Conversation"
      >
        <header className="flex h-14 shrink-0 items-center border-b px-5">
          <h1
            ref={headingRef}
            tabIndex={-1}
            className="min-w-0 truncate font-heading text-lg font-medium outline-none"
          >
            {title === null ? (
              <Skeleton className="h-5 w-32" />
            ) : (
              <TypewriterText
                text={title}
                animate={animateTitle}
                onComplete={onTitleAnimationComplete}
              />
            )}
          </h1>
        </header>

        {error ? (
          <Alert variant="destructive" className="m-4 mb-0 w-auto">
            <BotIcon />
            <AlertTitle>Chat could not continue</AlertTitle>
            <AlertDescription className="flex items-center justify-between gap-4">
              <span>{error}</span>
              <Button variant="outline" size="sm" onClick={onModelSetup}>
                <Settings2Icon />
                Model setup
              </Button>
            </AlertDescription>
          </Alert>
        ) : null}

        <ThreadPrimitive.Root className="relative flex min-h-0 flex-1 flex-col">
          <ChatViewport
            footer={bottomComposer ? composer("bottom") : undefined}
          >
            {view.status === "initializing" || isLoading ? (
              <div className="mx-auto w-full max-w-2xl space-y-4 p-6">
                <Skeleton className="ml-auto h-16 w-2/3" />
                <Skeleton className="h-24 w-4/5" />
              </div>
            ) : null}

            {view.status === "new" ? (
              <ThreadWelcome composer={composer("center")} />
            ) : null}

            {view.status === "active" && !isLoading ? (
              <ThreadPrimitive.Messages>
                {({ message }) =>
                  message.role === "user" ? (
                    <UserMessage />
                  ) : (
                    <AssistantMessage
                      citations={citationsFrom(message)}
                      documents={documents}
                      onCitation={onCitation}
                    />
                  )
                }
              </ThreadPrimitive.Messages>
            ) : null}
          </ChatViewport>
        </ThreadPrimitive.Root>
      </section>
    </AssistantRuntimeProvider>
  )
}
