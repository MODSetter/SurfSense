import { useEffect, useRef, useState, type ChangeEvent } from "react"

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
import { CircleAlertIcon } from "@/components/ui/icons"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { SettingsSection } from "@/features/settings/settings-section"

import {
  importLicense,
  readLicense,
  removeLicense,
  type LicenseStatus,
} from "./api"

const DAY = 24 * 60 * 60 * 1000
const EXPIRY_NOTICE_DAYS = 14

function messageFrom(error: unknown) {
  return error instanceof Error ? error.message : "An unexpected error occurred"
}

function planLabel(plan: string) {
  return `${plan.charAt(0).toUpperCase()}${plan.slice(1)} plan`
}

function dateLabel(iso: string) {
  return new Date(iso).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  })
}

function notice(
  status: LicenseStatus
): { title: string; description: string } | null {
  if (status.state === "clock_untrusted") {
    return {
      title: "Clock is off",
      description:
        "This computer's clock is behind the last time SurfSense ran. Set it right to use your license.",
    }
  }
  if (status.state === "license_expired") {
    return {
      title: "Expired",
      description:
        "This license has expired. Renew it from your account and add the new file.",
    }
  }
  if (status.expiry) {
    const days = Math.ceil((Date.parse(status.expiry) - Date.now()) / DAY)
    if (days <= EXPIRY_NOTICE_DAYS) {
      return {
        title: "Expiring soon",
        description: `This license runs out in ${days} ${days === 1 ? "day" : "days"}.`,
      }
    }
  }
  return null
}

function LicenseFormDialog({
  replacing,
  onOpenChange,
  onImported,
}: {
  replacing: boolean
  onOpenChange: (open: boolean) => void
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
    <Dialog open onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md select-none">
        <DialogHeader>
          <DialogTitle>
            {replacing ? "Replace license" : "Add license"}
          </DialogTitle>
          <DialogDescription>
            Choose a .lic file or paste it below.
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
              aria-label="Choose license file"
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
              Choose license file
            </Button>
          </Field>
          <Field>
            <FieldLabel htmlFor="license-paste">Or paste the file</FieldLabel>
            <textarea
              id="license-paste"
              aria-label="Paste license file"
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
            Cancel
          </Button>
          <Button
            type="button"
            disabled={busy || pasted.trim() === ""}
            onClick={() => void submit(pasted)}
          >
            {busy ? <Spinner data-icon="inline-start" /> : null}
            Add
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export function LicenseSettings() {
  const [status, setStatus] = useState<LicenseStatus | null>(null)
  const [editor, setEditor] = useState<"add" | "replace" | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    readLicense(controller.signal)
      .then(setStatus)
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) setError(messageFrom(cause))
      })
    return () => controller.abort()
  }, [])

  const remove = async () => {
    setBusy(true)
    setError(null)
    try {
      await removeLicense()
      setStatus(await readLicense())
    } catch (cause) {
      setError(messageFrom(cause))
    } finally {
      setBusy(false)
    }
  }

  const shown = status && status.state !== "none" ? notice(status) : null
  const loading = status === null && error === null

  return (
    <SettingsSection
      title="License"
      description="Paid plugins need a license file from your SurfSense account. It’s verified on this device."
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
            No license on this device
          </p>
          <Button type="button" onClick={() => setEditor("add")}>
            Add license
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
                <Badge variant="secondary">Active</Badge>
              ) : null}
            </div>
            <p className="text-sm text-pretty text-muted-foreground">
              {status.email}
            </p>
            {status.expiry ? (
              <p className="text-sm text-pretty text-muted-foreground tabular-nums">
                {status.state === "active" ? "Renews" : "Ended"}{" "}
                {dateLabel(status.expiry)}
                {status.max_users ? ` · ${status.max_users} seats` : ""}
              </p>
            ) : null}
          </div>
          <div className="flex shrink-0 gap-2">
            <Button
              type="button"
              variant="outline"
              disabled={busy}
              onClick={() => setEditor("replace")}
            >
              Replace license
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={busy}
              onClick={() => void remove()}
            >
              {busy ? <Spinner data-icon="inline-start" /> : null}
              Remove license
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

      {editor !== null ? (
        <LicenseFormDialog
          replacing={editor === "replace"}
          onOpenChange={(open) => {
            if (!open) setEditor(null)
          }}
          onImported={setStatus}
        />
      ) : null}
    </SettingsSection>
  )
}
