import { IconBrandGithub } from "@tabler/icons-react";
import { ArrowRight, Check, Plug, ShieldCheck, Wrench } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { ConnectorFaq } from "@/components/connectors-marketing/connector-faq";
import { Reveal } from "@/components/connectors-marketing/reveal";
import { MarketingSection } from "@/components/marketing/section";
import { BreadcrumbNav } from "@/components/seo/breadcrumb-nav";
import { FAQJsonLd, JsonLd } from "@/components/seo/json-ld";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import type { FaqItem } from "@/lib/connectors-marketing/types";

const canonicalUrl = "https://www.surfsense.com/mcp-connector";

const metaDescription =
	"The SurfSense MCP connector lets your AI agents use any MCP server. Paste a config, tools are auto-discovered, and every call runs with per-tool approval. Try it free.";

export const metadata: Metadata = {
	title: "MCP Connector for AI Agents: Add Any MCP Server | SurfSense",
	description: metaDescription,
	keywords: [
		"mcp connector",
		"what is an mcp connector",
		"mcp client",
		"add mcp server",
		"connect mcp server",
		"mcp integrations",
		"mcp server for ai agents",
	],
	alternates: { canonical: canonicalUrl },
	openGraph: {
		title: "MCP Connector for AI Agents: Add Any MCP Server | SurfSense",
		description: metaDescription,
		url: canonicalUrl,
		siteName: "SurfSense",
		type: "website",
		images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "SurfSense MCP connector" }],
	},
	twitter: {
		card: "summary_large_image",
		title: "MCP Connector for AI Agents: Add Any MCP Server | SurfSense",
		description: metaDescription,
		images: ["/og-image.png"],
	},
};

/* Mirrors the real server_config contract (stdio + HTTP transports). */
const STDIO_CONFIG = `{
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-filesystem", "/data"],
  "env": { "LOG_LEVEL": "info" },
  "transport": "stdio"
}`;

const HTTP_CONFIG = `{
  "url": "https://mcp.example.com/mcp",
  "headers": { "Authorization": "Bearer <token>" },
  "transport": "streamable-http"
}`;

const STEPS = [
	{
		icon: Plug,
		title: "Paste a server config",
		description:
			"Add any MCP server the same way you would in Cursor: a local command for stdio servers, or a URL and headers for remote HTTP and SSE servers.",
	},
	{
		icon: Wrench,
		title: "Tools are auto-discovered",
		description:
			"SurfSense tests the connection and pulls the full tool list from the server. No manual tool configuration, no schema files to maintain.",
	},
	{
		icon: ShieldCheck,
		title: "Your agent uses them, safely",
		description:
			"Read-only tools run automatically. Anything that writes asks for your approval first, and you can trust a tool once to always allow it.",
	},
] as const;

/** Hosted MCP apps with one-click OAuth (mirrors the backend MCP service registry). */
const ONE_CLICK_APPS = [
	"Notion",
	"Slack",
	"Jira",
	"Confluence",
	"Linear",
	"ClickUp",
	"Airtable",
] as const;

const FAQ: FaqItem[] = [
	{
		question: "What is an MCP connector?",
		answer:
			"An MCP connector links an AI application to an MCP (Model Context Protocol) server, so the app's agents can call the server's tools. In SurfSense, you add a server config once, its tools are auto-discovered, and every agent in your workspace can use them with per-tool approval.",
	},
	{
		question: "How is an MCP connector different from an MCP server?",
		answer:
			"An MCP server exposes tools; an MCP connector consumes them. This page covers SurfSense acting as the client: plugging outside MCP servers into your agents. SurfSense also ships its own MCP server, which exposes connectors like Reddit and Google Maps as tools inside Claude, Cursor, or any MCP client.",
	},
	{
		question: "Which MCP transports are supported?",
		answer:
			"All the common ones. Local stdio servers run as a process with a command, args, and environment variables. Remote servers connect over streamable HTTP, plain HTTP, or SSE with a URL and optional headers, which covers hosted MCP servers that require an auth token.",
	},
	{
		question: "Is it safe to give an agent MCP tools?",
		answer:
			"Every MCP tool runs through SurfSense's permission layer. Read-only tools are allowed automatically, while any tool that can write or act asks for your approval before it executes. You can mark tools you rely on as trusted so they skip the prompt on later calls.",
	},
	{
		question: "Can I connect Notion or Slack without writing a config?",
		answer:
			"Yes. Notion, Slack, Jira, Confluence, Linear, ClickUp, and Airtable connect through their official hosted MCP servers with one-click OAuth. SurfSense handles the token exchange and curates each app's tool list, so you sign in once and your agents can use them immediately.",
	},
];

