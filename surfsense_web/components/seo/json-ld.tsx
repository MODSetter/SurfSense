interface JsonLdProps {
	data: Record<string, unknown>;
}

export function JsonLd({ data }: JsonLdProps) {
	return (
		<script
			type="application/ld+json"
			dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }}
		/>
	);
}

export function OrganizationJsonLd() {
	return (
		<JsonLd
			data={{
				"@context": "https://schema.org",
				"@type": "Organization",
				name: "SurfSense",
				url: "https://surfsense.com",
				logo: "https://surfsense.com/logo.png",
			description:
				"Open source NotebookLM alternative for teams with no data limits. Use ChatGPT, Claude AI, and any AI model for free.",
				sameAs: [
					"https://github.com/MODSetter/SurfSense",
					"https://discord.gg/Cg2M4GUJ",
				],
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
				url: "https://surfsense.com",
			description:
				"Open source NotebookLM alternative for teams with no data limits. Free ChatGPT, Claude AI, and any AI model.",
				potentialAction: {
					"@type": "SearchAction",
					target: {
						"@type": "EntryPoint",
						urlTemplate: "https://surfsense.com/docs?search={search_term_string}",
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
				"Open source NotebookLM alternative with free access to ChatGPT, Claude AI, and any model. Connect Slack, Google Drive, Notion, Confluence, GitHub, and dozens more data sources.",
				url: "https://surfsense.com",
				downloadUrl: "https://github.com/MODSetter/SurfSense/releases",
			featureList: [
				"Free access to ChatGPT, Claude AI, and any AI model",
				"AI-powered semantic search across all connected tools",
				"Federated search across Slack, Google Drive, Notion, Confluence, GitHub",
				"No data limits with open source self-hosting",
				"Real-time collaborative team chats",
				"Document Q&A with citations",
				"Report generation",
				"Podcast and video generation from sources",
				"Enterprise knowledge management",
				"Self-hostable and privacy-focused",
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
	author,
	image,
}: {
	title: string;
	description: string;
	url: string;
	datePublished: string;
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
				author: {
					"@type": "Organization",
					name: author,
				},
				publisher: {
					"@type": "Organization",
					name: "SurfSense",
					logo: {
						"@type": "ImageObject",
						url: "https://surfsense.com/logo.png",
					},
				},
				image: image || "https://surfsense.com/og-image.png",
				mainEntityOfPage: {
					"@type": "WebPage",
					"@id": url,
				},
			}}
		/>
	);
}

export function BreadcrumbJsonLd({
	items,
}: {
	items: { name: string; url: string }[];
}) {
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

export function FAQJsonLd({
	questions,
}: {
	questions: { question: string; answer: string }[];
}) {
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
