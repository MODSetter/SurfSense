import {
	AuiIf,
	ComposerPrimitive,
	MessagePrimitive,
	ThreadPrimitive,
	useAui,
	useAuiState,
	useThreadViewportStore,
} from "@assistant-ui/react";
import { useAtom, useAtomValue, useSetAtom } from "jotai";
import {
	AlertCircle,
	ArrowDownIcon,
	ArrowUpIcon,
	ChevronDown,
	ChevronUp,
	Clipboard,
	Dot,
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
import { createPortal } from "react-dom";
import {
	agentToolsAtom,
	disabledToolsAtom,
	hydrateDisabledToolsAtom,
	toggleToolAtom,
} from "@/atoms/agent-tools/agent-tools.atoms";
import { chatSessionStateAtom } from "@/atoms/chat/chat-session-state.atom";
import {
	mentionedDocumentsAtom,
	sidebarSelectedDocumentsAtom,
} from "@/atoms/chat/mentioned-documents.atom";
import { connectorDialogOpenAtom } from "@/atoms/connector-dialog/connector-dialog.atoms";
import { connectorsAtom } from "@/atoms/connectors/connector-query.atoms";
import { documentsSidebarOpenAtom } from "@/atoms/documents/ui.atoms";
import { membersAtom } from "@/atoms/members/members-query.atoms";
import {
	globalNewLLMConfigsAtom,
	llmPreferencesAtom,
	newLLMConfigsAtom,
} from "@/atoms/new-llm-config/new-llm-config-query.atoms";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import { AssistantMessage } from "@/components/assistant-ui/assistant-message";
import { ChatSessionStatus } from "@/components/assistant-ui/chat-session-status";
import { ConnectorIndicator } from "@/components/assistant-ui/connector-popup";
import { useDocumentUploadDialog } from "@/components/assistant-ui/document-upload-popup";
import {
	InlineMentionEditor,
	type InlineMentionEditorRef,
} from "@/components/assistant-ui/inline-mention-editor";
import { TooltipIconButton } from "@/components/assistant-ui/tooltip-icon-button";
import { UserMessage } from "@/components/assistant-ui/user-message";
import { SLIDEOUT_PANEL_OPENED_EVENT } from "@/components/layout/ui/sidebar/SidebarSlideOutPanel";
import {
	DocumentMentionPicker,
	type DocumentMentionPickerRef,
} from "@/components/new-chat/document-mention-picker";
import { PromptPicker, type PromptPickerRef } from "@/components/new-chat/prompt-picker";
import { Avatar, AvatarFallback, AvatarGroup } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent, DrawerHandle, DrawerTitle } from "@/components/ui/drawer";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Switch } from "@/components/ui/switch";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import {
	CONNECTOR_ICON_TO_TYPES,
	CONNECTOR_TOOL_ICON_PATHS,
	getToolIcon,
} from "@/contracts/enums/toolIcons";
import type { Document } from "@/contracts/types/document.types";
import { useBatchCommentsPreload } from "@/hooks/use-comments";
import { useCommentsSync } from "@/hooks/use-comments-sync";
import { useMediaQuery } from "@/hooks/use-media-query";
import { useElectronAPI } from "@/hooks/use-platform";
import { cn } from "@/lib/utils";

const COMPOSER_PLACEHOLDER = "Ask anything · Type / for prompts · Type @ to mention docs";

export const Thread: FC = () => {
	return <ThreadContent />;
};

const ThreadContent: FC = () => {
	return (
		<ThreadPrimitive.Root
			className="aui-root aui-thread-root @container flex h-full min-h-0 flex-col bg-main-panel"
			style={{
				["--thread-max-width" as string]: "44rem",
			}}
		>
			<ThreadPrimitive.Viewport
				turnAnchor="top"
				className="aui-thread-viewport relative flex flex-1 min-h-0 flex-col overflow-y-auto px-4 pt-4"
				style={{ scrollbarGutter: "stable" }}
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

				<ThreadPrimitive.ViewportFooter
					className="aui-thread-viewport-footer sticky bottom-0 z-10 mx-auto flex w-full max-w-(--thread-max-width) flex-col gap-4 overflow-visible rounded-t-3xl bg-main-panel pb-4 md:pb-6"
					style={{ paddingBottom: "max(1rem, env(safe-area-inset-bottom))" }}
				>
					<ThreadScrollToBottom />
					<AuiIf condition={({ thread }) => !thread.isEmpty}>
						<div className="fade-in slide-in-from-bottom-4 animate-in duration-500 ease-out fill-mode-both">
							<Composer />
						</div>
					</AuiIf>
				</ThreadPrimitive.ViewportFooter>
			</ThreadPrimitive.Viewport>
		</ThreadPrimitive.Root>
	);
};

