import { IconBrandInstagram } from "@tabler/icons-react";
import type { ConnectorPageContent } from "./types";

export const instagram: ConnectorPageContent = {
	slug: "instagram",
	name: "Instagram",
	icon: IconBrandInstagram,

	metaTitle: "Instagram Scraper API for Creator Research | SurfSense",
	metaDescription:
		"Scrape public Instagram posts, reels, and profiles at scale with the SurfSense Instagram Scraper API. No login, no official API, plus a free tier. Start now.",
	keywords: [
		"instagram scraper",
		"instagram scraper api",
		"instagram api",
		"instagram api alternative",
		"scrape instagram",
		"instagram graph api alternative",
		"instagram profile scraper",
		"instagram post scraper",
		"instagram reel scraper",
		"instagram data api",
		"instagram mcp server",
		"creator research",
		"social listening",
	],

	h1: "Instagram Scraper API for Creator Research and Social Listening",
	heroLede:
		"The SurfSense Instagram API extracts public posts, reels, and profile details without logging in or registering for the Instagram Graph API. Give your AI agents a live feed of what creators post, so you spot trends and shifts in engagement first.",

	transcript: {
		prompt: "Pull recent reels from @competitor and summarize what they're posting",
		toolCall:
			'instagram.scrape({ urls: ["instagram.com/competitor/"],\n  result_type: "reels", max_items: 20 })',
		rows: [
			{
				primary: "Behind the scenes of our new launch",
				secondary: "@competitor · 84.2k likes · 1,203 comments",
				tag: "top reel",
			},
			{
				primary: "Cadence up 40% this month, all short-form reels",
				secondary: "20 reels · 12 days",
				tag: "trend",
			},
			{
				primary: "3 creators tagged asking for a collab",
				secondary: "@a · @b · @c · buying intent",
				tag: "lead signal",
			},
		],
		resultSummary: "20 reels · surfaced in 2.4s",
	},

	extractIntro:
		"Every call returns structured items keyed by type. Point the API at a public profile, post, or reel URL, or discover creators with a search query.",
	extractFields: [
		{
			label: "Posts & Reels",
			description:
				"Caption, hashtags, mentions, like and comment counts, media URLs, dimensions, and timestamp.",
		},
		{
			label: "Profiles",
			description:
				"Follower, following, and post counts, bio, external URL, verified and business flags.",
		},
		{
			label: "Owner & Media",
			description:
				"Owner username and id on every item, plus image and video URLs, alt text, and view counts.",
		},
	],

	useCasesHeading: "What teams do with the Instagram API",
	useCases: [
		{
			title: "Creator and competitor monitoring",
			description:
				"Track what your competitors and target creators post, and how engagement moves. Feed the stream to an agent that flags viral formats, launches, and shifts in cadence the moment they land.",
		},
		{
			title: "Content and format research",
			description:
				"Study a creator's recent posts and reels to see which formats earn the most likes and comments, and turn that into a content calendar your team can act on.",
		},
		{
			title: "Influencer vetting and outreach",
			description:
				"Verify a creator's follower count, post cadence, and real engagement from public data before you pay for a partnership.",
		},
	],

	comparison: {
		heading: "An Instagram API alternative built for agents",
		intro:
			"The official Instagram Graph API requires a Business account, app review, and access tokens, and it can't read arbitrary public profiles. Here is how SurfSense compares.",
		columnLabel: "Instagram Graph API",
		rows: [
			{
				feature: "Access",
				official: "Business/Creator account + app review + tokens",
				surfsense: "Public data only, no login or account required",
			},
			{
				feature: "Coverage",
				official: "Mostly your own or connected accounts",
				surfsense: "Any public profile, post, or reel",
			},
			{
				feature: "Setup",
				official: "Register an app, pass review, manage tokens",
				surfsense: "One API key, or add the MCP server to your agent",
			},
			{
				feature: "Agent-ready",
				official: "No; you build the harness yourself",
				surfsense: "MCP server exposes instagram.scrape as a native tool",
			},
		],
	},

	api: {
		platform: "instagram",
		verb: "scrape",
		mcpTool: "instagram.scrape",
		requestBody: {
			urls: ["instagram.com/natgeo/"],
			result_type: "reels",
			max_items: 20,
		},
	},

	schema: {
		requestNote:
			"Provide exactly one source: urls OR search_queries (never both). Up to 20 sources per call.",
		request: [
			{
				name: "urls",
				type: "string[]",
				defaultValue: "[]",
				description:
					"Instagram URLs or bare profile IDs: profile, post (/p/), or reel (/reel/). Hashtag and place URLs are login-walled and unsupported. Max 20.",
			},
			{
				name: "search_queries",
				type: "string[]",
				defaultValue: "[]",
				description:
					"Discovery keywords resolved to public profiles via Google. Provide these OR urls, not both. Max 20.",
			},
			{
				name: "search_type",
				type: "string",
				defaultValue: '"profile"',
				description:
					"What to discover from search_queries: profile or user. Only used with search_queries.",
			},
			{
				name: "result_type",
				type: "string",
				defaultValue: '"posts"',
				description: "Which feed to return: posts or reels.",
			},
			{
				name: "newer_than",
				type: "string",
				description:
					"Only return posts newer than this: YYYY-MM-DD, ISO timestamp, or relative ('1 day', '2 months'), UTC.",
			},
			{
				name: "skip_pinned_posts",
				type: "boolean",
				defaultValue: "false",
				description: "Exclude pinned posts in posts mode.",
			},
			{
				name: "max_per_target",
				type: "integer",
				defaultValue: "10",
				description: "Max results per URL or per discovered target.",
			},
			{
				name: "max_items",
				type: "integer",
				defaultValue: "10",
				description: "Max total items to return across all sources. 1 to 100.",
			},
			{
				name: "add_parent_data",
				type: "boolean",
				defaultValue: "false",
				description: "Attach a dataSource block to each feed item describing its source.",
			},
		],
		responseNote:
			"The response is { items: [...] } with one flat media item per result. Fields the anonymous endpoints do not expose are null. One returned item is one billable unit.",
		response: [
			{
				name: "id / shortCode / url",
				type: "string",
				description: "Identity and provenance: the media id, shortcode, and canonical post URL.",
			},
			{
				name: "type",
				type: "string",
				description: "Media type: Image, Video, or Sidecar (carousel).",
			},
			{
				name: "caption / hashtags / mentions",
				type: "string / string[]",
				description: "Caption text plus the hashtags and @-mentions parsed from it.",
			},
			{
				name: "likesCount / commentsCount",
				type: "integer",
				description: "Engagement counts. likesCount is -1 when the creator hides likes.",
			},
			{
				name: "displayUrl / videoUrl / videoViewCount",
				type: "string / integer",
				description: "Media URLs and, for videos, the public view count.",
			},
			{
				name: "ownerUsername / ownerId / ownerFullName",
				type: "string",
				description: "The account that posted the item.",
			},
			{
				name: "timestamp",
				type: "string",
				description: "ISO timestamp for when the post was published.",
			},
		],
	},

	faq: [
		{
			question: "Is scraping Instagram legal?",
			answer:
				"SurfSense reads only public Instagram data, the same posts, reels, and profiles any logged-out visitor can see. It never logs in and cannot access private accounts, stories, or login-walled feeds. As always, review Instagram's terms and your own compliance needs before you run at scale.",
		},
		{
			question: "Do I need an Instagram account or the Graph API?",
			answer:
				"No. This is an independent alternative to the Instagram Graph API, not a wrapper. You do not create a Business account, pass app review, or manage access tokens. You call the SurfSense API with one key, or add the MCP server to your agent, and get structured data back.",
		},
		{
			question: "What are the rate limits?",
			answer:
				"Each call caps at 100 returned items across all sources, with up to 20 URLs or search queries per request. SurfSense manages the underlying request budget and proxy rotation for you, so you scale reads without managing tokens.",
		},
		{
			question: "Can I scrape hashtags, places, or comments?",
			answer:
				"No. Instagram login-walls hashtag feeds, place feeds, and comment threads for logged-out visitors, so SurfSense does not offer them. The API focuses on what is reliably public and anonymous: profiles, posts, and reels.",
		},
	],

	related: [
		{ label: "Reddit API", href: "/reddit" },
		{ label: "YouTube API", href: "/youtube" },
		{ label: "Google Maps API", href: "/google-maps" },
		{ label: "SERP API", href: "/google-search" },
		{ label: "SurfSense MCP Server", href: "/mcp-server" },
		{ label: "Read the docs", href: "/docs" },
	],
};
