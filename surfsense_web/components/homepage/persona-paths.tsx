import { ArrowRight, Code2, Megaphone } from "lucide-react";
import Link from "next/link";
import { Reveal } from "@/components/connectors-marketing/reveal";
import { UseCaseArt, type UseCaseArtVariant } from "@/components/homepage/use-case-art";
import { MarketingSection } from "@/components/marketing/section";

/**
 * Answers "is this for me?" right below the hero: one card per audience.
 * Revenue persona (founders / marketing teams) first, growth persona
 * (developers / agent builders) second.
 */
const PATHS: {
	icon: typeof Megaphone;
	art: UseCaseArtVariant;
	eyebrow: string;
	title: string;
	description: string;
	links: { label: string; href: string }[];
}[] = [
	{
		icon: Megaphone,
		art: "chat",
		eyebrow: "For founders & marketing teams",
		title: "Live web research without the enterprise price tag",
		description:
			"Ask for a research brief, a lead list, or a competitor teardown in plain English. The agent gathers live data, cites its sources, and automations keep watch so you hear about changes first. Start free, pay only for what you use.",
		links: [
			{ label: "See what teams build", href: "/connectors" },
			{ label: "Pricing", href: "/pricing" },
		],
	},
	{
		icon: Code2,
		art: "api",
		eyebrow: "For developers & agents",
		title: "The whole platform is programmable",
		description:
			"Everything SurfSense agents can do is a typed REST API: scrape Reddit, YouTube, TikTok, Amazon, Walmart, Google Maps, Google Search, and the open web, search the knowledge base, run automations. One key, JSON in and out, $5 free credit, pay as you go. Already running agents in Claude, Cursor, or your own harness? The SurfSense MCP server hands them the same tools natively.",
		links: [
			{ label: "Read the docs", href: "/docs" },
			{ label: "SurfSense MCP server", href: "/mcp-server" },
		],
	},
];

export function PersonaPaths() {
	return (
		<MarketingSection>
			<Reveal>
				<h2 className="text-2xl font-bold tracking-tight sm:text-3xl">Who SurfSense is for</h2>
			</Reveal>
			<div className="mt-8 grid gap-6 md:grid-cols-2">
				{PATHS.map((path) => {
					const Icon = path.icon;
					return (
						<Reveal key={path.eyebrow}>
							<div className="flex h-full flex-col rounded-xl border bg-card p-6">
								<UseCaseArt variant={path.art} />
								<div className="flex items-center gap-2 text-sm font-medium text-brand">
									<Icon className="size-4" aria-hidden />
									{path.eyebrow}
								</div>
								<h3 className="mt-3 text-lg font-semibold">{path.title}</h3>
								<p className="mt-2 flex-1 text-sm leading-relaxed text-muted-foreground">
									{path.description}
								</p>
								<div className="mt-4 flex flex-wrap gap-4">
									{path.links.map((link) => (
										<Link
											key={link.href}
											href={link.href}
											className="group inline-flex items-center gap-1 text-sm font-medium text-foreground"
										>
											{link.label}
											<ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
										</Link>
									))}
								</div>
							</div>
						</Reveal>
					);
				})}
			</div>
		</MarketingSection>
	);
}
