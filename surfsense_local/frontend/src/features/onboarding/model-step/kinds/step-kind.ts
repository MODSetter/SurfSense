/**
 * What an onboarding step chooses: the chat model, or the library's embedding
 * model, which is chosen once and is never a slot (ADR 0037).
 */
export type OnboardingStepKind = "text_gen" | "embedding"
