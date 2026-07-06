import { Reveal } from "@/components/connectors-marketing/reveal";
import { FlowLine } from "@/components/homepage/flow-line";
import { MarketingSection } from "@/components/marketing/section";

/** Numbered because the content is genuinely sequential: connect, gather, act. */
const STEPS = [
	{
		number: "01",
		title: "Connect",
		description:
			"Grab one API key and call any connector straight from your own code, or add the SurfSense MCP server to Claude, Cursor, or your own agents. Every connector is a REST endpoint and a native agent tool.",
	},
	{
		number: "02",
		title: "Agents gather",
		description:
			"Your agents pull live data through the agent harness: platform connectors, retries, structured output, and credit metering handled for you.",
	},
	{
		number: "03",
		title: "You act",
		description:
			"Get briefs and alerts instead of raw exports. A rank moves, a price changes, a thread turns on you, and you hear about it first.",
	},
];

export function HowItWorks() {
	return (
		<MarketingSection>
			<Reveal>
				<h2 className="text-2xl font-bold tracking-tight sm:text-3xl">How SurfSense works</h2>
			</Reveal>
			<FlowLine />
			<div className="grid gap-6 md:mt-0 mt-8 md:grid-cols-3">
				{STEPS.map((step, i) => (
					<Reveal key={step.number} delay={i * 0.06}>
						<div className="h-full rounded-xl border bg-card p-6">
							<span className="font-mono text-sm font-medium text-brand">{step.number}</span>
							<h3 className="mt-2 text-lg font-semibold">{step.title}</h3>
							<p className="mt-2 text-sm leading-relaxed text-muted-foreground">
								{step.description}
							</p>
						</div>
					</Reveal>
				))}
			</div>
		</MarketingSection>
	);
}
