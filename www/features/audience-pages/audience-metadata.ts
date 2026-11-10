import type { Metadata } from "next";

/**
 * Metadata and structured data for the audience and job pages. Each page states its own
 * title, description and keywords, from its brief in
 * `plans/community-local/seo/09-audience-pages.md`; the shape around them is the one every
 * page on this site sets.
 */

const SITE = "https://www.surfsense.com";

export type AudiencePageMeta = {
	path: string;
	/** At most 60 characters. */
	title: string;
	/** At most 155 characters. */
	description: string;
	keywords: string[];
	imageAlt: string;
};

export function audiencePageMetadata(page: AudiencePageMeta): Metadata {
	const url = `${SITE}${page.path}`;
	return {
		title: page.title,
		description: page.description,
		keywords: page.keywords,
		alternates: { canonical: url },
		openGraph: {
			title: page.title,
			description: page.description,
			url,
			siteName: "SurfSense",
			type: "website",
			images: [{ url: "/og-image.png", width: 1200, height: 630, alt: page.imageAlt }],
		},
		twitter: {
			card: "summary_large_image",
			title: page.title,
			description: page.description,
			images: ["/og-image.png"],
		},
	};
}

/**
 * A page that names a paid job exists only once Business is on sale
 * (`NEXT_PUBLIC_BUSINESS_LAUNCHED`). Before that it is a 404, kept out of the index, as
 * `/pricing/business` is.
 */
export function businessPageMetadata(launched: boolean, page: AudiencePageMeta): Metadata {
	return launched ? audiencePageMetadata(page) : { robots: { index: false, follow: false } };
}

/**
 * `SoftwareApplication` for the free app, as the homepage states it, with the Business offer
 * beside it on a page that sells a job.
 */
export function audiencePageSchema(
	page: Pick<AudiencePageMeta, "path" | "description">,
	business?: { price: number; checkoutPath: string }
) {
	const free = {
		"@type": "Offer",
		name: "Free",
		price: 0,
		priceCurrency: "USD",
	};
	return {
		"@context": "https://schema.org",
		"@type": "SoftwareApplication",
		name: "SurfSense",
		applicationCategory: "BusinessApplication",
		operatingSystem: "Windows, macOS, Linux",
		description: page.description,
		url: `${SITE}${page.path}`,
		offers: business
			? [
					free,
					{
						"@type": "Offer",
						name: "Business",
						price: business.price,
						priceCurrency: "USD",
						url: `${SITE}${business.checkoutPath}`,
					},
				]
			: free,
	};
}
