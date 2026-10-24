const COUNTRY_CODE = /^[A-Z]{2}$/;

/**
 * Country from the header Vercel derives at its edge, so the address itself
 * is never read here (docs/contracts/05-desktop-telemetry.md).
 */
export function requestCountry(headers: Headers): string {
	const country = headers.get("x-vercel-ip-country");
	return country && COUNTRY_CODE.test(country) ? country : "unknown";
}
