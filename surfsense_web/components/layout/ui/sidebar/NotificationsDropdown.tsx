"use client";

import { useAtom } from "jotai";
import { Bell } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useMemo, useState } from "react";
import { setTargetCommentIdAtom } from "@/atoms/chat/current-thread.atom";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import {
	isCommentReplyMetadata,
	isInsufficientCreditsMetadata,
	isNewMentionMetadata,
} from "@/contracts/types/inbox.types";
import type { InboxItem } from "@/hooks/use-inbox";
import { cn } from "@/lib/utils";

export interface NotificationsDataSource {
	items: InboxItem[];
	unreadCount: number;
	loading: boolean;
	loadingMore?: boolean;
	hasMore?: boolean;
	loadMore?: () => void;
	markAsRead: (id: number) => Promise<boolean>;
	markAllAsRead: () => Promise<boolean>;
}

export interface NotificationsDropdownData {
	totalUnreadCount: number;
	comments: NotificationsDataSource;
	status: NotificationsDataSource;
}

interface NotificationsDropdownProps {
	notifications: NotificationsDropdownData;
	onCloseMobileSidebar?: () => void;
}

type NotificationFilter = "mentions" | "status" | null;

function formatNotificationCount(count: number): string {
	if (count <= 999) {
		return count.toString();
	}
	const thousands = Math.floor(count / 1000);
	return `${thousands}k+`;
}

function formatTime(dateString: string): string {
	try {
		const date = new Date(dateString);
		const now = new Date();
		const diffMs = now.getTime() - date.getTime();
		const diffMins = Math.floor(diffMs / (1000 * 60));
		const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
		const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

		if (diffMins < 1) return "now";
		if (diffMins < 60) return `${diffMins}m ago`;
		if (diffHours < 24) return `${diffHours}h ago`;
		if (diffDays < 7) return `${diffDays}d ago`;
		return `${Math.floor(diffDays / 7)}w ago`;
	} catch {
		return "now";
	}
}

function isCommentNotification(item: InboxItem): boolean {
	return item.type === "new_mention" || item.type === "comment_reply";
}

