import { useRef, type ChangeEvent } from "react"
import {
  FilePlus2Icon,
  FolderAddIcon,
  FolderUploadIcon,
  NoteAddIcon,
  PlusIcon,
} from "@/components/ui/icons"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { intl } from "@/i18n/intl"
import { SOURCE_FILE_ACCEPT } from "./api"
import type { UploadEntry } from "./folder-upload/upload-plan"

export type SourceUploads = {
  isUploading: boolean
  onUpload: (files: File[]) => void
  // Absent, the menu uploads files only.
  onUploadFolder?: (entries: UploadEntry[]) => void
}

// Every way to add to the list behind one button, so the header keeps room.
export function AddSourcesMenu({
  upload,
  onNewFolder,
  onNewNote,
}: {
  upload?: SourceUploads
  onNewFolder?: () => void
  onNewNote?: () => void
}) {
  const fileInput = useRef<HTMLInputElement>(null)
  const folderInput = useRef<HTMLInputElement>(null)
  const isUploading = upload?.isUploading ?? false
  const creates = onNewFolder !== undefined || onNewNote !== undefined
  if (!upload && !creates) return null

  const uploadSelectedFiles = (event: ChangeEvent<HTMLInputElement>) => {
    upload?.onUpload(Array.from(event.target.files ?? []))
    event.target.value = ""
  }
  const uploadSelectedFolder = (event: ChangeEvent<HTMLInputElement>) => {
    upload?.onUploadFolder?.(
      Array.from(event.target.files ?? []).map((file) => ({
        file,
        relativePath: file.webkitRelativePath || file.name,
      }))
    )
    event.target.value = ""
  }
  const label = isUploading
    ? intl.formatMessage({
        id: "sources_add_uploading_status",
        defaultMessage: "Uploading...",
      })
    : intl.formatMessage({
        id: "sources_add_menu_aria",
        defaultMessage: "Add sources",
      })

  return (
    <>
      {/* Outside the popup, which unmounts on close before the picker answers. */}
      {upload ? (
        <Input
          ref={fileInput}
          type="file"
          multiple
          accept={SOURCE_FILE_ACCEPT}
          className="sr-only"
          aria-label={intl.formatMessage({
            id: "sources_add_file_aria",
            defaultMessage: "Upload source files",
          })}
          disabled={isUploading}
          onChange={uploadSelectedFiles}
        />
      ) : null}
      {upload?.onUploadFolder ? (
        <Input
          ref={(node) => {
            folderInput.current = node
            // React has no prop for it; Chromium picks a folder with it.
            node?.setAttribute("webkitdirectory", "")
          }}
          type="file"
          multiple
          className="sr-only"
          aria-label={intl.formatMessage({
            id: "sources_add_folder_aria",
            defaultMessage: "Upload a source folder",
          })}
          disabled={isUploading}
          onChange={uploadSelectedFolder}
        />
      ) : null}
      <DropdownMenu>
        <Tooltip>
          <TooltipTrigger
            render={
              <DropdownMenuTrigger
                render={
                  <Button
                    type="button"
                    size="icon-sm"
                    variant="ghost"
                    className="text-muted-foreground"
                    aria-label={label}
                  >
                    {isUploading ? <Spinner /> : <PlusIcon />}
                  </Button>
                }
              />
            }
          />
          <TooltipContent side="top">{label}</TooltipContent>
        </Tooltip>
        <DropdownMenuContent align="end" sideOffset={6} className="min-w-44">
          {upload ? (
            <DropdownMenuGroup>
              <DropdownMenuItem
                disabled={isUploading}
                onClick={() => fileInput.current?.click()}
              >
                <FilePlus2Icon />
                {intl.formatMessage({
                  id: "sources_add_menu_upload_files_label",
                  defaultMessage: "Upload files…",
                })}
              </DropdownMenuItem>
              {upload.onUploadFolder ? (
                <DropdownMenuItem
                  disabled={isUploading}
                  onClick={() => folderInput.current?.click()}
                >
                  <FolderUploadIcon />
                  {intl.formatMessage({
                    id: "sources_add_menu_upload_folder_label",
                    defaultMessage: "Upload folder…",
                  })}
                </DropdownMenuItem>
              ) : null}
            </DropdownMenuGroup>
          ) : null}
          {upload && creates ? <DropdownMenuSeparator /> : null}
          {creates ? (
            <DropdownMenuGroup>
              {onNewFolder ? (
                <DropdownMenuItem onClick={onNewFolder}>
                  <FolderAddIcon />
                  {intl.formatMessage({
                    id: "sources_add_menu_new_folder_label",
                    defaultMessage: "New folder",
                  })}
                </DropdownMenuItem>
              ) : null}
              {onNewNote ? (
                <DropdownMenuItem onClick={onNewNote}>
                  <NoteAddIcon />
                  {intl.formatMessage({
                    id: "sources_add_menu_new_note_label",
                    defaultMessage: "New note",
                  })}
                </DropdownMenuItem>
              ) : null}
            </DropdownMenuGroup>
          ) : null}
        </DropdownMenuContent>
      </DropdownMenu>
    </>
  )
}
