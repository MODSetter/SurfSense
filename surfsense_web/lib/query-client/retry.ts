import { AppError } from "../error";

/** Attempts after the first, so 2 means three tries in total. */
export const MAX_QUERY_RETRIES = 2;

/**
 * Retry only failures a second attempt could plausibly fix.
 *
 * TanStack's default retries any error three times, which is wrong in both
 * directions: a 403 or a validation error is retried pointlessly (delaying the
 * message the user needs), while individual queries opting out with
 * `retry: false` lose the one case retrying exists for — a dropped connection.
 * A single blip then leaves that query permanently failed for the session.
 */
export function shouldRetryQuery(failureCount: number, error: unknown): boolean {
	if (failureCount >= MAX_QUERY_RETRIES) return false;
	if (!(error instanceof AppError)) return false;
	// A NetworkError never reached a server, so it carries no status.
	if (error.status === undefined) return error.code === "NETWORK_ERROR";
	return error.status >= 500;
}
