import type { Metadata } from "next";
import {
	BUSINESS_META_DESCRIPTION,
	BUSINESS_META_TITLE,
	BUSINESS_PLANS,
	BUSINESS_PRICING_FAQ,
	BUSINESS_PRICING_LEDE,
	BUSINESS_PRICING_SCHEMA,
	LICENCE_COMPARISON,
} from "@/app/(home)/pricing/business-pricing-content";
import {
	PricingComparison,
	PricingHero,
	PricingPlans,
	PricingQuestions,
} from "@/app/(home)/pricing/pricing-sections";
import { JsonLd } from "@/components/site/json-ld";

/**
 * Pricing page.
 *
 * Rendered in the site design: the palette, ruled column, navigation and footer
 * all come from `app/(home)/layout.tsx`, and every style on this page resolves
 * from `app/(home)/home.css`.
 *
 * The copy is `business-pricing-content.ts`; `pricing-content.ts` holds what the
 * pricing pages share, and the two items the brief asks for that are
 * deliberately left out.
 *
 * A server component with no client JavaScript — the FAQ uses native
 * details/summary and the only interactive elements are links.
 */

const canonicalUrl = "https://www.surfsense.com/pricing";

/** Title, meta and the lead-with-free rule come from the `/pricing` brief in
 *  `plans/community-local/seo/02-page-briefs.md` (B5). */
const metaTitle = BUSINESS_META_TITLE;
const metaDescription = BUSINESS_META_DESCRIPTION;

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

export default function PricingPage() {
	return (
		<>
			<JsonLd data={BUSINESS_PRICING_SCHEMA} />
			<PricingHero lede={BUSINESS_PRICING_LEDE} />
			<PricingPlans plans={BUSINESS_PLANS} />
			<PricingComparison rows={LICENCE_COMPARISON} />
			<PricingQuestions questions={BUSINESS_PRICING_FAQ} />
		</>
	);
}
