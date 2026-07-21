import { IconBrandWalmart } from "@tabler/icons-react";
import type { ConnectorPageContent } from "./types";

export const walmart: ConnectorPageContent = {
	slug: "walmart",
	name: "Walmart",
	cardTitle: "Walmart Product & Review API",
	icon: IconBrandWalmart,

	metaTitle: "Walmart Product & Review API | SurfSense",
	metaDescription:
		"Scrape public Walmart product data and deep customer reviews as structured JSON: prices, ratings, sellers, variants, availability, and full review history. Start free.",
	keywords: [
		"walmart product api",
		"walmart scraper api",
		"walmart review scraper",
		"walmart reviews api",
		"scrape walmart product data",
		"walmart price scraper",
		"walmart product data api",
		"walmart price tracking api",
		"walmart competitor monitoring",
		"walmart seller data",
		"walmart marketplace api",
		"ecommerce product api",
	],

	h1: "Walmart Product and Review API",
	heroLede:
		"The SurfSense Walmart API scrapes public Walmart.com listings as structured JSON: price and list price, rating and review count, availability, 1P and marketplace sellers, variants, and specifications. A second verb pages the full public review history — ratings, text, authors, verified-purchase flags, images, and seller responses. Point your AI agents at a search term or product URL — no login, only public data.",

	transcript: {
		prompt: "Pull the ratings and top complaints for this Walmart air fryer",
		toolCall:
			'walmart.reviews({ urls: ["walmart.com/ip/..."],\n  max_reviews: 500, sort_by: "most-recent" })',
		rows: [
			{
				primary: "Ninja 4-Qt Air Fryer — $79.00 (was $99.00)",
				secondary: "4.6 stars · 8,204 reviews · In Stock",
				tag: "-20%",
			},
			{
				primary: "512 reviews paged, 71% verified purchase",
				secondary: "sorted most-recent · 132 with photos",
				tag: "reviews",
			},
			{
				primary: 'Top complaint: "basket coating flaking after 3 months"',
				secondary: "surfaced across 24 recent 1-2 star reviews",
				tag: "theme",
			},
		],
		resultSummary: "1 product · 512 reviews · surfaced in 6.4s",
	},

	extractIntro:
		"Give the scraper Walmart product, search, category, or browse URLs, or plain search terms. The scrape verb returns product cards and full detail with a free on-page review sample; the reviews verb pages the complete public review history for any product. Walmart data is US marketplace (walmart.com), server-rendered as JSON for stability.",
	extractFields: [
		{
			label: "Product core",
			description:
				"Name, item id (usItemId), brand, price, list price, availability, in-stock flag, and canonical URL for every product.",
		},
		{
			label: "Ratings & review sample",
			description:
				"Average stars and total review count on every product, plus a free sample of on-page reviews when you fetch full detail.",
		},
		{
			label: "Deep reviews",
			description:
				"The reviews verb pages the full public review history: rating, title, text, author, date, verified-purchase flag, helpful votes, images, and seller responses.",
		},
		{
			label: "Sellers",
			description:
				"The seller behind each product, typed as Walmart first-party (1P) or third-party marketplace (3P), with id and name.",
		},
		{
			label: "Variants & media",
			description:
				"Product variants (color, size, count) with their own item ids and prices, plus the gallery and thumbnail images.",
		},
		{
			label: "Content & taxonomy",
			description:
				"Short and long descriptions, specifications, category, and breadcrumb trail for catalog enrichment and classification.",
		},
	],

	useCasesHeading: "What teams do with the Walmart API",
	useCases: [
		{
			title: "Review mining and product research",
			description:
				"Page the full review history for a product and brief an agent to cluster complaints, track sentiment over time, and separate verified-purchase signal from noise. Walmart exposes far more review depth than most marketplaces — use it to inform your roadmap or listing copy.",
		},
		{
			title: "Price and buy-box tracking",
			description:
				"Watch your own and competitors' prices, list prices, and which seller wins the offer (Walmart 1P vs a third-party marketplace seller). Run the same URLs on a schedule and diff the results to alert on undercuts and stockouts.",
		},
		{
			title: "Seller and marketplace intelligence",
			description:
				"See which third-party sellers are winning offers on the products that matter to you, and how first-party Walmart pricing compares, to size the marketplace opportunity in your category.",
		},
		{
			title: "Catalog and assortment enrichment",
			description:
				"Enrich a catalog by item id with structured attributes, variants, specifications, and images, and discover products from search or category URLs to map an entire assortment.",
		},
	],

	comparison: {
		heading: "A Walmart scraper API built for agents",
		intro:
			"Most Walmart data APIs bill per request, split product and review data across endpoints, and leave the discovery-to-detail logic to you. Here is how SurfSense compares.",
		columnLabel: "Typical Walmart data API",
		rows: [
			{
				feature: "Pricing",
				official: "Per-request pricing that climbs fast at scale",
				surfsense: "Pay per product or per review returned, with a free tier to start",
			},
			{
				feature: "Discovery",
				official: "Separate search and detail endpoints you stitch together",
				surfsense: "One verb takes search terms or product, search, category, and browse URLs",
			},
			{
				feature: "Reviews",
				official: "A separate paid endpoint, often capped shallow",
				surfsense: "A dedicated verb pages the full public review history with photos and seller replies",
			},
			{
				feature: "Data access",
				official: "Requires accounts, keys, or approval for many providers",
				surfsense: "Public, anonymous data only — no login or seller account",
			},
			{
				feature: "Agent-ready",
				official: "No; you wire the harness yourself",
				surfsense: "MCP server exposes walmart.scrape and walmart.reviews as native tools",
			},
		],
	},

	api: {
		platform: "walmart",
		verb: "scrape",
		mcpTool: "walmart.scrape",
		requestBody: {
			search_terms: ["air fryer"],
			max_items: 5,
			include_reviews_sample: true,
		},
	},

	schema: {
		requestNote:
			"walmart.scrape: provide urls or search_terms (at least one), up to 20 combined sources per call. For the full review history, use the walmart.reviews verb with product urls or item_ids.",
		request: [
			{
				name: "urls",
				type: "string[]",
				description:
					"Walmart product (/ip/), search (/search), category (/cp/), or browse (/browse/) URLs. Provide urls or search_terms.",
			},
			{
				name: "search_terms",
				type: "string[]",
				description:
					"Search phrases run on walmart.com, e.g. 'air fryer'. Provide search_terms or urls.",
			},
			{
				name: "max_items",
				type: "integer",
				defaultValue: "10",
				description: "Max products per search term or category/browse URL, 1 to 100.",
			},
			{
				name: "include_details",
				type: "boolean",
				defaultValue: "true",
				description: "Fetch full product detail pages; false returns faster card-only results.",
			},
			{
				name: "include_reviews_sample",
				type: "boolean",
				defaultValue: "true",
				description:
					"Attach the free on-page review sample from each detail page. For full history use walmart.reviews.",
			},
		],
		responseNote:
			"The response is { items: [...] } with one item per product. One returned product is one billable unit; error items are never billed.",
		response: [
			{
				name: "name / usItemId / brand",
				type: "string",
				description: "Product identity: display name, Walmart item id, and brand.",
			},
			{
				name: "price / listPrice",
				type: "object",
				description: "Current price and strike-through list price, each with value and currency.",
			},
			{
				name: "stars / reviewsCount",
				type: "number",
				description: "Average star rating and total public review count.",
			},
			{
				name: "seller",
				type: "object",
				description: "Offer seller with id, name, and type (WALMART 1P or MARKETPLACE 3P).",
			},
			{
				name: "availabilityStatus / inStock",
				type: "string",
				description: "Availability label and a boolean in-stock flag.",
			},
			{
				name: "variants",
				type: "object[]",
				description: "Product variants (color, size, count) with their own item ids and prices.",
			},
			{
				name: "reviewsSample",
				type: "object",
				description: "Free sample of on-page reviews returned with full detail pages.",
			},
		],
	},

	faq: [
		{
			question: "What is the Walmart product API?",
			answer:
				"It returns a Walmart listing's data as structured JSON instead of raw HTML. The SurfSense Walmart API scrapes public product pages and gives you price, rating, seller, variants, availability, and specifications as clean JSON your agents can read.",
		},
		{
			question: "Can I get the full Walmart review history?",
			answer:
				"Yes. The walmart.reviews verb pages the complete public review history for a product — rating, title, text, author, date, verified-purchase flag, helpful votes, images, and seller responses. Pass product URLs or item ids and set max_reviews and sort_by.",
		},
		{
			question: "Does it only use public data?",
			answer:
				"It does. The scraper collects public, anonymous Walmart data only — no login or seller account. That covers product details, prices, ratings, public reviews, seller identity, variants, and availability.",
		},
		{
			question: "How do I look up a product by item id or search term?",
			answer:
				"Pass a product URL (which contains the item id) or a phrase in search_terms to discover products. You can also pass search, category, and browse URLs. walmart.scrape handles discovery; walmart.reviews takes urls or item_ids directly.",
		},
		{
			question: "Which Walmart marketplace is supported?",
			answer:
				"The scraper targets the US marketplace at walmart.com. Data is read from the server-rendered JSON Walmart ships in the page, which keeps extraction stable against the frequent front-end A/B testing on the site.",
		},
	],

	related: [
		{ label: "Amazon Product API", href: "/amazon" },
		{ label: "Google Maps API", href: "/google-maps" },
		{ label: "Google Search API", href: "/google-search" },
		{ label: "Reddit API", href: "/reddit" },
		{ label: "SurfSense MCP Server", href: "/mcp-server" },
		{ label: "Read the docs", href: "/docs" },
	],
};
