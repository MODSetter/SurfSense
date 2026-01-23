"use client";

import {
	type AppendMessage,
	AssistantRuntimeProvider,
	type ThreadMessageLike,
	useExternalStoreRuntime,
} from "@assistant-ui/react";
import { useQueryClient } from "@tanstack/react-query";
import { useAtomValue, useSetAtom } from "jotai";
import { useParams, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { z } from "zod";
import { currentThreadAtom } from "@/atoms/chat/current-thread.atom";
import {
	type MentionedDocumentInfo,
	mentionedDocumentIdsAtom,
	mentionedDocumentsAtom,
	messageDocumentsMapAtom,
} from "@/atoms/chat/mentioned-documents.atom";
import {
	clearPlanOwnerRegistry,
	// extractWriteTodosFromContent,
	hydratePlanStateAtom,
} from "@/atoms/chat/plan-state.atom";
import { membersAtom } from "@/atoms/members/members-query.atoms";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import { Thread } from "@/components/assistant-ui/thread";
import { ChatHeader } from "@/components/new-chat/chat-header";
import type { ThinkingStep } from "@/components/tool-ui/deepagent-thinking";
import { DisplayImageToolUI } from "@/components/tool-ui/display-image";
import { GeneratePodcastToolUI } from "@/components/tool-ui/generate-podcast";
import { LinkPreviewToolUI } from "@/components/tool-ui/link-preview";
import { ScrapeWebpageToolUI } from "@/components/tool-ui/scrape-webpage";
import { RecallMemoryToolUI, SaveMemoryToolUI } from "@/components/tool-ui/user-memory";
import { useChatSessionStateSync } from "@/hooks/use-chat-session-state";
import { useMessagesElectric } from "@/hooks/use-messages-electric";
// import { WriteTodosToolUI } from "@/components/tool-ui/write-todos";
import { getBearerToken } from "@/lib/auth-utils";
import { createAttachmentAdapter, extractAttachmentContent } from "@/lib/chat/attachment-adapter";
import {
	isPodcastGenerating,
	looksLikePodcastRequest,
	setActivePodcastTaskId,
} from "@/lib/chat/podcast-state";
import {
	appendMessage,
	type ChatVisibility,
	createThread,
	getRegenerateUrl,
	getThreadFull,
	getThreadMessages,
	type MessageRecord,
	type ThreadRecord,
} from "@/lib/chat/thread-persistence";
import {
	trackChatCreated,
	trackChatError,
	trackChatMessageSent,
	trackChatResponseReceived,
} from "@/lib/posthog/events";

/**
 * Extract thinking steps from message content
 */
function extractThinkingSteps(content: unknown): ThinkingStep[] {
	if (!Array.isArray(content)) return [];

	const thinkingPart = content.find(
		(part: unknown) =>
			typeof part === "object" &&
			part !== null &&
			"type" in part &&
			(part as { type: string }).type === "thinking-steps"
	) as { type: "thinking-steps"; steps: ThinkingStep[] } | undefined;

	return thinkingPart?.steps || [];
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
 * Zod schema for persisted attachment info
 */
const PersistedAttachmentSchema = z.object({
	id: z.string(),
	name: z.string(),
	type: z.string(),
	contentType: z.string().optional(),
	imageDataUrl: z.string().optional(),
	extractedContent: z.string().optional(),
});

const AttachmentsPartSchema = z.object({
	type: z.literal("attachments"),
	items: z.array(PersistedAttachmentSchema),
});

type PersistedAttachment = z.infer<typeof PersistedAttachmentSchema>;

/**
 * Extract persisted attachments from message content (type-safe with Zod)
 */
function extractPersistedAttachments(content: unknown): PersistedAttachment[] {
	if (!Array.isArray(content)) return [];

	for (const part of content) {
		const result = AttachmentsPartSchema.safeParse(part);
		if (result.success) {
			return result.data.items;
		}
	}

	return [];
}

/**
 * Convert backend message to assistant-ui ThreadMessageLike format
 * Filters out 'thinking-steps' part as it's handled separately via messageThinkingSteps
 * Restores attachments for user messages from persisted data
 */
function convertToThreadMessage(msg: MessageRecord): ThreadMessageLike {
	let content: ThreadMessageLike["content"];

	if (typeof msg.content === "string") {
		content = [{ type: "text", text: msg.content }];
	} else if (Array.isArray(msg.content)) {
		// Filter out custom metadata parts - they're handled separately
		const filteredContent = msg.content.filter((part: unknown) => {
			if (typeof part !== "object" || part === null || !("type" in part)) return true;
			const partType = (part as { type: string }).type;
			// Filter out thinking-steps, mentioned-documents, and attachments
			return (
				partType !== "thinking-steps" &&
				partType !== "mentioned-documents" &&
				partType !== "attachments"
			);
		});
		content =
			filteredContent.length > 0
				? (filteredContent as ThreadMessageLike["content"])
				: [{ type: "text", text: "" }];
	} else {
		content = [{ type: "text", text: String(msg.content) }];
	}

	// Restore attachments for user messages
	let attachments: ThreadMessageLike["attachments"];
	if (msg.role === "user") {
		const persistedAttachments = extractPersistedAttachments(msg.content);
		if (persistedAttachments.length > 0) {
			attachments = persistedAttachments.map((att) => ({
				id: att.id,
				name: att.name,
				type: att.type as "document" | "image" | "file",
				contentType: att.contentType || "application/octet-stream",
				status: { type: "complete" as const },
				content: [],
				// Custom fields for our ChatAttachment interface
				imageDataUrl: att.imageDataUrl,
				extractedContent: att.extractedContent,
			}));
		}
	}

	// Build metadata.custom for author display in shared chats
	const metadata = msg.author_id
		? {
				custom: {
					author: {
						displayName: msg.author_display_name ?? null,
						avatarUrl: msg.author_avatar_url ?? null,
					},
				},
			}
		: undefined;

	return {
		id: `msg-${msg.id}`,
		role: msg.role,
		content,
		createdAt: new Date(msg.created_at),
		attachments,
		metadata,
	};
}

/**
 * Tools that should render custom UI in the chat.
 */
const TOOLS_WITH_UI = new Set([
	"generate_podcast",
	"link_preview",
	"display_image",
	"scrape_webpage",
	// "write_todos", // Disabled for now
]);

/**
 * Type for thinking step data from the backend
 */
interface ThinkingStepData {
	id: string;
	title: string;
	status: "pending" | "in_progress" | "completed";
	items: string[];
}

export default function NewChatPage() {
	const params = useParams();
	const queryClient = useQueryClient();
	const [isInitializing, setIsInitializing] = useState(true);
	const [threadId, setThreadId] = useState<number | null>(null);
	const [currentThread, setCurrentThread] = useState<ThreadRecord | null>(null);
	const [messages, setMessages] = useState<ThreadMessageLike[]>([]);
	const [isRunning, setIsRunning] = useState(false);
	// Store thinking steps per message ID - kept separate from content to avoid
	// "unsupported part type" errors from assistant-ui
	const [messageThinkingSteps, setMessageThinkingSteps] = useState<Map<string, ThinkingStep[]>>(
		new Map()
	);
	const abortControllerRef = useRef<AbortController | null>(null);

	// Get mentioned document IDs from the composer
	const mentionedDocumentIds = useAtomValue(mentionedDocumentIdsAtom);
	const mentionedDocuments = useAtomValue(mentionedDocumentsAtom);
	const setMentionedDocumentIds = useSetAtom(mentionedDocumentIdsAtom);
	const setMentionedDocuments = useSetAtom(mentionedDocumentsAtom);
	const setMessageDocumentsMap = useSetAtom(messageDocumentsMapAtom);
	const hydratePlanState = useSetAtom(hydratePlanStateAtom);
	const setCurrentThreadState = useSetAtom(currentThreadAtom);

	// Get current user for author info in shared chats
	const { data: currentUser } = useAtomValue(currentUserAtom);

	// Live collaboration: sync session state and messages via Electric SQL
	useChatSessionStateSync(threadId);
	const { data: membersData } = useAtomValue(membersAtom);

	const handleElectricMessagesUpdate = useCallback(
		(
			electricMessages: {
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
				if (electricMessages.length < prev.length) {
					return prev;
				}

				return electricMessages.map((msg) => {
					const member = msg.author_id
						? membersData?.find((m) => m.user_id === msg.author_id)
						: null;

					return convertToThreadMessage({
						id: msg.id,
						thread_id: msg.thread_id,
						role: msg.role.toLowerCase() as "user" | "assistant" | "system",
						content: msg.content,
						author_id: msg.author_id,
						created_at: msg.created_at,
						author_display_name: member?.user_display_name ?? null,
						author_avatar_url: member?.user_avatar_url ?? null,
					});
				});
			});
		},
		[isRunning, membersData]
	);

	useMessagesElectric(threadId, handleElectricMessagesUpdate);

	// Create the attachment adapter for file processing
	const attachmentAdapter = useMemo(() => createAttachmentAdapter(), []);

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
	const initializeThread = useCallback(async () => {
		setIsInitializing(true);

		// Reset all state when switching between chats to prevent stale data
		setMessages([]);
		setThreadId(null);
		setCurrentThread(null);
		setMessageThinkingSteps(new Map());
		setMentionedDocumentIds({
			surfsense_doc_ids: [],
			document_ids: [],
		});
		setMentionedDocuments([]);
		setMessageDocumentsMap({});
		clearPlanOwnerRegistry(); // Reset plan ownership for new chat

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

					// Extract and restore thinking steps from persisted messages
					const restoredThinkingSteps = new Map<string, ThinkingStep[]>();
					// Extract and restore mentioned documents from persisted messages
					const restoredDocsMap: Record<string, MentionedDocumentInfo[]> = {};

					for (const msg of messagesResponse.messages) {
						if (msg.role === "assistant") {
							const steps = extractThinkingSteps(msg.content);
							if (steps.length > 0) {
								restoredThinkingSteps.set(`msg-${msg.id}`, steps);
							}
						}
						if (msg.role === "user") {
							const docs = extractMentionedDocuments(msg.content);
							if (docs.length > 0) {
								restoredDocsMap[`msg-${msg.id}`] = docs;
							}
						}
					}
					if (restoredThinkingSteps.size > 0) {
						setMessageThinkingSteps(restoredThinkingSteps);
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
		setMessageDocumentsMap,
		setMentionedDocumentIds,
		setMentionedDocuments,
		hydratePlanState,
	]);

	// Initialize on mount
	useEffect(() => {
		initializeThread();
	}, [initializeThread]);

	// Handle scroll to comment from URL query params (e.g., from inbox item click)
	const searchParams = useSearchParams();
	const targetCommentId = searchParams.get("commentId");

	useEffect(() => {
		if (!targetCommentId || isInitializing || messages.length === 0) return;

		const tryScroll = () => {
			const el = document.querySelector(`[data-comment-id="${targetCommentId}"]`);
			if (el) {
				el.scrollIntoView({ behavior: "smooth", block: "center" });
				return true;
			}
			return false;
		};

		// Try immediately
		if (tryScroll()) return;

		// Retry every 200ms for up to 10 seconds
		const intervalId = setInterval(() => {
			if (tryScroll()) clearInterval(intervalId);
		}, 200);

		const timeoutId = setTimeout(() => clearInterval(intervalId), 10000);

		return () => {
			clearInterval(intervalId);
			clearTimeout(timeoutId);
		};
	}, [targetCommentId, isInitializing, messages.length]);

	// Sync current thread state to atom
	useEffect(() => {
		setCurrentThreadState({
			id: currentThread?.id ?? null,
			visibility: currentThread?.visibility ?? null,
			hasComments: currentThread?.has_comments ?? false,
			addingCommentToMessageId: null,
		});
	}, [currentThread, setCurrentThreadState]);

	// Cancel ongoing request
	const cancelRun = useCallback(async () => {
		if (abortControllerRef.current) {
			abortControllerRef.current.abort();
			abortControllerRef.current = null;
		}
		setIsRunning(false);
	}, []);

	// Handle visibility change from ChatShareButton
	const handleVisibilityChange = useCallback(
		(newVisibility: ChatVisibility) => {
			setCurrentThread((prev) => (prev ? { ...prev, visibility: newVisibility } : null));
			// Refetch all thread queries so sidebar reflects the change immediately
			// Use predicate to match any query that starts with "threads"
			queryClient.refetchQueries({
				predicate: (query) => Array.isArray(query.queryKey) && query.queryKey[0] === "threads",
			});
		},
		[queryClient]
	);

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

			// Extract attachments from message
			// AppendMessage.attachments contains the processed attachment objects (from adapter.send())
			const messageAttachments: Array<Record<string, unknown>> = [];
			if (message.attachments && message.attachments.length > 0) {
				for (const att of message.attachments) {
					messageAttachments.push(att as unknown as Record<string, unknown>);
				}
			}

			if (!userQuery.trim() && messageAttachments.length === 0) return;

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
					// Set currentThread so ChatHeader can show share button immediately
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
				attachments: message.attachments || [],
				metadata: authorMetadata,
			};
			setMessages((prev) => [...prev, userMessage]);

			// Track message sent
			trackChatMessageSent(searchSpaceId, currentThreadId, {
				hasAttachments: messageAttachments.length > 0,
				hasMentionedDocuments:
					mentionedDocumentIds.surfsense_doc_ids.length > 0 ||
					mentionedDocumentIds.document_ids.length > 0,
				messageLength: userQuery.length,
			});

			// Store mentioned documents with this message for display
			if (mentionedDocuments.length > 0) {
				const docsInfo: MentionedDocumentInfo[] = mentionedDocuments.map((doc) => ({
					id: doc.id,
					title: doc.title,
					document_type: doc.document_type,
				}));
				setMessageDocumentsMap((prev) => ({
					...prev,
					[userMsgId]: docsInfo,
				}));
			}

			// Persist user message with mentioned documents and attachments (don't await, fire and forget)
			const persistContent: unknown[] = [...message.content];

			// Add mentioned documents for persistence
			if (mentionedDocuments.length > 0) {
				persistContent.push({
					type: "mentioned-documents",
					documents: mentionedDocuments.map((doc) => ({
						id: doc.id,
						title: doc.title,
						document_type: doc.document_type,
					})),
				});
			}

			// Add attachments for persistence (so they survive page reload)
			if (message.attachments && message.attachments.length > 0) {
				persistContent.push({
					type: "attachments",
					items: message.attachments.map((att) => ({
						id: att.id,
						name: att.name,
						type: att.type,
						contentType: (att as { contentType?: string }).contentType,
						// Include imageDataUrl for images so they can be displayed after reload
						imageDataUrl: (att as { imageDataUrl?: string }).imageDataUrl,
						// Include extractedContent for context (already extracted, no re-processing needed)
						extractedContent: (att as { extractedContent?: string }).extractedContent,
					})),
				});
			}

			appendMessage(currentThreadId, {
				role: "user",
				content: persistContent,
			})
				.then(() => {
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

			// Ordered content parts to preserve inline tool call positions
			// Each part is either a text segment or a tool call
			type ContentPart =
				| { type: "text"; text: string }
				| {
						type: "tool-call";
						toolCallId: string;
						toolName: string;
						args: Record<string, unknown>;
						result?: unknown;
				  };
			const contentParts: ContentPart[] = [];

			// Track the current text segment index (for appending text deltas)
			let currentTextPartIndex = -1;

			// Map to track tool call indices for updating results
			const toolCallIndices = new Map<string, number>();

			// Helper to get or create the current text part for appending text
			const appendText = (delta: string) => {
				if (currentTextPartIndex >= 0 && contentParts[currentTextPartIndex]?.type === "text") {
					// Append to existing text part
					(contentParts[currentTextPartIndex] as { type: "text"; text: string }).text += delta;
				} else {
					// Create new text part
					contentParts.push({ type: "text", text: delta });
					currentTextPartIndex = contentParts.length - 1;
				}
			};

			// Helper to add a tool call (this "breaks" the current text segment)
			const addToolCall = (toolCallId: string, toolName: string, args: Record<string, unknown>) => {
				if (TOOLS_WITH_UI.has(toolName)) {
					contentParts.push({
						type: "tool-call",
						toolCallId,
						toolName,
						args,
					});
					toolCallIndices.set(toolCallId, contentParts.length - 1);
					// Reset text part index so next text creates a new segment
					currentTextPartIndex = -1;
				}
			};

			// Helper to update a tool call's args or result
			const updateToolCall = (
				toolCallId: string,
				update: { args?: Record<string, unknown>; result?: unknown }
			) => {
				const index = toolCallIndices.get(toolCallId);
				if (index !== undefined && contentParts[index]?.type === "tool-call") {
					const tc = contentParts[index] as ContentPart & { type: "tool-call" };
					if (update.args) tc.args = update.args;
					if (update.result !== undefined) tc.result = update.result;
				}
			};

			// Helper to build content for UI (without thinking-steps to avoid assistant-ui errors)
			const buildContentForUI = (): ThreadMessageLike["content"] => {
				// Filter to only include text parts with content and tool-calls with UI
				const filtered = contentParts.filter((part) => {
					if (part.type === "text") return part.text.length > 0;
					if (part.type === "tool-call") return TOOLS_WITH_UI.has(part.toolName);
					return false;
				});
				return filtered.length > 0
					? (filtered as ThreadMessageLike["content"])
					: [{ type: "text", text: "" }];
			};

			// Helper to build content for persistence (includes thinking-steps for restoration)
			const buildContentForPersistence = (): unknown[] => {
				const parts: unknown[] = [];

				// Include thinking steps for persistence
				if (currentThinkingSteps.size > 0) {
					parts.push({
						type: "thinking-steps",
						steps: Array.from(currentThinkingSteps.values()),
					});
				}

				// Add content parts (filtered)
				for (const part of contentParts) {
					if (part.type === "text" && part.text.length > 0) {
						parts.push(part);
					} else if (part.type === "tool-call" && TOOLS_WITH_UI.has(part.toolName)) {
						parts.push(part);
					}
				}

				return parts.length > 0 ? parts : [{ type: "text", text: "" }];
			};

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

				// Extract attachment content to send with the request
				const attachments = extractAttachmentContent(messageAttachments);

				// Get mentioned document IDs for context (separate fields for backend)
				const hasDocumentIds = mentionedDocumentIds.document_ids.length > 0;
				const hasSurfsenseDocIds = mentionedDocumentIds.surfsense_doc_ids.length > 0;

				// Clear mentioned documents after capturing them
				if (hasDocumentIds || hasSurfsenseDocIds) {
					setMentionedDocumentIds({
						surfsense_doc_ids: [],
						document_ids: [],
					});
					setMentionedDocuments([]);
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
						attachments: attachments.length > 0 ? attachments : undefined,
						mentioned_document_ids: hasDocumentIds ? mentionedDocumentIds.document_ids : undefined,
						mentioned_surfsense_doc_ids: hasSurfsenseDocIds
							? mentionedDocumentIds.surfsense_doc_ids
							: undefined,
					}),
					signal: controller.signal,
				});

				if (!response.ok) {
					throw new Error(`Backend error: ${response.status}`);
				}

				if (!response.body) {
					throw new Error("No response body");
				}

				// Parse SSE stream
				const reader = response.body.getReader();
				const decoder = new TextDecoder();
				let buffer = "";

				try {
					while (true) {
						const { done, value } = await reader.read();
						if (done) break;

						buffer += decoder.decode(value, { stream: true });
						const events = buffer.split(/\r?\n\r?\n/);
						buffer = events.pop() || "";

						for (const event of events) {
							const lines = event.split(/\r?\n/);
							for (const line of lines) {
								if (!line.startsWith("data: ")) continue;
								const data = line.slice(6).trim();
								if (!data || data === "[DONE]") continue;

								try {
									const parsed = JSON.parse(data);

									switch (parsed.type) {
										case "text-delta":
											appendText(parsed.delta);
											setMessages((prev) =>
												prev.map((m) =>
													m.id === assistantMsgId ? { ...m, content: buildContentForUI() } : m
												)
											);
											break;

										case "tool-input-start":
											// Add tool call inline - this breaks the current text segment
											addToolCall(parsed.toolCallId, parsed.toolName, {});
											setMessages((prev) =>
												prev.map((m) =>
													m.id === assistantMsgId ? { ...m, content: buildContentForUI() } : m
												)
											);
											break;

										case "tool-input-available": {
											// Update existing tool call's args, or add if not exists
											if (toolCallIndices.has(parsed.toolCallId)) {
												updateToolCall(parsed.toolCallId, { args: parsed.input || {} });
											} else {
												addToolCall(parsed.toolCallId, parsed.toolName, parsed.input || {});
											}
											setMessages((prev) =>
												prev.map((m) =>
													m.id === assistantMsgId ? { ...m, content: buildContentForUI() } : m
												)
											);
											break;
										}

										case "tool-output-available": {
											// Update the tool call with its result
											updateToolCall(parsed.toolCallId, { result: parsed.output });
											// Handle podcast-specific logic
											if (parsed.output?.status === "processing" && parsed.output?.task_id) {
												// Check if this is a podcast tool by looking at the content part
												const idx = toolCallIndices.get(parsed.toolCallId);
												if (idx !== undefined) {
													const part = contentParts[idx];
													if (part?.type === "tool-call" && part.toolName === "generate_podcast") {
														setActivePodcastTaskId(parsed.output.task_id);
													}
												}
											}
											setMessages((prev) =>
												prev.map((m) =>
													m.id === assistantMsgId ? { ...m, content: buildContentForUI() } : m
												)
											);
											break;
										}

										case "data-thinking-step": {
											// Handle thinking step events for chain-of-thought display
											const stepData = parsed.data as ThinkingStepData;
											if (stepData?.id) {
												currentThinkingSteps.set(stepData.id, stepData);
												// Update thinking steps state for rendering
												// The ThinkingStepsScrollHandler in Thread component
												// will handle auto-scrolling when this state changes
												setMessageThinkingSteps((prev) => {
													const newMap = new Map(prev);
													newMap.set(assistantMsgId, Array.from(currentThinkingSteps.values()));
													return newMap;
												});
											}
											break;
										}

										case "error":
											throw new Error(parsed.errorText || "Server error");
									}
								} catch (e) {
									if (e instanceof SyntaxError) continue;
									throw e;
								}
							}
						}
					}
				} finally {
					reader.releaseLock();
				}

				// Persist assistant message (with thinking steps for restoration on refresh)
				const finalContent = buildContentForPersistence();
				if (contentParts.length > 0) {
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

						// Also update thinking steps map with new ID
						setMessageThinkingSteps((prev) => {
							const steps = prev.get(assistantMsgId);
							if (steps) {
								const newMap = new Map(prev);
								newMap.delete(assistantMsgId);
								newMap.set(newMsgId, steps);
								return newMap;
							}
							return prev;
						});
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
						const partialContent = buildContentForPersistence();
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
				// Note: We no longer clear thinking steps - they persist with the message
			}
		},
		[
			threadId,
			searchSpaceId,
			messages,
			mentionedDocumentIds,
			mentionedDocuments,
			setMentionedDocumentIds,
			setMentionedDocuments,
			setMessageDocumentsMap,
			queryClient,
			currentThread,
			currentUser,
		]
	);

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
			let originalUserMessageAttachments: ThreadMessageLike["attachments"] | undefined;
			let originalUserMessageMetadata: ThreadMessageLike["metadata"] | undefined;

			if (!newUserQuery) {
				// Reload mode - find and preserve the last user message content
				const lastUserMessage = [...messages].reverse().find((m) => m.role === "user");
				if (lastUserMessage) {
					originalUserMessageContent = lastUserMessage.content;
					originalUserMessageAttachments = lastUserMessage.attachments;
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

			// Clear thinking steps for the removed messages
			setMessageThinkingSteps((prev) => {
				const newMap = new Map(prev);
				// Remove thinking steps for the last two messages
				const lastTwoIds = messages
					.slice(-2)
					.map((m) => m.id)
					.filter((id): id is string => !!id);
				for (const id of lastTwoIds) {
					newMap.delete(id);
				}
				return newMap;
			});

			// Start streaming
			setIsRunning(true);
			const controller = new AbortController();
			abortControllerRef.current = controller;

			// Add placeholder user message if we have a new query (edit mode)
			const userMsgId = `msg-user-${Date.now()}`;
			const assistantMsgId = `msg-assistant-${Date.now()}`;
			const currentThinkingSteps = new Map<string, ThinkingStepData>();

			// Content parts tracking (same as onNew)
			type ContentPart =
				| { type: "text"; text: string }
				| {
						type: "tool-call";
						toolCallId: string;
						toolName: string;
						args: Record<string, unknown>;
						result?: unknown;
				  };
			const contentParts: ContentPart[] = [];
			let currentTextPartIndex = -1;
			const toolCallIndices = new Map<string, number>();

			const appendText = (delta: string) => {
				if (currentTextPartIndex >= 0 && contentParts[currentTextPartIndex]?.type === "text") {
					(contentParts[currentTextPartIndex] as { type: "text"; text: string }).text += delta;
				} else {
					contentParts.push({ type: "text", text: delta });
					currentTextPartIndex = contentParts.length - 1;
				}
			};

			const addToolCall = (toolCallId: string, toolName: string, args: Record<string, unknown>) => {
				if (TOOLS_WITH_UI.has(toolName)) {
					contentParts.push({ type: "tool-call", toolCallId, toolName, args });
					toolCallIndices.set(toolCallId, contentParts.length - 1);
					currentTextPartIndex = -1;
				}
			};

			const updateToolCall = (
				toolCallId: string,
				update: { args?: Record<string, unknown>; result?: unknown }
			) => {
				const index = toolCallIndices.get(toolCallId);
				if (index !== undefined && contentParts[index]?.type === "tool-call") {
					const tc = contentParts[index] as ContentPart & { type: "tool-call" };
					if (update.args) tc.args = update.args;
					if (update.result !== undefined) tc.result = update.result;
				}
			};

			const buildContentForUI = (): ThreadMessageLike["content"] => {
				const filtered = contentParts.filter((part) => {
					if (part.type === "text") return part.text.length > 0;
					if (part.type === "tool-call") return TOOLS_WITH_UI.has(part.toolName);
					return false;
				});
				return filtered.length > 0
					? (filtered as ThreadMessageLike["content"])
					: [{ type: "text", text: "" }];
			};

			const buildContentForPersistence = (): unknown[] => {
				const parts: unknown[] = [];
				if (currentThinkingSteps.size > 0) {
					parts.push({
						type: "thinking-steps",
						steps: Array.from(currentThinkingSteps.values()),
					});
				}
				for (const part of contentParts) {
					if (part.type === "text" && part.text.length > 0) {
						parts.push(part);
					} else if (part.type === "tool-call" && TOOLS_WITH_UI.has(part.toolName)) {
						parts.push(part);
					}
				}
				return parts.length > 0 ? parts : [{ type: "text", text: "" }];
			};

			// Add placeholder messages to UI
			// Always add back the user message (with new query for edit, or original content for reload)
			const userMessage: ThreadMessageLike = {
				id: userMsgId,
				role: "user",
				content: newUserQuery
					? [{ type: "text", text: newUserQuery }]
					: originalUserMessageContent || [{ type: "text", text: userQueryToDisplay || "" }],
				createdAt: new Date(),
				attachments: newUserQuery ? undefined : originalUserMessageAttachments,
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
					}),
					signal: controller.signal,
				});

				if (!response.ok) {
					throw new Error(`Backend error: ${response.status}`);
				}

				if (!response.body) {
					throw new Error("No response body");
				}

				// Parse SSE stream (same logic as onNew)
				const reader = response.body.getReader();
				const decoder = new TextDecoder();
				let buffer = "";

				try {
					while (true) {
						const { done, value } = await reader.read();
						if (done) break;

						buffer += decoder.decode(value, { stream: true });
						const events = buffer.split(/\r?\n\r?\n/);
						buffer = events.pop() || "";

						for (const event of events) {
							const lines = event.split(/\r?\n/);
							for (const line of lines) {
								if (!line.startsWith("data: ")) continue;
								const data = line.slice(6).trim();
								if (!data || data === "[DONE]") continue;

								try {
									const parsed = JSON.parse(data);

									switch (parsed.type) {
										case "text-delta":
											appendText(parsed.delta);
											setMessages((prev) =>
												prev.map((m) =>
													m.id === assistantMsgId ? { ...m, content: buildContentForUI() } : m
												)
											);
											break;

										case "tool-input-start":
											addToolCall(parsed.toolCallId, parsed.toolName, {});
											setMessages((prev) =>
												prev.map((m) =>
													m.id === assistantMsgId ? { ...m, content: buildContentForUI() } : m
												)
											);
											break;

										case "tool-input-available":
											if (toolCallIndices.has(parsed.toolCallId)) {
												updateToolCall(parsed.toolCallId, { args: parsed.input || {} });
											} else {
												addToolCall(parsed.toolCallId, parsed.toolName, parsed.input || {});
											}
											setMessages((prev) =>
												prev.map((m) =>
													m.id === assistantMsgId ? { ...m, content: buildContentForUI() } : m
												)
											);
											break;

										case "tool-output-available":
											updateToolCall(parsed.toolCallId, { result: parsed.output });
											if (parsed.output?.status === "processing" && parsed.output?.task_id) {
												const idx = toolCallIndices.get(parsed.toolCallId);
												if (idx !== undefined) {
													const part = contentParts[idx];
													if (part?.type === "tool-call" && part.toolName === "generate_podcast") {
														setActivePodcastTaskId(parsed.output.task_id);
													}
												}
											}
											setMessages((prev) =>
												prev.map((m) =>
													m.id === assistantMsgId ? { ...m, content: buildContentForUI() } : m
												)
											);
											break;

										case "data-thinking-step": {
											const stepData = parsed.data as ThinkingStepData;
											if (stepData?.id) {
												currentThinkingSteps.set(stepData.id, stepData);
												setMessageThinkingSteps((prev) => {
													const newMap = new Map(prev);
													newMap.set(assistantMsgId, Array.from(currentThinkingSteps.values()));
													return newMap;
												});
											}
											break;
										}

										case "error":
											throw new Error(parsed.errorText || "Server error");
									}
								} catch (e) {
									if (e instanceof SyntaxError) continue;
									throw e;
								}
							}
						}
					}
				} finally {
					reader.releaseLock();
				}

				// Persist messages after streaming completes
				const finalContent = buildContentForPersistence();
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

						setMessageThinkingSteps((prev) => {
							const steps = prev.get(assistantMsgId);
							if (steps) {
								const newMap = new Map(prev);
								newMap.delete(assistantMsgId);
								newMap.set(newMsgId, steps);
								return newMap;
							}
							return prev;
						});

						// Track successful response
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
		[threadId, searchSpaceId, messages, setMessageThinkingSteps]
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
	const onReload = useCallback(
		async (parentId: string | null) => {
			// parentId is the ID of the message to reload from (the user message)
			// We call regenerate without a query to use the same query
			await handleRegenerate(null);
		},
		[handleRegenerate]
	);

	// Create external store runtime with attachment support
	const runtime = useExternalStoreRuntime({
		messages,
		isRunning,
		onNew,
		onEdit,
		onReload,
		convertMessage,
		onCancel: cancelRun,
		adapters: {
			attachments: attachmentAdapter,
		},
	});

	// Show loading state only when loading an existing thread
	if (isInitializing) {
		return (
			<div className="flex h-[calc(100vh-64px)] items-center justify-center">
				<div className="text-muted-foreground">Loading chat...</div>
			</div>
		);
	}

	// Show error state only if we tried to load an existing thread but failed
	// For new chats (urlChatId === 0), threadId being null is expected (lazy creation)
	if (!threadId && urlChatId > 0) {
		return (
			<div className="flex h-[calc(100vh-64px)] flex-col items-center justify-center gap-4">
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
			<GeneratePodcastToolUI />
			<LinkPreviewToolUI />
			<DisplayImageToolUI />
			<ScrapeWebpageToolUI />
			<SaveMemoryToolUI />
			<RecallMemoryToolUI />
			{/* <WriteTodosToolUI /> Disabled for now */}
			<div className="flex flex-col h-[calc(100vh-64px)] overflow-hidden">
				<Thread
					messageThinkingSteps={messageThinkingSteps}
					header={<ChatHeader searchSpaceId={searchSpaceId} />}
				/>
			</div>
		</AssistantRuntimeProvider>
	);
}
