import {
	ActionBarPrimitive,
	AssistantIf,
	BranchPickerPrimitive,
	ComposerPrimitive,
	ErrorPrimitive,
	MessagePrimitive,
	ThreadPrimitive,
	useAssistantState,
	useComposerRuntime,
} from "@assistant-ui/react";
import { useAtom, useAtomValue, useSetAtom } from "jotai";
import {
	AlertCircle,
	ArrowDownIcon,
	ArrowUpIcon,
	CheckIcon,
	ChevronLeftIcon,
	ChevronRightIcon,
	CopyIcon,
	DownloadIcon,
	Loader2,
	RefreshCwIcon,
	SquareIcon,
} from "lucide-react";
import { useParams } from "next/navigation";
import { type FC, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { chatSessionStateAtom } from "@/atoms/chat/chat-session-state.atom";
import { showCommentsGutterAtom } from "@/atoms/chat/current-thread.atom";
import {
	mentionedDocumentIdsAtom,
	mentionedDocumentsAtom,
} from "@/atoms/chat/mentioned-documents.atom";
import { membersAtom } from "@/atoms/members/members-query.atoms";
import {
	globalNewLLMConfigsAtom,
	llmPreferencesAtom,
	newLLMConfigsAtom,
} from "@/atoms/new-llm-config/new-llm-config-query.atoms";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import { AssistantMessage } from "@/components/assistant-ui/assistant-message";
import { ComposerAddAttachment, ComposerAttachments } from "@/components/assistant-ui/attachment";
import { ChatSessionStatus } from "@/components/assistant-ui/chat-session-status";
import { ConnectorIndicator } from "@/components/assistant-ui/connector-popup";
import {
	InlineMentionEditor,
	type InlineMentionEditorRef,
} from "@/components/assistant-ui/inline-mention-editor";
import { MarkdownText } from "@/components/assistant-ui/markdown-text";
import {
	ThinkingStepsContext,
	ThinkingStepsDisplay,
} from "@/components/assistant-ui/thinking-steps";
import { ToolFallback } from "@/components/assistant-ui/tool-fallback";
import { TooltipIconButton } from "@/components/assistant-ui/tooltip-icon-button";
import { UserMessage } from "@/components/assistant-ui/user-message";
import {
	DocumentMentionPicker,
	type DocumentMentionPickerRef,
} from "@/components/new-chat/document-mention-picker";
import type { ThinkingStep } from "@/components/tool-ui/deepagent-thinking";
import { Button } from "@/components/ui/button";
import type { Document } from "@/contracts/types/document.types";
import { useCommentsElectric } from "@/hooks/use-comments-electric";
import { cn } from "@/lib/utils";

/** Placeholder texts that cycle in new chats when input is empty */
const CYCLING_PLACEHOLDERS = [
	"Ask SurfSense anything or @mention docs.",
	"Generate a podcast from marketing tips in the company handbook.",
	"Sum up our vacation policy from Drive.",
	"Give me a brief overview of the most urgent tickets in Jira and Linear.",
	"Create a concise table of today's top ten emails and calendar events.",
	"Check if this week's Slack messages reference any GitHub issues.",
];

interface ThreadProps {
	messageThinkingSteps?: Map<string, ThinkingStep[]>;
	header?: React.ReactNode;
}

export const Thread: FC<ThreadProps> = ({ messageThinkingSteps = new Map(), header }) => {
	return (
		<ThinkingStepsContext.Provider value={messageThinkingSteps}>
			<ThreadContent header={header} />
		</ThinkingStepsContext.Provider>
	);
};

const ThreadContent: FC<{ header?: React.ReactNode }> = ({ header }) => {
	const showGutter = useAtomValue(showCommentsGutterAtom);

	return (
		<ThreadPrimitive.Root
			className="aui-root aui-thread-root @container flex h-full min-h-0 flex-col bg-background"
			style={{
				["--thread-max-width" as string]: "44rem",
			}}
		>
			<ThreadPrimitive.Viewport
				turnAnchor="top"
				autoScroll
				className={cn(
					"aui-thread-viewport relative flex flex-1 min-h-0 flex-col overflow-y-auto px-4 pt-4 transition-[padding] duration-300 ease-out",
					showGutter && "lg:pr-30"
				)}
			>
				{header && <div className="sticky top-0 z-10 mb-4">{header}</div>}

				<AssistantIf condition={({ thread }) => thread.isEmpty}>
					<ThreadWelcome />
				</AssistantIf>

				<ThreadPrimitive.Messages
					components={{
						UserMessage,
						EditComposer,
						AssistantMessage,
					}}
				/>

				<ThreadPrimitive.ViewportFooter className="aui-thread-viewport-footer sticky bottom-0 z-10 mx-auto mt-auto flex w-full max-w-(--thread-max-width) flex-col gap-4 overflow-visible rounded-t-3xl bg-background pb-4 md:pb-6">
					<ThreadScrollToBottom />
					<AssistantIf condition={({ thread }) => !thread.isEmpty}>
						<div className="fade-in slide-in-from-bottom-4 animate-in duration-500 ease-out fill-mode-both">
							<Composer />
						</div>
					</AssistantIf>
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
				className="aui-thread-scroll-to-bottom -top-12 absolute z-10 self-center rounded-full p-4 disabled:invisible dark:bg-background dark:hover:bg-accent"
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
			{/* Greeting positioned above the composer - fixed position */}
			<div className="aui-thread-welcome-message absolute bottom-[calc(50%+5rem)] left-0 right-0 flex flex-col items-center text-center">
				<h1 className="aui-thread-welcome-message-inner fade-in slide-in-from-bottom-2 animate-in text-3xl md:text-5xl delay-100 duration-500 ease-out fill-mode-both">
					{greeting}
				</h1>
			</div>
			{/* Composer - top edge fixed, expands downward only */}
			<div className="fade-in slide-in-from-bottom-3 animate-in delay-200 duration-500 ease-out fill-mode-both w-full flex items-start justify-center absolute top-[calc(50%-3.5rem)] left-0 right-0">
				<Composer />
			</div>
		</div>
	);
};

const Composer: FC = () => {
	// Document mention state (atoms persist across component remounts)
	const [mentionedDocuments, setMentionedDocuments] = useAtom(mentionedDocumentsAtom);
	const [showDocumentPopover, setShowDocumentPopover] = useState(false);
	const [mentionQuery, setMentionQuery] = useState("");
	const editorRef = useRef<InlineMentionEditorRef>(null);
	const editorContainerRef = useRef<HTMLDivElement>(null);
	const documentPickerRef = useRef<DocumentMentionPickerRef>(null);
	const { search_space_id, chat_id } = useParams();
	const setMentionedDocumentIds = useSetAtom(mentionedDocumentIdsAtom);
	const composerRuntime = useComposerRuntime();
	const hasAutoFocusedRef = useRef(false);

	const isThreadEmpty = useAssistantState(({ thread }) => thread.isEmpty);
	const isThreadRunning = useAssistantState(({ thread }) => thread.isRunning);

	// Cycling placeholder state - only cycles in new chats
	const [placeholderIndex, setPlaceholderIndex] = useState(0);

	// Cycle through placeholders every 4 seconds when thread is empty (new chat)
	useEffect(() => {
		// Only cycle when thread is empty (new chat)
		if (!isThreadEmpty) {
			// Reset to first placeholder when chat becomes active
			setPlaceholderIndex(0);
			return;
		}

		const intervalId = setInterval(() => {
			setPlaceholderIndex((prev) => (prev + 1) % CYCLING_PLACEHOLDERS.length);
		}, 6000);

		return () => clearInterval(intervalId);
	}, [isThreadEmpty]);

	// Compute current placeholder - only cycle in new chats
	const currentPlaceholder = isThreadEmpty
		? CYCLING_PLACEHOLDERS[placeholderIndex]
		: CYCLING_PLACEHOLDERS[0];

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

	// Sync comments for the entire thread via Electric SQL (one subscription per thread)
	useCommentsElectric(threadId);

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

	// Sync mentioned document IDs to atom for inclusion in chat request payload
	useEffect(() => {
		setMentionedDocumentIds({
			surfsense_doc_ids: mentionedDocuments
				.filter((doc) => doc.document_type === "SURFSENSE_DOCS")
				.map((doc) => doc.id),
			document_ids: mentionedDocuments
				.filter((doc) => doc.document_type !== "SURFSENSE_DOCS")
				.map((doc) => doc.id),
		});
	}, [mentionedDocuments, setMentionedDocumentIds]);

	// Sync editor text with assistant-ui composer runtime
	const handleEditorChange = useCallback(
		(text: string) => {
			composerRuntime.setText(text);
		},
		[composerRuntime]
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

	// Keyboard navigation for document picker (arrow keys, Enter, Escape)
	const handleKeyDown = useCallback(
		(e: React.KeyboardEvent) => {
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
		[showDocumentPopover]
	);

	// Submit message (blocked during streaming, document picker open, or AI responding to another user)
	const handleSubmit = useCallback(() => {
		if (isThreadRunning || isBlockedByOtherUser) {
			return;
		}
		if (!showDocumentPopover) {
			composerRuntime.send();
			editorRef.current?.clear();
			setMentionedDocuments([]);
			setMentionedDocumentIds({
				surfsense_doc_ids: [],
				document_ids: [],
			});
		}
	}, [
		showDocumentPopover,
		isThreadRunning,
		isBlockedByOtherUser,
		composerRuntime,
		setMentionedDocuments,
		setMentionedDocumentIds,
	]);

	// Remove document from mentions and sync IDs to atom
	const handleDocumentRemove = useCallback(
		(docId: number, docType?: string) => {
			setMentionedDocuments((prev) => {
				const updated = prev.filter((doc) => !(doc.id === docId && doc.document_type === docType));
				setMentionedDocumentIds({
					surfsense_doc_ids: updated
						.filter((doc) => doc.document_type === "SURFSENSE_DOCS")
						.map((doc) => doc.id),
					document_ids: updated
						.filter((doc) => doc.document_type !== "SURFSENSE_DOCS")
						.map((doc) => doc.id),
				});
				return updated;
			});
		},
		[setMentionedDocuments, setMentionedDocumentIds]
	);

	// Add selected documents from picker, insert chips, and sync IDs to atom
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
				const updated = [...prev, ...uniqueNewDocs];
				setMentionedDocumentIds({
					surfsense_doc_ids: updated
						.filter((doc) => doc.document_type === "SURFSENSE_DOCS")
						.map((doc) => doc.id),
					document_ids: updated
						.filter((doc) => doc.document_type !== "SURFSENSE_DOCS")
						.map((doc) => doc.id),
				});
				return updated;
			});

			setMentionQuery("");
		},
		[mentionedDocuments, setMentionedDocuments, setMentionedDocumentIds]
	);

	return (
		<ComposerPrimitive.Root className="aui-composer-root relative flex w-full flex-col gap-2">
			<ChatSessionStatus
				isAiResponding={isAiResponding}
				respondingToUserId={respondingToUserId}
				currentUserId={currentUser?.id ?? null}
				members={members ?? []}
			/>
			<ComposerPrimitive.AttachmentDropzone className="aui-composer-attachment-dropzone flex w-full flex-col rounded-2xl border-input bg-muted px-1 pt-2 outline-none transition-shadow data-[dragging=true]:border-ring data-[dragging=true]:border-dashed data-[dragging=true]:bg-accent/50">
				<ComposerAttachments />
				{/* Inline editor with @mention support */}
				<div ref={editorContainerRef} className="aui-composer-input-wrapper px-3 pt-3 pb-6">
					<InlineMentionEditor
						ref={editorRef}
						placeholder={currentPlaceholder}
						onMentionTrigger={handleMentionTrigger}
						onMentionClose={handleMentionClose}
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
				<ComposerAction isBlockedByOtherUser={isBlockedByOtherUser} />
			</ComposerPrimitive.AttachmentDropzone>
		</ComposerPrimitive.Root>
	);
};

