import Link from "next/link";
import { cn } from "@/components/ui/cn";
import type { PluginListing } from "./plugin-listing";
import { markTile, PluginMark } from "./plugin-mark";
import { VerifiedMark } from "./verified-mark";

/** One plugin as a compact row: its mark once, its name and one line. Opens its page. */
export function PluginLine({ plugin }: { plugin: PluginListing }) {
	return (
		<Link
			href={plugin.href}
			className="-mx-3 flex items-center gap-3 rounded-xl px-3 py-2.5 text-inherit transition-colors duration-150 ease-out hover:bg-secondary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
		>
			<span
				className={cn(
					"grid size-9 shrink-0 place-items-center rounded-lg border border-border bg-card",
					markTile(plugin)
				)}
			>
				<PluginMark plugin={plugin} size="sm" />
			</span>
			<span className="flex min-w-0 flex-1 flex-col">
				<span className="flex min-w-0 items-center gap-1.5">
					<span className="truncate font-medium">{plugin.name}</span>
					<VerifiedMark plugin={plugin} />
					{/* SurfSense's own sit under their own heading, so only another publisher is named. */}
					{plugin.publisher === "third-party" ? (
						<span className="ml-1 min-w-0 truncate text-sm text-muted-foreground">
							by {plugin.author}
						</span>
					) : null}
				</span>
				<span className="truncate text-sm text-muted-foreground">{plugin.description}</span>
			</span>
		</Link>
	);
}
