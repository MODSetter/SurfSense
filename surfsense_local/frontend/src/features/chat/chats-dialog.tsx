import { useRef, useState, type SubmitEvent } from "react"

import {
  EllipsisIcon,
  PencilEdit02Icon,
  PencilIcon,
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
  const [renaming, setRenaming] = useState<ChatThread | null>(null)

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="select-none sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Chats</DialogTitle>
            <DialogDescription className="sr-only">
              Every chat in this workspace.
            </DialogDescription>
          </DialogHeader>
          <ScrollShadow
            className="max-h-[60vh] min-h-24"
            viewportClassName="overflow-x-hidden"
            from="from-background"
          >
            <div className="flex w-full max-w-full min-w-0 flex-col gap-1 pr-1">
              {isLoading ? <SkeletonSlabs /> : null}
              {!isLoading && threads.length === 0 ? (
                <p className="px-2 py-1 text-sm text-muted-foreground select-none">
                  Start a conversation to see it here
                </p>
              ) : null}
              {threads.map((thread) => {
                const selected = thread.id === activeThreadId
                const title = thread.title || "New chat"
                return (
                  <div
                    key={thread.id}
                    className="group relative w-full min-w-0 overflow-hidden rounded-md"
                  >
                    <Button
                      variant="ghost"
                      className={cn(
                        "h-8 w-full min-w-0 justify-start overflow-hidden px-2 py-1.5 text-sm font-normal group-hover:bg-muted active:translate-y-0! dark:group-hover:bg-muted/50",
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
                    >
                      <span
                        className={cn(
                          "sidebar-row-title-fade sidebar-row-title-fade-focus-within min-w-0 flex-1 overflow-hidden text-left whitespace-nowrap",
                          openDropdownId === thread.id &&
                            "sidebar-row-title-fade-actions"
                        )}
                      >
                        <TypewriterText
                          text={title}
                          animate={thread.id === animatingTitleThreadId}
                          onComplete={onTitleAnimationComplete}
                        />
                      </span>
                    </Button>
                    <div className="absolute inset-y-0 right-0 flex items-center rounded-r-md py-1 pr-1">
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
          <DialogFooter>
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
