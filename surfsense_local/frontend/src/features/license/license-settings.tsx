import { useRef, useState, type ChangeEvent } from "react"
import { useQueryClient } from "@tanstack/react-query"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"
import { CircleAlertIcon, DotIcon } from "@/components/ui/icons"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { SettingsSection } from "@/features/settings/settings-section"
import { intl } from "@/i18n/intl"

import { translatedLicenseError } from "./license-error-text"
import {
  importLicense,
  readLicense,
  removeLicense,
  type LicenseStatus,
} from "./api"
import { licenseQueryKey, useLicense } from "./use-license"

const DAY = 24 * 60 * 60 * 1000
const EXPIRY_NOTICE_DAYS = 14

const messageFrom = translatedLicenseError

function planLabel(plan: string) {
  return intl.formatMessage(
    { id: "license_plan_title", defaultMessage: "{plan} plan" },
    {
      plan: `${plan.charAt(0).toUpperCase()}${plan.slice(1)}`,
    }
  )
}

function notice(
  status: LicenseStatus
): { title: string; description: string } | null {
  if (status.state === "clock_untrusted") {
    return {
      title: intl.formatMessage({
        id: "license_clock_notice_title",
        defaultMessage: "Clock is off",
      }),
      description: intl.formatMessage({
        id: "license_clock_notice_body",
        defaultMessage:
          "This computer’s clock is behind the last time SurfSense ran. Set it right to use your license.",
      }),
    }
  }
  if (status.state === "license_expired") {
    return {
      title: intl.formatMessage({
        id: "license_expired_notice_title",
        defaultMessage: "Expired",
      }),
      description: intl.formatMessage({
        id: "license_expired_notice_body",
        defaultMessage:
          "This license has expired. Renew it from your account and add the new file.",
      }),
    }
  }
  if (status.expiry) {
    const days = Math.ceil((Date.parse(status.expiry) - Date.now()) / DAY)
    if (days <= EXPIRY_NOTICE_DAYS) {
      return {
        title: intl.formatMessage({
          id: "license_expiring_notice_title",
          defaultMessage: "Expiring soon",
        }),
        description: intl.formatMessage(
          {
            id: "license_expiring_notice_body",
            defaultMessage:
              "This license runs out in {count, plural, one {# day} other {# days}}.",
          },
          { count: days }
        ),
      }
    }
  }
  return null
}

