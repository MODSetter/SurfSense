import { useId, useState, type SubmitEvent } from "react"

import { Button } from "@/components/ui/button"
import {
  Field,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"

import { AccessScreen } from "./access-screen"
import { MIN_PASSWORD_LENGTH, savePassword, type PasswordResult } from "./api"
import { PasswordField } from "./password-field"

function refusal(result: PasswordResult): string {
  if (result === "too-short") {
    return intl.formatMessage(
      {
        id: "access_setup_too_short_error",
        defaultMessage: "Use at least {count, number} characters.",
      },
      { count: MIN_PASSWORD_LENGTH }
    )
  }
  return intl.formatMessage({
    id: "access_setup_failed_error",
    defaultMessage: "SurfSense couldn’t save the password. Try again.",
  })
}

/** Docker only, before the instance has a password: its first, from this browser (ADR 0074). */
export function SetupScreen({ onDone }: { onDone: () => void }) {
  const fieldId = useId()
  const hintId = useId()
  const [password, setPassword] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async (event: SubmitEvent) => {
    event.preventDefault()
    setError(null)
    if (password.length < MIN_PASSWORD_LENGTH)
      return setError(refusal("too-short"))
    setBusy(true)
    const result = await savePassword(password).catch(() => "failed" as const)
    setBusy(false)
    // Creating it signs this browser in.
    if (result === "saved") return onDone()
    setError(refusal(result))
  }

  return (
    <AccessScreen
      title={intl.formatMessage({
        id: "access_setup_title",
        defaultMessage: "Set up SurfSense",
      })}
      body={intl.formatMessage({
        id: "access_setup_body",
        defaultMessage:
          "Create the password that protects SurfSense. You’ll use it to sign in on every device.",
      })}
      onSubmit={(event) => void submit(event)}
    >
      <FieldGroup>
        <Field data-invalid={error ? true : undefined}>
          <FieldLabel htmlFor={fieldId}>
            {intl.formatMessage({
              id: "access_setup_field_label",
              defaultMessage: "Password",
            })}
          </FieldLabel>
          <PasswordField
            id={fieldId}
            autoComplete="new-password"
            autoFocus
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            disabled={busy}
            aria-invalid={error ? true : undefined}
            aria-describedby={hintId}
          />
          <FieldDescription id={hintId}>
            {intl.formatMessage(
              {
                id: "access_setup_hint_body",
                defaultMessage: "At least {count, number} characters.",
              },
              { count: MIN_PASSWORD_LENGTH }
            )}
          </FieldDescription>
          {error ? <FieldError>{error}</FieldError> : null}
        </Field>
      </FieldGroup>
      <Button type="submit" disabled={busy || !password}>
        {busy ? <Spinner data-icon="inline-start" /> : null}
        {intl.formatMessage({
          id: "access_setup_button",
          defaultMessage: "Create password",
        })}
      </Button>
    </AccessScreen>
  )
}
