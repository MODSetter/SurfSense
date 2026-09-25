import type { LocalRow } from "@/features/models/local/chat/api"
import { describeHardware } from "@/features/models/local/chat/describe-hardware"
import { useLocalChatCatalog } from "@/features/models/local/chat/use-local-chat-catalog"
import { useLocalImageCatalog } from "@/features/models/local/image/use-local-image-catalog"
import { useAudioModels } from "@/features/models/your-models/use-audio-models"
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
    rows: (catalog.data?.rows ?? []).filter((row) => row.engine === "llamacpp"),
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

function useImageEditSlot(): SlotModels {
  const models = useImageModels("image_edit")
  const catalog = useLocalImageCatalog("image_edit")
  const rows = catalog.data ?? []
  // The image model chosen earlier leads when it edits too: one Use,
  // nothing more to download.
  const forImages = (row: LocalRow) =>
    row.builds.some((build) => build.selected_for?.includes("image_gen"))
  return {
    rows: [...rows.filter(forImages), ...rows.filter((row) => !forImages(row))],
    hardware: null,
    inUse: models.inUse,
    isPending: models.isPending,
    error: models.error,
  }
}

function useVideoSlot(): SlotModels {
  const models = useImageModels("video_gen")
  const catalog = useLocalImageCatalog("video_gen")
  return {
    rows: catalog.data ?? [],
    // sd.cpp has no fit estimate for video either.
    hardware: null,
    inUse: models.inUse,
    isPending: models.isPending,
    error: models.error,
  }
}

function useAudioSlot(): SlotModels {
  const models = useAudioModels()
  // The whole catalog, not audio's own view of it: the list reads chat's rows.
  const catalog = useLocalChatCatalog()
  return {
    // Without voicing figures Settings lists no row either, so neither does this.
    rows: (catalog.data?.rows ?? []).filter(
      (row) => row.engine === "audiocpp" && row.voicing
    ),
    // audio.cpp has no fit estimate either.
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
  image_edit: useImageEditSlot,
  video_gen: useVideoSlot,
  audio_gen: useAudioSlot,
}
