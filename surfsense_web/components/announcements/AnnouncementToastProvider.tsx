"use client";

import { Megaphone } from "lucide-react";
import { useEffect, useRef } from "react";
import { toast } from "sonner";
import type { Announcement } from "@/contracts/types/announcement.types";
import { announcements } from "@/lib/announcements/announcements-data";
import {
	isAnnouncementToasted,
	markAnnouncementRead,
	markAnnouncementToasted,
} from "@/lib/announcements/announcements-storage";
import { getActiveAnnouncements } from "@/lib/announcements/announcements-utils";
import { isAuthenticated } from "@/lib/auth-utils";

/** Map announcement category to the Sonner toast method */
const categoryToVariant: Record<string, "info" | "warning" | "success"> = {
	update: "info",
	feature: "success",
	maintenance: "warning",
	info: "info",
};

/** Show a single announcement as a toast */
function showAnnouncementToast(announcement: Announcement) {
	const variant = categoryToVariant[announcement.category] ?? "info";

	const options = {
		description: truncateText(announcement.description, 120),
		duration: 12000,
		icon: <Megaphone className="h-4 w-4" />,
		action: announcement.link
			? {
					label: announcement.link.label,
					onClick: () => {
						if (announcement.link?.url.startsWith("http")) {
							window.open(announcement.link.url, "_blank");
						} else if (announcement.link?.url) {
							window.location.href = announcement.link.url;
						}
					},
				}
			: undefined,
		onDismiss: () => {
			markAnnouncementRead(announcement.id);
		},
	};

	toast[variant](announcement.title, options);
	markAnnouncementToasted(announcement.id);
}

/**
 * Global provider that shows important announcements as toast notifications.
 *
 * Place this component once at the root layout level (alongside <Toaster />).
 * On mount, it checks for active, audience-matched, unread important
 * announcements that haven't been shown as toasts yet, and displays them
 * with a short stagger delay.
 */
export function AnnouncementToastProvider() {
	const hasChecked = useRef(false);

	useEffect(() => {
		if (hasChecked.current) return;
		hasChecked.current = true;

		const timer = setTimeout(() => {
			const authed = isAuthenticated();
			const active = getActiveAnnouncements(announcements, authed);
			const importantUntoasted = active.filter(
				(a) => a.isImportant && !isAnnouncementToasted(a.id)
			);

			for (let i = 0; i < importantUntoasted.length; i++) {
				const announcement = importantUntoasted[i];
				setTimeout(() => showAnnouncementToast(announcement), i * 800);
			}
		}, 1500);

		return () => clearTimeout(timer);
	}, []);

	return null;
}

/** Truncate text to a maximum length, adding ellipsis if needed */
function truncateText(text: string, maxLength: number): string {
	if (text.length <= maxLength) return text;
	return `${text.slice(0, maxLength).trimEnd()}...`;
}
