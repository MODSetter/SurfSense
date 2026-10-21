import { cn } from "@/lib/utils";
import type { PluginListing } from "./plugin-listing";

// Registry marks are light or coloured, so they sit on a grey tile, as in the app.
export function markTile(plugin: PluginListing) {
	return plugin.logo.kind === "inline" ? undefined : "bg-muted-foreground/20";
}

/** A plugin's logo, its registry icon, or its first letter. */
export function PluginMark({ plugin, size }: { plugin: PluginListing; size: "sm" | "md" | "lg" }) {
	const markSize = { sm: "size-5", md: "size-9", lg: "size-14" }[size];
	if (plugin.logo.kind === "inline") {
		return <plugin.logo.Logo className={markSize} />;
	}
	if (plugin.logo.kind === "letter") {
		return (
			<span
				aria-hidden="true"
				className={cn(
					"font-medium text-muted-foreground uppercase",
					{ sm: "text-sm", md: "text-2xl", lg: "text-4xl" }[size]
				)}
			>
				{plugin.logo.letter}
			</span>
		);
	}
	// biome-ignore lint/performance/noImgElement: the registry's own small icon; next/image would proxy it for nothing.
	return <img src={plugin.logo.src} alt="" className={cn(markSize, "object-contain")} />;
}
