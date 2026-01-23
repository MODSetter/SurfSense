"use client";

import { useAtom } from "jotai";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { cn } from "@/lib/utils";
import { CommentComposer } from "../comment-composer/comment-composer";
import { CommentThread } from "../comment-thread/comment-thread";
import type { CommentPanelProps } from "./types";

function getInitials(name: string | null | undefined, email: string): string {
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

export function CommentPanel({
	threads,
	members,
	membersLoading = false,
	isLoading = false,
	onCreateComment,
	onCreateReply,
	onEditComment,
	onDeleteComment,
	isSubmitting = false,
	maxHeight,
	variant = "desktop",
}: CommentPanelProps) {
	const [{ data: currentUser }] = useAtom(currentUserAtom);

	const handleCommentSubmit = (content: string) => {
		onCreateComment(content);
	};

	const isMobile = variant === "mobile";

	if (isLoading) {
		return (
			<div
				className={cn(
					"flex min-h-[120px] items-center justify-center p-4",
					!isMobile && "w-96 rounded-lg border bg-card"
				)}
			>
				<div className="flex items-center gap-2 text-sm text-muted-foreground">
					<div className="size-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
					Loading comments...
				</div>
			</div>
		);
	}

	const hasThreads = threads.length > 0;

	// Ensure minimum usable height for empty state + composer button
	const minHeight = 180;
	const effectiveMaxHeight = maxHeight ? Math.max(maxHeight, minHeight) : undefined;

	return (
		<div
			className={cn("flex flex-col", isMobile ? "w-full" : "w-85 rounded-lg border bg-card")}
			style={!isMobile && effectiveMaxHeight ? { maxHeight: effectiveMaxHeight } : undefined}
		>
			{hasThreads && (
				<div className={cn("min-h-0 flex-1 overflow-y-auto scrollbar-thin", isMobile && "pb-24")}>
					<div className="space-y-4 p-4">
						{threads.map((thread) => (
							<CommentThread
								key={thread.id}
								thread={thread}
								members={members}
								membersLoading={membersLoading}
								onCreateReply={onCreateReply}
								onEditComment={onEditComment}
								onDeleteComment={onDeleteComment}
								isSubmitting={isSubmitting}
							/>
						))}
					</div>
				</div>
			)}

			{!hasThreads && currentUser && (
				<div className="flex items-center gap-3 px-4 pt-4 pb-1">
					<Avatar className="size-10">
						<AvatarImage
							src={currentUser.avatar_url ?? undefined}
							alt={currentUser.display_name ?? currentUser.email}
						/>
						<AvatarFallback className="bg-primary/10 text-primary text-sm font-medium">
							{getInitials(currentUser.display_name, currentUser.email)}
						</AvatarFallback>
					</Avatar>
					<div className="flex flex-col">
						<span className="text-sm font-medium">
							{currentUser.display_name ?? currentUser.email}
						</span>
					</div>
				</div>
			)}

			<div className={cn("p-3", isMobile && "fixed bottom-0 left-0 right-0 z-50 bg-card border-t")}>
				<CommentComposer
					members={members}
					membersLoading={membersLoading}
					placeholder="Comment or @mention"
					submitLabel="Comment"
					isSubmitting={isSubmitting}
					onSubmit={handleCommentSubmit}
					autoFocus={!hasThreads}
				/>
			</div>
		</div>
	);
}
