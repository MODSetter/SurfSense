/**
 * Crawlers, link previews and the scanners mail providers run on every link
 * before a person clicks it. Matched on the User-Agent only, which is never
 * stored. A heuristic: a scanner posing as a browser is still counted.
 */
const AUTOMATED_AGENT =
	/bot\b|bot\/|crawl|spider|slurp|preview|scanner|headless|monitor|validator|embedly|iframely|facebookexternalhit|whatsapp|telegram|skypeuripreview|ms-office|microsoft office|safelinks|barracuda|mimecast|proofpoint|cloudmark|trendmicro|symantec|python|curl\/|wget\/|go-http-client|java\/|okhttp|axios|node-fetch|undici|libwww|httpclient/i;

export function isAutomatedFetch(userAgent: string | null): boolean {
	if (!userAgent?.trim()) return true;
	return AUTOMATED_AGENT.test(userAgent);
}
