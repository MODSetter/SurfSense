import { useEffect, useState, type ReactNode } from "react"

import { Button } from "@/components/ui/button"
import { DialogFooter } from "@/components/ui/dialog"
import { FieldGroup } from "@/components/ui/field"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"

import { updateConnection, type Connection } from "../api"

/** The provider-picker value for a Claude plan; no manifest entry has it. */
export const CLAUDE_PLAN_PROVIDER = "claude_plan"

/**
 * The connection form for a Claude plan: no URL, key or sign-in, since
 * Claude Code keeps all three. Only the name is the user's to edit here.
 */
export function ClaudePlanEdit({
  fields,
  label,
  connection,
  onBusyChange,
  onCancel,
  onSaved,
}: {
  /** The form's Name and Provider fields, shared with every other provider. */
  fields: ReactNode
  label: string
  connection: Connection
  onBusyChange: (busy: boolean) => void
  onCancel: () => void
  onSaved: (connection: Connection) => void
}) {
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const renamed = label.trim() !== connection.label

  useEffect(() => onBusyChange(saving), [saving, onBusyChange])

  const rename = async () => {
    setSaving(true)
    setSaveError(null)
    try {
      onSaved(
        await updateConnection(connection.id, {
          label: label.trim(),
          provider: "openai_compatible",
          base_url: connection.base_url,
          allow_unverified: false,
          catalog_provider: connection.catalog_provider,
        })
      )
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : null)
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <FieldGroup className="relative">
        {fields}
        <p className="text-sm text-muted-foreground">
          {intl.formatMessage({
            id: "models_claude_plan_edit_body",
            defaultMessage:
              "Runs through Claude Code on this computer, which keeps your sign-in. To sign in or out, or to switch accounts, run claude in a terminal.",
          })}
        </p>
        {saveError ? (
          <p className="text-sm text-destructive" role="alert">
            {saveError}
          </p>
        ) : null}
      </FieldGroup>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onCancel}>
          {intl.formatMessage({
            id: "models_claude_plan_edit_cancel_button",
            defaultMessage: "Cancel",
          })}
        </Button>
        <Button
          type="button"
          disabled={saving || !renamed || !label.trim()}
          onClick={() => void rename()}
        >
          {saving ? <Spinner data-icon="inline-start" /> : null}
          {intl.formatMessage({
            id: "models_claude_plan_edit_save_button",
            defaultMessage: "Save changes",
          })}
        </Button>
      </DialogFooter>
    </>
  )
}
