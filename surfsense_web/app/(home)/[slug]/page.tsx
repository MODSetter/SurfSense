import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ConnectorPage } from "@/components/connectors-marketing/connector-page";
import { FAQJsonLd, JsonLd } from "@/components/seo/json-ld";
import { getAllConnectorSlugs, getConnector } from "@/lib/connectors-marketing";

interface PageProps {
	params: Promise<{ slug: string }>;
}

// Only the known connector slugs are served; every other path falls through to 404.
export const dynamicParams = false;

export function generateStaticParams() {
	return getAllConnectorSlugs().map((slug) => ({ slug }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
	const { slug } = await params;
	const content = getConnector(slug);
	if (!content) return { title: "Connector Not Found | SurfSense" };

	const canonicalUrl = `https://www.surfsense.com/${content.slug}`;

	return {
		title: content.metaTitle,
		description: content.metaDescription,
		keywords: content.keywords,
		alternates: { canonical: canonicalUrl },
		openGraph: {
			title: content.metaTitle,
			description: content.metaDescription,
			url: canonicalUrl,
			siteName: "SurfSense",
			type: "website",
			images: [
				{
					url: "/og-image.png",
					width: 1200,
					height: 630,
					alt: `${content.name} Scraper API on SurfSense`,
				},
			],
		},
		twitter: {
			card: "summary_large_image",
			title: content.metaTitle,
			description: content.metaDescription,
			images: ["/og-image.png"],
		},
	};
}

export default async function ConnectorMarketingPage({ params }: PageProps) {
	const { slug } = await params;
	const content = getConnector(slug);
	if (!content) notFound();

	const canonicalUrl = `https://www.surfsense.com/${content.slug}`;

	return (
		<>
			<JsonLd
				data={{
					"@context": "https://schema.org",
					"@type": "SoftwareApplication",
					name: `${content.name} Scraper API`,
					applicationCategory: "DeveloperApplication",
					operatingSystem: "Web, API",
					description: content.metaDescription,
					url: canonicalUrl,
					offers: {
						"@type": "Offer",
						price: "0",
						priceCurrency: "USD",
						description: "Free tier included",
					},
					provider: {
						"@type": "Organization",
						name: "SurfSense",
						url: "https://www.surfsense.com",
					},
					isPartOf: {
						"@type": "WebSite",
						name: "SurfSense",
						url: "https://www.surfsense.com",
					},
				}}
			/>
			<FAQJsonLd questions={content.faq} />
			<ConnectorPage content={content} />
		</>
	);
}
