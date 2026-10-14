import { useLocalSpeechCatalog } from "../local/transcription/use-local-speech-catalog"
import { useSelection } from "../selection/use-selection"
import {
  describeInUse,
  type YourModelRow,
  type YourModels,
} from "./your-model-row"

/** Every speech recognition model on disk, and the one in use. Local only. */
export function useSpeechModels(): YourModels {
  const catalog = useLocalSpeechCatalog()
  const selection = useSelection("speech_to_text")
  const models = catalog.data ?? []

  const local: YourModelRow[] = models.flatMap((model) =>
    model.installed_as === null
      ? []
      : [
          {
            key: model.installed_as,
            name: model.label,
            selected: model.selected,
            badges: [],
            // The server loads a model on its first request; nothing to report.
            note: null,
            target: {
              provider: "audiocpp",
              connection_id: null,
              name: model.installed_as,
            },
            removeId: model.installed_as,
          },
        ]
  )

  return {
    local,
    // No server serves this slot, so there is none to name.
    inUse: describeInUse(selection.data, local, undefined),
    isPending: catalog.isPending || selection.isPending,
    // With no server to fall back on, a failed catalog leaves nothing to show.
    error: selection.error ?? catalog.error,
    canDownload: models.length > 0,
  }
}
