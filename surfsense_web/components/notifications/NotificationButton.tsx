"use client";

import { useAtomValue } from "jotai";
import { Bell } from "lucide-react";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useNotifications, type NotificationTypeEnum } from "@/hooks/use-notifications";
import { cn } from "@/lib/utils";
import { NotificationPopup } from "./NotificationPopup";

const NOTIFICATION_FILTER_STORAGE_KEY = "surfsense_notification_filter";

export function NotificationButton() {
	const [open, setOpen] = useState(false);
	const { data: user } = useAtomValue(currentUserAtom);
	const params = useParams();

	// Filter state - null means show all, otherwise filter by type
	const [activeFilter, setActiveFilter] = useState<NotificationTypeEnum | null>(null);

	// Load filter from localStorage on mount
	useEffect(() => {
		try {
			const stored = localStorage.getItem(NOTIFICATION_FILTER_STORAGE_KEY);
			if (stored) {
				const parsed = JSON.parse(stored);
				if (
					parsed === null ||
					["new_mention", "connector_indexing", "document_processing"].includes(parsed)
				) {
					setActiveFilter(parsed);
				}
			}
		} catch {
			// Ignore localStorage errors
		}
	}, []);

	// Handle filter toggle - clicking same pill again shows all
	const handleFilterChange = useCallback((filter: NotificationTypeEnum | null) => {
		setActiveFilter((current) => {
			const newFilter = current === filter ? null : filter;
			try {
				localStorage.setItem(NOTIFICATION_FILTER_STORAGE_KEY, JSON.stringify(newFilter));
			} catch {
				// Ignore localStorage errors
			}
			return newFilter;
		});
	}, []);

	const userId = user?.id ? String(user.id) : null;
	// Get searchSpaceId from URL params - the component is rendered within /dashboard/[search_space_id]/
	const searchSpaceId = params?.search_space_id ? Number(params.search_space_id) : null;

	const { notifications, unreadCount, loading, markAsRead, markAllAsRead } = useNotifications(
		userId,
		searchSpaceId,
		activeFilter
	);

	return (
		<Popover open={open} onOpenChange={setOpen}>
			<Tooltip>
				<TooltipTrigger asChild>
					<PopoverTrigger asChild>
						<Button variant="outline" size="icon" className="h-8 w-8 relative border-0">
							<Bell className="h-4 w-4" />
							{unreadCount > 0 && (
								<span
									className={cn(
										"absolute -top-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full bg-black text-[10px] font-medium text-white dark:bg-zinc-800 dark:text-zinc-50",
										unreadCount > 9 && "px-1"
									)}
								>
									{unreadCount > 99 ? "99+" : unreadCount}
								</span>
							)}
							<span className="sr-only">Notifications</span>
						</Button>
					</PopoverTrigger>
				</TooltipTrigger>
				<TooltipContent>Notifications</TooltipContent>
			</Tooltip>
			<PopoverContent align="end" className="w-80 p-0">
				<NotificationPopup
					notifications={notifications}
					unreadCount={unreadCount}
					loading={loading}
					markAsRead={markAsRead}
					markAllAsRead={markAllAsRead}
					onClose={() => setOpen(false)}
					activeFilter={activeFilter}
					onFilterChange={handleFilterChange}
				/>
			</PopoverContent>
		</Popover>
	);
}
