interface JsonLdProps {
	data: Record<string, unknown>;
}

export function JsonLd({ data }: JsonLdProps) {
	return (
		// biome-ignore lint/security/noDangerouslySetInnerHtml: JSON-LD structured data requires dangerouslySetInnerHTML for script injection
		<script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }} />
	);
}

export function OrganizationJsonLd() {
	return (
		<JsonLd
			data={{
				"@context": "https://schema.org",
				"@type": "Organization",
				name: "SurfSense",
				url: "https://www.surfsense.com",
				logo: "https://www.surfsense.com/logo.png",
				description:
					"SurfSense is an open-source competitive intelligence platform. AI agents monitor competitors, track rankings, and listen to your market through one API or MCP server.",
				sameAs: ["https://github.com/MODSetter/SurfSense", "https://discord.gg/ejRNvftDp9"],
				contactPoint: {
					"@type": "ContactPoint",
					email: "rohan@surfsense.com",
					contactType: "sales",
				},
			}}
		/>
	);
}

export function WebSiteJsonLd() {
	return (
		<JsonLd
			data={{
				"@context": "https://schema.org",
				"@type": "WebSite",
				name: "SurfSense",
				url: "https://www.surfsense.com",
				description:
					"SurfSense is an open-source competitive intelligence platform for AI agents, with live data connectors served through one API or MCP server.",
				potentialAction: {
					"@type": "SearchAction",
					target: {
						"@type": "EntryPoint",
						urlTemplate: "https://www.surfsense.com/docs?search={search_term_string}",
					},
					"query-input": "required name=search_term_string",
				},
			}}
		/>
	);
}

export function SoftwareApplicationJsonLd() {
	return (
		<JsonLd
			data={{
				"@context": "https://schema.org",
				"@type": "SoftwareApplication",
				name: "SurfSense",
				applicationCategory: "BusinessApplication",
				operatingSystem: "Windows, macOS, Linux, Web",
				offers: {
					"@type": "Offer",
					price: "0",
					priceCurrency: "USD",
					description: "Free plan with 500 pages included",
				},
				description:
					"SurfSense is an open-source competitive intelligence platform. AI agents monitor competitors, track rankings, and listen to your market with platform-native connectors for Reddit, YouTube, Google Maps, Google Search, and the open web, through one API or MCP server.",
				url: "https://www.surfsense.com",
				downloadUrl: "https://github.com/MODSetter/SurfSense/releases",
				featureList: [
					"Platform-native connectors: Reddit, YouTube, Google Maps, Google Search, Web Crawl",
					"MCP server that exposes every connector as a native agent tool",
					"Agent harness with retries, structured output, and credit metering",
					"Competitor, brand, and rank monitoring with briefs and alerts",
					"AI automations and agents (scheduled and event-triggered workflows)",
					"AI-powered semantic search across connected tools and documents",
					"Federated search across Slack, Google Drive, Notion, Confluence, GitHub",
					"Document Q&A with citations, report, podcast, and video generation",
					"Real-time collaborative team chats",
					"Native desktop app with Quick, General, and Screenshot Assist",
					"Open source and self-hostable with no data limits",
				],
			}}
		/>
	);
}

export function ArticleJsonLd({
	title,
	description,
	url,
	datePublished,
	dateModified,
	author,
	image,
}: {
	title: string;
	description: string;
	url: string;
	datePublished: string;
	dateModified?: string;
	author: string;
	image?: string;
}) {
	return (
		<JsonLd
			data={{
				"@context": "https://schema.org",
				"@type": "Article",
				headline: title,
				description,
				url,
				datePublished,
				...(dateModified ? { dateModified } : {}),
				author: {
					"@type": "Organization",
					name: author,
				},
				publisher: {
					"@type": "Organization",
					name: "SurfSense",
					logo: {
						"@type": "ImageObject",
						url: "https://www.surfsense.com/logo.png",
					},
				},
				image: image || "https://www.surfsense.com/og-image.png",
				mainEntityOfPage: {
					"@type": "WebPage",
					"@id": url,
				},
			}}
		/>
	);
}

export function BreadcrumbJsonLd({ items }: { items: { name: string; url: string }[] }) {
	return (
		<JsonLd
			data={{
				"@context": "https://schema.org",
				"@type": "BreadcrumbList",
				itemListElement: items.map((item, index) => ({
					"@type": "ListItem",
					position: index + 1,
					name: item.name,
					item: item.url,
				})),
			}}
		/>
	);
}

export function FAQJsonLd({ questions }: { questions: { question: string; answer: string }[] }) {
	return (
		<JsonLd
			data={{
				"@context": "https://schema.org",
				"@type": "FAQPage",
				mainEntity: questions.map((q) => ({
					"@type": "Question",
					name: q.question,
					acceptedAnswer: {
						"@type": "Answer",
						text: q.answer,
					},
				})),
			}}
		/>
	);
}
