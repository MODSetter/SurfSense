import type { ModelType } from "@/features/models/model-type"

/** The slots onboarding asks for. The others are chosen later, in Settings. */
export type OnboardingSlot = Extract<ModelType, "text_gen" | "image_gen">

/** The local runtime that runs each slot's downloads. */
export const LOCAL_PROVIDER: Record<OnboardingSlot, string> = {
  text_gen: "llamacpp",
  image_gen: "sdcpp",
}
