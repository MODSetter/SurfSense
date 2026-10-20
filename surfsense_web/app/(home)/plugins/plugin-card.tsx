import Link from "next/link";
import { siteText } from "@/components/site/site-text";
import { CheckIcon } from "@/components/ui/icons";
import { cn } from "@/lib/utils";
import type { PluginListing } from "./plugin-list";

const ACCESS_LABEL: Record<PluginListing["access"], string> = {
	license: "SurfSense licence",
	free: "Free",
	external: "Paid by publisher",
};

// Registry marks are light or coloured, so they sit on a grey tile, as in the app.
const REGISTRY_TILE = "bg-muted-foreground/20";

function PluginMark({ plugin, size }: { plugin: PluginListing; size: "sm" | "lg" }) {
	const markSize = size === "lg" ? "size-14" : "size-5";
	if (plugin.logo.kind === "inline") {
		return <plugin.logo.Logo className={markSize} />;
	}
	if (plugin.logo.kind === "letter") {
		return (
			<span
				aria-hidden="true"
				className={cn(
					"font-medium text-muted-foreground uppercase",
					size === "lg" ? "text-4xl" : "text-sm"
				)}
			>
				{plugin.logo.letter}
			</span>
		);
	}
	// biome-ignore lint/performance/noImgElement: the registry's own small icon; next/image would proxy it for nothing.
	return <img src={plugin.logo.src} alt="" className={cn(markSize, "object-contain")} />;
}

/** One plugin: a preview tile, its name, one line, and who publishes it. */
export function PluginCard({ plugin }: { plugin: PluginListing }) {
	const external = plugin.href.startsWith("http");
	const tile = plugin.logo.kind === "inline" ? undefined : REGISTRY_TILE;
	const className =
		"group flex h-full flex-col gap-3 rounded-2xl text-inherit focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring";

	const body = (
		<>
			<span
				className={cn(
					"grid aspect-[16/10] place-items-center rounded-2xl border border-border bg-card shadow-xs transition-[border-color] duration-150 ease-out group-hover:border-muted-foreground/40",
					tile
				)}
			>
				<PluginMark plugin={plugin} size="lg" />
			</span>
			<span className="mt-1 flex items-center gap-3">
				<span
					className={cn(
						"grid size-9 shrink-0 place-items-center rounded-lg border border-border bg-secondary",
						tile
					)}
				>
					<PluginMark plugin={plugin} size="sm" />
				</span>
				<span className={siteText.h3}>{plugin.name}</span>
			</span>
			<span className="line-clamp-2 text-sm leading-relaxed text-muted-foreground">
				{plugin.description}
			</span>
			<span className="mt-auto flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted-foreground">
				<span className="inline-flex items-center gap-1">
					{plugin.author}
					{plugin.verification === "verified" ? (
						<CheckIcon aria-label="Verified" className="size-3.5 text-primary" />
					) : null}
				</span>
				<span aria-hidden="true">·</span>
				<span>{ACCESS_LABEL[plugin.access]}</span>
				{plugin.verification === "community" ? (
					<>
						<span aria-hidden="true">·</span>
						<span>Community</span>
					</>
				) : null}
			</span>
		</>
	);

	if (external) {
		return (
			<a href={plugin.href} target="_blank" rel="noreferrer noopener" className={className}>
				{body}
			</a>
		);
	}
	return (
		<Link href={plugin.href} className={className}>
			{body}
		</Link>
	);
}
