import {
  memo,
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react"
import { ChevronDownIcon, PencilIcon, Trash2Icon } from "@/components/ui/icons"

import { ThreadPrimitive, useAui, type MessageState } from "@assistant-ui/react"

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
import type { ModelSelection } from "@/features/models/selection/api"
import { useStableCallback } from "@/hooks/use-stable-callback"
import { intl } from "@/i18n/intl"
import type { ChatThread } from "./api"
import { ChatComposer } from "./chat-composer"
import { ChatViewport } from "./chat-viewport"
import { LiveThreadRuntime, type LiveThreadSource } from "./live-thread-runtime"
import { AssistantMessage, UserMessage } from "./message"
import type { Citation } from "./sse"
import type { ConversationView } from "./use-chat-runtime"

// Shared, so a reply without citations passes the same props at every render.
const NO_CITATIONS: Citation[] = []

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
  return NO_CITATIONS
}

// Its props hold still between frames, so a reply re-renders only from its own
// state: the live one by its text, the rest not at all.
const ThreadAssistantMessage = memo(AssistantMessage)

type MessageHandlers = {
  onCitation: (chunkId: number) => void
  onModelSetup: () => void
  onRetry: (assistantId: string) => void
  onNewChat: () => void
}

/**
 * The thread's message renderer, made once. The handlers are read when a
 * message calls them, so new ones from the page re-render no message.
 */
function useMessageRenderer({
  onCitation,
  onModelSetup,
  onRetry,
  onNewChat,
}: MessageHandlers) {
  const citation = useStableCallback(onCitation)
  const modelSetup = useStableCallback(onModelSetup)
  const retry = useStableCallback(onRetry)
  const newChat = useStableCallback(onNewChat)
  const stable = useMemo<MessageHandlers>(
    () => ({
      onCitation: citation,
      onModelSetup: modelSetup,
      onRetry: retry,
      onNewChat: newChat,
    }),
    [citation, modelSetup, retry, newChat]
  )
  return useCallback(
    ({ message }: { message: MessageState }) =>
      message.role === "user" ? (
        <UserMessage />
      ) : (
        <ThreadAssistantMessage
          citations={citationsFrom(message)}
          {...stable}
        />
      ),
    [stable]
  )
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
    if (conversationId === "creating") {
      return
    }
    void aui.thread.composer().reset()
  }, [aui, conversationId])

  return null
}

