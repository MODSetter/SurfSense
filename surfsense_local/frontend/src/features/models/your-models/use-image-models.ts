import { intl } from "@/i18n/intl"

import type { ImageServerState, SdCppSlot } from "../local/image/api"
import { useLocalImageCatalog } from "../local/image/use-local-image-catalog"
import { useLocalImageState } from "../local/image/use-local-image-state"
import { useConnections } from "../remote/connections/use-connections"
import { useSelection } from "../selection/use-selection"
import {
  describeInUse,
  type YourModelRow,
  type YourModels,
} from "./your-model-row"

/** Every image model on disk that can fill `slot`, and the one in use for it
 *  wherever it runs. */
const SERVER_NOTE: Record<ImageServerState, (() => string) | null> = {
  none: null,
  idle: () =>
    intl.formatMessage({
      id: "models_image_server_idle_status",
      defaultMessage: "Starts when Studio needs it",
    }),
  running: () =>
    intl.formatMessage({
      id: "models_image_server_running_status",
      defaultMessage: "Running",
    }),
  // Its build is no longer installed, so it has no row: InUseSummary names it
  // "Not found on this computer" instead.
  missing: null,
}

export function useImageModels(slot: SdCppSlot = "image_gen"): YourModels {
  const catalog = useLocalImageCatalog(slot)
  const selection = useSelection(slot)
  const connections = useConnections()
  const rows = catalog.data ?? []
  const server = useLocalImageState(
    slot,
    rows.some((row) => row.builds.some((build) => build.selected))
  )

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
              // sd-server starts lazily, so the one in use says whether it is up.
              note: !row.runnable
                ? row.not_runnable_reason
                : build.selected && server.data
                  ? (SERVER_NOTE[server.data]?.() ?? null)
                  : null,
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
