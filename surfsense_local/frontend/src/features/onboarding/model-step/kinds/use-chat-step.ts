import { describeHardware } from "@/features/models/local/chat/describe-hardware"
import { useLocalChatCatalog } from "@/features/models/local/chat/use-local-chat-catalog"
import { toastUseFailure } from "@/features/models/selection/toast-use-failure"
import { useSelect } from "@/features/models/selection/use-selection"
import { useChatModels } from "@/features/models/your-models/use-chat-models"

import type { StepModels } from "./step-models"

/** The chat step: Use saves the selection, and a download becomes it. */
export function useChatStep(): StepModels {
  const models = useChatModels()
  const catalog = useLocalChatCatalog()
  const select = useSelect("text_gen")
  return {
    rows: (catalog.data?.rows ?? []).filter((row) => row.engine === "llamacpp"),
    hardware: catalog.data?.budget
      ? describeHardware(catalog.data.budget, catalog.data.gpu_status)
      : null,
    inUse: models.inUse,
    isPending: models.isPending,
    error: models.error,
    use: (name) =>
      void select
        .mutateAsync({
          target: { provider: "llamacpp", connection_id: null, name },
        })
        .catch(toastUseFailure),
    choosing: select.isPending,
    install: { select: true, modelType: "text_gen" },
    value: null,
  }
}