const ThreadScrollToBottom: FC = () => {
	return (
		<ThreadPrimitive.ScrollToBottom asChild>
			<TooltipIconButton
				tooltip="Scroll to bottom"
				variant="outline"
				className="aui-thread-scroll-to-bottom -top-12 absolute z-10 self-center rounded-full p-4 disabled:invisible dark:bg-main-panel dark:hover:bg-accent"
			>
				<ArrowDownIcon />
			</TooltipIconButton>
		</ThreadPrimitive.ScrollToBottom>
	);
};

const getTimeBasedGreeting = (user?: { display_name?: string | null; email?: string }): string => {
	const hour = new Date().getHours();

	// Extract first name: prefer display_name, fall back to email extraction
	let firstName: string | null = null;

	if (user?.display_name?.trim()) {
		// Use display_name if available and not empty
		// Extract first name from display_name (take first word)
		const nameParts = user.display_name.trim().split(/\s+/);
		firstName = nameParts[0].charAt(0).toUpperCase() + nameParts[0].slice(1).toLowerCase();
	} else if (user?.email) {
		// Fall back to email extraction if display_name is not available
		firstName =
			user.email.split("@")[0].split(".")[0].charAt(0).toUpperCase() +
			user.email.split("@")[0].split(".")[0].slice(1);
	}

	// Array of greeting variations for each time period
	const morningGreetings = ["Good morning", "Fresh start today", "Morning", "Hey there"];

	const afternoonGreetings = ["Good afternoon", "Afternoon", "Hey there", "Hi there"];

	const eveningGreetings = ["Good evening", "Evening", "Hey there", "Hi there"];

	const nightGreetings = ["Good night", "Evening", "Hey there", "Winding down"];

	const lateNightGreetings = ["Still up", "Night owl mode", "Up past bedtime", "Hi there"];

	// Select a random greeting based on time
	let greeting: string;
	if (hour < 5) {
		// Late night: midnight to 5 AM
		greeting = lateNightGreetings[Math.floor(Math.random() * lateNightGreetings.length)];
	} else if (hour < 12) {
		greeting = morningGreetings[Math.floor(Math.random() * morningGreetings.length)];
	} else if (hour < 18) {
		greeting = afternoonGreetings[Math.floor(Math.random() * afternoonGreetings.length)];
	} else if (hour < 22) {
		greeting = eveningGreetings[Math.floor(Math.random() * eveningGreetings.length)];
	} else {
		// Night: 10 PM to midnight
		greeting = nightGreetings[Math.floor(Math.random() * nightGreetings.length)];
	}

	// Add personalization with first name if available
	if (firstName) {
		return `${greeting}, ${firstName}!`;
	}

	return `${greeting}!`;
};

