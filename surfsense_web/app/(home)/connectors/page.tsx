import { ArrowRight, Plug } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { getAllConnectors } from "@/lib/connectors-marketing";

const canonicalUrl = "https://www.surfsense.com/connectors";

const metaDescription =
	"Platform-native scraper APIs for AI agents. Pull live data from the platforms your market uses through one typed API or the SurfSense MCP server. Explore every connector.";

export const metadata: Metadata = {
	title: "Scraper APIs for AI Agents: All Connectors | SurfSense",
	description: metaDescription,
	keywords: [
		"scraper api",
		"web scraping api",
		"scraper api for ai agents",
		"data connectors",
		"mcp server",
		"competitive intelligence platform",
	],
	alternates: { canonical: canonicalUrl },
	openGraph: {
		title: "Scraper APIs for AI Agents: All Connectors | SurfSense",
		description: metaDescription,
		url: canonicalUrl,
		siteName: "SurfSense",
		type: "website",
		images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "SurfSense connectors" }],
	},
};

export default function ConnectorsIndexPage() {
	const connectors = getAllConnectors();

	return (
		<div className="pt-28 pb-16 sm:pt-32">
			<div className="mx-auto w-full max-w-7xl px-2 md:px-8 xl:px-0">
				<header className="max-w-2xl">
					<h1 className="text-3xl font-bold tracking-tight text-balance sm:text-4xl lg:text-5xl">
						Connectors for every platform your market uses
					</h1>
					<p className="mt-5 text-base leading-relaxed text-muted-foreground sm:text-lg">
						Each connector is a platform-native scraper API your AI agents can call directly, or
						through the SurfSense MCP server. They are the live data behind the SurfSense{" "}
						<Link href="/" className="font-medium text-foreground underline underline-offset-4">
							competitive intelligence platform
						</Link>
						.
					</p>
				</header>

				<div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
					{connectors.map((connector) => {
						const Icon = connector.icon;
						return (
							<Link
								key={connector.slug}
								href={`/${connector.slug}`}
								className="group flex flex-col rounded-xl border bg-card p-6 transition-colors hover:border-brand/40"
							>
								<span className="flex size-11 items-center justify-center rounded-lg border bg-muted/40 transition-transform duration-200 ease-out group-hover:scale-110 motion-reduce:transition-none motion-reduce:group-hover:scale-100">
									<Icon className="size-5 text-foreground" />
								</span>
								<h2 className="mt-4 text-lg font-semibold">
									{connector.cardTitle ?? `${connector.name} API`}
								</h2>
								<p className="mt-2 flex-1 text-sm leading-relaxed text-muted-foreground line-clamp-4">
									{connector.heroLede}
								</p>
								<span className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-foreground">
									Explore
									<ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
								</span>
							</Link>
						);
					})}
					{/* Bespoke page (not in the scrape-API registry): SurfSense as an MCP client. */}
					<Link
						href="/mcp-connector"
						className="group flex flex-col rounded-xl border bg-card p-6 transition-colors hover:border-brand/40"
					>
						<span className="flex size-11 items-center justify-center rounded-lg border bg-muted/40 transition-transform duration-200 ease-out group-hover:scale-110 motion-reduce:transition-none motion-reduce:group-hover:scale-100">
							<Plug className="size-5 text-foreground" />
						</span>
						<h2 className="mt-4 text-lg font-semibold">MCP Connector</h2>
						<p className="mt-2 flex-1 text-sm leading-relaxed text-muted-foreground line-clamp-4">
							Bring any MCP server to your agents. Paste a config like you would in Cursor, tools
							are auto-discovered, and Notion, Slack, Jira, and more connect with one-click OAuth.
						</p>
						<span className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-foreground">
							Explore
							<ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
						</span>
					</Link>
				</div>
			</div>
		</div>
	);
}
