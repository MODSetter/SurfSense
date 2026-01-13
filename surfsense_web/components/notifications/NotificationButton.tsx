"use client";

import { Bell } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useNotifications } from "@/hooks/use-notifications";
import { useAtomValue } from "jotai";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import { NotificationPopup } from "./NotificationPopup";
import { cn } from "@/lib/utils";

export function NotificationButton() {
	const { data: user } = useAtomValue(currentUserAtom);
	const userId = user?.id ? String(user.id) : null;
	const { notifications, unreadCount, loading, markAsRead, markAllAsRead } =
		useNotifications(userId);

	return (
		<Popover>
			<Tooltip>
				<TooltipTrigger asChild>
					<PopoverTrigger asChild>
						<Button variant="outline" size="icon" className="h-8 w-8 relative">
							<Bell className="h-4 w-4" />
							{unreadCount > 0 && (
								<span
									className={cn(
										"absolute -top-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full bg-destructive text-[10px] font-medium text-destructive-foreground",
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
				/>
			</PopoverContent>
		</Popover>
	);
}
