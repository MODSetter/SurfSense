import { IconBrandGoogle } from "@tabler/icons-react";
import type { ConnectorPageContent } from "./types";

export const googleSearch: ConnectorPageContent = {
	slug: "google-search",
	name: "Google Search",
	cardTitle: "SERP API",
	icon: IconBrandGoogle,

	metaTitle: "SERP API for Rank Tracking and Competitor Intel | SurfSense",
	metaDescription:
		"Track rankings, competitor ads, and Google AI Overviews with the SurfSense SERP API. Scrape Google Search results as structured JSON via API or MCP. Start free.",
	keywords: [
		"serp api",
		"serp api alternative",
		"cheap serp api",
		"scrape google search results",
		"google search scraper",
		"google search api",
		"rank tracking api",
		"serp scraper api",
		"ai overview monitoring",
		"serp api python",
		"competitor rank tracking",
		"serp analysis",
	],

	h1: "SERP API for Rank Tracking and Competitor SERP Intelligence",
	heroLede:
		"The SurfSense SERP API scrapes Google Search results as structured JSON: organic rankings, paid ads, AI Overviews, and People Also Ask. Point your AI agents at the queries that matter to your market and know the moment a rank moves, an ad appears, or an AI answer starts citing a competitor.",

	transcript: {
		prompt: "Track who's ranking and running ads for 'competitor pricing' in the US",
		toolCall:
			'google_search.scrape({ queries: ["competitor pricing"], country_code: "us",\n  max_pages_per_query: 2 })',
		rows: [
			{
				primary: "competitor.com — #3 organic, up from #7",
				secondary: "google.com/search · desktop · US",
				tag: "+4 spots",
			},
			{
				primary: "AI Overview cites competitor.com and 2 others",
				secondary: "AI Overview · 3 sources",
				tag: "GEO risk",
			},
			{
				primary: "rival.com is running a paid ad at position 1",
				secondary: "paid result · sitelinks · US",
				tag: "new ad",
			},
		],
		resultSummary: "20 organic · 3 ads · 1 AI Overview · surfaced in 2.4s",
	},

	extractIntro:
		"Give the API a list of search terms or full Google URLs and a country. It returns one structured item per SERP page, with every block Google renders parsed into its own array.",
	extractFields: [
		{
			label: "Organic results",
			description:
				"Title, URL, displayed URL, description, date, and rank position for every listing.",
		},
		{
			label: "Paid ads",
			description:
				"Sponsored results and shopping ads with title, URL, sitelinks, prices, and ad position.",
		},
		{
			label: "AI Overviews",
			description:
				"The AI Overview answer text and the exact pages Google cites, for GEO and AI-visibility tracking.",
		},
		{
			label: "People Also Ask",
			description: "The related questions and answers Google expands beneath the results.",
		},
		{
			label: "Related searches",
			description:
				"Suggested and related queries, to map how your market actually phrases its search.",
		},
		{
			label: "SERP metadata",
			description:
				"Total result count, device, page number, and the country and language of each result.",
		},
	],

	useCasesHeading: "What teams do with the SERP API",
	useCases: [
		{
			title: "Rank tracking at agent speed",
			description:
				"Track your rankings and your competitors' across the queries and countries you care about. Feed the positions to an agent that diffs each run and pings you the moment something moves.",
		},
		{
			title: "Competitor ad monitoring",
			description:
				"See who is bidding on your keywords, what their ad copy and sitelinks say, and where they sit on the page. Watch a rival's paid strategy without a single manual search.",
		},
		{
			title: "AI Overview and GEO monitoring",
			description:
				"Capture whether an AI Overview appears for a query and exactly which sources it cites. It is the cleanest way to measure your visibility in AI search, a signal almost nobody is tracking yet.",
		},
		{
			title: "SERP and keyword research",
			description:
				"Pull People Also Ask and related queries at scale to see the questions and phrasings behind a topic, then brief an agent to turn them into a content plan.",
		},
	],

	comparison: {
		heading: "A SERP API alternative built for agents",
		intro:
			"Most SERP APIs bill per search, gate AI Overviews behind add-ons, and leave the rank-tracking logic to you. Here is how SurfSense compares.",
		columnLabel: "Typical SERP API",
		rows: [
			{
				feature: "Pricing",
				official: "Per-search pricing that climbs fast at scale",
				surfsense: "Pay per SERP page returned, with a free tier to start",
			},
			{
				feature: "AI Overviews",
				official: "Often a paid add-on, or not supported at all",
				surfsense: "Parsed inline with the answer text and the sources it cites",
			},
			{
				feature: "Rank tracking",
				official: "You build the diffing and alerting yourself",
				surfsense: "Structured positions your agent can diff and alert on",
			},
			{
				feature: "Setup",
				official: "A new vendor account and key management",
				surfsense: "One API key, or add the MCP server to your agent",
			},
			{
				feature: "Agent-ready",
				official: "No; you wire the harness yourself",
				surfsense: "MCP server exposes google_search.scrape as a native tool",
			},
		],
	},

	api: {
		platform: "google_search",
		verb: "scrape",
		mcpTool: "google_search.scrape",
		requestBody: {
			queries: ["competitor pricing"],
			country_code: "us",
			max_pages_per_query: 2,
		},
	},

	schema: {
		requestNote: "Only queries is required. Up to 20 queries per call.",
		request: [
			{
				name: "queries",
				type: "string[]",
				required: true,
				description:
					"Search terms (e.g. 'wedding photographers denver') or full Google Search URLs. Each term is searched; each URL is scraped as-is. 1 to 20.",
			},
			{
				name: "max_pages_per_query",
				type: "integer",
				defaultValue: "1",
				description: "Result pages to fetch per query, 1 to 10. 1 fetches the first page only.",
			},
			{
				name: "country_code",
				type: "string",
				description: "Two-letter country to search from, e.g. 'us', 'fr'.",
			},
			{
				name: "language_code",
				type: "string",
				defaultValue: '""',
				description: "Result language code, e.g. 'en', 'fr'. Blank uses Google's default.",
			},
			{
				name: "site",
				type: "string",
				description: "Restrict results to a single domain, e.g. 'example.com'.",
			},
		],
		responseNote:
			"The response is { items: [...] } with one item per fetched SERP page. One fetched page is one billable unit.",
		response: [
			{
				name: "searchQuery",
				type: "object",
				description:
					"Provenance for this page: the term or URL searched, page number, device, country, and language.",
			},
			{
				name: "resultsTotal",
				type: "integer",
				description: "Google's estimated total result count for the query.",
			},
			{
				name: "organicResults",
				type: "object[]",
				description:
					"The organic listings: title, url, displayedUrl, description, date, emphasizedKeywords, siteLinks, and position.",
			},
			{
				name: "paidResults / paidProducts",
				type: "object[]",
				description: "Ads and shopping placements on the page, with titles, URLs, and prices.",
			},
			{
				name: "relatedQueries",
				type: "object[]",
				description: "The 'related searches' block: title and search URL for each suggestion.",
			},
			{
				name: "peopleAlsoAsk",
				type: "object[]",
				description: "People Also Ask entries with the question, answer text, and source page URL.",
			},
			{
				name: "aiOverview",
				type: "object",
				description:
					"The AI Overview block when Google shows one: full answer content plus the sources it cites.",
			},
		],
	},

	faq: [
		{
			question: "What is a SERP API?",
			answer:
				"A SERP API returns the contents of a search engine results page as structured data instead of raw HTML. The SurfSense SERP API scrapes Google Search and gives you organic results, ads, AI Overviews, and People Also Ask as clean JSON your agents can read.",
		},
		{
			question: "Can I track keyword rankings with it?",
			answer:
				"Yes. Each organic result includes its rank position, and every item is stamped with the query, country, and language it came from. Run the same queries on a schedule and diff the positions to build rank tracking, without maintaining scrapers or proxies.",
		},
		{
			question: "Does it capture Google AI Overviews?",
			answer:
				"It does. When an AI Overview appears for a query, the response includes its answer text and the list of pages Google cites as sources. That makes it straightforward to monitor whether AI search is surfacing you or your competitors.",
		},
		{
			question: "How is this different from SerpApi or the Google Search API?",
			answer:
				"You get one API key instead of a new vendor relationship, AI Overviews parsed inline rather than as a paid add-on, and an MCP server so your agents can call google_search.scrape as a native tool. Pricing is per SERP page returned, with a free tier.",
		},
	],

	related: [
		{ label: "Web Crawl API", href: "/web-crawl" },
		{ label: "Google Maps API", href: "/google-maps" },
		{ label: "Reddit API", href: "/reddit" },
		{ label: "Instagram API", href: "/instagram" },
		{ label: "SurfSense MCP Server", href: "/mcp-server" },
		{ label: "Read the docs", href: "/docs" },
	],
};
