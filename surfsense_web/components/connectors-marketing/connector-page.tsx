import { IconBrandGithub } from "@tabler/icons-react";
import Link from "next/link";
import { HomeButton } from "@/components/homepage/home/home-button";
import { BreadcrumbNav } from "@/components/seo/breadcrumb-nav";
import { SiteFaqItem } from "@/components/site/site-faq-item";
import { siteText } from "@/components/site/site-text";
import { CheckIcon } from "@/components/ui/icons";
import type { ConnectorPageContent, SchemaField } from "@/lib/connectors-marketing/types";
import { cn } from "@/lib/utils";
import { AgentTranscript } from "./agent-transcript";
import { ApiMcpTabs } from "./api-mcp-tabs";

const GITHUB_URL = "https://github.com/MODSetter/SurfSense";

/**
 * The connector marketing pages (`/reddit`, `/amazon`, ...).
 *
 * Tailwind plus the shared `siteText` styles, with the same hero, ruled bands and
 * cell grids as the rest of the site, so all fourteen pages read as one site.
 * Rendered in the site design via `SITE_DESIGN_ROUTES` in
 * `components/site/site-shell.tsx`.
 *
 * A server component with no client JavaScript, except `ApiMcpTabs`: switching
 * the code sample's language is a real piece of interactive state, unlike the
 * scroll-triggered reveals the previous version of this page used everywhere.
 */

function SchemaTable({ caption, fields }: { caption: string; fields: SchemaField[] }) {
	return (
		<section
			className="overflow-x-auto focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring"
			aria-label={caption}
			/* biome-ignore lint/a11y/noNoninteractiveTabindex: a region that scrolls horizontally has to be focusable, or a keyboard-only visitor cannot reach the columns past the fold. The labelled landmark is what makes the focus stop meaningful. */
			tabIndex={0}
		>
			<table className="ss-home-table">
				<caption className="sr-only">{caption}</caption>
				<thead>
					<tr>
						<th scope="col">Field</th>
						<th scope="col">Type</th>
						<th scope="col">Description</th>
					</tr>
				</thead>
				<tbody>
					{fields.map((field) => (
						<tr key={field.name}>
							<th scope="row">
								<code className="font-mono text-[13px] font-semibold">{field.name}</code>
							</th>
							<td className="whitespace-nowrap">
								<code className="font-mono text-[13px] text-muted-foreground">{field.type}</code>
								{field.required ? (
									<span
										className="ml-2 inline-flex items-center rounded-full border border-border px-2 py-px text-[10px] font-semibold tracking-wide whitespace-nowrap text-muted-foreground uppercase data-[tone=accent]:border-primary/40 data-[tone=accent]:text-primary"
										data-tone="accent"
									>
										required
									</span>
								) : null}
								{field.defaultValue !== undefined ? (
									<div className="mt-1 text-xs text-muted-foreground">
										default <code className="font-mono">{field.defaultValue}</code>
									</div>
								) : null}
							</td>
							<td className="text-muted-foreground leading-relaxed">{field.description}</td>
						</tr>
					))}
				</tbody>
			</table>
		</section>
	);
}

