import { useState, type FormEvent } from "react"

import {
  EllipsisIcon,
  MessageSquareIcon,
  PencilIcon,
  PlusIcon,
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
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Skeleton } from "@/components/ui/skeleton"
import { TypewriterText } from "@/components/typewriter-text"
import { cn } from "@/lib/utils"

import type { ChatThread } from "./api"

function RenameChatDialog({
  thread,
  onClose,
  onRename,
}: {
  thread: ChatThread
  onClose: () => void
  onRename: (id: number, title: string) => Promise<boolean>
}) {
  const [title, setTitle] = useState(thread.title || "New chat")
  const [isSubmitting, setIsSubmitting] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const normalized = title.trim()
    if (!normalized) return

    setIsSubmitting(true)
    if (await onRename(thread.id, normalized)) onClose()
    setIsSubmitting(false)
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <form onSubmit={(event) => void submit(event)}>
          <DialogHeader>
            <DialogTitle>Rename chat</DialogTitle>
            <DialogDescription>
              Choose a short name that identifies this conversation.
            </DialogDescription>
          </DialogHeader>
          <Input
            className="my-4"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            aria-label="Chat name"
            maxLength={200}
            autoFocus
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

export function ThreadList({
  workspaceName,
  threads,
  activeThreadId,
  autoNamingThreadId,
  animatingTitleThreadId,
  isLoading,
  onNewChat,
  onSelect,
  onRename,
  onDelete,
  onTitleAnimationComplete,
}: {
  workspaceName: string
  threads: ChatThread[]
  activeThreadId: number | null
  autoNamingThreadId: number | null
  animatingTitleThreadId: number | null
  isLoading: boolean
  onNewChat: () => void
  onSelect: (id: number) => void
  onRename: (id: number, title: string) => Promise<boolean>
  onDelete: (id: number) => Promise<void>
  onTitleAnimationComplete: () => void
}) {
  const [openDropdownId, setOpenDropdownId] = useState<number | null>(null)
  const [renaming, setRenaming] = useState<ChatThread | null>(null)

  return (
    <aside className="flex h-full min-w-0 flex-col border-r bg-sidebar/60">
      <header className="space-y-3 border-b p-3">
        <h2 className="truncate px-1 text-sm font-semibold">{workspaceName}</h2>
        <Button className="w-full justify-start" onClick={onNewChat}>
          <PlusIcon />
          New chat
        </Button>
      </header>
      <ScrollArea className="min-h-0 flex-1">
        <div className="space-y-1 p-2">
          {isLoading
            ? [0, 1, 2, 3].map((item) => (
                <Skeleton key={item} className="h-11 w-full" />
              ))
            : null}
          {!isLoading && threads.length === 0 ? (
            <Empty className="border-0 px-2 py-12">
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <MessageSquareIcon />
                </EmptyMedia>
                <EmptyTitle>No chats yet</EmptyTitle>
                <EmptyDescription>
                  Your first message creates a chat here.
                </EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : null}
          {threads.map((thread) => {
            const selected = thread.id === activeThreadId
            const title = thread.title || "New chat"
            return (
              <div key={thread.id} className="group relative">
                <Button
                  variant="ghost"
                  className={cn(
                    "h-auto w-full min-w-0 justify-start px-2.5 py-2.5 pr-10 font-normal",
                    selected && "bg-sidebar-accent font-medium"
                  )}
                  aria-current={selected ? "page" : undefined}
                  onClick={() => onSelect(thread.id)}
                >
                  <span className="truncate">
                    <TypewriterText
                      text={title}
                      animate={thread.id === animatingTitleThreadId}
                      onComplete={onTitleAnimationComplete}
                    />
                  </span>
                </Button>
                <div className="absolute inset-y-0 right-1 flex items-center">
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
                        className="opacity-0 group-focus-within:opacity-100 group-hover:opacity-100 data-[state=open]:bg-accent data-[state=open]:opacity-100"
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
      </ScrollArea>
      {renaming ? (
        <RenameChatDialog
          key={renaming.id}
          thread={renaming}
          onClose={() => setRenaming(null)}
          onRename={onRename}
        />
      ) : null}
    </aside>
  )
}
