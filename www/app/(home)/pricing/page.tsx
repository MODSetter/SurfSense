import type { Metadata } from "next";
import {
	PRICING_FAQ,
	PRICING_META_DESCRIPTION,
	PRICING_META_TITLE,
	PRICING_SCHEMA,
} from "@/app/(home)/pricing/pricing-content";
import {
	PricingHero,
	PricingIncludes,
	PricingQuestions,
} from "@/app/(home)/pricing/pricing-sections";
import { JsonLd } from "@/components/site/json-ld";

/**
 * Pricing page: SurfSense is free.
 *
 * Rendered in the site design: the palette, ruled column, navigation and footer all come
 * from `app/(home)/layout.tsx`, and every style on this page resolves from
 * `app/(home)/home.css`. The copy is `pricing-content.ts`.
 *
 * The URL stays: installed apps, old licence emails and search results open it.
 */

const canonicalUrl = "https://www.surfsense.com/pricing";

export const metadata: Metadata = {
	title: PRICING_META_TITLE,
	description: PRICING_META_DESCRIPTION,
	keywords: [
		"surfsense pricing",
		"is surfsense free",
		"is notebooklm free",
		"notebooklm pricing",
		"open source notebooklm alternative",
		"private ai assistant",
		"self-hosted ai workspace",
	],
	alternates: {
		canonical: canonicalUrl,
	},
	openGraph: {
		title: PRICING_META_TITLE,
		description: PRICING_META_DESCRIPTION,
		url: canonicalUrl,
		siteName: "SurfSense",
		type: "website",
		images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "SurfSense pricing" }],
	},
	twitter: {
		card: "summary_large_image",
		title: PRICING_META_TITLE,
		description: PRICING_META_DESCRIPTION,
		images: ["/og-image.png"],
	},
};

export default function PricingPage() {
	return (
		<>
			<JsonLd data={PRICING_SCHEMA} />
			<PricingHero />
			<PricingIncludes />
			<PricingQuestions questions={PRICING_FAQ} />
		</>
	);
}