function LicenseFormDialog({
  open,
  replacing,
  onOpenChange,
  onOpenChangeComplete,
  onImported,
}: {
  open: boolean
  replacing: boolean
  onOpenChange: (open: boolean) => void
  onOpenChangeComplete: (open: boolean) => void
  onImported: (status: LicenseStatus) => void
}) {
  const fileInput = useRef<HTMLInputElement>(null)
  const [pasted, setPasted] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async (certificate: string) => {
    if (certificate.trim() === "") return
    setBusy(true)
    setError(null)
    try {
      onImported(await importLicense(certificate))
      onOpenChange(false)
    } catch (cause) {
      setError(messageFrom(cause))
    } finally {
      setBusy(false)
    }
  }

  const importPicked = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ""
    if (!file) return
    await submit(await file.text())
  }

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      onOpenChangeComplete={onOpenChangeComplete}
    >
      <DialogContent className="select-none sm:max-w-md">
        <DialogHeader>
          <DialogTitle>
            {replacing
              ? intl.formatMessage({
                  id: "license_form_replace_title",
                  defaultMessage: "Replace license",
                })
              : intl.formatMessage({
                  id: "license_form_add_title",
                  defaultMessage: "Add license",
                })}
          </DialogTitle>
          <DialogDescription>
            {intl.formatMessage({
              id: "license_form_body",
              defaultMessage: "Choose a .lic file or paste it below.",
            })}
          </DialogDescription>
        </DialogHeader>
        <FieldGroup>
          <Field>
            <Input
              ref={fileInput}
              id="license-file"
              type="file"
              accept=".lic"
              className="sr-only"
              aria-label={intl.formatMessage({
                id: "license_form_file_aria",
                defaultMessage: "Choose license file",
              })}
              disabled={busy}
              onChange={importPicked}
            />
            <Button
              type="button"
              variant="outline"
              disabled={busy}
              onClick={() => fileInput.current?.click()}
            >
              {busy ? <Spinner data-icon="inline-start" /> : null}
              {intl.formatMessage({
                id: "license_form_choose_file_button",
                defaultMessage: "Choose license file",
              })}
            </Button>
          </Field>
          <Field>
            <FieldLabel htmlFor="license-paste">
              {intl.formatMessage({
                id: "license_form_paste_label",
                defaultMessage: "Or paste the file",
              })}
            </FieldLabel>
            <textarea
              id="license-paste"
              aria-label={intl.formatMessage({
                id: "license_form_paste_aria",
                defaultMessage: "Paste license file",
              })}
              className="min-h-24 w-full min-w-0 resize-y rounded-lg border border-input bg-transparent px-2.5 py-2 font-mono text-xs transition-colors outline-none placeholder:text-muted-foreground focus-visible:border-ring/70 disabled:pointer-events-none disabled:cursor-not-allowed disabled:bg-input/50 disabled:opacity-50 dark:bg-input/30"
              placeholder="-----BEGIN LICENSE FILE-----"
              value={pasted}
              disabled={busy}
              onChange={(event) => setPasted(event.target.value)}
            />
          </Field>
          {error ? (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          ) : null}
        </FieldGroup>
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
          >
            {intl.formatMessage({
              id: "license_form_cancel_button",
              defaultMessage: "Cancel",
            })}
          </Button>
          <Button
            type="button"
            disabled={busy || pasted.trim() === ""}
            onClick={() => void submit(pasted)}
          >
            {busy ? <Spinner data-icon="inline-start" /> : null}
            {intl.formatMessage({
              id: "license_form_add_button",
              defaultMessage: "Add",
            })}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export function LicenseSettings() {
  const queryClient = useQueryClient()
  const license = useLicense()
  const [editor, setEditor] = useState<"add" | "replace" | null>(null)
  const [editorOpen, setEditorOpen] = useState(false)
  const openEditor = (mode: "add" | "replace") => {
    setEditor(mode)
    setEditorOpen(true)
  }
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  const status = license.data ?? null
  // Straight into the cache rather than local state, so the sidebar's license
  // row reacts to an import here without refetching.
  const publish = (next: LicenseStatus) =>
    queryClient.setQueryData(licenseQueryKey, next)

  const remove = async () => {
    setBusy(true)
    setActionError(null)
    try {
      await removeLicense()
      publish(await readLicense())
    } catch (cause) {
      setActionError(messageFrom(cause))
    } finally {
      setBusy(false)
    }
  }

  const shown = status && status.state !== "none" ? notice(status) : null
  const error =
    actionError ?? (license.error ? messageFrom(license.error) : null)
  const loading = license.isPending

  return (
    <SettingsSection
      title={intl.formatMessage({
        id: "license_settings_title",
        defaultMessage: "License",
      })}
      description={intl.formatMessage({
        id: "license_settings_body",
        defaultMessage:
          "Paid plugins need a license file tied to your email. It’s verified on this device.",
      })}
    >
      {loading ? (
        <div className="flex flex-col gap-1">
          <Skeleton className="h-5 w-36" />
          <Skeleton className="h-4 w-48" />
        </div>
      ) : null}

      {status?.state === "none" ? (
        <div className="flex items-center justify-between gap-8">
          <p className="text-sm text-pretty text-muted-foreground">
            {intl.formatMessage({
              id: "license_settings_empty",
              defaultMessage: "No license on this device",
            })}
          </p>
          <Button type="button" onClick={() => openEditor("add")}>
            {intl.formatMessage({
              id: "license_settings_add_button",
              defaultMessage: "Add license",
            })}
          </Button>
        </div>
      ) : null}

      {status && status.state !== "none" ? (
        <div className="flex items-start justify-between gap-8">
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-medium text-balance">
                {planLabel(status.plan ?? "")}
              </h3>
              {status.state === "active" ? (
                <Badge variant="secondary">
                  {intl.formatMessage({
                    id: "license_status_active_label",
                    defaultMessage: "Active",
                  })}
                </Badge>
              ) : null}
            </div>
            <p className="text-sm text-pretty text-muted-foreground">
              {status.email}
            </p>
            {status.expiry ? (
              <p className="flex flex-wrap items-center text-sm text-muted-foreground tabular-nums">
                <span>
                  {status.state === "active"
                    ? intl.formatMessage(
                        {
                          id: "license_status_expires_label",
                          defaultMessage: "Expires {date, date, ::yyyyMMMd}",
                        },
                        {
                          date: new Date(status.expiry),
                        }
                      )
                    : intl.formatMessage(
                        {
                          id: "license_status_ended_label",
                          defaultMessage: "Ended {date, date, ::yyyyMMMd}",
                        },
                        {
                          date: new Date(status.expiry),
                        }
                      )}
                </span>
                {status.max_users ? (
                  <>
                    <DotIcon aria-hidden="true" className="size-3 shrink-0" />
                    <span>
                      {intl.formatMessage(
                        {
                          id: "license_status_seats_label",
                          defaultMessage:
                            "{count, plural, one {# seat} other {# seats}}",
                        },
                        {
                          count: status.max_users,
                        }
                      )}
                    </span>
                  </>
                ) : null}
              </p>
            ) : null}
          </div>
          <div className="flex shrink-0 gap-2">
            <Button
              type="button"
              variant="outline"
              disabled={busy}
              onClick={() => openEditor("replace")}
            >
              {intl.formatMessage({
                id: "license_settings_replace_button",
                defaultMessage: "Replace license",
              })}
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={busy}
              onClick={() => void remove()}
            >
              {busy ? <Spinner data-icon="inline-start" /> : null}
              {intl.formatMessage({
                id: "license_settings_remove_button",
                defaultMessage: "Remove license",
              })}
            </Button>
          </div>
        </div>
      ) : null}

      {shown ? (
        <Alert role="status" className="mt-6">
          <CircleAlertIcon />
          <AlertTitle>{shown.title}</AlertTitle>
          <AlertDescription>{shown.description}</AlertDescription>
        </Alert>
      ) : null}

      {error ? (
        <p role="alert" className="mt-6 text-sm text-destructive">
          {error}
        </p>
      ) : null}

      {editor ? (
        <LicenseFormDialog
          key={editor}
          open={editorOpen}
          replacing={editor === "replace"}
          onOpenChange={setEditorOpen}
          onOpenChangeComplete={(open) => {
            if (!open) setEditor(null)
          }}
          onImported={publish}
        />
      ) : null}
    </SettingsSection>
  )
}
