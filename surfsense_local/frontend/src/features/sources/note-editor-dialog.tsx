import { useQuery } from "@tanstack/react-query"
import { useId, useState, type FormEvent } from "react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Field, FieldError, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { intl } from "@/i18n/intl"

import { MAX_SOURCE_TITLE, cleanSourceTitle } from "./source-title"

/** What the note editor needs from its owner: create, read back, save. */
export type NoteActions = {
  write: (title: string, content: string) => Promise<boolean>
  load: (documentId: number) => Promise<{ title: string; content: string }>
  edit: (documentId: number, title: string, content: string) => Promise<boolean>
}

/** A new note, or the note with this id reopened with its text. */
export type NoteTarget = { documentId: number | null }

export function NoteEditorDialog({
  target,
  open,
  notes,
  onOpenChange,
  onOpenChangeComplete,
}: {
  target: NoteTarget | null
  open: boolean
  notes: NoteActions
  onOpenChange: (open: boolean) => void
  onOpenChangeComplete: (open: boolean) => void
}) {
  const titleId = useId()
  const bodyId = useId()
  const documentId = target?.documentId ?? null
  // Read once per opening: the note's text as saved, which the fields start
  // from until edited.
  const saved = useQuery({
    queryKey: ["sources", "note", documentId],
    queryFn: () => notes.load(documentId as number),
    enabled: open && documentId !== null,
    gcTime: 0,
    staleTime: 0,
  })
  const [titleDraft, setTitleDraft] = useState<string | null>(null)
  const [contentDraft, setContentDraft] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const loading = documentId !== null && saved.isPending
  const loadFailed = documentId !== null && saved.isError
  const title = titleDraft ?? saved.data?.title ?? ""
  const content = contentDraft ?? saved.data?.content ?? ""

  const cleanTitle = cleanSourceTitle(title)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!cleanTitle) return
    setSaving(true)
    const saved =
      documentId === null
        ? await notes.write(cleanTitle, content)
        : await notes.edit(documentId, cleanTitle, content)
    setSaving(false)
    if (saved) onOpenChange(false)
  }

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      onOpenChangeComplete={(next) => {
        if (!next) {
          setTitleDraft(null)
          setContentDraft(null)
        }
        onOpenChangeComplete(next)
      }}
    >
      <DialogContent className="max-h-[calc(100dvh-2rem)] overflow-y-auto sm:max-w-2xl">
        <form
          className="flex min-w-0 flex-col gap-4"
          onSubmit={(event) => void submit(event)}
        >
          <DialogHeader>
            <DialogTitle>
              {documentId === null
                ? intl.formatMessage({
                    id: "sources_note_new_title",
                    defaultMessage: "New note",
                  })
                : intl.formatMessage({
                    id: "sources_note_edit_title",
                    defaultMessage: "Edit note",
                  })}
            </DialogTitle>
          </DialogHeader>
          <Field>
            <FieldLabel htmlFor={titleId}>
              {intl.formatMessage({
                id: "sources_note_title_label",
                defaultMessage: "Title",
              })}
            </FieldLabel>
            <Input
              id={titleId}
              value={title}
              maxLength={MAX_SOURCE_TITLE}
              disabled={loading}
              onChange={(event) => setTitleDraft(event.target.value)}
            />
          </Field>
          <Field>
            <FieldLabel htmlFor={bodyId}>
              {intl.formatMessage({
                id: "sources_note_body_label",
                defaultMessage: "Note",
              })}
            </FieldLabel>
            <Textarea
              id={bodyId}
              className="min-h-48"
              value={content}
              disabled={loading}
              onChange={(event) => setContentDraft(event.target.value)}
            />
          </Field>
          {loadFailed ? (
            <FieldError>
              {intl.formatMessage({
                id: "sources_note_load_error",
                defaultMessage:
                  "Couldn’t open this note. Close it and try again.",
              })}
            </FieldError>
          ) : null}
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              {intl.formatMessage({
                id: "sources_note_cancel_button",
                defaultMessage: "Cancel",
              })}
            </Button>
            <Button
              type="submit"
              disabled={!cleanTitle || loading || loadFailed || saving}
            >
              {intl.formatMessage({
                id: "sources_note_save_button",
                defaultMessage: "Save note",
              })}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
