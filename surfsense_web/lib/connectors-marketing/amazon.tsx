import { IconBrandAmazon } from "@tabler/icons-react";
import type { ConnectorPageContent } from "./types";

export const amazon: ConnectorPageContent = {
	slug: "amazon",
	name: "Amazon",
	cardTitle: "Amazon Product API",
	icon: IconBrandAmazon,

	metaTitle: "Amazon Product Scraper API for Price & Review Data | SurfSense",
	metaDescription:
		"Scrape public Amazon product data as structured JSON: prices, ratings, reviews, offers, sellers, and best-seller ranks. Query by URL or search term via API or MCP. Start free.",
	keywords: [
		"amazon product api",
		"amazon scraper api",
		"amazon price scraper",
		"scrape amazon product data",
		"amazon product data api",
		"amazon review scraper",
		"amazon best sellers api",
		"amazon asin lookup",
		"amazon price tracking api",
		"amazon competitor monitoring",
		"amazon offers scraper",
		"ecommerce product api",
	],

	h1: "Amazon Product Scraper API for Price, Review, and Offer Data",
	heroLede:
		"The SurfSense Amazon Product API scrapes public Amazon listings as structured JSON: price and list price, rating and review breakdown, availability, marketplace offers, sellers, best-seller ranks, and on-page reviews. Point your AI agents at a search term or product URL and track prices, monitor competitors, and mine reviews — no login, only public data.",

	transcript: {
		prompt: "Track the price and rating of the top mechanical keyboards on Amazon",
		toolCall:
			'amazon.scrape({ search_terms: ["mechanical keyboard"],\n  max_items: 5, max_offers: 3 })',
		rows: [
			{
				primary: "Keychron K8 Pro — $89.99 (was $99.99)",
				secondary: "4.7 stars · 12,431 ratings · In Stock",
				tag: "-10%",
			},
			{
				primary: "3 marketplace offers, cheapest $84.50 used",
				secondary: "sold by 2 third-party sellers",
				tag: "offers",
			},
			{
				primary: "#2 in Computer Keyboards best-sellers",
				secondary: "Electronics › Accessories › Keyboards",
				tag: "rank",
			},
		],
		resultSummary: "5 products · 14 offers · 5 best-seller ranks · surfaced in 3.1s",
	},

	extractIntro:
		"Give the API a list of product/search/category/best-seller URLs or search terms and a domain. It returns one structured item per product, with pricing, ratings, offers, and provenance parsed into their own fields.",
	extractFields: [
		{
			label: "Product core",
			description:
				"Title, ASIN, brand, price, list price, availability, condition, and canonical URL for every product.",
		},
		{
			label: "Ratings & reviews",
			description:
				"Star rating, review count, the 5-to-1-star histogram, and on-page customer reviews with text, author, and date.",
		},
		{
			label: "Marketplace offers",
			description:
				"Additional buy-box offers with price, condition, delivery, and the third-party seller behind each.",
		},
		{
			label: "Sellers",
			description:
				"Public seller profile summaries — name, rating, and feedback count — for the featured and offer sellers.",
		},
		{
			label: "Best-seller ranks",
			description:
				"Category rank positions and best-seller list placements, for demand and category monitoring.",
		},
		{
			label: "Variants & media",
			description:
				"Variant ASINs and attributes (color, size), per-variant prices, gallery and high-resolution images.",
		},
	],

	useCasesHeading: "What teams do with the Amazon Product API",
	useCases: [
		{
			title: "Price and buy-box tracking",
			description:
				"Watch your own and competitors' prices, list prices, and marketplace offers across marketplaces. Feed each run to an agent that diffs prices and alerts you when a competitor undercuts or the buy box changes hands.",
		},
		{
			title: "Review mining and product research",
			description:
				"Pull ratings, the star histogram, and on-page reviews to understand what customers love and complain about, then brief an agent to summarize themes and inform your roadmap or listing copy.",
		},
		{
			title: "Best-seller and category monitoring",
			description:
				"Track best-seller ranks in the categories you care about to spot rising products and demand shifts before they show up anywhere else.",
		},
		{
			title: "Catalog and seller intelligence",
			description:
				"Enrich a catalog by ASIN with structured attributes, variants, and images, and see which third-party sellers are winning offers on the products that matter to you.",
		},
	],

	comparison: {
		heading: "An Amazon scraper API built for agents",
		intro:
			"Most Amazon data APIs bill per request, meter add-ons separately, and leave the discovery-to-detail logic to you. Here is how SurfSense compares.",
		columnLabel: "Typical Amazon data API",
		rows: [
			{
				feature: "Pricing",
				official: "Per-request pricing that climbs fast at scale",
				surfsense: "Pay per product returned, with a free tier to start",
			},
			{
				feature: "Discovery",
				official: "Separate search and detail endpoints you stitch together",
				surfsense: "One verb takes search terms, product, category, or best-seller URLs",
			},
			{
				feature: "Offers & sellers",
				official: "Often separate paid endpoints",
				surfsense: "Offers and seller profiles enriched inline on the product",
			},
			{
				feature: "Data access",
				official: "Requires accounts, keys, or approval for many providers",
				surfsense: "Public, anonymous data only — no login or seller account",
			},
			{
				feature: "Agent-ready",
				official: "No; you wire the harness yourself",
				surfsense: "MCP server exposes amazon.scrape as a native tool",
			},
		],
	},

	api: {
		platform: "amazon",
		verb: "scrape",
		mcpTool: "amazon.scrape",
		requestBody: {
			search_terms: ["mechanical keyboard"],
			max_items: 5,
			max_offers: 3,
		},
	},

	schema: {
		requestNote:
			"Provide urls or search_terms (at least one). Up to 20 combined sources per call.",
		request: [
			{
				name: "urls",
				type: "string[]",
				description:
					"Amazon product, search, category, best-seller, or short (a.co / amzn.to) URLs. Provide urls or search_terms.",
			},
			{
				name: "search_terms",
				type: "string[]",
				description:
					"Search phrases run on the Amazon domain, e.g. 'wireless earbuds'. Provide search_terms or urls.",
			},
			{
				name: "max_items",
				type: "integer",
				defaultValue: "10",
				description: "Max products per search term or category/best-seller URL, 1 to 100.",
			},
			{
				name: "domain",
				type: "string",
				defaultValue: '"www.amazon.com"',
				description: "Amazon marketplace domain, e.g. 'www.amazon.co.uk'.",
			},
			{
				name: "include_details",
				type: "boolean",
				defaultValue: "true",
				description:
					"Fetch full product detail pages. false returns faster card-only results.",
			},
			{
				name: "max_offers",
				type: "integer",
				defaultValue: "0",
				description:
					"Extra marketplace offers to fetch per product, 0 to 100. 0 returns the featured offer only.",
			},
			{
				name: "include_sellers",
				type: "boolean",
				defaultValue: "false",
				description: "Enrich the product and each offer with the seller's public profile.",
			},
			{
				name: "max_variants",
				type: "integer",
				defaultValue: "0",
				description: "Product variants to return as separate results, 0 to 100.",
			},
			{
				name: "include_variant_prices",
				type: "boolean",
				defaultValue: "false",
				description: "Attach per-variant prices (one extra request per variant).",
			},
			{
				name: "country_code",
				type: "string",
				description: "Two-letter delivery country for localized pricing, e.g. 'us'.",
			},
			{
				name: "zip_code",
				type: "string",
				description: "Delivery ZIP/postal code for localized availability, e.g. '10001'.",
			},
			{
				name: "language",
				type: "string",
				description: "Content language for the domain, e.g. 'en'.",
			},
		],
		responseNote:
			"The response is { items: [...] } with one item per product. One returned product is one billable unit; error items are never billed.",
		response: [
			{
				name: "title / asin / brand",
				type: "string",
				description: "Product identity: display title, ASIN, and brand.",
			},
			{
				name: "price / listPrice",
				type: "object",
				description: "Current price and strike-through list price, each with value and currency.",
			},
			{
				name: "stars / reviewsCount / starsBreakdown",
				type: "object",
				description:
					"Average rating, total review count, and the 5-to-1-star distribution as fractions.",
			},
			{
				name: "offers",
				type: "object[]",
				description:
					"Marketplace offers with price, condition, delivery, seller, and pinned-offer flag.",
			},
			{
				name: "seller",
				type: "object",
				description: "Featured seller profile: id, name, url, rating, and feedback count.",
			},
			{
				name: "bestsellerRanks",
				type: "object[]",
				description: "Category rank positions and best-seller list placements.",
			},
			{
				name: "variantAsins / variantDetails / variantAttributes",
				type: "object[]",
				description: "Related variant ASINs and their attributes and per-variant prices.",
			},
			{
				name: "productPageReviews",
				type: "object[]",
				description: "On-page customer reviews with text, author, rating, and date.",
			},
		],
	},

	faq: [
		{
			question: "What is an Amazon product API?",
			answer:
				"An Amazon product API returns a listing's data as structured JSON instead of raw HTML. The SurfSense Amazon API scrapes public product pages and gives you price, rating, review breakdown, offers, sellers, and best-seller ranks as clean JSON your agents can read.",
		},
		{
			question: "Can I track Amazon prices with it?",
			answer:
				"Yes. Each product returns its current price, list price, and marketplace offers. Run the same URLs or search terms on a schedule and diff the prices to build price and buy-box tracking, without maintaining scrapers or proxies yourself.",
		},
		{
			question: "Does it only use public data?",
			answer:
				"It does. The scraper collects public, anonymous product data only — no login, seller account, or authenticated APIs. That covers product details, ratings, on-page reviews, offers, public seller profiles, and best-seller rankings.",
		},
		{
			question: "How do I look up a product by ASIN or search term?",
			answer:
				"Pass a product URL (which contains the ASIN) in urls, or a phrase in search_terms to discover products on the domain. You can also pass search, category, and best-seller URLs. One verb, amazon.scrape, handles all of them.",
		},
	],

	related: [
		{ label: "Google Search API", href: "/google-search" },
		{ label: "Google Maps API", href: "/google-maps" },
		{ label: "Web Crawl API", href: "/web-crawl" },
		{ label: "Reddit API", href: "/reddit" },
		{ label: "SurfSense MCP Server", href: "/mcp-server" },
		{ label: "Read the docs", href: "/docs" },
	],
};
