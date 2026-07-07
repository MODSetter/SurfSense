/**
 * Curated example chat prompts shown on the empty new-chat screen.
 *
 * These mirror the homepage hero's "use case" concept but with runnable chat
 * queries, grouped into a few broad categories. Bracketed slots like `[topic]`
 * are intentional: clicking a prompt prefills the composer so the user can fill
 * them in before sending.
 *
 * This is a module-scope constant so it is created once, not per render.
 */

export interface ChatExampleCategory {
	/** Stable id used as the Tabs value */
	id: string;
	/** Short, human-readable tab label */
	label: string;
	/** Runnable example queries for this category */
	prompts: string[];
}

export const CHAT_EXAMPLE_CATEGORIES: ChatExampleCategory[] = [
	{
		id: "monitor",
		label: "Monitor Competitors",
		prompts: [
			"Extract every plan, price, and limit from [competitor]'s pricing page",
			"Crawl [competitor]'s changelog and brief me on what they shipped this month",
			"Track who ranks and runs ads for [keyword] in the US",
			"Which of our target keywords trigger an AI Overview, and who gets cited?",
		],
	},
	{
		id: "listen",
		label: "Market Listening",
		prompts: [
			"Find 20 Reddit posts where people ask for an alternative to [product]",
			"Analyze the comments on [channel]'s last 10 videos and cluster the complaints",
			"Pull the Google Maps reviews for [business] and summarize the top complaints",
			"Find people actively looking to switch away from [competitor] this month",
		],
	},
	{
		id: "workflows",
		label: "Multi-Connector",
		prompts: [
			"Measure the reaction to [competitor]'s launch across search, Reddit, and YouTube",
			"Find the top-rated [category] businesses in [city], crawl their sites, and build a lead list with contacts",
			"Map who ranks for [keyword], crawl each result, and compare their pricing in one table",
			"Build a 360 on [competitor]: site changes, rank movements, Reddit sentiment, and YouTube reaction",
		],
	},
	{
		id: "automate",
		label: "Automate",
		prompts: [
			"Re-check [competitor]'s pricing page daily and alert me on any change",
			"Every Monday, crawl our competitors' changelogs and send me a brief",
			"Track our brand mentions on Reddit daily and tag buying intent",
			"Send me a weekly report on [keyword] rankings and AI Overview citations",
		],
	},
	{
		id: "tools",
		label: "Across your tools",
		prompts: [
			"Search across my Notion, Slack, Google Drive and Gmail for [topic]",
			"Post this research summary to my Notion workspace",
			"Send these findings to our team Slack channel",
			"Create a Jira ticket from this bug report",
		],
	},
];
