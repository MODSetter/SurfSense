import { IconBrandYoutube } from "@tabler/icons-react";
import type { ConnectorPageContent } from "./types";

export const youtube: ConnectorPageContent = {
	slug: "youtube",
	name: "YouTube",
	icon: IconBrandYoutube,

	metaTitle: "YouTube Data API for Comments and Transcripts | SurfSense",
	metaDescription:
		"Scrape YouTube videos, comments, and transcripts at scale with the SurfSense YouTube Scraper API. No Data API quotas, plus a free tier for AI agents. Start now.",
	keywords: [
		"youtube scraper",
		"youtube scraper api",
		"youtube comment scraper",
		"youtube comments api",
		"youtube data api",
		"youtube data api alternative",
		"youtube channel scraper",
		"youtube transcript scraper",
		"youtube mcp server",
		"youtube sentiment analysis",
		"audience research tools",
	],

	h1: "YouTube Data API for Comments, Transcripts, and Audience Sentiment",
	heroLede:
		"The SurfSense YouTube API pulls videos, channel stats, comments, and transcripts at scale, without YouTube Data API quotas. Feed your AI agents every comment and transcript that matters to your research, so you know what audiences actually think about any product, topic, or channel.",

	transcript: {
		prompt: "Summarize how people reacted in the comments on our launch video",
		toolCall:
			'youtube.comments({ urls: ["youtube.com/watch?v=launch"],\n  max_comments: 500, sort_by: "TOP_COMMENTS" })',
		rows: [
			{
				primary: '"Finally an API that does not throttle my agent"',
				secondary: "@devbuilds · 214 likes · creator hearted",
				tag: "positive",
			},
			{
				primary: '"How does pricing compare to the incumbent?"',
				secondary: "@growthlee · 96 likes · 12 replies",
				tag: "buying intent",
			},
			{
				primary: '"Does it handle transcripts too or just metadata?"',
				secondary: "@ml_ana · 71 likes · 8 replies",
				tag: "feature ask",
			},
		],
		resultSummary: "500 comments · 78% positive · surfaced in 3.4s",
	},

	extractIntro:
		"Give the API video URLs, channel or playlist URLs, or search queries. It returns structured video items; a separate comments call returns full comment and reply trees for any video.",
	extractFields: [
		{
			label: "Video metadata",
			description: "Title, view count, likes, duration, publish date, hashtags, and description.",
		},
		{
			label: "Channel stats",
			description: "Subscriber count, total views, total videos, join date, and verified status.",
		},
		{
			label: "Comments and replies",
			description: "Author, comment text, vote counts, reply counts, and creator-heart flags.",
		},
		{
			label: "Transcripts",
			description: "Subtitle tracks per video in the language you request, ready as agent context.",
		},
		{
			label: "Content types",
			description: "Standard videos, Shorts, and live streams, capped independently per source.",
		},
		{
			label: "Engagement",
			description: "Likes, comment counts, and monetization or members-only flags per video.",
		},
	],

	useCasesHeading: "What teams do with the YouTube API",
	useCases: [
		{
			title: "Comment sentiment at scale",
			description:
				"Read every comment on your launch video or a competitor's ad, not a sample. Score product feedback and ad reaction so your team knows what actually resonated with the audience.",
		},
		{
			title: "Channel analysis",
			description:
				"Pull any channel's full catalog with views, likes, and cadence to see which content wins in a niche, then brief an agent to spot the patterns worth copying.",
		},
		{
			title: "Influencer vetting",
			description:
				"Before you sponsor a creator, scrape their real view counts, comment sentiment, and posting history so you pay for genuine reach instead of a vanity subscriber number.",
		},
		{
			title: "Transcripts as agent context",
			description:
				"Download transcripts to feed RAG pipelines and research agents. Turn hours of video into searchable, citable context your agents can reason over in seconds.",
		},
	],

	comparison: {
		heading: "A YouTube Data API alternative without the quota",
		intro:
			"The official YouTube Data API gives you 10,000 units a day, and reading comments burns through it fast. Here is how SurfSense compares.",
		columnLabel: "YouTube Data API",
		rows: [
			{
				feature: "Quota",
				official: "10,000 units per day; comment reads drain it fast",
				surfsense: "No daily unit quota; pay per item returned",
			},
			{
				feature: "Comments",
				official: "Paginated and quota-heavy at depth",
				surfsense: "Up to 100,000 comments and replies per video",
			},
			{
				feature: "Transcripts",
				official: "Not available through the official API",
				surfsense: "Subtitle tracks included, in the language you pick",
			},
			{
				feature: "Setup",
				official: "Google Cloud project, OAuth, and API key",
				surfsense: "One API key, or add the MCP server to your agent",
			},
			{
				feature: "Agent-ready",
				official: "No; you build the harness yourself",
				surfsense: "MCP server exposes youtube.scrape as a native tool",
			},
		],
	},

	api: {
		platform: "youtube",
		verb: "scrape",
		mcpTool: "youtube.scrape",
		requestBody: {
			search_queries: ["your topic"],
			max_results: 50,
			download_subtitles: true,
			subtitles_language: "en",
		},
	},

	schema: {
		requestNote: "Provide at least one source: urls or search_queries. Up to 20 of each per call.",
		request: [
			{
				name: "urls",
				type: "string[]",
				defaultValue: "[]",
				description:
					"YouTube URLs to scrape: a video, channel (/@handle or /channel/UC...), playlist (?list=...), shorts, or hashtag page. Max 20.",
			},
			{
				name: "search_queries",
				type: "string[]",
				defaultValue: "[]",
				description:
					"Search terms to run on YouTube. Each returns up to max_results videos. Max 20.",
			},
			{
				name: "max_results",
				type: "integer",
				defaultValue: "10",
				description:
					"Max items per source and per content type, 1 to 1,000. For a channel, videos, shorts, and streams are capped independently.",
			},
			{
				name: "download_subtitles",
				type: "boolean",
				defaultValue: "false",
				description: "Also fetch each video's subtitle track. Slower.",
			},
			{
				name: "subtitles_language",
				type: "string",
				defaultValue: '"en"',
				description:
					"Subtitle language code, e.g. 'en', 'fr'. Used when download_subtitles is true.",
			},
		],
		responseNote:
			"The response is { items: [...] } with one item per video, short, or stream. One returned item is one billable unit.",
		response: [
			{
				name: "title / id / url",
				type: "string",
				description: "Video title, YouTube ID, and watch URL.",
			},
			{
				name: "type",
				type: "string",
				description: "What this item is: video, short, or stream.",
			},
			{
				name: "viewCount / likes / commentsCount",
				type: "integer",
				description: "Engagement metrics for ranking what resonates.",
			},
			{
				name: "date / duration",
				type: "string",
				description: "Publish date and video length.",
			},
			{
				name: "text / descriptionLinks / hashtags",
				type: "string / object[] / string[]",
				description: "Full description, the links it contains, and its hashtags.",
			},
			{
				name: "subtitles",
				type: "object[]",
				description:
					"Full transcript tracks with SRT content when download_subtitles is true. The raw material for content analysis.",
			},
			{
				name: "thumbnailUrl",
				type: "string",
				description: "The video's thumbnail image.",
			},
			{
				name: "channelName / channelUrl / channelId",
				type: "string",
				description: "The publishing channel's name, URL, and ID.",
			},
			{
				name: "numberOfSubscribers / isChannelVerified",
				type: "integer / boolean",
				description: "Channel reach and verification status.",
			},
			{
				name: "input / fromYTUrl / order",
				type: "string / integer",
				description: "Provenance: which source produced this item and its position.",
			},
		],
	},

	faq: [
		{
			question: "Is scraping YouTube legal?",
			answer:
				"SurfSense reads only public YouTube data, the videos, channels, and comments any visitor can see. It never signs in and cannot access private or unlisted content. Review YouTube's terms and your own compliance needs before running large jobs.",
		},
		{
			question: "Are there quota limits like the YouTube Data API?",
			answer:
				"No daily unit quota. Each scrape call takes up to 20 sources with up to 1,000 results each, and a comments call returns up to 100,000 comments and replies per video. You pay per item returned instead of budgeting Google's 10,000 daily units.",
		},
		{
			question: "Can it download transcripts, and in which languages?",
			answer:
				"Yes. Set download_subtitles to true and pass a language code such as en or fr, and each video comes back with its subtitle track. Transcripts make excellent context for RAG pipelines and research agents that need to reason over video content.",
		},
		{
			question: "Does it support YouTube Shorts?",
			answer:
				"Yes. Channel sources return videos, Shorts, and live streams, each capped independently so one source can return all three types. You can also pass Shorts URLs directly, or use search queries to discover them across the platform.",
		},
	],

	related: [
		{ label: "Reddit API", href: "/reddit" },
		{ label: "Instagram API", href: "/instagram" },
		{ label: "TikTok API", href: "/tiktok" },
		{ label: "Google Maps API", href: "/google-maps" },
		{ label: "SERP API", href: "/google-search" },
		{ label: "Web Crawl API", href: "/web-crawl" },
		{ label: "Indeed API", href: "/indeed" },
		{ label: "SurfSense MCP Server", href: "/mcp-server" },
	],
};
