import { IconBrandInstagram } from "@tabler/icons-react";
import type { ConnectorPageContent } from "./types";

export const instagram: ConnectorPageContent = {
	slug: "instagram",
	name: "Instagram",
	icon: IconBrandInstagram,

	metaTitle: "Instagram API for Profiles, Posts, and Reels | SurfSense",
	metaDescription:
		"Instagram scraper API for public profiles, posts, and reels. No login or Graph API review. Structured data for AI agents, plus a free tier. Start now.",
	keywords: [
		"instagram scraper",
		"instagram scraper api",
		"instagram api",
		"instagram api alternative",
		"scrape instagram",
		"instagram scraping",
		"instagram graph api alternative",
		"instagram profile scraper",
		"instagram post scraper",
		"instagram posts scraper",
		"instagram reel scraper",
		"instagram reels scraper",
		"instagram data scraper",
		"instagram data api",
		"instagram mcp server",
		"creator research",
		"social listening",
	],

	h1: "Instagram API for Profiles, Posts, and Reels",
	heroLede:
		"The SurfSense Instagram scraper extracts public profiles, posts, and reels without logging in or registering for the Instagram Graph API. Give your AI agents a live feed of what creators post, so you spot trends and shifts in engagement first.",

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
		"Every Instagram scraper call returns structured items keyed by type. Point the API at a public profile, post, or reel URL, or discover creators with a search query.",
	extractFields: [
		{
			label: "Posts and reels",
			description:
				"Caption, hashtags, mentions, like and comment counts, media URLs, dimensions, and timestamp from any public post or reel.",
		},
		{
			label: "Profile data",
			description:
				"Follower, following, and post counts, bio, external URL, verified and business flags for public Instagram profiles.",
		},
		{
			label: "Owner and media",
			description:
				"Owner username and id on every item, plus image and video URLs, alt text, and view counts.",
		},
	],

	useCasesHeading: "What teams do with the Instagram scraper API",
	useCases: [
		{
			title: "Creator and competitor monitoring",
			description:
				"Scrape Instagram profiles and feeds to track what competitors and target creators post, and how engagement moves. Feed the stream to an agent that flags viral formats, launches, and shifts in cadence the moment they land.",
		},
		{
			title: "Content and format research",
			description:
				"Pull a creator's recent posts and reels to see which formats earn the most likes and comments, and turn that into a content calendar your team can act on.",
		},
		{
			title: "Influencer vetting and outreach",
			description:
				"Use the Instagram profile scraper to verify follower count, post cadence, and real engagement from public data before you pay for a partnership.",
		},
	],

	comparison: {
		heading: "An Instagram Graph API alternative built for agents",
		intro:
			"The official Instagram Graph API requires a Business account, app review, and access tokens, and it cannot read arbitrary public profiles. SurfSense is an Instagram API alternative for public data. Here is how it compares.",
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
			{
				name: "images / childPosts",
				type: "string[] / object[]",
				description: "Carousel (sidecar) children: each child's media URL and metadata.",
			},
			{
				name: "taggedUsers / coauthorProducers",
				type: "object[]",
				description: "Users tagged in the media and any co-authors credited on it.",
			},
			{
				name: "locationName / locationId / productType / isPinned",
				type: "string / boolean",
				description: "Location tag, product type (feed/clips), and whether the post is pinned.",
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
				"No. This Instagram scraper API is an independent alternative to the Instagram Graph API, not a wrapper. You do not create a Business account, pass app review, or manage access tokens. You call SurfSense with one key, or add the MCP server to your agent, and get structured profile, post, and reel data back.",
		},
		{
			question: "What Instagram data can I scrape?",
			answer:
				"Public profiles, posts, and reels. Each item includes captions, hashtags, mentions, engagement counts, media URLs, and owner metadata. Point the Instagram profile scraper at a handle, or pass post and reel URLs directly. Discover creators with search queries when you do not have a URL yet.",
		},
		{
			question: "What are the rate limits?",
			answer:
				"Each call caps at 100 returned items across all sources, with up to 20 URLs or search queries per request. SurfSense manages the underlying request budget and proxy rotation for you, so you scale reads without managing tokens.",
		},
		{
			question: "Can I scrape hashtags, places, or comments?",
			answer:
				"No. Instagram login-walls hashtag feeds, place feeds, and comment threads for logged-out visitors, so SurfSense does not offer them. You still get each post's comment count, just not the comment text. The API focuses on what is reliably public and anonymous: profiles, posts, and reels.",
		},
	],

	related: [
		{ label: "TikTok API", href: "/tiktok" },
		{ label: "YouTube API", href: "/youtube" },
		{ label: "Reddit API", href: "/reddit" },
		{ label: "Google Maps API", href: "/google-maps" },
		{ label: "SERP API", href: "/google-search" },
		{ label: "Indeed API", href: "/indeed" },
		{ label: "SurfSense MCP Server", href: "/mcp-server" },
	],
};
