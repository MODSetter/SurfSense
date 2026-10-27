import { useQuery, useQueryClient } from "@tanstack/react-query"
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
import { SettingsSection } from "@/features/settings/settings-section"
import { intl } from "@/i18n/intl"

import {
  getAccessState,
  MIN_PASSWORD_LENGTH,
  savePassword,
  signOut,
  type PasswordResult,
} from "./api"

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
  return intl.formatMessage({
    id: "access_settings_failed_error",
    defaultMessage: "SurfSense couldn’t save the password. Try again.",
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

function PasswordForm({ creating }: { creating: boolean }) {
  const queryClient = useQueryClient()
  const currentId = useId()
  const newId = useId()
  const confirmId = useId()
  const [current, setCurrent] = useState("")
  const [password, setPassword] = useState("")
  const [confirm, setConfirm] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  const submit = async (event: SubmitEvent) => {
    event.preventDefault()
    setError(null)
    setSaved(false)
    if (password.length < MIN_PASSWORD_LENGTH) return setError(tooShort())
    if (password !== confirm) {
      return setError(
        intl.formatMessage({
          id: "access_settings_mismatch_error",
          defaultMessage: "The passwords don’t match.",
        })
      )
    }
    setBusy(true)
    const result = await savePassword(
      password,
      creating ? undefined : current
    ).catch(() => "failed" as const)
    setBusy(false)
    if (result !== "saved") return setError(refusal(result))
    setCurrent("")
    setPassword("")
    setConfirm("")
    setSaved(!creating)
    await queryClient.invalidateQueries({ queryKey: ACCESS_STATE })
  }

  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={(event) => void submit(event)}
    >
      <FieldGroup>
        {creating ? null : (
          <Field>
            <FieldLabel htmlFor={currentId}>
              {intl.formatMessage({
                id: "access_settings_current_label",
                defaultMessage: "Current password",
              })}
            </FieldLabel>
            <Input
              id={currentId}
              type="password"
              autoComplete="current-password"
              value={current}
              onChange={(event) => setCurrent(event.target.value)}
              disabled={busy}
            />
          </Field>
        )}
        <Field>
          <FieldLabel htmlFor={newId}>
            {intl.formatMessage({
              id: "access_settings_new_label",
              defaultMessage: "New password",
            })}
          </FieldLabel>
          <Input
            id={newId}
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            disabled={busy}
          />
        </Field>
        <Field data-invalid={error ? true : undefined}>
          <FieldLabel htmlFor={confirmId}>
            {intl.formatMessage({
              id: "access_settings_confirm_label",
              defaultMessage: "Confirm password",
            })}
          </FieldLabel>
          <Input
            id={confirmId}
            type="password"
            autoComplete="new-password"
            value={confirm}
            onChange={(event) => setConfirm(event.target.value)}
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
        disabled={busy || !password || !confirm || (!creating && !current)}
      >
        {busy ? <Spinner data-icon="inline-start" /> : null}
        {creating
          ? intl.formatMessage({
              id: "access_settings_create_button",
              defaultMessage: "Create password",
            })
          : intl.formatMessage({
              id: "access_settings_change_button",
              defaultMessage: "Change password",
            })}
      </Button>
    </form>
  )
}

/** Docker only: the password that opens this instance to other devices (ADR 0074). */
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
        state?.password
          ? intl.formatMessage({
              id: "access_settings_protected_body",
              defaultMessage:
                "Other devices sign in with this password. Changing it signs every other device out.",
            })
          : intl.formatMessage({
              id: "access_settings_unprotected_body",
              defaultMessage:
                "SurfSense answers only on this computer until it has a password. With one, other devices on your network can sign in.",
            })
      }
    >
      {state ? (
        <div className="flex flex-col gap-8">
          <PasswordForm
            key={String(state.password)}
            creating={!state.password}
          />
          {state.password ? (
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
          ) : null}
        </div>
      ) : null}
    </SettingsSection>
  )
}
