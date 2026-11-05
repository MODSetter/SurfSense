import { useRef, useState, type ChangeEvent } from "react"

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
import { ExternalLink } from "@/features/about/external-link"
import { useAppDetails } from "@/features/about/use-app-details"
import { SettingsSection } from "@/features/settings/settings-section"
import { intl } from "@/i18n/intl"

import { translatedLicenseError } from "./license-error-text"
import { pricingUrl } from "./license-links"
import { LicenseRenewal } from "./license-renewal"
import {
  importLicense,
  readLicense,
  removeLicense,
  type LicenseStatus,
} from "./api"
import { jobName } from "./job-names"
import { planName } from "./plan-name"
import { TrialButton } from "./trial-button"
import { useLicense, usePublishLicense } from "./use-license"
import { useLicenseRefresh } from "./use-license-refresh"

const DAY = 24 * 60 * 60 * 1000
const EXPIRY_NOTICE_DAYS = 14

const messageFrom = translatedLicenseError

function planLabel(status: LicenseStatus) {
  return intl.formatMessage(
    { id: "license_plan_title", defaultMessage: "{plan} plan" },
    { plan: planName(status) }
  )
}

// A team key counts seats and a business key people, Solo's one included.
function headcount(status: LicenseStatus): string | null {
  if (!status.max_users) return null
  if (status.plan !== "business")
    return intl.formatMessage(
      {
        id: "license_status_seats_label",
        defaultMessage: "{count, plural, one {# seat} other {# seats}}",
      },
      { count: status.max_users }
    )
  return intl.formatMessage(
    {
      id: "license_status_people_label",
      defaultMessage: "{count, plural, one {# person} other {# people}}",
    },
    { count: status.max_users }
  )
}

// Business renews on the same key, and a trial that carries jobs is Business's.
function offersRenewal(status: LicenseStatus) {
  return status.plan === "business" || status.jobs.length > 0
}

function notice(
  status: LicenseStatus,
  version: string | undefined
): {
  title: string
  description: string
  link?: { href: string; label: string }
  /** A heads-up rather than a problem reads quieter. */
  variant?: "secondary"
} | null {
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
    const title = intl.formatMessage({
      id: "license_expired_notice_title",
      defaultMessage: "Expired",
    })
    // A renewal extends this same key, so it is fetched rather than bought anew.
    if (offersRenewal(status))
      return {
        title,
        description: intl.formatMessage({
          id: "license_expired_business_notice_body",
          defaultMessage:
            "This license has ended. If it was renewed, Check for renewal fetches the new file.",
        }),
        link: {
          href: pricingUrl("license_renew", version),
          label: intl.formatMessage({
            id: "license_expired_business_notice_link",
            defaultMessage: "See pricing",
          }),
        },
      }
    return {
      title,
      description: intl.formatMessage({
        id: "license_expired_notice_body",
        defaultMessage:
          "This license has expired. Renewing issues a new file to add here.",
      }),
      link: {
        href: pricingUrl("license_renew", version),
        label: intl.formatMessage({
          id: "license_expired_notice_link",
          defaultMessage: "Renew license",
        }),
      },
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
        variant: "secondary",
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
  const license = useLicense()
  const version = useAppDetails().data?.version
  const [editor, setEditor] = useState<"add" | "replace" | null>(null)
  const [editorOpen, setEditorOpen] = useState(false)
  const openEditor = (mode: "add" | "replace") => {
    setEditor(mode)
    setEditorOpen(true)
  }
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const refresh = useLicenseRefresh()
  // One change to the license at a time, a renewal check included.
  const changing = busy || refresh.isPending

  const status = license.data ?? null
  const publishLicense = usePublishLicense()
  const publish = (next: LicenseStatus) => {
    publishLicense(next)
    // The last check's outcome was about the license this one replaces.
    refresh.reset()
  }

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

  const shown =
    status && status.state !== "none" ? notice(status, version) : null
  const count = status ? headcount(status) : null
  const firm = status?.firm?.trim()
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
        <div className="flex items-start justify-between gap-8">
          <div className="flex flex-col gap-2">
            <p className="text-sm text-pretty text-muted-foreground">
              {intl.formatMessage({
                id: "license_settings_empty",
                defaultMessage: "No license on this device",
              })}
            </p>
            <ExternalLink href={pricingUrl("license_pricing", version)}>
              {intl.formatMessage({
                id: "license_settings_pricing_link",
                defaultMessage: "See pricing",
              })}
            </ExternalLink>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => openEditor("add")}
            >
              {intl.formatMessage({
                id: "license_settings_add_button",
                defaultMessage: "Add license",
              })}
            </Button>
            <TrialButton />
          </div>
        </div>
      ) : null}

      {status && status.state !== "none" ? (
        <div className="flex items-start justify-between gap-8">
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-medium text-balance">
                {planLabel(status)}
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
            {firm ? (
              <p className="text-sm text-pretty text-muted-foreground">
                {intl.formatMessage(
                  {
                    id: "license_status_firm_label",
                    defaultMessage: "Licensed to {firm}",
                  },
                  { firm }
                )}
              </p>
            ) : null}
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
                {count ? (
                  <>
                    <DotIcon aria-hidden="true" className="size-3 shrink-0" />
                    <span>{count}</span>
                  </>
                ) : null}
              </p>
            ) : null}
            {status.jobs.length > 0 ? (
              <p className="text-sm text-pretty text-muted-foreground">
                {intl.formatMessage(
                  {
                    id: "license_status_jobs_label",
                    defaultMessage: "Jobs: {jobs}",
                  },
                  {
                    jobs: intl.formatList(status.jobs.map(jobName), {
                      type: "conjunction",
                    }),
                  }
                )}
              </p>
            ) : null}
          </div>
          <div className="flex shrink-0 gap-2">
            <Button
              type="button"
              variant="outline"
              disabled={changing}
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
              disabled={changing}
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

      {status && status.state !== "none" && offersRenewal(status) ? (
        <LicenseRenewal refresh={refresh} disabled={busy} />
      ) : null}

      {shown ? (
        <Alert role="status" variant={shown.variant} className="mt-6">
          <CircleAlertIcon />
          <AlertTitle>{shown.title}</AlertTitle>
          <AlertDescription className="flex flex-col items-start gap-1">
            <span>{shown.description}</span>
            {shown.link ? (
              <ExternalLink href={shown.link.href}>
                {shown.link.label}
              </ExternalLink>
            ) : null}
          </AlertDescription>
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
