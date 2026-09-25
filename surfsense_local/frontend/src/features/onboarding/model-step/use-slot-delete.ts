import { useDeleteLocalAudioModel } from "@/features/models/local/audio/use-delete-local-audio-model"
import { useDeleteLocalChatModel } from "@/features/models/local/chat/use-delete-local-chat-model"
import { useDeleteLocalImageModel } from "@/features/models/local/image/use-delete-local-image-model"

import type { OnboardingSlot } from "./slot"

type SlotDelete = {
  mutateAsync: (installedAs: string) => Promise<unknown>
  isPending: boolean
}

// No callback on clearing the chat slot: the step reads the selection itself,
// so Continue disables on its own when the model in use is deleted.
function useDeleteChat(): SlotDelete {
  return useDeleteLocalChatModel()
}

/** Settings' delete hooks, one per slot, picked once per step. */
export const slotDeletes: Record<OnboardingSlot, () => SlotDelete> = {
  text_gen: useDeleteChat,
  image_gen: useDeleteLocalImageModel,
  image_edit: useDeleteLocalImageModel,
  video_gen: useDeleteLocalImageModel,
  audio_gen: useDeleteLocalAudioModel,
}
