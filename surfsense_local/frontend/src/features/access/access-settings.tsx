import { useQuery } from "@tanstack/react-query"
import { useId, useState, type SubmitEvent } from "react"

import { Button } from "@/components/ui/button"
import {
  Field,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field"
import { LockPasswordIcon } from "@/components/ui/icons"
import { Spinner } from "@/components/ui/spinner"
import { SettingsSection } from "@/features/settings/settings-section"
import { intl } from "@/i18n/intl"

import {
  getAccessState,
  MIN_PASSWORD_LENGTH,
  savePassword,
  signOut,
  type PasswordResult,
} from "./api"
import { PasswordField } from "./password-field"

const ACCESS_STATE = ["access-state"]

function refusal(result: PasswordResult): string {
  if (result === "wrong-current") {
    return intl.formatMessage({
      id: "access_settings_wrong_current_error",
      defaultMessage: "The current password isn’t right.",
    })
  }
  if (result === "slowed") {
    return intl.formatMessage({
      id: "access_settings_slowed_error",
      defaultMessage: "Too many tries. Wait a minute, then try again.",
    })
  }
  if (result === "too-short") return tooShort()
  if (result === "set-by-setup") return lockedBySetup()
  return intl.formatMessage({
    id: "access_settings_failed_error",
    defaultMessage: "SurfSense couldn’t save the password. Try again.",
  })
}

function lockedBySetup(): string {
  return intl.formatMessage({
    id: "access_settings_set_by_setup_body",
    defaultMessage:
      "This password is set where SurfSense is installed. To change it, update SurfSense’s setup on that computer, then restart it.",
  })
}

function tooShort(): string {
  return intl.formatMessage(
    {
      id: "access_settings_too_short_error",
      defaultMessage: "Use at least {count, number} characters.",
    },
    { count: MIN_PASSWORD_LENGTH }
  )
}

function ChangePasswordForm() {
  const currentId = useId()
  const newId = useId()
  const [current, setCurrent] = useState("")
  const [password, setPassword] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  const submit = async (event: SubmitEvent) => {
    event.preventDefault()
    setError(null)
    setSaved(false)
    if (password.length < MIN_PASSWORD_LENGTH) return setError(tooShort())
    setBusy(true)
    const result = await savePassword(password, current).catch(
      () => "failed" as const
    )
    setBusy(false)
    if (result !== "saved") return setError(refusal(result))
    setCurrent("")
    setPassword("")
    setSaved(true)
  }

  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={(event) => void submit(event)}
    >
      <FieldGroup>
        <Field>
          <FieldLabel htmlFor={currentId}>
            {intl.formatMessage({
              id: "access_settings_current_label",
              defaultMessage: "Current password",
            })}
          </FieldLabel>
          <PasswordField
            id={currentId}
            autoComplete="current-password"
            value={current}
            onChange={(event) => setCurrent(event.target.value)}
            disabled={busy}
          />
        </Field>
        <Field data-invalid={error ? true : undefined}>
          <FieldLabel htmlFor={newId}>
            {intl.formatMessage({
              id: "access_settings_new_label",
              defaultMessage: "New password",
            })}
          </FieldLabel>
          <PasswordField
            id={newId}
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            disabled={busy}
            aria-invalid={error ? true : undefined}
          />
          {error ? <FieldError>{error}</FieldError> : null}
        </Field>
      </FieldGroup>
      {saved ? (
        <p role="status" className="text-sm text-muted-foreground">
          {intl.formatMessage({
            id: "access_settings_changed_status",
            defaultMessage:
              "Password changed. Other devices must sign in again.",
          })}
        </p>
      ) : null}
      <Button
        type="submit"
        className="w-fit"
        disabled={busy || !password || !current}
      >
        {busy ? <Spinner data-icon="inline-start" /> : null}
        {intl.formatMessage({
          id: "access_settings_change_button",
          defaultMessage: "Change password",
        })}
      </Button>
    </form>
  )
}

/** A muted note with a lock: what cannot be changed here, and where it can. */
function LockedNote({ children }: { children: string }) {
  return (
    <p className="flex gap-2 rounded-lg bg-muted/50 px-3 py-2.5 text-sm text-pretty text-muted-foreground">
      <LockPasswordIcon aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
      {children}
    </p>
  )
}

/** Docker only: the instance's password, or why there is none to manage here (ADR 0074). */
export function AccessSettings() {
  const { data: state } = useQuery({
    queryKey: ACCESS_STATE,
    queryFn: getAccessState,
  })
  const [signingOut, setSigningOut] = useState(false)

  const leave = async () => {
    setSigningOut(true)
    await signOut().catch(() => undefined)
    window.location.reload()
  }

  return (
    <SettingsSection
      title={intl.formatMessage({
        id: "access_settings_title",
        defaultMessage: "Access",
      })}
      description={
        state?.signInOff
          ? undefined
          : intl.formatMessage({
              id: "access_settings_protected_body",
              defaultMessage:
                "Every device signs in with this password. Changing it signs every other device out.",
            })
      }
    >
      {state ? (
        state.signInOff ? (
          <LockedNote>
            {intl.formatMessage({
              id: "access_settings_sign_in_off_body",
              defaultMessage:
                "Sign-in is turned off where SurfSense is installed. Anyone who can reach it can use it.",
            })}
          </LockedNote>
        ) : (
          <div className="flex flex-col gap-8">
            {state.source === "setup" ? (
              <LockedNote>{lockedBySetup()}</LockedNote>
            ) : (
              <ChangePasswordForm />
            )}
            <div className="flex flex-col gap-1">
              <h3 className="text-sm font-medium">
                {intl.formatMessage({
                  id: "access_settings_sign_out_title",
                  defaultMessage: "Sign out",
                })}
              </h3>
              <p className="text-sm text-pretty text-muted-foreground">
                {intl.formatMessage({
                  id: "access_settings_sign_out_body",
                  defaultMessage:
                    "Sign this browser out. Other devices stay signed in.",
                })}
              </p>
              <Button
                type="button"
                variant="outline"
                className="mt-2 w-fit"
                disabled={signingOut}
                onClick={() => void leave()}
              >
                {intl.formatMessage({
                  id: "access_settings_sign_out_button",
                  defaultMessage: "Sign out",
                })}
              </Button>
            </div>
          </div>
        )
      ) : null}
    </SettingsSection>
  )
}
