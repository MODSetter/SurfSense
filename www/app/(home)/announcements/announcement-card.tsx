import Image from "next/image";
import Link from "next/link";
import { siteText } from "@/components/site/site-text";
import { cn } from "@/components/ui/cn";
import { DotIcon } from "@/components/ui/icons";
import type { Announcement } from "@/features/announcements/announcement.types";
import { announcementPath } from "@/features/announcements/announcements-utils";
import { categoryLabel } from "./category-label";
import { formatAnnouncementDate } from "./format-announcement-date";

function truncate(text: string, length: number) {
	return text.length > length ? `${text.slice(0, length)}…` : text;
}

/**
 * One earlier announcement in the grid, in the blog's post-card shape.
 *
 * Page-local rather than `components/announcements/AnnouncementCard.tsx`,
 * which backs the in-app "What's New" dialog on its own shadcn styling.
 */
export function AnnouncementCard({ announcement }: { announcement: Announcement }) {
	return (
		<Link
			href={announcementPath(announcement.id)}
			className="flex h-full flex-col overflow-hidden rounded-2xl border border-border bg-card p-2 shadow-xs hover:border-muted-foreground/40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
		>
			<div className="relative aspect-16/10 overflow-hidden rounded-xl bg-muted">
				<Image
					src={announcement.image?.src ?? "/og-image.png"}
					alt=""
					fill
					sizes="(max-width: 639px) 100vw, (max-width: 1023px) 50vw, 33vw"
					className="object-cover"
				/>
			</div>
			<div className="flex flex-1 flex-col px-4 pt-5 pb-4">
				<p className="flex items-center gap-2 text-xs">
					<span className="font-medium whitespace-nowrap text-foreground">
						{categoryLabel[announcement.category]}
					</span>
					<DotIcon aria-hidden="true" className="size-3.5 text-muted-foreground" />
					<time className="whitespace-nowrap text-muted-foreground" dateTime={announcement.date}>
						{formatAnnouncementDate(announcement.date)}
					</time>
				</p>
				<h3 className={cn(siteText.h3, "mt-3")}>{announcement.title}</h3>
				<p className={cn(siteText.body, "mt-2 flex-1 text-sm")}>
					{truncate(announcement.description, 120)}
				</p>
			</div>
		</Link>
	);
}
