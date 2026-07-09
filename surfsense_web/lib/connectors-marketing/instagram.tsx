import { IconBrandInstagram } from "@tabler/icons-react";
import type { ConnectorPageContent } from "./types";

export const instagram: ConnectorPageContent = {
	slug: "instagram",
	name: "Instagram",
	icon: IconBrandInstagram,

	metaTitle: "Instagram Scraper API for Social Listening | SurfSense",
	metaDescription:
		"Scrape public Instagram posts, reels, comments, and profiles at scale with the SurfSense Instagram Scraper API. No login, no official API, plus a free tier. Start now.",
	keywords: [
		"instagram scraper",
		"instagram scraper api",
		"instagram api",
		"instagram api alternative",
		"scrape instagram",
		"instagram graph api alternative",
		"instagram comment scraper",
		"instagram profile scraper",
		"instagram hashtag scraper",
		"instagram data api",
		"instagram mcp server",
		"instagram sentiment analysis",
		"social listening",
	],

	h1: "Instagram Scraper API for Social Listening and Creator Research",
	heroLede:
		"The SurfSense Instagram API extracts public posts, reels, comments, and profile, hashtag, and place details without logging in or registering for the Instagram Graph API. Give your AI agents a live feed of what creators post and what their audiences say, so you spot trends and sentiment first.",

	transcript: {
		prompt: "Pull recent reels from @competitor and tell me what the comments think",
		toolCall:
			'instagram.scrape({ urls: ["instagram.com/competitor/"],\n  result_type: "reels", max_items: 20 })',
		rows: [
			{
				primary: "Behind the scenes of our new launch",
				secondary: "@competitor · 84.2k likes · 1,203 comments",
				tag: "top reel",
			},
			{
				primary: "Comments skew positive on price, negative on shipping",
				secondary: "1,203 comments · 0.71 positive",
				tag: "sentiment",
			},
			{
				primary: "3 creators tagged asking for a collab",
				secondary: "@a · @b · @c · buying intent",
				tag: "lead signal",
			},
		],
		resultSummary: "20 reels · 4,910 comments · surfaced in 2.4s",
	},

	extractIntro:
		"Every call returns structured items keyed by type. Point the API at a profile, post, reel, hashtag, or place URL, or discover content with a search query.",
	extractFields: [
		{
			label: "Posts & Reels",
			description:
				"Caption, hashtags, mentions, like and comment counts, media URLs, dimensions, and timestamp.",
		},
		{
			label: "Comments",
			description: "Comment text, author, like and reply counts, and nested replies for any post.",
		},
		{
			label: "Profiles",
			description:
				"Follower, following, and post counts, bio, external URL, verified and business flags.",
		},
		{
			label: "Hashtags",
			description: "Post volume, top posts, and recent posts for any /explore/tags/ hashtag.",
		},
		{
			label: "Places",
			description: "Name, coordinates, address, and recent posts for any /explore/locations/ place.",
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
				"Track what your competitors and target creators post, and how their audiences react. Feed the stream to an agent that flags viral formats, launches, and shifts in engagement the moment they land.",
		},
		{
			title: "Audience sentiment and comment mining",
			description:
				"Pull full comment threads on a post or reel and score them for sentiment, so you can measure how a launch, a collab, or a campaign actually resonated with real followers.",
		},
		{
			title: "Hashtag and trend research",
			description:
				"Map the volume and top content behind any hashtag before you spend on a campaign. Turn trend research into a content calendar your team can act on.",
		},
		{
			title: "Influencer vetting and outreach",
			description:
				"Verify a creator's follower count, post cadence, and real engagement from public data before you pay for a partnership, and surface who is already mentioning your brand.",
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
				surfsense: "Any public profile, post, hashtag, or place",
			},
			{
				feature: "Comments",
				official: "Limited to accounts you manage",
				surfsense: "Public comments and replies on any post, up to 50 per post",
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
					"Instagram URLs or bare profile IDs: profile, post (/p/), reel (/reel/), hashtag (/explore/tags/), or place (/explore/locations/). Max 20.",
			},
			{
				name: "search_queries",
				type: "string[]",
				defaultValue: "[]",
				description:
					"Discovery keywords (hashtags as plaintext, no '#'). Provide these OR urls, not both. Max 20.",
			},
			{
				name: "search_type",
				type: "string",
				defaultValue: '"hashtag"',
				description:
					"What to discover from search_queries: hashtag, profile, place, or user. Only used with search_queries.",
			},
			{
				name: "result_type",
				type: "string",
				defaultValue: '"posts"',
				description: "Which feed to return: posts, reels, or mentions. 'mentions' requires profile URLs.",
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
				"SurfSense reads only public Instagram data, the same posts, reels, and comments any logged-out visitor can see. It never logs in and cannot access private accounts or stories. As always, review Instagram's terms and your own compliance needs before you run at scale.",
		},
		{
			question: "Do I need an Instagram account or the Graph API?",
			answer:
				"No. This is an independent alternative to the Instagram Graph API, not a wrapper. You do not create a Business account, pass app review, or manage access tokens. You call the SurfSense API with one key, or add the MCP server to your agent, and get structured data back.",
		},
		{
			question: "What are the rate limits?",
			answer:
				"Each call caps at 100 returned items across all sources, with up to 20 URLs or search queries per request, and up to 50 comments per post. SurfSense manages the underlying request budget and proxy rotation for you, so you scale reads without managing tokens.",
		},
		{
			question: "Can I get comments and replies?",
			answer:
				"Yes. The instagram.comments verb returns public comments on any post or reel, with author, like and reply counts, and optionally the nested replies. Get post URLs first from instagram.scrape if you only have a topic or a profile.",
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
