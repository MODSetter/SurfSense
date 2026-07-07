import type { Metadata } from "next";
import PricingBasic from "@/components/pricing/pricing-section";
import { JsonLd } from "@/components/seo/json-ld";

const canonicalUrl = "https://www.surfsense.com/pricing";

const metaTitle = "SurfSense Pricing: Self-Host Free or Pay As You Go";
const metaDescription =
	"Self-host SurfSense for free from our open-source repo, or use the cloud with $5 of free credit and pay as you go at provider cost. No subscription.";

export const metadata: Metadata = {
	title: metaTitle,
	description: metaDescription,
	keywords: [
		"surfsense pricing",
		"pay as you go ai platform",
		"open source ai agent platform",
		"self-hosted ai workspace",
		"ai automation pricing",
		"competitive intelligence pricing",
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
							name: "Free (Self-Hosted)",
							price: "0",
							priceCurrency: "USD",
							description:
								"Open source and self-hostable with unlimited usage. Bring your own model keys.",
						},
						{
							"@type": "Offer",
							name: "Pay As You Go",
							price: "0",
							priceCurrency: "USD",
							description:
								"Cloud accounts start with $5 of free credit. Top up any amount after that; $1 buys $1 of credit at provider cost with no subscription.",
						},
					],
				}}
			/>
			<PricingBasic />
		</div>
	);
};

export default page;