export function ConnectorPage({ content }: { content: ConnectorPageContent }) {
	const label = content.cardTitle ?? `${content.name} API`;
	const useCasesWide = content.useCases.length % 2 !== 0;

	return (
		<>
			{/* Hero */}
			<section className="py-20 md:py-28">
				<div className="grid items-center gap-12 lg:grid-cols-2 lg:gap-16">
					<div>
						<BreadcrumbNav
							className="flex flex-wrap items-center gap-1.5 text-sm text-muted-foreground"
							items={[
								{ name: "Plugins", href: "/plugins" },
								{ name: content.name, href: `/${content.slug}` },
							]}
						/>
						<h1 className={cn(siteText.display, "mt-6")}>{content.h1}</h1>
						<p className={cn(siteText.lede, "mt-6 max-w-xl")}>{content.heroLede}</p>
						<div className="mt-8">
							<HomeButton asChild size="xl">
								<Link href="/register">Start for free</Link>
							</HomeButton>
						</div>
						<p className={cn(siteText.body, "mt-5 text-sm")}>
							Prefer to look at the code first?{" "}
							<Link className={siteText.link} href="/docs">
								Read the docs
							</Link>
							.
						</p>
					</div>
					<AgentTranscript transcript={content.transcript} />
				</div>
			</section>

			{/* What you can extract */}
			<section className="border-t border-border">
				<div className="border-b border-border pt-10 pb-8 md:pt-40">
					<h2 className={siteText.h2}>What you can extract from {content.name}</h2>
					<p className={cn(siteText.body, "mt-3 max-w-2xl")}>{content.extractIntro}</p>
				</div>
				<div className="ss-home-grid sm:grid-cols-2 md:grid-cols-3">
					{content.extractFields.map((field) => (
						<div key={field.label} className="px-6 py-8 md:px-10">
							<p className={cn(siteText.h3, "flex items-center gap-2")}>
								<CheckIcon aria-hidden="true" className="size-4 shrink-0 text-primary" />
								{field.label}
							</p>
							<p className={cn(siteText.body, "mt-2 text-sm")}>{field.description}</p>
						</div>
					))}
				</div>
			</section>

			{/* Use cases */}
			<section className="border-t border-border">
				<div className="border-b border-border pt-10 pb-8 md:pt-40">
					<h2 className={siteText.h2}>{content.useCasesHeading}</h2>
				</div>
				<div className="ss-home-grid sm:grid-cols-2">
					{content.useCases.map((useCase, index) => (
						<div
							key={useCase.title}
							className={cn(
								"px-6 py-8 md:px-10",
								useCasesWide && index === content.useCases.length - 1 && "col-span-full"
							)}
						>
							<p className={siteText.h3}>{useCase.title}</p>
							<p className={cn(siteText.body, "mt-2 text-sm")}>{useCase.description}</p>
						</div>
					))}
				</div>
			</section>

			{/* API / MCP */}
			<section className="border-t border-border py-16">
				<h2 className={cn(siteText.h2, "max-w-2xl")}>Call it from your code or your agent</h2>
				<p className={cn(siteText.body, "mt-3 max-w-2xl")}>
					One typed endpoint, one API key. Or add the SurfSense MCP server and let your agent call{" "}
					<code className="font-mono rounded-none border border-border bg-muted px-1.5 py-0.5 text-sm">
						{content.api.mcpTool}
					</code>{" "}
					as a native tool.
				</p>
				<div className="mt-8 max-w-3xl">
					<ApiMcpTabs api={content.api} />
				</div>
			</section>

			{/* Request / response schema */}
			<section className="border-t border-border py-16">
				<h2 className={cn(siteText.h2, "max-w-2xl")}>
					{content.name} API request and response schema
				</h2>
				<p className={cn(siteText.body, "mt-3 max-w-2xl")}>
					The exact contract behind{" "}
					<code className="font-mono rounded-none border border-border bg-muted px-1.5 py-0.5 text-sm">
						POST /workspaces/{"{workspace_id}"}/scrapers/{content.api.platform}/{content.api.verb}
					</code>
					. The same fields power the{" "}
					<code className="font-mono rounded-none border border-border bg-muted px-1.5 py-0.5 text-sm">
						{content.api.mcpTool}
					</code>{" "}
					MCP tool.
				</p>

				<h3 className={cn(siteText.h3, "mt-10")}>Request parameters</h3>
				<p className={cn(siteText.body, "mt-2 max-w-2xl text-sm")}>{content.schema.requestNote}</p>
				<div className="mt-4">
					<SchemaTable caption="Request parameters" fields={content.schema.request} />
				</div>

				<h3 className={cn(siteText.h3, "mt-10")}>Response fields</h3>
				<p className={cn(siteText.body, "mt-2 max-w-2xl text-sm")}>{content.schema.responseNote}</p>
				<div className="mt-4">
					<SchemaTable caption="Response fields" fields={content.schema.response} />
				</div>
			</section>

			{/* Comparison */}
			<section className="border-t border-border py-16">
				<h2 className={cn(siteText.h2, "max-w-2xl")}>{content.comparison.heading}</h2>
				<p className={cn(siteText.body, "mt-3 max-w-2xl")}>{content.comparison.intro}</p>
				<section
					className="mt-8 overflow-x-auto focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring"
					aria-label={content.comparison.heading}
					/* biome-ignore lint/a11y/noNoninteractiveTabindex: a region that scrolls horizontally has to be focusable, or a keyboard-only visitor cannot reach the columns past the fold. The labelled landmark is what makes the focus stop meaningful. */
					tabIndex={0}
				>
					<table className="ss-home-table">
						<thead>
							<tr>
								<th scope="col">
									<span className="sr-only">Feature</span>
								</th>
								<th scope="col">{content.comparison.columnLabel}</th>
								<th scope="col" data-col="ours">
									SurfSense
								</th>
							</tr>
						</thead>
						<tbody>
							{content.comparison.rows.map((row) => (
								<tr key={row.feature}>
									<th scope="row">{row.feature}</th>
									<td>{row.official}</td>
									<td data-col="ours">{row.surfsense}</td>
								</tr>
							))}
						</tbody>
					</table>
				</section>
			</section>

			{/* FAQ */}
			<section className="border-t border-border" aria-labelledby="ss-connector-faq-label">
				<div className="pt-12 pb-8">
					<h2
						id="ss-connector-faq-label"
						className="text-center text-lg font-medium tracking-tight text-muted-foreground md:text-2xl"
					>
						{label}: frequently asked questions
					</h2>
				</div>
				<div className="ss-home-grid border-t border-border">
					{content.faq.map((item) => (
						<SiteFaqItem key={item.question} question={item.question}>
							<p className={siteText.body}>{item.answer}</p>
						</SiteFaqItem>
					))}
				</div>
			</section>

			{/* Closing CTA + related */}
			<section className="border-t border-border py-16">
				<div className="mx-auto max-w-2xl text-center">
					<h2 className={siteText.h2}>Point your agents at {content.name}</h2>
					<p className={cn(siteText.body, "mt-3")}>
						The {content.name} connector is one of many in the SurfSense{" "}
						<Link className={siteText.link} href="/">
							open web research platform
						</Link>
						. Start free, no credit card required.
					</p>
					<div className="mt-8 flex flex-wrap items-center justify-center gap-3">
						<HomeButton asChild size="xl">
							<Link href="/register">Start for free</Link>
						</HomeButton>
						<HomeButton asChild variant="secondary" size="xl">
							<Link href="/pricing">See pricing</Link>
						</HomeButton>
						<HomeButton asChild variant="ghost" size="xl">
							<a href={GITHUB_URL} target="_blank" rel="noreferrer noopener">
								<IconBrandGithub className="size-4" />
								GitHub
							</a>
						</HomeButton>
					</div>
				</div>
			</section>
		</>
	);
}
