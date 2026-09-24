/**
 * What a model is for, mirroring the backend's `ModelType`. The user picks one
 * model per type, so a type is also the slot a selection fills.
 */
export const MODEL_TYPES = [
  "text_gen",
  "image_gen",
  "image_edit",
  "video_gen",
  "audio_gen",
] as const

export type ModelType = (typeof MODEL_TYPES)[number]

/** How copy names a slot, as in "Use gpt-4o for chat". */
export const SLOT_NAMES: Record<ModelType, string> = {
  text_gen: "chat",
  image_gen: "image",
  image_edit: "image editing",
  video_gen: "video",
  audio_gen: "audio",
}
