import type { SdCppSlot } from "../local/image/api"
import { useLocalImageCatalog } from "../local/image/use-local-image-catalog"
import { useConnections } from "../remote/connections/use-connections"
import { useSelection } from "../selection/use-selection"
import {
  describeInUse,
  type YourModelRow,
  type YourModels,
} from "./your-model-row"

/** Every image model on disk that can fill `slot`, and the one in use for it
 *  wherever it runs. */
export function useImageModels(slot: SdCppSlot = "image_gen"): YourModels {
  const catalog = useLocalImageCatalog(slot)
  const selection = useSelection(slot)
  const connections = useConnections()
  const rows = catalog.data ?? []

  const local: YourModelRow[] = rows.flatMap((row) =>
    row.builds.flatMap((build) =>
      build.installed_as === null
        ? []
        : [
            {
              key: build.installed_as,
              name: row.name,
              selected: build.selected,
              badges: [],
              // Nothing reports whether sd-server is up yet, so no "Starting…".
              note: row.runnable ? null : row.not_runnable_reason,
              target: {
                provider: "sdcpp",
                connection_id: null,
                name: build.installed_as,
              },
              // As with chat: deleting the one in use clears the image slot,
              // and sd-server stops once the API reports no model.
              removeId: build.installed_as,
            },
          ]
    )
  )

  return {
    local,
    inUse: describeInUse(selection.data, local, connections.data),
    // A failed local catalog still leaves servers usable, so it is not an error.
    isPending: catalog.isPending || selection.isPending,
    error: selection.error,
    canDownload: rows.length > 0,
  }
}
