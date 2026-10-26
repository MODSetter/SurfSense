import { cn } from "@/components/ui/cn";
import { CheckmarkBadgeIcon } from "@/components/ui/icons";
import type { PluginListing } from "./plugin-listing";

/** Beside a verified plugin's name, the app's mark: SurfSense checked that its author runs it. */
export function VerifiedMark({ plugin, className }: { plugin: PluginListing; className?: string }) {
	if (plugin.verification !== "verified") return null;
	return (
		<span
			role="img"
			aria-label="Verified"
			title={`Verified publisher. SurfSense checked that ${plugin.author} runs it.`}
			className="inline-flex shrink-0"
		>
			<CheckmarkBadgeIcon className={cn("size-4 text-muted-foreground", className)} />
		</span>
	);
}