export function NotificationsDropdown({
	notifications,
	onCloseMobileSidebar,
}: NotificationsDropdownProps) {
	const router = useRouter();
	const [, setTargetCommentId] = useAtom(setTargetCommentIdAtom);
	const [open, setOpen] = useState(false);
	const [activeFilter, setActiveFilter] = useState<NotificationFilter>(null);
	const [markingAsReadId, setMarkingAsReadId] = useState<number | null>(null);
	const [markingAllAsRead, setMarkingAllAsRead] = useState(false);

	const unreadLabel = formatNotificationCount(notifications.totalUnreadCount);
	const visibleUnreadCount =
		activeFilter === "mentions"
			? notifications.comments.unreadCount
			: activeFilter === "status"
				? notifications.status.unreadCount
				: notifications.totalUnreadCount;
	const visibleUnreadLabel = formatNotificationCount(visibleUnreadCount);
	const isLoading =
		activeFilter === "mentions"
			? notifications.comments.loading
			: activeFilter === "status"
				? notifications.status.loading
				: notifications.comments.loading || notifications.status.loading;
	const items = useMemo(() => {
		const sourceItems =
			activeFilter === "mentions"
				? notifications.comments.items
				: activeFilter === "status"
					? notifications.status.items
					: [...notifications.comments.items, ...notifications.status.items];

		return sourceItems
			.toSorted((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
			.slice(0, 8);
	}, [activeFilter, notifications.comments.items, notifications.status.items]);

	const markItemAsRead = useCallback(
		async (item: InboxItem) => {
			if (item.read) return;
			setMarkingAsReadId(item.id);
			try {
				await (isCommentNotification(item)
					? notifications.comments.markAsRead(item.id)
					: notifications.status.markAsRead(item.id));
			} finally {
				setMarkingAsReadId(null);
			}
		},
		[notifications.comments, notifications.status]
	);

	const handleItemClick = useCallback(
		async (item: InboxItem) => {
			await markItemAsRead(item);

			if (item.type === "new_mention" && isNewMentionMetadata(item.metadata)) {
				const threadId = item.metadata.thread_id;
				const commentId = item.metadata.comment_id;
				if (item.workspace_id && threadId) {
					if (commentId) setTargetCommentId(commentId);
					setOpen(false);
					onCloseMobileSidebar?.();
					router.push(
						commentId
							? `/dashboard/${item.workspace_id}/new-chat/${threadId}?commentId=${commentId}`
							: `/dashboard/${item.workspace_id}/new-chat/${threadId}`
					);
				}
				return;
			}

			if (item.type === "comment_reply" && isCommentReplyMetadata(item.metadata)) {
				const threadId = item.metadata.thread_id;
				const replyId = item.metadata.reply_id;
				if (item.workspace_id && threadId) {
					if (replyId) setTargetCommentId(replyId);
					setOpen(false);
					onCloseMobileSidebar?.();
					router.push(
						replyId
							? `/dashboard/${item.workspace_id}/new-chat/${threadId}?commentId=${replyId}`
							: `/dashboard/${item.workspace_id}/new-chat/${threadId}`
					);
				}
				return;
			}

			if (item.type === "insufficient_credits" && isInsufficientCreditsMetadata(item.metadata)) {
				if (item.metadata.action_url) {
					setOpen(false);
					onCloseMobileSidebar?.();
					router.push(item.metadata.action_url);
				}
			}
		},
		[markItemAsRead, onCloseMobileSidebar, router, setTargetCommentId]
	);

	const handleMarkAllAsRead = useCallback(async () => {
		if (visibleUnreadCount === 0 || markingAllAsRead) return;
		setMarkingAllAsRead(true);
		try {
			if (activeFilter === "mentions") {
				await notifications.comments.markAllAsRead();
			} else if (activeFilter === "status") {
				await notifications.status.markAllAsRead();
			} else {
				await Promise.all([
					notifications.comments.markAllAsRead(),
					notifications.status.markAllAsRead(),
				]);
			}
		} finally {
			setMarkingAllAsRead(false);
		}
	}, [activeFilter, markingAllAsRead, notifications, visibleUnreadCount]);

	const handleFilterClick = useCallback((filter: Exclude<NotificationFilter, null>) => {
		setActiveFilter((current) => (current === filter ? null : filter));
	}, []);

	const emptyStateCopy =
		activeFilter === "mentions"
			? {
					title: "No mentions",
					description: "Mentions and replies will appear here.",
				}
			: activeFilter === "status"
				? {
						title: "No status updates",
						description: "Connector and document updates will appear here.",
					}
				: {
						title: "No notifications",
						description: "Mentions, replies, and status updates will appear here.",
					};

	return (
		<Popover open={open} onOpenChange={setOpen}>
			<Tooltip>
				<TooltipTrigger asChild>
					<PopoverTrigger asChild>
						<Button
							type="button"
							variant="ghost"
							size="icon"
							aria-label={
								notifications.totalUnreadCount > 0
									? `Notifications, ${unreadLabel} unread`
									: "Notifications"
							}
							className={cn(
								"relative h-10 w-10 rounded-lg text-muted-foreground hover:bg-accent hover:text-accent-foreground",
								open && "bg-accent text-accent-foreground"
							)}
						>
							<Bell className="h-4 w-4" />
							{notifications.totalUnreadCount > 0 ? (
								<span className="absolute right-1 top-1 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-semibold leading-none text-destructive-foreground">
									{unreadLabel}
								</span>
							) : null}
						</Button>
					</PopoverTrigger>
				</TooltipTrigger>
				<TooltipContent side="right" sideOffset={8}>
					Notifications
				</TooltipContent>
			</Tooltip>
			<PopoverContent
				side="right"
				align="end"
				sideOffset={10}
				className="z-80 flex max-h-[min(520px,calc(100vh-2rem))] w-[360px] flex-col overflow-hidden rounded-xl border bg-popover p-0 text-popover-foreground shadow-lg"
			>
				<div className="flex shrink-0 items-center justify-between gap-3 border-b px-4 py-3">
					<div className="min-w-0">
						<h2 className="text-base font-semibold">Notifications</h2>
						<p className="text-xs text-muted-foreground">
							{visibleUnreadCount > 0 ? `${visibleUnreadLabel} unread` : "You're all caught up"}
						</p>
					</div>
					<Button
						type="button"
						variant="ghost"
						size="sm"
						onClick={handleMarkAllAsRead}
						disabled={visibleUnreadCount === 0 || markingAllAsRead}
						className="h-8 shrink-0 gap-1.5 px-2 text-xs text-muted-foreground hover:text-accent-foreground"
					>
						{markingAllAsRead ? <Spinner size="xs" /> : null}
						Mark all read
					</Button>
				</div>

				<div className="flex shrink-0 items-center gap-2 border-b px-3 py-2">
					<Button
						type="button"
						variant="ghost"
						size="sm"
						aria-pressed={activeFilter === "mentions"}
						onClick={() => handleFilterClick("mentions")}
						className={cn(
							"h-7 rounded-full px-2.5 text-xs text-muted-foreground",
							activeFilter === "mentions" && "bg-accent text-accent-foreground"
						)}
					>
						Mentions
						{notifications.comments.unreadCount > 0 ? (
							<span className="ml-1 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-primary/15 px-1 text-[10px] font-medium text-primary">
								{formatNotificationCount(notifications.comments.unreadCount)}
							</span>
						) : null}
					</Button>
					<Button
						type="button"
						variant="ghost"
						size="sm"
						aria-pressed={activeFilter === "status"}
						onClick={() => handleFilterClick("status")}
						className={cn(
							"h-7 rounded-full px-2.5 text-xs text-muted-foreground",
							activeFilter === "status" && "bg-accent text-accent-foreground"
						)}
					>
						Status
						{notifications.status.unreadCount > 0 ? (
							<span className="ml-1 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-primary/15 px-1 text-[10px] font-medium text-primary">
								{formatNotificationCount(notifications.status.unreadCount)}
							</span>
						) : null}
					</Button>
				</div>

				<div className="min-h-0 flex-1 overflow-y-auto p-2">
					{isLoading ? (
						<div className="space-y-1">
							{[82, 64, 74].map((width) => (
								<div key={width} className="flex h-[72px] items-center rounded-lg px-2 py-2">
									<div className="min-w-0 flex-1 space-y-2">
										<Skeleton className="h-3 rounded" style={{ width: `${width}%` }} />
										<Skeleton className="h-2.5 w-1/2 rounded" />
									</div>
								</div>
							))}
						</div>
					) : items.length > 0 ? (
						<div className="space-y-1">
							{items.map((item) => {
								const isMarkingAsRead = markingAsReadId === item.id;
								return (
									<Button
										key={item.id}
										type="button"
										variant="ghost"
										disabled={isMarkingAsRead}
										onClick={() => handleItemClick(item)}
										className={cn(
											"group h-auto w-full justify-start rounded-lg px-2 py-2 text-left",
											"hover:bg-accent hover:text-accent-foreground",
											!item.read && "bg-accent/40"
										)}
										style={{ contentVisibility: "auto", containIntrinsicSize: "0 72px" }}
									>
										<div className="min-w-0 flex-1">
											<div className="flex min-w-0 items-start gap-2">
												<p
													className={cn(
														"line-clamp-1 flex-1 text-sm font-medium",
														!item.read && "font-semibold"
													)}
												>
													{item.title}
												</p>
												{!item.read ? (
													<span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
												) : null}
											</div>
											<p className="mt-0.5 line-clamp-2 text-xs font-normal text-muted-foreground group-hover:text-accent-foreground/80">
												{item.message}
											</p>
											<p className="mt-1 text-[11px] font-normal text-muted-foreground/70">
												{formatTime(item.created_at)}
											</p>
										</div>
										{isMarkingAsRead ? <Spinner size="xs" className="shrink-0" /> : null}
									</Button>
								);
							})}
						</div>
					) : (
						<div className="flex flex-col items-center justify-center px-6 py-10 text-center">
							<p className="text-sm font-medium">{emptyStateCopy.title}</p>
							<p className="mt-1 text-xs text-muted-foreground">{emptyStateCopy.description}</p>
						</div>
					)}
				</div>
			</PopoverContent>
		</Popover>
	);
}
