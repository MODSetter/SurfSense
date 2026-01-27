import {
	ActionBarPrimitive,
	AssistantIf,
	ErrorPrimitive,
	MessagePrimitive,
	useAssistantState,
} from "@assistant-ui/react";
import { useAtom, useAtomValue, useSetAtom } from "jotai";
import { CheckIcon, CopyIcon, DownloadIcon, MessageSquare, RefreshCwIcon } from "lucide-react";
import type { FC } from "react";
import { useContext, useEffect, useMemo, useRef, useState } from "react";
import {
	addingCommentToMessageIdAtom,
	clearTargetCommentIdAtom,
	commentsCollapsedAtom,
	commentsEnabledAtom,
	targetCommentIdAtom,
} from "@/atoms/chat/current-thread.atom";
import { activeSearchSpaceIdAtom } from "@/atoms/search-spaces/search-space-query.atoms";
import { BranchPicker } from "@/components/assistant-ui/branch-picker";
import { MarkdownText } from "@/components/assistant-ui/markdown-text";
import {
	ThinkingStepsContext,
	ThinkingStepsDisplay,
} from "@/components/assistant-ui/thinking-steps";
import { ToolFallback } from "@/components/assistant-ui/tool-fallback";
import { TooltipIconButton } from "@/components/assistant-ui/tooltip-icon-button";
import { CommentPanelContainer } from "@/components/chat-comments/comment-panel-container/comment-panel-container";
import { CommentSheet } from "@/components/chat-comments/comment-sheet/comment-sheet";
import { CommentTrigger } from "@/components/chat-comments/comment-trigger/comment-trigger";
import { useComments } from "@/hooks/use-comments";
import { useMediaQuery } from "@/hooks/use-media-query";
import { cn } from "@/lib/utils";

export const MessageError: FC = () => {
	return (
		<MessagePrimitive.Error>
			<ErrorPrimitive.Root className="aui-message-error-root mt-2 rounded-md border border-destructive bg-destructive/10 p-3 text-destructive text-sm dark:bg-destructive/5 dark:text-red-200">
				<ErrorPrimitive.Message className="aui-message-error-message line-clamp-2" />
			</ErrorPrimitive.Root>
		</MessagePrimitive.Error>
	);
};

/**
 * Custom component to render thinking steps from Context
 */
const ThinkingStepsPart: FC = () => {
	const thinkingStepsMap = useContext(ThinkingStepsContext);

	// Get the current message ID to look up thinking steps
	const messageId = useAssistantState(({ message }) => message?.id);
	const thinkingSteps = thinkingStepsMap.get(messageId) || [];

	// Check if this specific message is currently streaming
	// A message is streaming if: thread is running AND this is the last assistant message
	const isThreadRunning = useAssistantState(({ thread }) => thread.isRunning);
	const isLastMessage = useAssistantState(({ message }) => message?.isLast ?? false);
	const isMessageStreaming = isThreadRunning && isLastMessage;

	if (thinkingSteps.length === 0) return null;

	return (
		<div className="mb-3">
			<ThinkingStepsDisplay steps={thinkingSteps} isThreadRunning={isMessageStreaming} />
		</div>
	);
};

const AssistantMessageInner: FC = () => {
	return (
		<>
			{/* Render thinking steps from message content - this ensures proper scroll tracking */}
			<ThinkingStepsPart />

			<div className="aui-assistant-message-content wrap-break-word px-2 text-foreground leading-relaxed">
				<MessagePrimitive.Parts
					components={{
						Text: MarkdownText,
						tools: { Fallback: ToolFallback },
					}}
				/>
				<MessageError />
			</div>

			<div className="aui-assistant-message-footer mt-1 mb-5 ml-2 flex">
				<BranchPicker />
				<AssistantActionBar />
			</div>
		</>
	);
};

function parseMessageId(assistantUiMessageId: string | undefined): number | null {
	if (!assistantUiMessageId) return null;
	const match = assistantUiMessageId.match(/^msg-(\d+)$/);
	return match ? Number.parseInt(match[1], 10) : null;
}

