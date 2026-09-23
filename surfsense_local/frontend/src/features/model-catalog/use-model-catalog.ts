import { useEffect, useRef, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import {
  deleteLocalModel,
  getModelCatalog,
  installCatalogModel,
  type InstallEvent,
  type LocalRow,
} from "./api"
import {
  setGenerationSelection,
  setSelection,
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

/** An installed build, and the engine whose selection it would fill. */
export type InstalledTarget = {
  installed_as: string
  engine: LocalRow["engine"]
}

/**
 * The parent hears only about the chat model: it holds that selection as the
 * app's model, and an image model chosen here must not replace it.
 */
function isChatSelection(selection: ModelSelection | null | undefined) {
  return selection?.model_type === "text_gen"
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

  // Curated and searched builds install through one path, because the id is
  // opaque either way. A searched build is read exactly before any bytes move,
  // and a refusal arrives as the stream's error, shown as a toast.
  const install = useMutation({
    mutationFn: async (target: { catalog_id: string }) => {
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
      if (isChatSelection(selection)) onSelected?.(selection)
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
    // The runtime's own name for the file, not a row. A model installed from
    // search has no curated row to carry it, and that list is the only place
    // it appears.
    mutationFn: (target: InstalledTarget) =>
      target.engine === "sdcpp"
        ? setSelection("image_gen", {
            provider: "sdcpp",
            connection_id: null,
            name: target.installed_as,
          })
        : setGenerationSelection({
            provider: "llamacpp",
            connection_id: null,
            name: target.installed_as,
          }),
    onSuccess: async (selection) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: catalogQueryKey }),
        queryClient.invalidateQueries({ queryKey: selectionQueryKey }),
      ])
      if (isChatSelection(selection)) onSelected?.(selection)
    },
  })

  const deleteModel = useMutation({
    mutationFn: (target: InstalledTarget) =>
      deleteLocalModel(target.installed_as),
    onSuccess: async (result, target) => {
      // Only the chat model's loss is the parent's to handle; losing the image
      // model only makes image formats unavailable, which Studio asks for.
      if (result.selection_cleared && target.engine !== "sdcpp") {
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
