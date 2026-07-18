import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { Reveal } from "@/components/connectors-marketing/reveal";
import { MarketingSection } from "@/components/marketing/section";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getAllConnectors } from "@/lib/connectors-marketing";

/** Registry-driven connector grid with a live count badge (brief: never list connectors in copy). */
export function ConnectorGrid() {
	const connectors = getAllConnectors();

	return (
		<MarketingSection>
			<Reveal>
				<div className="flex flex-wrap items-center gap-3">
					<h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
						Connectors for every platform where answers live
					</h2>
					<Badge variant="outline" className="py-1">
						{connectors.length} connectors and growing
					</Badge>
				</div>
				<p className="mt-3 max-w-2xl text-muted-foreground leading-relaxed">
					Each connector is a platform-native REST API. Call it from your own app with your
					SurfSense API key, or hand it to your agents through the SurfSense MCP server. Live data
					in, structured intelligence out.
				</p>
			</Reveal>
			<Reveal>
				<div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
					{connectors.map((connector) => {
						const Icon = connector.icon;
						return (
							<Link
								key={connector.slug}
								href={`/${connector.slug}`}
								className="group flex flex-col rounded-xl border bg-card p-5 transition-colors hover:border-brand/40"
							>
								<span className="flex size-10 items-center justify-center rounded-lg border bg-muted/40 transition-transform duration-200 ease-out group-hover:scale-110 motion-reduce:transition-none motion-reduce:group-hover:scale-100">
									<Icon className="size-5 text-foreground" />
								</span>
								<h3 className="mt-3 font-semibold">
									{connector.cardTitle ?? `${connector.name} API`}
								</h3>
								<p className="mt-1.5 flex-1 text-sm leading-relaxed text-muted-foreground line-clamp-2">
									{connector.heroLede}
								</p>
								<span className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-foreground">
									Explore
									<ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
								</span>
							</Link>
						);
					})}
				</div>
				<div className="mt-6">
					<Button asChild variant="outline">
						<Link href="/connectors">
							View all connectors
							<ArrowRight className="size-4" />
						</Link>
					</Button>
				</div>
			</Reveal>
		</MarketingSection>
	);
}
