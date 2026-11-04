/**
 * Reading web pages, YouTube transcripts and web search: built into the app, free and with no
 * licence, from the release that retires the scrapers (ADR 0081). The agent has them as tools and
 * Add from the web uses them; each site they reach follows egress consent. The app's plugin list no
 * longer holds them, so the site keeps what it says about them here. Each keeps the page and the
 * id its plugin had.
 */

export type BuiltInSource = { id: string; name: string; description: string; about: string };

export const BUILT_IN_SOURCES: BuiltInSource[] = [
	{
		id: "google-search",
		name: "Web Search",
		description: "Search the web from SurfSense and read the results.",
		about:
			"Search the web from SurfSense, so answers can draw on what the web says today, not only on your files. Searches go through SearXNG, an open-source metasearch engine: SurfSense’s own instance, unless you set your firm’s. The agent searches as it answers, and Add from the web saves the results worth keeping as sources. Useful for checking current facts, comparing options, or finding the pages worth reading on a topic.",
	},
	{
		id: "web-crawl",
		name: "Web Crawl",
		description: "Read a public web page as clean text.",
		about:
			"Read the web as clean, readable text. SurfSense opens a public page from your own computer, so the agent can summarize it, compare it with others or answer questions from it, and Add from the web can save it to your sources. Useful for summarizing articles, comparing products across sites, or answering questions from a product’s documentation. Pages behind a login or a paywall stay out of reach.",
	},
	{
		id: "youtube",
		name: "YouTube",
		description: "Read a YouTube video through its transcript.",
		about:
			"Work with YouTube videos without watching every one. SurfSense fetches a public video’s transcript over your own connection, so the agent can summarize a talk or tutorial or pull quotes from an interview, and Add from the web can save the video to your sources.",
	},
];
