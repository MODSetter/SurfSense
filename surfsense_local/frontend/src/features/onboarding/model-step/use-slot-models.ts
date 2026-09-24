import type { LocalRow } from "@/features/models/local/chat/api"
import { describeHardware } from "@/features/models/local/chat/describe-hardware"
import { useLocalChatCatalog } from "@/features/models/local/chat/use-local-chat-catalog"
import { useLocalImageCatalog } from "@/features/models/local/image/use-local-image-catalog"
import { useChatModels } from "@/features/models/your-models/use-chat-models"
import { useImageModels } from "@/features/models/your-models/use-image-models"
import type { InUse } from "@/features/models/your-models/your-model-row"

import type { OnboardingSlot } from "./slot"

export type SlotModels = {
  /** The slot's local rows: tested ones and anything already on disk. */
  rows: LocalRow[]
  /** What the rows were priced against, where the engine prices them at all. */
  hardware: string[] | null
  inUse: InUse | null
  isPending: boolean
  error: Error | null
}

function useChatSlot(): SlotModels {
  const models = useChatModels()
  const catalog = useLocalChatCatalog()
  return {
    rows: (catalog.data?.rows ?? []).filter((row) => row.engine !== "sdcpp"),
    hardware: catalog.data?.budget
      ? describeHardware(catalog.data.budget, catalog.data.gpu_status)
      : null,
    inUse: models.inUse,
    isPending: models.isPending,
    error: models.error,
  }
}

function useImageSlot(): SlotModels {
  const models = useImageModels()
  const catalog = useLocalImageCatalog()
  return {
    rows: catalog.data ?? [],
    // sd.cpp has no fit estimate, so there is nothing to say about the machine.
    hardware: null,
    inUse: models.inUse,
    isPending: models.isPending,
    error: models.error,
  }
}

/** One hook per slot, picked once per step, so the settings hooks stay the source. */
export const slotModels: Record<OnboardingSlot, () => SlotModels> = {
  text_gen: useChatSlot,
  image_gen: useImageSlot,
}
