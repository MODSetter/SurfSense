import { ConnectorFaq } from "@/components/connectors-marketing/connector-faq";
import { Reveal } from "@/components/connectors-marketing/reveal";
import { MarketingSection } from "@/components/marketing/section";
import { FAQJsonLd } from "@/components/seo/json-ld";

/** Answers are 40-60 words, written as quotable definitions for AI Overviews. */
export const HOME_FAQ = [
	{
		question: "What is competitive intelligence?",
		answer:
			"Competitive intelligence is the practice of gathering and analyzing public information about competitors and your market to make better decisions. It covers pricing, product moves, rankings, reviews, and what customers say online. SurfSense automates it: AI agents collect the live data and turn it into briefs and alerts.",
	},
	{
		question: "What is an MCP server?",
		answer:
			"An MCP server exposes tools and data to AI agents through the Model Context Protocol, an open standard adopted by Claude, Cursor, and most agent frameworks. Add the SurfSense MCP server and your agents can call every connector, such as reddit.scrape or google_search.scrape, as native tools.",
	},
	{
		question: "How is SurfSense different from a web scraping API?",
		answer:
			"A web scraping API returns raw data and leaves the intelligence to you. SurfSense pairs platform-native connectors with an agent harness: retries, structured output, credit metering, and an MCP server, so your agents go from a question to a brief without you building the plumbing in between.",
	},
	{
		question: "Can I use the connector APIs directly in my own app?",
		answer:
			"Yes. Every platform connector is a typed REST endpoint you can call from any language with your SurfSense API key, no agent required. Send a POST request with your query and get structured JSON back. Each connector page has copy-paste examples in cURL, Python, JavaScript, Go, and more.",
	},
	{
		question: "Can I self-host SurfSense?",
		answer:
			"Yes. SurfSense is open source and self-hostable, so you can run the entire platform on your own infrastructure and keep sensitive competitive research in-house. Use the cloud version to start in minutes, or deploy from the GitHub repository when you need full control.",
	},
];

export function HomeFaq() {
	return (
		<MarketingSection>
			<FAQJsonLd questions={HOME_FAQ} />
			<Reveal>
				<h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
					Frequently asked questions
				</h2>
			</Reveal>
			<Reveal>
				{/* Accordion capped at a readable measure; left edge stays on the page grid. */}
				<div className="mt-6 max-w-3xl">
					<ConnectorFaq items={HOME_FAQ} />
				</div>
			</Reveal>
		</MarketingSection>
	);
}
