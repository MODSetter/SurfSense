import { useEffect, useRef } from "react"
import {
  ArrowDownIcon,
  ArrowUp02Icon,
  BotIcon,
  ChevronDownIcon,
  CircleStopIcon,
  Settings2Icon,
} from "@/components/ui/icons"

import {
  AssistantRuntimeProvider,
  ComposerPrimitive,
  ThreadPrimitive,
  type AssistantRuntime,
} from "@assistant-ui/react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import type { ModelSelection } from "@/features/model-selection/api"
import type { WorkspaceDocument } from "@/features/sources/api"
import { cn } from "@/lib/utils"

import type { ChatThread } from "./api"
import { AssistantMessage, UserMessage } from "./message"
import type { Citation } from "./sse"

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

export function ThreadPanel({
  runtime,
  thread,
  model,
  documents,
  error,
  isLoading,
  isRunning,
  providerAvailable,
  onCitation,
  onModelSetup,
}: {
  runtime: AssistantRuntime
  thread: ChatThread | null
  model: ModelSelection
  documents: WorkspaceDocument[]
  error: string | null
  isLoading: boolean
  isRunning: boolean
  providerAvailable: boolean
  onCitation: (citation: Citation) => void
  onModelSetup: () => void
}) {
  const headingRef = useRef<HTMLHeadingElement>(null)

  useEffect(() => {
    if (thread) {
      headingRef.current?.focus()
    }
  }, [thread])

  return (
    <AssistantRuntimeProvider runtime={runtime}>
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
            {thread?.title || "New chat"}
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
          <ThreadPrimitive.Viewport
            className="flex min-h-0 flex-1 flex-col overflow-y-auto"
            autoScroll
          >
            {isLoading ? (
              <div className="mx-auto w-full max-w-3xl space-y-4 p-6">
                <Skeleton className="ml-auto h-16 w-2/3" />
                <Skeleton className="h-24 w-4/5" />
              </div>
            ) : null}

            {!isLoading ? (
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

            <ThreadPrimitive.ViewportFooter
              className={cn(
                "absolute inset-x-0 z-20 px-4",
                thread
                  ? "bottom-0 bg-gradient-to-t from-background via-background to-transparent pt-7 pb-2"
                  : "top-1/2 -translate-y-1/2"
              )}
            >
              <div className="relative mx-auto max-w-3xl">
                {thread ? (
                  <ThreadPrimitive.ScrollToBottom asChild>
                    <Button
                      variant="outline"
                      size="icon-sm"
                      className="absolute -top-8 left-1/2 -translate-x-1/2 rounded-full bg-background disabled:invisible"
                      aria-label="Scroll to latest message"
                    >
                      <ArrowDownIcon />
                    </Button>
                  </ThreadPrimitive.ScrollToBottom>
                ) : null}
                <ComposerPrimitive.Root className="flex items-end gap-2 rounded-2xl border bg-card p-1.5 shadow-sm focus-within:ring-2 focus-within:ring-ring/20">
                  <ComposerPrimitive.Input
                    className={cn(
                      "max-h-44 flex-1 resize-none bg-transparent px-2 py-2.5 text-sm outline-none placeholder:text-muted-foreground",
                      thread ? "min-h-10" : "min-h-28"
                    )}
                    placeholder={
                      providerAvailable
                        ? "Ask SurfSense about anything"
                        : "Reconnect your model provider to send"
                    }
                    submitMode="enter"
                    rows={1}
                    aria-label="Message"
                  />
                  {!isRunning ? (
                    <ComposerPrimitive.Send asChild>
                      <Button
                        size="icon-lg"
                        className="mb-0.5 rounded-xl"
                        aria-label="Send message"
                      >
                        <ArrowUp02Icon />
                      </Button>
                    </ComposerPrimitive.Send>
                  ) : (
                    <ComposerPrimitive.Cancel asChild>
                      <Button
                        size="icon-lg"
                        variant="secondary"
                        className="mb-0.5 rounded-xl"
                        aria-label="Stop generating"
                      >
                        <CircleStopIcon />
                      </Button>
                    </ComposerPrimitive.Cancel>
                  )}
                </ComposerPrimitive.Root>
                <div className="mt-1 flex min-h-7 items-center justify-between gap-3 px-2">
                  <p className="min-w-0 text-left text-[11px] text-muted-foreground">
                    {providerAvailable
                      ? `${model.name} runs locally. Check important answers.`
                      : "Historical chats remain available while the provider is offline."}
                  </p>
                  <button
                    type="button"
                    onClick={onModelSetup}
                    className="flex shrink-0 cursor-pointer items-center gap-1.5 rounded-lg px-1.5 py-1 text-[11px] font-normal text-muted-foreground hover:bg-accent hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/20 focus-visible:outline-none"
                    title="Change model"
                    aria-label={`Model ${model.name} on ${model.provider}. Change model.`}
                  >
                    <span>{model.name}</span>
                    <span>
                      {providerAvailable ? model.provider : "Provider offline"}
                    </span>
                    <ChevronDownIcon className="size-3" />
                  </button>
                </div>
              </div>
            </ThreadPrimitive.ViewportFooter>
          </ThreadPrimitive.Viewport>
        </ThreadPrimitive.Root>
      </section>
    </AssistantRuntimeProvider>
  )
}
