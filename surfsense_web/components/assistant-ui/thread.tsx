import {
	AuiIf,
	ComposerPrimitive,
	MessagePrimitive,
	ThreadPrimitive,
	useAui,
	useAuiState,
} from "@assistant-ui/react";
import { useAtom, useAtomValue, useSetAtom } from "jotai";
import {
	AlertCircle,
	ArrowUpIcon,
	Camera,
	ChevronDown,
	ChevronRight,
	Clipboard,
	Globe,
	Plus,
	Settings2,
	SquareIcon,
	Unplug,
	Upload,
	Wrench,
	X,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import Image from "next/image";
import { useParams } from "next/navigation";
import { type FC, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
	agentToolsAtom,
	disabledToolsAtom,
	hydrateDisabledToolsAtom,
	toggleToolAtom,
} from "@/atoms/agent-tools/agent-tools.atoms";
import { chatSessionStateAtom } from "@/atoms/chat/chat-session-state.atom";
import { currentThreadAtom } from "@/atoms/chat/current-thread.atom";
import {
	type MentionedDocumentInfo,
	mentionedDocumentsAtom,
} from "@/atoms/chat/mentioned-documents.atom";
import { pendingUserImageDataUrlsAtom } from "@/atoms/chat/pending-user-images.atom";
import {
	clearPremiumAlertForThreadAtom,
	premiumAlertByThreadAtom,
} from "@/atoms/chat/premium-alert.atom";
import { connectorDialogOpenAtom } from "@/atoms/connector-dialog/connector-dialog.atoms";
import { connectorsAtom } from "@/atoms/connectors/connector-query.atoms";
import { membersAtom } from "@/atoms/members/members-query.atoms";
import {
	globalNewLLMConfigsAtom,
	llmPreferencesAtom,
	newLLMConfigsAtom,
} from "@/atoms/new-llm-config/new-llm-config-query.atoms";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import { AssistantMessage } from "@/components/assistant-ui/assistant-message";
import { ChatSessionStatus } from "@/components/assistant-ui/chat-session-status";
import { ChatViewport } from "@/components/assistant-ui/chat-viewport";
import { ConnectorIndicator } from "@/components/assistant-ui/connector-popup";
import { useDocumentUploadDialog } from "@/components/assistant-ui/document-upload-popup";
import {
	InlineMentionEditor,
	type InlineMentionEditorRef,
	type MentionedDocument,
	type SuggestionAnchorRect,
	type SuggestionTriggerInfo,
} from "@/components/assistant-ui/inline-mention-editor";
import { TooltipIconButton } from "@/components/assistant-ui/tooltip-icon-button";
import { UserMessage } from "@/components/assistant-ui/user-message";
import { ComposerSuggestionPopoverContent } from "@/components/new-chat/composer-suggestion-popup";
import { PromptPicker, type PromptPickerRef } from "@/components/new-chat/prompt-picker";
import { Avatar, AvatarFallback, AvatarGroup } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import {
	Drawer,
	DrawerContent,
	DrawerHandle,
	DrawerHeader,
	DrawerTitle,
} from "@/components/ui/drawer";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuPortal,
	DropdownMenuSub,
	DropdownMenuSubContent,
	DropdownMenuSubTrigger,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Popover, PopoverAnchor } from "@/components/ui/popover";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import {
	CONNECTOR_ICON_TO_TYPES,
	CONNECTOR_TOOL_ICON_PATHS,
	getToolDisplayName,
	getToolIcon,
} from "@/contracts/enums/toolIcons";
import { useBatchCommentsPreload } from "@/hooks/use-comments";
import { useCommentsSync } from "@/hooks/use-comments-sync";
import { useMediaQuery } from "@/hooks/use-media-query";
import { useElectronAPI } from "@/hooks/use-platform";
import { captureDisplayToPngDataUrl } from "@/lib/chat/display-media-capture";
import { getMentionDocKey } from "@/lib/chat/mention-doc-key";
import { slideoutOpenedTickAtom } from "@/lib/layout-events";
import { cn } from "@/lib/utils";
import {
	DocumentMentionPicker,
	type DocumentMentionPickerRef,
	promoteRecentMention,
} from "../new-chat/document-mention-picker";

const COMPOSER_PLACEHOLDER = "Ask anything, type / for prompts, type @ to mention docs";

type ComposerSuggestionAnchorPoint = {
	left: number;
	top: number;
};

function ComposerSuggestionAnchor({ point }: { point: ComposerSuggestionAnchorPoint }) {
	return (
		<PopoverAnchor
			className="pointer-events-none fixed size-0"
			style={{
				left: point.left,
				top: point.top,
			}}
		/>
	);
}

function getComposerSuggestionAnchorPoint(
	triggerRect: SuggestionAnchorRect | null,
	side: "top" | "bottom"
): ComposerSuggestionAnchorPoint | null {
	if (!triggerRect) return null;
	return {
		left: triggerRect.left,
		top: side === "bottom" ? triggerRect.bottom : triggerRect.top,
	};
}

export const Thread: FC = () => {
	return <ThreadContent />;
};

const ThreadContent: FC = () => {
	return (
		<ThreadPrimitive.Root
			className="aui-root aui-thread-root @container flex h-full min-h-0 flex-col bg-main-panel"
			style={{
				["--thread-max-width" as string]: "42rem",
			}}
		>
			<ChatViewport
				footer={
					<AuiIf condition={({ thread }) => !thread.isEmpty}>
						<PremiumQuotaPinnedAlert />
						<Composer />
					</AuiIf>
				}
			>
				<AuiIf condition={({ thread }) => thread.isEmpty}>
					<ThreadWelcome />
				</AuiIf>

				<ThreadPrimitive.Messages
					components={{
						UserMessage,
						EditComposer,
						AssistantMessage,
					}}
				/>
			</ChatViewport>
		</ThreadPrimitive.Root>
	);
};

const PremiumQuotaPinnedAlert: FC = () => {
	const currentThreadState = useAtomValue(currentThreadAtom);
	const alertsByThread = useAtomValue(premiumAlertByThreadAtom);
	const clearPremiumAlertForThread = useSetAtom(clearPremiumAlertForThreadAtom);

	const currentThreadId = currentThreadState?.id;
	if (!currentThreadId) return null;

	const alert = alertsByThread[currentThreadId];
	if (!alert) return null;

	return (
		<div className="mx-0 overflow-hidden rounded-2xl border-input bg-muted px-4 py-4 text-foreground select-none">
			<div className="flex items-center gap-2">
				<AlertCircle className="size-4 shrink-0 text-muted-foreground" />
				<div className="min-w-0 flex-1">
					<p className="text-sm">{alert.message}</p>
				</div>
				<Button
					type="button"
					variant="ghost"
					size="icon"
					className="size-6 text-muted-foreground hover:bg-transparent hover:text-accent-foreground"
					aria-label="Dismiss premium quota alert"
					onClick={() => clearPremiumAlertForThread(currentThreadId)}
				>
					<X className="size-4" />
				</Button>
			</div>
		</div>
	);
};

