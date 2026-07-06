import { IconWorldWww } from "@tabler/icons-react";
import type { ConnectorPageContent } from "./types";

export const webCrawl: ConnectorPageContent = {
	slug: "web-crawl",
	name: "Web Crawl",
	cardTitle: "Web Crawl API",
	icon: IconWorldWww,

	metaTitle: "Web Crawl API for AI Agents and Deep Research | SurfSense",
	metaDescription:
		"Point your agents at any URL and get clean, LLM-ready markdown, links, and contacts back. The SurfSense Web Crawl API for deep research and competitor monitoring. Start free.",
	keywords: [
		"web crawl api",
		"web crawler api",
		"web crawling api",
		"firecrawl alternative",
		"llm web scraping",
		"agentic web scraping",
		"deep research api",
		"web scraping mcp",
		"competitor price monitoring",
		"crawl website for ai",
		"website to markdown",
		"web data for ai",
	],

	h1: "Web Crawl API: Turn Any Website into Agent-Ready Context",
	heroLede:
		"The SurfSense Web Crawl API points your AI agents at any URL and returns clean, LLM-ready markdown, structured links, and harvested contacts. Scrape a single page or spider a whole site, with the same agent harness that powers our platform connectors.",

	transcript: {
		prompt: "Crawl our top competitor's site and pull their pricing and contacts",
		toolCall:
			'web.crawl({ startUrls: ["https://competitor.com"], maxCrawlDepth: 2,\n  maxCrawlPages: 50 })',
		rows: [
			{
				primary: "/pricing — Pro plan now $49/mo, up from $39",
				secondary: "markdown · depth 1 · success",
				tag: "price change",
			},
			{
				primary: "sales@competitor.com",
				secondary: "found on 12 pages · site-wide",
				tag: "contact",
			},
			{
				primary: "linkedin.com/in/their-head-of-sales",
				secondary: "team page · anchor: 'VP Sales'",
				tag: "social",
			},
		],
		resultSummary: "50 pages · 41 markdown · 6 contacts · surfaced in 8.3s",
	},

	extractIntro:
		"Give the API one or more start URLs. With depth 0 it scrapes just those pages; with a higher depth it spiders the site, bounded by your page cap, and returns one structured item per page.",
	extractFields: [
		{
			label: "Clean markdown",
			description:
				"Cleaned, LLM-ready markdown for every page, truncated to the character limit you set.",
		},
		{
			label: "Page metadata",
			description:
				"Title, description, and other metadata, plus the URL, fetch status, and crawl depth.",
		},
		{
			label: "Links",
			description:
				"Every link with its anchor text and kind: internal, external, social, email, or tel.",
		},
		{
			label: "Contacts",
			description:
				"Emails, phone numbers, and social profiles harvested from each page's raw HTML.",
		},
		{
			label: "Site-wide contacts",
			description:
				"A deduplicated roll-up that separates company boilerplate from page-local people, with provenance.",
		},
		{
			label: "Crawl control",
			description:
				"Depth, page cap, and include or exclude URL regex patterns to keep the spider on target.",
		},
	],

	useCasesHeading: "What teams do with the Web Crawl API",
	useCases: [
		{
			title: "Deep research over the open web",
			description:
				"Let an agent crawl dozens of sources on a topic, collect clean markdown, and synthesize an answer with citations. A deep-research API that reads the live web, not a stale index.",
		},
		{
			title: "Competitor website monitoring",
			description:
				"Crawl a rival's pricing, product, and changelog pages on a schedule and diff them. Catch a price change, a new feature, or a repositioning the day it ships, not the quarter after.",
		},
		{
			title: "Lead and contact enrichment",
			description:
				"Spider a company site and pull emails, phone numbers, and social profiles with provenance, so your agent knows which contact belongs to the company and which to a specific person.",
		},
		{
			title: "RAG and knowledge-base ingestion",
			description:
				"Turn any set of sites into clean markdown ready to embed. Feed a knowledge base or a RAG pipeline without writing a parser or babysitting a headless browser.",
		},
	],

	comparison: {
		heading: "A Firecrawl alternative with an agent harness",
		intro:
			"Commodity crawlers hand you markdown and leave the rest to you. SurfSense adds the harness, the contact extraction, and the platform connectors around it.",
		columnLabel: "Commodity crawler",
		rows: [
			{
				feature: "Output",
				official: "Markdown or HTML you post-process yourself",
				surfsense: "Markdown plus parsed links, contacts, and site-wide roll-ups",
			},
			{
				feature: "Contacts",
				official: "Not extracted; you write the regex",
				surfsense: "Emails, phones, and socials harvested with page provenance",
			},
			{
				feature: "Scope",
				official: "One site at a time",
				surfsense: "Crawl the open web, then combine with platform connectors in one workflow",
			},
			{
				feature: "Pricing",
				official: "Per-page credits that add up quickly",
				surfsense: "Pay per successful page, with a free tier to start",
			},
			{
				feature: "Agent-ready",
				official: "An SDK you wire into your own harness",
				surfsense: "MCP server exposes web.crawl as a native tool",
			},
		],
	},

	api: {
		platform: "web",
		verb: "crawl",
		mcpTool: "web.crawl",
		requestBody: {
			startUrls: ["https://competitor.com"],
			maxCrawlDepth: 2,
			maxCrawlPages: 50,
		},
	},

	schema: {
		requestNote:
			"Only startUrls is required. With maxCrawlDepth 0 the call scrapes exactly those URLs; with a higher depth it spiders the site from them.",
		request: [
			{
				name: "startUrls",
				type: "string[]",
				required: true,
				description:
					"Seed URLs to crawl, 1 to 20. With maxCrawlDepth 0 only these are fetched; otherwise they are the spider's entry points.",
			},
			{
				name: "maxCrawlDepth",
				type: "integer",
				defaultValue: "0",
				description:
					"Link-hops to follow from each start URL, 0 to 5. 0 scrapes only the start URLs; 1 also fetches their linked pages. The spider stays on the start URL's site.",
			},
			{
				name: "maxCrawlPages",
				type: "integer",
				defaultValue: "10",
				description:
					"Max pages to fetch in total, start URLs included, 1 to 200. The crawl stops at this ceiling.",
			},
			{
				name: "maxLength",
				type: "integer",
				defaultValue: "50000",
				description: "Max characters of cleaned markdown kept per page. Longer pages truncate.",
			},
			{
				name: "includeUrlPatterns",
				type: "string[]",
				defaultValue: "[]",
				description:
					"Regex patterns a discovered link must match to be followed. Empty follows every same-site link. Start URLs are always fetched. Max 25.",
			},
			{
				name: "excludeUrlPatterns",
				type: "string[]",
				defaultValue: "[]",
				description:
					"Regex patterns that exclude a discovered link from being followed. Wins over includeUrlPatterns. Max 25.",
			},
		],
		responseNote:
			"The response is { items: [...], contacts: {...} }: one item per fetched page in crawl order, plus site-wide deduplicated contacts. Only successful pages are billed.",
		response: [
			{
				name: "items[].url / status",
				type: "string",
				description:
					"The requested URL and its outcome: success, empty (fetched but no content), or failed.",
			},
			{
				name: "items[].markdown",
				type: "string",
				description: "The page's content as cleaned markdown, ready for an LLM or a diff.",
			},
			{
				name: "items[].metadata",
				type: "object",
				description: "Page metadata such as title and description.",
			},
			{
				name: "items[].crawl",
				type: "object",
				description:
					"Crawl provenance: the URL actually loaded, its link depth, and the referrer page it was discovered on.",
			},
			{
				name: "items[].links",
				type: "object[]",
				description:
					"Every link on the page with its anchor text and kind: internal, external, social, email, or tel.",
			},
			{
				name: "items[].contacts",
				type: "object",
				description:
					"Emails, phones, and social profile URLs harvested from the page's raw HTML, including footer boilerplate the markdown omits.",
			},
			{
				name: "items[].error",
				type: "string",
				description: "Failure reason when status is not success.",
			},
			{
				name: "contacts",
				type: "object",
				description:
					"Site-wide contact rollup: every email, phone, and social URL deduplicated across pages, each with the pages it appeared on and a siteWide flag separating company boilerplate from page-local finds like team members.",
			},
		],
	},

	faq: [
		{
			question: "What formats does the Web Crawl API return?",
			answer:
				"Every page comes back as cleaned, LLM-ready markdown, alongside structured JSON for its metadata, links, and contacts. You set the maximum characters kept per page, so you control how much content each result carries.",
		},
		{
			question: "Can it crawl a whole site or just one page?",
			answer:
				"Both. Set maxCrawlDepth to 0 to scrape only the URLs you pass in, or raise it to spider the site, following links hop by hop. maxCrawlPages caps the total pages fetched, and the spider stays on the start URL's site.",
		},
		{
			question: "Does it handle JavaScript-heavy sites?",
			answer:
				"Yes. The underlying engine renders dynamic pages and waits for content to load automatically, so you get the same markdown a browser would show. You do not configure a headless browser or manage proxies yourself.",
		},
		{
			question: "How is this different from Firecrawl?",
			answer:
				"You get more than markdown: parsed links, harvested contacts with provenance, and an MCP server that exposes web.crawl as a native agent tool. It shares one harness and workspace with the SurfSense platform connectors, so a crawl and a Reddit or Maps pull live in the same workflow.",
		},
	],

	related: [
		{ label: "SERP API", href: "/google-search" },
		{ label: "Google Maps API", href: "/google-maps" },
		{ label: "Reddit API", href: "/reddit" },
		{ label: "MCP Connector", href: "/mcp-connector" },
		{ label: "Read the docs", href: "/docs" },
	],
};
