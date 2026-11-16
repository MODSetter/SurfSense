export type TrialOutcome = "sent" | "already_claimed" | "refused" | "error";

/**
 * What a trial request came to, from the route's status (null when the request
 * never got an answer). 400 is the address refused: disposable, or rejected by
 * its own mail server. Rate limits, outages and anything unexpected are errors.
 */
export function trialOutcome(status: number | null): TrialOutcome {
	if (status !== null && status >= 200 && status < 300) return "sent";
	if (status === 409) return "already_claimed";
	if (status === 400) return "refused";
	return "error";
}
