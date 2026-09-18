import type { Metadata } from "next";
import { PricingHero, PricingPlans, PricingQuestions } from "@/components/pricing/pricing-sections";
import { JsonLd } from "@/components/seo/json-ld";

/**
 * Pricing page.
 *
 * Rendered in the site design: the palette, ruled column, navigation and footer
 * all come from `app/(home)/layout.tsx`, and every style on this page resolves
 * from `app/(home)/home.css`.
 *
 * Copy is sourced from `plans/community-local/` — see `pricing-content.ts` for
 * what came from where, and for the two items the brief asks for that are
 * deliberately left out.
 *
 * A server component with no client JavaScript — the FAQ uses native
 * details/summary and the only interactive elements are links.
 */

const canonicalUrl = "https://www.surfsense.com/pricing";

/** Title, meta and the lead-with-free rule come from the `/pricing` brief in
 *  `plans/community-local/seo/02-page-briefs.md` (B5). */
const metaTitle = "SurfSense Pricing: Free App, Paid Plugins";
const metaDescription =
	"The app and its updates are free forever, with a 30-day licence included and no account. Licences add scraper plugins and priority support, from $60 a year.";

export const metadata: Metadata = {
	title: metaTitle,
	description: metaDescription,
	keywords: [
		"surfsense pricing",
		"is notebooklm free",
		"notebooklm pricing",
		"notebooklm cost",
		"open source notebooklm alternative",
		"private ai assistant",
		"self-hosted ai workspace",
	],
	alternates: {
		canonical: canonicalUrl,
	},
	openGraph: {
		title: metaTitle,
		description: metaDescription,
		url: canonicalUrl,
		siteName: "SurfSense",
		type: "website",
		images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "SurfSense pricing" }],
	},
	twitter: {
		card: "summary_large_image",
		title: metaTitle,
		description: metaDescription,
		images: ["/og-image.png"],
	},
};

/**
 * `Product` with an offer per priced tier, per the brief's schema note.
 *
 * The free tier is the product itself, so `price: 0` is the honest figure for
 * it; the paid offer is the licence. Individual carries the early-bird $60
 * rather than the $120 list price, because structured data that disagrees with
 * the price on the page is a rich-result penalty. `priceValidUntil` stays out
 * until launch day fixes the window's end.
 *
 * Enterprise has no offer here. An `Offer` without a price is invalid, and a
 * made-up figure on a tier that is quoted per deployment would be worse than
 * its absence.
 */
const PRICING_SCHEMA = {
	"@context": "https://schema.org",
	"@type": "Product",
	name: "SurfSense",
	description:
		"A private, open-source research notebook that runs on your own machine. The app is free; licences add the scraper plugins and priority support.",
	url: canonicalUrl,
	brand: { "@type": "Brand", name: "SurfSense" },
	offers: [
		{
			"@type": "Offer",
			name: "Free",
			price: 0,
			priceCurrency: "USD",
			description:
				"The full app and every update on Windows, macOS and Linux, forever, plus a 30-day licence for the plugins. No account, runs offline, bring your own model keys.",
		},
		{
			"@type": "Offer",
			name: "Individual",
			price: 60,
			priceCurrency: "USD",
			description:
				"Adds every scraper plugin, unlimited and unmetered, plus priority support. Billed yearly at the early-bird price, down from $120.",
		},
	],
};

export default function PricingPage() {
	return (
		<>
			<JsonLd data={PRICING_SCHEMA} />
			<PricingHero />
			<PricingPlans />
			<PricingQuestions />
		</>
	);
}
