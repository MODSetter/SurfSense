import { useMemo } from "react"
import { useQueryClient } from "@tanstack/react-query"

import { errorToast } from "@/features/feedback/error-toast"
import { intl } from "@/i18n/intl"

import type { ModelType } from "../../model-type"
import { cancelInstall, startInstall } from "./api"
import { noteStarted } from "./feed"
import { isRunning } from "./job-state"
import { useInstalls } from "./use-installs"

function messageFrom(error: unknown) {
  return error instanceof Error
    ? error.message
    : intl.formatMessage({
        id: "models_install_error",
        defaultMessage: "Could not install this model",
      })
}

/**
 * Starting and cancelling installs, and the ones running. `select` is whether
 * a finished install becomes the model in use, for `modelType` when given.
 */
export function useInstall({
  select,
  modelType,
}: {
  select: boolean
  modelType?: ModelType
}) {
  const client = useQueryClient()
  const jobs = useInstalls()
  const installs = useMemo(() => jobs.filter(isRunning), [jobs])

  const install = async (catalogId: string) => {
    try {
      noteStarted(client, await startInstall(catalogId, { select, modelType }))
    } catch (error) {
      errorToast(messageFrom(error), { id: "model-install-error" })
    }
  }

  const cancel = (jobId: string) => {
    // A 404 means it already ended, which the feed reports.
    void cancelInstall(jobId).catch(() => undefined)
  }

  return { installs, install, cancel }
}
