import { useEffect, useRef } from "react"
import {
  ArrowDownIcon,
  ArrowUpIcon,
  BotIcon,
  CircleStopIcon,
  Settings2Icon,
} from "lucide-react"
import {
  AssistantRuntimeProvider,
  ComposerPrimitive,
  ThreadPrimitive,
  type AssistantRuntime,
} from "@assistant-ui/react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import type { ModelSelection } from "@/features/model-selection/api"
import type { WorkspaceDocument } from "@/features/sources/api"

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
        className="flex h-svh min-w-0 flex-col bg-background"
        aria-label="Conversation"
      >
        <header className="flex h-14 shrink-0 items-center justify-between gap-4 border-b px-5">
          <h1
            ref={headingRef}
            tabIndex={-1}
            className="min-w-0 truncate font-serif text-lg font-medium outline-none"
          >
            {thread?.title || "New chat"}
          </h1>
          <div className="flex items-center gap-2">
            <Badge variant="outline">{model.name}</Badge>
            <Badge variant={providerAvailable ? "secondary" : "destructive"}>
              {providerAvailable ? model.provider : "Provider offline"}
            </Badge>
          </div>
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
              <>
                <ThreadPrimitive.Empty>
                  <div className="m-auto flex max-w-md flex-col items-center px-8 py-20 text-center">
                    <div className="mb-4 flex size-11 items-center justify-center rounded-xl bg-muted">
                      <BotIcon className="size-5" />
                    </div>
                    <h2 className="font-serif text-xl font-medium">
                      Ask this workspace
                    </h2>
                    <p className="mt-2 text-sm leading-6 text-muted-foreground">
                      Answers use the sources indexed in this workspace.
                    </p>
                  </div>
                </ThreadPrimitive.Empty>
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
              </>
            ) : null}

            <ThreadPrimitive.ViewportFooter className="sticky bottom-0 mt-auto bg-gradient-to-t from-background via-background to-transparent px-4 pt-10 pb-4">
              <div className="relative mx-auto max-w-3xl">
                <ThreadPrimitive.ScrollToBottom asChild>
                  <Button
                    variant="outline"
                    size="icon-sm"
                    className="absolute -top-10 left-1/2 -translate-x-1/2 rounded-full bg-background"
                    aria-label="Scroll to latest message"
                  >
                    <ArrowDownIcon />
                  </Button>
                </ThreadPrimitive.ScrollToBottom>
                <ComposerPrimitive.Root className="flex items-end gap-2 rounded-2xl border bg-card p-2 shadow-sm focus-within:ring-2 focus-within:ring-ring/20">
                  <ComposerPrimitive.Input
                    className="max-h-44 min-h-12 flex-1 resize-none bg-transparent px-2 py-3 text-sm outline-none placeholder:text-muted-foreground"
                    placeholder={
                      providerAvailable
                        ? "Ask about your sources…"
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
                        className="rounded-xl"
                        aria-label="Send message"
                      >
                        <ArrowUpIcon />
                      </Button>
                    </ComposerPrimitive.Send>
                  ) : (
                    <ComposerPrimitive.Cancel asChild>
                      <Button
                        size="icon-lg"
                        variant="secondary"
                        className="rounded-xl"
                        aria-label="Stop generating"
                      >
                        <CircleStopIcon />
                      </Button>
                    </ComposerPrimitive.Cancel>
                  )}
                </ComposerPrimitive.Root>
                <p className="mt-2 text-center text-[11px] text-muted-foreground">
                  {providerAvailable
                    ? `${model.name} runs locally. Check important answers.`
                    : "Historical chats remain available while the provider is offline."}
                </p>
              </div>
            </ThreadPrimitive.ViewportFooter>
          </ThreadPrimitive.Viewport>
        </ThreadPrimitive.Root>
      </section>
    </AssistantRuntimeProvider>
  )
}
