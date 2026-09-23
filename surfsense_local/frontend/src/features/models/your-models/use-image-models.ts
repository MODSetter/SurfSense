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
  const data = catalog.data
  const offered = data?.offered ?? false

  const local: YourModelRow[] = (offered ? (data?.models ?? []) : [])
    .filter((model) => model.installed)
    .map((model) => ({
      key: model.name,
      name: model.label,
      selected: model.selected,
      badges: [],
      note: model.selected && !data?.ready ? "Starting…" : null,
      target: {
        provider: data?.provider ?? "",
        connection_id: null,
        name: model.name,
      },
      // The server is running it; removing the file under it is refused.
      removeId: model.selected ? null : model.name,
    }))

  return {
    local,
    inUse: describeInUse(selection.data, local, connections.data),
    // A failed local catalog still leaves servers usable, so it is not an error.
    isPending: catalog.isPending || selection.isPending,
    error: selection.error,
    canDownload: offered && (data?.models?.length ?? 0) > 0,
  }
}
