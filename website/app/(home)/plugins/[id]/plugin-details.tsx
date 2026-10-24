import type { ReactNode } from "react";
import { siteText } from "@/components/site/site-text";
import { cn } from "@/components/ui/cn";
import { ArrowUpRight01Icon } from "@/components/ui/icons";
import type { PluginListing, PluginSignIn } from "../plugin-listing";

// What connecting asks of the user, as the app's plugin page names it.
function signInLabel(signIn: PluginSignIn, plugin: string) {
	switch (signIn) {
		case "license":
			return "SurfSense licence";
		case "token":
			return "API key";
		case "oauth":
			return `Your ${plugin} account`;
		case "none":
			return "None";
	}
}

// UTC, so `2026-10` reads as October wherever the page is rendered.
function addedMonth(added: string) {
	const [year, month] = added.split("-").map(Number);
	return new Intl.DateTimeFormat("en", {
		month: "long",
		year: "numeric",
		timeZone: "UTC",
	}).format(new Date(Date.UTC(year, month - 1, 1)));
}

function Fact({ term, children }: { term: string; children: ReactNode }) {
	return (
		<div className="grid grid-cols-1 gap-1 border-b border-border py-3 text-sm last:border-b-0 sm:grid-cols-[10rem_1fr] sm:gap-4">
			<dt className="text-muted-foreground">{term}</dt>
			<dd className="m-0 min-w-0 wrap-break-word">{children}</dd>
		</div>
	);
}

function PageLink({ url }: { url: string }) {
	return (
		<a
			href={url}
			target="_blank"
			rel="noreferrer noopener"
			className={cn(siteText.link, "inline-flex max-w-full items-center gap-1")}
		>
			<span className="min-w-0 break-all">{new URL(url).host}</span>
			{/* The app's external-link mark. */}
			<ArrowUpRight01Icon aria-hidden="true" className="size-3.5 shrink-0" />
		</a>
	);
}

/** Who publishes a plugin, how it signs in, what it connects to and its pages, from its entry. */
export function PluginDetails({ plugin }: { plugin: PluginListing }) {
	return (
		<dl className="m-0">
			<Fact term="Publisher">{plugin.author}</Fact>
			<Fact term="Authentication">
				{signInLabel(plugin.signIn, plugin.name)}
				{plugin.accessNote ? (
					<span className="block text-muted-foreground">{plugin.accessNote}</span>
				) : null}
			</Fact>
			<Fact term="Connects to">{plugin.serverHost}</Fact>
			{/* An OAuth plugin's other hosts see the sign-in, never a call. */}
			{plugin.signInHosts.length ? (
				<Fact term="Signs in with">{plugin.signInHosts.join(", ")}</Fact>
			) : null}
			{plugin.added ? <Fact term="Added">{addedMonth(plugin.added)}</Fact> : null}
			{plugin.homepage ? (
				<Fact term="Homepage">
					<PageLink url={plugin.homepage} />
				</Fact>
			) : null}
			{plugin.privacyPolicy ? (
				<Fact term="Privacy policy">
					<PageLink url={plugin.privacyPolicy} />
				</Fact>
			) : null}
		</dl>
	);
}
