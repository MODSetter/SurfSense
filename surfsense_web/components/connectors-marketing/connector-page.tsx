import { IconBrandGithub } from "@tabler/icons-react";
import { ArrowRight, Check } from "lucide-react";
import Link from "next/link";
import { MarketingSection } from "@/components/marketing/section";
import { BreadcrumbNav } from "@/components/seo/breadcrumb-nav";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import type { ConnectorPageContent, SchemaField } from "@/lib/connectors-marketing/types";
import { AgentTranscript } from "./agent-transcript";
import { ApiMcpTabs } from "./api-mcp-tabs";
import { ConnectorFaq } from "./connector-faq";
import { Reveal } from "./reveal";

const GITHUB_URL = "https://github.com/MODSetter/SurfSense";

function SchemaTable({ caption, fields }: { caption: string; fields: SchemaField[] }) {
	return (
		<div className="overflow-x-auto rounded-xl border bg-card">
			<table className="w-full min-w-xl text-sm">
				<caption className="sr-only">{caption}</caption>
				<thead>
					<tr className="border-b bg-muted/40 text-left">
						<th className="p-4 font-medium">Field</th>
						<th className="p-4 font-medium">Type</th>
						<th className="p-4 font-medium">Description</th>
					</tr>
				</thead>
				<tbody>
					{fields.map((field) => (
						<tr key={field.name} className="border-b align-top last:border-b-0">
							<th scope="row" className="p-4 text-left">
								<code className="font-mono text-[13px] font-semibold">{field.name}</code>
							</th>
							<td className="whitespace-nowrap p-4">
								<code className="font-mono text-[13px] text-muted-foreground">{field.type}</code>
								{field.required ? (
									<span className="ml-2 rounded-full bg-brand/10 px-2 py-0.5 text-xs font-medium text-brand">
										required
									</span>
								) : null}
								{field.defaultValue !== undefined ? (
									<div className="mt-1 text-xs text-muted-foreground">
										default <code className="font-mono">{field.defaultValue}</code>
									</div>
								) : null}
							</td>
							<td className="p-4 text-muted-foreground leading-relaxed">{field.description}</td>
						</tr>
					))}
				</tbody>
			</table>
		</div>
	);
}

