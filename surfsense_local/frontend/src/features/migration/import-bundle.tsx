import { useRef, useState, type ChangeEvent } from "react"

import { Button } from "@/components/ui/button"
import { DownloadIcon } from "@/components/ui/icons"
import { Input } from "@/components/ui/input"

import { importBundle, type ImportAccepted } from "./api"

function messageFrom(error: unknown) {
  return error instanceof Error ? error.message : "An unexpected error occurred"
}

export function ImportBundleButton({
  onImported,
  variant = "outline",
}: {
  onImported: (accepted: ImportAccepted) => Promise<void> | void
  variant?: "outline" | "default"
}) {
  const fileInput = useRef<HTMLInputElement>(null)
  const [isImporting, setIsImporting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const importSelected = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ""
    if (!file) return
    setIsImporting(true)
    setError(null)
    try {
      await onImported(await importBundle(file))
    } catch (cause) {
      setError(messageFrom(cause))
    } finally {
      setIsImporting(false)
    }
  }

  return (
    <div className="flex flex-col items-center gap-2">
      <Input
        ref={fileInput}
        type="file"
        accept=".zip"
        className="sr-only"
        aria-label="Import from SurfSense cloud"
        disabled={isImporting}
        onChange={importSelected}
      />
      <Button
        type="button"
        variant={variant}
        disabled={isImporting}
        onClick={() => fileInput.current?.click()}
      >
        <DownloadIcon />
        {isImporting ? "Importing…" : "Import from SurfSense cloud"}
      </Button>
      {error ? (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      ) : null}
    </div>
  )
}
