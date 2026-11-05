/**
 * The Stripe Payment Link with the visitor's channel as `client_reference_id`,
 * which Stripe hands back on the checkout session for the purchase event. Only
 * a channel tag goes there, never a person or browser id.
 *
 * The `/contact` fallback, used when no Payment Link is configured, takes no
 * parameters.
 */
export function isPaymentLink(buyUrl: string): boolean {
	return /^https:\/\//.test(buyUrl);
}

export function checkoutHref(buyUrl: string, channel: string): string {
	if (!isPaymentLink(buyUrl)) return buyUrl;
	try {
		const url = new URL(buyUrl);
		url.searchParams.set("client_reference_id", channel);
		return url.toString();
	} catch {
		return buyUrl;
	}
}
