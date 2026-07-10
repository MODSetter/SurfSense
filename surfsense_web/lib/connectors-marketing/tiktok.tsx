import { IconBrandTiktok } from "@tabler/icons-react";
import type { ConnectorPageContent } from "./types";

export const tiktok: ConnectorPageContent = {
	slug: "tiktok",
	name: "TikTok",
	icon: IconBrandTiktok,

	metaTitle: "TikTok Scraper API for Trend and Creator Research | SurfSense",
	metaDescription:
		"Scrape public TikTok videos, comments, accounts, and trending feeds by hashtag, profile, or URL with the SurfSense TikTok Scraper API. No approval process or research-API gatekeeping, plus a free tier. Start now.",
	keywords: [
		"tiktok scraper",
		"tiktok scraper api",
		"tiktok api",
		"tiktok api alternative",
		"scrape tiktok",
		"tiktok data api",
		"tiktok hashtag scraper",
		"tiktok comments scraper",
		"tiktok trending scraper",
		"tiktok user search",
		"tiktok trend tracking",
		"tiktok mcp",
		"social listening",
		"influencer research tool",
		"short-form video analytics",
	],

	h1: "TikTok Scraper API for Trend and Creator Research",
	heroLede:
		"The SurfSense TikTok API extracts public videos by hashtag, creator profile, or URL without TikTok's approval-gated Research API. Give your AI agents a live feed of what your market watches and shares, so you catch a trend while it is still rising.",

	transcript: {
		prompt: "Find trending TikToks about meal prep this week",
		toolCall: 'tiktok.scrape({ hashtags: ["mealprep"], max_items: 25 })',
		rows: [
			{
				primary: "5 high-protein lunches under 400 cals",
				secondary: "@fitmeals · 2.1M plays · 184K likes",
				tag: "breakout",
			},
			{
				primary: "The $20 weekly meal prep everyone's copying",
				secondary: "@budgetbites · 980K plays · 72K likes",
				tag: "rising",
			},
			{
				primary: "POV: your fridge after Sunday meal prep",
				secondary: "@cleaneats · 640K plays · 51K likes",
				tag: "high engagement",
			},
		],
		resultSummary: "25 videos · 8.4M plays · surfaced in 3.2s",
	},

	extractIntro:
		"Every call returns structured items. Scrape videos from a hashtag, creator profile, or video URL — or switch verbs to pull a video's comments, discover accounts by keyword, or fetch the current trending feed.",
	extractFields: [
		{
			label: "Videos",
			description: "Caption text, canonical web URL, duration, and cover image for each video.",
		},
		{
			label: "Engagement",
			description:
				"Play, like, comment, share, and save counts — the signal for what is breaking out.",
		},
		{
			label: "Authors",
			description: "Creator handle, nickname, follower and heart counts, and verified status.",
		},
		{
			label: "Music",
			description: "Track name, artist, and whether the sound is original — the seed of a trend.",
		},
		{
			label: "Hashtags",
			description: "Every hashtag on a video, so you can map a topic cluster or campaign.",
		},
		{
			label: "Timestamps",
			description: "Created and scraped times so you can track a video's momentum over runs.",
		},
	],

	useCasesHeading: "What teams do with the TikTok API",
	useCases: [
		{
			title: "Trend and hashtag monitoring",
			description:
				"Track a hashtag and feed the stream to an agent that flags breakout videos, rising sounds, and formats before they saturate. Catch the wave while it is still rising, not after.",
		},
		{
			title: "Creator and influencer discovery",
			description:
				"Surface the creators driving a topic, ranked by real engagement, so your team shortlists partners from data instead of a manager's pitch deck.",
		},
		{
			title: "Competitor content analysis",
			description:
				"Watch what your category posts and what actually lands. Turn a competitor's best-performing formats and hooks into your own content brief.",
		},
		{
			title: "Campaign and sentiment tracking",
			description:
				"Measure how a launch or branded hashtag spreads across TikTok — video count, reach, and engagement over time — then pull the comments on top videos to read how the audience actually reacts, not just a vanity view count.",
		},
	],

	comparison: {
		heading: "A TikTok API alternative built for agents",
		intro:
			"TikTok's official Research API is approval-gated and largely limited to academic and nonprofit use. If you cannot get access or need it for commercial research, here is how SurfSense compares.",
		columnLabel: "Official TikTok API",
		rows: [
			{
				feature: "Access",
				official: "Application and approval, often restricted to academic/nonprofit use",
				surfsense: "One API key, no approval process",
			},
			{
				feature: "Pricing",
				official: "Free but gated, with usage quotas per approved project",
				surfsense: "Pay per item returned, with a free tier to start",
			},
			{
				feature: "Signing",
				official: "You manage the client-side signature that TikTok rotates",
				surfsense: "Handled for you; a real browser signs each request",
			},
			{
				feature: "Setup",
				official: "Register a developer app and await review",
				surfsense: "One API key, or add the MCP server to your agent",
			},
			{
				feature: "Agent-ready",
				official: "No; you build the harness yourself",
				surfsense: "MCP server exposes scrape, comments, user search, and trending as native tools",
			},
		],
	},

	api: {
		platform: "tiktok",
		verb: "scrape",
		mcpTool: "tiktok.scrape",
		requestBody: {
			hashtags: ["mealprep"],
			max_items: 25,
		},
	},

	schema: {
		requestNote:
			"Provide at least one source: urls, profiles, hashtags, or search_queries. Up to 20 sources per call.",
		request: [
			{
				name: "urls",
				type: "string[]",
				defaultValue: "[]",
				description:
					"TikTok URLs to scrape: a video, a profile (/@user), or a hashtag (/tag/name). Max 20.",
			},
			{
				name: "profiles",
				type: "string[]",
				defaultValue: "[]",
				description: "Profile usernames to scrape, with or without a leading @. Max 20.",
			},
			{
				name: "hashtags",
				type: "string[]",
				defaultValue: "[]",
				description: "Hashtag names to scrape, without the # prefix. Max 20.",
			},
			{
				name: "search_queries",
				type: "string[]",
				defaultValue: "[]",
				description:
					"Keyword search terms. Keyword video search is login-walled and returns no videos — use hashtags/profiles/urls for videos, or user_search for accounts. Max 20.",
			},
			{
				name: "results_per_page",
				type: "integer",
				defaultValue: "10",
				description: "Max videos to pull per profile or hashtag target. 1 to 100.",
			},
			{
				name: "max_items",
				type: "integer",
				defaultValue: "10",
				description: "Max total videos to return across all sources. 1 to 100.",
			},
		],
		responseNote:
			"The response is { items: [...] } with one video item per result. One returned item is one billable unit.",
		response: [
			{
				name: "id / webVideoUrl",
				type: "string",
				description: "The TikTok video ID and its canonical web URL.",
			},
			{
				name: "text",
				type: "string",
				description: "The video caption, including inline hashtags and mentions.",
			},
			{
				name: "authorMeta",
				type: "object",
				description: "Creator handle, nickname, follower and heart counts, and verified flag.",
			},
			{
				name: "musicMeta",
				type: "object",
				description: "Track name, artist, and whether the sound is original.",
			},
			{
				name: "videoMeta",
				type: "object",
				description: "Duration, dimensions, and cover image for the video.",
			},
			{
				name: "playCount / diggCount",
				type: "integer",
				description: "Play count and like (digg) count, the core reach and engagement signals.",
			},
			{
				name: "commentCount / shareCount",
				type: "integer",
				description: "Comment and share counts for measuring conversation and spread.",
			},
			{
				name: "hashtags",
				type: "object[]",
				description: "The hashtags attached to the video, for topic and campaign mapping.",
			},
			{
				name: "createTimeISO / scrapedAt",
				type: "string",
				description: "ISO timestamps for when the video was posted and when it was scraped.",
			},
		],
	},

	faq: [
		{
			question: "Is scraping TikTok legal?",
			answer:
				"SurfSense reads only public TikTok data, the same videos any logged-out visitor can see. It never logs in and cannot access private or deleted content. As always, review TikTok's terms and your own compliance needs before you run at scale.",
		},
		{
			question: "Does this need the official TikTok API?",
			answer:
				"No. It is an independent alternative, not a wrapper on the Research API, so there is no application or approval process. You call the SurfSense API with one key, or add the MCP server to your agent, and get structured videos back.",
		},
		{
			question: "What are the rate limits?",
			answer:
				"Each call caps at 100 returned videos across all sources, with up to 20 hashtags, profiles, or URLs per request. SurfSense manages the underlying request budget and request signing for you.",
		},
		{
			question: "Can I scrape a specific creator's videos?",
			answer:
				"Pass a profile or profile URL and you always get the account's metadata — name, followers, bio, verification. TikTok often withholds the profile video list from automated clients, so that list can come back empty even for a public account; for reliable video results, scrape by hashtag or by a direct video URL.",
		},
		{
			question: "What TikTok data can I scrape?",
			answer:
				"Four verbs: scrape (videos by hashtag, profile, or URL), comments (a video's public comment thread), user search (find accounts by keyword — the reliable discovery path, since keyword video search is login-walled), and trending (the current Explore feed). Each returns structured items and is billed per item returned.",
		},
	],

	related: [
		{ label: "Reddit API", href: "/reddit" },
		{ label: "YouTube API", href: "/youtube" },
		{ label: "Google Maps API", href: "/google-maps" },
		{ label: "SERP API", href: "/google-search" },
		{ label: "Web Crawl API", href: "/web-crawl" },
		{ label: "SurfSense MCP Server", href: "/mcp-server" },
	],
};
