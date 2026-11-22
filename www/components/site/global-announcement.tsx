import { cn } from "@/components/ui/cn";
import { Alert02Icon, ArrowRightIcon, InformationCircleIcon } from "@/components/ui/icons";
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

/** The wind-down notice, from `announcement.md`'s banner line. */
const WIND_DOWN_MESSAGE =
	"SurfSense Inc. winds down on Nov 27. SurfSense stays free and open source, maintained by its creator.";
const WIND_DOWN_LINK = { label: "Get 2.4.0", href: "/downloads" };

/**
 * Site-wide banner at the top of every page.
 *
 * By default it carries the wind-down notice, which ships with the code so it needs no
 * Vercel setting. NEXT_PUBLIC_GLOBAL_ANNOUNCEMENT_ENABLED, _MESSAGE and _TONE (`info`, the
 * default, or `warning` for downtime) still replace it with another one-line notice.
 *
 * Sticky, and publishes its height as `--fd-banner-height`: the docs layout
 * offsets its sticky header by that variable, and so does the site nav.
 */
export function GlobalAnnouncement() {
	const custom = GLOBAL_ANNOUNCEMENT_ENABLED ? GLOBAL_ANNOUNCEMENT_MESSAGE.trim() : "";
	const message = custom || WIND_DOWN_MESSAGE;
	const link = custom ? null : WIND_DOWN_LINK;
	const tone = TONES[custom ? GLOBAL_ANNOUNCEMENT_TONE : "info"];

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
				{/* A plain link, not next/link: on `/sunset` its `<base target="_blank">` must
				    send it to the browser rather than navigate inside a legacy app's window. */}
				{link ? (
					<a
						href={link.href}
						className="inline-flex shrink-0 items-center gap-1 font-semibold underline underline-offset-2 hover:no-underline focus-visible:rounded-xs focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
					>
						{link.label}
						<ArrowRightIcon className="size-3.5" aria-hidden="true" />
					</a>
				) : null}
			</div>
		</div>
	);
}
