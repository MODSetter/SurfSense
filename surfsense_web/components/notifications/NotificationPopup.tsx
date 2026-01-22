"use client";

import { formatDistanceToNow } from "date-fns";
import {
	AlertCircle,
	AtSign,
	Bell,
	Cable,
	CheckCheck,
	CheckCircle2,
	FileText,
	Loader2,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { convertRenderedToDisplay } from "@/components/chat-comments/comment-item/comment-item";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import type { Notification, NotificationTypeEnum } from "@/hooks/use-notifications";
import { cn } from "@/lib/utils";

/**
 * Filter configuration for notification types
 */
const NOTIFICATION_FILTERS = {
	new_mention: { label: "Mentions", icon: AtSign },
	connector_indexing: { label: "Connectors", icon: Cable },
	document_processing: { label: "Documents", icon: FileText },
} as const;

/**
 * Get initials from name or email for avatar fallback
 */
function getInitials(name: string | null | undefined, email: string | null | undefined): string {
	if (name) {
		return name
			.split(" ")
			.map((n) => n[0])
			.join("")
			.toUpperCase()
			.slice(0, 2);
	}
	if (email) {
		const localPart = email.split("@")[0];
		return localPart.slice(0, 2).toUpperCase();
	}
	return "U";
}

interface NotificationPopupProps {
	notifications: Notification[];
	unreadCount: number;
	loading: boolean;
	markAsRead: (id: number) => Promise<boolean>;
	markAllAsRead: () => Promise<boolean>;
	onClose?: () => void;
	activeFilter: NotificationTypeEnum | null;
	onFilterChange: (filter: NotificationTypeEnum | null) => void;
}

export function NotificationPopup({
	notifications,
	unreadCount,
	loading,
	markAsRead,
	markAllAsRead,
	onClose,
	activeFilter,
	onFilterChange,
}: NotificationPopupProps) {
	const router = useRouter();

	const handleMarkAllAsRead = async () => {
		await markAllAsRead();
	};

	const handleNotificationClick = async (notification: Notification) => {
		if (!notification.read) {
			await markAsRead(notification.id);
		}

		if (notification.type === "new_mention") {
			const metadata = notification.metadata as {
				thread_id?: number;
				comment_id?: number;
			};
			const searchSpaceId = notification.search_space_id;
			const threadId = metadata?.thread_id;
			const commentId = metadata?.comment_id;

			if (searchSpaceId && threadId) {
				const url = commentId
					? `/dashboard/${searchSpaceId}/new-chat/${threadId}?commentId=${commentId}`
					: `/dashboard/${searchSpaceId}/new-chat/${threadId}`;
				onClose?.();
				router.push(url);
			}
		}
	};

	const formatTime = (dateString: string) => {
		try {
			return formatDistanceToNow(new Date(dateString), { addSuffix: true });
		} catch {
			return "Recently";
		}
	};

	const getStatusIcon = (notification: Notification) => {
		// For mentions, show the author's avatar with initials fallback
		if (notification.type === "new_mention") {
			const metadata = notification.metadata as {
				author_name?: string;
				author_avatar_url?: string | null;
				author_email?: string;
			};
			const authorName = metadata?.author_name;
			const avatarUrl = metadata?.author_avatar_url;
			const authorEmail = metadata?.author_email;

			return (
				<Avatar className="h-6 w-6">
					{avatarUrl && <AvatarImage src={avatarUrl} alt={authorName || "User"} />}
					<AvatarFallback className="text-[10px] bg-primary/10 text-primary">
						{getInitials(authorName, authorEmail)}
					</AvatarFallback>
				</Avatar>
			);
		}

		// For other notification types, show status icons
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
			<div className="flex items-center justify-between px-4 py-3">
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

			{/* Filter Pills */}
			<div className="flex items-center gap-1.5 px-4 py-2 overflow-x-auto">
				{(
					Object.entries(NOTIFICATION_FILTERS) as [
						NotificationTypeEnum,
						(typeof NOTIFICATION_FILTERS)[keyof typeof NOTIFICATION_FILTERS],
					][]
				).map(([key, { label, icon: Icon }]) => {
					const isActive = activeFilter === key;
					return (
						<button
							key={key}
							type="button"
							onClick={() => onFilterChange(key)}
							className={cn(
								"inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-medium transition-colors whitespace-nowrap",
								"border focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1",
								isActive
									? "bg-primary text-primary-foreground border-primary"
									: "bg-transparent text-muted-foreground border-border hover:bg-accent hover:text-accent-foreground"
							)}
						>
							<Icon className="h-3 w-3" />
							{label}
						</button>
					);
				})}
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
									onClick={() => handleNotificationClick(notification)}
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
												{convertRenderedToDisplay(notification.message)}
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
