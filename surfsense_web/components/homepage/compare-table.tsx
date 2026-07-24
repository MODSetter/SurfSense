import { Reveal } from "@/components/connectors-marketing/reveal";
import { MarketingSection } from "@/components/marketing/section";

const COLUMNS = [
	{ label: "Browser agents", examples: "Browserbase, Browser Use" },
	{ label: "Scraping APIs", examples: "Firecrawl" },
	{ label: "Search APIs", examples: "Exa, Tavily, Parallel" },
	{ label: "Scraper marketplaces", examples: "Apify" },
];

const ROWS = [
	{
		feature: "Built for",
		browser: "Web tasks that need clicking, logins, and forms",
		scraping: "Turning individual pages into LLM-ready content",
		search: "Finding and reading pages about a topic",
		marketplace: "Thousands of community-built scrapers, one per site",
		surfsense: "Live platform data as research primitives for agents",
	},
	{
		feature: "How retrieval works",
		browser: "An LLM drives a real browser, page by page",
		scraping: "Fetch a URL, get markdown or schema-extracted JSON",
		search: "Query an index, get ranked results and page content",
		marketplace: "Pick an actor per site, learn its input, run it",
		surfsense: "One typed REST call per platform, no LLM in the retrieval loop",
	},
	{
		feature: "Platform data (comment trees, transcripts, reviews)",
		browser: "Whatever the LLM extracts from rendered pages",
		scraping: "Page-level extraction; social platforms aren't the focus",
		search: "Page text and snippets, not structured platform items",
		marketplace: "Yes, but schema and quality vary per actor",
		surfsense: "Native items: posts, comment trees, transcripts, reviews, SERPs",
	},
	{
		feature: "Consistency",
		browser: "Depends on the model and the page",
		scraping: "One API, you define schemas per page type",
		search: "One API, snippet and page-content shapes",
		marketplace: "A different schema and quality bar per actor",
		surfsense: "One API and one schema style across every connector",
	},
	{
		feature: "Research workspace & knowledge base",
		browser: "No",
		scraping: "No",
		search: "No",
		marketplace: "No",
		surfsense: "Cited briefs, knowledge base, scheduled automations, deliverables",
	},
	{
		feature: "Pricing",
		browser: "Per browser minute (1-minute session minimum) plus the LLM tokens driving it",
		scraping: "Credits per page; schema extraction costs extra credits",
		search: "Per search request",
		marketplace: "Per event or result, set by each actor",
		surfsense: "Per item returned; failed calls never billed",
	},
];

export function CompareTable() {
	return (
		<MarketingSection>
			<Reveal>
				<h2 className="text-2xl font-bold tracking-tight sm:text-3xl">How SurfSense compares</h2>
				<p className="mt-3 max-w-2xl text-muted-foreground leading-relaxed">
					SurfSense is the only open-source product that combines a NotebookLM-style research
					workspace for people with live-data primitives for agents. Here is how that stacks up
					against each class of tool.
				</p>
			</Reveal>
			<Reveal>
				<div className="mt-8 overflow-x-auto rounded-xl border bg-card">
					<table className="w-full min-w-4xl text-sm">
						<thead>
							<tr className="border-b bg-muted/40 text-left">
								<th className="p-4 font-medium">Feature</th>
								{COLUMNS.map((col) => (
									<th key={col.label} className="p-4 font-medium text-muted-foreground">
										{col.label}
										<span className="block text-xs font-normal">{col.examples}</span>
									</th>
								))}
								<th className="p-4 font-medium text-brand">SurfSense</th>
							</tr>
						</thead>
						<tbody>
							{ROWS.map((row) => (
								<tr key={row.feature} className="border-b last:border-b-0">
									<th scope="row" className="p-4 text-left font-medium">
										{row.feature}
									</th>
									<td className="p-4 text-muted-foreground">{row.browser}</td>
									<td className="p-4 text-muted-foreground">{row.scraping}</td>
									<td className="p-4 text-muted-foreground">{row.search}</td>
									<td className="p-4 text-muted-foreground">{row.marketplace}</td>
									<td className="bg-brand/5 p-4 text-foreground">{row.surfsense}</td>
								</tr>
							))}
						</tbody>
					</table>
				</div>
			</Reveal>
		</MarketingSection>
	);
}