interface ComposerActionProps {
	isBlockedByOtherUser?: boolean;
}

const ComposerAction: FC<ComposerActionProps> = ({ isBlockedByOtherUser = false }) => {
	// Check if any attachments are still being processed (running AND progress < 100)
	// When progress is 100, processing is done but waiting for send()
	const hasProcessingAttachments = useAssistantState(({ composer }) =>
		composer.attachments?.some((att) => {
			const status = att.status;
			if (status?.type !== "running") return false;
			const progress = (status as { type: "running"; progress?: number }).progress;
			return progress === undefined || progress < 100;
		})
	);

	// Check if composer text is empty
	const isComposerEmpty = useAssistantState(({ composer }) => {
		const text = composer.text?.trim() || "";
		return text.length === 0;
	});

	// Check if a model is configured
	const { data: userConfigs } = useAtomValue(newLLMConfigsAtom);
	const { data: globalConfigs } = useAtomValue(globalNewLLMConfigsAtom);
	const { data: preferences } = useAtomValue(llmPreferencesAtom);

	const hasModelConfigured = useMemo(() => {
		if (!preferences) return false;
		const agentLlmId = preferences.agent_llm_id;
		if (agentLlmId === null || agentLlmId === undefined) return false;

		// Check if the configured model actually exists
		// Auto mode (ID 0) and global configs (negative IDs) are in globalConfigs
		if (agentLlmId <= 0) {
			return globalConfigs?.some((c) => c.id === agentLlmId) ?? false;
		}
		return userConfigs?.some((c) => c.id === agentLlmId) ?? false;
	}, [preferences, globalConfigs, userConfigs]);

	const isSendDisabled =
		hasProcessingAttachments || isComposerEmpty || !hasModelConfigured || isBlockedByOtherUser;

	return (
		<div className="aui-composer-action-wrapper relative mx-2 mb-2 flex items-center justify-between">
			<div className="flex items-center gap-1">
				<ComposerAddAttachment />
				<ConnectorIndicator />
			</div>

			{/* Show processing indicator when attachments are being processed */}
			{hasProcessingAttachments && (
				<div className="flex items-center gap-1.5 text-muted-foreground text-xs">
					<Loader2 className="size-3 animate-spin" />
					<span>Processing...</span>
				</div>
			)}

			{/* Show warning when no model is configured */}
			{!hasModelConfigured && !hasProcessingAttachments && (
				<div className="flex items-center gap-1.5 text-amber-600 dark:text-amber-400 text-xs">
					<AlertCircle className="size-3" />
					<span>Select a model</span>
				</div>
			)}

			<AssistantIf condition={({ thread }) => !thread.isRunning}>
				<ComposerPrimitive.Send asChild disabled={isSendDisabled}>
					<TooltipIconButton
						tooltip={
							isBlockedByOtherUser
								? "Wait for AI to finish responding"
								: !hasModelConfigured
									? "Please select a model from the header to start chatting"
									: hasProcessingAttachments
										? "Wait for attachments to process"
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
			</AssistantIf>

			<AssistantIf condition={({ thread }) => thread.isRunning}>
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
			</AssistantIf>
		</div>
	);
};

const MessageError: FC = () => {
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

const AssistantActionBar: FC = () => {
	return (
		<ActionBarPrimitive.Root
			hideWhenRunning
			autohide="not-last"
			autohideFloat="single-branch"
			className="aui-assistant-action-bar-root -ml-1 col-start-3 row-start-2 flex gap-1 text-muted-foreground data-floating:absolute data-floating:rounded-md data-floating:border data-floating:bg-background data-floating:p-1 data-floating:shadow-sm"
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

const BranchPicker: FC<BranchPickerPrimitive.Root.Props> = ({ className, ...rest }) => {
	return (
		<BranchPickerPrimitive.Root
			hideWhenSingleBranch
			className={cn(
				"aui-branch-picker-root -ml-2 mr-2 inline-flex items-center text-muted-foreground text-xs",
				className
			)}
			{...rest}
		>
			<BranchPickerPrimitive.Previous asChild>
				<TooltipIconButton tooltip="Previous">
					<ChevronLeftIcon />
				</TooltipIconButton>
			</BranchPickerPrimitive.Previous>
			<span className="aui-branch-picker-state font-medium">
				<BranchPickerPrimitive.Number /> / <BranchPickerPrimitive.Count />
			</span>
			<BranchPickerPrimitive.Next asChild>
				<TooltipIconButton tooltip="Next">
					<ChevronRightIcon />
				</TooltipIconButton>
			</BranchPickerPrimitive.Next>
		</BranchPickerPrimitive.Root>
	);
};
