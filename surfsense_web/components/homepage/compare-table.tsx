import { Reveal } from "@/components/connectors-marketing/reveal";
import { MarketingSection } from "@/components/marketing/section";

const ROWS = [
	{
		feature: "Who does the work",
		suites: "Analysts read human dashboards",
		scrapers: "You build everything on raw data",
		surfsense: "Your AI agents gather, analyze, and alert",
	},
	{
		feature: "Intelligence layer",
		suites: "Curated but slow, human-in-the-loop",
		scrapers: "None; data only",
		surfsense: "Agent harness turns live data into briefs",
	},
	{
		feature: "Pricing",
		suites: "Enterprise contracts, annual quotes",
		scrapers: "Usage-priced infrastructure",
		surfsense: "Self-serve, pay per item, free tier",
	},
	{
		feature: "Developer surface",
		suites: "No agent surface",
		scrapers: "APIs, but no MCP or harness",
		surfsense: "REST API with your API key, plus an MCP server for agents",
	},
	{
		feature: "Open source",
		suites: "No",
		scrapers: "No",
		surfsense: "Yes, self-hostable",
	},
];

export function CompareTable() {
	return (
		<MarketingSection>
			<Reveal>
				<h2 className="text-2xl font-bold tracking-tight sm:text-3xl">How SurfSense compares</h2>
				<p className="mt-3 max-w-2xl text-muted-foreground leading-relaxed">
					CI suites sell dashboards to analysts. Scraper APIs sell raw data to engineers. SurfSense
					gives AI agents the data and the harness in one open-source platform.
				</p>
			</Reveal>
			<Reveal>
				<div className="mt-8 overflow-x-auto rounded-xl border bg-card">
					<table className="w-full min-w-2xl text-sm">
						<thead>
							<tr className="border-b bg-muted/40 text-left">
								<th className="p-4 font-medium">Feature</th>
								<th className="p-4 font-medium text-muted-foreground">
									CI suites
									<span className="block text-xs font-normal">Crayon, Klue</span>
								</th>
								<th className="p-4 font-medium text-muted-foreground">
									Scraper APIs
									<span className="block text-xs font-normal">Bright Data, Apify</span>
								</th>
								<th className="p-4 font-medium text-brand">SurfSense</th>
							</tr>
						</thead>
						<tbody>
							{ROWS.map((row) => (
								<tr key={row.feature} className="border-b last:border-b-0">
									<th scope="row" className="p-4 text-left font-medium">
										{row.feature}
									</th>
									<td className="p-4 text-muted-foreground">{row.suites}</td>
									<td className="p-4 text-muted-foreground">{row.scrapers}</td>
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
