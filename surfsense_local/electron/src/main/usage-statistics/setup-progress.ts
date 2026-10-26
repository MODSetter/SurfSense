// Setup's steps in the order onboarding reaches them (contract 05, week.onboarding).
// "unknown" is not a step: it never moves the furthest step nor sends a report.
export const SETUP_STEPS = [
  "not_started",
  "model_chosen",
  "model_ready",
  "first_source",
  "first_answer",
] as const

export type SetupStep = (typeof SETUP_STEPS)[number]

function rank(step: unknown): number {
  return SETUP_STEPS.indexOf(step as SetupStep)
}

export function setupStep(value: unknown): SetupStep | null {
  return rank(value) >= 0 ? (value as SetupStep) : null
}

export function setupFinished(reported: SetupStep | null): boolean {
  return reported === SETUP_STEPS[SETUP_STEPS.length - 1]
}

/** The later of the step reported so far and the one a report just carried. */
export function furthestStep(reported: SetupStep | null, carried: unknown): SetupStep | null {
  return rank(carried) > rank(reported) ? (carried as SetupStep) : reported
}

/**
 * A setup report is due for a step past any a report carried. "not_started" is
 * never one, so an install sends at most four.
 */
export function setupReportDue(current: unknown, reported: SetupStep | null): boolean {
  return rank(current) > Math.max(rank("not_started"), rank(reported))
}
