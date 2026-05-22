"use client";

import Script from "next/script";

const ADSENSE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_ADSENSE_CLIENT_ID;

/**
 * Loads the Google AdSense library (adsbygoogle.js). Mount this once on any
 * route that renders <AdUnit /> instances. Scoped per-route (not in the root
 * layout) so the third-party script is not shipped on unrelated pages.
 *
 * Renders nothing if NEXT_PUBLIC_GOOGLE_ADSENSE_CLIENT_ID is unset, so dev and
 * preview deployments without the env var stay ad-free.
 */
export function AdSenseScript() {
	if (!ADSENSE_CLIENT_ID) return null;

	return (
		<Script
			id="adsbygoogle-init"
			async
			strategy="afterInteractive"
			src={`https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${ADSENSE_CLIENT_ID}`}
			crossOrigin="anonymous"
		/>
	);
}