export const AssistantMessage: FC = () => {
	const [messageHeight, setMessageHeight] = useState<number | undefined>(undefined);
	const [isSheetOpen, setIsSheetOpen] = useState(false);
	const messageRef = useRef<HTMLDivElement>(null);
	const messageId = useAssistantState(({ message }) => message?.id);
	const searchSpaceId = useAtomValue(activeSearchSpaceIdAtom);
	const dbMessageId = parseMessageId(messageId);
	const commentsEnabled = useAtomValue(commentsEnabledAtom);
	const commentsCollapsed = useAtomValue(commentsCollapsedAtom);
	const [addingCommentToMessageId, setAddingCommentToMessageId] = useAtom(
		addingCommentToMessageIdAtom
	);

	// Screen size detection for responsive comment UI
	// Mobile: < 768px (bottom sheet), Medium: 768px - 1024px (right sheet), Desktop: >= 1024px (inline panel)
	const isMediumScreen = useMediaQuery("(min-width: 768px) and (max-width: 1023px)");
	const isDesktop = useMediaQuery("(min-width: 1024px)");

	const isThreadRunning = useAssistantState(({ thread }) => thread.isRunning);
	const isLastMessage = useAssistantState(({ message }) => message?.isLast ?? false);
	const isMessageStreaming = isThreadRunning && isLastMessage;

	const { data: commentsData, isSuccess: commentsLoaded } = useComments({
		messageId: dbMessageId ?? 0,
		enabled: !!dbMessageId,
	});

	// Target comment navigation - read target from global atom
	const targetCommentId = useAtomValue(targetCommentIdAtom);
	const clearTargetCommentId = useSetAtom(clearTargetCommentIdAtom);

	// Check if target comment belongs to this message (including replies)
	const hasTargetComment = useMemo(() => {
		if (!targetCommentId || !commentsData?.comments) return false;
		return commentsData.comments.some(
			(c) => c.id === targetCommentId || c.replies?.some((r) => r.id === targetCommentId)
		);
	}, [targetCommentId, commentsData]);

	const commentCount = commentsData?.total_count ?? 0;
	const hasComments = commentCount > 0;
	const isAddingComment = dbMessageId !== null && addingCommentToMessageId === dbMessageId;
	const showCommentPanel = hasComments || isAddingComment;

	const handleToggleAddComment = () => {
		if (!dbMessageId) return;
		setAddingCommentToMessageId(isAddingComment ? null : dbMessageId);
	};

	const handleCommentTriggerClick = () => {
		setIsSheetOpen(true);
	};

	useEffect(() => {
		if (!messageRef.current) return;
		const el = messageRef.current;
		const update = () => setMessageHeight(el.offsetHeight);
		update();
		const observer = new ResizeObserver(update);
		observer.observe(el);
		return () => observer.disconnect();
	}, []);

	// Auto-open sheet on mobile/tablet when this message has the target comment
	useEffect(() => {
		if (hasTargetComment && !isDesktop && commentsLoaded) {
			setIsSheetOpen(true);
		}
	}, [hasTargetComment, isDesktop, commentsLoaded]);

	// Scroll message into view when it contains target comment (desktop)
	useEffect(() => {
		if (hasTargetComment && isDesktop && commentsLoaded && messageRef.current) {
			// Small delay to ensure DOM is ready after comments render
			const timeoutId = setTimeout(() => {
				messageRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
			}, 100);
			return () => clearTimeout(timeoutId);
		}
	}, [hasTargetComment, isDesktop, commentsLoaded]);

	const showCommentTrigger = searchSpaceId && commentsEnabled && !isMessageStreaming && dbMessageId;

	// Determine sheet side based on screen size
	const sheetSide = isMediumScreen ? "right" : "bottom";

	return (
		<MessagePrimitive.Root
			ref={messageRef}
			className="aui-assistant-message-root group fade-in slide-in-from-bottom-1 relative mx-auto w-full max-w-(--thread-max-width) animate-in py-3 duration-150"
			data-role="assistant"
		>
			<AssistantMessageInner />

			{/* Desktop comment panel - only on lg screens and above, hidden when collapsed */}
			{searchSpaceId && commentsEnabled && !isMessageStreaming && !commentsCollapsed && (
				<div className="absolute left-full top-0 ml-4 hidden lg:block w-72">
					<div
						className={`sticky top-3 ${showCommentPanel ? "opacity-100" : "opacity-0 group-hover:opacity-100"} transition-opacity`}
					>
						{!hasComments && (
							<CommentTrigger
								commentCount={0}
								isOpen={isAddingComment}
								onClick={handleToggleAddComment}
								disabled={!dbMessageId}
							/>
						)}

						{showCommentPanel && dbMessageId && (
							<div
								className={
									hasComments ? "" : "mt-2 animate-in fade-in slide-in-from-top-2 duration-200"
								}
							>
								<CommentPanelContainer
									messageId={dbMessageId}
									isOpen={true}
									maxHeight={messageHeight}
								/>
							</div>
						)}
					</div>
				</div>
			)}

			{/* Mobile & Medium screen comment trigger - shown below lg breakpoint */}
			{showCommentTrigger && !isDesktop && (
				<div className="ml-2 mt-1 flex justify-start">
					<button
						type="button"
						onClick={handleCommentTriggerClick}
						className={cn(
							"flex items-center gap-2 rounded-full px-3 py-1.5 text-sm transition-colors",
							hasComments
								? "border border-primary/50 bg-primary/5 text-primary hover:bg-primary/10"
								: "text-muted-foreground hover:bg-muted hover:text-foreground"
						)}
					>
						<MessageSquare className={cn("size-4", hasComments && "fill-current")} />
						{hasComments ? (
							<span>
								{commentCount} {commentCount === 1 ? "comment" : "comments"}
							</span>
						) : (
							<span>Add comment</span>
						)}
					</button>
				</div>
			)}

			{/* Comment sheet - bottom for mobile, right for medium screens */}
			{showCommentTrigger && !isDesktop && (
				<CommentSheet
					messageId={dbMessageId}
					isOpen={isSheetOpen}
					onOpenChange={setIsSheetOpen}
					commentCount={commentCount}
					side={sheetSide}
				/>
			)}
		</MessagePrimitive.Root>
	);
};

