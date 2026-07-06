import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { Reveal } from "@/components/connectors-marketing/reveal";
import { UseCaseArt, type UseCaseArtVariant } from "@/components/homepage/use-case-art";
import { MarketingSection } from "@/components/marketing/section";

/** Buyer language from the high-CPC keyword clusters; each anchors to the connector that fulfills it. */
const USE_CASES: {
	title: string;
	description: string;
	href: string;
	anchor: string;
	art: UseCaseArtVariant;
}[] = [
	{
		title: "Competitor price monitoring",
		description:
			"Crawl competitor pricing and product pages on a schedule and get an alert the day something changes, not the quarter after.",
		href: "/web-crawl",
		anchor: "Web Crawl API",
		art: "price",
	},
	{
		title: "Brand monitoring",
		description:
			"Track every mention of your brand, your competitors, and your category across the communities where buyers speak candidly.",
		href: "/reddit",
		anchor: "Reddit API",
		art: "brand",
	},
	{
		title: "B2B lead generation",
		description:
			"Turn a category and a territory into a clean lead list with phones, websites, and ratings, ready for your CRM.",
		href: "/google-maps",
		anchor: "Google Maps API",
		art: "leads",
	},
	{
		title: "Market research",
		description:
			"Watch the rankings, ads, and AI answers your market actually sees, and mine audience sentiment at scale.",
		href: "/google-search",
		anchor: "SERP API",
		art: "serp",
	},
];

export function UseCasesRow() {
	return (
		<MarketingSection>
			<Reveal>
				<h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
					What teams use SurfSense for
				</h2>
			</Reveal>
			<div className="mt-8 grid gap-6 sm:grid-cols-2">
				{USE_CASES.map((useCase) => (
					<Reveal key={useCase.title}>
						<div className="flex h-full flex-col rounded-xl border bg-card p-6">
							<UseCaseArt variant={useCase.art} />
							<h3 className="text-lg font-semibold">{useCase.title}</h3>
							<p className="mt-2 flex-1 text-sm leading-relaxed text-muted-foreground">
								{useCase.description}
							</p>
							<Link
								href={useCase.href}
								className="group mt-4 inline-flex items-center gap-1 text-sm font-medium text-foreground"
							>
								{useCase.anchor}
								<ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
							</Link>
						</div>
					</Reveal>
				))}
			</div>
		</MarketingSection>
	);
}
