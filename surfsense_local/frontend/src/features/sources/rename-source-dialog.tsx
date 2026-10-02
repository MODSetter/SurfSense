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

import type { WorkspaceDocument } from "./api"
import { MAX_SOURCE_TITLE, cleanSourceTitle } from "./source-title"

/** Renames any source. Sends the title alone: a file's text is not editable. */
export function RenameSourceDialog({
  document,
  open,
  onOpenChange,
  onOpenChangeComplete,
  onRename,
}: {
  document: WorkspaceDocument | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onOpenChangeComplete: (open: boolean) => void
  onRename: (documentId: number, title: string) => Promise<boolean>
}) {
  const nameId = useId()
  const [draft, setDraft] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const value = draft ?? document?.title ?? ""
  const title = cleanSourceTitle(value)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!document || !title) return
    setSaving(true)
    const saved = await onRename(document.id, title)
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
              {intl.formatMessage({
                id: "sources_rename_dialog_title",
                defaultMessage: "Rename source",
              })}
            </DialogTitle>
          </DialogHeader>
          <Field>
            <FieldLabel htmlFor={nameId}>
              {intl.formatMessage({
                id: "sources_rename_name_label",
                defaultMessage: "Name",
              })}
            </FieldLabel>
            <Input
              id={nameId}
              value={value}
              maxLength={MAX_SOURCE_TITLE}
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
                id: "sources_rename_cancel_button",
                defaultMessage: "Cancel",
              })}
            </Button>
            <Button type="submit" disabled={!title || saving}>
              {intl.formatMessage({
                id: "sources_rename_submit_button",
                defaultMessage: "Rename",
              })}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
