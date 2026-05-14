import {
	ActionBarMorePrimitive,
	ActionBarPrimitive,
	AuiIf,
	ErrorPrimitive,
	MessagePrimitive,
	type ToolCallMessagePartComponent,
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
	MessageCircleReply,
	MoreHorizontalIcon,
	RefreshCwIcon,
} from "lucide-react";
import dynamic from "next/dynamic";
import type { FC } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import { commentsEnabledAtom, targetCommentIdAtom } from "@/atoms/chat/current-thread.atom";
import {
	globalNewLLMConfigsAtom,
	newLLMConfigsAtom,
} from "@/atoms/new-llm-config/new-llm-config-query.atoms";
import { activeSearchSpaceIdAtom } from "@/atoms/search-spaces/search-space-query.atoms";
import {
	CitationMetadataProvider,
	useAllCitationMetadata,
} from "@/components/assistant-ui/citation-metadata-context";
import { MarkdownText } from "@/components/assistant-ui/markdown-text";
import { ReasoningMessagePart } from "@/components/assistant-ui/reasoning-message-part";
import { RevertTurnButton } from "@/components/assistant-ui/revert-turn-button";
import { useTokenUsage } from "@/components/assistant-ui/token-usage-context";
import { TooltipIconButton } from "@/components/assistant-ui/tooltip-icon-button";
import { CommentPanelContainer } from "@/components/chat-comments/comment-panel-container/comment-panel-container";
import { CommentSheet } from "@/components/chat-comments/comment-sheet/comment-sheet";
import type { SerializableCitation } from "@/components/tool-ui/citation";
import {
	openSafeNavigationHref,
	resolveSafeNavigationHref,
} from "@/components/tool-ui/shared/media";
import { Button } from "@/components/ui/button";
import {
	Drawer,
	DrawerContent,
	DrawerHandle,
	DrawerHeader,
	DrawerTitle,
} from "@/components/ui/drawer";
import { DropdownMenuLabel } from "@/components/ui/dropdown-menu";
import { useComments } from "@/hooks/use-comments";
import { useMediaQuery } from "@/hooks/use-media-query";
import { useElectronAPI } from "@/hooks/use-platform";
import { getProviderIcon } from "@/lib/provider-icons";
import { cn } from "@/lib/utils";

// Captured once at module load — survives client-side navigations that strip the query param.
const IS_QUICK_ASSIST_WINDOW =
	typeof window !== "undefined" &&
	new URLSearchParams(window.location.search).get("quickAssist") === "true";

