import {
	ActionBarPrimitive,
	AssistantIf,
	ErrorPrimitive,
	MessagePrimitive,
	useAssistantState,
	useMessage,
} from "@assistant-ui/react";
import { useAtomValue } from "jotai";
import { CheckIcon, CopyIcon, DownloadIcon, MessageSquare, RefreshCwIcon } from "lucide-react";
import type { FC } from "react";
import { useContext, useEffect, useMemo, useRef, useState } from "react";
import { commentsEnabledAtom, targetCommentIdAtom } from "@/atoms/chat/current-thread.atom";
import { activeSearchSpaceIdAtom } from "@/atoms/search-spaces/search-space-query.atoms";
import { MarkdownText } from "@/components/assistant-ui/markdown-text";
import {
	ThinkingStepsContext,
	ThinkingStepsDisplay,
} from "@/components/assistant-ui/thinking-steps";
import { ToolFallback } from "@/components/assistant-ui/tool-fallback";
import { TooltipIconButton } from "@/components/assistant-ui/tooltip-icon-button";
import { CommentPanelContainer } from "@/components/chat-comments/comment-panel-container/comment-panel-container";
import { CommentSheet } from "@/components/chat-comments/comment-sheet/comment-sheet";
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
	const [isSheetOpen, setIsSheetOpen] = useState(false);
	const [isInlineOpen, setIsInlineOpen] = useState(false);
	const messageRef = useRef<HTMLDivElement>(null);
	const commentPanelRef = useRef<HTMLDivElement>(null);
	const commentTriggerRef = useRef<HTMLButtonElement>(null);
	const messageId = useAssistantState(({ message }) => message?.id);
	const searchSpaceId = useAtomValue(activeSearchSpaceIdAtom);
	const dbMessageId = parseMessageId(messageId);
	const commentsEnabled = useAtomValue(commentsEnabledAtom);

	// Desktop: >= 1024px (inline expandable), Medium: 768px-1023px (right sheet), Mobile: <768px (bottom sheet)
	const isMediumScreen = useMediaQuery("(min-width: 768px) and (max-width: 1023px)");
	const isDesktop = useMediaQuery("(min-width: 1024px)");

	const isThreadRunning = useAssistantState(({ thread }) => thread.isRunning);
	const isLastMessage = useAssistantState(({ message }) => message?.isLast ?? false);
	const isMessageStreaming = isThreadRunning && isLastMessage;

	const { data: commentsData, isSuccess: commentsLoaded } = useComments({
		messageId: dbMessageId ?? 0,
		enabled: !!dbMessageId,
	});

	const targetCommentId = useAtomValue(targetCommentIdAtom);

	const hasTargetComment = useMemo(() => {
		if (!targetCommentId || !commentsData?.comments) return false;
		return commentsData.comments.some(
			(c) => c.id === targetCommentId || c.replies?.some((r) => r.id === targetCommentId)
		);
	}, [targetCommentId, commentsData]);

	const commentCount = commentsData?.total_count ?? 0;
	const hasComments = commentCount > 0;

	const showCommentTrigger = searchSpaceId && commentsEnabled && !isMessageStreaming && dbMessageId;

	// Close floating panel when clicking outside (but not on portaled popover/dropdown content)
	useEffect(() => {
		if (!isInlineOpen) return;
		const handleClickOutside = (e: MouseEvent) => {
			const target = e.target as Element;
			if (
				commentPanelRef.current?.contains(target) ||
				commentTriggerRef.current?.contains(target) ||
				target.closest?.("[data-radix-popper-content-wrapper]")
			)
				return;
			setIsInlineOpen(false);
		};
		document.addEventListener("mousedown", handleClickOutside);
		return () => document.removeEventListener("mousedown", handleClickOutside);
	}, [isInlineOpen]);

	// Auto-open floating panel on desktop when this message has the target comment
	useEffect(() => {
		if (hasTargetComment && isDesktop && commentsLoaded) {
			setIsInlineOpen(true);
			const timeoutId = setTimeout(() => {
				messageRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
			}, 100);
			return () => clearTimeout(timeoutId);
		}
	}, [hasTargetComment, isDesktop, commentsLoaded]);

	// Auto-open sheet on mobile/tablet when this message has the target comment
	useEffect(() => {
		if (hasTargetComment && !isDesktop && commentsLoaded) {
			setIsSheetOpen(true);
		}
	}, [hasTargetComment, isDesktop, commentsLoaded]);

	const sheetSide = isMediumScreen ? "right" : "bottom";

	return (
		<MessagePrimitive.Root
			ref={messageRef}
			className="aui-assistant-message-root group fade-in slide-in-from-bottom-1 relative mx-auto w-full max-w-(--thread-max-width) animate-in py-3 duration-150"
			data-role="assistant"
		>
			{/* Comment trigger — right-aligned, just below user query on all screen sizes */}
			{showCommentTrigger && (
				<div className="mr-2 mb-1 flex justify-end">
					<button
						ref={isDesktop ? commentTriggerRef : undefined}
						type="button"
						onClick={
							isDesktop ? () => setIsInlineOpen((prev) => !prev) : () => setIsSheetOpen(true)
						}
						className={cn(
							"flex items-center gap-1.5 rounded-full px-3 py-1 text-sm transition-colors",
							isDesktop && isInlineOpen
								? "bg-primary/10 text-primary"
								: hasComments
									? "text-primary hover:bg-primary/10"
									: "text-muted-foreground hover:text-foreground hover:bg-muted"
						)}
					>
						<MessageSquare className={cn("size-3.5", hasComments && "fill-current")} />
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

			{/* Desktop floating comment panel — overlays on top of chat content */}
			{showCommentTrigger && isDesktop && isInlineOpen && dbMessageId && (
				<div
					ref={commentPanelRef}
					className="absolute right-0 top-10 z-30 w-full max-w-md animate-in fade-in slide-in-from-top-2 duration-200"
				>
					<CommentPanelContainer messageId={dbMessageId} isOpen={true} variant="inline" />
				</div>
			)}

			<AssistantMessageInner />

			{/* Comment sheet — bottom for mobile, right for medium screens */}
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
	const { isLast } = useMessage();

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
			{/* Only allow regenerating the last assistant message */}
			{isLast && (
				<ActionBarPrimitive.Reload asChild>
					<TooltipIconButton tooltip="Refresh">
						<RefreshCwIcon />
					</TooltipIconButton>
				</ActionBarPrimitive.Reload>
			)}
		</ActionBarPrimitive.Root>
	);
};
