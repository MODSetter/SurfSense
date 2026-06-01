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
		id: "search",
		label: "Search & Summarize",
		prompts: [
			"Summarize the key points across all the documents in this space.",
			"What do my files say about [topic]? Answer with citations.",
			"Find every mention of [keyword] and list the sources.",
			"Give me a cited briefing on the documents I added this week.",
			"Compare these two documents and highlight the differences.",
		],
	},
	{
		id: "create",
		label: "Create",
		prompts: [
			"Write a cited research report on [topic] from my documents.",
			"Turn this folder into a two-host podcast I can listen to.",
			"Create a slide deck and a narrated video overview from these sources.",
			"Generate an image to illustrate [concept] for my report.",
			"Tailor my resume to this job description so it gets past ATS and lands an interview.",
		],
	},
	{
		id: "automate",
		label: "Automate",
		prompts: [
			"Email me a daily brief of new documents in my knowledge base every morning.",
			"When a PDF lands in my Research folder, generate a cited AI summary.",
			"Generate a weekly status report from my Slack and Gmail every Friday.",
			"Build an automation that turns new meeting notes into minutes with action items.",
			"Run a monthly competitor analysis report and save it to my workspace.",
		],
	},
	{
		id: "tools",
		label: "Across your tools",
		prompts: [
			"Search across my Notion, Slack, Google Drive and Gmail for [topic].",
			"Post this research summary to my Notion workspace.",
			"Send these meeting action items to our team Slack channel.",
			"Create a Jira ticket from this bug report.",
			"Open a Linear issue from this feature request.",
		],
	},
];
