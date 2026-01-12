"use client";

import { Bell, Check, CheckCheck, Loader2, AlertCircle, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
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

	const getStatusBadge = (notification: Notification) => {
		const status = notification.metadata?.status as string | undefined;
		if (!status) return null;

		switch (status) {
			case "in_progress":
				return (
					<Badge variant="secondary" className="text-xs">
						<Loader2 className="h-3 w-3 mr-1 animate-spin" />
						In Progress
					</Badge>
				);
			case "completed":
				return (
					<Badge variant="default" className="text-xs bg-green-600 hover:bg-green-700">
						<CheckCircle2 className="h-3 w-3 mr-1" />
						Completed
					</Badge>
				);
			case "failed":
				return (
					<Badge variant="destructive" className="text-xs">
						<AlertCircle className="h-3 w-3 mr-1" />
						Failed
					</Badge>
				);
			default:
				return null;
		}
	};

	return (
		<div className="flex flex-col">
			{/* Header */}
			<div className="flex items-center justify-between px-4 py-3 border-b">
				<div className="flex items-center gap-2">
					<Bell className="h-4 w-4" />
					<h3 className="font-semibold text-sm">Notifications</h3>
					{unreadCount > 0 && (
						<span className="flex h-5 w-5 items-center justify-center rounded-full bg-destructive text-[10px] font-medium text-destructive-foreground">
							{unreadCount > 99 ? "99+" : unreadCount}
						</span>
					)}
				</div>
				{unreadCount > 0 && (
					<Button
						variant="ghost"
						size="sm"
						onClick={handleMarkAllAsRead}
						className="h-7 text-xs"
					>
						<CheckCheck className="h-3.5 w-3.5 mr-1" />
						Mark all read
					</Button>
				)}
			</div>

			{/* Notifications List */}
			<ScrollArea className="h-[400px]">
				{loading ? (
					<div className="flex items-center justify-center py-8">
						<Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
					</div>
				) : notifications.length === 0 ? (
					<div className="flex flex-col items-center justify-center py-8 px-4 text-center">
						<Bell className="h-8 w-8 text-muted-foreground mb-2" />
						<p className="text-sm text-muted-foreground">No notifications</p>
					</div>
				) : (
					<div className="py-2">
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
									<div className="flex items-start gap-3">
										<div className="flex-1 min-w-0">
											<div className="flex items-start justify-between gap-2 mb-1">
												<p
													className={cn(
														"text-sm font-medium truncate",
														!notification.read && "font-semibold"
													)}
												>
													{notification.title}
												</p>
												<div className="flex items-center gap-2 shrink-0">
													{getStatusBadge(notification)}
													{!notification.read && (
														<div className="h-2 w-2 rounded-full bg-primary mt-1.5" />
													)}
												</div>
											</div>
											<p className="text-xs text-muted-foreground line-clamp-2">
												{notification.message}
											</p>
											<div className="flex items-center justify-between mt-2">
												<span className="text-xs text-muted-foreground">
													{formatTime(notification.created_at)}
												</span>
												{!notification.read && (
													<Button
														variant="ghost"
														size="sm"
														className="h-6 px-2 text-xs"
														onClick={(e) => {
															e.stopPropagation();
															handleMarkAsRead(notification.id);
														}}
													>
														<Check className="h-3 w-3 mr-1" />
														Mark read
													</Button>
												)}
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

