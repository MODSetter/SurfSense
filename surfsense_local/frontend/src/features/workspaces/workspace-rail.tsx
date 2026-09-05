import { useState, type FormEvent } from "react"
import { EllipsisIcon, PencilIcon, PlusIcon, Trash2Icon } from "lucide-react"

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"

import type { Workspace } from "./api"

function workspaceMark(name: string) {
  return (
    name
      .trim()
      .split(/\s+/)
      .slice(0, 2)
      .map((word) => word[0])
      .join("")
      .toUpperCase() || "W"
  )
}

function WorkspaceNameDialog({
  open,
  title,
  description,
  initialName,
  submitLabel,
  onOpenChange,
  onSubmit,
}: {
  open: boolean
  title: string
  description: string
  initialName: string
  submitLabel: string
  onOpenChange: (open: boolean) => void
  onSubmit: (name: string) => Promise<boolean>
}) {
  const [name, setName] = useState(initialName)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const normalized = name.trim()
    if (!normalized) {
      return
    }
    setIsSubmitting(true)
    if (await onSubmit(normalized)) {
      onOpenChange(false)
    }
    setIsSubmitting(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={(event) => void submit(event)}>
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
            <DialogDescription>{description}</DialogDescription>
          </DialogHeader>
          <Input
            className="my-4"
            value={name}
            onChange={(event) => setName(event.target.value)}
            aria-label="Workspace name"
            autoFocus
            maxLength={200}
          />
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={!name.trim() || isSubmitting}>
              {isSubmitting ? "Saving..." : submitLabel}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export function WorkspaceRail({
  workspaces,
  activeWorkspaceId,
  isMutating,
  onSelect,
  onCreate,
  onRename,
  onDelete,
}: {
  workspaces: Workspace[]
  activeWorkspaceId: number
  isMutating: boolean
  onSelect: (id: number) => void
  onCreate: (name: string) => Promise<boolean>
  onRename: (id: number, name: string) => Promise<boolean>
  onDelete: (id: number) => Promise<boolean>
}) {
  const [createOpen, setCreateOpen] = useState(false)
  const [renaming, setRenaming] = useState<Workspace | null>(null)
  const [deleting, setDeleting] = useState<Workspace | null>(null)

  return (
    <nav
      className="flex h-svh flex-col items-center border-r bg-sidebar py-3 text-sidebar-foreground"
      aria-label="Workspaces"
    >
      <div className="mb-3 flex size-9 items-center justify-center rounded-lg bg-sidebar-primary font-serif text-lg text-sidebar-primary-foreground">
        S
      </div>
      <ScrollArea className="min-h-0 w-full flex-1">
        <div className="flex flex-col items-center gap-2 px-1.5">
          {workspaces.map((workspace) => {
            const selected = workspace.id === activeWorkspaceId
            return (
              <div key={workspace.id} className="group relative flex w-full">
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      size="icon-lg"
                      variant="ghost"
                      className={cn(
                        "relative mx-auto rounded-xl",
                        selected &&
                          "bg-sidebar-accent text-sidebar-accent-foreground"
                      )}
                      aria-label={workspace.name}
                      aria-current={selected ? "page" : undefined}
                      onClick={() => onSelect(workspace.id)}
                    >
                      {selected ? (
                        <span className="absolute -left-1.5 h-5 w-0.5 rounded-full bg-sidebar-primary" />
                      ) : null}
                      <Avatar className="size-7 rounded-lg">
                        <AvatarFallback className="rounded-lg text-[10px] font-semibold">
                          {workspaceMark(workspace.name)}
                        </AvatarFallback>
                      </Avatar>
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="right">{workspace.name}</TooltipContent>
                </Tooltip>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      size="icon-xs"
                      variant="ghost"
                      className="absolute top-1.5 right-0 opacity-0 group-focus-within:opacity-100 group-hover:opacity-100"
                      aria-label={`Actions for ${workspace.name}`}
                    >
                      <EllipsisIcon />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent side="right" align="start">
                    <DropdownMenuItem onSelect={() => setRenaming(workspace)}>
                      <PencilIcon />
                      Rename
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      variant="destructive"
                      onSelect={() => setDeleting(workspace)}
                    >
                      <Trash2Icon />
                      Delete
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            )
          })}
        </div>
      </ScrollArea>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            size="icon-lg"
            variant="ghost"
            className="mt-2 rounded-xl border border-dashed"
            disabled={isMutating}
            aria-label="Create workspace"
            onClick={() => setCreateOpen(true)}
          >
            <PlusIcon />
          </Button>
        </TooltipTrigger>
        <TooltipContent side="right">Create workspace</TooltipContent>
      </Tooltip>

      <WorkspaceNameDialog
        key={`create-${createOpen}`}
        open={createOpen}
        title="Create workspace"
        description="Keep a separate source library and set of chats."
        initialName=""
        submitLabel="Create"
        onOpenChange={setCreateOpen}
        onSubmit={onCreate}
      />
      {renaming ? (
        <WorkspaceNameDialog
          key={renaming.id}
          open
          title="Rename workspace"
          description="Choose a name that identifies this research context."
          initialName={renaming.name}
          submitLabel="Rename"
          onOpenChange={(open) => {
            if (!open) setRenaming(null)
          }}
          onSubmit={(name) => onRename(renaming.id, name)}
        />
      ) : null}
      <AlertDialog
        open={deleting !== null}
        onOpenChange={(open) => {
          if (!open) setDeleting(null)
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {deleting?.name}?</AlertDialogTitle>
            <AlertDialogDescription>
              This permanently deletes its chats, documents, and indexed data.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() => {
                if (deleting) void onDelete(deleting.id)
                setDeleting(null)
              }}
            >
              Delete workspace
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </nav>
  )
}