export function ConnectorPage({ content }: { content: ConnectorPageContent }) {
	const Icon = content.icon;
	const label = content.cardTitle ?? `${content.name} API`;

	return (
		<div className="pb-4">
			{/* Hero */}
			<MarketingSection className="pt-28 pb-12 sm:pt-32 sm:pb-16">
				<div className="grid items-center gap-10 lg:grid-cols-2 lg:gap-14">
					<div>
						<BreadcrumbNav
							className="mb-6"
							items={[
								{ name: "Connectors", href: "/connectors" },
								{ name: content.name, href: `/${content.slug}` },
							]}
						/>
						<Badge variant="outline" className="mb-5 gap-1.5 py-1">
							<Icon className="size-3.5" />
							{content.name} connector
						</Badge>
						<h1 className="text-3xl font-bold tracking-tight text-balance sm:text-4xl lg:text-5xl">
							{content.h1}
						</h1>
						<p className="mt-5 max-w-xl text-base leading-relaxed text-muted-foreground sm:text-lg">
							{content.heroLede}
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
								<Link href={GITHUB_URL} target="_blank" rel="noopener noreferrer">
									<IconBrandGithub className="size-4" />
									GitHub
								</Link>
							</Button>
						</div>
					</div>
					<AgentTranscript transcript={content.transcript} />
				</div>
			</MarketingSection>

			{/* What you can extract */}
			<MarketingSection>
				<Reveal>
					<h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
						What you can extract from {content.name}
					</h2>
					<p className="mt-3 max-w-2xl text-muted-foreground leading-relaxed">
						{content.extractIntro}
					</p>
				</Reveal>
				<Reveal>
					<div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
						{content.extractFields.map((field) => (
							<div
								key={field.label}
								className="rounded-xl border bg-card p-5 transition-colors hover:border-brand/40"
							>
								<h3 className="flex items-center gap-2 font-semibold">
									<Check className="size-4 text-brand" aria-hidden />
									{field.label}
								</h3>
								<p className="mt-2 text-sm leading-relaxed text-muted-foreground">
									{field.description}
								</p>
							</div>
						))}
					</div>
				</Reveal>
			</MarketingSection>

			{/* Use cases */}
			<MarketingSection>
				<Reveal>
					<h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
						{content.useCasesHeading}
					</h2>
				</Reveal>
				<div className="mt-8 grid gap-6 sm:grid-cols-2">
					{content.useCases.map((useCase) => (
						<Reveal key={useCase.title}>
							<div className="h-full rounded-xl border bg-card p-6">
								<h3 className="text-lg font-semibold">{useCase.title}</h3>
								<p className="mt-2 text-sm leading-relaxed text-muted-foreground">
									{useCase.description}
								</p>
							</div>
						</Reveal>
					))}
				</div>
			</MarketingSection>

			{/* API / MCP */}
			<MarketingSection>
				<Reveal>
					<h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
						Call it from your code or your agent
					</h2>
					<p className="mt-3 max-w-2xl text-muted-foreground leading-relaxed">
						One typed endpoint, one API key. Or add the SurfSense MCP server and let your agent call{" "}
						<code className="rounded bg-muted px-1.5 py-0.5 font-mono text-sm">
							{content.api.mcpTool}
						</code>{" "}
						as a native tool.
					</p>
				</Reveal>
				<Reveal>
					{/* Code capped at a readable measure; left edge stays on the page grid. */}
					<div className="mt-8 max-w-4xl">
						<ApiMcpTabs api={content.api} />
					</div>
				</Reveal>
			</MarketingSection>

			{/* Request / response schema */}
			<MarketingSection>
				<Reveal>
					<h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
						{content.name} API request and response schema
					</h2>
					<p className="mt-3 max-w-2xl text-muted-foreground leading-relaxed">
						The exact contract behind{" "}
						<code className="rounded bg-muted px-1.5 py-0.5 font-mono text-sm">
							POST /workspaces/{"{workspace_id}"}/scrapers/{content.api.platform}/{content.api.verb}
						</code>
						. The same fields power the{" "}
						<code className="rounded bg-muted px-1.5 py-0.5 font-mono text-sm">
							{content.api.mcpTool}
						</code>{" "}
						MCP tool.
					</p>
				</Reveal>
				<Reveal>
					<h3 className="mt-8 text-lg font-semibold">Request parameters</h3>
					<p className="mt-2 max-w-2xl text-sm text-muted-foreground leading-relaxed">
						{content.schema.requestNote}
					</p>
					<div className="mt-4">
						<SchemaTable caption="Request parameters" fields={content.schema.request} />
					</div>
				</Reveal>
				<Reveal>
					<h3 className="mt-10 text-lg font-semibold">Response fields</h3>
					<p className="mt-2 max-w-2xl text-sm text-muted-foreground leading-relaxed">
						{content.schema.responseNote}
					</p>
					<div className="mt-4">
						<SchemaTable caption="Response fields" fields={content.schema.response} />
					</div>
				</Reveal>
			</MarketingSection>

			{/* Comparison */}
			<MarketingSection>
				<Reveal>
					<h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
						{content.comparison.heading}
					</h2>
					<p className="mt-3 max-w-2xl text-muted-foreground leading-relaxed">
						{content.comparison.intro}
					</p>
				</Reveal>
				<Reveal>
					<div className="mt-8 overflow-x-auto rounded-xl border bg-card">
						<table className="w-full min-w-xl text-sm">
							<thead>
								<tr className="border-b bg-muted/40 text-left">
									<th className="p-4 font-medium">Feature</th>
									<th className="p-4 font-medium text-muted-foreground">
										{content.comparison.columnLabel}
									</th>
									<th className="p-4 font-medium text-brand">SurfSense</th>
								</tr>
							</thead>
							<tbody>
								{content.comparison.rows.map((row) => (
									<tr key={row.feature} className="border-b last:border-b-0">
										<th scope="row" className="p-4 text-left font-medium">
											{row.feature}
										</th>
										<td className="p-4 text-muted-foreground">{row.official}</td>
										<td className="bg-brand/5 p-4 text-foreground">{row.surfsense}</td>
									</tr>
								))}
							</tbody>
						</table>
					</div>
				</Reveal>
			</MarketingSection>

			{/* FAQ */}
			<MarketingSection>
				<Reveal>
					<h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
						{label}: frequently asked questions
					</h2>
				</Reveal>
				<Reveal>
					{/* Accordion capped at a readable measure; left edge stays on the page grid. */}
					<div className="mt-6 max-w-3xl">
						<ConnectorFaq items={content.faq} />
					</div>
				</Reveal>
			</MarketingSection>

			{/* Closing CTA + related */}
			<MarketingSection>
				<Reveal>
					<div className="rounded-2xl border bg-card p-8 text-center sm:p-12">
						<h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
							Point your agents at {content.name}
						</h2>
						<p className="mx-auto mt-3 max-w-xl text-muted-foreground leading-relaxed">
							The {content.name} connector is one of many in the SurfSense{" "}
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
							{content.related.map((link) => (
								<Button key={link.href} asChild variant="ghost" size="sm">
									<Link href={link.href}>{link.label}</Link>
								</Button>
							))}
						</nav>
					</div>
				</Reveal>
			</MarketingSection>
		</div>
	);
}
