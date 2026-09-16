"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect } from "react";
import { Badge } from "@/components/ui/badge";
import { LinkSquare02Icon, Notification03Icon } from "@/components/ui/icons";
import type { AnnouncementCategory } from "@/contracts/types/announcement.types";
import { type AnnouncementWithState, useAnnouncements } from "@/hooks/use-announcements";
import { formatRelativeDate } from "@/lib/format-date";

/**
 * Rendered in the site design: listed in `SITE_DESIGN_ROUTES` in
 * `components/site/site-shell.tsx`, so the palette, ruled column, navigation
 * and footer all come from `app/(home)/home.css`.
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

function AnnouncementRow({ announcement }: { announcement: AnnouncementWithState }) {
	const config = categoryConfig[announcement.category] ?? categoryConfig.info;

	return (
		<article className="ss-home-cell flex flex-col gap-4 md:flex-row md:gap-8">
			<div className="flex h-min shrink-0 flex-col items-start gap-3 md:w-48 md:sticky md:top-24">
				<time className="ss-home-eyebrow">{formatRelativeDate(announcement.date)}</time>
				<Badge variant="secondary" className="rounded-full px-3 py-1">
					{config.label}
				</Badge>
				{announcement.isImportant && (
					<Badge variant="secondary" className="rounded-full px-3 py-1">
						Important
					</Badge>
				)}
			</div>

			<div className="flex min-w-0 max-w-2xl flex-1 flex-col">
				{announcement.image && (
					<div className="relative mb-4 aspect-video w-full overflow-hidden border border-border">
						<Image
							src={announcement.image.src}
							alt={announcement.image.alt}
							fill
							sizes="(max-width: 768px) 100vw, 640px"
							className="object-cover"
						/>
					</div>
				)}
				<h2 className="ss-home-h3 mb-2 text-xl md:text-2xl">{announcement.title}</h2>
				<p className="ss-home-body">{announcement.description}</p>
				{announcement.link && (
					<Link
						href={announcement.link.url}
						target={announcement.link.url.startsWith("http") ? "_blank" : undefined}
						className="ss-home-forward mt-4 self-start"
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
		<div className="ss-home-pad flex flex-col items-center py-24 text-center">
			<Notification03Icon className="mb-4 size-8 text-muted-foreground" />
			<h3 className="ss-home-h3">Nothing new yet</h3>
			<p className="ss-home-body mt-2 max-w-xs">
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
		<>
			<section className="ss-home-hero ss-home-pad">
				<div className="mx-auto max-w-2xl text-center">
					<h1 className="ss-home-display">What's New</h1>
					<p className="ss-home-lede mx-auto mt-6 max-w-xl">
						Product updates, features and fixes as they ship.
					</p>
				</div>
			</section>

			<section className="ss-home-rule ss-home-rule-plain">
				{announcements.length === 0 ? (
					<EmptyState />
				) : (
					announcements.map((announcement, index) => (
						<div key={announcement.id} className={index > 0 ? "ss-home-rule" : undefined}>
							<AnnouncementRow announcement={announcement} />
						</div>
					))
				)}
			</section>
		</>
	);
}