function ConfigCard() {
	return (
		<div className="rounded-xl border bg-card p-5 shadow-sm">
			<p className="font-mono text-xs text-muted-foreground">Local server (stdio)</p>
			<pre className="mt-2 overflow-x-auto rounded-lg bg-muted/50 p-4 font-mono text-xs leading-relaxed">
				{STDIO_CONFIG}
			</pre>
			<p className="mt-4 font-mono text-xs text-muted-foreground">Remote server (HTTP / SSE)</p>
			<pre className="mt-2 overflow-x-auto rounded-lg bg-muted/50 p-4 font-mono text-xs leading-relaxed">
				{HTTP_CONFIG}
			</pre>
			<p className="mt-3 flex items-center gap-1.5 text-xs text-muted-foreground">
				<Check className="size-3.5 text-brand" aria-hidden />
				Tools auto-discovered on connect
			</p>
		</div>
	);
}

export default function McpConnectorPage() {
	return (
		<>
			<JsonLd
				data={{
					"@context": "https://schema.org",
					"@type": "SoftwareApplication",
					name: "SurfSense MCP Connector",
					applicationCategory: "DeveloperApplication",
					operatingSystem: "Web",
					description: metaDescription,
					url: canonicalUrl,
					offers: {
						"@type": "Offer",
						price: "0",
						priceCurrency: "USD",
						description: "Free tier included",
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
									{ name: "MCP Connector", href: "/mcp-connector" },
								]}
							/>
							<Badge variant="outline" className="mb-5 gap-1.5 py-1">
								<Plug className="size-3.5" />
								MCP connector
							</Badge>
							<h1 className="text-3xl font-bold tracking-tight text-balance sm:text-4xl lg:text-5xl">
								Bring any MCP server to your AI agents
							</h1>
							<p className="mt-5 max-w-xl text-base leading-relaxed text-muted-foreground sm:text-lg">
								The SurfSense MCP connector turns your workspace into an MCP client. Add any MCP
								server with the same config you'd use in Cursor, and its tools are auto-discovered
								and handed to your agents, guarded by per-tool approval. Notion, Slack, Jira, and
								more connect with one-click OAuth.
							</p>
							<div className="mt-8 flex flex-wrap items-center gap-3">
								<Button asChild size="lg">
									<Link href="/register">
										Start for free
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
							From config to agent tool in three steps
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

				{/* One-click apps */}
				<MarketingSection>
					<Reveal>
						<h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
							Your work apps, no config required
						</h2>
						<p className="mt-3 max-w-2xl text-muted-foreground leading-relaxed">
							These apps run on their official hosted MCP servers. Sign in once with OAuth and
							SurfSense manages the tokens and curates each tool list, so your agents can search
							Notion, read Slack threads, or file Jira issues alongside your market intelligence.
						</p>
					</Reveal>
					<Reveal>
						<div className="mt-8 flex flex-wrap gap-2">
							{ONE_CLICK_APPS.map((app) => (
								<span
									key={app}
									className="inline-flex items-center gap-1.5 rounded-full border bg-card px-4 py-2 text-sm font-medium"
								>
									<Check className="size-3.5 text-brand" aria-hidden />
									{app}
								</span>
							))}
						</div>
					</Reveal>
				</MarketingSection>

				{/* Connector vs server */}
				<MarketingSection>
					<Reveal>
						<h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
							MCP connector vs MCP server
						</h2>
						<p className="mt-3 max-w-2xl text-muted-foreground leading-relaxed">
							They are two sides of the same protocol. The MCP connector on this page makes
							SurfSense a <em>client</em>: it consumes tools from outside MCP servers. The SurfSense
							MCP <em>server</em> does the reverse, exposing platform connectors like{" "}
							<Link
								href="/reddit"
								className="font-medium text-foreground underline underline-offset-4"
							>
								Reddit
							</Link>{" "}
							and{" "}
							<Link
								href="/google-maps"
								className="font-medium text-foreground underline underline-offset-4"
							>
								Google Maps
							</Link>{" "}
							as native tools inside Claude, Cursor, or any agent you already run. Use both and data
							flows in either direction.
						</p>
					</Reveal>
				</MarketingSection>

				{/* FAQ */}
				<MarketingSection>
					<Reveal>
						<h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
							MCP connector: frequently asked questions
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
								Give your agents every tool they need
							</h2>
							<p className="mx-auto mt-3 max-w-xl text-muted-foreground leading-relaxed">
								The MCP connector is part of the SurfSense{" "}
								<Link href="/" className="font-medium text-foreground underline underline-offset-4">
									competitive intelligence platform
								</Link>
								. Start free, no credit card required.
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
									<Link href="/reddit">Reddit API</Link>
								</Button>
								<Button asChild variant="ghost" size="sm">
									<Link href="/youtube">YouTube API</Link>
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
