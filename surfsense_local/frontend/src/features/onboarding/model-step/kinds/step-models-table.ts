import type { OnboardingStepKind } from "./step-kind"
import type { StepModels } from "./step-models"
import { useChatStep } from "./use-chat-step"
import { useEmbeddingStep } from "./use-embedding-step"

/** One hook per step, picked once per step: the steps differ only here. */
export const stepModels: Record<OnboardingStepKind, () => StepModels> = {
  text_gen: useChatStep,
  embedding: useEmbeddingStep,
}
