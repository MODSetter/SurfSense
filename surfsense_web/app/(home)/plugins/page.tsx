import type { Metadata } from "next";
import Link from "next/link";
import { HomeBadge } from "@/components/homepage/home/home-badge";
import { HomeButton } from "@/components/homepage/home/home-button";
import { sectionSpacing } from "@/components/homepage/home/home-section-spacing";
import { AmazonLogo } from "@/components/homepage/icons/amazon-logo";
import { GoogleMapsLogo } from "@/components/homepage/icons/google-maps-logo";
import { GoogleSearchLogo } from "@/components/homepage/icons/google-search-logo";
import { IndeedLogo } from "@/components/homepage/icons/indeed-logo";
import { TiktokLogo } from "@/components/homepage/icons/tiktok-logo";
import { WalmartLogo } from "@/components/homepage/icons/walmart-logo";
import { WebCrawlLogo } from "@/components/homepage/icons/web-crawl-logo";
import { YoutubeLogo } from "@/components/homepage/icons/youtube-logo";
import { DOWNLOADS_URL, REPO_URL } from "@/components/site/site-content";
import { siteText } from "@/components/site/site-text";
import { ArrowUpRight01Icon } from "@/components/ui/icons";
import { cn } from "@/lib/utils";

/**
 * Plugins page.
 *
 * Rendered in the site design: the palette, column, navigation and footer all
 * come from `app/(home)/layout.tsx`; the page uses the homepage's centred
 * headings and rounded cards, with no motion. Listed in `SITE_DESIGN_ROUTES` in
 * `components/site/site-shell.tsx`.
 *
 * SurfSense's own plugins shipped in 2.2.1. The list mirrors the app's
 * first-party list, `surfsense_local/backend/modules/plugins/lists/first_party/plugins.json`,
 * in its order and with its one-line descriptions; change them together.
 * Reddit and Instagram are written but left out of that list, because both now
 * close their public pages to readers who are not signed in, so this page says
 * so rather than listing them.
 *
 * Each tile links to that platform's marketing page under
 * `lib/connectors-marketing`.
 *
 * Logos are inline components from `components/homepage/icons/`, so they
 * arrive in the HTML and paint with the page instead of loading one request
 * each afterwards. They are the marketing site's own copies of the brand
 * marks the product's connector picker reads from `public/connectors/`.
 *
 * Replaces the old `/connectors` index, which now redirects here from
 * `next.config.ts`.
 *
 * A server component with no client JavaScript.
 */

const canonicalUrl = "https://www.surfsense.com/plugins";
const registryUrl = `${REPO_URL}/tree/main/plugins/registry`;

const metaTitle = "SurfSense Plugins: Google Search, YouTube, TikTok, Amazon and More";
const metaDescription =
	"Plugins give SurfSense's agent live data from Google Search, YouTube, TikTok, Google Maps, Amazon, Walmart, Indeed and any web page. Free for 30 days, plus any MCP server you add.";

export const metadata: Metadata = {
	title: metaTitle,
	description: metaDescription,
	alternates: { canonical: canonicalUrl },
	openGraph: {
		title: metaTitle,
		description: metaDescription,
		url: canonicalUrl,
		siteName: "SurfSense",
		type: "website",
		images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "SurfSense plugins" }],
	},
	twitter: {
		card: "summary_large_image",
		title: metaTitle,
		description: metaDescription,
		images: ["/og-image.png"],
	},
};

const PLUGINS = [
	{
		name: "Google Search",
		href: "/google-search",
		Logo: GoogleSearchLogo,
		description: "Search Google and read its results, ads and related questions.",
	},
	{
		name: "Web Crawl",
		href: "/web-crawl",
		Logo: WebCrawlLogo,
		description: "Read a web page, or crawl a whole site into clean text.",
	},
	{
		name: "YouTube",
		href: "/youtube",
		Logo: YoutubeLogo,
		description: "Read YouTube videos, channels and their comments.",
	},
	{
		name: "TikTok",
		href: "/tiktok",
		Logo: TiktokLogo,
		description: "Read TikTok videos and their comments, search users, and see what is trending.",
	},
	{
		name: "Google Maps",
		href: "/google-maps",
		Logo: GoogleMapsLogo,
		description: "Find places on Google Maps and read their reviews.",
	},
	{
		name: "Amazon",
		href: "/amazon",
		Logo: AmazonLogo,
		description: "Read Amazon products and search results.",
	},
	{
		name: "Walmart",
		href: "/walmart",
		Logo: WalmartLogo,
		description: "Read Walmart products, search results and reviews.",
	},
	{
		name: "Indeed",
		href: "/indeed",
		Logo: IndeedLogo,
		description: "Read job listings on Indeed.",
	},
];

/** How a new user gets from the website to a plugin answering in a chat. */
const STEPS = [
	{
		title: "Get the app and a licence",
		body: "Download SurfSense and enter your email on the download page. A free 30-day licence arrives in your inbox; import it in Settings › License.",
	},
	{
		title: "Connect the plugins you want",
		body: "In Settings › Plugins, open Browse and connect the ones you want under By SurfSense. The first asks you to allow plugins.surfsense.com.",
	},
	{
		title: "Name one in a chat",
		body: "In an Agentic chat, type @ and pick a plugin, such as @amazon, then ask. The agent reads the results and answers from them.",
	},
];

