import {
	ActionBarPrimitive,
	AuiIf,
	ErrorPrimitive,
	MessagePrimitive,
	useAui,
	useAuiState,
} from "@assistant-ui/react";
import { useAtomValue } from "jotai";
import {
	CheckIcon,
	ClipboardPaste,
	CopyIcon,
	DownloadIcon,
	ExternalLink,
	Globe,
	MessageSquare,
	RefreshCwIcon,
} from "lucide-react";
import type { FC } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import { commentsEnabledAtom, targetCommentIdAtom } from "@/atoms/chat/current-thread.atom";
import { activeSearchSpaceIdAtom } from "@/atoms/search-spaces/search-space-query.atoms";
import {
	CitationMetadataProvider,
	useAllCitationMetadata,
} from "@/components/assistant-ui/citation-metadata-context";
import { MarkdownText } from "@/components/assistant-ui/markdown-text";
import { ToolFallback } from "@/components/assistant-ui/tool-fallback";
import { TooltipIconButton } from "@/components/assistant-ui/tooltip-icon-button";
import { CommentPanelContainer } from "@/components/chat-comments/comment-panel-container/comment-panel-container";
import { CommentSheet } from "@/components/chat-comments/comment-sheet/comment-sheet";
import type { SerializableCitation } from "@/components/tool-ui/citation";
import {
	CreateConfluencePageToolUI,
	DeleteConfluencePageToolUI,
	UpdateConfluencePageToolUI,
} from "@/components/tool-ui/confluence";
import { GenerateImageToolUI } from "@/components/tool-ui/generate-image";
import { GeneratePodcastToolUI } from "@/components/tool-ui/generate-podcast";
import { GenerateReportToolUI } from "@/components/tool-ui/generate-report";
import {
	CreateGmailDraftToolUI,
	SendGmailEmailToolUI,
	TrashGmailEmailToolUI,
	UpdateGmailDraftToolUI,
} from "@/components/tool-ui/gmail";
import {
	CreateCalendarEventToolUI,
	DeleteCalendarEventToolUI,
	UpdateCalendarEventToolUI,
} from "@/components/tool-ui/google-calendar";
import {
	CreateGoogleDriveFileToolUI,
	DeleteGoogleDriveFileToolUI,
} from "@/components/tool-ui/google-drive";
import {
	CreateJiraIssueToolUI,
	DeleteJiraIssueToolUI,
	UpdateJiraIssueToolUI,
} from "@/components/tool-ui/jira";
import {
	CreateLinearIssueToolUI,
	DeleteLinearIssueToolUI,
	UpdateLinearIssueToolUI,
} from "@/components/tool-ui/linear";
import {
	CreateNotionPageToolUI,
	DeleteNotionPageToolUI,
	UpdateNotionPageToolUI,
} from "@/components/tool-ui/notion";
import { CreateOneDriveFileToolUI, DeleteOneDriveFileToolUI } from "@/components/tool-ui/onedrive";
import { SandboxExecuteToolUI } from "@/components/tool-ui/sandbox-execute";
import {
	openSafeNavigationHref,
	resolveSafeNavigationHref,
} from "@/components/tool-ui/shared/media";
import { RecallMemoryToolUI, SaveMemoryToolUI } from "@/components/tool-ui/user-memory";
import { GenerateVideoPresentationToolUI } from "@/components/tool-ui/video-presentation";
import { Drawer, DrawerContent, DrawerHandle, DrawerHeader, DrawerTitle } from "@/components/ui/drawer";
import { useComments } from "@/hooks/use-comments";
import { useMediaQuery } from "@/hooks/use-media-query";
import { cn } from "@/lib/utils";

function extractDomain(url: string): string | undefined {
	try {
		return new URL(url).hostname.replace(/^www\./, "");
	} catch {
		return undefined;
	}
}

function useCitationsFromMetadata(): SerializableCitation[] {
	const allCitations = useAllCitationMetadata();
	return useMemo(() => {
		const result: SerializableCitation[] = [];
		for (const [url, meta] of allCitations) {
			const domain = extractDomain(url);
			result.push({
				id: `url-cite-${url}`,
				href: url,
				title: meta.title,
				snippet: meta.snippet,
				domain,
				favicon: domain ? `https://www.google.com/s2/favicons?domain=${domain}&sz=32` : undefined,
				type: "webpage",
			});
		}
		return result;
	}, [allCitations]);
}

