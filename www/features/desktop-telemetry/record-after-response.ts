import { after } from "next/server";
import { capturePersonlessEvent, type PersonlessEvent } from "./personless-capture";

/**
 * Captures once the response has gone, so PostHog being slow or down never
 * delays an update check or a usage report. On Vercel, after() keeps the
 * function alive until the send settles.
 */
export function recordAfterResponse(event: PersonlessEvent): void {
	after(() => capturePersonlessEvent(event));
}
