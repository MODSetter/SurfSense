"use client";

import {
	type AppendMessage,
	AssistantRuntimeProvider,
	type ThreadMessageLike,
	useAui,
	useExternalStoreRuntime,
} from "@assistant-ui/react";
import { useQueryClient } from "@tanstack/react-query";
import { useAtomValue, useSetAtom } from "jotai";
import { useParams, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { z } from "zod";
import { disabledToolsAtom } from "@/atoms/agent-tools/agent-tools.atoms";
import {
	clearTargetCommentIdAtom,
	currentThreadAtom,
	setTargetCommentIdAtom,
} from "@/atoms/chat/current-thread.atom";
import {
	type MentionedDocumentInfo,
	mentionedDocumentIdsAtom,
	mentionedDocumentsAtom,
	messageDocumentsMapAtom,
	sidebarSelectedDocumentsAtom,
} from "@/atoms/chat/mentioned-documents.atom";
import {
	clearPlanOwnerRegistry,
	// extractWriteTodosFromContent,
} from "@/atoms/chat/plan-state.atom";
import { closeReportPanelAtom } from "@/atoms/chat/report-panel.atom";
import { closeEditorPanelAtom } from "@/atoms/editor/editor-panel.atom";
import { membersAtom } from "@/atoms/members/members-query.atoms";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import { ThinkingStepsDataUI } from "@/components/assistant-ui/thinking-steps";
import { Thread } from "@/components/assistant-ui/thread";
import { MobileEditorPanel } from "@/components/editor-panel/editor-panel";
import { MobileHitlEditPanel } from "@/components/hitl-edit-panel/hitl-edit-panel";
import { MobileReportPanel } from "@/components/report-panel/report-panel";
import { Skeleton } from "@/components/ui/skeleton";
import { useChatSessionStateSync } from "@/hooks/use-chat-session-state";
import { useMessagesSync } from "@/hooks/use-messages-sync";
import { documentsApiService } from "@/lib/apis/documents-api.service";
import { getBearerToken } from "@/lib/auth-utils";
import { convertToThreadMessage } from "@/lib/chat/message-utils";
import {
	isPodcastGenerating,
	looksLikePodcastRequest,
	setActivePodcastTaskId,
} from "@/lib/chat/podcast-state";
import {
	addToolCall,
	appendText,
	buildContentForPersistence,
	buildContentForUI,
	type ContentPartsState,
	readSSEStream,
	type ThinkingStepData,
	updateThinkingSteps,
	updateToolCall,
} from "@/lib/chat/streaming-state";
import {
	appendMessage,
	createThread,
	getRegenerateUrl,
	getThreadFull,
	getThreadMessages,
	type ThreadRecord,
} from "@/lib/chat/thread-persistence";
import {
	trackChatCreated,
	trackChatError,
	trackChatMessageSent,
	trackChatResponseReceived,
} from "@/lib/posthog/events";

/**
 * After a tool produces output, mark any previously-decided interrupt tool
 * calls as completed so the ApprovalCard can transition from shimmer to done.
 */
function markInterruptsCompleted(contentParts: Array<{ type: string; result?: unknown }>): void {
	for (const part of contentParts) {
		if (
			part.type === "tool-call" &&
			typeof part.result === "object" &&
			part.result !== null &&
			(part.result as Record<string, unknown>).__interrupt__ === true &&
			(part.result as Record<string, unknown>).__decided__ &&
			!(part.result as Record<string, unknown>).__completed__
		) {
			part.result = { ...(part.result as Record<string, unknown>), __completed__: true };
		}
	}
}

/**
 * Zod schema for mentioned document info (for type-safe parsing)
 */
const MentionedDocumentInfoSchema = z.object({
	id: z.number(),
	title: z.string(),
	document_type: z.string(),
});

const MentionedDocumentsPartSchema = z.object({
	type: z.literal("mentioned-documents"),
	documents: z.array(MentionedDocumentInfoSchema),
});

/**
 * Extract mentioned documents from message content (type-safe with Zod)
 */
function extractMentionedDocuments(content: unknown): MentionedDocumentInfo[] {
	if (!Array.isArray(content)) return [];

	for (const part of content) {
		const result = MentionedDocumentsPartSchema.safeParse(part);
		if (result.success) {
			return result.data.documents;
		}
	}

	return [];
}

/**
 * Tools that should render custom UI in the chat.
 */
const TOOLS_WITH_UI = new Set([
	"generate_podcast",
	"generate_report",
	"generate_video_presentation",
	"display_image",
	"generate_image",
	"delete_notion_page",
	"create_notion_page",
	"update_notion_page",
	"create_linear_issue",
	"update_linear_issue",
	"delete_linear_issue",
	"create_google_drive_file",
	"delete_google_drive_file",
	"create_calendar_event",
	"update_calendar_event",
	"delete_calendar_event",
	"create_gmail_draft",
	"update_gmail_draft",
	"send_gmail_email",
	"trash_gmail_email",
	"create_jira_issue",
	"update_jira_issue",
	"delete_jira_issue",
	"create_confluence_page",
	"update_confluence_page",
	"delete_confluence_page",
	"execute",
	// "write_todos", // Disabled for now
]);

function QuickAskAutoSubmit() {
	const searchParams = useSearchParams();
	const aui = useAui();
	const handledRef = useRef(false);

	useEffect(() => {
		if (!window.electronAPI || handledRef.current) return;
		if (sessionStorage.getItem("quickAskAutoSubmit") === "false") return;

		const prompt = searchParams.get("quickAskPrompt");
		if (!prompt) return;

		handledRef.current = true;
		setTimeout(() => {
			aui.composer().setText(prompt);
			aui.composer().send();
		}, 500);
	}, [searchParams, aui]);

	return null;
}

export default function NewChatPage() {
	const params = useParams();
	const queryClient = useQueryClient();
	const [isInitializing, setIsInitializing] = useState(true);
	const [threadId, setThreadId] = useState<number | null>(null);
	const [currentThread, setCurrentThread] = useState<ThreadRecord | null>(null);
	const [messages, setMessages] = useState<ThreadMessageLike[]>([]);
	const [isRunning, setIsRunning] = useState(false);
	const abortControllerRef = useRef<AbortController | null>(null);
	const [pendingInterrupt, setPendingInterrupt] = useState<{
		threadId: number;
		assistantMsgId: string;
		interruptData: Record<string, unknown>;
	} | null>(null);

	// Get disabled tools from the tool toggle UI
	const disabledTools = useAtomValue(disabledToolsAtom);

	// Get mentioned document IDs from the composer (derived from @ mentions + sidebar selections)
	const mentionedDocumentIds = useAtomValue(mentionedDocumentIdsAtom);
	const mentionedDocuments = useAtomValue(mentionedDocumentsAtom);
	const sidebarDocuments = useAtomValue(sidebarSelectedDocumentsAtom);
	const setMentionedDocuments = useSetAtom(mentionedDocumentsAtom);
	const setSidebarDocuments = useSetAtom(sidebarSelectedDocumentsAtom);
	const setMessageDocumentsMap = useSetAtom(messageDocumentsMapAtom);
	const setCurrentThreadState = useSetAtom(currentThreadAtom);
	const setTargetCommentId = useSetAtom(setTargetCommentIdAtom);
	const clearTargetCommentId = useSetAtom(clearTargetCommentIdAtom);
	const closeReportPanel = useSetAtom(closeReportPanelAtom);
	const closeEditorPanel = useSetAtom(closeEditorPanelAtom);

	// Get current user for author info in shared chats
	const { data: currentUser } = useAtomValue(currentUserAtom);

	// Live collaboration: sync session state and messages via Zero
	useChatSessionStateSync(threadId);
	const { data: membersData } = useAtomValue(membersAtom);

	const handleSyncedMessagesUpdate = useCallback(
		(
			syncedMessages: {
				id: number;
				thread_id: number;
				role: string;
				content: unknown;
				author_id: string | null;
				created_at: string;
			}[]
		) => {
			if (isRunning) {
				return;
			}

			setMessages((prev) => {
				if (syncedMessages.length < prev.length) {
					return prev;
				}

				return syncedMessages.map((msg) => {
					const member = msg.author_id
						? membersData?.find((m) => m.user_id === msg.author_id)
						: null;

					// Preserve existing author info if member lookup fails (e.g., cloned chats)
					const existingMsg = prev.find((m) => m.id === `msg-${msg.id}`);
					const existingAuthor = existingMsg?.metadata?.custom?.author as
						| { displayName?: string | null; avatarUrl?: string | null }
						| undefined;

					return convertToThreadMessage({
						id: msg.id,
						thread_id: msg.thread_id,
						role: msg.role.toLowerCase() as "user" | "assistant" | "system",
						content: msg.content,
						author_id: msg.author_id,
						created_at: msg.created_at,
						author_display_name: member?.user_display_name ?? existingAuthor?.displayName ?? null,
						author_avatar_url: member?.user_avatar_url ?? existingAuthor?.avatarUrl ?? null,
					});
				});
			});
		},
		[isRunning, membersData]
	);

	useMessagesSync(threadId, handleSyncedMessagesUpdate);

	// Extract search_space_id from URL params
	const searchSpaceId = useMemo(() => {
		const id = params.search_space_id;
		const parsed = typeof id === "string" ? Number.parseInt(id, 10) : 0;
		return Number.isNaN(parsed) ? 0 : parsed;
	}, [params.search_space_id]);

	// Extract chat_id from URL params
	const urlChatId = useMemo(() => {
		const id = params.chat_id;
		let parsed = 0;
		if (Array.isArray(id) && id.length > 0) {
			parsed = Number.parseInt(id[0], 10);
		} else if (typeof id === "string") {
			parsed = Number.parseInt(id, 10);
		}
		return Number.isNaN(parsed) ? 0 : parsed;
	}, [params.chat_id]);

	// Initialize thread and load messages
	// For new chats (no urlChatId), we use lazy creation - thread is created on first message
	// biome-ignore lint/correctness/useExhaustiveDependencies: searchSpaceId triggers re-init when switching spaces with the same urlChatId
	const initializeThread = useCallback(async () => {
		setIsInitializing(true);

		// Reset all state when switching between chats/search spaces to prevent stale data
		setMessages([]);
		setThreadId(null);
		setCurrentThread(null);
		setMentionedDocuments([]);
		setSidebarDocuments([]);
		setMessageDocumentsMap({});
		clearPlanOwnerRegistry();
		closeReportPanel();
		closeEditorPanel();

		try {
			if (urlChatId > 0) {
				// Thread exists - load thread data and messages
				setThreadId(urlChatId);

				// Load thread data (for visibility info) and messages in parallel
				const [threadData, messagesResponse] = await Promise.all([
					getThreadFull(urlChatId),
					getThreadMessages(urlChatId),
				]);

				setCurrentThread(threadData);

				if (messagesResponse.messages && messagesResponse.messages.length > 0) {
					const loadedMessages = messagesResponse.messages.map(convertToThreadMessage);
					setMessages(loadedMessages);

					const restoredDocsMap: Record<string, MentionedDocumentInfo[]> = {};
					for (const msg of messagesResponse.messages) {
						if (msg.role === "user") {
							const docs = extractMentionedDocuments(msg.content);
							if (docs.length > 0) {
								restoredDocsMap[`msg-${msg.id}`] = docs;
							}
						}
					}
					if (Object.keys(restoredDocsMap).length > 0) {
						setMessageDocumentsMap(restoredDocsMap);
					}
				}
			}
			// For new chats (urlChatId === 0), don't create thread yet
			// Thread will be created lazily when user sends first message
			// This improves UX (instant load) and avoids orphan threads
		} catch (error) {
			console.error("[NewChatPage] Failed to initialize thread:", error);
			// Keep threadId as null - don't use Date.now() as it creates an invalid ID
			// that will cause 404 errors on subsequent API calls
			setThreadId(null);
			setCurrentThread(null);
			toast.error("Failed to load chat. Please try again.");
		} finally {
			setIsInitializing(false);
		}
	}, [
		urlChatId,
		searchSpaceId,
		setMessageDocumentsMap,
		setMentionedDocuments,
		setSidebarDocuments,
		closeReportPanel,
		closeEditorPanel,
	]);

	// Initialize on mount
	useEffect(() => {
		initializeThread();
	}, [initializeThread]);

	// Prefetch document titles for @ mention picker
	// Runs when user lands on page so data is ready when they type @
	useEffect(() => {
		if (!searchSpaceId) return;

		const prefetchParams = {
			search_space_id: searchSpaceId,
			page: 0,
			page_size: 20,
		};

		queryClient.prefetchQuery({
			queryKey: ["document-titles", prefetchParams],
			queryFn: () => documentsApiService.searchDocumentTitles({ queryParams: prefetchParams }),
			staleTime: 60 * 1000,
		});

		queryClient.prefetchQuery({
			queryKey: ["surfsense-docs-mention", "", false],
			queryFn: () =>
				documentsApiService.getSurfsenseDocs({
					queryParams: { page: 0, page_size: 20 },
				}),
			staleTime: 3 * 60 * 1000,
		});
	}, [searchSpaceId, queryClient]);

	// Handle scroll to comment from URL query params (e.g., from inbox item click)
	const searchParams = useSearchParams();
	const targetCommentIdParam = searchParams.get("commentId");

	// Set target comment ID from URL param - the AssistantMessage and CommentItem
	// components will handle scrolling and highlighting once comments are loaded
	useEffect(() => {
		if (targetCommentIdParam && !isInitializing) {
			const commentId = Number.parseInt(targetCommentIdParam, 10);
			if (!Number.isNaN(commentId)) {
				setTargetCommentId(commentId);
			}
		}

		// Cleanup on unmount or when navigating away
		return () => clearTargetCommentId();
	}, [targetCommentIdParam, isInitializing, setTargetCommentId, clearTargetCommentId]);

	// Sync current thread state to atom
	useEffect(() => {
		setCurrentThreadState((prev) => ({
			...prev,
			id: currentThread?.id ?? null,
			visibility: currentThread?.visibility ?? null,
			hasComments: currentThread?.has_comments ?? false,
		}));
	}, [currentThread, setCurrentThreadState]);

	// Cleanup on unmount - abort any in-flight requests
	useEffect(() => {
		return () => {
			if (abortControllerRef.current) {
				abortControllerRef.current.abort();
				abortControllerRef.current = null;
			}
		};
	}, []);

	// Cancel ongoing request
	const cancelRun = useCallback(async () => {
		if (abortControllerRef.current) {
			abortControllerRef.current.abort();
			abortControllerRef.current = null;
		}
		setIsRunning(false);
	}, []);

	// Handle new message from user
	const onNew = useCallback(
		async (message: AppendMessage) => {
			// Abort any previous streaming request to prevent race conditions
			// when user sends a second query while the first is still streaming
			if (abortControllerRef.current) {
				abortControllerRef.current.abort();
				abortControllerRef.current = null;
			}

			// Extract user query text from content parts
			let userQuery = "";
			for (const part of message.content) {
				if (part.type === "text") {
					userQuery += part.text;
				}
			}

			if (!userQuery.trim()) return;

			// Check if podcast is already generating
			if (isPodcastGenerating() && looksLikePodcastRequest(userQuery)) {
				toast.warning("A podcast is already being generated.");
				return;
			}

			const token = getBearerToken();
			if (!token) {
				toast.error("Not authenticated. Please log in again.");
				return;
			}

			// Lazy thread creation: create thread on first message if it doesn't exist
			let currentThreadId = threadId;
			let isNewThread = false;
			if (!currentThreadId) {
				try {
					const newThread = await createThread(searchSpaceId, "New Chat");
					currentThreadId = newThread.id;
					setThreadId(currentThreadId);
					// Set currentThread so share button in header appears immediately
					setCurrentThread(newThread);

					// Track chat creation
					trackChatCreated(searchSpaceId, currentThreadId);

					isNewThread = true;
					// Update URL silently using browser API (not router.replace) to avoid
					// interrupting the ongoing fetch/streaming with React navigation
					window.history.replaceState(
						null,
						"",
						`/dashboard/${searchSpaceId}/new-chat/${currentThreadId}`
					);
				} catch (error) {
					console.error("[NewChatPage] Failed to create thread:", error);
					toast.error("Failed to start chat. Please try again.");
					return;
				}
			}

			// Add user message to state
			const userMsgId = `msg-user-${Date.now()}`;

			// Include author metadata for shared chats
			const authorMetadata =
				currentThread?.visibility === "SEARCH_SPACE" && currentUser
					? {
							custom: {
								author: {
									displayName: currentUser.display_name ?? null,
									avatarUrl: currentUser.avatar_url ?? null,
								},
							},
						}
					: undefined;

			const userMessage: ThreadMessageLike = {
				id: userMsgId,
				role: "user",
				content: message.content,
				createdAt: new Date(),
				metadata: authorMetadata,
			};
			setMessages((prev) => [...prev, userMessage]);

			// Track message sent
			trackChatMessageSent(searchSpaceId, currentThreadId, {
				hasAttachments: false,
				hasMentionedDocuments:
					mentionedDocumentIds.surfsense_doc_ids.length > 0 ||
					mentionedDocumentIds.document_ids.length > 0,
				messageLength: userQuery.length,
			});

			// Combine @-mention chips + sidebar selections for display & persistence
			const allMentionedDocs: MentionedDocumentInfo[] = [];
			const seenDocKeys = new Set<string>();
			for (const doc of [...mentionedDocuments, ...sidebarDocuments]) {
				const key = `${doc.document_type}:${doc.id}`;
				if (!seenDocKeys.has(key)) {
					seenDocKeys.add(key);
					allMentionedDocs.push({ id: doc.id, title: doc.title, document_type: doc.document_type });
				}
			}

			if (allMentionedDocs.length > 0) {
				setMessageDocumentsMap((prev) => ({
					...prev,
					[userMsgId]: allMentionedDocs,
				}));
			}

			const persistContent: unknown[] = [...message.content];

			if (allMentionedDocs.length > 0) {
				persistContent.push({
					type: "mentioned-documents",
					documents: allMentionedDocs,
				});
			}

			appendMessage(currentThreadId, {
				role: "user",
				content: persistContent,
			})
				.then((savedMessage) => {
					const newUserMsgId = `msg-${savedMessage.id}`;
					setMessages((prev) =>
						prev.map((m) => (m.id === userMsgId ? { ...m, id: newUserMsgId } : m))
					);
					setMessageDocumentsMap((prev) => {
						const docs = prev[userMsgId];
						if (!docs) return prev;
						const { [userMsgId]: _, ...rest } = prev;
						return { ...rest, [newUserMsgId]: docs };
					});
					if (isNewThread) {
						queryClient.invalidateQueries({ queryKey: ["threads", String(searchSpaceId)] });
					}
				})
				.catch((err) => console.error("Failed to persist user message:", err));

			// Start streaming response
			setIsRunning(true);
			const controller = new AbortController();
			abortControllerRef.current = controller;

			// Prepare assistant message
			const assistantMsgId = `msg-assistant-${Date.now()}`;
			const currentThinkingSteps = new Map<string, ThinkingStepData>();

			const contentPartsState: ContentPartsState = {
				contentParts: [],
				currentTextPartIndex: -1,
				toolCallIndices: new Map(),
			};
			const { contentParts, toolCallIndices } = contentPartsState;
			let wasInterrupted = false;

			// Add placeholder assistant message
			setMessages((prev) => [
				...prev,
				{
					id: assistantMsgId,
					role: "assistant",
					content: [{ type: "text", text: "" }],
					createdAt: new Date(),
				},
			]);

			try {
				const backendUrl = process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL || "http://localhost:8000";

				// Build message history for context
				const messageHistory = messages
					.filter((m) => m.role === "user" || m.role === "assistant")
					.map((m) => {
						let text = "";
						for (const part of m.content) {
							if (typeof part === "object" && part.type === "text" && "text" in part) {
								text += part.text;
							}
						}
						return { role: m.role, content: text };
					})
					.filter((m) => m.content.length > 0);

				// Get mentioned document IDs for context (separate fields for backend)
				const hasDocumentIds = mentionedDocumentIds.document_ids.length > 0;
				const hasSurfsenseDocIds = mentionedDocumentIds.surfsense_doc_ids.length > 0;

				// Clear mentioned documents after capturing them
				if (hasDocumentIds || hasSurfsenseDocIds) {
					setMentionedDocuments([]);
					setSidebarDocuments([]);
				}

				const response = await fetch(`${backendUrl}/api/v1/new_chat`, {
					method: "POST",
					headers: {
						"Content-Type": "application/json",
						Authorization: `Bearer ${token}`,
					},
					body: JSON.stringify({
						chat_id: currentThreadId,
						user_query: userQuery.trim(),
						search_space_id: searchSpaceId,
						messages: messageHistory,
						mentioned_document_ids: hasDocumentIds ? mentionedDocumentIds.document_ids : undefined,
						mentioned_surfsense_doc_ids: hasSurfsenseDocIds
							? mentionedDocumentIds.surfsense_doc_ids
							: undefined,
						disabled_tools: disabledTools.length > 0 ? disabledTools : undefined,
					}),
					signal: controller.signal,
				});

				if (!response.ok) {
					throw new Error(`Backend error: ${response.status}`);
				}

				for await (const parsed of readSSEStream(response)) {
					switch (parsed.type) {
						case "text-delta":
							appendText(contentPartsState, parsed.delta);
							setMessages((prev) =>
								prev.map((m) =>
									m.id === assistantMsgId
										? { ...m, content: buildContentForUI(contentPartsState, TOOLS_WITH_UI) }
										: m
								)
							);
							break;

						case "tool-input-start":
							// Add tool call inline - this breaks the current text segment
							addToolCall(contentPartsState, TOOLS_WITH_UI, parsed.toolCallId, parsed.toolName, {});
							setMessages((prev) =>
								prev.map((m) =>
									m.id === assistantMsgId
										? { ...m, content: buildContentForUI(contentPartsState, TOOLS_WITH_UI) }
										: m
								)
							);
							break;

						case "tool-input-available": {
							// Update existing tool call's args, or add if not exists
							if (toolCallIndices.has(parsed.toolCallId)) {
								updateToolCall(contentPartsState, parsed.toolCallId, { args: parsed.input || {} });
							} else {
								addToolCall(
									contentPartsState,
									TOOLS_WITH_UI,
									parsed.toolCallId,
									parsed.toolName,
									parsed.input || {}
								);
							}
							setMessages((prev) =>
								prev.map((m) =>
									m.id === assistantMsgId
										? { ...m, content: buildContentForUI(contentPartsState, TOOLS_WITH_UI) }
										: m
								)
							);
							break;
						}

						case "tool-output-available": {
							// Update the tool call with its result
							updateToolCall(contentPartsState, parsed.toolCallId, { result: parsed.output });
							markInterruptsCompleted(contentParts);
							// Handle podcast-specific logic
							if (parsed.output?.status === "pending" && parsed.output?.podcast_id) {
								// Check if this is a podcast tool by looking at the content part
								const idx = toolCallIndices.get(parsed.toolCallId);
								if (idx !== undefined) {
									const part = contentParts[idx];
									if (part?.type === "tool-call" && part.toolName === "generate_podcast") {
										setActivePodcastTaskId(String(parsed.output.podcast_id));
									}
								}
							}
							setMessages((prev) =>
								prev.map((m) =>
									m.id === assistantMsgId
										? { ...m, content: buildContentForUI(contentPartsState, TOOLS_WITH_UI) }
										: m
								)
							);
							break;
						}

						case "data-thinking-step": {
							const stepData = parsed.data as ThinkingStepData;
							if (stepData?.id) {
								currentThinkingSteps.set(stepData.id, stepData);
								updateThinkingSteps(contentPartsState, currentThinkingSteps);
								setMessages((prev) =>
									prev.map((m) =>
										m.id === assistantMsgId
											? { ...m, content: buildContentForUI(contentPartsState, TOOLS_WITH_UI) }
											: m
									)
								);
							}
							break;
						}

						case "data-thread-title-update": {
							// Handle thread title update from LLM-generated title
							const titleData = parsed.data as { threadId: number; title: string };
							if (titleData?.title && titleData?.threadId === currentThreadId) {
								// Update current thread state with new title
								setCurrentThread((prev) => (prev ? { ...prev, title: titleData.title } : prev));
								// Invalidate thread list to refresh sidebar
								queryClient.invalidateQueries({
									queryKey: ["threads", String(searchSpaceId)],
								});
							}
							break;
						}

						case "data-interrupt-request": {
							wasInterrupted = true;
							const interruptData = parsed.data as Record<string, unknown>;
							const actionRequests = (interruptData.action_requests ?? []) as Array<{
								name: string;
								args: Record<string, unknown>;
							}>;
							for (const action of actionRequests) {
								const existingIdx = Array.from(toolCallIndices.entries()).find(([, idx]) => {
									const part = contentParts[idx];
									return part?.type === "tool-call" && part.toolName === action.name;
								});
								if (existingIdx) {
									updateToolCall(contentPartsState, existingIdx[0], {
										result: { __interrupt__: true, ...interruptData },
									});
								} else {
									const tcId = `interrupt-${action.name}`;
									addToolCall(contentPartsState, TOOLS_WITH_UI, tcId, action.name, action.args);
									updateToolCall(contentPartsState, tcId, {
										result: { __interrupt__: true, ...interruptData },
									});
								}
							}
							setMessages((prev) =>
								prev.map((m) =>
									m.id === assistantMsgId
										? { ...m, content: buildContentForUI(contentPartsState, TOOLS_WITH_UI) }
										: m
								)
							);
							if (currentThreadId) {
								setPendingInterrupt({
									threadId: currentThreadId,
									assistantMsgId,
									interruptData,
								});
							}
							break;
						}

						case "error":
							throw new Error(parsed.errorText || "Server error");
					}
				}

				// Skip persistence for interrupted messages -- handleResume will persist the final version
				const finalContent = buildContentForPersistence(contentPartsState, TOOLS_WITH_UI);
				if (contentParts.length > 0 && !wasInterrupted) {
					try {
						const savedMessage = await appendMessage(currentThreadId, {
							role: "assistant",
							content: finalContent,
						});

						// Update message ID from temporary to database ID so comments work immediately
						const newMsgId = `msg-${savedMessage.id}`;
						setMessages((prev) =>
							prev.map((m) => (m.id === assistantMsgId ? { ...m, id: newMsgId } : m))
						);

						// Update pending interrupt with the new persisted message ID
						setPendingInterrupt((prev) =>
							prev && prev.assistantMsgId === assistantMsgId
								? { ...prev, assistantMsgId: newMsgId }
								: prev
						);
					} catch (err) {
						console.error("Failed to persist assistant message:", err);
					}

					// Track successful response
					trackChatResponseReceived(searchSpaceId, currentThreadId);
				}
			} catch (error) {
				if (error instanceof Error && error.name === "AbortError") {
					// Request was cancelled by user - persist partial response if any content was received
					const hasContent = contentParts.some(
						(part) =>
							(part.type === "text" && part.text.length > 0) ||
							(part.type === "tool-call" && TOOLS_WITH_UI.has(part.toolName))
					);
					if (hasContent && currentThreadId) {
						const partialContent = buildContentForPersistence(contentPartsState, TOOLS_WITH_UI);
						try {
							const savedMessage = await appendMessage(currentThreadId, {
								role: "assistant",
								content: partialContent,
							});

							// Update message ID from temporary to database ID
							const newMsgId = `msg-${savedMessage.id}`;
							setMessages((prev) =>
								prev.map((m) => (m.id === assistantMsgId ? { ...m, id: newMsgId } : m))
							);
						} catch (err) {
							console.error("Failed to persist partial assistant message:", err);
						}
					}
					return;
				}
				console.error("[NewChatPage] Chat error:", error);

				// Track chat error
				trackChatError(
					searchSpaceId,
					currentThreadId,
					error instanceof Error ? error.message : "Unknown error"
				);

				toast.error("Failed to get response. Please try again.");
				// Update assistant message with error
				setMessages((prev) =>
					prev.map((m) =>
						m.id === assistantMsgId
							? {
									...m,
									content: [
										{
											type: "text",
											text: "Sorry, there was an error. Please try again.",
										},
									],
								}
							: m
					)
				);
			} finally {
				setIsRunning(false);
				abortControllerRef.current = null;
			}
		},
		[
			threadId,
			searchSpaceId,
			messages,
			mentionedDocumentIds,
			mentionedDocuments,
			sidebarDocuments,
			setMentionedDocuments,
			setSidebarDocuments,
			setMessageDocumentsMap,
			queryClient,
			currentThread,
			currentUser,
			disabledTools,
		]
	);

	const handleResume = useCallback(
		async (
			decisions: Array<{
				type: string;
				message?: string;
				edited_action?: { name: string; args: Record<string, unknown> };
			}>
		) => {
			if (!pendingInterrupt) return;
			const { threadId: resumeThreadId, assistantMsgId } = pendingInterrupt;
			setPendingInterrupt(null);
			setIsRunning(true);

			const token = getBearerToken();
			if (!token) {
				toast.error("Not authenticated. Please log in again.");
				setIsRunning(false);
				return;
			}

			const controller = new AbortController();
			abortControllerRef.current = controller;

			const currentThinkingSteps = new Map<string, ThinkingStepData>();

			const contentPartsState: ContentPartsState = {
				contentParts: [],
				currentTextPartIndex: -1,
				toolCallIndices: new Map(),
			};
			const { contentParts, toolCallIndices } = contentPartsState;

			const existingMsg = messages.find((m) => m.id === assistantMsgId);
			if (existingMsg && Array.isArray(existingMsg.content)) {
				for (const part of existingMsg.content) {
					if (typeof part === "object" && part !== null) {
						const p = part as Record<string, unknown>;
						if (p.type === "text") {
							contentParts.push({ type: "text", text: String(p.text ?? "") });
							contentPartsState.currentTextPartIndex = contentParts.length - 1;
						} else if (p.type === "tool-call") {
							toolCallIndices.set(String(p.toolCallId), contentParts.length);
							contentParts.push({
								type: "tool-call",
								toolCallId: String(p.toolCallId),
								toolName: String(p.toolName),
								args: (p.args as Record<string, unknown>) ?? {},
								result: p.result as unknown,
							});
							contentPartsState.currentTextPartIndex = -1;
						} else if (p.type === "data-thinking-steps") {
							const stepsData = p.data as { steps: ThinkingStepData[] } | undefined;
							contentParts.push({
								type: "data-thinking-steps",
								data: { steps: stepsData?.steps ?? [] },
							});
							for (const step of stepsData?.steps ?? []) {
								currentThinkingSteps.set(step.id, step);
							}
						}
					}
				}
			}

			// Merge edited args if present to fix race condition
			if (decisions.length > 0 && decisions[0].type === "edit" && decisions[0].edited_action) {
				const editedAction = decisions[0].edited_action;
				for (const part of contentParts) {
					if (part.type === "tool-call" && part.toolName === editedAction.name) {
						part.args = { ...part.args, ...editedAction.args };
						break;
					}
				}
			}

			const decisionType = decisions[0]?.type as "approve" | "reject" | undefined;
			if (decisionType) {
				for (const part of contentParts) {
					if (
						part.type === "tool-call" &&
						typeof part.result === "object" &&
						part.result !== null &&
						"__interrupt__" in (part.result as Record<string, unknown>)
					) {
						part.result = {
							...(part.result as Record<string, unknown>),
							__decided__: decisionType,
						};
					}
				}
			}

			try {
				const backendUrl = process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL || "http://localhost:8000";
				const response = await fetch(`${backendUrl}/api/v1/threads/${resumeThreadId}/resume`, {
					method: "POST",
					headers: {
						"Content-Type": "application/json",
						Authorization: `Bearer ${token}`,
					},
					body: JSON.stringify({
						search_space_id: searchSpaceId,
						decisions,
					}),
					signal: controller.signal,
				});

				if (!response.ok) {
					throw new Error(`Backend error: ${response.status}`);
				}

				for await (const parsed of readSSEStream(response)) {
					switch (parsed.type) {
						case "text-delta":
							appendText(contentPartsState, parsed.delta);
							setMessages((prev) =>
								prev.map((m) =>
									m.id === assistantMsgId
										? { ...m, content: buildContentForUI(contentPartsState, TOOLS_WITH_UI) }
										: m
								)
							);
							break;

						case "tool-input-start":
							addToolCall(contentPartsState, TOOLS_WITH_UI, parsed.toolCallId, parsed.toolName, {});
							setMessages((prev) =>
								prev.map((m) =>
									m.id === assistantMsgId
										? { ...m, content: buildContentForUI(contentPartsState, TOOLS_WITH_UI) }
										: m
								)
							);
							break;

						case "tool-input-available":
							if (toolCallIndices.has(parsed.toolCallId)) {
								updateToolCall(contentPartsState, parsed.toolCallId, {
									args: parsed.input || {},
								});
							} else {
								addToolCall(
									contentPartsState,
									TOOLS_WITH_UI,
									parsed.toolCallId,
									parsed.toolName,
									parsed.input || {}
								);
							}
							setMessages((prev) =>
								prev.map((m) =>
									m.id === assistantMsgId
										? { ...m, content: buildContentForUI(contentPartsState, TOOLS_WITH_UI) }
										: m
								)
							);
							break;

						case "tool-output-available":
							updateToolCall(contentPartsState, parsed.toolCallId, {
								result: parsed.output,
							});
							markInterruptsCompleted(contentParts);
							setMessages((prev) =>
								prev.map((m) =>
									m.id === assistantMsgId
										? { ...m, content: buildContentForUI(contentPartsState, TOOLS_WITH_UI) }
										: m
								)
							);
							break;

						case "data-thinking-step": {
							const stepData = parsed.data as ThinkingStepData;
							if (stepData?.id) {
								currentThinkingSteps.set(stepData.id, stepData);
								updateThinkingSteps(contentPartsState, currentThinkingSteps);
								setMessages((prev) =>
									prev.map((m) =>
										m.id === assistantMsgId
											? { ...m, content: buildContentForUI(contentPartsState, TOOLS_WITH_UI) }
											: m
									)
								);
							}
							break;
						}

						case "data-interrupt-request": {
							const interruptData = parsed.data as Record<string, unknown>;
							const actionRequests = (interruptData.action_requests ?? []) as Array<{
								name: string;
								args: Record<string, unknown>;
							}>;
							for (const action of actionRequests) {
								const existingIdx = Array.from(toolCallIndices.entries()).find(([, idx]) => {
									const part = contentParts[idx];
									return part?.type === "tool-call" && part.toolName === action.name;
								});
								if (existingIdx) {
									updateToolCall(contentPartsState, existingIdx[0], {
										result: {
											__interrupt__: true,
											...interruptData,
										},
									});
								} else {
									const tcId = `interrupt-${action.name}`;
									addToolCall(contentPartsState, TOOLS_WITH_UI, tcId, action.name, action.args);
									updateToolCall(contentPartsState, tcId, {
										result: {
											__interrupt__: true,
											...interruptData,
										},
									});
								}
							}
							setMessages((prev) =>
								prev.map((m) =>
									m.id === assistantMsgId
										? { ...m, content: buildContentForUI(contentPartsState, TOOLS_WITH_UI) }
										: m
								)
							);
							setPendingInterrupt({
								threadId: resumeThreadId,
								assistantMsgId,
								interruptData,
							});
							break;
						}

						case "error":
							throw new Error(parsed.errorText || "Server error");
					}
				}

				const finalContent = buildContentForPersistence(contentPartsState, TOOLS_WITH_UI);
				if (contentParts.length > 0) {
					try {
						const savedMessage = await appendMessage(resumeThreadId, {
							role: "assistant",
							content: finalContent,
						});
						const newMsgId = `msg-${savedMessage.id}`;
						setMessages((prev) =>
							prev.map((m) => (m.id === assistantMsgId ? { ...m, id: newMsgId } : m))
						);
					} catch (err) {
						console.error("Failed to persist resumed assistant message:", err);
					}
				}
			} catch (error) {
				if (error instanceof Error && error.name === "AbortError") {
					return;
				}
				console.error("[NewChatPage] Resume error:", error);
				toast.error("Failed to resume. Please try again.");
			} finally {
				setIsRunning(false);
				abortControllerRef.current = null;
			}
		},
		[pendingInterrupt, messages, searchSpaceId]
	);

	useEffect(() => {
		const handler = (e: Event) => {
			const detail = (e as CustomEvent).detail as {
				decisions: Array<{
					type: string;
					message?: string;
					edited_action?: { name: string; args: Record<string, unknown> };
				}>;
			};
			if (detail?.decisions && pendingInterrupt) {
				const decision = detail.decisions[0];
				const decisionType = decision?.type as "approve" | "reject" | "edit";

				setMessages((prev) =>
					prev.map((m) => {
						if (m.id !== pendingInterrupt.assistantMsgId) return m;
						const parts = m.content as unknown as Array<Record<string, unknown>>;
						const newContent = parts.map((part) => {
							if (
								part.type === "tool-call" &&
								typeof part.result === "object" &&
								part.result !== null &&
								"__interrupt__" in part.result
							) {
								// For edit decisions, also update the displayed args
								if (decisionType === "edit" && decision.edited_action) {
									return {
										...part,
										args: decision.edited_action.args, // Update displayed args
										result: {
											...(part.result as Record<string, unknown>),
											__decided__: decisionType,
										},
									};
								}
								return {
									...part,
									result: {
										...(part.result as Record<string, unknown>),
										__decided__: decisionType,
									},
								};
							}
							return part;
						});
						return { ...m, content: newContent as unknown as ThreadMessageLike["content"] };
					})
				);
				handleResume(detail.decisions);
			}
		};
		window.addEventListener("hitl-decision", handler);
		return () => window.removeEventListener("hitl-decision", handler);
	}, [handleResume, pendingInterrupt]);

	// Convert message (pass through since already in correct format)
	const convertMessage = useCallback(
		(message: ThreadMessageLike): ThreadMessageLike => message,
		[]
	);

	/**
	 * Handle regeneration (edit or reload) by calling the regenerate endpoint
	 * and streaming the response. This rewinds the LangGraph checkpointer state.
	 *
	 * @param newUserQuery - The new user query (for edit). Pass null/undefined for reload.
	 */
	const handleRegenerate = useCallback(
		async (newUserQuery?: string | null) => {
			if (!threadId) {
				toast.error("Cannot regenerate: no active chat thread");
				return;
			}

			// Abort any previous streaming request
			if (abortControllerRef.current) {
				abortControllerRef.current.abort();
				abortControllerRef.current = null;
			}

			const token = getBearerToken();
			if (!token) {
				toast.error("Not authenticated. Please log in again.");
				return;
			}

			// Extract the original user query BEFORE removing messages (for reload mode)
			let userQueryToDisplay = newUserQuery;
			let originalUserMessageContent: ThreadMessageLike["content"] | null = null;
			let originalUserMessageMetadata: ThreadMessageLike["metadata"] | undefined;

			if (!newUserQuery) {
				// Reload mode - find and preserve the last user message content
				const lastUserMessage = [...messages].reverse().find((m) => m.role === "user");
				if (lastUserMessage) {
					originalUserMessageContent = lastUserMessage.content;
					originalUserMessageMetadata = lastUserMessage.metadata;
					// Extract text for the API request
					for (const part of lastUserMessage.content) {
						if (typeof part === "object" && part.type === "text" && "text" in part) {
							userQueryToDisplay = part.text;
							break;
						}
					}
				}
			}

			// Remove the last two messages (user + assistant) from the UI immediately
			// The backend will also delete them from the database
			setMessages((prev) => {
				if (prev.length >= 2) {
					return prev.slice(0, -2);
				}
				return prev;
			});

			// Start streaming
			setIsRunning(true);
			const controller = new AbortController();
			abortControllerRef.current = controller;

			// Add placeholder user message if we have a new query (edit mode)
			const userMsgId = `msg-user-${Date.now()}`;
			const assistantMsgId = `msg-assistant-${Date.now()}`;
			const currentThinkingSteps = new Map<string, ThinkingStepData>();

			const contentPartsState: ContentPartsState = {
				contentParts: [],
				currentTextPartIndex: -1,
				toolCallIndices: new Map(),
			};
			const { contentParts, toolCallIndices } = contentPartsState;

			// Add placeholder messages to UI
			// Always add back the user message (with new query for edit, or original content for reload)
			const userMessage: ThreadMessageLike = {
				id: userMsgId,
				role: "user",
				content: newUserQuery
					? [{ type: "text", text: newUserQuery }]
					: originalUserMessageContent || [{ type: "text", text: userQueryToDisplay || "" }],
				createdAt: new Date(),
				metadata: newUserQuery ? undefined : originalUserMessageMetadata,
			};
			setMessages((prev) => [...prev, userMessage]);

			// Add placeholder assistant message
			setMessages((prev) => [
				...prev,
				{
					id: assistantMsgId,
					role: "assistant",
					content: [{ type: "text", text: "" }],
					createdAt: new Date(),
				},
			]);

			try {
				const response = await fetch(getRegenerateUrl(threadId), {
					method: "POST",
					headers: {
						"Content-Type": "application/json",
						Authorization: `Bearer ${token}`,
					},
					body: JSON.stringify({
						search_space_id: searchSpaceId,
						user_query: newUserQuery || null,
						disabled_tools: disabledTools.length > 0 ? disabledTools : undefined,
					}),
					signal: controller.signal,
				});

				if (!response.ok) {
					throw new Error(`Backend error: ${response.status}`);
				}

				for await (const parsed of readSSEStream(response)) {
					switch (parsed.type) {
						case "text-delta":
							appendText(contentPartsState, parsed.delta);
							setMessages((prev) =>
								prev.map((m) =>
									m.id === assistantMsgId
										? { ...m, content: buildContentForUI(contentPartsState, TOOLS_WITH_UI) }
										: m
								)
							);
							break;

						case "tool-input-start":
							addToolCall(contentPartsState, TOOLS_WITH_UI, parsed.toolCallId, parsed.toolName, {});
							setMessages((prev) =>
								prev.map((m) =>
									m.id === assistantMsgId
										? { ...m, content: buildContentForUI(contentPartsState, TOOLS_WITH_UI) }
										: m
								)
							);
							break;

						case "tool-input-available":
							if (toolCallIndices.has(parsed.toolCallId)) {
								updateToolCall(contentPartsState, parsed.toolCallId, { args: parsed.input || {} });
							} else {
								addToolCall(
									contentPartsState,
									TOOLS_WITH_UI,
									parsed.toolCallId,
									parsed.toolName,
									parsed.input || {}
								);
							}
							setMessages((prev) =>
								prev.map((m) =>
									m.id === assistantMsgId
										? { ...m, content: buildContentForUI(contentPartsState, TOOLS_WITH_UI) }
										: m
								)
							);
							break;

						case "tool-output-available":
							updateToolCall(contentPartsState, parsed.toolCallId, { result: parsed.output });
							markInterruptsCompleted(contentParts);
							if (parsed.output?.status === "pending" && parsed.output?.podcast_id) {
								const idx = toolCallIndices.get(parsed.toolCallId);
								if (idx !== undefined) {
									const part = contentParts[idx];
									if (part?.type === "tool-call" && part.toolName === "generate_podcast") {
										setActivePodcastTaskId(String(parsed.output.podcast_id));
									}
								}
							}
							setMessages((prev) =>
								prev.map((m) =>
									m.id === assistantMsgId
										? { ...m, content: buildContentForUI(contentPartsState, TOOLS_WITH_UI) }
										: m
								)
							);
							break;

						case "data-thinking-step": {
							const stepData = parsed.data as ThinkingStepData;
							if (stepData?.id) {
								currentThinkingSteps.set(stepData.id, stepData);
								updateThinkingSteps(contentPartsState, currentThinkingSteps);
								setMessages((prev) =>
									prev.map((m) =>
										m.id === assistantMsgId
											? { ...m, content: buildContentForUI(contentPartsState, TOOLS_WITH_UI) }
											: m
									)
								);
							}
							break;
						}

						case "error":
							throw new Error(parsed.errorText || "Server error");
					}
				}

				// Persist messages after streaming completes
				const finalContent = buildContentForPersistence(contentPartsState, TOOLS_WITH_UI);
				if (contentParts.length > 0) {
					try {
						// Persist user message (for both edit and reload modes, since backend deleted it)
						const userContentToPersist = newUserQuery
							? [{ type: "text", text: newUserQuery }]
							: originalUserMessageContent || [{ type: "text", text: userQueryToDisplay || "" }];

						const savedUserMessage = await appendMessage(threadId, {
							role: "user",
							content: userContentToPersist,
						});

						// Update user message ID to database ID
						const newUserMsgId = `msg-${savedUserMessage.id}`;
						setMessages((prev) =>
							prev.map((m) => (m.id === userMsgId ? { ...m, id: newUserMsgId } : m))
						);

						// Persist assistant message
						const savedMessage = await appendMessage(threadId, {
							role: "assistant",
							content: finalContent,
						});

						// Update assistant message ID to database ID
						const newMsgId = `msg-${savedMessage.id}`;
						setMessages((prev) =>
							prev.map((m) => (m.id === assistantMsgId ? { ...m, id: newMsgId } : m))
						);

						trackChatResponseReceived(searchSpaceId, threadId);
					} catch (err) {
						console.error("Failed to persist regenerated message:", err);
					}
				}
			} catch (error) {
				if (error instanceof Error && error.name === "AbortError") {
					return;
				}
				console.error("[NewChatPage] Regeneration error:", error);
				trackChatError(
					searchSpaceId,
					threadId,
					error instanceof Error ? error.message : "Unknown error"
				);
				toast.error("Failed to regenerate response. Please try again.");
				// Update assistant message with error
				setMessages((prev) =>
					prev.map((m) =>
						m.id === assistantMsgId
							? {
									...m,
									content: [{ type: "text", text: "Sorry, there was an error. Please try again." }],
								}
							: m
					)
				);
			} finally {
				setIsRunning(false);
				abortControllerRef.current = null;
			}
		},
		[threadId, searchSpaceId, messages, disabledTools]
	);

	// Handle editing a message - truncates history and regenerates with new query
	const onEdit = useCallback(
		async (message: AppendMessage) => {
			// Extract the new user query from the message content
			let newUserQuery = "";
			for (const part of message.content) {
				if (part.type === "text") {
					newUserQuery += part.text;
				}
			}

			if (!newUserQuery.trim()) {
				toast.error("Cannot edit with empty message");
				return;
			}

			// Call regenerate with the new query
			await handleRegenerate(newUserQuery.trim());
		},
		[handleRegenerate]
	);

	// Handle reloading/refreshing the last AI response
	const onReload = useCallback(async () => {
		// parentId is the ID of the message to reload from (the user message)
		// We call regenerate without a query to use the same query
		await handleRegenerate(null);
	}, [handleRegenerate]);

	// Create external store runtime
	const runtime = useExternalStoreRuntime({
		messages,
		isRunning,
		onNew,
		onEdit,
		onReload,
		convertMessage,
		onCancel: cancelRun,
	});

	// Show loading state only when loading an existing thread
	if (isInitializing) {
		return (
			<div className="flex h-[calc(100dvh-64px)] flex-col bg-main-panel px-4">
				<div className="mx-auto w-full max-w-[44rem] flex flex-1 flex-col gap-6 py-8">
					{/* User message */}
					<div className="flex justify-end">
						<Skeleton className="h-12 w-56 rounded-2xl" />
					</div>

					{/* Assistant message */}
					<div className="flex flex-col gap-2">
						<Skeleton className="h-4 w-full" />
						<Skeleton className="h-4 w-[85%]" />
						<Skeleton className="h-4 w-[70%]" />
					</div>

					{/* User message */}
					<div className="flex justify-end">
						<Skeleton className="h-12 w-40 rounded-2xl" />
					</div>

					{/* Assistant message */}
					<div className="flex flex-col gap-2">
						<Skeleton className="h-4 w-full" />
						<Skeleton className="h-4 w-[90%]" />
						<Skeleton className="h-4 w-[60%]" />
					</div>
				</div>

				{/* Input bar */}
				<div className="sticky bottom-0 pb-6 bg-main-panel">
					<div className="mx-auto w-full max-w-[44rem]">
						<Skeleton className="h-24 w-full rounded-2xl" />
					</div>
				</div>
			</div>
		);
	}

	// Show error state only if we tried to load an existing thread but failed
	// For new chats (urlChatId === 0), threadId being null is expected (lazy creation)
	if (!threadId && urlChatId > 0) {
		return (
			<div className="flex h-[calc(100dvh-64px)] flex-col items-center justify-center gap-4">
				<div className="text-destructive">Failed to load chat</div>
				<button
					type="button"
					onClick={() => {
						setIsInitializing(true);
						initializeThread();
					}}
					className="rounded-md bg-primary px-4 py-2 text-primary-foreground hover:bg-primary/90"
				>
					Try Again
				</button>
			</div>
		);
	}

	return (
		<AssistantRuntimeProvider runtime={runtime}>
			<ThinkingStepsDataUI />
			<QuickAskAutoSubmit />
			<div key={searchSpaceId} className="flex h-[calc(100dvh-64px)] overflow-hidden">
				<div className="flex-1 flex flex-col min-w-0 overflow-hidden">
					<Thread />
				</div>
				<MobileReportPanel />
				<MobileEditorPanel />
				<MobileHitlEditPanel />
			</div>
		</AssistantRuntimeProvider>
	);
}