export default function PluginsPage() {
	return (
		<>
			<section className="text-center">
				<div className={sectionSpacing.head}>
					<HomeBadge>Available now</HomeBadge>
					<h1 className={cn(siteText.display, "mx-auto mt-4 max-w-4xl")}>
						Plugins for the platforms your <span className="text-primary">answers live on</span>
					</h1>
					<p className={cn(siteText.lede, "mx-auto mt-8 max-w-2xl")}>
						Plugins give SurfSense's agent live data from the web. Ours read public pages without
						your own accounts, so nothing is ever bought, posted or applied for.
					</p>
					<div className="mt-8 flex justify-center">
						<HomeButton asChild size="xl" className="rounded-full">
							<Link href={DOWNLOADS_URL}>Download and try them free</Link>
						</HomeButton>
					</div>
				</div>
			</section>

			<section aria-labelledby="ss-plugins-label" className={sectionSpacing.foot}>
				<div className={cn("text-center", sectionSpacing.head)}>
					<HomeBadge>By SurfSense</HomeBadge>
					<h2 id="ss-plugins-label" className={cn(siteText.h2, "mt-4")}>
						Eight plugins, one licence
					</h2>
					<p className={cn(siteText.body, "mx-auto mt-4 max-w-2xl")}>
						A licence unlocks all of them, unlimited and unmetered.{" "}
						<Link className={siteText.link} href="/pricing">
							See pricing
						</Link>
						.
					</p>
				</div>

				<ul className="m-0 mt-10 grid list-none gap-4 p-0 sm:grid-cols-2 lg:mt-14 lg:grid-cols-4">
					{PLUGINS.map((plugin) => (
						<li key={plugin.name}>
							<Link
								href={plugin.href}
								className="group flex h-full flex-col gap-3 rounded-2xl border border-border bg-card p-4 text-inherit shadow-xs hover:border-muted-foreground/40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
							>
								<span className="flex items-center justify-between gap-4">
									<span className="grid size-12 shrink-0 place-items-center rounded-xl bg-secondary">
										<plugin.Logo className="size-6" />
									</span>
									<ArrowUpRight01Icon
										aria-hidden="true"
										className="size-4 shrink-0 text-muted-foreground group-hover:text-foreground group-focus-visible:text-foreground"
									/>
								</span>
								<span className={siteText.h3}>{plugin.name}</span>
								<span className="text-sm text-muted-foreground">{plugin.description}</span>
							</Link>
						</li>
					))}
				</ul>

				<p className={cn(siteText.body, "mx-auto mt-6 max-w-2xl text-center text-sm")}>
					Reddit and Instagram plugins are written but not offered: both platforms now close their
					public pages to readers who are not signed in.
				</p>
			</section>

			<section aria-labelledby="ss-plugins-steps-label" className={sectionSpacing.foot}>
				<div className={cn("text-center", sectionSpacing.head)}>
					<HomeBadge>Get started</HomeBadge>
					<h2 id="ss-plugins-steps-label" className={cn(siteText.h2, "mt-4")}>
						From download to answer in three steps
					</h2>
				</div>

				<ol className="m-0 mt-10 grid list-none gap-4 p-0 md:grid-cols-3 lg:mt-14">
					{STEPS.map((step, index) => (
						<li
							key={step.title}
							className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-6 shadow-xs"
						>
							<span className="grid size-8 place-items-center rounded-full bg-foreground text-sm font-semibold text-background">
								{index + 1}
							</span>
							<span className={siteText.h3}>{step.title}</span>
							<span className={cn(siteText.body, "text-sm")}>{step.body}</span>
						</li>
					))}
				</ol>
			</section>

			<section aria-labelledby="ss-plugins-third-party-label" className={sectionSpacing.foot}>
				<div className="flex flex-col items-start gap-6 rounded-4xl border border-border bg-card px-6 py-8 shadow-xs md:px-12 md:py-12 lg:flex-row lg:items-center lg:justify-between">
					<div>
						<h2 id="ss-plugins-third-party-label" className={siteText.h3}>
							Third-party plugins and your own MCP servers
						</h2>
						<p className={cn(siteText.body, "mt-2 max-w-2xl")}>
							Plugins from other publishers, such as DeepWiki and Notion, and any MCP server you add
							by URL work too, with no SurfSense licence. They stay off until you allow them in
							Settings › Plugins. Publishers list theirs in the registry by pull request.
						</p>
					</div>
					<a
						href={registryUrl}
						target="_blank"
						rel="noreferrer noopener"
						className="inline-flex h-12 shrink-0 items-center rounded-full border border-border px-6 text-sm font-semibold text-foreground hover:bg-secondary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
					>
						See the registry
					</a>
				</div>
			</section>

			<section className={sectionSpacing.foot}>
				<div className="flex flex-col items-start gap-6 rounded-4xl border border-border bg-card px-6 py-8 shadow-xs md:px-12 md:py-12 lg:flex-row lg:items-center lg:justify-between">
					<div>
						<p className={siteText.h3}>Need a platform that is not on this list?</p>
						<p className={cn(siteText.body, "mt-2")}>
							Tell us which one, and we will weigh it for the next plugins we build.
						</p>
					</div>
					<Link
						href="/contact"
						className="inline-flex h-12 shrink-0 items-center rounded-full bg-foreground px-6 text-sm font-semibold text-background shadow-lg hover:bg-foreground/90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
					>
						Tell us which one
					</Link>
				</div>
			</section>
		</>
	);
}
