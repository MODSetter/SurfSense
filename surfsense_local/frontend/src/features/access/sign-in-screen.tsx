import { useId, useState, type SubmitEvent } from "react"

import { Button } from "@/components/ui/button"
import {
  Field,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"
import surfSenseLogo from "@/surfsense-logo.svg"

import { signIn } from "./api"

/** The Docker image's sign-in, shown until this browser has a session (ADR 0074). */
export function SignInScreen({ onSignedIn }: { onSignedIn: () => void }) {
  const fieldId = useId()
  const [password, setPassword] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async (event: SubmitEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    const result = await signIn(password).catch(
      () => ({ status: "failed" }) as const
    )
    setBusy(false)
    if (result.status === "signed-in") return onSignedIn()
    if (result.status === "wrong") {
      return setError(
        intl.formatMessage({
          id: "access_sign_in_wrong_error",
          defaultMessage: "That password isn’t right.",
        })
      )
    }
    if (result.status === "slowed") {
      return setError(
        intl.formatMessage(
          {
            id: "access_sign_in_slowed_error",
            defaultMessage:
              "Too many tries. Try again in {seconds, plural, one {# second} other {# seconds}}.",
          },
          { seconds: result.retryAfterSeconds }
        )
      )
    }
    setError(
      intl.formatMessage({
        id: "access_sign_in_failed_error",
        defaultMessage: "SurfSense couldn’t sign you in. Try again.",
      })
    )
  }

  return (
    <main className="flex h-full items-center justify-center bg-app-shell p-8">
      <form
        className="flex w-full max-w-sm flex-col gap-6"
        onSubmit={(event) => void submit(event)}
      >
        <div className="flex flex-col items-center gap-3 text-center">
          <span
            aria-hidden="true"
            className="size-10 bg-foreground"
            style={{
              maskImage: `url(${surfSenseLogo})`,
              maskPosition: "center",
              maskRepeat: "no-repeat",
              maskSize: "contain",
            }}
          />
          <h1 className="text-xl font-semibold text-balance">
            {intl.formatMessage({
              id: "access_sign_in_title",
              defaultMessage: "Sign in to SurfSense",
            })}
          </h1>
          <p className="text-sm text-pretty text-muted-foreground">
            {intl.formatMessage({
              id: "access_sign_in_body",
              defaultMessage: "Enter the password set for this SurfSense.",
            })}
          </p>
        </div>
        <FieldGroup>
          <Field data-invalid={error ? true : undefined}>
            <FieldLabel htmlFor={fieldId}>
              {intl.formatMessage({
                id: "access_sign_in_field_label",
                defaultMessage: "Password",
              })}
            </FieldLabel>
            <Input
              id={fieldId}
              type="password"
              autoComplete="current-password"
              autoFocus
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              disabled={busy}
              aria-invalid={error ? true : undefined}
            />
            {error ? <FieldError>{error}</FieldError> : null}
          </Field>
        </FieldGroup>
        <Button type="submit" disabled={busy || !password}>
          {busy ? <Spinner data-icon="inline-start" /> : null}
          {intl.formatMessage({
            id: "access_sign_in_button",
            defaultMessage: "Sign in",
          })}
        </Button>
      </form>
    </main>
  )
}
