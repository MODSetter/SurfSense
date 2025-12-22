"use client";

import {
	type AppendMessage,
	AssistantRuntimeProvider,
	type ThreadMessageLike,
	useExternalStoreRuntime,
} from "@assistant-ui/react";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { Thread } from "@/components/assistant-ui/thread";
import { GeneratePodcastToolUI } from "@/components/tool-ui/generate-podcast";
import { LinkPreviewToolUI } from "@/components/tool-ui/link-preview";
import type { ThinkingStep } from "@/components/tool-ui/deepagent-thinking";
import { getBearerToken } from "@/lib/auth-utils";
import { createAttachmentAdapter, extractAttachmentContent } from "@/lib/chat/attachment-adapter";
import {
	isPodcastGenerating,
	looksLikePodcastRequest,
	setActivePodcastTaskId,
} from "@/lib/chat/podcast-state";
import {
	appendMessage,
	createThread,
	getThreadMessages,
	type MessageRecord,
} from "@/lib/chat/thread-persistence";

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
 * Convert backend message to assistant-ui ThreadMessageLike format
 * Filters out 'thinking-steps' part as it's handled separately
 */
function convertToThreadMessage(msg: MessageRecord): ThreadMessageLike {
	let content: ThreadMessageLike["content"];

	if (typeof msg.content === "string") {
		content = [{ type: "text", text: msg.content }];
	} else if (Array.isArray(msg.content)) {
		// Filter out thinking-steps part - it's handled separately via messageThinkingSteps
		const filteredContent = msg.content.filter(
			(part: unknown) => 
				!(typeof part === "object" && 
				  part !== null && 
				  "type" in part && 
				  (part as { type: string }).type === "thinking-steps")
		);
		content = filteredContent.length > 0 
			? (filteredContent as ThreadMessageLike["content"])
			: [{ type: "text", text: "" }];
	} else {
		content = [{ type: "text", text: String(msg.content) }];
	}

	return {
		id: `msg-${msg.id}`,
		role: msg.role,
		content,
		createdAt: new Date(msg.created_at),
	};
}

/**
 * Tools that should render custom UI in the chat.
 */
