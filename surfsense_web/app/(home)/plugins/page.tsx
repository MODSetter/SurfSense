import type { Metadata } from "next";
import Link from "next/link";
import { HomeBadge } from "@/components/homepage/home/home-badge";
import { sectionSpacing } from "@/components/homepage/home/home-section-spacing";
import { AmazonLogo } from "@/components/homepage/icons/amazon-logo";
import { GoogleMapsLogo } from "@/components/homepage/icons/google-maps-logo";
import { GoogleSearchLogo } from "@/components/homepage/icons/google-search-logo";
import { IndeedLogo } from "@/components/homepage/icons/indeed-logo";
import { InstagramLogo } from "@/components/homepage/icons/instagram-logo";
import { RedditLogo } from "@/components/homepage/icons/reddit-logo";
import { TiktokLogo } from "@/components/homepage/icons/tiktok-logo";
import { WalmartLogo } from "@/components/homepage/icons/walmart-logo";
import { WebCrawlLogo } from "@/components/homepage/icons/web-crawl-logo";
import { YoutubeLogo } from "@/components/homepage/icons/youtube-logo";
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
 * The page is a placeholder while the plugins ship, so it says the one thing a
 * visitor came for (which platforms are covered) and nothing else. The list is
 * declared here rather than read from a registry: this page is the whole of
 * what the site claims about plugins.
 *
 * Each tile links to that platform's existing marketing page under
 * `lib/connectors-marketing` — the plugin itself is not live yet, but the page
 * explaining what it will do already is.
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

const metaTitle = "SurfSense Plugins: Scrapers for Every Platform";
const metaDescription =
	"Scraper plugins for Reddit, YouTube, Instagram, TikTok, Google Maps, Google Search, Indeed, Amazon, Walmart and the open web. Coming soon to SurfSense.";

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
	{ name: "Reddit", href: "/reddit", Logo: RedditLogo },
	{ name: "YouTube", href: "/youtube", Logo: YoutubeLogo },
	{ name: "Instagram", href: "/instagram", Logo: InstagramLogo },
	{ name: "TikTok", href: "/tiktok", Logo: TiktokLogo },
	{ name: "Google Maps", href: "/google-maps", Logo: GoogleMapsLogo },
	{ name: "Google Search", href: "/google-search", Logo: GoogleSearchLogo },
	{ name: "Indeed", href: "/indeed", Logo: IndeedLogo },
	{ name: "Amazon", href: "/amazon", Logo: AmazonLogo },
	{ name: "Walmart", href: "/walmart", Logo: WalmartLogo },
	{ name: "Web Crawl", href: "/web-crawl", Logo: WebCrawlLogo },
];

export default function PluginsPage() {
	return (
		<>
			<section className="text-center">
				<div className={sectionSpacing.head}>
					<HomeBadge>Coming soon</HomeBadge>
					<h1 className={cn(siteText.display, "mx-auto mt-4 max-w-4xl")}>
						Plugins for the platforms your <span className="text-primary">answers live on</span>
					</h1>
					<p className={cn(siteText.lede, "mx-auto mt-8 max-w-2xl")}>
						Each plugin pulls public data from one platform straight into your notebook. These are
						the ones being built first.
					</p>
				</div>
			</section>

			<section aria-labelledby="ss-plugins-label" className={sectionSpacing.foot}>
				<div className={cn("text-center", sectionSpacing.head)}>
					<HomeBadge>Plugins</HomeBadge>
					<h2 id="ss-plugins-label" className={cn(siteText.h2, "mt-4")}>
						Shipping first
					</h2>
				</div>

				<ul className="m-0 mt-10 grid list-none gap-4 p-0 sm:grid-cols-2 lg:mt-14 lg:grid-cols-3">
					{PLUGINS.map((plugin) => (
						<li key={plugin.name}>
							<Link
								href={plugin.href}
								className="group flex items-center gap-4 rounded-2xl border border-border bg-card p-4 text-inherit shadow-xs hover:border-muted-foreground/40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
							>
								<span className="grid size-12 shrink-0 place-items-center rounded-xl bg-secondary">
									<plugin.Logo className="size-6" />
								</span>
								<span className="flex flex-1 flex-col gap-0.5">
									<span className={siteText.h3}>{plugin.name}</span>
									<span className="text-xs text-muted-foreground">Coming soon</span>
								</span>
								<ArrowUpRight01Icon
									aria-hidden="true"
									className="size-4 shrink-0 text-muted-foreground group-hover:text-foreground group-focus-visible:text-foreground"
								/>
							</Link>
						</li>
					))}
					{/* Fills out the last row: ten is not a multiple of three, and this says
					    so instead of leaving the row's remaining cells empty. Not a link —
					    there is nothing to open yet for whatever comes after this list. */}
					<li className="sm:col-span-2">
						<div className="flex h-full min-h-20 items-center justify-center rounded-2xl border border-dashed border-border p-4 text-sm text-muted-foreground">
							And many more on the way
						</div>
					</li>
				</ul>
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
