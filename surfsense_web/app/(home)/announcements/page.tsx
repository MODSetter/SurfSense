import type { Metadata } from "next";
import { HomeBadge } from "@/components/homepage/home/home-badge";
import { sectionSpacing } from "@/components/homepage/home/home-section-spacing";
import { siteText } from "@/components/site/site-text";
import { Notification03Icon } from "@/components/ui/icons";
import { getPublishedAnnouncementPosts } from "@/lib/announcements/announcements-source";
import { cn } from "@/lib/utils";
import { AnnouncementCard } from "./announcement-card";
import { FeaturedAnnouncement } from "./featured-announcement";
import { MarkAnnouncementsRead } from "./mark-announcements-read";

/**
 * Rendered in the site design: listed in `SITE_DESIGN_ROUTES` in
 * `components/site/site-shell.tsx`, so the palette, column, navigation and
 * footer come from the site shell. Laid out like the blog index: the newest
 * announcement as a wide feature, the rest as cards, each linking to its page.
 *
 * Every published announcement is listed, expired or not and whatever its
 * audience: this is the public archive.
 */

const description = "Latest product updates, feature releases, and news from SurfSense.";

export const metadata: Metadata = {
	title: "What's New | SurfSense",
	description,
	alternates: {
		canonical: "https://www.surfsense.com/announcements",
	},
	openGraph: {
		title: "What's New | SurfSense",
		description,
		url: "https://www.surfsense.com/announcements",
		siteName: "SurfSense",
		locale: "en_US",
		type: "website",
		images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "What's new in SurfSense" }],
	},
	twitter: {
		card: "summary_large_image",
		title: "What's New | SurfSense",
		description,
		creator: "@SurfSenseAI",
		site: "@SurfSenseAI",
	},
};

// Hourly, so a scheduled announcement goes live without a redeploy.
export const revalidate = 3600;

function EmptyState() {
	return (
		<div className="flex flex-col items-center rounded-3xl border border-dashed border-border px-6 py-20 text-center">
			<span className="grid size-12 place-items-center rounded-full bg-secondary">
				<Notification03Icon className="size-5 text-muted-foreground" />
			</span>
			<h2 className={cn(siteText.h3, "mt-5")}>Nothing new yet</h2>
			<p className={cn(siteText.body, "mt-2 max-w-xs")}>
				You're all caught up! New updates will appear here.
			</p>
		</div>
	);
}

export default function AnnouncementsPage() {
	const [lead, ...rest] = getPublishedAnnouncementPosts();

	return (
		<section className={sectionSpacing.foot}>
			<MarkAnnouncementsRead />

			<div className={cn("text-center", sectionSpacing.head)}>
				<HomeBadge>Announcements</HomeBadge>
				<h1 className={cn(siteText.display, "mt-4")}>What's New</h1>
				<p className={cn(siteText.lede, "mx-auto mt-6 max-w-xl")}>
					Product updates, features and fixes as they ship.
				</p>
			</div>

			<div className="mt-10 flex flex-col gap-6 lg:mt-14">
				{lead ? <FeaturedAnnouncement announcement={lead} /> : <EmptyState />}

				{rest.length > 0 && (
					<>
						<h2 className="sr-only">Earlier announcements</h2>
						<ul className="m-0 grid list-none gap-6 p-0 sm:grid-cols-2 lg:grid-cols-3">
							{rest.map((announcement) => (
								<li key={announcement.id}>
									<AnnouncementCard announcement={announcement} />
								</li>
							))}
						</ul>
					</>
				)}
			</div>
		</section>
	);
}