// Dynamically import tool UI components to avoid loading them in main bundle
const GenerateReportToolUI = dynamic(
	() =>
		import("@/components/tool-ui/generate-report").then((m) => ({
			default: m.GenerateReportToolUI,
		})),
	{ ssr: false }
);
const GenerateResumeToolUI = dynamic(
	() =>
		import("@/components/tool-ui/generate-resume").then((m) => ({
			default: m.GenerateResumeToolUI,
		})),
	{ ssr: false }
);
const GeneratePodcastToolUI = dynamic(
	() =>
		import("@/components/tool-ui/generate-podcast").then((m) => ({
			default: m.GeneratePodcastToolUI,
		})),
	{ ssr: false }
);
const GenerateVideoPresentationToolUI = dynamic(
	() =>
		import("@/components/tool-ui/video-presentation").then((m) => ({
			default: m.GenerateVideoPresentationToolUI,
		})),
	{ ssr: false }
);
const GenerateImageToolUI = dynamic(
	() =>
		import("@/components/tool-ui/generate-image").then((m) => ({ default: m.GenerateImageToolUI })),
	{ ssr: false }
);
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
			<Button
				type="button"
				variant="ghost"
				onClick={() => setOpen(true)}
				className={cn(
					"isolate h-auto cursor-pointer gap-2 rounded-lg px-3 py-2",
					"bg-muted/40 outline-none",
					"transition-colors duration-150",
					"hover:bg-accent hover:text-accent-foreground",
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
			</Button>

			<Drawer open={open} onOpenChange={setOpen}>
				<DrawerContent className="max-h-[85vh] flex flex-col">
					<DrawerHandle />
					<DrawerHeader className="text-left">
						<DrawerTitle className="text-base font-semibold">Sources</DrawerTitle>
					</DrawerHeader>
					<div className="overflow-y-auto flex-1 min-h-0 px-1 pb-6">
						{citations.map((citation) => (
							<Button
								key={citation.id}
								type="button"
								variant="ghost"
								onClick={() => handleNavigate(citation)}
								className="group h-auto w-full justify-start gap-2.5 px-3 py-2.5 text-left hover:bg-accent hover:text-accent-foreground focus-visible:bg-muted"
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
							</Button>
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

function formatMessageDate(date: Date): string {
	return date.toLocaleDateString(undefined, {
		month: "short",
		day: "numeric",
		hour: "numeric",
		minute: "2-digit",
		hour12: true,
	});
}

/**
 * Format provider USD cost (in micro-USD) for inline display next to a
 * token count. Falls back to ``"<$0.001"`` for sub-tenth-of-a-cent
 * costs so a real-but-tiny figure doesn't render as ``$0.000``.
 */
function formatTurnCost(micros: number): string {
	const dollars = micros / 1_000_000;
	if (dollars >= 1) return `$${dollars.toFixed(2)}`;
	if (dollars >= 0.01) return `$${dollars.toFixed(3)}`;
	if (dollars > 0) return "<$0.001";
	return "$0";
}

const MessageInfoDropdown: FC = () => {
	const messageId = useAuiState(({ message }) => message?.id);
	const createdAt = useAuiState(({ message }) => message?.createdAt);
	const usage = useTokenUsage(messageId);

	const { data: localConfigs } = useAtomValue(newLLMConfigsAtom);
	const { data: globalConfigs } = useAtomValue(globalNewLLMConfigsAtom);

	const configByModel = useMemo(() => {
		const map = new Map<string, { name: string; provider: string }>();
		for (const c of [...(globalConfigs ?? []), ...(localConfigs ?? [])]) {
			map.set(c.model_name, { name: c.name, provider: c.provider });
		}
		return map;
	}, [localConfigs, globalConfigs]);

	const resolveModel = (modelKey: string) => {
		const parts = modelKey.split("/");
		const bare = parts[parts.length - 1] ?? modelKey;
		const config = configByModel.get(modelKey) ?? configByModel.get(bare);
		return config
			? { name: config.name, icon: getProviderIcon(config.provider, { className: "size-3.5" }) }
			: { name: modelKey, icon: null };
	};

	const modelBreakdown = usage ? (usage.usage ?? usage.model_breakdown) : undefined;
	const models = modelBreakdown ? Object.entries(modelBreakdown) : [];
	const hasUsage = usage && usage.total_tokens > 0;

	return (
		<ActionBarMorePrimitive.Root>
			<ActionBarMorePrimitive.Trigger asChild>
				<Button variant="ghost" size="icon" className="aui-button-icon size-6 p-1">
					<MoreHorizontalIcon className="size-4" />
					<span className="sr-only">More</span>
				</Button>
			</ActionBarMorePrimitive.Trigger>
			<ActionBarMorePrimitive.Content
				align="start"
				className="bg-popover text-popover-foreground z-50 max-h-(--radix-dropdown-menu-content-available-height) min-w-[180px] origin-(--radix-dropdown-menu-content-transform-origin) overflow-x-hidden overflow-y-auto rounded-md p-1 shadow-md data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2"
			>
				{createdAt && (
					<DropdownMenuLabel className="text-xs text-muted-foreground font-normal select-none">
						{formatMessageDate(createdAt)}
					</DropdownMenuLabel>
				)}
				{hasUsage && (
					<>
						<ActionBarMorePrimitive.Separator className="bg-popover-border mx-2 my-1 h-px" />
						{models.length > 0 ? (
							models.map(([model, counts]) => {
								const { name, icon } = resolveModel(model);
								const costMicros = counts.cost_micros;
								return (
									<ActionBarMorePrimitive.Item
										key={model}
										className="focus:bg-accent focus:text-accent-foreground relative flex cursor-default flex-col items-start gap-0.5 rounded-sm px-2 py-1.5 text-sm outline-hidden select-none"
										onSelect={(e) => e.preventDefault()}
									>
										<span className="flex items-center gap-1.5 text-xs font-medium">
											{icon}
											{name}
										</span>
										<span className="text-xs text-muted-foreground">
											{counts.total_tokens.toLocaleString()} tokens
											{costMicros && costMicros > 0 ? ` · ${formatTurnCost(costMicros)}` : ""}
										</span>
									</ActionBarMorePrimitive.Item>
								);
							})
						) : (
							<ActionBarMorePrimitive.Item
								className="focus:bg-accent focus:text-accent-foreground relative flex cursor-default flex-col items-start gap-0.5 rounded-sm px-2 py-1.5 text-sm outline-hidden select-none"
								onSelect={(e) => e.preventDefault()}
							>
								<span className="text-xs text-muted-foreground">
									{usage.total_tokens.toLocaleString()} tokens
									{usage.cost_micros && usage.cost_micros > 0
										? ` · ${formatTurnCost(usage.cost_micros)}`
										: ""}
								</span>
							</ActionBarMorePrimitive.Item>
						)}
					</>
				)}
			</ActionBarMorePrimitive.Content>
		</ActionBarMorePrimitive.Root>
	);
};

/**
 * Tools rendered in the message BODY — value-add deliverables only.
 *
 * Process tools (connector CRUD, sandbox execute, memory updates,
 * etc.) are NOT here; they render in the timeline via the slice's
 * tool registry (see ``features/chat-messages/timeline``). The body
 * opts out of every other tool by registering ``NullBodyTool`` as the
 * fallback — any tool name not in this map renders nothing in the
 * body and is picked up by the timeline instead.
 */
const BODY_TOOLS = {
	generate_report: GenerateReportToolUI,
	generate_resume: GenerateResumeToolUI,
	generate_podcast: GeneratePodcastToolUI,
	generate_video_presentation: GenerateVideoPresentationToolUI,
	display_image: GenerateImageToolUI,
	generate_image: GenerateImageToolUI,
} as const;

const NullBodyTool: ToolCallMessagePartComponent = () => null;

const AssistantMessageInner: FC = () => {
	const isMobile = !useMediaQuery("(min-width: 768px)");

	return (
		<CitationMetadataProvider>
			<div className="aui-assistant-message-content wrap-break-word px-2 text-foreground leading-relaxed">
				<MessagePrimitive.Parts
					components={{
						Text: MarkdownText,
						Reasoning: ReasoningMessagePart,
						tools: {
							by_name: BODY_TOOLS,
							Fallback: NullBodyTool,
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

			<div className="aui-assistant-message-footer mt-3 mb-5 ml-2 h-6">
				<div className="h-full opacity-100 transition-opacity">
					<AssistantActionBar />
				</div>
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
			{/* Fixed trigger slot prevents any vertical reflow when visibility changes */}
			<div className="mr-2 mb-1 flex h-7 justify-end">
				<Button
					ref={isDesktop ? commentTriggerRef : undefined}
					type="button"
					variant="ghost"
					onClick={
						showCommentTrigger
							? isDesktop
								? () => setIsInlineOpen((prev) => !prev)
								: () => setIsSheetOpen(true)
							: undefined
					}
					aria-hidden={!showCommentTrigger}
					tabIndex={showCommentTrigger ? 0 : -1}
					className={cn(
						"h-auto gap-1.5 rounded-full px-3 py-1 text-sm transition-colors",
						"opacity-0 pointer-events-none",
						showCommentTrigger && "opacity-100 pointer-events-auto",
						isDesktop && isInlineOpen
							? "bg-primary/10 text-primary"
							: hasComments
								? "text-primary hover:bg-primary/10"
								: "text-muted-foreground hover:text-accent-foreground hover:bg-accent hover:text-accent-foreground"
					)}
				>
					<MessageCircleReply className={cn("size-3.5", hasComments && "fill-current")} />
					{hasComments ? (
						<span>
							{commentCount} {commentCount === 1 ? "comment" : "comments"}
						</span>
					) : (
						<span>Add comment</span>
					)}
				</Button>
			</div>

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
	const api = useElectronAPI();
	// Surface the persisted ``chat_turn_id`` so the per-turn revert
	// affordance can scope to just this message's actions. Streamed
	// turns get their id once the assistant message is hydrated/finalised.
	const chatTurnId = useAuiState(({ message }) => {
		const meta = message?.metadata as { custom?: { chatTurnId?: string | null } } | undefined;
		return meta?.custom?.chatTurnId ?? null;
	});

	const isQuickAssist = !!api?.replaceText && IS_QUICK_ASSIST_WINDOW;

	return (
		<ActionBarPrimitive.Root
			hideWhenRunning
			autohide="not-last"
			autohideFloat="single-branch"
			className="aui-assistant-action-bar-root -ml-1 col-start-3 row-start-2 flex gap-1 text-muted-foreground md:data-floating:absolute md:data-floating:rounded-md md:data-floating:p-1 [&>button]:opacity-100 md:[&>button]:opacity-[var(--aui-button-opacity,1)]"
		>
			<ActionBarPrimitive.Copy asChild>
				<TooltipIconButton tooltip="Copy to clipboard">
					<AuiIf condition={({ message }) => message.isCopied}>
						<CheckIcon />
					</AuiIf>
					<AuiIf condition={({ message }) => !message.isCopied}>
						<CopyIcon />
					</AuiIf>
				</TooltipIconButton>
			</ActionBarPrimitive.Copy>
			<ActionBarPrimitive.ExportMarkdown asChild>
				<TooltipIconButton tooltip="Download as Markdown">
					<DownloadIcon />
				</TooltipIconButton>
			</ActionBarPrimitive.ExportMarkdown>
			{isLast && (
				<ActionBarPrimitive.Reload asChild>
					<TooltipIconButton tooltip="Regenerate response">
						<RefreshCwIcon />
					</TooltipIconButton>
				</ActionBarPrimitive.Reload>
			)}
			{isQuickAssist && (
				<TooltipIconButton
					tooltip="Paste back into source app"
					onClick={() => {
						const text = aui.message().getCopyText();
						api?.replaceText(text);
					}}
				>
					<ClipboardPaste />
				</TooltipIconButton>
			)}
			<MessageInfoDropdown />
			<div className="ml-auto">
				<RevertTurnButton chatTurnId={chatTurnId} />
			</div>
		</ActionBarPrimitive.Root>
	);
};
