import { IconBrandGithub } from "@tabler/icons-react";
import { ArrowRight, Check, Database, KeyRound, Server, TerminalSquare } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { ConnectorFaq } from "@/components/connectors-marketing/connector-faq";
import { Reveal } from "@/components/connectors-marketing/reveal";
import { MarketingSection } from "@/components/marketing/section";
import { AgentSetupTabs } from "@/components/mcp/agent-setup-tabs";
import { BreadcrumbNav } from "@/components/seo/breadcrumb-nav";
import { FAQJsonLd, JsonLd } from "@/components/seo/json-ld";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import type { FaqItem } from "@/lib/connectors-marketing/types";

const canonicalUrl = "https://www.surfsense.com/mcp-server";

const metaDescription =
	"The SurfSense MCP server gives Claude, Cursor, and any MCP client native tools for your workspace: scrape Reddit, YouTube, Instagram, TikTok, Amazon, Walmart, Google Maps, Google Search, and the web, plus full knowledge base access. One API key.";

export const metadata: Metadata = {
	title: "SurfSense MCP Server: Scraper APIs and Knowledge Base as Agent Tools",
	description: metaDescription,
	keywords: [
		"surfsense mcp server",
		"mcp server",
		"mcp server for web scraping",
		"reddit mcp server",
		"youtube mcp server",
		"google maps mcp server",
		"serp mcp server",
		"mcp server for claude",
		"mcp server for cursor",
		"knowledge base mcp server",
	],
	alternates: { canonical: canonicalUrl },
	openGraph: {
		title: "SurfSense MCP Server: Scraper APIs and Knowledge Base as Agent Tools",
		description: metaDescription,
		url: canonicalUrl,
		siteName: "SurfSense",
		type: "website",
		images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "SurfSense MCP server" }],
	},
	twitter: {
		card: "summary_large_image",
		title: "SurfSense MCP Server: Scraper APIs and Knowledge Base as Agent Tools",
		description: metaDescription,
		images: ["/og-image.png"],
	},
};

/* The hosted Cursor config; mirrors lib/mcp/clients.ts. */
const CURSOR_CONFIG = `{
  "mcpServers": {
    "surfsense": {
      "url": "https://mcp.surfsense.com/mcp",
      "headers": {
        "Authorization": "Bearer ss_pat_..."
      }
    }
  }
}`;

const STEPS = [
	{
		icon: KeyRound,
		title: "Create an API key",
		description:
			"In SurfSense, go to Settings, then API, and create a key. Enable API access on the workspaces you want your agents to reach. That key is all the server needs.",
	},
	{
		icon: TerminalSquare,
		title: "Add the server to your client",
		description:
			"Point your client at https://mcp.surfsense.com/mcp with your key in an Authorization header — the hosted config for Cursor, Claude Code, and others is one paste. Prefer stdio? Switch to Self-host and run it against your own backend.",
	},
	{
		icon: Server,
		title: "Your agent has the tools",
		description:
			"Every scraper and knowledge base operation shows up as a native, typed MCP tool. Your agent picks a workspace once and the server carries the context between calls.",
	},
] as const;

/** Mirrors the tool registry in surfsense_mcp (see its README). */
const TOOL_GROUPS = [
	{
		icon: Server,
		title: "Live scrapers",
		description: "Structured, current platform data. One returned item is one billable unit.",
		tools: [
			"surfsense_reddit_scrape",
			"surfsense_youtube_scrape",
			"surfsense_youtube_comments",
			"surfsense_instagram_scrape",
			"surfsense_instagram_details",
			"surfsense_tiktok_scrape",
			"surfsense_tiktok_comments",
			"surfsense_tiktok_user_search",
			"surfsense_tiktok_trending",
			"surfsense_google_maps_scrape",
			"surfsense_google_maps_reviews",
			"surfsense_google_search",
			"surfsense_amazon_scrape",
			"surfsense_walmart_scrape",
			"surfsense_walmart_reviews",
			"surfsense_web_crawl",
			"surfsense_list_scraper_runs",
			"surfsense_get_scraper_run",
		],
	},
	{
		icon: Database,
		title: "Knowledge base",
		description: "Read and write the same knowledge base your SurfSense agents use.",
		tools: [
			"surfsense_search_knowledge_base",
			"surfsense_list_documents",
			"surfsense_get_document",
			"surfsense_add_document",
			"surfsense_upload_file",
			"surfsense_update_document",
			"surfsense_delete_document",
		],
	},
	{
		icon: KeyRound,
		title: "Workspace selector",
		description: "Pick a workspace once; every later call defaults to it.",
		tools: ["surfsense_list_workspaces", "surfsense_select_workspace"],
	},
] as const;