const AssistantActionBar: FC = () => {
	return (
		<ActionBarPrimitive.Root
			hideWhenRunning
			autohide="not-last"
			autohideFloat="single-branch"
			className="aui-assistant-action-bar-root -ml-1 col-start-3 row-start-2 flex gap-1 text-muted-foreground md:data-floating:absolute md:data-floating:rounded-md md:data-floating:border md:data-floating:bg-background md:data-floating:p-1 md:data-floating:shadow-sm [&>button]:opacity-100 md:[&>button]:opacity-[var(--aui-button-opacity,1)]"
		>
			<ActionBarPrimitive.Copy asChild>
				<TooltipIconButton tooltip="Copy">
					<AssistantIf condition={({ message }) => message.isCopied}>
						<CheckIcon />
					</AssistantIf>
					<AssistantIf condition={({ message }) => !message.isCopied}>
						<CopyIcon />
					</AssistantIf>
				</TooltipIconButton>
			</ActionBarPrimitive.Copy>
			<ActionBarPrimitive.ExportMarkdown asChild>
				<TooltipIconButton tooltip="Export as Markdown">
					<DownloadIcon />
				</TooltipIconButton>
			</ActionBarPrimitive.ExportMarkdown>
			<ActionBarPrimitive.Reload asChild>
				<TooltipIconButton tooltip="Refresh">
					<RefreshCwIcon />
				</TooltipIconButton>
			</ActionBarPrimitive.Reload>
		</ActionBarPrimitive.Root>
	);
};
