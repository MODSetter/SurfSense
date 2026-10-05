import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  ChevronRightIcon,
  EllipsisIcon,
  Folder01Icon,
  FolderAddIcon,
  FolderTransferIcon,
  PencilIcon,
  Trash2Icon,
} from "@/components/ui/icons"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

import type { SourceFolder } from "./folders-api"
import type { Tick } from "./scope-state"
import type { TreeItemProps } from "./tree-item-props"

export function FolderRow({
  folder,
  expanded,
  hasChildren,
  tick,
  dropping,
  rowRef,
  itemProps,
  onToggleExpanded,
  onTickChange,
  onNewFolder,
  onRename,
  onMove,
  onDelete,
}: {
  folder: SourceFolder
  expanded: boolean
  hasChildren: boolean
  tick: Tick
  // A drag is over this folder, and dropping would put it here.
  dropping: boolean
  rowRef: (node: HTMLLIElement | null) => void
  itemProps: TreeItemProps
  onToggleExpanded: () => void
  onTickChange: (included: boolean) => void
  onNewFolder: () => void
  onRename: () => void
  onMove: () => void
  onDelete: () => void
}) {
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <li
      {...itemProps}
      ref={rowRef}
      className={cn(
        "group/source relative flex h-8 w-full min-w-0 items-center gap-1 overflow-hidden rounded-lg border border-transparent pr-2 pl-1 outline-none select-none hover:bg-muted focus-visible:border-ring dark:hover:bg-muted/50",
        (menuOpen || dropping) && "bg-muted dark:bg-muted/50",
        dropping && "border-ring"
      )}
    >
      <button
        type="button"
        tabIndex={-1}
        aria-label={
          expanded
            ? intl.formatMessage(
                {
                  id: "sources_folder_collapse_aria",
                  defaultMessage: "Collapse {name}",
                },
                { name: folder.name }
              )
            : intl.formatMessage(
                {
                  id: "sources_folder_expand_aria",
                  defaultMessage: "Expand {name}",
                },
                { name: folder.name }
              )
        }
        className={cn(
          "flex size-5 shrink-0 items-center justify-center rounded-sm text-muted-foreground",
          !hasChildren && "opacity-40"
        )}
        onClick={onToggleExpanded}
      >
        <ChevronRightIcon
          className={cn(
            "size-3.5 transition-transform duration-150 motion-reduce:transition-none",
            expanded && "rotate-90"
          )}
        />
      </button>
      <span className="relative flex size-5 shrink-0 items-center justify-center">
        <Checkbox
          checked={tick === "checked"}
          indeterminate={tick === "mixed"}
          tabIndex={-1}
          aria-label={intl.formatMessage(
            {
              id: "sources_folder_select_aria",
              defaultMessage: "Select folder {name}",
            },
            { name: folder.name }
          )}
          onClick={(event) => event.stopPropagation()}
          onCheckedChange={() => onTickChange(tick !== "checked")}
        />
      </span>
      <button
        type="button"
        tabIndex={-1}
        className={cn(
          "sidebar-row-title-fade flex min-w-0 flex-1 items-center gap-1.5 overflow-hidden rounded-sm text-left text-sm font-normal whitespace-nowrap outline-none",
          menuOpen && "sidebar-row-title-fade-actions"
        )}
        onClick={onToggleExpanded}
      >
        <Folder01Icon className="size-4 shrink-0 text-muted-foreground" />
        {folder.name}
      </button>
      <div className="absolute inset-y-0 right-0 flex items-center pr-1">
        <DropdownMenu open={menuOpen} onOpenChange={setMenuOpen}>
          <DropdownMenuTrigger
            render={
              <Button
                type="button"
                size="icon-sm"
                variant="ghost"
                className="size-6 shrink-0 opacity-0 group-hover/source:opacity-100 group-focus-visible/source:opacity-100 hover:bg-transparent focus-visible:opacity-100 active:translate-y-px data-popup-open:bg-accent data-popup-open:opacity-100"
                aria-label={intl.formatMessage(
                  {
                    id: "sources_folder_actions_aria",
                    defaultMessage: "Actions for folder {name}",
                  },
                  { name: folder.name }
                )}
              >
                <EllipsisIcon />
              </Button>
            }
          />
          <DropdownMenuContent align="end" sideOffset={8} className="min-w-40">
            <DropdownMenuGroup>
              <DropdownMenuItem onClick={onNewFolder}>
                <FolderAddIcon />
                {intl.formatMessage({
                  id: "sources_folder_menu_new_folder_label",
                  defaultMessage: "New folder",
                })}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={onRename}>
                <PencilIcon />
                {intl.formatMessage({
                  id: "sources_folder_menu_rename_label",
                  defaultMessage: "Rename",
                })}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={onMove}>
                <FolderTransferIcon />
                {intl.formatMessage({
                  id: "sources_folder_menu_move_label",
                  defaultMessage: "Move to…",
                })}
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem variant="destructive" onClick={onDelete}>
                <Trash2Icon />
                {intl.formatMessage({
                  id: "sources_folder_menu_delete_label",
                  defaultMessage: "Delete",
                })}
              </DropdownMenuItem>
            </DropdownMenuGroup>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </li>
  )
}
