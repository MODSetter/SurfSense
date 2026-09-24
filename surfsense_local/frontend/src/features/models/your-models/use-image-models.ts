import { useLocalImageCatalog } from "../local/image/use-local-image-catalog"
import { useConnections } from "../remote/connections/use-connections"
import { useSelection } from "../selection/use-selection"
import {
  describeInUse,
  type YourModelRow,
  type YourModels,
} from "./your-model-row"

/** Every image model on disk, and the one in use wherever it runs. */
export function useImageModels(): YourModels {
  const catalog = useLocalImageCatalog()
  const selection = useSelection("image_gen")
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
            // Nothing reports whether sd-server is up yet, so no "Starting…".
            note: null,
            target: {
              provider: "sdcpp",
              connection_id: null,
              name: model.installed_as,
            },
            // The server is running it; removing the file under it is refused.
            removeId: model.selected ? null : model.installed_as,
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
