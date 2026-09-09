import { useEffect, useRef, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import {
  deleteLocalModel,
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

function isAbort(error: unknown) {
  return error instanceof DOMException && error.name === "AbortError"
}

function messageFrom(error: unknown) {
  return error instanceof Error ? error.message : "Could not install this model"
}

export function useModelCatalog(
  onSelected?: (selection: ModelSelection) => void,
  onModelUnavailable?: () => void,
  onModelsChanged?: () => void
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
    onError: (error) => {
      controller.current = null
      if (isAbort(error)) {
        toast.info("Installation cancelled. You can retry.", {
          id: "model-install-cancelled",
        })
        setInstallState({ status: "idle" })
      } else {
        toast.error(messageFrom(error), { id: "model-install-error" })
        setInstallState({ status: "idle" })
      }
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

  const deleteModel = useMutation({
    mutationFn: (row: CatalogRow) =>
      deleteLocalModel(row.runtime, row.runtime_model),
    onSuccess: async (result) => {
      if (result.selection_cleared) {
        onModelUnavailable?.()
      }
      onModelsChanged?.()
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: catalogQueryKey }),
        queryClient.invalidateQueries({ queryKey: selectionQueryKey }),
        queryClient.invalidateQueries({
          queryKey: ["installed-generation-models"],
        }),
      ])
    },
  })

  useEffect(() => () => controller.current?.abort(), [])

  return {
    catalog,
    rescan,
    install,
    installState,
    cancelInstall: () => controller.current?.abort(),
    deleteModel,
    selectInstalled,
  }
}
