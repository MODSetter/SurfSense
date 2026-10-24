import { cn } from "@/components/ui/cn";
import type { PluginListing } from "./plugin-listing";

// A registry mark may be white (DeepWiki's) or black, so it sits on taupe, in the site's
// warm palette: 4.2:1 against white and 5.0:1 against black, above icons' 3:1.
export function markTile(plugin: PluginListing) {
	return plugin.logo.kind === "inline" ? undefined : "border-transparent bg-[#857a6e]";
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
					// White on the taupe tile `markTile` gives it.
					"font-medium text-white uppercase",
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