const MobileCitationDrawer: FC = () => {
	const [open, setOpen] = useState(false);
	const citations = useCitationsFromMetadata();

	if (citations.length === 0) return null;

	const maxIcons = 4;
	const visible = citations.slice(0, maxIcons);
	const remainingCount = Math.max(0, citations.length - maxIcons);

	const handleNavigate = (citation: SerializableCitation) => {
		const href = resolveSafeNavigationHref(citation.href);
		if (href) openSafeNavigationHref(href);
	};

	return (
		<>
			<button
				type="button"
				onClick={() => setOpen(true)}
				className={cn(
					"isolate inline-flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2",
					"bg-muted/40 outline-none",
					"transition-colors duration-150",
					"hover:bg-muted/70",
					"focus-visible:ring-ring focus-visible:ring-2"
				)}
			>
				<div className="flex items-center">
					{visible.map((citation, index) => (
						<div
							key={citation.id}
							className={cn(
								"border-border bg-background dark:border-foreground/20 relative flex size-6 items-center justify-center rounded-full border shadow-xs",
								index > 0 && "-ml-2"
							)}
							style={{ zIndex: maxIcons - index }}
						>
							{citation.favicon ? (
								// biome-ignore lint/performance/noImgElement: external favicon from arbitrary domain
								<img
									src={citation.favicon}
									alt=""
									aria-hidden="true"
									width={18}
									height={18}
									className="size-4.5 rounded-full object-cover"
								/>
							) : (
								<Globe className="text-muted-foreground size-3" aria-hidden="true" />
							)}
						</div>
					))}
					{remainingCount > 0 && (
						<div
							className="border-border bg-background dark:border-foreground/20 relative -ml-2 flex size-6 items-center justify-center rounded-full border shadow-xs"
							style={{ zIndex: 0 }}
						>
							<span className="text-muted-foreground text-[10px] font-medium tracking-tight">
								•••
							</span>
						</div>
					)}
				</div>
				<span className="text-muted-foreground text-sm tabular-nums">
					{citations.length} source{citations.length !== 1 && "s"}
				</span>
			</button>

			<Drawer open={open} onOpenChange={setOpen}>
				<DrawerContent className="max-h-[85vh] flex flex-col">
					<DrawerHandle />
					<DrawerHeader className="text-left">
						<DrawerTitle className="text-base font-semibold">Sources</DrawerTitle>
					</DrawerHeader>
					<div className="overflow-y-auto flex-1 min-h-0 px-1 pb-6">
						{citations.map((citation) => (
							<button
								key={citation.id}
								type="button"
								onClick={() => handleNavigate(citation)}
								className="group flex w-full items-center gap-2.5 rounded-md px-3 py-2.5 text-left transition-colors hover:bg-muted focus-visible:bg-muted focus-visible:outline-none"
							>
								{citation.favicon ? (
									// biome-ignore lint/performance/noImgElement: external favicon from arbitrary domain
									<img
										src={citation.favicon}
										alt=""
										aria-hidden="true"
										width={16}
										height={16}
										className="bg-muted size-4 shrink-0 rounded object-cover"
									/>
								) : (
									<Globe className="text-muted-foreground size-4 shrink-0" aria-hidden="true" />
								)}
								<div className="min-w-0 flex-1">
									<p className="truncate text-sm font-medium group-hover:underline group-hover:underline-offset-2">
										{citation.title}
									</p>
									<p className="text-muted-foreground truncate text-xs">{citation.domain}</p>
								</div>
								<ExternalLink className="text-muted-foreground size-3.5 shrink-0 opacity-0 transition-opacity group-hover:opacity-100" />
							</button>
						))}
					</div>
				</DrawerContent>
			</Drawer>
		</>
	);
};

export const MessageError: FC = () => {
	return (
		<MessagePrimitive.Error>
			<ErrorPrimitive.Root className="aui-message-error-root mt-2 rounded-md border border-destructive bg-destructive/10 p-3 text-destructive text-sm dark:bg-destructive/5 dark:text-red-200">
				<ErrorPrimitive.Message className="aui-message-error-message line-clamp-2" />
			</ErrorPrimitive.Root>
		</MessagePrimitive.Error>
	);
};

