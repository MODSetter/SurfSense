import { cn } from "@/components/ui/cn";
import { Alert02Icon, InformationCircleIcon } from "@/components/ui/icons";
import {
	GLOBAL_ANNOUNCEMENT_ENABLED,
	GLOBAL_ANNOUNCEMENT_MESSAGE,
	GLOBAL_ANNOUNCEMENT_TONE,
} from "@/features/announcements/announcement-settings";

// One line, fixed, so the sticky headers below can offset by exactly this.
const HEIGHT = "2.5rem";

const TONES = {
	info: { className: "bg-(--notice) text-white", Icon: InformationCircleIcon },
	warning: {
		className: "border-b border-amber-300 bg-amber-100 text-amber-950",
		Icon: Alert02Icon,
	},
};

/**
 * Site-wide banner at the top of every page, toggled from Vercel with
 * NEXT_PUBLIC_GLOBAL_ANNOUNCEMENT_ENABLED, _MESSAGE and _TONE (`info`, the
 * default, or `warning` for downtime).
 *
 * Sticky, and publishes its height as `--fd-banner-height`: the docs layout
 * offsets its sticky header by that variable, and so does the site nav.
 */
export function GlobalAnnouncement() {
	const message = GLOBAL_ANNOUNCEMENT_MESSAGE.trim();

	if (!GLOBAL_ANNOUNCEMENT_ENABLED || !message) {
		return null;
	}

	const tone = TONES[GLOBAL_ANNOUNCEMENT_TONE];

	return (
		<div
			role="status"
			className={cn(
				"sticky top-0 z-60 flex w-full items-center justify-center px-4 text-sm font-medium",
				tone.className
			)}
			style={{ height: HEIGHT }}
		>
			<style>{`:root { --fd-banner-height: ${HEIGHT}; }`}</style>
			<div className="flex min-w-0 max-w-7xl items-center gap-2">
				<tone.Icon className="size-4 shrink-0" aria-hidden="true" />
				<span className="truncate" title={message}>
					{message}
				</span>
			</div>
		</div>
	);
}
