import { useEffect, useRef, useState, type ChangeEvent } from "react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { CircleAlertIcon } from "@/components/ui/icons"
import { Input } from "@/components/ui/input"
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

function notice(status: LicenseStatus): string | null {
  if (status.state === "clock_untrusted") {
    return "This computer's clock is behind the last time SurfSense ran. Set it right to use your license."
  }
  if (status.state === "license_expired") {
    return "This license has expired. Renew it from your account and add the new file."
  }
  if (status.expiry) {
    const days = Math.ceil((Date.parse(status.expiry) - Date.now()) / DAY)
    if (days <= EXPIRY_NOTICE_DAYS) {
      return `This license runs out in ${days} ${days === 1 ? "day" : "days"}.`
    }
  }
  return null
}

export function LicenseSettings() {
  const [status, setStatus] = useState<LicenseStatus | null>(null)
  const [pasted, setPasted] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const controller = new AbortController()
    readLicense(controller.signal)
      .then(setStatus)
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) setError(messageFrom(cause))
      })
    return () => controller.abort()
  }, [])

  const run = async (action: () => Promise<LicenseStatus>) => {
    setBusy(true)
    setError(null)
    try {
      setStatus(await action())
      setPasted("")
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
    await run(async () => importLicense(await file.text()))
  }

  const remove = () =>
    run(async () => {
      await removeLicense()
      return readLicense()
    })

  const shown = status && status.state !== "none" ? notice(status) : null

  return (
    <SettingsSection
      title="License"
      description="Plugins that call paid services need a license file from your SurfSense account. The file is checked on this device; nothing is sent anywhere."
    >
      {status?.state === "none" ? (
        <p className="text-sm text-muted-foreground">
          No license on this device
        </p>
      ) : null}

      {status && status.state !== "none" ? (
        <div className="flex items-start justify-between gap-8">
          <div className="flex flex-col gap-1">
            <h3 className="text-sm font-medium">
              {planLabel(status.plan ?? "")}
            </h3>
            <p className="text-sm text-muted-foreground">{status.email}</p>
            {status.expiry ? (
              <p className="text-sm text-muted-foreground">
                {status.state === "active" ? "Renews" : "Ended"}{" "}
                {dateLabel(status.expiry)}
                {status.max_users ? ` · ${status.max_users} seats` : ""}
              </p>
            ) : null}
          </div>
          <Button
            type="button"
            variant="outline"
            disabled={busy}
            onClick={remove}
          >
            Remove license
          </Button>
        </div>
      ) : null}

      {shown ? (
        <Alert role="status" className="mt-6">
          <CircleAlertIcon />
          <AlertTitle>License</AlertTitle>
          <AlertDescription>{shown}</AlertDescription>
        </Alert>
      ) : null}

      <div className="mt-8 flex flex-col gap-3">
        <h3 className="text-sm font-medium">
          {status?.state === "none" ? "Add a license" : "Replace the license"}
        </h3>
        <Input
          ref={fileInput}
          type="file"
          accept=".lic"
          className="sr-only"
          aria-label="Choose license file"
          disabled={busy}
          onChange={importPicked}
        />
        <div className="flex gap-2">
          <Button
            type="button"
            variant="outline"
            disabled={busy}
            onClick={() => fileInput.current?.click()}
          >
            Choose license file
          </Button>
        </div>
        <textarea
          aria-label="Paste license file"
          className="min-h-24 rounded-md border bg-transparent px-3 py-2 font-mono text-xs"
          placeholder="-----BEGIN LICENSE FILE-----"
          value={pasted}
          disabled={busy}
          onChange={(event) => setPasted(event.target.value)}
        />
        <div>
          <Button
            type="button"
            disabled={busy || pasted.trim() === ""}
            onClick={() => run(() => importLicense(pasted))}
          >
            Add license
          </Button>
        </div>
        {error ? (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        ) : null}
      </div>
    </SettingsSection>
  )
}
