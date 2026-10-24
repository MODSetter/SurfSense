"use client";

import { useEffect } from "react";
import { useAnnouncements } from "@/hooks/use-announcements";

/**
 * Clears the in-app unread badge for what the page shows: every announcement
 * on the index, or the one `id` on its own page. Renders nothing.
 */
export function MarkAnnouncementsRead({ id }: { id?: string }) {
	const { markRead, markAllRead } = useAnnouncements({ includeExpired: true });

	useEffect(() => {
		if (id) markRead(id);
		else markAllRead();
	}, [id, markRead, markAllRead]);

	return null;
}