const ThreadWelcome: FC = () => {
	const { data: user } = useAtomValue(currentUserAtom);

	// Memoize greeting so it doesn't change on re-renders (only on user change)
	const greeting = useMemo(() => getTimeBasedGreeting(user), [user]);

	return (
		<div className="aui-thread-welcome-root mx-auto flex w-full max-w-(--thread-max-width) grow flex-col items-center px-4 relative">
			{/* Greeting positioned above the composer */}
			<div className="aui-thread-welcome-message absolute bottom-[calc(50%+5rem)] left-0 right-0 flex flex-col items-center text-center">
				<h1 className="aui-thread-welcome-message-inner text-3xl md:text-5xl select-none">
					{greeting}
				</h1>
			</div>
			{/* Composer - top edge fixed, expands downward only */}
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

const ConnectToolsBanner: FC<{ isThreadEmpty: boolean }> = ({ isThreadEmpty }) => {
	const { data: connectors } = useAtomValue(connectorsAtom);
	const setConnectorDialogOpen = useSetAtom(connectorDialogOpenAtom);
	const [dismissed, setDismissed] = useState(() => {
		if (typeof window === "undefined") return false;
		return localStorage.getItem(BANNER_DISMISSED_KEY) === "true";
	});

	const hasConnectors = (connectors?.length ?? 0) > 0;

	if (dismissed || hasConnectors || !isThreadEmpty) return null;

	const handleDismiss = (e: React.MouseEvent) => {
		e.stopPropagation();
		setDismissed(true);
		localStorage.setItem(BANNER_DISMISSED_KEY, "true");
	};

	return (
		<div className="border-t border-border/50">
			<div className="flex w-full items-center gap-2.5 px-4 py-2.5">
				<button
					type="button"
					className="flex flex-1 items-center gap-2.5 text-left cursor-pointer"
					onClick={() => setConnectorDialogOpen(true)}
				>
					<Unplug className="size-4 text-muted-foreground shrink-0" />
					<span className="text-[13px] text-muted-foreground/80 flex-1">Connect your tools</span>
					<AvatarGroup className="shrink-0">
						{BANNER_CONNECTORS.map(({ type }, i) => (
							<Avatar
								key={type}
								className="size-6"
								style={{ zIndex: BANNER_CONNECTORS.length - i }}
							>
								<AvatarFallback className="bg-muted text-[10px]">
									{getConnectorIcon(type, "size-3.5")}
								</AvatarFallback>
							</Avatar>
						))}
					</AvatarGroup>
				</button>
				<button
					type="button"
					onClick={handleDismiss}
					className="shrink-0 ml-0.5 p-1.5 -mr-1 text-muted-foreground/40 hover:text-foreground transition-colors cursor-pointer"
					aria-label="Dismiss"
				>
					<X className="size-3.5 text-muted-foreground" />
				</button>
			</div>
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
					<button
						type="button"
						onClick={() => setExpanded((v) => !v)}
						className="flex items-center text-muted-foreground hover:text-foreground transition-colors"
					>
						{expanded ? <ChevronUp className="size-3.5" /> : <ChevronDown className="size-3.5" />}
					</button>
				)}
				<button
					type="button"
					onClick={onDismiss}
					className="flex items-center text-muted-foreground hover:text-foreground transition-colors"
				>
					<X className="size-3.5" />
				</button>
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
	// Document mention state (atoms persist across component remounts)
	const [mentionedDocuments, setMentionedDocuments] = useAtom(mentionedDocumentsAtom);
	const setSidebarDocs = useSetAtom(sidebarSelectedDocumentsAtom);
	const [showDocumentPopover, setShowDocumentPopover] = useState(false);
	const [showPromptPicker, setShowPromptPicker] = useState(false);
	const [mentionQuery, setMentionQuery] = useState("");
	const [actionQuery, setActionQuery] = useState("");
	const editorRef = useRef<InlineMentionEditorRef>(null);
	const editorContainerRef = useRef<HTMLDivElement>(null);
	const composerBoxRef = useRef<HTMLDivElement>(null);
	const documentPickerRef = useRef<DocumentMentionPickerRef>(null);
	const promptPickerRef = useRef<PromptPickerRef>(null);
	const { search_space_id, chat_id } = useParams();
	const aui = useAui();
	const threadViewportStore = useThreadViewportStore();
	const hasAutoFocusedRef = useRef(false);
	const submitCleanupRef = useRef<(() => void) | null>(null);

	useEffect(() => {
		return () => {
			submitCleanupRef.current?.();
		};
	}, []);

	const electronAPI = useElectronAPI();
	const [clipboardInitialText, setClipboardInitialText] = useState<string | undefined>();
	const clipboardLoadedRef = useRef(false);
	useEffect(() => {
		if (!electronAPI || clipboardLoadedRef.current) return;
		clipboardLoadedRef.current = true;
		electronAPI.getQuickAskText().then((text) => {
			if (text) {
				setClipboardInitialText(text);
			}
		});
	}, [electronAPI]);

	const isThreadEmpty = useAuiState(({ thread }) => thread.isEmpty);
	const isThreadRunning = useAuiState(({ thread }) => thread.isRunning);

	const currentPlaceholder = COMPOSER_PLACEHOLDER;

	// Live collaboration state
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

	// Sync comments for the entire thread via Zero (one subscription per thread)
	useCommentsSync(threadId);

	// Batch-prefetch comments for all assistant messages so individual useComments
	// hooks never fire their own network requests (eliminates N+1 API calls).
	// Return a primitive string from the selector so useSyncExternalStore can
	// compare snapshots by value and avoid infinite re-render loops.
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

	// Auto-focus editor on new chat page after mount
	useEffect(() => {
		if (isThreadEmpty && !hasAutoFocusedRef.current && editorRef.current) {
			const timeoutId = setTimeout(() => {
				editorRef.current?.focus();
				hasAutoFocusedRef.current = true;
			}, 100);
			return () => clearTimeout(timeoutId);
		}
	}, [isThreadEmpty]);

	// Close document picker when a slide-out panel (inbox, shared/private chats) opens
	useEffect(() => {
		const handler = () => {
			setShowDocumentPopover(false);
			setMentionQuery("");
		};
		window.addEventListener(SLIDEOUT_PANEL_OPENED_EVENT, handler);
		return () => window.removeEventListener(SLIDEOUT_PANEL_OPENED_EVENT, handler);
	}, []);

	// Sync editor text with assistant-ui composer runtime
	const handleEditorChange = useCallback(
		(text: string) => {
			aui.composer().setText(text);
		},
		[aui]
	);

	// Open document picker when @ mention is triggered
	const handleMentionTrigger = useCallback((query: string) => {
		setShowDocumentPopover(true);
		setMentionQuery(query);
	}, []);

	// Close document picker and reset query
	const handleMentionClose = useCallback(() => {
		if (showDocumentPopover) {
			setShowDocumentPopover(false);
			setMentionQuery("");
		}
	}, [showDocumentPopover]);

	// Open action picker when / is triggered
	const handleActionTrigger = useCallback((query: string) => {
		setShowPromptPicker(true);
		setActionQuery(query);
	}, []);

	// Close action picker and reset query
	const handleActionClose = useCallback(() => {
		if (showPromptPicker) {
			setShowPromptPicker(false);
			setActionQuery("");
		}
	}, [showPromptPicker]);

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
			setClipboardInitialText(undefined);
		},
		[clipboardInitialText, electronAPI, aui]
	);

	// Keyboard navigation for document/action picker (arrow keys, Enter, Escape)
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
					setShowDocumentPopover(false);
					setMentionQuery("");
					return;
				}
			}
		},
		[showDocumentPopover, showPromptPicker]
	);

	// Submit message (blocked during streaming, document picker open, or AI responding to another user)
	const handleSubmit = useCallback(() => {
		if (isThreadRunning || isBlockedByOtherUser) {
			return;
		}
		if (!showDocumentPopover && !showPromptPicker) {
			if (clipboardInitialText) {
				const userText = editorRef.current?.getText() ?? "";
				const combined = userText ? `${userText}\n\n${clipboardInitialText}` : clipboardInitialText;
				aui.composer().setText(combined);
				setClipboardInitialText(undefined);
			}
			aui.composer().send();
			editorRef.current?.clear();
			setMentionedDocuments([]);
			setSidebarDocs([]);
		}
		if (isThreadRunning || isBlockedByOtherUser) return;
		if (showDocumentPopover) return;

		const viewportEl = document.querySelector(".aui-thread-viewport");
		const heightBefore = viewportEl?.scrollHeight ?? 0;

		aui.composer().send();
		editorRef.current?.clear();
		setMentionedDocuments([]);
		setSidebarDocs([]);

		// With turnAnchor="top", ViewportSlack adds min-height to the last
		// assistant message so that scrolling-to-bottom actually positions the
		// user message at the TOP of the viewport. That slack height is
		// calculated asynchronously (ResizeObserver → style → layout).
		//
		// We poll via rAF for ~2 s, re-scrolling whenever scrollHeight changes
		// (user msg render → assistant placeholder → ViewportSlack min-height →
		// first streamed content). Backup setTimeout calls cover cases where
		// the batcher's 50 ms throttle delays the DOM update past the rAF.
		const scrollToBottom = () =>
			threadViewportStore.getState().scrollToBottom({ behavior: "instant" });

		let lastHeight = heightBefore;
		let frames = 0;
		let cancelled = false;
		const POLL_FRAMES = 120;

		const pollAndScroll = () => {
			if (cancelled) return;
			const el = document.querySelector(".aui-thread-viewport");
			if (el) {
				const h = el.scrollHeight;
				if (h !== lastHeight) {
					lastHeight = h;
					scrollToBottom();
				}
			}
			if (++frames < POLL_FRAMES) {
				requestAnimationFrame(pollAndScroll);
			}
		};
		requestAnimationFrame(pollAndScroll);

		const t1 = setTimeout(scrollToBottom, 100);
		const t2 = setTimeout(scrollToBottom, 300);
		const t3 = setTimeout(scrollToBottom, 600);

		// Cleanup if component unmounts during the polling window. The ref is
		// checked inside pollAndScroll; timeouts are cleared in the return below.
		// Store cleanup fn so it can be called from a useEffect cleanup if needed.
		submitCleanupRef.current = () => {
			cancelled = true;
			clearTimeout(t1);
			clearTimeout(t2);
			clearTimeout(t3);
		};
	}, [
		showDocumentPopover,
		showPromptPicker,
		isThreadRunning,
		isBlockedByOtherUser,
		clipboardInitialText,
		aui,
		setMentionedDocuments,
		setSidebarDocs,
		threadViewportStore,
	]);

	const handleDocumentRemove = useCallback(
		(docId: number, docType?: string) => {
			setMentionedDocuments((prev) =>
				prev.filter((doc) => !(doc.id === docId && doc.document_type === docType))
			);
		},
		[setMentionedDocuments]
	);

	const handleDocumentsMention = useCallback(
		(documents: Pick<Document, "id" | "title" | "document_type">[]) => {
			const existingKeys = new Set(mentionedDocuments.map((d) => `${d.document_type}:${d.id}`));
			const newDocs = documents.filter(
				(doc) => !existingKeys.has(`${doc.document_type}:${doc.id}`)
			);

			for (const doc of newDocs) {
				editorRef.current?.insertDocumentChip(doc);
			}

			setMentionedDocuments((prev) => {
				const existingKeySet = new Set(prev.map((d) => `${d.document_type}:${d.id}`));
				const uniqueNewDocs = documents.filter(
					(doc) => !existingKeySet.has(`${doc.document_type}:${doc.id}`)
				);
				return [...prev, ...uniqueNewDocs];
			});

			setMentionQuery("");
		},
		[mentionedDocuments, setMentionedDocuments]
	);

	return (
		<ComposerPrimitive.Root
			className="aui-composer-root relative flex w-full flex-col gap-2"
			style={showPromptPicker && clipboardInitialText ? { marginBottom: 220 } : undefined}
		>
			<ChatSessionStatus
				isAiResponding={isAiResponding}
				respondingToUserId={respondingToUserId}
				currentUserId={currentUser?.id ?? null}
				members={members ?? []}
			/>
			<div
				ref={composerBoxRef}
				className="aui-composer-attachment-dropzone flex w-full flex-col overflow-hidden rounded-2xl border-input bg-muted pt-2 outline-none transition-shadow"
			>
				{clipboardInitialText && (
					<ClipboardChip
						text={clipboardInitialText}
						onDismiss={() => setClipboardInitialText(undefined)}
					/>
				)}
				{/* Inline editor with @mention support */}
				<div ref={editorContainerRef} className="aui-composer-input-wrapper px-4 pt-3 pb-6">
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
						className="min-h-[24px]"
					/>
				</div>
				{/* Document picker popover (portal to body for proper z-index stacking) */}
				{showDocumentPopover &&
					typeof document !== "undefined" &&
					createPortal(
						<DocumentMentionPicker
							ref={documentPickerRef}
							searchSpaceId={Number(search_space_id)}
							onSelectionChange={handleDocumentsMention}
							onDone={() => {
								setShowDocumentPopover(false);
								setMentionQuery("");
							}}
							initialSelectedDocuments={mentionedDocuments}
							externalSearch={mentionQuery}
							containerStyle={{
								bottom: editorContainerRef.current
									? `${window.innerHeight - editorContainerRef.current.getBoundingClientRect().top + 8}px`
									: "200px",
								left: editorContainerRef.current
									? `${editorContainerRef.current.getBoundingClientRect().left}px`
									: "50%",
							}}
						/>,
						document.body
					)}
				{showPromptPicker &&
					typeof document !== "undefined" &&
					createPortal(
						<PromptPicker
							ref={promptPickerRef}
							onSelect={clipboardInitialText ? handleQuickAskSelect : handleActionSelect}
							onDone={() => {
								setShowPromptPicker(false);
								setActionQuery("");
							}}
							externalSearch={actionQuery}
							containerStyle={{
								position: "fixed",
								...(clipboardInitialText && composerBoxRef.current
									? { top: `${composerBoxRef.current.getBoundingClientRect().bottom + 8}px` }
									: {
											bottom: editorContainerRef.current
												? `${window.innerHeight - editorContainerRef.current.getBoundingClientRect().top + 8}px`
												: "200px",
										}),
								left: editorContainerRef.current
									? `${editorContainerRef.current.getBoundingClientRect().left}px`
									: "50%",
								zIndex: 50,
							}}
						/>,
						document.body
					)}
				<ComposerAction isBlockedByOtherUser={isBlockedByOtherUser} />
				<ConnectorIndicator showTrigger={false} />
				<ConnectToolsBanner isThreadEmpty={isThreadEmpty} />
			</div>
		</ComposerPrimitive.Root>
	);
};

