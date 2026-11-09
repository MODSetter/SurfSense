import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { BreadcrumbNav } from "@/components/site/breadcrumb-nav";
import { JsonLd } from "@/components/site/json-ld";
import { BUSINESS_LAUNCHED } from "@/features/business-launch/business-launched.mts";
import { FIRST_PERSON_PRICE, FURTHER_PERSON_PRICE, yearlyPriceLabel } from "../business-price";
import {
	AfterPaying,
	BusinessHero,
	BusinessOffer,
	BusinessQuestions,
	ClosingCheckout,
	FeatureRequestTerms,
	Reassurances,
} from "./business-sections";

/**
 * The Business licence's checkout landing page, between the `/pricing` card and the Stripe
 * Payment Link in `NEXT_PUBLIC_STRIPE_LICENSE_BUSINESS_URL`. Its job is that nobody reaches
 * Stripe unsure what they are buying, or that it renews.
 *
 * A 404 until Business is on sale (`NEXT_PUBLIC_BUSINESS_LAUNCHED`); from then on
 * `/pricing/individual` redirects here. Copy and its sources are in `business-content.ts`.
 */

const canonicalUrl = "https://www.surfsense.com/pricing/business";

const FIRST = yearlyPriceLabel(FIRST_PERSON_PRICE);
const FURTHER = yearlyPriceLabel(FURTHER_PERSON_PRICE);

const metaTitle = `SurfSense Business Licence: Job Plugins From ${FIRST} a Year`;
const metaDescription = `SurfSense's job plugins for firms: the security questionnaire and the contract redline. ${FIRST} a year for the first person, ${FURTHER} for each further one. No account, 30-day refund.`;

export const metadata: Metadata = BUSINESS_LAUNCHED
	? {
			title: metaTitle,
			description: metaDescription,
			keywords: [
				"surfsense business",
				"surfsense licence",
				"security questionnaire software",
				"contract redline software",
				"buy surfsense",
				"private ai for firms",
			],
			alternates: { canonical: canonicalUrl },
			openGraph: {
				title: metaTitle,
				description: metaDescription,
				url: canonicalUrl,
				siteName: "SurfSense",
				type: "website",
				images: [
					{ url: "/og-image.png", width: 1200, height: 630, alt: "SurfSense Business licence" },
				],
			},
			twitter: {
				card: "summary_large_image",
				title: metaTitle,
				description: metaDescription,
				images: ["/og-image.png"],
			},
		}
	: { robots: { index: false, follow: false } };

/** The offer as `/pricing` states it, so the two pages never disagree on price. */
const BUSINESS_SCHEMA = {
	"@context": "https://schema.org",
	"@type": "Product",
	name: "SurfSense Business licence",
	description:
		"SurfSense's security questionnaire and contract redline job plugins, priced per person, with priority support and one feature build request a year.",
	url: canonicalUrl,
	brand: { "@type": "Brand", name: "SurfSense" },
	offers: {
		"@type": "Offer",
		price: FIRST_PERSON_PRICE,
		priceCurrency: "USD",
		url: canonicalUrl,
		description: `A year for the first person; each further person is ${FURTHER} a year. Renews yearly until cancelled.`,
	},
};

export default function BusinessLicencePage() {
	if (!BUSINESS_LAUNCHED) notFound();

	return (
		<>
			<JsonLd data={BUSINESS_SCHEMA} />
			<BreadcrumbNav
				className="flex justify-center pt-8"
				items={[
					{ name: "Pricing", href: "/pricing" },
					{ name: "Business", href: "/pricing/business" },
				]}
			/>
			<BusinessHero />
			<BusinessOffer />
			<FeatureRequestTerms />
			<AfterPaying />
			<Reassurances />
			<BusinessQuestions />
			<ClosingCheckout />
		</>
	);
}
