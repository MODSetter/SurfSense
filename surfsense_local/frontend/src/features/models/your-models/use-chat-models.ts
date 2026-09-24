import { intl } from "@/i18n/intl"

import { useLocalChatCatalog } from "../local/chat/use-local-chat-catalog"
import { useConnections } from "../remote/connections/use-connections"
import { useSelection } from "../selection/use-selection"
import {
  describeInUse,
  type YourModelRow,
  type YourModels,
} from "./your-model-row"

/** Every chat model on disk, and the one in use wherever it runs. */
export function useChatModels(): YourModels {
  const catalog = useLocalChatCatalog()
  const selection = useSelection("text_gen")
  const connections = useConnections()

  // Curated or not: for a model installed from search this is the only place
  // it appears. Image and audio rows are not chat models.
  const rows = (catalog.data?.rows ?? []).filter(
    (row) => row.engine === "llamacpp"
  )
  const local: YourModelRow[] = rows.flatMap((row) =>
    row.builds.flatMap((build) =>
      build.installed_as === null
        ? []
        : [
            {
              key: build.installed_as,
              name:
                row.origin === "curated"
                  ? `${row.name} ${build.quantization}`
                  : row.name,
              selected: build.selected,
              badges: build.reads_images
                ? [
                    intl.formatMessage({
                      id: "models_your_models_vision_label",
                    }),
                  ]
                : [],
              note: row.runnable ? null : row.not_runnable_reason,
              target: row.selectable_for.includes("text_gen")
                ? {
                    provider: "llamacpp",
                    connection_id: null,
                    name: build.installed_as,
                  }
                : null,
              removeId: build.installed_as,
            },
          ]
    )
  )

  return {
    local,
    inUse: describeInUse(selection.data, local, connections.data),
    isPending: catalog.isPending || selection.isPending,
    error: catalog.error ?? selection.error,
    canDownload: true,
  }
}