const getTimeBasedGreeting = (user?: { display_name?: string | null; email?: string }): string => {
	const hour = new Date().getHours();

	let firstName: string | null = null;
	if (user?.display_name?.trim()) {
		const nameParts = user.display_name.trim().split(/\s+/);
		firstName = nameParts[0].charAt(0).toUpperCase() + nameParts[0].slice(1).toLowerCase();
	} else if (user?.email) {
		firstName =
			user.email.split("@")[0].split(".")[0].charAt(0).toUpperCase() +
			user.email.split("@")[0].split(".")[0].slice(1);
	}

	const morningGreetings = ["Good morning", "Fresh start today", "Morning", "Hey there"];
	const afternoonGreetings = ["Good afternoon", "Afternoon", "Hey there", "Hi there"];
	const eveningGreetings = ["Good evening", "Evening", "Hey there", "Hi there"];
	const nightGreetings = ["Good night", "Evening", "Hey there", "Winding down"];
	const lateNightGreetings = ["Still up", "Night owl mode", "Up past bedtime", "Hi there"];

	let greeting: string;
	if (hour < 5) {
		greeting = lateNightGreetings[Math.floor(Math.random() * lateNightGreetings.length)];
	} else if (hour < 12) {
		greeting = morningGreetings[Math.floor(Math.random() * morningGreetings.length)];
	} else if (hour < 18) {
		greeting = afternoonGreetings[Math.floor(Math.random() * afternoonGreetings.length)];
	} else if (hour < 22) {
		greeting = eveningGreetings[Math.floor(Math.random() * eveningGreetings.length)];
	} else {
		greeting = nightGreetings[Math.floor(Math.random() * nightGreetings.length)];
	}

	return firstName ? `${greeting}, ${firstName}!` : `${greeting}!`;
};

const ThreadWelcome: FC = () => {
	const { data: user } = useAtomValue(currentUserAtom);
	const greeting = useMemo(() => getTimeBasedGreeting(user), [user]);

	return (
		<div className="aui-thread-welcome-root mx-auto flex w-full max-w-(--thread-max-width) grow flex-col items-center px-4 relative">
			<div className="aui-thread-welcome-message absolute bottom-[calc(50%+5rem)] left-0 right-0 flex flex-col items-center text-center">
				<h1 className="aui-thread-welcome-message-inner text-3xl md:text-[2.625rem] select-none">
					{greeting}
				</h1>
			</div>
			<div className="w-full flex items-start justify-center absolute top-[calc(50%-3.5rem)] left-0 right-0">
				<Composer />
			</div>
		</div>
	);
};

const BANNER_CONNECTORS = [
	{ type: "GOOGLE_DRIVE_CONNECTOR", label: "Google Drive" },
	{ type: "GOOGLE_GMAIL_CONNECTOR", label: "Gmail" },
	{ type: "NOTION_CONNECTOR", label: "Notion" },
	{ type: "YOUTUBE_CONNECTOR", label: "YouTube" },
	{ type: "SLACK_CONNECTOR", label: "Slack" },
] as const;

const BANNER_DISMISSED_KEY = "surfsense-connect-tools-banner-dismissed";

const ConnectToolsBanner: FC<{
	isThreadEmpty: boolean;
	onVisibleChange?: (visible: boolean) => void;
}> = ({ isThreadEmpty, onVisibleChange }) => {
	const { data: connectors } = useAtomValue(connectorsAtom);
	const setConnectorDialogOpen = useSetAtom(connectorDialogOpenAtom);
	const [dismissed, setDismissed] = useState(() => {
		if (typeof window === "undefined") return false;
		return localStorage.getItem(BANNER_DISMISSED_KEY) === "true";
	});
	const [dismissRequested, setDismissRequested] = useState(false);

	const hasConnectors = (connectors?.length ?? 0) > 0;
	const isVisible = !dismissed && !hasConnectors && isThreadEmpty;
	const shouldShowTray = isVisible && !dismissRequested;

	useEffect(() => {
		onVisibleChange?.(isVisible);
	}, [isVisible, onVisibleChange]);

	const handleDismiss = (e: React.MouseEvent) => {
		e.stopPropagation();
		setDismissRequested(true);
	};

	return (
		<AnimatePresence
			initial={false}
			onExitComplete={() => {
				if (!dismissRequested) return;
				setDismissed(true);
				localStorage.setItem(BANNER_DISMISSED_KEY, "true");
			}}
		>
			{shouldShowTray ? (
				<motion.div
					key="connect-tools-tray"
					initial={{ opacity: 0, y: -10 }}
					animate={{ opacity: 1, y: 0 }}
					exit={{ opacity: 0, y: -14 }}
					transition={{ duration: 0.18, ease: "easeOut" }}
					className="relative z-0 -mt-5 flex min-w-0 items-center gap-2 rounded-b-3xl border border-input bg-muted/40 px-4 pt-7 pb-3 shadow-sm shadow-black/5 dark:shadow-black/10"
				>
					<Button
						type="button"
						variant="ghost"
						size="sm"
						className="h-7 min-w-0 cursor-pointer justify-start gap-2 rounded-md px-0 text-[13px] font-normal text-muted-foreground select-none hover:bg-transparent hover:text-foreground"
						onClick={() => setConnectorDialogOpen(true)}
					>
						<Unplug className="size-4 shrink-0" />
						<span className="truncate">Connect your tools</span>
					</Button>
					<div className="min-w-0 flex-1" />
					<AvatarGroup className="shrink-0">
						{BANNER_CONNECTORS.map(({ type }, i) => (
							<Avatar
								key={type}
								className="size-5"
								style={{ zIndex: BANNER_CONNECTORS.length - i }}
							>
								<AvatarFallback className="bg-accent text-[10px]">
									{getConnectorIcon(type, "size-3")}
								</AvatarFallback>
							</Avatar>
						))}
					</AvatarGroup>
					<Button
						type="button"
						onClick={handleDismiss}
						variant="ghost"
						size="icon"
						className="size-7 shrink-0 cursor-pointer rounded-md text-muted-foreground hover:bg-transparent hover:text-foreground"
						aria-label="Dismiss"
					>
						<X className="size-3.5" />
					</Button>
				</motion.div>
			) : null}
		</AnimatePresence>
	);
};

const PendingScreenImageStrip: FC = () => {
	const [urls, setUrls] = useAtom(pendingUserImageDataUrlsAtom);
	if (urls.length === 0) return null;
	return (
		<div className="mx-3 mt-2 flex flex-wrap gap-2">
			{urls.map((url, index) => (
				<div
					key={url}
					className="group relative h-14 w-14 shrink-0 overflow-hidden rounded-md border border-border/50 bg-muted"
				>
					<Image
						src={url}
						alt="Pending screenshot preview"
						fill
						sizes="56px"
						className="object-cover"
						draggable={false}
						unoptimized
					/>
					<Button
						type="button"
						onClick={() => setUrls((prev) => prev.filter((_, i) => i !== index))}
						variant="ghost"
						size="icon"
						className="absolute right-0.5 top-0.5 size-5 rounded-full bg-background/90 text-muted-foreground shadow-sm transition-opacity hover:bg-background/90 hover:text-accent-foreground sm:opacity-0 sm:group-hover:opacity-100"
						aria-label="Remove screenshot"
					>
						<X className="size-3" />
					</Button>
				</div>
			))}
		</div>
	);
};

const ClipboardChip: FC<{ text: string; onDismiss: () => void }> = ({ text, onDismiss }) => {
	const [expanded, setExpanded] = useState(false);
	const isLong = text.length > 120;
	const preview = isLong ? `${text.slice(0, 120)}…` : text;

	return (
		<div className="mx-3 mt-2 rounded-lg border border-border/40 bg-background/60">
			<div className="flex items-center gap-2 px-3 py-2">
				<Clipboard className="size-4 shrink-0 text-muted-foreground" />
				<span className="text-xs font-medium text-muted-foreground">From clipboard</span>
				<div className="flex-1" />
				{isLong && (
					<Button
						type="button"
						onClick={() => setExpanded((v) => !v)}
						variant="ghost"
						size="icon"
						className="size-5 text-muted-foreground hover:bg-transparent hover:text-accent-foreground"
					>
						<ChevronDown
							className={cn("size-3.5 transition-transform", expanded && "rotate-180")}
						/>
					</Button>
				)}
				<Button
					type="button"
					onClick={onDismiss}
					variant="ghost"
					size="icon"
					className="size-5 text-muted-foreground hover:bg-transparent hover:text-accent-foreground"
				>
					<X className="size-3.5" />
				</Button>
			</div>
			<div className="px-3 pb-2">
				<p className="text-xs text-foreground/80 whitespace-pre-wrap wrap-break-word leading-relaxed">
					{expanded ? text : preview}
				</p>
			</div>
		</div>
	);
};