interface ComposerActionProps {
	isBlockedByOtherUser?: boolean;
}

const ComposerAction: FC<ComposerActionProps> = ({ isBlockedByOtherUser = false }) => {
	const mentionedDocuments = useAtomValue(mentionedDocumentsAtom);
	const sidebarDocs = useAtomValue(sidebarSelectedDocumentsAtom);
	const setDocumentsSidebarOpen = useSetAtom(documentsSidebarOpenAtom);
	const setConnectorDialogOpen = useSetAtom(connectorDialogOpenAtom);
	const [toolsPopoverOpen, setToolsPopoverOpen] = useState(false);
	const isDesktop = useMediaQuery("(min-width: 640px)");
	const { openDialog: openUploadDialog } = useDocumentUploadDialog();
	const [toolsScrollPos, setToolsScrollPos] = useState<"top" | "middle" | "bottom">("top");
	const toolsRafRef = useRef<number>();
	const handleToolsScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
		const el = e.currentTarget;
		if (toolsRafRef.current) return;
		toolsRafRef.current = requestAnimationFrame(() => {
			const atTop = el.scrollTop <= 2;
			const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight <= 2;
			setToolsScrollPos(atTop ? "top" : atBottom ? "bottom" : "middle");
			toolsRafRef.current = undefined;
		});
	}, []);
	useEffect(
		() => () => {
			if (toolsRafRef.current) cancelAnimationFrame(toolsRafRef.current);
		},
		[]
	);
	const isComposerTextEmpty = useAuiState(({ composer }) => {
		const text = composer.text?.trim() || "";
		return text.length === 0;
	});
	const isComposerEmpty = isComposerTextEmpty && mentionedDocuments.length === 0;

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
		<div className="aui-composer-action-wrapper relative mx-3 mb-2 flex items-center justify-between">
			<div className="flex items-center gap-1">
				{!isDesktop ? (
					<>
						<DropdownMenu>
							<DropdownMenuTrigger asChild>
								<Button
									variant="ghost"
									size="icon"
									className="size-[34px] rounded-full p-1 font-semibold text-xs hover:bg-muted-foreground/15 dark:border-muted-foreground/15 dark:hover:bg-muted-foreground/30"
									aria-label="More actions"
									data-joyride="connector-icon"
								>
									<Plus className="size-4" />
								</Button>
							</DropdownMenuTrigger>
							<DropdownMenuContent side="bottom" align="start" sideOffset={8}>
								<DropdownMenuItem onSelect={() => setToolsPopoverOpen(true)}>
									<Settings2 className="size-4" />
									Manage Tools
								</DropdownMenuItem>
								<DropdownMenuItem onSelect={() => openUploadDialog()}>
									<Upload className="size-4" />
									Upload Files
								</DropdownMenuItem>
							</DropdownMenuContent>
						</DropdownMenu>
						<Drawer open={toolsPopoverOpen} onOpenChange={setToolsPopoverOpen}>
							<DrawerContent className="max-h-[60dvh]">
								<DrawerHandle />
								<div className="px-4 py-2">
									<DrawerTitle className="text-sm font-medium">Manage Tools</DrawerTitle>
								</div>
								<div className="overflow-y-auto pb-6" onScroll={handleToolsScroll}>
									{groupedTools
										.filter((g) => !g.connectorIcon)
										.map((group) => (
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
															className="flex w-full items-center gap-3 px-4 py-2 hover:bg-muted-foreground/10 transition-colors"
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
									{groupedTools.some((g) => g.connectorIcon) && (
										<div>
											<div className="px-4 pt-3 pb-1 text-xs text-muted-foreground/80 font-medium select-none">
												Connector Actions
											</div>
											{groupedTools
												.filter((g) => g.connectorIcon)
												.map((group) => {
													const iconKey = group.connectorIcon ?? "";
													const iconInfo = CONNECTOR_TOOL_ICON_PATHS[iconKey];
													const toolNames = group.tools.map((t) => t.name);
													const allDisabled = toolNames.every((n) => disabledToolsSet.has(n));
													return (
														<div
															key={group.label}
															className="flex w-full items-center gap-3 px-4 py-2 hover:bg-muted-foreground/10 transition-colors"
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
															<span className="flex-1 min-w-0 text-sm font-medium truncate">
																{group.label}
															</span>
															<Switch
																checked={!allDisabled}
																onCheckedChange={() => toggleToolGroup(toolNames)}
																className="shrink-0"
															/>
														</div>
													);
												})}
										</div>
									)}
									{!filteredTools?.length && (
										<div className="px-4 py-6 text-center text-sm text-muted-foreground">
											Loading tools...
										</div>
									)}
								</div>
							</DrawerContent>
						</Drawer>
						<Button
							variant="ghost"
							size="icon"
							className="size-[34px] rounded-full p-1 font-semibold text-xs hover:bg-muted-foreground/15 dark:border-muted-foreground/15 dark:hover:bg-muted-foreground/30"
							aria-label="Manage connectors"
							onClick={() => setConnectorDialogOpen(true)}
						>
							<Unplug className="size-4" />
						</Button>
					</>
				) : (
					<Popover open={toolsPopoverOpen} onOpenChange={setToolsPopoverOpen}>
						<PopoverTrigger asChild>
							<TooltipIconButton
								tooltip="Manage tools"
								side="bottom"
								disableTooltip={toolsPopoverOpen}
								variant="ghost"
								size="icon"
								className="size-[34px] rounded-full p-1 font-semibold text-xs hover:bg-muted-foreground/15 dark:border-muted-foreground/15 dark:hover:bg-muted-foreground/30"
								aria-label="Manage tools"
								data-joyride="connector-icon"
							>
								<Settings2 className="size-4" />
							</TooltipIconButton>
						</PopoverTrigger>
						<PopoverContent
							side="bottom"
							align="start"
							sideOffset={12}
							className="w-[calc(100vw-2rem)] max-w-56 sm:max-w-72 sm:w-72 p-0 select-none"
							onOpenAutoFocus={(e) => e.preventDefault()}
						>
							<div className="sr-only">Manage Tools</div>
							<div
								className="max-h-48 sm:max-h-64 overflow-y-auto overscroll-none py-0.5 sm:py-1"
								onScroll={handleToolsScroll}
								style={{
									maskImage: `linear-gradient(to bottom, ${toolsScrollPos === "top" ? "black" : "transparent"}, black 16px, black calc(100% - 16px), ${toolsScrollPos === "bottom" ? "black" : "transparent"})`,
									WebkitMaskImage: `linear-gradient(to bottom, ${toolsScrollPos === "top" ? "black" : "transparent"}, black 16px, black calc(100% - 16px), ${toolsScrollPos === "bottom" ? "black" : "transparent"})`,
								}}
							>
								{groupedTools
									.filter((g) => !g.connectorIcon)
									.map((group) => (
										<div key={group.label}>
											<div className="px-2.5 sm:px-3 pt-2 pb-0.5 text-[10px] sm:text-xs text-muted-foreground/80 font-normal select-none">
												{group.label}
											</div>
											{group.tools.map((tool) => {
												const isDisabled = disabledToolsSet.has(tool.name);
												const ToolIcon = getToolIcon(tool.name);
												const row = (
													<div className="flex w-full items-center gap-2 sm:gap-3 px-2.5 sm:px-3 py-1 sm:py-1.5 hover:bg-muted-foreground/10 transition-colors">
														<ToolIcon className="size-3.5 sm:size-4 shrink-0 text-muted-foreground" />
														<span className="flex-1 min-w-0 text-xs sm:text-sm font-medium truncate">
															{formatToolName(tool.name)}
														</span>
														<Switch
															checked={!isDisabled}
															onCheckedChange={() => toggleTool(tool.name)}
															className="shrink-0 scale-[0.6] sm:scale-75"
														/>
													</div>
												);
												return (
													<Tooltip key={tool.name}>
														<TooltipTrigger asChild>{row}</TooltipTrigger>
														<TooltipContent side="right" className="max-w-64 text-xs">
															{tool.description}
														</TooltipContent>
													</Tooltip>
												);
											})}
										</div>
									))}
								{groupedTools.some((g) => g.connectorIcon) && (
									<div>
										<div className="px-2.5 sm:px-3 pt-2 pb-0.5 text-[10px] sm:text-xs text-muted-foreground/80 font-normal select-none">
											Connector Actions
										</div>
										{groupedTools
											.filter((g) => g.connectorIcon)
											.map((group) => {
												const iconKey = group.connectorIcon ?? "";
												const iconInfo = CONNECTOR_TOOL_ICON_PATHS[iconKey];
												const toolNames = group.tools.map((t) => t.name);
												const allDisabled = toolNames.every((n) => disabledToolsSet.has(n));
												const groupDef = TOOL_GROUPS.find((g) => g.label === group.label);
												const row = (
													<div className="flex w-full items-center gap-2 sm:gap-3 px-2.5 sm:px-3 py-1 sm:py-1.5 hover:bg-muted-foreground/10 transition-colors">
														{iconInfo ? (
															<Image
																src={iconInfo.src}
																alt={iconInfo.alt}
																width={16}
																height={16}
																className="size-3.5 sm:size-4 shrink-0 select-none pointer-events-none"
																draggable={false}
															/>
														) : (
															<Wrench className="size-3.5 sm:size-4 shrink-0 text-muted-foreground" />
														)}
														<span className="flex-1 min-w-0 text-xs sm:text-sm font-medium truncate">
															{group.label}
														</span>
														<Switch
															checked={!allDisabled}
															onCheckedChange={() => toggleToolGroup(toolNames)}
															className="shrink-0 scale-[0.6] sm:scale-75"
														/>
													</div>
												);
												return (
													<Tooltip key={group.label}>
														<TooltipTrigger asChild>{row}</TooltipTrigger>
														<TooltipContent side="right" className="max-w-72 text-xs">
															{groupDef?.tooltip ??
																group.tools.flatMap((t, i) =>
																	i === 0
																		? [t.description]
																		: [<Dot key={i} className="inline h-4 w-4" />, t.description]
																)}
														</TooltipContent>
													</Tooltip>
												);
											})}
									</div>
								)}
								{!filteredTools?.length && (
									<div className="px-3 py-4 text-center text-xs text-muted-foreground">
										Loading tools...
									</div>
								)}
							</div>
						</PopoverContent>
					</Popover>
				)}
				{hasWebSearchTool && (
					<button
						type="button"
						aria-label={isWebSearchEnabled ? "Disable web search" : "Enable web search"}
						aria-pressed={isWebSearchEnabled}
						onClick={() => toggleTool("web_search")}
						className={cn(
							"rounded-full transition-all flex items-center gap-1 px-2 py-1 border h-8 select-none",
							isWebSearchEnabled
								? "bg-sky-500/15 border-sky-500/60 text-sky-500"
								: "bg-transparent border-transparent text-muted-foreground hover:text-foreground"
						)}
					>
						<motion.div
							animate={{
								rotate: isWebSearchEnabled ? 360 : 0,
								scale: isWebSearchEnabled ? 1.1 : 1,
							}}
							whileHover={{
								rotate: isWebSearchEnabled ? 360 : 15,
								scale: 1.1,
								transition: { type: "spring", stiffness: 300, damping: 10 },
							}}
							transition={{ type: "spring", stiffness: 260, damping: 25 }}
						>
							<Globe className="size-4" />
						</motion.div>
						<AnimatePresence>
							{isWebSearchEnabled && (
								<motion.span
									initial={{ width: 0, opacity: 0 }}
									animate={{ width: "auto", opacity: 1 }}
									exit={{ width: 0, opacity: 0 }}
									transition={{ duration: 0.2 }}
									className="text-xs overflow-hidden whitespace-nowrap"
								>
									Search
								</motion.span>
							)}
						</AnimatePresence>
					</button>
				)}
				{sidebarDocs.length > 0 && (
					<button
						type="button"
						onClick={() => setDocumentsSidebarOpen(true)}
						className="rounded-full border border-border/60 bg-accent/50 px-2.5 py-1 text-xs font-medium text-foreground/80 transition-colors hover:bg-accent"
					>
						{sidebarDocs.length} {sidebarDocs.length === 1 ? "source" : "sources"} selected
					</button>
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
											? "Enter a message to send"
											: "Send message"
							}
							side="bottom"
							type="submit"
							variant="default"
							size="icon"
							className={cn(
								"aui-composer-send size-8 rounded-full",
								isSendDisabled && "cursor-not-allowed opacity-50"
							)}
							aria-label="Send message"
							disabled={isSendDisabled}
						>
							<ArrowUpIcon className="aui-composer-send-icon size-4" />
						</TooltipIconButton>
					</ComposerPrimitive.Send>
				</AuiIf>

				<AuiIf condition={({ thread }) => thread.isRunning}>
					<ComposerPrimitive.Cancel asChild>
						<Button
							type="button"
							variant="default"
							size="icon"
							className="aui-composer-cancel size-8 rounded-full"
							aria-label="Stop generating"
						>
							<SquareIcon className="aui-composer-cancel-icon size-3 fill-current" />
						</Button>
					</ComposerPrimitive.Cancel>
				</AuiIf>
			</div>
		</div>
	);
};

/** Convert snake_case tool names to human-readable labels */
function formatToolName(name: string): string {
	return name
		.split("_")
		.map((word) => word.charAt(0).toUpperCase() + word.slice(1))
		.join(" ");
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
		tools: ["search_surfsense_docs", "scrape_webpage"],
	},
	{
		label: "Generate",
		tools: ["generate_podcast", "generate_video_presentation", "generate_report", "generate_image"],
	},
	{
		label: "Memory",
		tools: ["save_memory", "recall_memory"],
	},
	{
		label: "Gmail",
		tools: ["create_gmail_draft", "update_gmail_draft", "send_gmail_email", "trash_gmail_email"],
		connectorIcon: "gmail",
		tooltip: "Create drafts, update drafts, send emails, and trash emails in Gmail",
	},
	{
		label: "Google Calendar",
		tools: ["create_calendar_event", "update_calendar_event", "delete_calendar_event"],
		connectorIcon: "google_calendar",
		tooltip: "Create, update, and delete events in Google Calendar",
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
