"use client";

import Link from "next/link";
import { useDeferredValue, useState } from "react";
import { HomeButton } from "@/components/site/home-button";
import { siteText } from "@/components/site/site-text";
import { cn } from "@/components/ui/cn";
import { Search01Icon } from "@/components/ui/icons";
import { PluginCard } from "./plugin-card";
import { PluginLine } from "./plugin-line";
import { FEATURED_IDS, type PluginListing, SURFSENSE_PLUGINS } from "./plugin-list";

function matches(plugin: PluginListing, query: string) {
	const haystack = `${plugin.name} ${plugin.description} ${plugin.author}`.toLowerCase();
	return query
		.toLowerCase()
		.split(/\s+/)
		.every((word) => haystack.includes(word));
}

function PluginRow({
	id,
	title,
	subtitle,
	plugins,
	layout = "lines",
}: {
	id: string;
	title: string;
	subtitle: React.ReactNode;
	plugins: PluginListing[];
	/** Cards for the hand picked few; a compact line for every other list. */
	layout?: "cards" | "lines";
}) {
	return (
		<section aria-labelledby={id} className="pt-16 md:pt-24">
			<h2 id={id} className={cn(siteText.h3, "text-2xl")}>
				{title}
			</h2>
			<p className={cn(siteText.body, "mt-1")}>{subtitle}</p>
			{layout === "cards" ? (
				<ul className="m-0 mt-8 grid list-none gap-x-6 gap-y-10 p-0 sm:grid-cols-2 lg:grid-cols-4">
					{plugins.map((plugin) => (
						<li key={plugin.id}>
							<PluginCard plugin={plugin} />
						</li>
					))}
				</ul>
			) : (
				<ul className="m-0 mt-6 grid list-none gap-x-10 gap-y-1 p-0 lg:grid-cols-2">
					{plugins.map((plugin) => (
						<li key={plugin.id} className="min-w-0">
							<PluginLine plugin={plugin} />
						</li>
					))}
				</ul>
			)}
		</section>
	);
}

/** The actions, the search box, and the rows it filters. Other publishers' come from the server. */
export function PluginBrowser({
	registryPlugins,
	submitUrl,
	docsUrl,
}: {
	registryPlugins: PluginListing[];
	submitUrl: string;
	docsUrl: string;
}) {
	const [query, setQuery] = useState("");
	const deferredQuery = useDeferredValue(query.trim());
	const allPlugins = [...SURFSENSE_PLUGINS, ...registryPlugins];
	const featured = FEATURED_IDS.flatMap((id) => allPlugins.filter((plugin) => plugin.id === id));
	const results = deferredQuery
		? allPlugins.filter((plugin) => matches(plugin, deferredQuery))
		: [];

	return (
		<>
			<div className="mt-8 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
				<div className="flex flex-wrap gap-3">
					<HomeButton asChild size="xl">
						<a href={submitUrl} target="_blank" rel="noreferrer noopener">
							Submit a plugin
						</a>
					</HomeButton>
					<HomeButton asChild size="xl" variant="outline">
						<a href={docsUrl} target="_blank" rel="noreferrer noopener">
							Read the docs
						</a>
					</HomeButton>
				</div>
				<label className="relative block w-full md:max-w-sm">
					<span className="sr-only">Search plugins</span>
					<Search01Icon
						aria-hidden="true"
						className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-muted-foreground"
					/>
					<input
						type="search"
						value={query}
						onChange={(event) => setQuery(event.target.value)}
						placeholder="Search plugins"
						className="h-10 w-full rounded-lg border border-border bg-transparent pr-3 pl-10 text-base outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 md:text-sm"
					/>
				</label>
			</div>

			{deferredQuery ? (
				results.length > 0 ? (
					<PluginRow
						id="plugins-results-label"
						title="Results"
						subtitle={`${results.length} ${results.length === 1 ? "plugin matches" : "plugins match"} “${deferredQuery}”.`}
						plugins={results}
					/>
				) : (
					<section aria-live="polite" className="pt-16 md:pt-24">
						<p className={siteText.h3}>No plugin matches “{deferredQuery}”.</p>
						<p className={cn(siteText.body, "mt-1")}>
							Any MCP server works as a custom plugin in Settings › Plugins, or{" "}
							<Link className={siteText.link} href="/contact">
								tell us which one to build
							</Link>
							.
						</p>
					</section>
				)
			) : (
				<>
					<PluginRow
						id="plugins-featured-label"
						title="Featured"
						subtitle="A selection of hand picked plugins."
						plugins={featured}
						layout="cards"
					/>
					<PluginRow
						id="plugins-surfsense-label"
						title="By SurfSense"
						subtitle={
							<>
								Made by us. One licence for all.{" "}
								<Link className={siteText.link} href="/pricing">
									See pricing
								</Link>
								.
							</>
						}
						plugins={SURFSENSE_PLUGINS}
					/>
					{registryPlugins.length > 0 ? (
						<PluginRow
							id="plugins-third-party-label"
							title="From other publishers"
							subtitle="Plugins other companies publish. No SurfSense licence needed."
							plugins={registryPlugins}
						/>
					) : null}
				</>
			)}
		</>
	);
}
