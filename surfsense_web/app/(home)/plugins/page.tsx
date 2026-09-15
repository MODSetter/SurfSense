import { ArrowUpRight } from "lucide-react";
import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";

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
 * Logos are the same brand SVGs the product's own connector picker uses (see
 * `contracts/enums/connectorIcons.tsx`), read from `public/connectors/`, rather
 * than a second icon set drawn just for this page.
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
	{ name: "Reddit", href: "/reddit", logo: "/connectors/reddit.svg" },
	{ name: "YouTube", href: "/youtube", logo: "/connectors/youtube.svg" },
	{ name: "Instagram", href: "/instagram", logo: "/connectors/instagram.svg" },
	{ name: "TikTok", href: "/tiktok", logo: "/connectors/tiktok.svg" },
	{ name: "Google Maps", href: "/google-maps", logo: "/connectors/google-maps.svg" },
	{ name: "Google Search", href: "/google-search", logo: "/connectors/google-search.svg" },
	{ name: "Indeed", href: "/indeed", logo: "/connectors/indeed.svg" },
	{ name: "Amazon", href: "/amazon", logo: "/connectors/amazon.svg" },
	{ name: "Walmart", href: "/walmart", logo: "/connectors/walmart.svg" },
	{ name: "Web Crawl", href: "/web-crawl", logo: "/connectors/web.svg" },
];

export default function PluginsPage() {
	return (
		<>
			<section className="ss-home-hero ss-home-pad">
				<div className="mx-auto max-w-3xl text-center">
					<span className="ss-home-badge">Coming soon</span>
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
						Shipping <span className="ss-home-accent">first</span>
					</h2>
				</div>

				<ul className="ss-home-grid ss-home-grid-2 ss-home-grid-3 list-none border-t border-[color:var(--border)] p-0">
					{PLUGINS.map((plugin) => (
						<li key={plugin.name}>
							<Link href={plugin.href} className="ss-home-cell ss-home-cell-link">
								<Image
									src={plugin.logo}
									alt=""
									width={20}
									height={20}
									className="size-5 shrink-0"
								/>
								<span className="ss-home-h3">{plugin.name}</span>
								<ArrowUpRight
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
