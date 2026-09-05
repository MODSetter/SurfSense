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

type LoadedState = {
  providers: Provider[]
  selection: ModelSelection | null
  staleSelection: boolean
}

export type ModelSelectionState =
  | { status: "loading" }
  | { status: "api-unavailable"; message: string }
  | { status: "provider-unavailable"; message: string }
  | ({ status: "empty" } & LoadedState)
  | ({ status: "ready"; models: SelectableModel[] } & LoadedState)

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
  signal: AbortSignal
): Promise<ModelSelectionState> {
  let providers
  let selection
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

  const healthyProviders = providers.filter((provider) => provider.healthy)
  if (healthyProviders.length === 0) {
    return {
      status: "provider-unavailable",
      message: "No local model provider is currently reachable.",
    }
  }

  try {
    const modelGroups = await Promise.all(
      healthyProviders.map(async (provider) => {
        const models = await getProviderModels(provider.name, signal)
        return models
          .filter(
            (model) =>
              model.installed && model.capabilities.includes("completion")
          )
          .map((model) => ({ ...model, provider: provider.name }))
      })
    )
    const models = modelGroups
      .flat()
      .toSorted(
        (left, right) =>
          left.provider.localeCompare(right.provider) ||
          left.name.localeCompare(right.name)
      )
    const selectionIsCurrent =
      selection !== null &&
      models.some((model) => modelKey(model) === modelKey(selection))
    const loadedState = {
      providers,
      selection,
      staleSelection: selection !== null && !selectionIsCurrent,
    }

    return models.length === 0
      ? { status: "empty", ...loadedState }
      : { status: "ready", models, ...loadedState }
  } catch (error) {
    if (isAbort(error)) {
      throw error
    }
    return { status: "provider-unavailable", message: messageFrom(error) }
  }
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
    } else if (next.status === "empty") {
      setDraftKey(null)
    }
    setState(next)
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    loadController.current = controller
    void fetchSelectionState(controller.signal)
      .then((next) => {
        if (loadController.current === controller) {
          acceptState(next)
        }
      })
      .catch(() => undefined)

    return () => {
      controller.abort()
      saveController.current?.abort()
    }
  }, [acceptState])

  const select = (value: string) => {
    setDraftKey(value)
    setSaveState({ status: "idle" })
  }

  const refresh = async () => {
    loadController.current?.abort()
    const controller = new AbortController()
    loadController.current = controller
    setIsRefreshing(true)
    setSaveState({ status: "idle" })

    try {
      const next = await fetchSelectionState(controller.signal)
      if (loadController.current === controller) {
        acceptState(next)
      }
    } catch {
      // A newer refresh or unmount deliberately aborts the stale request.
    } finally {
      if (loadController.current === controller) {
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
