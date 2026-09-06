import type { Metadata } from "next";
import PricingBasic from "@/components/pricing/pricing-section";
import { JsonLd } from "@/components/seo/json-ld";

const canonicalUrl = "https://www.surfsense.com/pricing";

const metaTitle = "SurfSense Pricing: Free Plan, Pro at $15/month, or Self-Host";
const metaDescription =
	"Start free in the SurfSense cloud, upgrade to Pro for $15 a month, or self-host for free from our open-source repo. Premium models billed at provider cost.";

export const metadata: Metadata = {
	title: metaTitle,
	description: metaDescription,
	keywords: [
		"surfsense pricing",
		"ai agent platform pricing",
		"open source ai agent platform",
		"self-hosted ai workspace",
		"ai automation pricing",
		"web scraping api pricing",
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

const page = () => {
	return (
		<div>
			<JsonLd
				data={{
					"@context": "https://schema.org",
					"@type": "SoftwareApplication",
					name: "SurfSense",
					applicationCategory: "BusinessApplication",
					operatingSystem: "Windows, macOS, Linux, Web",
					url: canonicalUrl,
					offers: [
						{
							"@type": "Offer",
							name: "Free",
							price: "0",
							priceCurrency: "USD",
							description:
								"Self-host from the open-source repo with unlimited usage and your own model keys, or use the cloud free with $1 of premium model usage each month.",
						},
						{
							"@type": "Offer",
							name: "Pro",
							price: "15",
							priceCurrency: "USD",
							description:
								"$6 of premium model usage, connector calls, and crawls included every month, plus priority support. Top up credit at $1 for $1 if you need more.",
							// Google reads a bare `price` as one-time. The recurrence has
							// to be spelled out here or the rich result advertises Pro as
							// a $15 purchase.
							priceSpecification: {
								"@type": "UnitPriceSpecification",
								price: "15",
								priceCurrency: "USD",
								billingDuration: 1,
								billingIncrement: 1,
								unitCode: "MON",
							},
						},
					],
				}}
			/>
			<PricingBasic />
		</div>
	);
};

export default page;
