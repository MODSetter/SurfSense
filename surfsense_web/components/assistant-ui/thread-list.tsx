"use client";

import {
	ArchiveIcon,
	MessageSquareIcon,
	MoreVerticalIcon,
	PlusIcon,
	RotateCcwIcon,
	TrashIcon,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
	createThreadListManager,
	type ThreadListItem,
	type ThreadListState,
} from "@/lib/chat/thread-persistence";
import { cn } from "@/lib/utils";

interface ThreadListProps {
	searchSpaceId: number;
	currentThreadId?: number;
	className?: string;
}

export function ThreadList({ searchSpaceId, currentThreadId, className }: ThreadListProps) {
	const router = useRouter();
	const [state, setState] = useState<ThreadListState>({
		threads: [],
		archivedThreads: [],
		isLoading: true,
		error: null,
	});
	const [showArchived, setShowArchived] = useState(false);

	// Create the thread list manager
	const manager = useCallback(
		() =>
			createThreadListManager({
				searchSpaceId,
				currentThreadId: currentThreadId ?? null,
				onThreadSwitch: (threadId) => {
					router.push(`/dashboard/${searchSpaceId}/new-chat/${threadId}`);
				},
				onNewThread: (threadId) => {
					router.push(`/dashboard/${searchSpaceId}/new-chat/${threadId}`);
				},
			}),
		[searchSpaceId, currentThreadId, router]
	);

	// Load threads on mount and when searchSpaceId changes
	const loadThreads = useCallback(async () => {
		setState((prev) => ({ ...prev, isLoading: true }));
		const newState = await manager().loadThreads();
		setState(newState);
	}, [manager]);

	useEffect(() => {
		loadThreads();
	}, [loadThreads]);

	// Handle new thread creation
	const handleNewThread = async () => {
		await manager().createNewThread();
		await loadThreads();
	};

	// Handle thread actions
	const handleArchive = async (threadId: number) => {
		const success = await manager().archiveThread(threadId);
		if (success) await loadThreads();
	};

	const handleUnarchive = async (threadId: number) => {
		const success = await manager().unarchiveThread(threadId);
		if (success) await loadThreads();
	};

	const handleDelete = async (threadId: number) => {
		const success = await manager().deleteThread(threadId);
		if (success) {
			await loadThreads();
			// If we deleted the current thread, redirect to new chat
			if (threadId === currentThreadId) {
				router.push(`/dashboard/${searchSpaceId}/new-chat`);
			}
		}
	};

	const handleSwitchToThread = (threadId: number) => {
		manager().switchToThread(threadId);
	};

	const displayedThreads = showArchived ? state.archivedThreads : state.threads;

	if (state.isLoading) {
		return (
			<div className={cn("flex h-full flex-col", className)}>
				<div className="flex items-center justify-center p-4">
					<span className="text-muted-foreground text-sm">Loading threads...</span>
				</div>
			</div>
		);
	}

	if (state.error) {
		return (
			<div className={cn("flex h-full flex-col", className)}>
				<div className="p-4 text-center">
					<span className="text-destructive text-sm">{state.error}</span>
					<Button variant="ghost" size="sm" className="mt-2" onClick={loadThreads}>
						Retry
					</Button>
				</div>
			</div>
		);
	}

	return (
		<div className={cn("flex h-full flex-col", className)}>
			{/* Header with New Chat button */}
			<div className="flex items-center justify-between border-b p-3">
				<h2 className="font-semibold text-sm">Conversations</h2>
				<Button
					variant="ghost"
					size="icon"
					className="size-8"
					onClick={handleNewThread}
					title="New Chat"
				>
					<PlusIcon className="size-4" />
				</Button>
			</div>

			{/* Tab toggle for active/archived */}
			<div className="flex border-b">
				<button
					type="button"
					onClick={() => setShowArchived(false)}
					className={cn(
						"flex-1 px-3 py-2 text-center text-xs font-medium transition-colors",
						!showArchived
							? "border-b-2 border-primary text-primary"
							: "text-muted-foreground hover:text-foreground"
					)}
				>
					Active ({state.threads.length})
				</button>
				<button
					type="button"
					onClick={() => setShowArchived(true)}
					className={cn(
						"flex-1 px-3 py-2 text-center text-xs font-medium transition-colors",
						showArchived
							? "border-b-2 border-primary text-primary"
							: "text-muted-foreground hover:text-foreground"
					)}
				>
					Archived ({state.archivedThreads.length})
				</button>
			</div>

			{/* Thread list */}
			<div className="flex-1 overflow-y-auto">
				{displayedThreads.length === 0 ? (
					<div className="flex flex-col items-center justify-center p-6 text-center">
						<MessageSquareIcon className="mb-2 size-8 text-muted-foreground/50" />
						<p className="text-muted-foreground text-sm">
							{showArchived ? "No archived conversations" : "No conversations yet"}
						</p>
						{!showArchived && (
							<Button variant="outline" size="sm" className="mt-3" onClick={handleNewThread}>
								<PlusIcon className="mr-1 size-3" />
								Start a conversation
							</Button>
						)}
					</div>
				) : (
					<div className="space-y-1 p-2">
						{displayedThreads.map((thread) => (
							<ThreadListItemComponent
								key={thread.id}
								thread={thread}
								isActive={thread.id === currentThreadId}
								isArchived={showArchived}
								onClick={() => handleSwitchToThread(thread.id)}
								onArchive={() => handleArchive(thread.id)}
								onUnarchive={() => handleUnarchive(thread.id)}
								onDelete={() => handleDelete(thread.id)}
							/>
						))}
					</div>
				)}
			</div>
		</div>
	);
}