const FAQ: FaqItem[] = [
	{
		question: "What is the SurfSense MCP server?",
		answer:
			"It is a Model Context Protocol server that exposes your SurfSense workspace to MCP clients like Claude Code, Cursor, and Claude Desktop. Your agents get native tools for every scraper API (Reddit, YouTube, Instagram, TikTok, Amazon, Walmart, Google Maps, Google Search, web crawl) and for searching, reading, and writing your knowledge base.",
	},
	{
		question: "Which MCP clients does it work with?",
		answer:
			"Any MCP client that speaks remote (streamable HTTP) or stdio. Claude Code, Codex, OpenCode, Cursor, Claude Desktop, VS Code, Windsurf, and Gemini CLI all have copy-paste configs on this page — Hosted for the one-paste https://mcp.surfsense.com/mcp endpoint, or Self-host for stdio against your own backend.",
	},
	{
		question: "How is usage billed?",
		answer:
			"Exactly like the REST API, because the server is a thin layer over it. Scraper tools consume the same pay-as-you-go credits, priced per returned item, and knowledge base operations work within your plan. New accounts start with $5 of free credit.",
	},
	{
		question: "Does it work with a self-hosted SurfSense?",
		answer:
			"Yes. The server talks to SurfSense purely over its REST API and imports no backend code, so pointing SURFSENSE_BASE_URL at your own instance is all it takes. It works with the cloud at api.surfsense.com the same way.",
	},
	{
		question: "How does the agent know which workspace to use?",
		answer:
			"The server ships a workspace selector: the agent lists the workspaces your API key can access, selects one by name, and every later call defaults to it. Any tool also accepts a workspace override for a single call, and ids never need to be typed by hand.",
	},
];

function ConfigCard() {
	return (
		<div className="rounded-xl border bg-card p-5 shadow-sm">
			<p className="font-mono text-xs text-muted-foreground">.cursor/mcp.json</p>
			<pre className="mt-2 overflow-x-auto rounded-lg bg-muted/50 p-4 font-mono text-xs leading-relaxed">
				{CURSOR_CONFIG}
			</pre>
			<p className="mt-3 flex items-center gap-1.5 text-xs text-muted-foreground">
				<Check className="size-3.5 text-brand" aria-hidden />
				Works with Claude Code, Cursor, Claude Desktop, and any MCP client
			</p>
		</div>
	);
}

