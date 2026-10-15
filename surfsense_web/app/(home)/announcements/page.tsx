"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect } from "react";
import { HomeBadge } from "@/components/homepage/home/home-badge";
import { sectionSpacing } from "@/components/homepage/home/home-section-spacing";
import { siteText } from "@/components/site/site-text";
import { LinkSquare02Icon, Notification03Icon } from "@/components/ui/icons";
import type { AnnouncementCategory } from "@/contracts/types/announcement.types";
import { type AnnouncementWithState, useAnnouncements } from "@/hooks/use-announcements";
import { formatRelativeDate } from "@/lib/format-date";
import { cn } from "@/lib/utils";

/**
 * Rendered in the site design: listed in `SITE_DESIGN_ROUTES` in
 * `components/site/site-shell.tsx`, so the palette, column, navigation and
 * footer come from the site shell. Laid out like the changelog: a centred
 * badge head, then one announcement per row, ruled off from the next.
 *
 * The card here is page-local rather than a reuse of
 * `components/announcements/AnnouncementCard.tsx`: that component also backs
 * the in-app `AnnouncementsDialog` (the dashboard's "What's New" popover),
 * which stays on its own shadcn styling untouched by this page's redesign.
 */

const categoryConfig: Record<AnnouncementCategory, { label: string }> = {
	feature: { label: "Feature" },
	update: { label: "Update" },
	maintenance: { label: "Maintenance" },
	info: { label: "Info" },
};

function AnnouncementCard({ announcement }: { announcement: AnnouncementWithState }) {
	const config = categoryConfig[announcement.category] ?? categoryConfig.info;

	return (
		<article className="grid gap-6 py-10 md:grid-cols-[11rem_1fr] md:gap-10 md:py-14">
			<div className="flex h-min flex-wrap items-center gap-2 md:sticky md:top-24 md:flex-col md:items-start md:gap-3">
				<span className="rounded-full bg-foreground px-3 py-1 text-xs font-medium text-background">
					{config.label}
				</span>
				{announcement.isImportant && <HomeBadge>Important</HomeBadge>}
				<time className="text-sm text-muted-foreground">
					{formatRelativeDate(announcement.date)}
				</time>
			</div>

			<div className="flex min-w-0 max-w-3xl flex-col">
				{announcement.image && (
					<div className="relative mb-6 aspect-video w-full overflow-hidden rounded-2xl border border-border">
						<Image
							src={announcement.image.src}
							alt={announcement.image.alt}
							fill
							sizes="(max-width: 768px) 100vw, 640px"
							className="object-cover"
						/>
					</div>
				)}
				<h2 className={cn(siteText.h3, "mb-2 text-xl md:text-2xl")}>{announcement.title}</h2>
				<p className={siteText.body}>{announcement.description}</p>
				{announcement.link && (
					<Link
						href={announcement.link.url}
						target={announcement.link.url.startsWith("http") ? "_blank" : undefined}
						className={cn(siteText.forward, "mt-4 self-start")}
					>
						{announcement.link.label}
						<LinkSquare02Icon className="size-3.5" />
					</Link>
				)}
			</div>
		</article>
	);
}

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
	const { announcements, markAllRead } = useAnnouncements({ includeExpired: true });

	// Auto-mark all visible announcements as read when the page is opened
	useEffect(() => {
		markAllRead();
	}, [markAllRead]);

	return (
		<section className={sectionSpacing.foot}>
			<div className={cn("text-center", sectionSpacing.head)}>
				<HomeBadge>Announcements</HomeBadge>
				<h1 className={cn(siteText.display, "mt-4")}>What's New</h1>
				<p className={cn(siteText.lede, "mx-auto mt-6 max-w-xl")}>
					Product updates, features and fixes as they ship.
				</p>
			</div>

			<div className="mt-10 lg:mt-14">
				{announcements.length === 0 ? (
					<EmptyState />
				) : (
					<ol className="m-0 list-none divide-y divide-border border-y border-border p-0">
						{announcements.map((announcement) => (
							<li key={announcement.id}>
								<AnnouncementCard announcement={announcement} />
							</li>
						))}
					</ol>
				)}
			</div>
		</section>
	);
}
