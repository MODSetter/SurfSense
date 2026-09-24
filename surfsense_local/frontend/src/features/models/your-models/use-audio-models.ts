import { useLocalAudioCatalog } from "../local/audio/use-local-audio-catalog"
import { useConnections } from "../remote/connections/use-connections"
import { useSelection } from "../selection/use-selection"
import {
  describeInUse,
  type YourModelRow,
  type YourModels,
} from "./your-model-row"

/** Every audio model on disk, and the one in use wherever it runs. */
export function useAudioModels(): YourModels {
  const catalog = useLocalAudioCatalog()
  const selection = useSelection("audio_gen")
  const connections = useConnections()
  const models = catalog.data?.models ?? []

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
    inUse: describeInUse(selection.data, local, connections.data),
    // A failed local catalog still leaves servers usable, so it is not an error.
    isPending: catalog.isPending || selection.isPending,
    error: selection.error,
    canDownload: models.length > 0,
  }
}
