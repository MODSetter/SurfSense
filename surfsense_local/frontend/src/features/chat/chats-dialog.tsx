import { useRef, useState, type SubmitEvent } from "react"

import {
  EllipsisIcon,
  PencilEdit02Icon,
  PencilIcon,
  SearchIcon,
  Trash2Icon,
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
import { ScrollShadow } from "@/components/ui/scroll-shadow"
import { SkeletonSlabs } from "@/components/ui/skeleton"
import { RelativeTime } from "@/components/relative-time"
import { TypewriterText } from "@/components/typewriter-text"
import { cn } from "@/lib/utils"

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
  const [title, setTitle] = useState(thread.title || "New chat")
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
        onOpenAutoFocus={(event) => {
          event.preventDefault()
          const input = inputRef.current
          if (!input) return
          input.focus()
          input.select()
        }}
      >
        <form onSubmit={(event) => void submit(event)}>
          <DialogHeader>
            <DialogTitle>Rename chat</DialogTitle>
            <DialogDescription>
              Choose a short name that identifies this conversation.
            </DialogDescription>
          </DialogHeader>
          <Input
            ref={inputRef}
            className="my-4"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            aria-label="Chat name"
            maxLength={200}
          />
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={!title.trim() || isSubmitting}>
              {isSubmitting ? "Saving..." : "Rename"}
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
  const visibleThreads = needle
    ? threads.filter((thread) =>
        (thread.title || "New chat").toLowerCase().includes(needle)
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
          onOpenAutoFocus={(event) => {
            event.preventDefault()
            searchRef.current?.focus()
          }}
        >
          <DialogHeader>
            <DialogTitle className="text-xl">Chats</DialogTitle>
            <DialogDescription className="sr-only">
              Every chat in this workspace.
            </DialogDescription>
          </DialogHeader>
          <div className="relative mt-4">
            <SearchIcon className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              ref={searchRef}
              type="search"
              value={query}
              placeholder="Search chats"
              aria-label="Search chats"
              className="h-10 border-0 bg-secondary pl-9 focus-visible:border-0 dark:bg-secondary"
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>
          <ScrollShadow
            className="h-[32rem] min-w-0"
            viewportClassName="overflow-x-hidden"
          >
            <div className="flex w-full max-w-full min-w-0 flex-col pr-1">
              {isLoading ? <SkeletonSlabs /> : null}
              {!isLoading && visibleThreads.length === 0 ? (
                <p className="px-2 py-1 text-sm text-muted-foreground select-none">
                  {needle
                    ? "No chats match your search"
                    : "Start a conversation to see it here"}
                </p>
              ) : null}
              {visibleThreads.map((thread, index) => {
                const selected = thread.id === activeThreadId
                const title = thread.title || "New chat"
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
                        <DropdownMenuTrigger asChild>
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            className="size-6 opacity-0 group-focus-within:opacity-100 group-hover:opacity-100 hover:bg-transparent active:translate-y-px data-[state=open]:bg-accent data-[state=open]:opacity-100"
                            aria-label={`Actions for ${title}`}
                            onMouseEnter={onRowMouseEnter}
                            onMouseLeave={onRowMouseLeave}
                          >
                            <EllipsisIcon />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent
                          align="end"
                          sideOffset={8}
                          className="w-36"
                          onCloseAutoFocus={(event) => event.preventDefault()}
                        >
                          <DropdownMenuGroup>
                            <DropdownMenuItem
                              disabled={thread.id === autoNamingThreadId}
                              onSelect={() => {
                                setOpenDropdownId(null)
                                setRenaming(thread)
                              }}
                            >
                              <PencilIcon />
                              Rename
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              variant="destructive"
                              onSelect={() => {
                                setOpenDropdownId(null)
                                void onDelete(thread.id)
                              }}
                            >
                              <Trash2Icon />
                              Delete chat
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
              New chat
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