export function ThreadPanel({
  live,
  thread,
  view,
  model,
  isLoading,
  isRunning,
  animateTitle,
  providerAvailable,
  notice,
  blockedPlaceholder,
  onCitation,
  onModelSetup,
  onModelSelected,
  onRetry,
  onNewChat,
  sourceCount,
  onTitleAnimationComplete,
  autoNamingThreadId,
  onRename,
  onDelete,
  onUploadSources,
  isUploadingSources,
}: {
  live: LiveThreadSource
  thread: ChatThread | null
  view: ConversationView
  model: ModelSelection | null
  isLoading: boolean
  isRunning: boolean
  animateTitle: boolean
  providerAvailable: boolean
  notice?: ReactNode
  blockedPlaceholder?: string
  sourceCount: number
  onCitation: (chunkId: number) => void
  onModelSetup: () => void
  onModelSelected: (selection: ModelSelection) => void
  onRetry: (assistantId: string) => void
  onNewChat: () => void
  onTitleAnimationComplete: () => void
  autoNamingThreadId: number | null
  onRename: (id: number, title: string) => Promise<boolean>
  onDelete: (id: number) => Promise<void>
  onUploadSources?: (files: File[]) => void
  isUploadingSources?: boolean
}) {
  const titleInputRef = useRef<HTMLInputElement>(null)
  const headingId = useId()
  const ignoreMenuFocusRef = useRef(false)
  const [editingThreadId, setEditingThreadId] = useState<number | null>(null)
  const [draft, setDraft] = useState("")
  const untitled = intl.formatMessage({
    id: "chat_thread_panel_untitled_label",
    defaultMessage: "New chat",
  })
  const title = thread?.title || untitled
  const conversationId =
    view.status === "active" ? `thread:${view.threadId}` : view.status
  const editing = thread != null && editingThreadId === thread.id
  const canRename =
    thread != null && thread.id !== autoNamingThreadId && !animateTitle
  const bottomComposer = view.status === "creating" || view.status === "active"
  const composer = (placement: "center" | "bottom") => (
    <ChatComposer
      key={conversationId}
      placement={placement}
      model={model}
      sourceCount={sourceCount}
      isRunning={isRunning}
      providerAvailable={providerAvailable}
      notice={notice}
      blockedPlaceholder={blockedPlaceholder}
      onModelSetup={onModelSetup}
      onModelSelected={onModelSelected}
      readsImages={model?.reads_images === true}
      describedBy={thread == null ? undefined : headingId}
      onUploadSources={onUploadSources}
      isUploadingSources={isUploadingSources}
      threadMode={
        thread == null ? null : thread.uses_agent ? "agentic" : "basic"
      }
      onNewChat={onNewChat}
    />
  )
  const bottomFooter = bottomComposer ? composer("bottom") : undefined
  const renderMessage = useMessageRenderer({
    onCitation,
    onModelSetup,
    onRetry,
    onNewChat,
  })

  useEffect(() => {
    if (editing) {
      const input = titleInputRef.current
      if (!input) return
      input.focus()
      input.select()
    }
  }, [editing])

  const startEditing = () => {
    if (!canRename || thread == null) return
    setDraft(title)
    setEditingThreadId(thread.id)
  }

  const cancelEditing = () => {
    setEditingThreadId(null)
    setDraft(title)
  }

  const commitEditing = () => {
    if (!thread || !editing) return
    const next = draft.trim()
    setEditingThreadId(null)
    if (!next || next === (thread.title || untitled)) return
    void onRename(thread.id, next)
  }

  // Built here, once per render of the panel: a streamed token renders the
  // runtime alone, which hands React these same elements, so it skips them.
  return (
    <LiveThreadRuntime {...live}>
      <ComposerDraftLifecycle view={view} />
      <section
        className="flex h-full min-w-0 flex-col bg-background"
        aria-label={intl.formatMessage({
          id: "chat_thread_panel_conversation_aria",
          defaultMessage: "Conversation",
        })}
      >
        {/* The title control is a button that renames, so the heading is its
            own element. Focus stays on the composer, which it describes. A
            new chat has no conversation to name yet. */}
        {thread == null ? null : (
          <h2 id={headingId} className="sr-only">
            {title}
          </h2>
        )}
        <header className="flex h-14 shrink-0 items-center px-5">
          {thread == null ? null : editing ? (
            <Input
              ref={titleInputRef}
              value={draft}
              maxLength={200}
              aria-label={intl.formatMessage({
                id: "chat_thread_panel_name_aria",
                defaultMessage: "Chat name",
              })}
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
            <ButtonGroup
              aria-label={intl.formatMessage({
                id: "chat_thread_panel_header_aria",
                defaultMessage: "Chat",
              })}
              className="max-w-lg min-w-0"
            >
              <Button
                type="button"
                variant="ghost"
                disabled={!canRename}
                className="h-auto max-w-full min-w-0 px-1.5 py-0 font-heading text-base font-medium active:translate-y-0"
                onClick={startEditing}
              >
                <span className="sidebar-row-title-fade min-w-0 overflow-hidden whitespace-nowrap">
                  <TypewriterText
                    text={title}
                    animate={animateTitle}
                    onComplete={onTitleAnimationComplete}
                  />
                </span>
              </Button>
              <DropdownMenu>
                <DropdownMenuTrigger
                  render={
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      aria-label={intl.formatMessage(
                        {
                          id: "chat_thread_panel_options_aria",
                          defaultMessage: "Chat options for {title}",
                        },
                        {
                          title,
                        }
                      )}
                    >
                      <ChevronDownIcon />
                    </Button>
                  }
                />
                <DropdownMenuContent
                  align="start"
                  sideOffset={8}
                  className="w-36"
                  finalFocus={() => {
                    if (!ignoreMenuFocusRef.current) return true
                    ignoreMenuFocusRef.current = false
                    return false
                  }}
                >
                  <DropdownMenuGroup>
                    <DropdownMenuItem
                      disabled={!canRename}
                      onClick={() => {
                        ignoreMenuFocusRef.current = true
                        startEditing()
                      }}
                    >
                      <PencilIcon />
                      {intl.formatMessage({
                        id: "chat_thread_panel_rename_label",
                        defaultMessage: "Rename",
                      })}
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      variant="destructive"
                      onClick={() => {
                        void onDelete(thread.id)
                      }}
                    >
                      <Trash2Icon />
                      {intl.formatMessage({
                        id: "chat_thread_panel_delete_label",
                        defaultMessage: "Delete chat",
                      })}
                    </DropdownMenuItem>
                  </DropdownMenuGroup>
                </DropdownMenuContent>
              </DropdownMenu>
            </ButtonGroup>
          )}
        </header>

        <ThreadPrimitive.Root className="relative flex min-h-0 flex-1 flex-col">
          <ChatViewport footer={bottomFooter} footerHasNotice={notice != null}>
            {isLoading ? (
              <div className="mx-auto flex w-full max-w-xl flex-col">
                <div className="flex flex-col items-end px-6 py-3">
                  <Skeleton className="h-10 w-[42%] rounded-2xl rounded-br-md" />
                </div>
                <div className="flex flex-col items-start gap-2 px-6 py-4">
                  <Skeleton className="h-4 w-[92%]" />
                  <Skeleton className="h-4 w-[80%]" />
                  <Skeleton className="h-4 w-[58%]" />
                </div>
              </div>
            ) : null}

            {view.status === "new" ? (
              <ThreadWelcome composer={composer("center")} />
            ) : null}

            {view.status === "active" && !isLoading ? (
              <ThreadPrimitive.Messages>
                {renderMessage}
              </ThreadPrimitive.Messages>
            ) : null}
          </ChatViewport>
        </ThreadPrimitive.Root>
      </section>
    </LiveThreadRuntime>
  )
}
