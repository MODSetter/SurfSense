import { useRef, useState, type SubmitEvent } from "react"
import {
  PencilIcon,
  PlusIcon,
  Settings2Icon,
  Trash2Icon,
} from "@/components/ui/icons"

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
  ContextMenu,
  ContextMenuContent,
  ContextMenuGroup,
  ContextMenuItem,
  ContextMenuTrigger,
} from "@/components/ui/context-menu"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { intl } from "@/i18n/intl"
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
  const inputRef = useRef<HTMLInputElement>(null)
  const [name, setName] = useState(initialName)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const submit = async (event: SubmitEvent) => {
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
      <DialogContent
        className="select-none"
        initialFocus={() => {
          inputRef.current?.select()
          return inputRef.current
        }}
      >
        <form onSubmit={(event) => void submit(event)}>
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
            <DialogDescription>{description}</DialogDescription>
          </DialogHeader>
          <Input
            ref={inputRef}
            className="my-4"
            value={name}
            onChange={(event) => setName(event.target.value)}
            aria-label={intl.formatMessage({
              id: "workspaces_name_dialog_name_aria",
              defaultMessage: "Workspace name",
            })}
            maxLength={200}
          />
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              {intl.formatMessage({
                id: "workspaces_name_dialog_cancel_button",
                defaultMessage: "Cancel",
              })}
            </Button>
            <Button type="submit" disabled={!name.trim() || isSubmitting}>
              {isSubmitting
                ? intl.formatMessage({
                    id: "workspaces_name_dialog_saving_status",
                    defaultMessage: "Saving...",
                  })
                : submitLabel}
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
  onOpenSettings,
}: {
  workspaces: Workspace[]
  activeWorkspaceId: number
  isMutating: boolean
  onSelect: (id: number) => void
  onCreate: (name: string) => Promise<boolean>
  onRename: (id: number, name: string) => Promise<boolean>
  onDelete: (id: number) => Promise<boolean>
  onOpenSettings: () => void
}) {
  const [createOpen, setCreateOpen] = useState(false)
  const [renaming, setRenaming] = useState<Workspace | null>(null)
  const [deleting, setDeleting] = useState<Workspace | null>(null)

  return (
    <nav
      className="flex h-full flex-col items-center bg-app-shell py-3 text-sidebar-foreground"
      aria-label={intl.formatMessage({
        id: "workspaces_rail_aria",
        defaultMessage: "Workspaces",
      })}
    >
      <ScrollArea className="min-h-0 w-full flex-1">
        <div className="flex flex-col items-center gap-2 px-1.5">
          {workspaces.map((workspace) => {
            const selected = workspace.id === activeWorkspaceId
            return (
              <ContextMenu key={workspace.id}>
                <ContextMenuTrigger
                  render={
                    <div className="flex w-full">
                      <Tooltip>
                        <TooltipTrigger
                          render={
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
                          }
                        />
                        <TooltipContent side="right">
                          {workspace.name}
                        </TooltipContent>
                      </Tooltip>
                    </div>
                  }
                />
                <ContextMenuContent className="w-36" finalFocus={false}>
                  <ContextMenuGroup>
                    <ContextMenuItem onClick={() => setRenaming(workspace)}>
                      <PencilIcon />
                      {intl.formatMessage({
                        id: "workspaces_rail_rename_label",
                        defaultMessage: "Rename",
                      })}
                    </ContextMenuItem>
                    <ContextMenuItem
                      variant="destructive"
                      onClick={() => setDeleting(workspace)}
                    >
                      <Trash2Icon />
                      {intl.formatMessage({
                        id: "workspaces_rail_delete_label",
                        defaultMessage: "Delete",
                      })}
                    </ContextMenuItem>
                  </ContextMenuGroup>
                </ContextMenuContent>
              </ContextMenu>
            )
          })}
          <Tooltip>
            <TooltipTrigger
              render={
                <Button
                  size="icon-lg"
                  variant="ghost"
                  className="rounded-xl border border-dashed border-sidebar-border"
                  disabled={isMutating}
                  aria-label={intl.formatMessage({
                    id: "workspaces_rail_create_aria",
                    defaultMessage: "Create workspace",
                  })}
                  onClick={() => setCreateOpen(true)}
                >
                  <PlusIcon />
                </Button>
              }
            />
            <TooltipContent side="right">
              {intl.formatMessage({
                id: "workspaces_rail_create_tooltip",
                defaultMessage: "Create workspace",
              })}
            </TooltipContent>
          </Tooltip>
        </div>
      </ScrollArea>

      <Tooltip>
        <TooltipTrigger
          render={
            <Button
              size="icon-lg"
              variant="ghost"
              className="rounded-xl"
              aria-label={intl.formatMessage({
                id: "workspaces_rail_settings_aria",
                defaultMessage: "Open settings",
              })}
              onClick={onOpenSettings}
            >
              <Settings2Icon />
            </Button>
          }
        />
        <TooltipContent side="right">
          {intl.formatMessage({
            id: "workspaces_rail_settings_tooltip",
            defaultMessage: "Settings",
          })}
        </TooltipContent>
      </Tooltip>

      <WorkspaceNameDialog
        key={`create-${createOpen}`}
        open={createOpen}
        title={intl.formatMessage({
          id: "workspaces_create_dialog_title",
          defaultMessage: "Create workspace",
        })}
        description={intl.formatMessage({
          id: "workspaces_create_dialog_body",
          defaultMessage: "Keep a separate source library and set of chats.",
        })}
        initialName=""
        submitLabel={intl.formatMessage({
          id: "workspaces_create_dialog_submit_button",
          defaultMessage: "Create",
        })}
        onOpenChange={setCreateOpen}
        onSubmit={onCreate}
      />
      {renaming ? (
        <WorkspaceNameDialog
          key={renaming.id}
          open
          title={intl.formatMessage({
            id: "workspaces_rename_dialog_title",
            defaultMessage: "Rename workspace",
          })}
          description={intl.formatMessage({
            id: "workspaces_rename_dialog_body",
            defaultMessage:
              "Choose a name that identifies this research context.",
          })}
          initialName={renaming.name}
          submitLabel={intl.formatMessage({
            id: "workspaces_rename_dialog_submit_button",
            defaultMessage: "Rename",
          })}
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
        <AlertDialogContent className="select-none">
          <AlertDialogHeader>
            <AlertDialogTitle>
              {intl.formatMessage(
                {
                  id: "workspaces_delete_dialog_title",
                  defaultMessage: "Delete {name}?",
                },
                {
                  name: deleting?.name ?? "",
                }
              )}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {intl.formatMessage({
                id: "workspaces_delete_dialog_body",
                defaultMessage:
                  "This permanently deletes its chats, documents, and indexed data.",
              })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>
              {intl.formatMessage({
                id: "workspaces_delete_dialog_cancel_button",
                defaultMessage: "Cancel",
              })}
            </AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() => {
                if (deleting) void onDelete(deleting.id)
                setDeleting(null)
              }}
            >
              {intl.formatMessage({
                id: "workspaces_delete_dialog_confirm_button",
                defaultMessage: "Delete workspace",
              })}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </nav>
  )
}