export default function McpServerPage() {
	return (
		<>
			<JsonLd
				data={{
					"@context": "https://schema.org",
					"@type": "SoftwareApplication",
					name: "SurfSense MCP Server",
					applicationCategory: "DeveloperApplication",
					operatingSystem: "Web",
					description: metaDescription,
					url: canonicalUrl,
					offers: {
						"@type": "Offer",
						price: "0",
						priceCurrency: "USD",
						description: "$5 free credit included, pay as you go",
					},
					provider: {
						"@type": "Organization",
						name: "SurfSense",
						url: "https://www.surfsense.com",
					},
					isPartOf: { "@type": "WebSite", name: "SurfSense", url: "https://www.surfsense.com" },
				}}
			/>
			<FAQJsonLd questions={FAQ} />

			<div className="pb-4">
				{/* Hero */}
				<MarketingSection className="pt-28 pb-12 sm:pt-32 sm:pb-16">
					<div className="grid items-center gap-10 lg:grid-cols-2 lg:gap-14">
						<div>
							<BreadcrumbNav
								className="mb-6"
								items={[
									{ name: "Connectors", href: "/connectors" },
									{ name: "SurfSense MCP Server", href: "/mcp-server" },
								]}
							/>
							<Badge variant="outline" className="mb-5 gap-1.5 py-1">
								<Server className="size-3.5" />
								SurfSense MCP server
							</Badge>
							<h1 className="text-3xl font-bold tracking-tight text-balance sm:text-4xl lg:text-5xl">
								Give your agents SurfSense as native tools
							</h1>
							<p className="mt-5 max-w-xl text-base leading-relaxed text-muted-foreground sm:text-lg">
								The SurfSense MCP server hands Claude, Cursor, or any MCP client the whole platform:
								scrape Reddit, YouTube, Instagram, TikTok, Amazon, Walmart, Google Maps, Google
								Search, and the open web, and search, read, and write your knowledge base. One API
								key, typed tools, pay as you go.
							</p>
							<div className="mt-8 flex flex-wrap items-center gap-3">
								<Button asChild size="lg">
									<Link href="/register">
										Get your API key
										<ArrowRight className="size-4" />
									</Link>
								</Button>
								<Button asChild variant="outline" size="lg">
									<Link href="/docs">Read the docs</Link>
								</Button>
								<Button asChild variant="ghost" size="lg">
									<Link
										href="https://github.com/MODSetter/SurfSense"
										target="_blank"
										rel="noopener noreferrer"
									>
										<IconBrandGithub className="size-4" />
										GitHub
									</Link>
								</Button>
							</div>
						</div>
						<ConfigCard />
					</div>
				</MarketingSection>

				{/* How it works */}
				<MarketingSection>
					<Reveal>
						<h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
							From API key to agent tools in three steps
						</h2>
					</Reveal>
					<div className="mt-8 grid gap-4 sm:grid-cols-3">
						{STEPS.map((step) => (
							<Reveal key={step.title}>
								<div className="h-full rounded-xl border bg-card p-6 transition-colors hover:border-brand/40">
									<span className="flex size-10 items-center justify-center rounded-lg border bg-muted/40">
										<step.icon className="size-5 text-foreground" aria-hidden />
									</span>
									<h3 className="mt-4 font-semibold">{step.title}</h3>
									<p className="mt-2 text-sm leading-relaxed text-muted-foreground">
										{step.description}
									</p>
								</div>
							</Reveal>
						))}
					</div>
				</MarketingSection>

				{/* Per-agent setup */}
				<MarketingSection>
					<Reveal>
						<h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
							Step-by-step setup for every agent
						</h2>
						<p className="mt-3 max-w-2xl text-muted-foreground leading-relaxed">
							Pick your client, choose <strong>Hosted</strong> or <strong>Self-host</strong>, and
							paste the config. Replace the key with one from API Playground → API Keys — or grab a
							pre-filled config from the playground itself.
						</p>
					</Reveal>
					<Reveal>
						<div className="mt-8 rounded-xl border bg-card p-5 shadow-sm sm:p-6">
							<AgentSetupTabs />
						</div>
					</Reveal>
				</MarketingSection>

				{/* Tools */}
				<MarketingSection>
					<Reveal>
						<h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
							Every tool the server exposes
						</h2>
						<p className="mt-3 max-w-2xl text-muted-foreground leading-relaxed">
							The server is a thin layer over the SurfSense REST API: the same endpoints, the same
							billing, no backend code imported. Whatever ships in the API shows up here.
						</p>
					</Reveal>
					<div className="mt-8 grid gap-4 lg:grid-cols-3">
						{TOOL_GROUPS.map((group) => (
							<Reveal key={group.title}>
								<div className="h-full rounded-xl border bg-card p-6">
									<span className="flex size-10 items-center justify-center rounded-lg border bg-muted/40">
										<group.icon className="size-5 text-foreground" aria-hidden />
									</span>
									<h3 className="mt-4 font-semibold">{group.title}</h3>
									<p className="mt-2 text-sm leading-relaxed text-muted-foreground">
										{group.description}
									</p>
									<ul className="mt-4 space-y-1.5">
										{group.tools.map((tool) => (
											<li key={tool} className="truncate font-mono text-xs text-muted-foreground">
												{tool}
											</li>
										))}
									</ul>
								</div>
							</Reveal>
						))}
					</div>
				</MarketingSection>

				{/* Server vs external connectors */}
				<MarketingSection>
					<Reveal>
						<h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
							The SurfSense MCP server vs external MCP connectors
						</h2>
						<p className="mt-3 max-w-2xl text-muted-foreground leading-relaxed">
							They are two sides of the same protocol. The MCP <em>server</em> on this page pushes
							SurfSense tools out to agents you already run in Claude, Cursor, or your own harness.{" "}
							<Link
								href="/external-mcp-connectors"
								className="font-medium text-foreground underline underline-offset-4"
							>
								External MCP connectors
							</Link>{" "}
							do the reverse: they pull outside tools like Notion, Slack, and Jira into your
							SurfSense agents. Use both and data flows in either direction.
						</p>
					</Reveal>
				</MarketingSection>

				{/* FAQ */}
				<MarketingSection>
					<Reveal>
						<h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
							SurfSense MCP server: frequently asked questions
						</h2>
					</Reveal>
					<Reveal>
						<div className="mt-6 max-w-3xl">
							<ConnectorFaq items={FAQ} />
						</div>
					</Reveal>
				</MarketingSection>

				{/* Closing CTA + related */}
				<MarketingSection>
					<Reveal>
						<div className="rounded-2xl border bg-card p-8 text-center sm:p-12">
							<h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
								Put live web data inside your agents
							</h2>
							<p className="mx-auto mt-3 max-w-xl text-muted-foreground leading-relaxed">
								The MCP server is part of the SurfSense{" "}
								<Link href="/" className="font-medium text-foreground underline underline-offset-4">
									open web research platform
								</Link>
								. Start with $5 of free credit, no credit card required.
							</p>
							<div className="mt-7 flex flex-wrap justify-center gap-3">
								<Button asChild size="lg">
									<Link href="/register">
										Start for free
										<ArrowRight className="size-4" />
									</Link>
								</Button>
								<Button asChild variant="outline" size="lg">
									<Link href="/pricing">See pricing</Link>
								</Button>
							</div>

							<Separator className="my-8" />

							<nav aria-label="Other connectors" className="flex flex-wrap justify-center gap-2">
								<Button asChild variant="ghost" size="sm">
									<Link href="/connectors">All connectors</Link>
								</Button>
								<Button asChild variant="ghost" size="sm">
									<Link href="/external-mcp-connectors">External MCP Connectors</Link>
								</Button>
								<Button asChild variant="ghost" size="sm">
									<Link href="/reddit">Reddit API</Link>
								</Button>
								<Button asChild variant="ghost" size="sm">
									<Link href="/youtube">YouTube API</Link>
								</Button>
								<Button asChild variant="ghost" size="sm">
									<Link href="/instagram">Instagram API</Link>
								</Button>
								<Button asChild variant="ghost" size="sm">
									<Link href="/tiktok">TikTok API</Link>
								</Button>
								<Button asChild variant="ghost" size="sm">
									<Link href="/google-maps">Google Maps API</Link>
								</Button>
								<Button asChild variant="ghost" size="sm">
									<Link href="/google-search">SERP API</Link>
								</Button>
								<Button asChild variant="ghost" size="sm">
									<Link href="/web-crawl">Web Crawl API</Link>
								</Button>
							</nav>
						</div>
					</Reveal>
				</MarketingSection>
			</div>
		</>
	);
}
