import { useId, useState, type FormEvent } from "react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Field, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { intl } from "@/i18n/intl"

// The server's limit on a folder name, mirrored so the field stops there.
const MAX_FOLDER_NAME = 255

/** A new folder, or a folder's new name. */
export type FolderNameTarget =
  | { kind: "create"; parentId: number | null }
  | { kind: "rename"; folderId: number; name: string }

export function FolderNameDialog({
  target,
  open,
  onOpenChange,
  onOpenChangeComplete,
  onSubmit,
}: {
  target: FolderNameTarget | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onOpenChangeComplete: (open: boolean) => void
  onSubmit: (target: FolderNameTarget, name: string) => Promise<boolean>
}) {
  const nameId = useId()
  const [draft, setDraft] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const value = draft ?? (target?.kind === "rename" ? target.name : "")
  const name = value.trim()
  const creating = target?.kind !== "rename"

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!target || !name) return
    setSaving(true)
    const saved = await onSubmit(target, name)
    setSaving(false)
    if (saved) onOpenChange(false)
  }

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      onOpenChangeComplete={(next) => {
        if (!next) setDraft(null)
        onOpenChangeComplete(next)
      }}
    >
      <DialogContent className="sm:max-w-md">
        <form
          className="flex min-w-0 flex-col gap-4"
          onSubmit={(event) => void submit(event)}
        >
          <DialogHeader>
            <DialogTitle>
              {creating
                ? intl.formatMessage({
                    id: "sources_folder_create_dialog_title",
                    defaultMessage: "New folder",
                  })
                : intl.formatMessage({
                    id: "sources_folder_rename_dialog_title",
                    defaultMessage: "Rename folder",
                  })}
            </DialogTitle>
          </DialogHeader>
          <Field>
            <FieldLabel htmlFor={nameId}>
              {intl.formatMessage({
                id: "sources_folder_name_label",
                defaultMessage: "Name",
              })}
            </FieldLabel>
            <Input
              id={nameId}
              value={value}
              maxLength={MAX_FOLDER_NAME}
              autoFocus
              onChange={(event) => setDraft(event.target.value)}
            />
          </Field>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              {intl.formatMessage({
                id: "sources_folder_name_cancel_button",
                defaultMessage: "Cancel",
              })}
            </Button>
            <Button type="submit" disabled={!name || saving}>
              {creating
                ? intl.formatMessage({
                    id: "sources_folder_create_submit_button",
                    defaultMessage: "Create",
                  })
                : intl.formatMessage({
                    id: "sources_folder_rename_submit_button",
                    defaultMessage: "Rename",
                  })}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