const AssistantMessageInner: FC = () => {
	const isMobile = !useMediaQuery("(min-width: 768px)");

	return (
		<CitationMetadataProvider>
			<div className="aui-assistant-message-content wrap-break-word px-2 text-foreground leading-relaxed">
				<MessagePrimitive.Parts
					components={{
						Text: MarkdownText,
						tools: {
							by_name: {
								generate_report: GenerateReportToolUI,
								generate_podcast: GeneratePodcastToolUI,
								generate_video_presentation: GenerateVideoPresentationToolUI,
								display_image: GenerateImageToolUI,
								generate_image: GenerateImageToolUI,
								save_memory: SaveMemoryToolUI,
								recall_memory: RecallMemoryToolUI,
								execute: SandboxExecuteToolUI,
								create_notion_page: CreateNotionPageToolUI,
								update_notion_page: UpdateNotionPageToolUI,
								delete_notion_page: DeleteNotionPageToolUI,
								create_linear_issue: CreateLinearIssueToolUI,
								update_linear_issue: UpdateLinearIssueToolUI,
								delete_linear_issue: DeleteLinearIssueToolUI,
								create_google_drive_file: CreateGoogleDriveFileToolUI,
								delete_google_drive_file: DeleteGoogleDriveFileToolUI,
								create_onedrive_file: CreateOneDriveFileToolUI,
								delete_onedrive_file: DeleteOneDriveFileToolUI,
								create_calendar_event: CreateCalendarEventToolUI,
								update_calendar_event: UpdateCalendarEventToolUI,
								delete_calendar_event: DeleteCalendarEventToolUI,
								create_gmail_draft: CreateGmailDraftToolUI,
								update_gmail_draft: UpdateGmailDraftToolUI,
								send_gmail_email: SendGmailEmailToolUI,
								trash_gmail_email: TrashGmailEmailToolUI,
								create_jira_issue: CreateJiraIssueToolUI,
								update_jira_issue: UpdateJiraIssueToolUI,
								delete_jira_issue: DeleteJiraIssueToolUI,
								create_confluence_page: CreateConfluencePageToolUI,
								update_confluence_page: UpdateConfluencePageToolUI,
								delete_confluence_page: DeleteConfluencePageToolUI,
								web_search: () => null,
								link_preview: () => null,
								multi_link_preview: () => null,
								scrape_webpage: () => null,
							},
							Fallback: ToolFallback,
						},
					}}
				/>
				<MessageError />
			</div>

			{isMobile && (
				<div className="ml-2 mt-2">
					<MobileCitationDrawer />
				</div>
			)}

			<div className="aui-assistant-message-footer mt-1 mb-5 ml-2 flex">
				<AssistantActionBar />
			</div>
		</CitationMetadataProvider>
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
	const messageId = useAuiState(({ message }) => message?.id);
	const searchSpaceId = useAtomValue(activeSearchSpaceIdAtom);
	const dbMessageId = parseMessageId(messageId);
	const commentsEnabled = useAtomValue(commentsEnabledAtom);

	// Desktop: >= 1024px (inline expandable), Medium: 768px-1023px (right sheet), Mobile: <768px (bottom sheet)
	const isMediumScreen = useMediaQuery("(min-width: 768px) and (max-width: 1023px)");
	const isDesktop = useMediaQuery("(min-width: 1024px)");

	const isThreadRunning = useAuiState(({ thread }) => thread.isRunning);
	const isLastMessage = useAuiState(({ message }) => message?.isLast ?? false);
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
	const isLast = useAuiState((s) => s.message.isLast);
	const aui = useAui();
	const [quickAskMode, setQuickAskMode] = useState("");

	useEffect(() => {
		if (!isLast || !window.electronAPI?.getQuickAskMode) return;
		window.electronAPI.getQuickAskMode().then((mode) => {
			if (mode) setQuickAskMode(mode);
		});
	}, [isLast]);

	const isTransform = isLast && !!window.electronAPI?.replaceText && quickAskMode === "transform";

	return (
		<ActionBarPrimitive.Root
			hideWhenRunning
			autohide="not-last"
			autohideFloat="single-branch"
			className="aui-assistant-action-bar-root -ml-1 col-start-3 row-start-2 flex gap-1 text-muted-foreground md:data-floating:absolute md:data-floating:rounded-md md:data-floating:p-1 [&>button]:opacity-100 md:[&>button]:opacity-[var(--aui-button-opacity,1)]"
		>
			<ActionBarPrimitive.Copy asChild>
				<TooltipIconButton tooltip="Copy">
					<AuiIf condition={({ message }) => message.isCopied}>
						<CheckIcon />
					</AuiIf>
					<AuiIf condition={({ message }) => !message.isCopied}>
						<CopyIcon />
					</AuiIf>
				</TooltipIconButton>
			</ActionBarPrimitive.Copy>
			<ActionBarPrimitive.ExportMarkdown asChild>
				<TooltipIconButton tooltip="Download">
					<DownloadIcon />
				</TooltipIconButton>
			</ActionBarPrimitive.ExportMarkdown>
			{isLast && (
				<ActionBarPrimitive.Reload asChild>
					<TooltipIconButton tooltip="Refresh">
						<RefreshCwIcon />
					</TooltipIconButton>
				</ActionBarPrimitive.Reload>
			)}
			{isTransform && (
				<button
					type="button"
					onClick={() => {
						const text = aui.message().getCopyText();
						window.electronAPI?.replaceText(text);
					}}
					className="ml-1 inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground transition-colors hover:bg-primary/90"
				>
					<ClipboardPaste className="size-3.5" />
					Paste back
				</button>
			)}
		</ActionBarPrimitive.Root>
	);
};
