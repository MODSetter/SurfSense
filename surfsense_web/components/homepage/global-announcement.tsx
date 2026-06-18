import { IconInfoCircle } from "@tabler/icons-react";
import { GLOBAL_ANNOUNCEMENT_ENABLED, GLOBAL_ANNOUNCEMENT_MESSAGE } from "@/lib/env-config";

/**
 * Small, site-wide banner for planned downtime / maintenance notices.
 *
 * Controlled entirely through build-time env vars so it can be toggled from
 * Vercel without a code change:
 *   - NEXT_PUBLIC_GLOBAL_ANNOUNCEMENT_ENABLED ("true" to show)
 *   - NEXT_PUBLIC_GLOBAL_ANNOUNCEMENT_MESSAGE (the copy to display)
 */
export function GlobalAnnouncement() {
	const message = GLOBAL_ANNOUNCEMENT_MESSAGE.trim();

	if (!GLOBAL_ANNOUNCEMENT_ENABLED || !message) {
		return null;
	}

	return (
		<div className="fixed bottom-0 left-0 right-0 z-60 w-full bg-amber-500/15 text-amber-900 backdrop-blur-md dark:bg-amber-400/10 dark:text-amber-200 border-t border-amber-500/30">
			<div className="mx-auto flex max-w-7xl items-center justify-center gap-2 px-4 py-2 text-center text-sm font-medium">
				<IconInfoCircle className="h-4 w-4 shrink-0" />
				<span>{message}</span>
			</div>
		</div>
	);
}
