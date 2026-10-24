import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";
import { BreadcrumbNav } from "@/components/site/breadcrumb-nav";
import { HomeButton } from "@/components/site/home-button";
import { sectionSpacing } from "@/components/site/home-section-spacing";
import { DOWNLOADS_URL } from "@/components/site/site-content";
import { siteText } from "@/components/site/site-text";
import { cn } from "@/components/ui/cn";
import { DotIcon } from "@/components/ui/icons";
import { ACCESS_LABEL } from "../access-label";
import { allPlugins, findPlugin } from "../all-plugins";
import { markTile, PluginMark } from "../plugin-mark";
import { VerifiedMark } from "../verified-mark";
import { PluginDetails } from "./plugin-details";
import { PluginTools } from "./plugin-tools";

/**
 * `/plugins/<id>`: a listed plugin's page, the one the app opens from Browse, built from
 * its list entry alone. Replaces the per-scraper marketing pages, which redirect here
 * from `next.config.ts`. A plugin the registry lists later is rendered on first visit.
 */

// The registry list is read at most hourly, as on `/plugins`.
export const revalidate = 3600;

interface PageProps {
	params: Promise<{ id: string }>;
}

export async function generateStaticParams() {
	return (await allPlugins()).map((plugin) => ({ id: plugin.id }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
	const plugin = await findPlugin((await params).id);
	if (!plugin) return { title: "Plugin not found | SurfSense" };
	const title = `${plugin.name} plugin for SurfSense`;
	const canonicalUrl = `https://www.surfsense.com${plugin.href}`;
	return {
		title,
		description: plugin.description,
		alternates: { canonical: canonicalUrl },
		openGraph: {
			title,
			description: plugin.description,
			url: canonicalUrl,
			siteName: "SurfSense",
			type: "website",
			images: [{ url: "/og-image.png", width: 1200, height: 630, alt: title }],
		},
		twitter: {
			card: "summary_large_image",
			title,
			description: plugin.description,
			images: ["/og-image.png"],
		},
	};
}

function Section({ title, children }: { title: string; children: ReactNode }) {
	return (
		<section className="border-t border-border pt-8">
			<h2 className={siteText.h3}>{title}</h2>
			<div className="mt-4">{children}</div>
		</section>
	);
}

export default async function PluginPage({ params }: PageProps) {
	const plugin = await findPlugin((await params).id);
	if (!plugin) notFound();

	const tile = markTile(plugin);
	const thirdParty = plugin.publisher === "third-party";
	return (
		<article className={cn(sectionSpacing.head, sectionSpacing.foot, "mx-auto max-w-3xl")}>
			<BreadcrumbNav
				items={[
					{ name: "Plugins", href: "/plugins" },
					{ name: plugin.name, href: plugin.href },
				]}
			/>

			<header className="mt-8 flex flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
				<div className="flex min-w-0 items-center gap-4">
					<span
						className={cn(
							"grid size-16 shrink-0 place-items-center rounded-2xl border border-border bg-card shadow-xs",
							tile
						)}
					>
						<PluginMark plugin={plugin} size="md" />
					</span>
					<div className="min-w-0">
						<h1 className={cn(siteText.h2, "flex items-center gap-2")}>
							{plugin.name}
							<VerifiedMark plugin={plugin} className="size-6" />
						</h1>
						<p className="mt-1 flex flex-wrap items-center gap-x-2 text-sm text-muted-foreground">
							<span>by {plugin.author}</span>
							<DotIcon aria-hidden="true" className="size-3 shrink-0" />
							<span>{ACCESS_LABEL[plugin.access]}</span>
						</p>
					</div>
				</div>
				<HomeButton asChild size="lg" className="shrink-0 self-start">
					<Link href={DOWNLOADS_URL}>Get SurfSense</Link>
				</HomeButton>
			</header>

			<p className={cn(siteText.lede, "mt-8")}>{plugin.description}</p>
			<p className={cn(siteText.body, "mt-3 text-sm")}>
				{thirdParty
					? "Connect it in the SurfSense desktop app: turn on Allow third-party plugins in Settings › Plugins, then find it in Browse."
					: "Connect it in the SurfSense desktop app, in Settings › Plugins."}
			</p>

			<div className="mt-12 flex flex-col gap-10">
				{/* Never the description in its place: the page already leads with it. */}
				{plugin.about ? (
					<Section title="About">
						<p className={siteText.body}>{plugin.about}</p>
					</Section>
				) : null}
				<Section title="Tools">
					<PluginTools tools={plugin.tools} />
				</Section>
				<Section title="Details">
					<PluginDetails plugin={plugin} />
				</Section>
			</div>
		</article>
	);
}
