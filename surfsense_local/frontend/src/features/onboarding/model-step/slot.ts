import type { ModelType } from "@/features/models/model-type"

/** The slots onboarding asks for. The others are chosen later, in Settings. */
export type OnboardingSlot = Extract<
  ModelType,
  "text_gen" | "image_gen" | "image_edit" | "video_gen" | "audio_gen"
>

/** The local runtime that runs each slot's downloads. */
export const LOCAL_PROVIDER: Record<OnboardingSlot, string> = {
  text_gen: "llamacpp",
  image_gen: "sdcpp",
  image_edit: "sdcpp",
  video_gen: "sdcpp",
  audio_gen: "audiocpp",
}
