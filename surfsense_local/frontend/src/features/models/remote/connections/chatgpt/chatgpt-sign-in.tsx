import { useEffect, useState, type ReactNode } from "react"

import { Button } from "@/components/ui/button"
import { DialogFooter } from "@/components/ui/dialog"
import { FieldGroup } from "@/components/ui/field"
import { ExternalLinkIcon } from "@/components/ui/icons"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"

import { getConnections, updateConnection, type Connection } from "../api"
import { signOut } from "./api"
import { SignInProgress } from "./sign-in-progress"
import { useChatGPTSignIn } from "./use-sign-in"

function accountText(connection: Connection) {
  if (!connection.signed_in)
    return intl.formatMessage({
      id: "models_chatgpt_signed_out_body",
      defaultMessage: "Signed out. Sign in again to use this plan’s models.",
    })
  return connection.account_email
    ? intl.formatMessage(
        {
          id: "models_chatgpt_signed_in_body",
          defaultMessage: "Signed in as {email}.",
        },
        { email: connection.account_email }
      )
    : intl.formatMessage({
        id: "models_chatgpt_signed_in_unnamed_body",
        defaultMessage: "Signed in.",
      })
}

/**
 * The connection form for a ChatGPT subscription: no URL or key, a browser
 * sign-in instead. Editing one renames it, signs it out, or signs in again.
 */
export function ChatGPTSignIn({
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
  connection?: Connection
  onBusyChange: (busy: boolean) => void
  onCancel: () => void
  onSaved: (connection: Connection) => void
}) {
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  const finish = async (connectionId: number) => {
    const saved = (await getConnections()).find(
      (entry) => entry.id === connectionId
    )
    if (saved) onSaved(saved)
  }
  const { state, start, cancel } = useChatGPTSignIn((id) => void finish(id))
  const signingIn = state.phase === "starting" || state.phase === "waiting"
  const busy = signingIn || saving
  const renamed = Boolean(connection && label.trim() !== connection.label)

  // The shared Name and Provider fields lock while anything is in flight.
  useEffect(() => onBusyChange(busy), [busy, onBusyChange])

  const signIn = () => {
    setSaveError(null)
    void start(
      connection ? { connection_id: connection.id } : { label: label.trim() }
    )
  }

  // Run an edit that needs no browser: a rename or a sign-out.
  const edit = async (work: () => Promise<Connection>) => {
    setSaving(true)
    setSaveError(null)
    try {
      onSaved(await work())
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : null)
    } finally {
      setSaving(false)
    }
  }

  const rename = (current: Connection) =>
    edit(() =>
      updateConnection(current.id, {
        label: label.trim(),
        provider: "openai_compatible",
        base_url: current.base_url,
        allow_unverified: false,
        catalog_provider: current.catalog_provider,
      })
    )

  const leave = (current: Connection) =>
    edit(async () => {
      await signOut(current.id)
      return { ...current, signed_in: false, account_email: null }
    })

  return (
    <>
      <FieldGroup className="relative">
        {fields}
        <p className="text-sm text-muted-foreground">
          {connection
            ? accountText(connection)
            : intl.formatMessage({
                id: "models_chatgpt_intro_body",
                defaultMessage:
                  "Uses your ChatGPT Plus or Pro plan for chat, with no API key. You sign in with your ChatGPT account in your browser.",
              })}
        </p>
        <SignInProgress state={state} />
        {saveError ? (
          <p className="text-sm text-destructive" role="alert">
            {saveError}
          </p>
        ) : null}
      </FieldGroup>
      <DialogFooter>
        <Button
          type="button"
          variant="outline"
          onClick={signingIn ? cancel : onCancel}
        >
          {intl.formatMessage({
            id: "models_chatgpt_cancel_button",
            defaultMessage: "Cancel",
          })}
        </Button>
        {connection?.signed_in ? (
          <Button
            type="button"
            variant="outline"
            disabled={busy}
            onClick={() => void leave(connection)}
          >
            {intl.formatMessage({
              id: "models_chatgpt_sign_out_button",
              defaultMessage: "Sign out",
            })}
          </Button>
        ) : null}
        {connection && renamed ? (
          <Button
            type="button"
            variant="outline"
            disabled={busy || !label.trim()}
            onClick={() => void rename(connection)}
          >
            {saving ? <Spinner data-icon="inline-start" /> : null}
            {intl.formatMessage({
              id: "models_chatgpt_save_changes_button",
              defaultMessage: "Save changes",
            })}
          </Button>
        ) : null}
        <Button type="button" disabled={busy || !label.trim()} onClick={signIn}>
          {signingIn ? <Spinner data-icon="inline-start" /> : null}
          {connection
            ? intl.formatMessage({
                id: "models_chatgpt_sign_in_again_button",
                defaultMessage: "Sign in again",
              })
            : intl.formatMessage({
                id: "models_chatgpt_sign_in_button",
                defaultMessage: "Sign in with ChatGPT",
              })}
          {/* Sign-in continues in the browser, as "Continue on GitHub" does. */}
          <ExternalLinkIcon data-icon="inline-end" />
        </Button>
      </DialogFooter>
    </>
  )
}