const Composer: FC = () => {
	const [mentionedDocuments, setMentionedDocuments] = useAtom(mentionedDocumentsAtom);
	const [showDocumentPopover, setShowDocumentPopover] = useState(false);
	const [showPromptPicker, setShowPromptPicker] = useState(false);
	const [mentionQuery, setMentionQuery] = useState("");
	const [actionQuery, setActionQuery] = useState("");
	const [suggestionAnchorPoint, setSuggestionAnchorPoint] =
		useState<ComposerSuggestionAnchorPoint | null>(null);
	const editorRef = useRef<InlineMentionEditorRef>(null);
	const prevMentionedDocsRef = useRef<Map<string, MentionedDocumentInfo>>(new Map());
	const documentPickerRef = useRef<DocumentMentionPickerRef>(null);
	const promptPickerRef = useRef<PromptPickerRef>(null);
	const { search_space_id, chat_id } = useParams();
	const aui = useAui();
	// Desktop-only auto-focus; on mobile, programmatic focus would
	// summon the soft keyboard on every picker close / thread switch.
	const isDesktop = useMediaQuery("(min-width: 640px)");

	const electronAPI = useElectronAPI();
	const [clipboardInitialText, setClipboardInitialText] = useState<string | undefined>();
	const clipboardLoadedRef = useRef(false);
	useEffect(() => {
		if (!electronAPI || clipboardLoadedRef.current) return;
		clipboardLoadedRef.current = true;
		electronAPI.getQuickAskText().then((text: string) => {
			if (text) {
				setClipboardInitialText(text);
			}
		});
	}, [electronAPI]);

	const isThreadEmpty = useAuiState(({ thread }) => thread.isEmpty);
	const isThreadRunning = useAuiState(({ thread }) => thread.isRunning);
	const [connectToolsTrayVisible, setConnectToolsTrayVisible] = useState(false);

	const currentPlaceholder = COMPOSER_PLACEHOLDER;

	const { data: currentUser } = useAtomValue(currentUserAtom);
	const { data: members } = useAtomValue(membersAtom);
	const threadId = useMemo(() => {
		if (Array.isArray(chat_id) && chat_id.length > 0) {
			return Number.parseInt(chat_id[0], 10) || null;
		}
		return typeof chat_id === "string" ? Number.parseInt(chat_id, 10) || null : null;
	}, [chat_id]);
	const sessionState = useAtomValue(chatSessionStateAtom);
	const isAiResponding = sessionState?.isAiResponding ?? false;
	const respondingToUserId = sessionState?.respondingToUserId ?? null;
	const isBlockedByOtherUser = isAiResponding && respondingToUserId !== currentUser?.id;

	// One Zero subscription per thread for comment sync.
	useCommentsSync(threadId);

	// Batch-prefetch assistant message comments to avoid N+1 fetches.
	// Returns a primitive string so useSyncExternalStore can compare by value.
	const assistantIdsKey = useAuiState(({ thread }) =>
		thread.messages
			.filter((m) => m.role === "assistant" && m.id?.startsWith("msg-"))
			.map((m) => m.id?.replace("msg-", ""))
			.join(",")
	);
	const assistantDbMessageIds = useMemo(
		() => (assistantIdsKey ? assistantIdsKey.split(",").map(Number) : []),
		[assistantIdsKey]
	);
	useBatchCommentsPreload(assistantDbMessageIds);

	// Always-focused composer: refocus whenever no picker has taken
	// over input. ``threadId`` is in the deps so the effect re-fires
	// on thread switch (Composer instance is reused).
	useEffect(() => {
		if (!isDesktop) return;
		if (showDocumentPopover || showPromptPicker) return;
		void threadId;
		editorRef.current?.focus();
	}, [isDesktop, showDocumentPopover, showPromptPicker, threadId]);

	// Close document picker when a sidebar slide-out panel (inbox, etc.) opens.
	// React only on changes to the tick — comparing against the previously-seen
	// value preserves the one-shot semantics of the prior window-event approach
	// (no retroactive close on mount if a panel had already opened earlier).
	const slideoutOpenedTick = useAtomValue(slideoutOpenedTickAtom);
	const lastSeenSlideoutTickRef = useRef(slideoutOpenedTick);
	useEffect(() => {
		if (lastSeenSlideoutTickRef.current === slideoutOpenedTick) return;
		lastSeenSlideoutTickRef.current = slideoutOpenedTick;
		setShowDocumentPopover(false);
		setMentionQuery("");
		setSuggestionAnchorPoint(null);
	}, [slideoutOpenedTick]);

	// Sync editor text into assistant-ui's composer and mirror the chip
	// atom from the editor's reported ``docs``. The editor is the
	// single source of truth, so this catches every Plate deletion path
	// (Backspace, X button, Cmd+Backspace, range-delete, cut,
	// paste-over) without per-keybinding plumbing. The ``prev``
	// short-circuit keeps pure-text keystrokes from churning the atom.
	const handleEditorChange = useCallback(
		(text: string, docs: MentionedDocument[]) => {
			aui.composer().setText(text);
			setMentionedDocuments((prev) => {
				if (prev.length === docs.length) {
					const editorKeys = new Set(docs.map((d) => getMentionDocKey(d)));
					if (prev.every((d) => editorKeys.has(getMentionDocKey(d)))) {
						return prev;
					}
				}
				return docs.map<MentionedDocumentInfo>((d) => {
					if (d.kind === "connector") {
						return {
							id: d.id,
							title: d.title,
							kind: "connector",
							connector_type: d.connector_type ?? "UNKNOWN",
							account_name: d.account_name ?? d.title,
						};
					}
					if (d.kind === "folder") {
						return {
							id: d.id,
							title: d.title,
							kind: "folder",
						};
					}
					return {
						id: d.id,
						title: d.title,
						document_type: d.document_type ?? "UNKNOWN",
						kind: "doc",
					};
				});
			});
		},
		[aui, setMentionedDocuments]
	);

	const handleMentionTrigger = useCallback((trigger: SuggestionTriggerInfo) => {
		const anchorPoint = getComposerSuggestionAnchorPoint(trigger.anchorRect, "top");
		if (!anchorPoint) {
			setShowDocumentPopover(false);
			setMentionQuery("");
			setSuggestionAnchorPoint(null);
			return;
		}
		setSuggestionAnchorPoint((current) => current ?? anchorPoint);
		setShowDocumentPopover(true);
		setMentionQuery(trigger.query);
	}, []);

	const handleMentionClose = useCallback(() => {
		if (showDocumentPopover) {
			setShowDocumentPopover(false);
			setMentionQuery("");
			setSuggestionAnchorPoint(null);
		}
	}, [showDocumentPopover]);

	const handleDocumentPopoverOpenChange = useCallback((open: boolean) => {
		setShowDocumentPopover(open);
		if (!open) {
			setMentionQuery("");
			setSuggestionAnchorPoint(null);
		}
	}, []);

	const handleActionTrigger = useCallback(
		(trigger: SuggestionTriggerInfo) => {
			const anchorPoint = getComposerSuggestionAnchorPoint(
				trigger.anchorRect,
				clipboardInitialText ? "bottom" : "top"
			);
			if (!anchorPoint) {
				setShowPromptPicker(false);
				setActionQuery("");
				setSuggestionAnchorPoint(null);
				return;
			}
			setSuggestionAnchorPoint((current) => current ?? anchorPoint);
			setShowPromptPicker(true);
			setActionQuery(trigger.query);
		},
		[clipboardInitialText]
	);

	const handleActionClose = useCallback(() => {
		if (showPromptPicker) {
			setShowPromptPicker(false);
			setActionQuery("");
			setSuggestionAnchorPoint(null);
		}
	}, [showPromptPicker]);

	const handlePromptPickerOpenChange = useCallback((open: boolean) => {
		setShowPromptPicker(open);
		if (!open) {
			setActionQuery("");
			setSuggestionAnchorPoint(null);
		}
	}, []);

	const handleActionSelect = useCallback(
		(action: { name: string; prompt: string; mode: "transform" | "explore" }) => {
			let userText = editorRef.current?.getText() ?? "";
			const trigger = `/${actionQuery}`;
			if (userText.endsWith(trigger)) {
				userText = userText.slice(0, -trigger.length).trimEnd();
			}
			const finalPrompt = action.prompt.includes("{selection}")
				? action.prompt.replace("{selection}", () => userText)
				: userText
					? `${action.prompt}\n\n${userText}`
					: action.prompt;
			editorRef.current?.setText(finalPrompt);
			aui.composer().setText(finalPrompt);
			setShowPromptPicker(false);
			setActionQuery("");
			setSuggestionAnchorPoint(null);
		},
		[actionQuery, aui]
	);

	const handleQuickAskSelect = useCallback(
		(action: { name: string; prompt: string; mode: "transform" | "explore" }) => {
			if (!clipboardInitialText) return;
			electronAPI?.setQuickAskMode(action.mode);
			const finalPrompt = action.prompt.includes("{selection}")
				? action.prompt.replace("{selection}", () => clipboardInitialText)
				: `${action.prompt}\n\n${clipboardInitialText}`;
			editorRef.current?.setText(finalPrompt);
			aui.composer().setText(finalPrompt);
			setShowPromptPicker(false);
			setActionQuery("");
			setSuggestionAnchorPoint(null);
			setClipboardInitialText(undefined);
		},
		[clipboardInitialText, electronAPI, aui]
	);

	// Arrow / Enter / Escape navigation for the active picker.
	const handleKeyDown = useCallback(
		(e: React.KeyboardEvent) => {
			if (showPromptPicker) {
				if (e.key === "ArrowDown") {
					e.preventDefault();
					promptPickerRef.current?.moveDown();
					return;
				}
				if (e.key === "ArrowUp") {
					e.preventDefault();
					promptPickerRef.current?.moveUp();
					return;
				}
				if (e.key === "Enter") {
					e.preventDefault();
					promptPickerRef.current?.selectHighlighted();
					return;
				}
				if (e.key === "Escape") {
					e.preventDefault();
					setShowPromptPicker(false);
					setActionQuery("");
					setSuggestionAnchorPoint(null);
					return;
				}
			}
			if (showDocumentPopover) {
				if (e.key === "ArrowDown") {
					e.preventDefault();
					documentPickerRef.current?.moveDown();
					return;
				}
				if (e.key === "ArrowUp") {
					e.preventDefault();
					documentPickerRef.current?.moveUp();
					return;
				}
				if (e.key === "Enter") {
					e.preventDefault();
					documentPickerRef.current?.selectHighlighted();
					return;
				}
				if (e.key === "Escape") {
					e.preventDefault();
					if (documentPickerRef.current?.goBack()) {
						return;
					}
					setShowDocumentPopover(false);
					setMentionQuery("");
					setSuggestionAnchorPoint(null);
					return;
				}
			}
		},
		[showDocumentPopover, showPromptPicker]
	);

	const handleSubmit = useCallback(() => {
		if (isThreadRunning || isBlockedByOtherUser) return;
		if (showDocumentPopover || showPromptPicker) return;

		if (clipboardInitialText) {
			const userText = editorRef.current?.getText() ?? "";
			const combined = userText ? `${userText}\n\n${clipboardInitialText}` : clipboardInitialText;
			aui.composer().setText(combined);
			setClipboardInitialText(undefined);
		}

		aui.composer().send();
		editorRef.current?.clear();
		setMentionedDocuments([]);
	}, [
		showDocumentPopover,
		showPromptPicker,
		isThreadRunning,
		isBlockedByOtherUser,
		clipboardInitialText,
		aui,
		setMentionedDocuments,
	]);

	const handleDocumentRemove = useCallback(
		(
			docId: number,
			docType?: string,
			kind?: "doc" | "folder" | "connector",
			connectorType?: string
		) => {
			setMentionedDocuments((prev) => {
				const removedKey = getMentionDocKey({
					id: docId,
					document_type: docType,
					kind,
					connector_type: connectorType,
				});
				return prev.filter((doc) => getMentionDocKey(doc) !== removedKey);
			});
		},
		[setMentionedDocuments]
	);

	const handleDocumentsMention = useCallback(
		(mentions: MentionedDocumentInfo[]) => {
			const parsedSearchSpaceId = Number(search_space_id);
			const editorMentionedDocs = editorRef.current?.getMentionedDocuments() ?? [];
			const editorDocKeys = new Set(editorMentionedDocs.map((doc) => getMentionDocKey(doc)));

			for (const mention of mentions) {
				const key = getMentionDocKey(mention);
				if (editorDocKeys.has(key)) continue;
				editorRef.current?.insertMentionChip(mention);
				if (Number.isFinite(parsedSearchSpaceId)) {
					promoteRecentMention(parsedSearchSpaceId, mention);
				}
				// Track within the loop so a duplicate-in-batch can't double-insert.
				editorDocKeys.add(key);
			}

			// Atom is reconciled by ``handleEditorChange`` via the editor's
			// onChange — no second write path here.
			setMentionQuery("");
			setSuggestionAnchorPoint(null);
		},
		[search_space_id]
	);

	useEffect(() => {
		const editor = editorRef.current;
		const nextDocsMap = new Map(mentionedDocuments.map((doc) => [getMentionDocKey(doc), doc]));
		const prevDocsMap = prevMentionedDocsRef.current;

		if (!editor) {
			prevMentionedDocsRef.current = nextDocsMap;
			return;
		}

		const editorKeys = new Set(editor.getMentionedDocuments().map(getMentionDocKey));

		for (const [key, doc] of nextDocsMap) {
			if (prevDocsMap.has(key) || editorKeys.has(key)) continue;
			editor.insertMentionChip(doc, { removeTriggerText: false });
		}

		for (const [key, doc] of prevDocsMap) {
			if (!nextDocsMap.has(key)) {
				editor.removeDocumentChip(
					doc.id,
					doc.kind === "doc" ? doc.document_type : undefined,
					doc.kind,
					doc.kind === "connector" ? doc.connector_type : undefined
				);
			}
		}

		prevMentionedDocsRef.current = nextDocsMap;
	}, [mentionedDocuments]);

	return (
		<ComposerPrimitive.Root className="aui-composer-root relative flex w-full flex-col gap-2 rounded-2xl">
			<ChatSessionStatus
				isAiResponding={isAiResponding}
				respondingToUserId={respondingToUserId}
				currentUserId={currentUser?.id ?? null}
				members={members ?? []}
			/>
			<Popover open={showDocumentPopover} onOpenChange={handleDocumentPopoverOpenChange}>
				{suggestionAnchorPoint ? (
					<>
						<ComposerSuggestionAnchor point={suggestionAnchorPoint} />
						<ComposerSuggestionPopoverContent side="top">
							<DocumentMentionPicker
								ref={documentPickerRef}
								searchSpaceId={Number(search_space_id)}
								onSelectionChange={handleDocumentsMention}
								onDone={() => {
									setShowDocumentPopover(false);
									setMentionQuery("");
									setSuggestionAnchorPoint(null);
								}}
								initialSelectedDocuments={mentionedDocuments}
								externalSearch={mentionQuery}
							/>
						</ComposerSuggestionPopoverContent>
					</>
				) : null}
			</Popover>
			<Popover open={showPromptPicker} onOpenChange={handlePromptPickerOpenChange}>
				{suggestionAnchorPoint ? (
					<>
						<ComposerSuggestionAnchor point={suggestionAnchorPoint} />
						<ComposerSuggestionPopoverContent side={clipboardInitialText ? "bottom" : "top"}>
							<PromptPicker
								ref={promptPickerRef}
								onSelect={clipboardInitialText ? handleQuickAskSelect : handleActionSelect}
								onDone={() => {
									setShowPromptPicker(false);
									setActionQuery("");
									setSuggestionAnchorPoint(null);
								}}
								externalSearch={actionQuery}
							/>
						</ComposerSuggestionPopoverContent>
					</>
				) : null}
			</Popover>
			<div className="flex w-full flex-col">
				<div
					className={cn(
						"aui-composer-attachment-dropzone relative z-10 flex w-full flex-col overflow-hidden rounded-3xl border border-input bg-muted pt-2 shadow-sm shadow-black/5 outline-none transition-shadow dark:shadow-black/10",
						connectToolsTrayVisible && "rounded-b-3xl shadow-none dark:shadow-none"
					)}
				>
					<PendingScreenImageStrip />
					{clipboardInitialText && (
						<ClipboardChip
							text={clipboardInitialText}
							onDismiss={() => setClipboardInitialText(undefined)}
						/>
					)}
					<div className="aui-composer-input-wrapper px-4 pt-3 pb-6">
						<InlineMentionEditor
							ref={editorRef}
							placeholder={currentPlaceholder}
							onMentionTrigger={handleMentionTrigger}
							onMentionClose={handleMentionClose}
							onActionTrigger={handleActionTrigger}
							onActionClose={handleActionClose}
							onChange={handleEditorChange}
							onDocumentRemove={handleDocumentRemove}
							onSubmit={handleSubmit}
							onKeyDown={handleKeyDown}
							className="min-h-[24px] **:data-slate-placeholder:font-normal"
						/>
					</div>
					<ComposerAction isBlockedByOtherUser={isBlockedByOtherUser} />
					<ConnectorIndicator showTrigger={false} />
				</div>
				<ConnectToolsBanner
					isThreadEmpty={isThreadEmpty}
					onVisibleChange={setConnectToolsTrayVisible}
				/>
			</div>
		</ComposerPrimitive.Root>
	);
};

