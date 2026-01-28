"use client";

import { useAtomValue, useSetAtom } from "jotai";
import { MessageSquare } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { clearTargetCommentIdAtom, targetCommentIdAtom } from "@/atoms/chat/current-thread.atom";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { CommentComposer } from "../comment-composer/comment-composer";
import { CommentActions } from "./comment-actions";
import type { CommentItemProps } from "./types";

function getInitials(name: string | null, email: string): string {
	if (name) {
		return name
			.split(" ")
			.map((part) => part[0])
			.join("")
			.toUpperCase()
			.slice(0, 2);
	}
	return email[0].toUpperCase();
}

function formatTimestamp(dateString: string): string {
	const date = new Date(dateString);
	const now = new Date();
	const diffMs = now.getTime() - date.getTime();
	const diffMins = Math.floor(diffMs / 60000);
	const diffHours = Math.floor(diffMs / 3600000);
	const diffDays = Math.floor(diffMs / 86400000);

	const timeStr = date.toLocaleTimeString("en-US", {
		hour: "numeric",
		minute: "2-digit",
		hour12: true,
	});

	if (diffMins < 1) {
		return "Just now";
	}

	if (diffMins < 60) {
		return `${diffMins}m ago`;
	}

	if (diffHours < 24 && date.getDate() === now.getDate()) {
		return `Today at ${timeStr}`;
	}

	const yesterday = new Date(now);
	yesterday.setDate(yesterday.getDate() - 1);
	if (date.getDate() === yesterday.getDate() && diffDays < 2) {
		return `Yesterday at ${timeStr}`;
	}

	if (diffDays < 7) {
		const dayName = date.toLocaleDateString("en-US", { weekday: "long" });
		return `${dayName} at ${timeStr}`;
	}

	return (
		date.toLocaleDateString("en-US", {
			month: "short",
			day: "numeric",
			year: date.getFullYear() !== now.getFullYear() ? "numeric" : undefined,
		}) + ` at ${timeStr}`
	);
}

export function convertRenderedToDisplay(contentRendered: string): string {
	// Convert @{DisplayName} format to @DisplayName for editing
	return contentRendered.replace(/@\{([^}]+)\}/g, "@$1");
}

function renderMentions(content: string): React.ReactNode {
	// Match @{DisplayName} format from backend
	const mentionPattern = /@\{([^}]+)\}/g;
	const parts: React.ReactNode[] = [];
	let lastIndex = 0;

	for (const match of content.matchAll(mentionPattern)) {
		if (match.index !== undefined && match.index > lastIndex) {
			parts.push(content.slice(lastIndex, match.index));
		}

		// Display as @DisplayName (without curly braces)
		parts.push(
			<span key={match.index} className="rounded bg-primary/10 px-1 font-medium text-primary">
				@{match[1]}
			</span>
		);

		lastIndex = (match.index ?? 0) + match[0].length;
	}

	if (lastIndex < content.length) {
		parts.push(content.slice(lastIndex));
	}

	return parts.length > 0 ? parts : content;
}

export function CommentItem({
	comment,
	onEdit,
	onEditSubmit,
	onEditCancel,
	onDelete,
	onReply,
	isReply = false,
	isEditing = false,
	isSubmitting = false,
	members = [],
	membersLoading = false,
}: CommentItemProps) {
	const commentRef = useRef<HTMLDivElement>(null);
	const [isHighlighted, setIsHighlighted] = useState(false);

	// Target comment navigation
	const targetCommentId = useAtomValue(targetCommentIdAtom);
	const clearTargetCommentId = useSetAtom(clearTargetCommentIdAtom);

	const isTarget = targetCommentId === comment.id;

	// Scroll into view and highlight when this is the target comment
	useEffect(() => {
		if (isTarget && commentRef.current) {
			// Small delay to ensure DOM is ready
			const scrollTimeoutId = setTimeout(() => {
				commentRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
				setIsHighlighted(true);
			}, 150);

			// Remove highlight and clear target after delay
			const clearTimeoutId = setTimeout(() => {
				setIsHighlighted(false);
				clearTargetCommentId();
			}, 3000);

			return () => {
				clearTimeout(scrollTimeoutId);
				clearTimeout(clearTimeoutId);
			};
		}
	}, [isTarget, clearTargetCommentId]);

	const displayName =
		comment.author?.displayName || comment.author?.email.split("@")[0] || "Unknown";
	const email = comment.author?.email || "";

	const handleEditSubmit = (content: string) => {
		onEditSubmit?.(comment.id, content);
	};

	return (
		<div
			ref={commentRef}
			className={cn(
				"group flex gap-3 rounded-lg p-1 -m-1 transition-all duration-300",
				isHighlighted && "ring-2 ring-primary ring-offset-2 ring-offset-background"
			)}
			data-comment-id={comment.id}
		>
			<Avatar className="size-8 shrink-0">
				{comment.author?.avatarUrl && (
					<AvatarImage src={comment.author.avatarUrl} alt={displayName} />
				)}
				<AvatarFallback className="text-xs">
					{getInitials(comment.author?.displayName ?? null, email || "U")}
				</AvatarFallback>
			</Avatar>

			<div className="flex min-w-0 flex-1 flex-col">
				<div className="flex items-center gap-2">
					<span className="truncate text-sm font-medium">{displayName}</span>
					<span className="shrink-0 text-xs text-muted-foreground">
						{formatTimestamp(comment.createdAt)}
					</span>
					{comment.isEdited && (
						<span className="shrink-0 text-xs text-muted-foreground">(edited)</span>
					)}
					{!isEditing && (
						<div className="ml-auto">
							<CommentActions
								canEdit={comment.canEdit}
								canDelete={comment.canDelete}
								onEdit={() => onEdit?.(comment.id)}
								onDelete={() => onDelete?.(comment.id)}
							/>
						</div>
					)}
				</div>

				{isEditing ? (
					<div className="mt-1">
						<CommentComposer
							members={members}
							membersLoading={membersLoading}
							placeholder="Edit your comment..."
							submitLabel="Save"
							isSubmitting={isSubmitting}
							onSubmit={handleEditSubmit}
							onCancel={onEditCancel}
							initialValue={convertRenderedToDisplay(comment.contentRendered)}
							autoFocus
						/>
					</div>
				) : (
					<div className="mt-1 text-sm text-foreground whitespace-pre-wrap wrap-break-word">
						{renderMentions(comment.contentRendered)}
					</div>
				)}

				{!isReply && onReply && !isEditing && (
					<Button
						variant="ghost"
						size="sm"
						className="mt-1 h-7 w-fit px-2 text-xs text-muted-foreground hover:text-foreground"
						onClick={() => onReply(comment.id)}
					>
						<MessageSquare className="mr-1 size-3" />
						Reply
					</Button>
				)}
			</div>
		</div>
	);
}