const TOOLS_WITH_UI = new Set(["generate_podcast", "link_preview"]);

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
	const router = useRouter();
	const [isInitializing, setIsInitializing] = useState(true);
	const [threadId, setThreadId] = useState<number | null>(null);
	const [messages, setMessages] = useState<ThreadMessageLike[]>([]);
	const [isRunning, setIsRunning] = useState(false);
	// Store thinking steps per message ID
	const [messageThinkingSteps, setMessageThinkingSteps] = useState<
		Map<string, ThinkingStep[]>
	>(new Map());
	const abortControllerRef = useRef<AbortController | null>(null);

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
	const initializeThread = useCallback(async () => {
		setIsInitializing(true);

		try {
			if (urlChatId > 0) {
				// Thread exists - load messages
				setThreadId(urlChatId);
				const response = await getThreadMessages(urlChatId);
				if (response.messages && response.messages.length > 0) {
					const loadedMessages = response.messages.map(convertToThreadMessage);
					setMessages(loadedMessages);
					
					// Extract and restore thinking steps from persisted messages
					const restoredThinkingSteps = new Map<string, ThinkingStep[]>();
					for (const msg of response.messages) {
						if (msg.role === "assistant") {
							const steps = extractThinkingSteps(msg.content);
							if (steps.length > 0) {
								restoredThinkingSteps.set(`msg-${msg.id}`, steps);
							}
						}
					}
					if (restoredThinkingSteps.size > 0) {
						setMessageThinkingSteps(restoredThinkingSteps);
					}
				}
			} else {
				// Create new thread
				const newThread = await createThread(searchSpaceId, "New Chat");
				setThreadId(newThread.id);
				router.replace(`/dashboard/${searchSpaceId}/new-chat/${newThread.id}`);
			}
		} catch (error) {
			console.error("[NewChatPage] Failed to initialize thread:", error);
			// Keep threadId as null - don't use Date.now() as it creates an invalid ID
			// that will cause 404 errors on subsequent API calls
			setThreadId(null);
			toast.error("Failed to initialize chat. Please try again.");
		} finally {
			setIsInitializing(false);
		}
	}, [urlChatId, searchSpaceId, router]);

	// Initialize on mount
	useEffect(() => {
		initializeThread();
	}, [initializeThread]);

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
			if (!threadId) return;

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

			// Add user message to state
			const userMsgId = `msg-user-${Date.now()}`;
			const userMessage: ThreadMessageLike = {
				id: userMsgId,
				role: "user",
				content: message.content,
				createdAt: new Date(),
			};
			setMessages((prev) => [...prev, userMessage]);

			// Persist user message (don't await, fire and forget)
			appendMessage(threadId, {
				role: "user",
				content: message.content,
			}).catch((err) => console.error("Failed to persist user message:", err));

			// Start streaming response
			setIsRunning(true);
			const controller = new AbortController();
			abortControllerRef.current = controller;

			// Prepare assistant message
			const assistantMsgId = `msg-assistant-${Date.now()}`;
			let accumulatedText = "";
			const currentThinkingSteps = new Map<string, ThinkingStepData>();
			const toolCalls = new Map<
				string,
				{
					toolCallId: string;
					toolName: string;
					args: Record<string, unknown>;
					result?: unknown;
				}
			>();

			// Helper to build content for UI (without thinking-steps)
			const buildContentForUI = (): ThreadMessageLike["content"] => {
				const parts: Array<
					| { type: "text"; text: string }
					| {
							type: "tool-call";
							toolCallId: string;
							toolName: string;
							args: Record<string, unknown>;
							result?: unknown;
					  }
				> = [];
				
				if (accumulatedText) {
					parts.push({ type: "text", text: accumulatedText });
				}
				for (const toolCall of toolCalls.values()) {
					if (TOOLS_WITH_UI.has(toolCall.toolName)) {
						parts.push({
							type: "tool-call",
							toolCallId: toolCall.toolCallId,
							toolName: toolCall.toolName,
							args: toolCall.args,
							result: toolCall.result,
						});
					}
				}
				return parts.length > 0
					? (parts as ThreadMessageLike["content"])
					: [{ type: "text", text: "" }];
			};

			// Helper to build content for persistence (includes thinking-steps)
			const buildContentForPersistence = (): unknown[] => {
				const parts: unknown[] = [];
				
				// Include thinking steps for persistence
				if (currentThinkingSteps.size > 0) {
					parts.push({
						type: "thinking-steps",
						steps: Array.from(currentThinkingSteps.values()),
					});
				}
				
				if (accumulatedText) {
					parts.push({ type: "text", text: accumulatedText });
				}
				for (const toolCall of toolCalls.values()) {
					if (TOOLS_WITH_UI.has(toolCall.toolName)) {
						parts.push({
							type: "tool-call",
							toolCallId: toolCall.toolCallId,
							toolName: toolCall.toolName,
							args: toolCall.args,
							result: toolCall.result,
						});
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

				const response = await fetch(`${backendUrl}/api/v1/new_chat`, {
					method: "POST",
					headers: {
						"Content-Type": "application/json",
						Authorization: `Bearer ${token}`,
					},
					body: JSON.stringify({
						chat_id: threadId,
						user_query: userQuery.trim(),
						search_space_id: searchSpaceId,
						messages: messageHistory,
						attachments: attachments.length > 0 ? attachments : undefined,
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
											accumulatedText += parsed.delta;
											setMessages((prev) =>
												prev.map((m) =>
													m.id === assistantMsgId ? { ...m, content: buildContentForUI() } : m
												)
											);
											break;

										case "tool-input-start":
											toolCalls.set(parsed.toolCallId, {
												toolCallId: parsed.toolCallId,
												toolName: parsed.toolName,
												args: {},
											});
											setMessages((prev) =>
												prev.map((m) =>
													m.id === assistantMsgId ? { ...m, content: buildContentForUI() } : m
												)
											);
											break;

										case "tool-input-available": {
											const tc = toolCalls.get(parsed.toolCallId);
											if (tc) tc.args = parsed.input || {};
											else
												toolCalls.set(parsed.toolCallId, {
													toolCallId: parsed.toolCallId,
													toolName: parsed.toolName,
													args: parsed.input || {},
												});
											setMessages((prev) =>
												prev.map((m) =>
													m.id === assistantMsgId ? { ...m, content: buildContentForUI() } : m
												)
											);
											break;
										}

										case "tool-output-available": {
											const tc = toolCalls.get(parsed.toolCallId);
											if (tc) {
												tc.result = parsed.output;
												if (
													tc.toolName === "generate_podcast" &&
													parsed.output?.status === "processing" &&
													parsed.output?.task_id
												) {
													setActivePodcastTaskId(parsed.output.task_id);
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
												// Update message-specific thinking steps
												setMessageThinkingSteps((prev) => {
													const newMap = new Map(prev);
													newMap.set(
														assistantMsgId,
														Array.from(currentThinkingSteps.values())
													);
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
				if (accumulatedText || toolCalls.size > 0) {
					appendMessage(threadId, {
						role: "assistant",
						content: finalContent,
					}).catch((err) => console.error("Failed to persist assistant message:", err));
				}
			} catch (error) {
				if (error instanceof Error && error.name === "AbortError") {
					// Request was cancelled
					return;
				}
				console.error("[NewChatPage] Chat error:", error);
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
		[threadId, searchSpaceId, messages]
	);

	// Convert message (pass through since already in correct format)
	const convertMessage = useCallback(
		(message: ThreadMessageLike): ThreadMessageLike => message,
		[]
	);

	// Handle editing a message - removes messages after the edited one and sends as new
	const onEdit = useCallback(
		async (message: AppendMessage) => {
			// Find the message being edited by looking at the parentId
			// The parentId tells us which message's response we're editing
			// For now, we'll just treat edits like new messages
			// A more sophisticated implementation would truncate the history
			await onNew(message);
		},
		[onNew]
	);

	// Create external store runtime with attachment support
	const runtime = useExternalStoreRuntime({
		messages,
		isRunning,
		onNew,
		onEdit,
		convertMessage,
		onCancel: cancelRun,
		adapters: {
			attachments: attachmentAdapter,
		},
	});

	// Show loading state
	if (isInitializing) {
		return (
			<div className="flex h-[calc(100vh-64px)] items-center justify-center">
				<div className="text-muted-foreground">Loading chat...</div>
			</div>
		);
	}

	// Show error state if thread initialization failed
	if (!threadId) {
		return (
			<div className="flex h-[calc(100vh-64px)] flex-col items-center justify-center gap-4">
				<div className="text-destructive">Failed to initialize chat</div>
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
			<div className="h-[calc(100vh-64px)] max-h-[calc(100vh-64px)] overflow-hidden">
				<Thread messageThinkingSteps={messageThinkingSteps} />
			</div>
		</AssistantRuntimeProvider>
	);
}