interface ComposerActionProps {
	isBlockedByOtherUser?: boolean;
}

const ComposerAction: FC<ComposerActionProps> = ({ isBlockedByOtherUser = false }) => {
	const mentionedDocuments = useAtomValue(mentionedDocumentsAtom);
	const setConnectorDialogOpen = useSetAtom(connectorDialogOpenAtom);
	const [toolsPopoverOpen, setToolsPopoverOpen] = useState(false);
	const [openConnectorSubmenu, setOpenConnectorSubmenu] = useState<string | null>(null);
	const [expandedConnectorGroups, setExpandedConnectorGroups] = useState<Set<string>>(
		() => new Set()
	);
	const isDesktop = useMediaQuery("(min-width: 640px)");
	const { openDialog: openUploadDialog } = useDocumentUploadDialog();
	const pendingScreenImages = useAtomValue(pendingUserImageDataUrlsAtom);
	const setPendingScreenImages = useSetAtom(pendingUserImageDataUrlsAtom);
	const electronAPI = useElectronAPI();

	const isComposerTextEmpty = useAuiState(({ composer }) => {
		const text = composer.text?.trim() || "";
		return text.length === 0;
	});
	const isComposerEmpty =
		isComposerTextEmpty && mentionedDocuments.length === 0 && pendingScreenImages.length === 0;

	const handleScreenCapture = useCallback(async () => {
		const url = electronAPI?.captureFullScreen
			? await electronAPI.captureFullScreen()
			: await captureDisplayToPngDataUrl();
		if (url) setPendingScreenImages((prev) => [...prev, url]);
	}, [electronAPI, setPendingScreenImages]);

	const { data: userConfigs } = useAtomValue(newLLMConfigsAtom);
	const { data: globalConfigs } = useAtomValue(globalNewLLMConfigsAtom);
	const { data: preferences } = useAtomValue(llmPreferencesAtom);

	const { data: agentTools } = useAtomValue(agentToolsAtom);
	const disabledTools = useAtomValue(disabledToolsAtom);
	const disabledToolsSet = useMemo(() => new Set(disabledTools), [disabledTools]);
	const toggleTool = useSetAtom(toggleToolAtom);
	const setDisabledTools = useSetAtom(disabledToolsAtom);
	const hydrateDisabled = useSetAtom(hydrateDisabledToolsAtom);

	const { data: connectors } = useAtomValue(connectorsAtom);
	const connectedTypes = useMemo(
		() => new Set<string>((connectors ?? []).map((c) => c.connector_type)),
		[connectors]
	);

	const toggleToolGroup = useCallback(
		(toolNames: string[]) => {
			const allDisabled = toolNames.every((name) => disabledToolsSet.has(name));
			if (allDisabled) {
				setDisabledTools((prev) => prev.filter((t) => !toolNames.includes(t)));
			} else {
				setDisabledTools((prev) => [...new Set([...prev, ...toolNames])]);
			}
		},
		[disabledToolsSet, setDisabledTools]
	);
	const setConnectorGroupExpanded = useCallback((label: string, expanded: boolean) => {
		setExpandedConnectorGroups((prev) => {
			const next = new Set(prev);
			if (expanded) {
				next.add(label);
			} else {
				next.delete(label);
			}
			return next;
		});
	}, []);

	const hasWebSearchTool = agentTools?.some((t) => t.name === "web_search") ?? false;
	const isWebSearchEnabled = hasWebSearchTool && !disabledToolsSet.has("web_search");
	const filteredTools = useMemo(
		() => agentTools?.filter((t) => t.name !== "web_search"),
		[agentTools]
	);
	const groupedTools = useMemo(() => {
		if (!filteredTools) return [];
		const toolsByName = new Map(filteredTools.map((t) => [t.name, t]));
		const result: { label: string; tools: typeof filteredTools; connectorIcon?: string }[] = [];
		const placed = new Set<string>();

		for (const group of TOOL_GROUPS) {
			if (group.connectorIcon) {
				const requiredTypes = CONNECTOR_ICON_TO_TYPES[group.connectorIcon];
				const isConnected = requiredTypes?.some((t) => connectedTypes.has(t));
				if (!isConnected) {
					for (const name of group.tools) placed.add(name);
					continue;
				}
			}

			const matched = group.tools.flatMap((name) => {
				const tool = toolsByName.get(name);
				if (!tool) return [];
				placed.add(name);
				return [tool];
			});
			if (matched.length > 0) {
				result.push({ label: group.label, tools: matched, connectorIcon: group.connectorIcon });
			}
		}

		const ungrouped = filteredTools.filter((t) => !placed.has(t.name));
		if (ungrouped.length > 0) {
			result.push({ label: "Other", tools: ungrouped });
		}

		return result;
	}, [filteredTools, connectedTypes]);
	const regularToolGroups = groupedTools.filter((g) => !g.connectorIcon && g.label !== "Other");
	const connectorToolGroups = groupedTools.filter((g) => g.connectorIcon);
	const otherToolGroup = groupedTools.find((g) => !g.connectorIcon && g.label === "Other");

	useEffect(() => {
		hydrateDisabled();
	}, [hydrateDisabled]);

	const hasModelConfigured = useMemo(() => {
		if (!preferences) return false;
		const agentLlmId = preferences.agent_llm_id;
		if (agentLlmId === null || agentLlmId === undefined) return false;

		if (agentLlmId <= 0) {
			return globalConfigs?.some((c) => c.id === agentLlmId) ?? false;
		}
		return userConfigs?.some((c) => c.id === agentLlmId) ?? false;
	}, [preferences, globalConfigs, userConfigs]);

	const isSendDisabled = isComposerEmpty || !hasModelConfigured || isBlockedByOtherUser;

	return (
		<div className="aui-composer-action-wrapper relative mx-3 mb-3 flex items-center justify-between">
			<div className="flex items-center gap-1">
				{!isDesktop ? (
					<>
						<DropdownMenu>
							<DropdownMenuTrigger asChild>
								<Button
									variant="ghost"
									size="icon"
									className="h-9 w-9 rounded-full p-0 font-semibold text-xs text-muted-foreground transition-colors dark:border-muted-foreground/15 hover:bg-foreground/10 hover:text-foreground"
									aria-label="Upload files, manage tools and more"
									data-joyride="connector-icon"
								>
									<Plus className="size-5" />
								</Button>
							</DropdownMenuTrigger>
							<DropdownMenuContent side="bottom" align="start" sideOffset={8}>
								<DropdownMenuItem onSelect={() => openUploadDialog()}>
									<Upload className="size-4" />
									Upload Files
								</DropdownMenuItem>
								{hasWebSearchTool && (
									<DropdownMenuItem
										onSelect={(event) => {
											event.preventDefault();
											toggleTool("web_search");
										}}
									>
										<Globe className="size-4" />
										<span className="flex-1">Web Search</span>
										<Switch
											checked={isWebSearchEnabled}
											tabIndex={-1}
											className="pointer-events-none shrink-0 origin-right scale-[0.6]"
										/>
									</DropdownMenuItem>
								)}
								<DropdownMenuItem onSelect={() => setConnectorDialogOpen(true)}>
									<Unplug className="size-4" />
									Manage Connectors
								</DropdownMenuItem>
								<DropdownMenuItem onSelect={() => setToolsPopoverOpen(true)}>
									<Settings2 className="size-4" />
									Manage Tools
								</DropdownMenuItem>
							</DropdownMenuContent>
						</DropdownMenu>
						<Drawer
							open={toolsPopoverOpen}
							onOpenChange={setToolsPopoverOpen}
							shouldScaleBackground={false}
						>
							<DrawerContent className="h-[85vh] max-h-[85vh] z-80" overlayClassName="z-80">
								<DrawerHandle />
								<DrawerHeader className="px-4 pb-3 pt-2">
									<DrawerTitle className="flex items-center justify-center gap-2 text-base font-semibold">
										Manage Tools
									</DrawerTitle>
								</DrawerHeader>
								<div className="min-h-0 flex-1 overflow-y-auto scrollbar-thin pb-6">
									{regularToolGroups.map((group) => (
										<div key={group.label}>
											<div className="px-4 pt-3 pb-1 text-xs text-muted-foreground/80 font-medium select-none">
												{group.label}
											</div>
											{group.tools.map((tool) => {
												const isDisabled = disabledToolsSet.has(tool.name);
												const ToolIcon = getToolIcon(tool.name);
												return (
													<div
														key={tool.name}
														className="flex w-full items-center gap-3 px-4 py-2 hover:bg-accent hover:text-accent-foreground transition-colors"
													>
														<ToolIcon className="size-4 shrink-0 text-muted-foreground" />
														<span className="flex-1 min-w-0 text-sm font-medium truncate">
															{formatToolName(tool.name)}
														</span>
														<Switch
															checked={!isDisabled}
															onCheckedChange={() => toggleTool(tool.name)}
															className="shrink-0"
														/>
													</div>
												);
											})}
										</div>
									))}
									{connectorToolGroups.length > 0 && (
										<div>
											<div className="px-4 pt-3 pb-1 text-xs text-muted-foreground/80 font-medium select-none">
												Connector Actions
											</div>
											{connectorToolGroups.map((group) => {
												const iconKey = group.connectorIcon ?? "";
												const iconInfo = CONNECTOR_TOOL_ICON_PATHS[iconKey];
												const toolNames = group.tools.map((t) => t.name);
												const allDisabled = toolNames.every((n) => disabledToolsSet.has(n));
												const isExpanded = expandedConnectorGroups.has(group.label);
												return (
													<Collapsible
														key={group.label}
														open={isExpanded}
														onOpenChange={(open) => setConnectorGroupExpanded(group.label, open)}
													>
														<div className="flex w-full items-center gap-3 px-4 py-2 hover:bg-accent hover:text-accent-foreground transition-colors">
															<CollapsibleTrigger asChild>
																<Button
																	type="button"
																	variant="ghost"
																	className="h-auto min-w-0 flex-1 justify-start gap-3 p-0 text-left hover:bg-transparent hover:text-inherit"
																>
																	{iconInfo ? (
																		<Image
																			src={iconInfo.src}
																			alt={iconInfo.alt}
																			width={18}
																			height={18}
																			className="size-[18px] shrink-0 select-none pointer-events-none"
																			draggable={false}
																		/>
																	) : (
																		<Wrench className="size-4 shrink-0 text-muted-foreground" />
																	)}
																	<span className="min-w-0 flex-1 truncate text-sm font-medium">
																		{group.label}
																	</span>
																	{isExpanded ? (
																		<ChevronDown className="size-4 shrink-0 text-muted-foreground" />
																	) : (
																		<ChevronRight className="size-4 shrink-0 text-muted-foreground" />
																	)}
																</Button>
															</CollapsibleTrigger>
															<Switch
																checked={!allDisabled}
																onCheckedChange={() => toggleToolGroup(toolNames)}
																className="shrink-0"
															/>
														</div>
														<CollapsibleContent className="pb-1">
															{group.tools.map((tool) => {
																const isDisabled = disabledToolsSet.has(tool.name);
																return (
																	<div
																		key={tool.name}
																		className={cn(
																			"ml-8 flex items-center gap-3 px-4 py-1.5 rounded-md transition-colors",
																			"hover:bg-accent hover:text-accent-foreground",
																			!isDisabled && "text-primary"
																		)}
																	>
																		<span className="min-w-0 flex-1 truncate text-sm">
																			{formatToolName(tool.name)}
																		</span>
																		<Switch
																			checked={!isDisabled}
																			onCheckedChange={() => toggleTool(tool.name)}
																			className="shrink-0"
																		/>
																	</div>
																);
															})}
														</CollapsibleContent>
													</Collapsible>
												);
											})}
										</div>
									)}
									{otherToolGroup && (
										<div>
											<div className="px-4 pt-3 pb-1 text-xs text-muted-foreground/80 font-medium select-none">
												{otherToolGroup.label}
											</div>
											{otherToolGroup.tools.map((tool) => {
												const isDisabled = disabledToolsSet.has(tool.name);
												const ToolIcon = getToolIcon(tool.name);
												return (
													<div
														key={tool.name}
														className="flex w-full items-center gap-3 px-4 py-2 hover:bg-accent hover:text-accent-foreground transition-colors"
													>
														<ToolIcon className="size-4 shrink-0 text-muted-foreground" />
														<span className="flex-1 min-w-0 text-sm font-medium truncate">
															{formatToolName(tool.name)}
														</span>
														<Switch
															checked={!isDisabled}
															onCheckedChange={() => toggleTool(tool.name)}
															className="shrink-0"
														/>
													</div>
												);
											})}
										</div>
									)}
									{!filteredTools?.length && (
										<div className="px-4 pt-3 pb-2">
											<Skeleton className="h-3 w-16 mb-2" />
											{["t1", "t2", "t3", "t4"].map((k) => (
												<div key={k} className="flex items-center gap-3 py-2">
													<Skeleton className="size-4 rounded shrink-0" />
													<Skeleton className="h-3.5 flex-1" />
													<Skeleton className="h-5 w-9 rounded-full shrink-0" />
												</div>
											))}
											<Skeleton className="h-3 w-24 mt-3 mb-2" />
											{["c1", "c2", "c3"].map((k) => (
												<div key={k} className="flex items-center gap-3 py-2">
													<Skeleton className="size-4 rounded shrink-0" />
													<Skeleton className="h-3.5 flex-1" />
													<Skeleton className="h-5 w-9 rounded-full shrink-0" />
												</div>
											))}
										</div>
									)}
								</div>
							</DrawerContent>
						</Drawer>
					</>
				) : (
					<DropdownMenu
						onOpenChange={(open) => {
							if (!open) {
								setToolsPopoverOpen(false);
								setOpenConnectorSubmenu(null);
							}
						}}
					>
						<DropdownMenuTrigger asChild>
							<TooltipIconButton
								tooltip="Upload files, manage tools and more"
								side="bottom"
								disableTooltip={toolsPopoverOpen}
								variant="ghost"
								size="icon"
								className="h-9 w-9 rounded-full p-0 font-semibold text-xs text-muted-foreground transition-colors dark:border-muted-foreground/15 hover:bg-foreground/10 hover:text-foreground"
								aria-label="Upload files, manage tools and more"
								data-joyride="connector-icon"
							>
								<Plus className="size-5" />
							</TooltipIconButton>
						</DropdownMenuTrigger>
						<DropdownMenuContent
							className="w-48"
							side="bottom"
							align="start"
							sideOffset={8}
							onCloseAutoFocus={(event) => event.preventDefault()}
						>
							<DropdownMenuItem onSelect={() => openUploadDialog()}>
								<Upload className="h-4 w-4" />
								Upload Files
							</DropdownMenuItem>
							<DropdownMenuItem onSelect={() => void handleScreenCapture()}>
								<Camera className="h-4 w-4" />
								Take a screenshot
							</DropdownMenuItem>
							{hasWebSearchTool && (
								<DropdownMenuItem
									onSelect={(event) => {
										event.preventDefault();
										toggleTool("web_search");
									}}
									className={cn(
										"hover:bg-accent hover:text-accent-foreground",
										isWebSearchEnabled && "text-primary"
									)}
								>
									<Globe className="h-4 w-4" />
									<span className="flex-1 min-w-0 truncate">Web Search</span>
									<Switch
										checked={isWebSearchEnabled}
										tabIndex={-1}
										className="pointer-events-none shrink-0 origin-right scale-[0.6]"
									/>
								</DropdownMenuItem>
							)}
							<DropdownMenuSub
								open={toolsPopoverOpen}
								onOpenChange={(open) => {
									setToolsPopoverOpen(open);
									if (!open) setOpenConnectorSubmenu(null);
								}}
							>
								<DropdownMenuSubTrigger>
									<Settings2 className="h-4 w-4" />
									Manage Tools
								</DropdownMenuSubTrigger>
								<DropdownMenuPortal>
									<DropdownMenuSubContent
										alignOffset={-192}
										collisionPadding={8}
										className="w-60 h-56 gap-1 overflow-y-auto overscroll-none"
										onScroll={() => setOpenConnectorSubmenu(null)}
									>
										{regularToolGroups.map((group) => (
											<div key={group.label}>
												<div className="px-2 pt-1.5 pb-0.5 text-[10px] text-muted-foreground/80 font-normal select-none">
													{group.label}
												</div>
												{group.tools.map((tool) => {
													const isDisabled = disabledToolsSet.has(tool.name);
													const ToolIcon = getToolIcon(tool.name);
													return (
														<DropdownMenuItem
															key={tool.name}
															onSelect={(e) => {
																e.preventDefault();
																toggleTool(tool.name);
															}}
															className={cn(
																"mb-1 last:mb-0 transition-all",
																"hover:bg-accent hover:text-accent-foreground",
																!isDisabled && "text-primary"
															)}
														>
															<ToolIcon className="h-4 w-4" />
															<span className="flex-1 min-w-0 truncate">
																{formatToolName(tool.name)}
															</span>
															<Switch
																checked={!isDisabled}
																tabIndex={-1}
																className="pointer-events-none shrink-0 origin-right scale-[0.6]"
															/>
														</DropdownMenuItem>
													);
												})}
											</div>
										))}
										{connectorToolGroups.length > 0 && (
											<div>
												<div className="px-2 pt-1.5 pb-0.5 text-[10px] text-muted-foreground/80 font-normal select-none">
													Connector Actions
												</div>
												{connectorToolGroups.map((group) => {
													const iconKey = group.connectorIcon ?? "";
													const iconInfo = CONNECTOR_TOOL_ICON_PATHS[iconKey];
													const toolNames = group.tools.map((t) => t.name);
													const allDisabled = toolNames.every((n) => disabledToolsSet.has(n));
													return (
														<DropdownMenuSub
															key={group.label}
															open={openConnectorSubmenu === group.label}
															onOpenChange={(open) =>
																setOpenConnectorSubmenu(open ? group.label : null)
															}
														>
															<DropdownMenuSubTrigger
																className={cn(
																	"mb-1 last:mb-0 transition-all",
																	"hover:bg-accent hover:text-accent-foreground",
																	"gap-1 [&>svg:last-child]:ml-0",
																	!allDisabled && "text-primary"
																)}
															>
																{iconInfo ? (
																	<Image
																		src={iconInfo.src}
																		alt={iconInfo.alt}
																		width={16}
																		height={16}
																		className="h-4 w-4 shrink-0 select-none pointer-events-none"
																		draggable={false}
																	/>
																) : (
																	<Wrench className="h-4 w-4" />
																)}
																<span className="min-w-0 flex-1 truncate">{group.label}</span>
																<Switch
																	checked={!allDisabled}
																	tabIndex={-1}
																	onPointerDown={(event) => event.stopPropagation()}
																	onClick={(event) => event.stopPropagation()}
																	onCheckedChange={() => toggleToolGroup(toolNames)}
																	className="mr-2 shrink-0 origin-right scale-[0.6]"
																/>
															</DropdownMenuSubTrigger>
															<DropdownMenuPortal>
																<DropdownMenuSubContent
																	collisionPadding={8}
																	className="w-60 max-h-56 overflow-y-auto overscroll-none"
																>
																	{group.tools.map((tool) => {
																		const isDisabled = disabledToolsSet.has(tool.name);
																		return (
																			<DropdownMenuItem
																				key={tool.name}
																				onSelect={(e) => {
																					e.preventDefault();
																					toggleTool(tool.name);
																				}}
																				className={cn(
																					"mb-1 last:mb-0 transition-all",
																					"hover:bg-accent hover:text-accent-foreground",
																					!isDisabled && "text-primary"
																				)}
																			>
																				<span className="min-w-0 flex-1 truncate">
																					{formatToolName(tool.name)}
																				</span>
																				<Switch
																					checked={!isDisabled}
																					tabIndex={-1}
																					className="pointer-events-none shrink-0 origin-right scale-[0.6]"
																				/>
																			</DropdownMenuItem>
																		);
																	})}
																</DropdownMenuSubContent>
															</DropdownMenuPortal>
														</DropdownMenuSub>
													);
												})}
											</div>
										)}
										{otherToolGroup && (
											<div>
												<div className="px-2 pt-1.5 pb-0.5 text-[10px] text-muted-foreground/80 font-normal select-none">
													{otherToolGroup.label}
												</div>
												{otherToolGroup.tools.map((tool) => {
													const isDisabled = disabledToolsSet.has(tool.name);
													const ToolIcon = getToolIcon(tool.name);
													return (
														<DropdownMenuItem
															key={tool.name}
															onSelect={(e) => {
																e.preventDefault();
																toggleTool(tool.name);
															}}
															className={cn(
																"mb-1 last:mb-0 transition-all",
																"hover:bg-accent hover:text-accent-foreground",
																!isDisabled && "text-primary"
															)}
														>
															<ToolIcon className="h-4 w-4" />
															<span className="flex-1 min-w-0 truncate">
																{formatToolName(tool.name)}
															</span>
															<Switch
																checked={!isDisabled}
																tabIndex={-1}
																className="pointer-events-none shrink-0 origin-right scale-[0.6]"
															/>
														</DropdownMenuItem>
													);
												})}
											</div>
										)}
										{!filteredTools?.length && (
											<div className="px-2 pt-1.5 pb-1">
												<Skeleton className="h-2 w-12 mb-1.5" />
												{["dt1", "dt2", "dt3", "dt4"].map((k) => (
													<div key={k} className="flex items-center gap-2 py-1">
														<Skeleton className="h-4 w-4 rounded shrink-0" />
														<Skeleton className="h-3 flex-1" />
														<Skeleton className="h-4 w-8 rounded-full shrink-0" />
													</div>
												))}
											</div>
										)}
									</DropdownMenuSubContent>
								</DropdownMenuPortal>
							</DropdownMenuSub>
						</DropdownMenuContent>
					</DropdownMenu>
				)}
			</div>
			{!hasModelConfigured && (
				<div className="flex items-center gap-1.5 text-amber-600 dark:text-amber-400 text-xs">
					<AlertCircle className="size-3" />
					<span>Select a model</span>
				</div>
			)}
			<div className="flex items-center gap-2">
				<AuiIf condition={({ thread }) => !thread.isRunning}>
					<ComposerPrimitive.Send asChild disabled={isSendDisabled}>
						<TooltipIconButton
							tooltip={
								isBlockedByOtherUser
									? "Wait for AI to finish responding"
									: !hasModelConfigured
										? "Please select a model from the header to start chatting"
										: isComposerEmpty
											? "Enter a message or add a screenshot to send"
											: "Send message"
							}
							side="bottom"
							type="submit"
							variant="default"
							size="icon"
							className={cn(
								"aui-composer-send size-9 rounded-full",
								isSendDisabled && "cursor-not-allowed opacity-50"
							)}
							aria-label="Send message"
							disabled={isSendDisabled}
						>
							<ArrowUpIcon className="aui-composer-send-icon size-5" />
						</TooltipIconButton>
					</ComposerPrimitive.Send>
				</AuiIf>

				<AuiIf condition={({ thread }) => thread.isRunning}>
					<ComposerPrimitive.Cancel asChild>
						<Button
							type="button"
							variant="default"
							size="icon"
							className="aui-composer-cancel size-9 rounded-full"
							aria-label="Stop generating"
						>
							<SquareIcon className="aui-composer-cancel-icon size-3.5 fill-current" />
						</Button>
					</ComposerPrimitive.Cancel>
				</AuiIf>
			</div>
		</div>
	);
};

