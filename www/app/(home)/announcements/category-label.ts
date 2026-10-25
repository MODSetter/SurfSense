import type { AnnouncementCategory } from "@/features/announcements/announcement.types";

/** The category pill's text on the announcement pages. */
export const categoryLabel: Record<AnnouncementCategory, string> = {
	feature: "Feature",
	update: "Update",
	maintenance: "Maintenance",
	info: "Info",
};
