import { useCallback, useEffect, useRef, useState } from "react"

import {
  getGenerationSelection,
  getProviderModels,
  getProviders,
  modelKey,
  setGenerationSelection,
  type ModelSelection,
  type Provider,
  type SelectableModel,
} from "./api"

export type ModelSelectionState =
  | { status: "loading" }
  | { status: "api-unavailable"; message: string }
  | {
      status: "ready"
      providers: Provider[]
      models: SelectableModel[]
      selection: ModelSelection | null
      staleSelection: boolean
      modelsLoading: boolean
      loadingProviders: string[]
    }

type SaveState =
  | { status: "idle" }
  | { status: "saving" }
  | { status: "saved" }
  | { status: "error"; message: string }

function messageFrom(error: unknown) {
  return error instanceof Error ? error.message : "An unexpected error occurred"
}

function isAbort(error: unknown) {
  return error instanceof DOMException && error.name === "AbortError"
}

async function fetchSelectionState(
  signal: AbortSignal,
  onProgress: (state: ModelSelectionState) => void
): Promise<ModelSelectionState> {
  let providers: Provider[]
  let selection: ModelSelection | null
  try {
    const result = await Promise.all([
      getProviders(signal),
      getGenerationSelection(signal),
    ])
    providers = result[0]
    selection = result[1]
  } catch (error) {
    if (isAbort(error)) {
      throw error
    }
    return { status: "api-unavailable", message: messageFrom(error) }
  }

  let models: SelectableModel[] = []
  const loadingProviders = new Set(
    providers
      .filter((provider) => provider.healthy)
      .map((provider) => provider.name)
  )
  const nextState = (modelsLoading: boolean): ModelSelectionState => {
    const sortedModels = models.toSorted(
      (left, right) =>
        left.provider.localeCompare(right.provider) ||
        left.name.localeCompare(right.name)
    )
    const selectionIsCurrent =
      selection !== null &&
      sortedModels.some((model) => modelKey(model) === modelKey(selection))

    return {
      status: "ready",
      providers,
      models: sortedModels,
      selection,
      staleSelection:
        !modelsLoading && selection !== null && !selectionIsCurrent,
      modelsLoading,
      loadingProviders: [...loadingProviders],
    }
  }

  onProgress(nextState(loadingProviders.size > 0))
  await Promise.all(
    providers
      .filter((provider) => provider.healthy)
      .map(async (provider) => {
        try {
          const providerModels = await getProviderModels(provider.name, signal)
          models = [
            ...models,
            ...providerModels
              .filter(
                (model) =>
                  model.installed && model.capabilities.includes("completion")
              )
              .map((model) => ({ ...model, provider: provider.name })),
          ]
        } catch (error) {
          if (signal.aborted) {
            throw error
          }
        } finally {
          loadingProviders.delete(provider.name)
          onProgress(nextState(loadingProviders.size > 0))
        }
      })
  )
  return nextState(false)
}

export function useModelSelection() {
  const [state, setState] = useState<ModelSelectionState>({
    status: "loading",
  })
  const [draftKey, setDraftKey] = useState<string | null>(null)
  const [saveState, setSaveState] = useState<SaveState>({ status: "idle" })
  const [isRefreshing, setIsRefreshing] = useState(false)
  const loadController = useRef<AbortController | null>(null)
  const saveController = useRef<AbortController | null>(null)

  const acceptState = useCallback((next: ModelSelectionState) => {
    if (next.status === "ready") {
      setDraftKey((current) => {
        if (next.modelsLoading) {
          return current ?? (next.selection ? modelKey(next.selection) : null)
        }
        if (
          current !== null &&
          next.models.some((model) => modelKey(model) === current)
        ) {
          return current
        }
        const selection = next.selection
        const selectionIsCurrent =
          selection !== null &&
          next.models.some((model) => modelKey(model) === modelKey(selection))
        return selection !== null && selectionIsCurrent
          ? modelKey(selection)
          : null
      })
    }
    setState(next)
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    loadController.current = controller
    const acceptProgress = (next: ModelSelectionState) => {
      if (loadController.current === controller) {
        acceptState(next)
      }
    }
    void fetchSelectionState(controller.signal, acceptProgress)
      .then((next) => {
        acceptProgress(next)
      })
      .catch(() => undefined)

    return () => {
      if (loadController.current === controller) {
        loadController.current = null
      }
      controller.abort()
      saveController.current?.abort()
    }
  }, [acceptState])

  const select = (value: string) => {
    setDraftKey(value)
    setSaveState({ status: "idle" })
  }

  // Silent reloads let the caller own the spinner; the footer Refresh stays idle.
  const refresh = async (options?: { silent?: boolean }) => {
    loadController.current?.abort()
    const controller = new AbortController()
    loadController.current = controller
    if (!options?.silent) {
      setIsRefreshing(true)
    }
    setSaveState({ status: "idle" })

    try {
      const acceptProgress = (next: ModelSelectionState) => {
        if (loadController.current === controller) {
          acceptState(next)
        }
      }
      const next = await fetchSelectionState(controller.signal, acceptProgress)
      acceptProgress(next)
    } catch {
      // Aborted by a newer refresh or unmount.
    } finally {
      if (!options?.silent && loadController.current === controller) {
        setIsRefreshing(false)
      }
    }
  }

  const save = async () => {
    if (state.status !== "ready" || draftKey === null) {
      return null
    }
    const model = state.models.find(
      (candidate) => modelKey(candidate) === draftKey
    )
    if (!model) {
      return null
    }

    saveController.current?.abort()
    const controller = new AbortController()
    saveController.current = controller
    setSaveState({ status: "saving" })

    try {
      const selection = await setGenerationSelection(model, controller.signal)
      setState((current) =>
        current.status === "ready"
          ? { ...current, selection, staleSelection: false }
          : current
      )
      setSaveState({ status: "saved" })
      return selection
    } catch (error) {
      if (!isAbort(error)) {
        setSaveState({ status: "error", message: messageFrom(error) })
      }
      return null
    }
  }

  return {
    state,
    draftKey,
    saveState,
    isRefreshing,
    select,
    refresh,
    save,
  }
}
