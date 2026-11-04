import { useRef, useState, type ChangeEvent } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Upload01Icon } from "@/components/ui/icons"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { intl } from "@/i18n/intl"
import { cn } from "@/lib/utils"

import { importPackFile, type PackInfo } from "../api"
import { jobTitle } from "../catalog"
import { importErrorText, packTooLargeText } from "../job-error-text"
import { jobsKeys } from "../query-keys"

import { forgetDeliveries } from "./download-job-packs"

// The backend's cap (MAX_PACK_BYTES), checked first so a larger file is never sent.
const MAX_PACK_BYTES = 50 * 1024 * 1024

const versionsOf = (packs: readonly PackInfo[] | undefined) =>
  new Set((packs ?? []).map((pack) => `${pack.id}@${pack.version}`))

// The pack the import put in place; none when it was the version already here.
const addedPack = (before: Set<string>, packs: readonly PackInfo[]) =>
  packs.find((pack) => !before.has(`${pack.id}@${pack.version}`))

const entitlementsOf = (pack: PackInfo) =>
  pack.jobs.flatMap((job) => (job.entitlement ? [job.entitlement] : []))

function installedToast(added: PackInfo | undefined) {
  if (!added) {
    toast.success(
      intl.formatMessage({
        id: "jobs_import_same_toast",
        defaultMessage: "That version is already installed",
      })
    )
    return
  }
  const [first] = added.jobs
  toast.success(
    intl.formatMessage(
      {
        id: "jobs_import_installed_toast",
        defaultMessage: "{job} version {version} is installed",
      },
      {
        job: first ? jobTitle(first.entitlement, first.name) : added.name,
        version: added.version,
      }
    )
  )
}

/** A job pack's .zip from SurfSense support, for a computer that cannot
 *  reach the license server. Only a pack SurfSense signed installs. */
export function ImportPackButton({
  disabled = false,
  size = "default",
  className,
}: {
  disabled?: boolean
  size?: "default" | "sm"
  className?: string
}) {
  const queryClient = useQueryClient()
  const fileInput = useRef<HTMLInputElement>(null)
  const [tooLarge, setTooLarge] = useState(false)
  const importing = useMutation({
    mutationFn: async (file: File) => {
      const before = versionsOf(
        queryClient.getQueryData<PackInfo[]>(jobsKeys.packs())
      )
      return { before, packs: await importPackFile(file) }
    },
    onSuccess: ({ before, packs }) => {
      queryClient.setQueryData(jobsKeys.packs(), packs)
      void queryClient.invalidateQueries({ queryKey: jobsKeys.settingsAll() })
      const added = addedPack(before, packs)
      // Its jobs are on this computer now, whatever their last download said.
      if (added) forgetDeliveries(queryClient, entitlementsOf(added))
      installedToast(added)
    },
  })

  const pick = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ""
    if (!file) return
    importing.reset()
    setTooLarge(file.size > MAX_PACK_BYTES)
    if (file.size <= MAX_PACK_BYTES) importing.mutate(file)
  }

  const error = tooLarge
    ? packTooLargeText()
    : importing.error
      ? importErrorText(importing.error)
      : null

  return (
    <div className={cn("flex flex-col items-start gap-1.5", className)}>
      <Input
        ref={fileInput}
        type="file"
        accept=".zip"
        className="sr-only"
        aria-label={intl.formatMessage({
          id: "jobs_import_file_aria",
          defaultMessage: "Choose a job pack file",
        })}
        disabled={disabled || importing.isPending}
        onChange={pick}
      />
      <Button
        type="button"
        variant="outline"
        size={size}
        disabled={disabled || importing.isPending}
        onClick={() => fileInput.current?.click()}
      >
        {importing.isPending ? (
          <Spinner data-icon="inline-start" />
        ) : (
          <Upload01Icon data-icon="inline-start" />
        )}
        {importing.isPending
          ? intl.formatMessage({
              id: "jobs_import_importing_status",
              defaultMessage: "Importing…",
            })
          : intl.formatMessage({
              id: "jobs_import_button",
              defaultMessage: "Import pack file",
            })}
      </Button>
      {error ? (
        <p role="alert" className="text-sm text-pretty text-destructive">
          {error}
        </p>
      ) : null}
    </div>
  )
}
