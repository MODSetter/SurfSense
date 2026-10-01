import type { OnboardingStepKind } from "./step-kind"
import type { StepModels } from "./step-models"
import { useEmbeddingStep } from "./use-embedding-step"
import { useSlotStep } from "./use-slot-step"

const useTextGenStep = () => useSlotStep("text_gen")
const useImageGenStep = () => useSlotStep("image_gen")
const useImageEditStep = () => useSlotStep("image_edit")
const useVideoGenStep = () => useSlotStep("video_gen")
const useAudioGenStep = () => useSlotStep("audio_gen")

/** One hook per step, picked once per step: the steps differ only here. */
export const stepModels: Record<OnboardingStepKind, () => StepModels> = {
  text_gen: useTextGenStep,
  image_gen: useImageGenStep,
  image_edit: useImageEditStep,
  video_gen: useVideoGenStep,
  audio_gen: useAudioGenStep,
  embedding: useEmbeddingStep,
}
