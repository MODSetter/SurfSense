import { useRef, useState, type SubmitEvent } from "react"

import {
  EllipsisIcon,
  PencilEdit02Icon,
  PencilIcon,
  SearchIcon,
  Trash2Icon,
  XIcon,
} from "@/components/ui/icons"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from "@/components/ui/input-group"
import { ScrollShadow } from "@/components/ui/scroll-shadow"
import { SkeletonSlabs } from "@/components/ui/skeleton"
import { RelativeTime } from "@/components/relative-time"
import { TypewriterText } from "@/components/typewriter-text"
import { cn } from "@/lib/utils"
import { intl } from "@/i18n/intl"

import type { ChatThread } from "./api"

export function RenameChatDialog({
  thread,
  onClose,
  onRename,
}: {
  thread: ChatThread
  onClose: () => void
  onRename: (id: number, title: string) => Promise<boolean>
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [title, setTitle] = useState(
    thread.title ||
      intl.formatMessage({
        id: "chat_rename_dialog_untitled_label",
        defaultMessage: "New chat",
      })
  )
  const [isSubmitting, setIsSubmitting] = useState(false)

  const submit = async (event: SubmitEvent) => {
    event.preventDefault()
    const normalized = title.trim()
    if (!normalized) return

    setIsSubmitting(true)
    if (await onRename(thread.id, normalized)) onClose()
    setIsSubmitting(false)
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        className="select-none"
        initialFocus={() => {
          inputRef.current?.select()
          return inputRef.current
        }}
      >
        <form onSubmit={(event) => void submit(event)}>
          <DialogHeader>
            <DialogTitle>
              {intl.formatMessage({
                id: "chat_rename_dialog_title",
                defaultMessage: "Rename chat",
              })}
            </DialogTitle>
            <DialogDescription>
              {intl.formatMessage({
                id: "chat_rename_dialog_body",
                defaultMessage:
                  "Choose a short name that identifies this conversation.",
              })}
            </DialogDescription>
          </DialogHeader>
          <Input
            ref={inputRef}
            className="my-4"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            aria-label={intl.formatMessage({
              id: "chat_rename_dialog_name_aria",
              defaultMessage: "Chat name",
            })}
            maxLength={200}
          />
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              {intl.formatMessage({
                id: "chat_rename_dialog_cancel_button",
                defaultMessage: "Cancel",
              })}
            </Button>
            <Button type="submit" disabled={!title.trim() || isSubmitting}>
              {isSubmitting
                ? intl.formatMessage({
                    id: "chat_rename_dialog_saving_status",
                    defaultMessage: "Saving...",
                  })
                : intl.formatMessage({
                    id: "chat_rename_dialog_rename_button",
                    defaultMessage: "Rename",
                  })}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// Every chat in the workspace, opened from the "Chats" row in the left
// sidebar. Selecting or starting a chat here closes the dialog; renaming and
// deleting stay inline, same as the old sidebar list.
export function ChatsDialog({
  open,
  onOpenChange,
  threads,
  activeThreadId,
  autoNamingThreadId,
  animatingTitleThreadId,
  isLoading,
  onSelect,
  onNewChat,
  onRename,
  onDelete,
  onTitleAnimationComplete,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  threads: ChatThread[]
  activeThreadId: number | null
  autoNamingThreadId: number | null
  animatingTitleThreadId: number | null
  isLoading: boolean
  onSelect: (id: number) => void
  onNewChat: () => void
  onRename: (id: number, title: string) => Promise<boolean>
  onDelete: (id: number) => Promise<void>
  onTitleAnimationComplete: () => void
}) {
  const [openDropdownId, setOpenDropdownId] = useState<number | null>(null)
  const [hoveredId, setHoveredId] = useState<number | null>(null)
  const [renaming, setRenaming] = useState<ChatThread | null>(null)
  const [query, setQuery] = useState("")
  const searchRef = useRef<HTMLInputElement>(null)

  // A separator between two rows hides whenever either of its neighbors is
  // hovered or has its actions menu open, so the highlighted row reads as
  // one unbroken block instead of being cut by the line above or below it.
  const rowActive = (thread: ChatThread | undefined) =>
    thread != null && (thread.id === hoveredId || thread.id === openDropdownId)

  const needle = query.trim().toLowerCase()
  const untitled = intl.formatMessage({
    id: "chat_chats_dialog_untitled_label",
    defaultMessage: "New chat",
  })
  const visibleThreads = needle
    ? threads.filter((thread) =>
        (thread.title || untitled).toLowerCase().includes(needle)
      )
    : threads

  return (
    <>
      <Dialog
        open={open}
        onOpenChange={(nextOpen) => {
          onOpenChange(nextOpen)
          if (!nextOpen) setQuery("")
        }}
      >
        <DialogContent
          className="select-none sm:max-w-3xl"
          initialFocus={searchRef}
        >
          <DialogHeader>
            <DialogTitle className="text-xl">
              {intl.formatMessage({
                id: "chat_chats_dialog_title",
                defaultMessage: "Chats",
              })}
            </DialogTitle>
            <DialogDescription className="sr-only">
              {intl.formatMessage({
                id: "chat_chats_dialog_body",
                defaultMessage: "Every chat in this workspace.",
              })}
            </DialogDescription>
          </DialogHeader>
          <InputGroup className="mt-4 h-10 border-0">
            <InputGroupAddon>
              <SearchIcon />
            </InputGroupAddon>
            <InputGroupInput
              ref={searchRef}
              type="search"
              value={query}
              placeholder={intl.formatMessage({
                id: "chat_chats_dialog_search_placeholder",
                defaultMessage: "Search chats",
              })}
              aria-label={intl.formatMessage({
                id: "chat_chats_dialog_search_aria",
                defaultMessage: "Search chats",
              })}
              // The clear button below replaces the browser's own.
              className="[&::-webkit-search-cancel-button]:appearance-none"
              onChange={(event) => setQuery(event.target.value)}
            />
            {query ? (
              <InputGroupAddon align="inline-end">
                <InputGroupButton
                  size="icon-xs"
                  aria-label={intl.formatMessage({
                    id: "chat_chats_dialog_search_clear_aria",
                    defaultMessage: "Clear search",
                  })}
                  onClick={() => {
                    setQuery("")
                    searchRef.current?.focus()
                  }}
                >
                  <XIcon />
                </InputGroupButton>
              </InputGroupAddon>
            ) : null}
          </InputGroup>
          <ScrollShadow
            className="h-[32rem] min-w-0"
            viewportClassName="overflow-x-hidden"
          >
            <div className="flex w-full max-w-full min-w-0 flex-col pr-1">
              {isLoading ? <SkeletonSlabs /> : null}
              {!isLoading && visibleThreads.length === 0 ? (
                <p className="px-2 py-1 text-sm text-muted-foreground select-none">
                  {needle
                    ? intl.formatMessage({
                        id: "chat_chats_dialog_no_match_empty",
                        defaultMessage: "No chats match your search",
                      })
                    : intl.formatMessage({
                        id: "chat_chats_dialog_empty",
                        defaultMessage: "Start a conversation to see it here",
                      })}
                </p>
              ) : null}
              {visibleThreads.map((thread, index) => {
                const selected = thread.id === activeThreadId
                const title = thread.title || untitled
                const showSeparator =
                  index > 0 &&
                  !rowActive(thread) &&
                  !rowActive(visibleThreads[index - 1])
                // mouseenter/mouseleave don't bubble from descendants, so
                // both interactive elements in the row (not the wrapping
                // div, which is non-interactive) report hover explicitly —
                // that also keeps the row's hover state accurate over the
                // absolutely-positioned actions button.
                const onRowMouseEnter = () => setHoveredId(thread.id)
                const onRowMouseLeave = () =>
                  setHoveredId((current) =>
                    current === thread.id ? null : current
                  )
                return (
                  <div
                    key={thread.id}
                    className="group relative w-full min-w-0 overflow-hidden"
                  >
                    {index > 0 ? (
                      <div
                        className={cn(
                          "mx-1.5 border-t",
                          showSeparator
                            ? "border-border/60"
                            : "border-transparent"
                        )}
                      />
                    ) : null}
                    <Button
                      variant="ghost"
                      className={cn(
                        "h-10 w-full min-w-0 justify-start gap-3 overflow-hidden rounded-lg px-2 py-2 text-sm font-normal group-hover:bg-muted active:translate-y-0! dark:group-hover:bg-muted/50",
                        selected &&
                          "bg-sidebar-accent text-foreground group-hover:text-foreground hover:text-foreground",
                        openDropdownId === thread.id &&
                          "bg-muted dark:bg-muted/50"
                      )}
                      aria-current={selected ? "page" : undefined}
                      // Named by the title alone: read as content, the time
                      // runs into it ("Q3 rollup2 weeks ago"). It stays a
                      // description, so a screen reader still hears it.
                      aria-label={title}
                      aria-describedby={`chat-row-time-${thread.id}`}
                      onClick={() => {
                        onSelect(thread.id)
                        onOpenChange(false)
                      }}
                      onMouseEnter={onRowMouseEnter}
                      onMouseLeave={onRowMouseLeave}
                    >
                      <span
                        className={cn(
                          "chats-dialog-title-fade chats-dialog-title-fade-focus-within min-w-0 flex-1 overflow-hidden text-left whitespace-nowrap",
                          openDropdownId === thread.id &&
                            "chats-dialog-title-fade-actions"
                        )}
                      >
                        <TypewriterText
                          text={title}
                          animate={thread.id === animatingTitleThreadId}
                          onComplete={onTitleAnimationComplete}
                        />
                      </span>
                      <RelativeTime
                        id={`chat-row-time-${thread.id}`}
                        date={new Date(thread.updated_at)}
                        showTooltip={false}
                        className={cn(
                          "shrink-0 overflow-hidden text-xs text-muted-foreground transition-[opacity,width]",
                          "group-focus-within:w-0 group-focus-within:opacity-0",
                          "group-hover:w-0 group-hover:opacity-0",
                          openDropdownId === thread.id && "w-0 opacity-0"
                        )}
                      />
                    </Button>
                    <div className="absolute inset-y-0 right-0 flex items-center rounded-r-lg py-1 pr-1">
                      <DropdownMenu
                        open={openDropdownId === thread.id}
                        onOpenChange={(open) =>
                          setOpenDropdownId(open ? thread.id : null)
                        }
                      >
                        <DropdownMenuTrigger
                          render={
                            <Button
                              variant="ghost"
                              size="icon-sm"
                              className="size-6 opacity-0 group-focus-within:opacity-100 group-hover:opacity-100 hover:bg-transparent active:translate-y-px data-popup-open:bg-accent data-popup-open:opacity-100"
                              aria-label={intl.formatMessage(
                                {
                                  id: "chat_chats_dialog_row_actions_aria",
                                  defaultMessage: "Actions for {title}",
                                },
                                {
                                  title,
                                }
                              )}
                              onMouseEnter={onRowMouseEnter}
                              onMouseLeave={onRowMouseLeave}
                            >
                              <EllipsisIcon />
                            </Button>
                          }
                        />
                        <DropdownMenuContent
                          align="end"
                          sideOffset={8}
                          className="w-36"
                          finalFocus={false}
                        >
                          <DropdownMenuGroup>
                            <DropdownMenuItem
                              disabled={thread.id === autoNamingThreadId}
                              onClick={() => {
                                setOpenDropdownId(null)
                                setRenaming(thread)
                              }}
                            >
                              <PencilIcon />
                              {intl.formatMessage({
                                id: "chat_chats_dialog_rename_label",
                                defaultMessage: "Rename",
                              })}
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              variant="destructive"
                              onClick={() => {
                                setOpenDropdownId(null)
                                void onDelete(thread.id)
                              }}
                            >
                              <Trash2Icon />
                              {intl.formatMessage({
                                id: "chat_chats_dialog_delete_label",
                                defaultMessage: "Delete chat",
                              })}
                            </DropdownMenuItem>
                          </DropdownMenuGroup>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </div>
                )
              })}
            </div>
          </ScrollShadow>
          <DialogFooter className="-mt-4">
            <Button
              type="button"
              variant="ghost"
              className="w-full justify-start px-2"
              onClick={() => {
                onOpenChange(false)
                onNewChat()
              }}
            >
              <PencilEdit02Icon />
              {intl.formatMessage({
                id: "chat_chats_dialog_new_chat_button",
                defaultMessage: "New chat",
              })}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      {renaming ? (
        <RenameChatDialog
          key={renaming.id}
          thread={renaming}
          onClose={() => setRenaming(null)}
          onRename={onRename}
        />
      ) : null}
    </>
  )
}
