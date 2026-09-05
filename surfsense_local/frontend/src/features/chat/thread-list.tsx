import {
  EllipsisIcon,
  MessageSquareIcon,
  PlusIcon,
  Trash2Icon,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"

import type { ChatThread } from "./api"

export function ThreadList({
  workspaceName,
  threads,
  activeThreadId,
  isLoading,
  onNewChat,
  onSelect,
  onDelete,
}: {
  workspaceName: string
  threads: ChatThread[]
  activeThreadId: number | null
  isLoading: boolean
  onNewChat: () => void
  onSelect: (id: number) => void
  onDelete: (id: number) => Promise<void>
}) {
  return (
    <aside className="flex h-svh min-w-0 flex-col border-r bg-sidebar/60">
      <header className="space-y-3 border-b p-3">
        <h2 className="truncate px-1 text-sm font-semibold">{workspaceName}</h2>
        <Button className="w-full justify-start" onClick={onNewChat}>
          <PlusIcon />
          New chat
        </Button>
      </header>
      <ScrollArea className="min-h-0 flex-1">
        <div className="space-y-1 p-2" aria-label="Chat threads">
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
              <div key={thread.id} className="group flex items-center">
                <Button
                  variant="ghost"
                  className={cn(
                    "h-auto min-w-0 flex-1 justify-start px-2.5 py-2.5 font-normal",
                    selected && "bg-sidebar-accent font-medium"
                  )}
                  aria-current={selected ? "page" : undefined}
                  onClick={() => onSelect(thread.id)}
                >
                  <span className="truncate">{title}</span>
                </Button>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      className="-ml-8 opacity-0 group-focus-within:opacity-100 group-hover:opacity-100"
                      aria-label={`Actions for ${title}`}
                    >
                      <EllipsisIcon />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem
                      variant="destructive"
                      onSelect={() => void onDelete(thread.id)}
                    >
                      <Trash2Icon />
                      Delete chat
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            )
          })}
        </div>
      </ScrollArea>
    </aside>
  )
}
