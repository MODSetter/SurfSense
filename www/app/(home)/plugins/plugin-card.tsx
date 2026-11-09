import Link from "next/link";
import { siteText } from "@/components/site/site-text";
import { cn } from "@/components/ui/cn";
import type { PluginListing } from "./plugin-listing";
import { markTile, PluginMark } from "./plugin-mark";
import { VerifiedMark } from "./verified-mark";

/** One plugin: a preview tile, its name, one line, and who publishes it. Opens its page. */
export function PluginCard({ plugin }: { plugin: PluginListing }) {
	const tile = markTile(plugin);
	return (
		<Link
			href={plugin.href}
			className="group flex h-full flex-col gap-3 rounded-2xl text-inherit focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring"
		>
			<span
				className={cn(
					"grid aspect-16/10 place-items-center rounded-2xl border border-border bg-card shadow-xs transition-[border-color] duration-150 ease-out group-hover:border-muted-foreground/40",
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
				<span className="flex min-w-0 items-center gap-1.5">
					<span className={cn(siteText.h3, "truncate")}>{plugin.name}</span>
					<VerifiedMark plugin={plugin} />
				</span>
			</span>
			<span className="line-clamp-2 text-sm leading-relaxed text-muted-foreground">
				{plugin.description}
			</span>
			{/* Who pays is on the plugin's page. */}
			<span className="mt-auto truncate text-sm text-muted-foreground">By {plugin.author}</span>
		</Link>
	);
}
