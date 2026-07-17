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
		id: "research",
		label: "Research the Web",
		prompts: [
			"Research [topic] across the live web and give me a cited brief",
			"Map who ranks for [keyword], crawl each result, and compare their claims in one table",
			"Pull the Google Maps reviews for [business] and summarize the top complaints",
			"Which queries about [topic] trigger an AI Overview, and who gets cited?",
		],
	},
	{
		id: "listen",
		label: "Community Listening",
		prompts: [
			"Find 20 Reddit posts where people ask for an alternative to [product]",
			"Analyze the comments on [channel]'s last 10 videos and cluster the complaints",
			"What is Reddit saying about [topic] this week?",
			"Pull the top TikTok videos for [hashtag] and summarize the trend",
		],
	},
	{
		id: "monitor",
		label: "Monitor Competitors",
		prompts: [
			"Extract every plan, price, and limit from [competitor]'s pricing page",
			"Crawl [competitor]'s changelog and brief me on what they shipped this month",
			"Measure the reaction to [competitor]'s launch across search, Reddit, and YouTube",
			"Find the top-rated [category] businesses in [city], crawl their sites, and build a lead list with contacts",
		],
	},
	{
		id: "automate",
		label: "Automate",
		prompts: [
			"Watch [url] daily and alert me on any change",
			"Track our brand mentions on Reddit daily and tag buying intent",
			"Send me a weekly report on [keyword] rankings and AI Overview citations",
			"Every Monday, crawl [site]'s changelog and send me a brief",
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