interface ThreadListItemComponentProps {
	thread: ThreadListItem;
	isActive: boolean;
	isArchived: boolean;
	onClick: () => void;
	onArchive: () => void;
	onUnarchive: () => void;
	onDelete: () => void;
}

function ThreadListItemComponent({
	thread,
	isActive,
	isArchived,
	onClick,
	onArchive,
	onUnarchive,
	onDelete,
}: ThreadListItemComponentProps) {
	return (
		<div
			className={cn(
				"group flex items-center gap-2 rounded-lg px-3 py-2 transition-colors cursor-pointer",
				isActive ? "bg-accent text-accent-foreground" : "hover:bg-muted/50"
			)}
			onClick={onClick}
			onKeyDown={(e) => {
				if (e.key === "Enter" || e.key === " ") onClick();
			}}
			role="button"
			tabIndex={0}
		>
			<MessageSquareIcon className="size-4 shrink-0 text-muted-foreground" />
			<div className="flex-1 min-w-0">
				<p className="truncate text-sm font-medium">{thread.title || "New Chat"}</p>
				<p className="truncate text-xs text-muted-foreground">
					{formatRelativeTime(new Date(thread.updatedAt))}
				</p>
			</div>
			<DropdownMenu>
				<DropdownMenuTrigger asChild>
					<Button
						variant="ghost"
						size="icon"
						className="size-7 opacity-0 group-hover:opacity-100 transition-opacity"
						onClick={(e) => e.stopPropagation()}
					>
						<MoreVerticalIcon className="size-4" />
					</Button>
				</DropdownMenuTrigger>
				<DropdownMenuContent align="end">
					{isArchived ? (
						<DropdownMenuItem onClick={onUnarchive}>
							<RotateCcwIcon className="mr-2 size-4" />
							Unarchive
						</DropdownMenuItem>
					) : (
						<DropdownMenuItem onClick={onArchive}>
							<ArchiveIcon className="mr-2 size-4" />
							Archive
						</DropdownMenuItem>
					)}
					<DropdownMenuSeparator />
					<DropdownMenuItem onClick={onDelete} className="text-destructive focus:text-destructive">
						<TrashIcon className="mr-2 size-4" />
						Delete
					</DropdownMenuItem>
				</DropdownMenuContent>
			</DropdownMenu>
		</div>
	);
}

/**
 * Format a date as relative time (e.g., "2 hours ago", "Yesterday")
 */
function formatRelativeTime(date: Date): string {
	const now = new Date();
	const diffMs = now.getTime() - date.getTime();
	const diffSecs = Math.floor(diffMs / 1000);
	const diffMins = Math.floor(diffSecs / 60);
	const diffHours = Math.floor(diffMins / 60);
	const diffDays = Math.floor(diffHours / 24);

	if (diffSecs < 60) return "Just now";
	if (diffMins < 60) return `${diffMins} min${diffMins === 1 ? "" : "s"} ago`;
	if (diffHours < 24) return `${diffHours} hour${diffHours === 1 ? "" : "s"} ago`;
	if (diffDays === 1) return "Yesterday";
	if (diffDays < 7) return `${diffDays} days ago`;

	return date.toLocaleDateString();
}