/** Friendly tool name (delegates to ``getToolDisplayName``). */
function formatToolName(name: string): string {
	return getToolDisplayName(name);
}

interface ToolGroup {
	label: string;
	tools: string[];
	connectorIcon?: string;
	tooltip?: string;
}

const TOOL_GROUPS: ToolGroup[] = [
	{
		label: "Research",
		tools: ["scrape_webpage"],
	},
	{
		label: "Generate",
		tools: [
			"generate_podcast",
			"generate_video_presentation",
			"generate_report",
			"generate_resume",
			"generate_image",
		],
	},
	{
		label: "Memory",
		tools: ["update_memory"],
	},
	{
		label: "Gmail",
		tools: [
			"search_gmail",
			"read_gmail_email",
			"create_gmail_draft",
			"update_gmail_draft",
			"send_gmail_email",
			"trash_gmail_email",
		],
		connectorIcon: "gmail",
		tooltip: "Search, read, draft, update, send, and trash emails in Gmail",
	},
	{
		label: "Google Calendar",
		tools: [
			"search_calendar_events",
			"create_calendar_event",
			"update_calendar_event",
			"delete_calendar_event",
		],
		connectorIcon: "google_calendar",
		tooltip: "Search, create, update, and delete events in Google Calendar",
	},
	{
		label: "Google Drive",
		tools: ["create_google_drive_file", "delete_google_drive_file"],
		connectorIcon: "google_drive",
		tooltip: "Create and delete files in Google Drive",
	},
	{
		label: "OneDrive",
		tools: ["create_onedrive_file", "delete_onedrive_file"],
		connectorIcon: "onedrive",
		tooltip: "Create and delete files in OneDrive",
	},
	{
		label: "Dropbox",
		tools: ["create_dropbox_file", "delete_dropbox_file"],
		connectorIcon: "dropbox",
		tooltip: "Create and delete files in Dropbox",
	},
	{
		label: "Notion",
		tools: ["create_notion_page", "update_notion_page", "delete_notion_page"],
		connectorIcon: "notion",
		tooltip: "Create, update, and delete pages in Notion",
	},
	{
		label: "Linear",
		tools: ["create_linear_issue", "update_linear_issue", "delete_linear_issue"],
		connectorIcon: "linear",
		tooltip: "Create, update, and delete issues in Linear",
	},
	{
		label: "Jira",
		tools: ["create_jira_issue", "update_jira_issue", "delete_jira_issue"],
		connectorIcon: "jira",
		tooltip: "Create, update, and delete issues in Jira",
	},
	{
		label: "Confluence",
		tools: ["create_confluence_page", "update_confluence_page", "delete_confluence_page"],
		connectorIcon: "confluence",
		tooltip: "Create, update, and delete pages in Confluence",
	},
	{
		label: "Discord",
		tools: ["list_discord_channels", "read_discord_messages", "send_discord_message"],
		connectorIcon: "discord",
		tooltip: "List channels, read messages, and send messages in Discord",
	},
	{
		label: "Microsoft Teams",
		tools: ["list_teams_channels", "read_teams_messages", "send_teams_message"],
		connectorIcon: "teams",
		tooltip: "List channels, read messages, and send messages in Microsoft Teams",
	},
	{
		label: "Luma",
		tools: ["list_luma_events", "read_luma_event", "create_luma_event"],
		connectorIcon: "luma",
		tooltip: "List, read, and create events in Luma",
	},
];

const EditComposer: FC = () => {
	return (
		<MessagePrimitive.Root className="aui-edit-composer-wrapper mx-auto flex w-full max-w-(--thread-max-width) flex-col px-2 py-3">
			<ComposerPrimitive.Root className="aui-edit-composer-root ml-auto flex w-full max-w-[85%] flex-col rounded-2xl bg-muted">
				<ComposerPrimitive.Input
					className="aui-edit-composer-input min-h-14 w-full resize-none bg-transparent p-4 text-foreground text-sm outline-none"
					autoFocus
				/>
				<div className="aui-edit-composer-footer mx-3 mb-3 flex items-center gap-2 self-end">
					<ComposerPrimitive.Cancel asChild>
						<Button variant="ghost" size="sm">
							Cancel
						</Button>
					</ComposerPrimitive.Cancel>
					<ComposerPrimitive.Send asChild>
						<Button size="sm">Update</Button>
					</ComposerPrimitive.Send>
				</div>
			</ComposerPrimitive.Root>
		</MessagePrimitive.Root>
	);
};
