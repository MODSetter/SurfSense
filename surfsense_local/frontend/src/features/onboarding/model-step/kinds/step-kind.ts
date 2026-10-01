import type { OnboardingSlot } from "./slot"

/**
 * What an onboarding step chooses: a slot's model, or the library's embedding
 * model, which is chosen once and is never a slot (ADR 0037).
 */
export type OnboardingStepKind = OnboardingSlot | "embedding"

/** The slot a step fills, or null for the embedding step. */
export function slotOf(kind: OnboardingStepKind): OnboardingSlot | null {
  return kind === "embedding" ? null : kind
}
