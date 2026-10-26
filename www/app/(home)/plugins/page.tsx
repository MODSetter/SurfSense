import type { Metadata } from "next";
import { HomeButton } from "@/components/site/home-button";
import { sectionSpacing } from "@/components/site/home-section-spacing";
import { REPO_URL } from "@/components/site/site-content";
import { siteText } from "@/components/site/site-text";
import { cn } from "@/components/ui/cn";
import { PluginBrowser } from "./plugin-browser";
import { SURFSENSE_PLUGINS } from "./plugin-list";
import { registryPlugins } from "./registry-plugins";

/**
 * Plugins page: every plugin SurfSense lists, as a browsable gallery.
 *
 * Rendered in the site design from `app/(home)/layout.tsx`; listed in
 * `SITE_DESIGN_ROUTES` in `components/site/site-shell.tsx`. Replaces the old
 * `/connectors` index, which redirects here from `next.config.ts`. Other publishers'
 * plugins are read from the registry container when the page is rendered.
 */

const canonicalUrl = "https://www.surfsense.com/plugins";
const registryUrl = `${REPO_URL}/tree/main/backend/plugins/registry`;
/** A form a bot checks and turns into the registry pull request; no git for the publisher. */
const submitUrl = `${REPO_URL}/issues/new?template=plugin-submit.yml`;

const metaTitle = "SurfSense Plugins: Google Search, Reddit, YouTube, Instagram and More";
const metaDescription =
	"Plugins give SurfSense's agent live data from Google Search, Reddit, YouTube, Instagram, TikTok, Google Maps, Amazon, Walmart, Indeed and any web page. Free for 14 days, plus any MCP server you add.";

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

export default async function PluginsPage() {
	const listed = await registryPlugins();
	const pluginCount = SURFSENSE_PLUGINS.length + listed.length;
	const publisherCount = new Set([...SURFSENSE_PLUGINS, ...listed].map((p) => p.author)).size;
	return (
		<>
			<section className={sectionSpacing.head}>
				<h1 className="flex flex-wrap items-baseline gap-x-4 gap-y-2">
					<span className={siteText.display}>Plugins</span>
					<span className="text-lg font-normal text-muted-foreground md:text-xl">
						{pluginCount} plugins by {publisherCount} publishers
					</span>
				</h1>
				<p className={cn(siteText.lede, "mt-6 max-w-2xl")}>
					Plugins give SurfSense's agent live data and tools. Ours read public pages without your
					own accounts; others come from their publishers through the registry.
				</p>
				<PluginBrowser registryPlugins={listed} submitUrl={submitUrl} docsUrl={registryUrl} />
			</section>

			<section
				aria-labelledby="ss-plugins-third-party-label"
				className={cn("pt-16 md:pt-24", sectionSpacing.foot)}
			>
				<div className="flex flex-col items-start gap-6 rounded-4xl border border-border bg-card px-6 py-8 shadow-xs md:px-12 md:py-12 lg:flex-row lg:items-center lg:justify-between">
					<div>
						<h2 id="ss-plugins-third-party-label" className={siteText.h3}>
							Third-party plugins and your own MCP servers
						</h2>
						<p className={cn(siteText.body, "mt-2 max-w-2xl")}>
							Plugins from other publishers, such as DeepWiki and Notion, and any MCP server you add
							by URL work too, with no SurfSense licence. They stay off until you allow them in
							Settings › Plugins. Publishers list theirs in the registry with a short form.
						</p>
					</div>
					<HomeButton
						asChild
						variant="bare"
						className={cn(
							"inline-flex h-12 shrink-0 items-center rounded-full border border-border px-6 text-sm font-semibold text-foreground hover:bg-secondary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
						)}
					>
						<a href={registryUrl} target="_blank" rel="noreferrer noopener">
							See the registry
						</a>
					</HomeButton>
				</div>
			</section>
		</>
	);
}
