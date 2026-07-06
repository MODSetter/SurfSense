import { IconBrandReddit } from "@tabler/icons-react";
import type { ConnectorPageContent } from "./types";

export const reddit: ConnectorPageContent = {
	slug: "reddit",
	name: "Reddit",
	icon: IconBrandReddit,

	metaTitle: "Reddit Scraper API for Brand Monitoring | SurfSense",
	metaDescription:
		"Track every brand and competitor mention across Reddit with the SurfSense Reddit Scraper API. No official API rate limits or pricing, plus a free tier. Start now.",
	keywords: [
		"reddit scraper",
		"reddit scraper api",
		"reddit api",
		"reddit api alternative",
		"scrape reddit",
		"reddit data api",
		"reddit comment scraper",
		"reddit monitoring tool",
		"reddit sentiment analysis",
		"reddit mcp",
		"social listening",
		"brand monitoring tool",
	],

	h1: "Reddit API for Brand Monitoring and Market Research",
	heroLede:
		"The SurfSense Reddit API extracts posts, comments, subreddits, and user data without the official Reddit API's rate limits or per-call pricing. Give your AI agents a live feed of what your market says about your brand, your competitors, and your category, so you hear it first.",

	transcript: {
		prompt: "See what r/webscraping is saying about our competitor this week",
		toolCall:
			'reddit.scrape({ search_queries: ["competitor"], community: "webscraping",\n  sort: "top", time_filter: "week", max_comments: 50 })',
		rows: [
			{
				primary: "Switched off Competitor after the API price hike",
				secondary: "r/webscraping · 312 upvotes · 0.94 ratio",
				tag: "pricing pain",
			},
			{
				primary: "Anyone got a Competitor alternative that does comments?",
				secondary: "r/webscraping · 148 upvotes · 61 comments",
				tag: "buying intent",
			},
			{
				primary: "Competitor keeps rate-limiting my agent, help",
				secondary: "r/webscraping · 89 upvotes · 44 comments",
				tag: "churn signal",
			},
		],
		resultSummary: "37 posts · 1,204 comments · surfaced in 2.1s",
	},

	extractIntro:
		"Every call returns structured items keyed by type: posts, comments, communities, and users. Point the API at a subreddit, a search query, a post, or a user profile.",
	extractFields: [
		{
			label: "Posts",
			description: "Title, body text, upvotes, upvote ratio, comment count, flair, and permalink.",
		},
		{
			label: "Comments",
			description: "Full comment trees with body, vote counts, reply counts, and parent threading.",
		},
		{
			label: "Communities",
			description: "Subreddit name, member count, and listing metadata for any /r/ community.",
		},
		{
			label: "Users",
			description: "Public profile and authored posts or comments for any /user/ handle.",
		},
		{
			label: "Media",
			description: "Image and video URLs, thumbnails, and NSFW flags attached to each post.",
		},
		{
			label: "Timestamps",
			description:
				"Created and scraped times, with date limits for incremental, delta-only scrapes.",
		},
	],

	useCasesHeading: "What teams do with the Reddit API",
	useCases: [
		{
			title: "Brand and competitor monitoring",
			description:
				"Track every mention of your brand, your competitors, and your category across Reddit. Feed the stream to an agent that flags churn signals, pricing complaints, and buying intent the moment they surface.",
		},
		{
			title: "Voice-of-customer and pain-point mining",
			description:
				"Mine real complaints and feature requests to find your next product idea. Reddit is where people say what they actually think, unfiltered by a survey or a support ticket.",
		},
		{
			title: "Reddit sentiment analysis",
			description:
				"Pull comment trees at depth and score them for sentiment, so you can measure how a launch, a price change, or a competitor's move actually landed with your market.",
		},
		{
			title: "Community research for go-to-market",
			description:
				"Map the subreddits, language, and objections of your buyers before you spend on ads. Turn community research into positioning your GTM team can act on.",
		},
	],

	comparison: {
		heading: "A Reddit API alternative built for agents",
		intro:
			"Reddit's official Data API added rate limits and per-call pricing in 2023. If you are hitting the paywall or the throttle, here is how SurfSense compares.",
		columnLabel: "Official Reddit API",
		rows: [
			{
				feature: "Rate limits",
				official: "Per-OAuth-app quotas that throttle bulk and agent use",
				surfsense: "Managed for you; scale reads without minding the throttle",
			},
			{
				feature: "Pricing",
				official: "Per-call pricing since the 2023 changes",
				surfsense: "Pay per item returned, with a free tier to start",
			},
			{
				feature: "Comment depth",
				official: "Paginated; deep trees are slow and quota-heavy",
				surfsense: "Full comment trees in one call, up to 100 items",
			},
			{
				feature: "Setup",
				official: "Register an OAuth app and manage tokens",
				surfsense: "One API key, or add the MCP server to your agent",
			},
			{
				feature: "Agent-ready",
				official: "No; you build the harness yourself",
				surfsense: "MCP server exposes reddit.scrape as a native tool",
			},
		],
	},

	api: {
		platform: "reddit",
		verb: "scrape",
		mcpTool: "reddit.scrape",
		requestBody: {
			search_queries: ["your brand"],
			community: "webscraping",
			sort: "top",
			time_filter: "week",
			max_comments: 50,
		},
	},

	schema: {
		requestNote:
			"Provide at least one source: urls, search_queries, or community. Up to 20 sources per call.",
		request: [
			{
				name: "urls",
				type: "string[]",
				defaultValue: "[]",
				description:
					"Reddit URLs to scrape: a post, a subreddit (/r/name), a user (/user/name), or a search URL. Max 20.",
			},
			{
				name: "search_queries",
				type: "string[]",
				defaultValue: "[]",
				description:
					"Search terms to run on Reddit. Each returns up to max_items results. Scope to one subreddit with community. Max 20.",
			},
			{
				name: "community",
				type: "string",
				description:
					"Subreddit name without the r/ prefix, e.g. 'python'. Scopes search_queries to that subreddit; with no search_queries, its listing is scraped.",
			},
			{
				name: "sort",
				type: "string",
				defaultValue: '"new"',
				description: "Result ordering: relevance, hot, top, new, rising, or comments.",
			},
			{
				name: "time_filter",
				type: "string",
				description: "Time window for top sorts: hour, day, week, month, year, or all.",
			},
			{
				name: "include_nsfw",
				type: "boolean",
				defaultValue: "true",
				description: "Include posts flagged over-18 in the results.",
			},
			{
				name: "skip_comments",
				type: "boolean",
				defaultValue: "false",
				description: "Skip fetching comment trees. Faster when you only need posts or listings.",
			},
			{
				name: "max_items",
				type: "integer",
				defaultValue: "10",
				description: "Max total items to return across all sources. 1 to 100.",
			},
			{
				name: "max_posts",
				type: "integer",
				defaultValue: "10",
				description: "Max posts to pull per subreddit, user, or search target.",
			},
			{
				name: "max_comments",
				type: "integer",
				defaultValue: "10",
				description: "Max comments to pull per post. 0 disables comments.",
			},
			{
				name: "post_date_limit",
				type: "string",
				description: "ISO date. Only return posts newer than this, for incremental scrapes.",
			},
			{
				name: "comment_date_limit",
				type: "string",
				description: "ISO date. Only return comments newer than this, for incremental scrapes.",
			},
		],
		responseNote:
			"The response is { items: [...] } with one flat item per result, keyed by dataType. Fields that do not apply to a given dataType are null. One returned item is one billable unit.",
		response: [
			{
				name: "dataType",
				type: "string",
				description: "What this item is: post, comment, community, or user.",
			},
			{
				name: "id / url / username",
				type: "string",
				description: "Identity and provenance: the Reddit ID, permalink, and author username.",
			},
			{
				name: "title / body",
				type: "string",
				description: "Post title and full text body (or comment text for comments).",
			},
			{
				name: "communityName",
				type: "string",
				description: "The subreddit the item belongs to, plus numberOfMembers for communities.",
			},
			{
				name: "upVotes / upVoteRatio",
				type: "integer / number",
				description: "Score and upvote ratio, the engagement signal for ranking what matters.",
			},
			{
				name: "numberOfComments",
				type: "integer",
				description: "Comment count on a post; numberOfReplies for comments.",
			},
			{
				name: "flair / over18 / isVideo",
				type: "string / boolean",
				description: "Post flair and content flags.",
			},
			{
				name: "thumbnailUrl / imageUrls / videoUrls",
				type: "string / string[]",
				description: "Media attached to the post.",
			},
			{
				name: "postId / parentId",
				type: "string",
				description: "Threading for comments: the parent post and parent comment IDs.",
			},
			{
				name: "createdAt / scrapedAt",
				type: "string",
				description: "ISO timestamps for when the item was posted and when it was scraped.",
			},
		],
	},

	faq: [
		{
			question: "Is scraping Reddit legal?",
			answer:
				"SurfSense reads only public Reddit data, the same posts and comments any logged-out visitor can see. It never logs in and cannot access private or deleted content. As always, review Reddit's terms and your own compliance needs before you run at scale.",
		},
		{
			question: "Does this bypass the official Reddit API?",
			answer:
				"It is an independent alternative, not a wrapper. You do not register an OAuth app or manage Reddit tokens. You call the SurfSense API with one key, or add the MCP server to your agent, and get structured posts and comments back without the official API's limits.",
		},
		{
			question: "What are the rate limits?",
			answer:
				"Each call caps at 100 returned items across all sources, with up to 20 URLs or search queries per request. SurfSense manages the underlying request budget for you, so you scale reads without registering apps or watching an OAuth quota.",
		},
		{
			question: "How much historical data can I pull?",
			answer:
				"You can scrape a subreddit, user, or search back through its available public history, then use post and comment date limits to run incremental, delta-only scrapes. That keeps repeat monitoring cheap: pull only what is new since your last run.",
		},
	],

	related: [
		{ label: "YouTube API", href: "/youtube" },
		{ label: "Google Maps API", href: "/google-maps" },
		{ label: "SERP API", href: "/google-search" },
		{ label: "Web Crawl API", href: "/web-crawl" },
		{ label: "MCP Connector", href: "/mcp-connector" },
		{ label: "Read the docs", href: "/docs" },
	],
};
