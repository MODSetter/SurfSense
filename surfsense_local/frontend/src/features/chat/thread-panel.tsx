import { useEffect, useRef, useState, type ReactNode } from "react"
import {
  BotIcon,
  ChevronDownIcon,
  PencilIcon,
  Settings2Icon,
  Trash2Icon,
} from "@/components/ui/icons"

import {
  AssistantRuntimeProvider,
  ThreadPrimitive,
  type AssistantRuntime,
  useAui,
} from "@assistant-ui/react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { ButtonGroup } from "@/components/ui/button-group"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { TypewriterText } from "@/components/typewriter-text"
import type { ModelSelection } from "@/features/model-selection/api"
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
  autoNamingThreadId,
  onRename,
  onDelete,
}: {
  runtime: AssistantRuntime
  thread: ChatThread | null
  view: ConversationView
  model: ModelSelection | null
  error: string | null
  isLoading: boolean
  isRunning: boolean
  isUploading: boolean
  animateTitle: boolean
  providerAvailable: boolean
  onCitation: (chunkId: number) => void
  onModelSetup: () => void
  onModelSelected: (selection: ModelSelection) => void
  onUpload: (files: File[]) => void
  onTitleAnimationComplete: () => void
  autoNamingThreadId: number | null
  onRename: (id: number, title: string) => Promise<boolean>
  onDelete: (id: number) => Promise<void>
}) {
  const titleButtonRef = useRef<HTMLButtonElement>(null)
  const titleInputRef = useRef<HTMLInputElement>(null)
  const ignoreMenuFocusRef = useRef(false)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState("")
  const threadId = thread?.id
  const title =
    view.status === "initializing" ? null : thread?.title || "New chat"
  const canRename =
    thread != null && thread.id !== autoNamingThreadId && !animateTitle
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
    setEditing(false)
    if (threadId !== undefined) {
      titleButtonRef.current?.focus()
    }
  }, [threadId])

  useEffect(() => {
    if (editing) {
      const input = titleInputRef.current
      if (!input) return
      input.focus()
      input.select()
    }
  }, [editing])

  const startEditing = () => {
    if (!canRename || title == null) return
    setDraft(title)
    setEditing(true)
  }

  const cancelEditing = () => {
    setEditing(false)
    setDraft(title ?? "")
  }

  const commitEditing = () => {
    if (!thread || !editing) return
    const next = draft.trim()
    setEditing(false)
    if (!next || next === (thread.title || "New chat")) return
    void onRename(thread.id, next)
  }

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <ComposerDraftLifecycle view={view} />
      <section
        className="flex h-full min-w-0 flex-col bg-background"
        aria-label="Conversation"
      >
        <header className="flex h-14 shrink-0 items-center px-5">
          {title === null ? (
            <Skeleton className="h-5 w-32" />
          ) : thread == null ? (
            <h1 className="min-w-0 truncate font-heading text-base font-medium">
              <TypewriterText
                text={title}
                animate={animateTitle}
                onComplete={onTitleAnimationComplete}
              />
            </h1>
          ) : editing ? (
            <Input
              ref={titleInputRef}
              value={draft}
              maxLength={200}
              aria-label="Chat name"
              className="w-auto max-w-full font-heading text-base font-medium md:text-base"
              onChange={(event) => setDraft(event.target.value)}
              onBlur={commitEditing}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault()
                  commitEditing()
                }
                if (event.key === "Escape") {
                  event.preventDefault()
                  cancelEditing()
                }
              }}
            />
          ) : (
            <ButtonGroup aria-label="Chat">
              <Button
                ref={titleButtonRef}
                type="button"
                variant="ghost"
                disabled={!canRename}
                className="h-auto min-w-0 max-w-full px-1.5 py-0 font-heading text-base font-medium active:translate-y-0"
                onClick={startEditing}
              >
                <span className="truncate">
                  <TypewriterText
                    text={title}
                    animate={animateTitle}
                    onComplete={onTitleAnimationComplete}
                  />
                </span>
              </Button>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    aria-label={`Chat options for ${title}`}
                  >
                    <ChevronDownIcon />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent
                  align="start"
                  sideOffset={8}
                  className="w-36"
                  onCloseAutoFocus={(event) => {
                    if (ignoreMenuFocusRef.current) {
                      event.preventDefault()
                      ignoreMenuFocusRef.current = false
                    }
                  }}
                >
                  <DropdownMenuGroup>
                    <DropdownMenuItem
                      disabled={!canRename}
                      onSelect={() => {
                        ignoreMenuFocusRef.current = true
                        startEditing()
                      }}
                    >
                      <PencilIcon />
                      Rename
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      variant="destructive"
                      onSelect={() => {
                        void onDelete(thread.id)
                      }}
                    >
                      <Trash2Icon />
                      Delete chat
                    </DropdownMenuItem>
                  </DropdownMenuGroup>
                </DropdownMenuContent>
              </DropdownMenu>
            </ButtonGroup>
          )}
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
