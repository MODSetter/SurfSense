import type { Metadata } from "next";
import Link from "next/link";
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
import { Badge } from "@/components/ui/badge";
import { ArrowUpRight01Icon } from "@/components/ui/icons";

/**
 * Plugins page.
 *
 * Rendered in the site design: the palette, ruled column, navigation and footer
 * all come from `app/(home)/layout.tsx`, and every style resolves from
 * `app/(home)/home.css`. Listed in `SITE_DESIGN_ROUTES` in
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
			<section className="ss-home-hero ss-home-pad">
				<div className="mx-auto max-w-3xl text-center">
					<Badge variant="secondary" className="rounded-full px-3 py-1">
						Coming soon
					</Badge>
					<h1 className="ss-home-display mt-4">
						Plugins for the platforms your <span className="ss-home-accent">answers live on</span>
					</h1>
					<p className="ss-home-lede mx-auto mt-8 max-w-2xl">
						Each plugin pulls public data from one platform straight into your notebook. These are
						the ones being built first.
					</p>
				</div>
			</section>

			<section className="ss-home-rule" aria-labelledby="ss-plugins-label">
				<div className="ss-home-head">
					<p className="ss-home-eyebrow">Plugins</p>
					<h2 id="ss-plugins-label" className="ss-home-h2 mt-2">
						Shipping first
					</h2>
				</div>

				<ul className="ss-home-grid ss-home-grid-2 ss-home-grid-3 list-none border-t border-[color:var(--border)] p-0">
					{PLUGINS.map((plugin) => (
						<li key={plugin.name}>
							<Link href={plugin.href} className="ss-home-cell ss-home-cell-link">
								<plugin.Logo className="size-5 shrink-0" />
								<span className="ss-home-h3">{plugin.name}</span>
								<ArrowUpRight01Icon
									aria-hidden="true"
									className="ss-home-cell-link-arrow size-4 shrink-0"
								/>
							</Link>
						</li>
					))}
					{/* Fills out the last row of the three-column grid: ten platforms is
					    not a multiple of three, and this says so instead of leaving the
					    row's remaining cells empty. Not a link — there is nothing to open
					    yet for whatever comes after this list. */}
					<li className="ss-home-grid-span-2">
						<div className="ss-home-cell flex items-center text-[color:var(--muted-foreground)]">
							<span className="text-sm">And many more on the way</span>
						</div>
					</li>
				</ul>
			</section>

			<section className="ss-home-rule ss-home-pad py-12">
				<p className="ss-home-body mx-auto max-w-2xl text-center text-sm">
					Need a platform that is not on this list?{" "}
					<Link className="ss-home-link" href="/contact">
						Tell us which one
					</Link>
					.
				</p>
			</section>
		</>
	);
}
