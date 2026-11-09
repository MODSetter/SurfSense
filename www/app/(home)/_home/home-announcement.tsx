import Link from "next/link";
import { HomeButton } from "@/components/site/home-button";
import { cn } from "@/components/ui/cn";
import { ArrowRightIcon } from "@/components/ui/icons";
import { TOP_ANNOUNCEMENT_ENABLED } from "@/features/announcements/announcement-settings";

/** The one announcement on the homepage; change the copy and link here. */
const ANNOUNCEMENT = {
	tag: "New",
	text: "SurfSense is moving to a local app",
	href: "/announcements/2026-09-18-surfsense-2-desktop-app",
};

/**
 * A pill above the hero headline. It replaced the site-wide banner: one quiet
 * line where a visitor already looks, instead of a strip on every page.
 */
export function HomeAnnouncement() {
	if (!TOP_ANNOUNCEMENT_ENABLED) {
		return null;
	}

	return (
		<div className="mb-8 flex justify-center">
			<HomeButton
				asChild
				variant="bare"
				className={cn(
					"group inline-flex items-center gap-2 rounded-full border border-white/40 bg-card/90 backdrop-blur-sm py-0.75 pr-3.5 pl-0.75 shadow-xs hover:bg-card focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
				)}
			>
				<Link href={ANNOUNCEMENT.href}>
					<span className="rounded-full bg-(--notice) px-3 py-2 text-xs leading-none font-semibold text-primary-foreground">
						{ANNOUNCEMENT.tag}
					</span>
					<span className="text-xs font-medium text-foreground/80">{ANNOUNCEMENT.text}</span>
					<ArrowRightIcon
						aria-hidden="true"
						className="size-3 text-(--notice) transition-transform duration-150 group-hover:translate-x-0.5"
					/>
				</Link>
			</HomeButton>
		</div>
	);
}
