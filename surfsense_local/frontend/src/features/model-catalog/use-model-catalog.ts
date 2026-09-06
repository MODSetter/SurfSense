import { useEffect, useRef, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  getModelCatalog,
  installCatalogModel,
  type CatalogRow,
  type InstallEvent,
} from "./api"
import {
  setGenerationSelection,
  type ModelSelection,
} from "@/features/model-selection/api"

export const catalogQueryKey = ["model-catalog"] as const
export const selectionQueryKey = ["model-selection"] as const

export type InstallState =
  | { status: "idle" }
  | {
      status: "installing"
      catalogId: string
      event: InstallEvent
    }
  | { status: "cancelled"; catalogId: string }
  | { status: "error"; catalogId: string; message: string }

function isAbort(error: unknown) {
  return error instanceof DOMException && error.name === "AbortError"
}

function messageFrom(error: unknown) {
  return error instanceof Error ? error.message : "Could not install this model"
}

export function useModelCatalog(
  onSelected?: (selection: ModelSelection) => void
) {
  const queryClient = useQueryClient()
  const controller = useRef<AbortController | null>(null)
  const [installState, setInstallState] = useState<InstallState>({
    status: "idle",
  })

  const catalog = useQuery({
    queryKey: catalogQueryKey,
    queryFn: ({ signal }) => getModelCatalog(false, signal),
  })

  const rescan = useMutation({
    mutationFn: () => getModelCatalog(true),
    onSuccess: (data) => queryClient.setQueryData(catalogQueryKey, data),
  })

  const install = useMutation({
    mutationFn: async (row: CatalogRow) => {
      const nextController = new AbortController()
      controller.current = nextController
      setInstallState({
        status: "installing",
        catalogId: row.catalog_id,
        event: { type: "starting", message: "Preparing download" },
      })
      return installCatalogModel(
        row.catalog_id,
        (event) =>
          setInstallState({
            status: "installing",
            catalogId: row.catalog_id,
            event,
          }),
        nextController.signal
      )
    },
    onSuccess: async (selection) => {
      controller.current = null
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: catalogQueryKey }),
        queryClient.invalidateQueries({ queryKey: selectionQueryKey }),
      ])
      setInstallState({ status: "idle" })
      onSelected?.(selection)
    },
    onError: (error, row) => {
      controller.current = null
      setInstallState(
        isAbort(error)
          ? { status: "cancelled", catalogId: row.catalog_id }
          : {
              status: "error",
              catalogId: row.catalog_id,
              message: messageFrom(error),
            }
      )
    },
  })

  const selectInstalled = useMutation({
    mutationFn: (row: CatalogRow) =>
      setGenerationSelection({
        provider: row.runtime,
        name: row.runtime_model,
      }),
    onSuccess: async (selection) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: catalogQueryKey }),
        queryClient.invalidateQueries({ queryKey: selectionQueryKey }),
      ])
      onSelected?.(selection)
    },
  })

  useEffect(() => () => controller.current?.abort(), [])

  return {
    catalog,
    rescan,
    install,
    installState,
    cancelInstall: () => controller.current?.abort(),
    selectInstalled,
  }
}
