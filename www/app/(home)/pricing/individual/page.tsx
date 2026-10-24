import type { Metadata } from "next";
import { INDIVIDUAL_PRICE, PLUGIN_PLATFORMS } from "@/app/(home)/pricing/pricing-content";
import { BreadcrumbNav } from "@/components/site/breadcrumb-nav";
import { JsonLd } from "@/components/site/json-ld";
import {
	AfterPaying,
	ClosingCheckout,
	FeatureRequestTerms,
	IndividualHero,
	IndividualOffer,
	IndividualQuestions,
	Reassurances,
} from "./individual-sections";

/**
 * The Individual licence's checkout landing page, between the `/pricing` card
 * and the Stripe Payment Link, which needs no account. Its job is that nobody
 * reaches Stripe unsure what they are buying.
 *
 * Rendered in the site design (listed in `SITE_DESIGN_ROUTES`). Copy and its
 * sources are in `individual-content.ts`.
 */

const canonicalUrl = "https://www.surfsense.com/pricing/individual";

const metaTitle = "SurfSense Individual Licence: Every Plugin, $60 First Year";
const metaDescription =
	"Every SurfSense plugin, unlimited, with priority support and one feature build request a year. $60 for the first year, then $120. No account, 30-day refund.";

export const metadata: Metadata = {
	title: metaTitle,
	description: metaDescription,
	keywords: [
		"surfsense licence",
		"surfsense individual",
		"surfsense plugins",
		"buy surfsense",
		"notebooklm alternative pricing",
	],
	alternates: { canonical: canonicalUrl },
	openGraph: {
		title: metaTitle,
		description: metaDescription,
		url: canonicalUrl,
		siteName: "SurfSense",
		type: "website",
		images: [
			{ url: "/og-image.png", width: 1200, height: 630, alt: "SurfSense Individual licence" },
		],
	},
	twitter: {
		card: "summary_large_image",
		title: metaTitle,
		description: metaDescription,
		images: ["/og-image.png"],
	},
};

/** The offer as `/pricing` states it, so the two pages never disagree on price. */
const INDIVIDUAL_SCHEMA = {
	"@context": "https://schema.org",
	"@type": "Product",
	name: "SurfSense Individual licence",
	description: `Every SurfSense plugin (${PLUGIN_PLATFORMS.join(", ")} and the web crawler), unlimited, with priority support and one feature build request a year.`,
	url: canonicalUrl,
	brand: { "@type": "Brand", name: "SurfSense" },
	offers: {
		"@type": "Offer",
		price: Number(INDIVIDUAL_PRICE.replace("$", "")),
		priceCurrency: "USD",
		url: canonicalUrl,
		description: "The first year at the early-bird price, then $120 a year.",
	},
};

export default function IndividualLicencePage() {
	return (
		<>
			<JsonLd data={INDIVIDUAL_SCHEMA} />
			<BreadcrumbNav
				className="flex justify-center pt-8"
				items={[
					{ name: "Pricing", href: "/pricing" },
					{ name: "Individual", href: "/pricing/individual" },
				]}
			/>
			<IndividualHero />
			<IndividualOffer />
			<FeatureRequestTerms />
			<AfterPaying />
			<Reassurances />
			<IndividualQuestions />
			<ClosingCheckout />
		</>
	);
}
