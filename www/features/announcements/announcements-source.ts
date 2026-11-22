import "server-only";
import { loader } from "fumadocs-core/source";
import type { MDXComponents } from "mdx/types";
import type { ComponentType } from "react";
import { announcements as announcementBodies } from "@/.source/server";
import type { Announcement } from "@/features/announcements/announcement.types";
import { announcements } from "@/features/announcements/announcements-data";
import { isAnnouncementPublished } from "@/features/announcements/announcements-utils";

/**
 * Announcement pages: each entry in `announcements-data.ts` joined by its id
 * to `content/announcements/<id>.mdx`.
 *
 * Server-only, as the bodies are compiled MDX. The in-app dialog, spotlight
 * and toasts keep reading the data file alone, synchronously.
 *
 * Audience is ignored: the pages are the public archive, and targeting stays
 * an in-app concern.
 */

const source = loader({
	baseUrl: "/announcements",
	source: announcementBodies.toFumadocsSource(),
});

export interface AnnouncementPost extends Announcement {
	body: ComponentType<{ components?: MDXComponents }>;
}

function withBody(announcement: Announcement): AnnouncementPost | undefined {
	const page = source.getPage([announcement.id]);
	return page ? { ...announcement, body: page.data.body } : undefined;
}

/** Every announcement whose start time has passed and that has a body, newest first. */
export function getPublishedAnnouncementPosts(now = new Date()): AnnouncementPost[] {
	return announcements
		.filter((announcement) => isAnnouncementPublished(announcement, now))
		.map(withBody)
		.filter((post): post is AnnouncementPost => post !== undefined)
		.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
}

/** One published announcement, or undefined for an unknown slug or one still scheduled. */
export function getPublishedAnnouncementPost(
	slug: string,
	now = new Date()
): AnnouncementPost | undefined {
	const announcement = announcements.find((a) => a.id === slug);
	if (!announcement || !isAnnouncementPublished(announcement, now)) return undefined;
	return withBody(announcement);
}
