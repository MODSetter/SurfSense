import { useEffect, useRef, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import {
  deleteLocalModel,
  getModelCatalog,
  installCatalogModel,
  type CatalogRow,
  type InstallEvent,
  type RepoBuild,
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

  // No refresh parameter and no rescan mutation: the catalog is the manifest
  // plus a directory listing, priced locally, so there is nothing to re-probe.
  const catalog = useQuery({
    queryKey: catalogQueryKey,
    queryFn: ({ signal }) => getModelCatalog(signal),
  })

  // Curated rows and searched builds install through one path, because the id
  // is opaque either way and the server cannot tell them apart.
  const install = useMutation({
    mutationFn: async (target: CatalogRow | RepoBuild) => {
      const nextController = new AbortController()
      controller.current = nextController
      setInstallState({
        status: "installing",
        catalogId: target.catalog_id,
        event: { type: "starting", message: "Preparing download" },
      })
      return installCatalogModel(
        target.catalog_id,
        (event) =>
          setInstallState({
            status: "installing",
            catalogId: target.catalog_id,
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
        provider: "llamacpp",
        connection_id: null,
        name: row.variant_model_id,
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
    mutationFn: (target: { variant_model_id: string }) =>
      deleteLocalModel(target.variant_model_id),
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
    install,
    installState,
    cancelInstall: () => controller.current?.abort(),
    deleteModel,
    selectInstalled,
  }
}
