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
	"The app and its updates are free forever. Licences add scraper plugins and priority support, from $120 a year with a 14-day trial and no account.";

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
 * `Product` with one offer per tier, per the brief's schema note.
 *
 * The free tier is the product itself, so `price: 0` is the honest figure for
 * it; the paid offers are the licence. The early-bird price is deliberately not
 * modelled as an offer — it is a time-boxed coupon whose window opens at launch,
 * and a `priceValidUntil` we cannot fill would be worse than leaving it out.
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
				"The full app and every update on Windows, macOS and Linux, forever. No account, runs offline, bring your own model keys.",
		},
		{
			"@type": "Offer",
			name: "Individual",
			price: 120,
			priceCurrency: "USD",
			description:
				"Adds every scraper plugin, flat-included and unlimited, plus priority support. Billed yearly, with a 14-day trial.",
		},
		{
			"@type": "Offer",
			name: "Team",
			price: 80,
			priceCurrency: "USD",
			description:
				"The same licence for 5 to 25 seats, billed per seat per year and delivered as one shared key.",
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
