import { IconMapPin } from "@tabler/icons-react";
import type { ConnectorPageContent } from "./types";

export const googleMaps: ConnectorPageContent = {
	slug: "google-maps",
	name: "Google Maps",
	icon: IconMapPin,

	metaTitle: "Google Maps Scraper API for Lead Generation | SurfSense",
	metaDescription:
		"Turn Google Maps into a B2B lead engine with the SurfSense Google Maps Scraper API. Extract business data, ratings, and reviews at scale for your AI agents. Start now.",
	keywords: [
		"google maps scraper",
		"google maps scraper api",
		"google maps data extraction",
		"google maps lead generation",
		"google maps lead scraper",
		"businesses without websites",
		"google maps reviews api",
		"local business data api",
		"google maps scraper python",
	],

	h1: "Google Maps Scraper API for Lead Generation and Local Market Intelligence",
	heroLede:
		"The SurfSense Google Maps API turns Maps into a B2B lead engine. Extract business names, categories, phones, websites, ratings, and reviews at scale, then point your AI agents at any territory or category to build lead lists and map a local market in minutes.",

	transcript: {
		prompt: "Find every dentist in Austin without a website",
		toolCall:
			'google_maps.scrape({ search_queries: ["dentist"], location: "Austin, TX",\n  max_places: 100, include_details: true })',
		rows: [
			{
				primary: "Barton Springs Family Dental",
				secondary: "4.9 ★ · 212 reviews · (512) 555-0148",
				tag: "no website",
			},
			{
				primary: "Congress Ave Dentistry",
				secondary: "4.7 ★ · 88 reviews · (512) 555-0192",
				tag: "no website",
			},
			{
				primary: "East Austin Smiles",
				secondary: "4.8 ★ · 141 reviews · (512) 555-0175",
				tag: "no website",
			},
		],
		resultSummary: "100 places · 23 without a website · surfaced in 4.0s",
	},

	extractIntro:
		"Give the API a search query plus a location, a Maps URL, or a known place ID. It returns one structured item per place, with reviews and images attached on request.",
	extractFields: [
		{
			label: "Business identity",
			description: "Name, category, description, and Google place ID for every result.",
		},
		{
			label: "Contact",
			description: "Phone number and website when Google lists them, ready for outreach lists.",
		},
		{
			label: "Address and geo",
			description: "Full address, neighborhood, city, postal code, and latitude/longitude.",
		},
		{
			label: "Ratings",
			description: "Star rating, review count, and the full one-to-five-star distribution.",
		},
		{
			label: "Reviews",
			description: "Attach up to the review count you set per place, with text, stars, and author.",
		},
		{
			label: "Details",
			description: "Opening hours, popular times, and images when you enable detail pages.",
		},
	],

	useCasesHeading: "What teams do with the Google Maps API",
	useCases: [
		{
			title: "B2B lead lists",
			description:
				"Point an agent at a category and a territory and get back a clean list of businesses with phone numbers, ratings, and websites, ready to load into your CRM or outreach tool.",
		},
		{
			title: "Businesses without websites",
			description:
				"Filter results down to places Google lists with no website, the classic warm lead for agencies and web shops. It is the highest-converting local lead-gen angle there is.",
		},
		{
			title: "Competitor and review analysis",
			description:
				"Pull a competitor's rating, review count, and review text to see exactly what their customers praise and complain about, then brief an agent to summarize the gaps you can win on.",
		},
		{
			title: "Territory and market mapping",
			description:
				"Scrape an entire category across a city or region to size a market, spot white space, and plan coverage before your sales team ever picks up the phone.",
		},
	],

	comparison: {
		heading: "A Google Maps API alternative for lead gen",
		intro:
			"Google's official Places API is metered per call and returns only a handful of reviews. Here is how SurfSense compares for lead generation and market research.",
		columnLabel: "Official Places API",
		rows: [
			{
				feature: "Results per query",
				official: "Paginated and capped; bulk pulls are painful",
				surfsense: "Up to 1,000 places per search query",
			},
			{
				feature: "Reviews",
				official: "Only about five reviews per place",
				surfsense: "Attach up to the review count you set, or use the reviews verb for depth",
			},
			{
				feature: "Pricing",
				official: "Metered per API call, per field mask",
				surfsense: "Pay per place returned, with a free tier to start",
			},
			{
				feature: "Setup",
				official: "Google Cloud project, billing, and API key",
				surfsense: "One API key, or add the MCP server to your agent",
			},
			{
				feature: "Agent-ready",
				official: "No; you build the harness yourself",
				surfsense: "MCP server exposes google_maps.scrape as a native tool",
			},
		],
	},

	api: {
		platform: "google_maps",
		verb: "scrape",
		mcpTool: "google_maps.scrape",
		requestBody: {
			search_queries: ["dentist"],
			location: "Austin, TX",
			max_places: 100,
			include_details: true,
		},
	},

	schema: {
		requestNote:
			"Provide at least one source: search_queries, urls, or place_ids. Up to 20 sources per call.",
		request: [
			{
				name: "search_queries",
				type: "string[]",
				defaultValue: "[]",
				description:
					"Google Maps search terms, e.g. 'coffee shops', 'dentist'. Each returns up to max_places. Pair with location to scope the search. Max 20.",
			},
			{
				name: "urls",
				type: "string[]",
				defaultValue: "[]",
				description:
					"Google Maps URLs: a place page (/maps/place/...) or a search results URL. Max 20.",
			},
			{
				name: "place_ids",
				type: "string[]",
				defaultValue: "[]",
				description: "Known Google place IDs (ChIJ...) to fetch directly. Max 20.",
			},
			{
				name: "location",
				type: "string",
				description: "Location to scope search_queries to, e.g. 'New York, USA'.",
			},
			{
				name: "max_places",
				type: "integer",
				defaultValue: "10",
				description: "Max places to return per search query. 1 to 1,000.",
			},
			{
				name: "language",
				type: "string",
				defaultValue: '"en"',
				description: "Result language code, e.g. 'en', 'fr'.",
			},
			{
				name: "include_details",
				type: "boolean",
				defaultValue: "false",
				description:
					"Also fetch each place's detail page: opening hours, popular times, and extra contact info. Slower.",
			},
			{
				name: "max_reviews",
				type: "integer",
				defaultValue: "0",
				description: "Reviews to attach per place, up to 100,000. 0 disables reviews.",
			},
			{
				name: "max_images",
				type: "integer",
				defaultValue: "0",
				description: "Images to attach per place. 0 disables images.",
			},
		],
		responseNote:
			"The response is { items: [...] } with one item per place. One returned place is one billable unit; attached reviews are metered separately.",
		response: [
			{
				name: "title / categoryName / categories",
				type: "string / string[]",
				description: "Business name and its Google Maps categories.",
			},
			{
				name: "placeId / cid / url",
				type: "string",
				description: "Stable Google identifiers and the place's Maps URL.",
			},
			{
				name: "address / street / city / state / postalCode / countryCode",
				type: "string",
				description: "Full and structured address components.",
			},
			{
				name: "location",
				type: "object",
				description: "Coordinates: { lat, lng }.",
			},
			{
				name: "website / phone",
				type: "string",
				description:
					"Contact details as listed on the profile. Null website is a classic lead-gen signal.",
			},
			{
				name: "totalScore / reviewsCount / reviewsDistribution",
				type: "number / integer / object",
				description: "Average rating, review count, and the one-to-five-star breakdown.",
			},
			{
				name: "permanentlyClosed / temporarilyClosed",
				type: "boolean",
				description: "Business status flags.",
			},
			{
				name: "openingHours",
				type: "object[]",
				description: "Day-by-day hours. Populated when include_details is true.",
			},
			{
				name: "reviews",
				type: "object[]",
				description:
					"Attached reviews when max_reviews > 0: text, stars, publishedAtDate, likesCount, reviewer info, and the owner's response.",
			},
			{
				name: "images / imageUrl / imagesCount",
				type: "object[] / string / integer",
				description: "Photos attached when max_images > 0, plus the cover image and count.",
			},
			{
				name: "searchString / rank",
				type: "string / integer",
				description: "Provenance: which query found this place and its position in the results.",
			},
			{
				name: "scrapedAt",
				type: "string",
				description: "ISO timestamp for when the place was scraped.",
			},
		],
	},

	faq: [
		{
			question: "Is scraping Google Maps legal?",
			answer:
				"SurfSense reads only public Google Maps listings, the business data any visitor can see. It collects no private data and cannot access anything behind a login. Review Google's terms and your own compliance needs, especially around personal data in reviews, before running at scale.",
		},
		{
			question: "How many results can I get per search?",
			answer:
				"Up to 1,000 places per search query, and you can send up to 20 queries, URLs, or place IDs in a single call. Pair a query like 'dentist' with a location such as 'Austin, TX' to scope the search to one market.",
		},
		{
			question: "Does it include reviews and contact details?",
			answer:
				"Yes. Every place includes its phone number and website when Google lists them, plus address and coordinates. Set max_reviews to attach review text and stars per place, or use the dedicated reviews verb when you need deep review history for one location.",
		},
		{
			question: "How is this different from the official Places API?",
			answer:
				"The Places API is metered per call and returns only about five reviews per place. SurfSense returns up to 1,000 places per query with deeper reviews, no Cloud project to set up, and an MCP server so your agents can call it as a native tool.",
		},
	],

	related: [
		{ label: "Reddit API", href: "/reddit" },
		{ label: "YouTube API", href: "/youtube" },
		{ label: "Instagram API", href: "/instagram" },
		{ label: "SERP API", href: "/google-search" },
		{ label: "Web Crawl API", href: "/web-crawl" },
		{ label: "Indeed API", href: "/indeed" },
		{ label: "SurfSense MCP Server", href: "/mcp-server" },
		{ label: "Read the docs", href: "/docs" },
	],
};
