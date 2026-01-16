"use client";

import { Bell, CheckCheck, Loader2, AlertCircle, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import type { Notification } from "@/hooks/use-notifications";
import { formatDistanceToNow } from "date-fns";
import { cn } from "@/lib/utils";

interface NotificationPopupProps {
	notifications: Notification[];
	unreadCount: number;
	loading: boolean;
	markAsRead: (id: number) => Promise<boolean>;
	markAllAsRead: () => Promise<boolean>;
}

export function NotificationPopup({
	notifications,
	unreadCount,
	loading,
	markAsRead,
	markAllAsRead,
}: NotificationPopupProps) {
	const handleMarkAsRead = async (id: number) => {
		await markAsRead(id);
	};

	const handleMarkAllAsRead = async () => {
		await markAllAsRead();
	};

	const formatTime = (dateString: string) => {
		try {
			return formatDistanceToNow(new Date(dateString), { addSuffix: true });
		} catch {
			return "Recently";
		}
	};

	const getStatusIcon = (notification: Notification) => {
		const status = notification.metadata?.status as string | undefined;

		switch (status) {
			case "in_progress":
				return <Loader2 className="h-4 w-4 text-foreground animate-spin" />;
			case "completed":
				return <CheckCircle2 className="h-4 w-4 text-green-500" />;
			case "failed":
				return <AlertCircle className="h-4 w-4 text-red-500" />;
			default:
				return <Bell className="h-4 w-4 text-muted-foreground" />;
		}
	};

	return (
		<div className="flex flex-col w-80 max-w-[calc(100vw-2rem)]">
			{/* Header */}
			<div className="flex items-center justify-between px-4 py-3 border-b">
				<div className="flex items-center gap-2">
					<h3 className="font-semibold text-sm">Notifications</h3>
				</div>
				{unreadCount > 0 && (
					<Button variant="ghost" size="sm" onClick={handleMarkAllAsRead} className="h-7 text-xs">
						<CheckCheck className="h-3.5 w-3.5 mr-0" />
						Mark all read
					</Button>
				)}
			</div>

			{/* Notifications List */}
			<ScrollArea className="h-[400px]">
				{loading ? (
					<div className="flex items-center justify-center py-8">
						<Loader2 className="h-5 w-5 animate-spin text-foreground" />
					</div>
				) : notifications.length === 0 ? (
					<div className="flex flex-col items-center justify-center py-8 px-4 text-center">
						<Bell className="h-8 w-8 text-muted-foreground mb-2" />
						<p className="text-sm text-muted-foreground">No notifications</p>
					</div>
				) : (
					<div className="pt-0 pb-2">
						{notifications.map((notification, index) => (
							<div key={notification.id}>
								<button
									type="button"
									onClick={() => !notification.read && handleMarkAsRead(notification.id)}
									className={cn(
										"w-full px-4 py-3 text-left hover:bg-accent transition-colors",
										!notification.read && "bg-accent/50"
									)}
								>
									<div className="flex items-start gap-3 overflow-hidden">
										<div className="flex-shrink-0 mt-0.5">{getStatusIcon(notification)}</div>
										<div className="flex-1 min-w-0 overflow-hidden">
											<div className="flex items-start justify-between gap-2 mb-1">
												<p
													className={cn(
														"text-xs font-medium break-all",
														!notification.read && "font-semibold"
													)}
												>
													{notification.title}
												</p>
											</div>
											<p className="text-[11px] text-muted-foreground break-all line-clamp-2">
												{notification.message}
											</p>
											<div className="flex items-center justify-between mt-2">
												<span className="text-[10px] text-muted-foreground">
													{formatTime(notification.created_at)}
												</span>
											</div>
										</div>
									</div>
								</button>
								{index < notifications.length - 1 && <Separator />}
							</div>
						))}
					</div>
				)}
			</ScrollArea>
		</div>
	);
}
