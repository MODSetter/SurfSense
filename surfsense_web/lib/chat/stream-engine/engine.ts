import type { AppendMessage, ThreadMessageLike } from "@assistant-ui/react";
import { getDefaultStore } from "jotai";
import type { Dispatch, SetStateAction } from "react";
import { toast } from "sonner";
import { agentFlagsAtom } from "@/atoms/agent/agent-flags-query.atom";
import { disabledToolsAtom } from "@/atoms/agent-tools/agent-tools.atoms";
import {
	deriveMentionedPayload,
	type MentionedDocumentInfo,
	mentionedDocumentsAtom,
	messageDocumentsMapAtom,
	submittedMentionsAtom,
} from "@/atoms/chat/mentioned-documents.atom";
import { pendingUserImageDataUrlsAtom } from "@/atoms/chat/pending-user-images.atom";
import { setPremiumAlertForThreadAtom } from "@/atoms/chat/premium-alert.atom";
import { type AgentCreatedDocument, agentCreatedDocumentsAtom } from "@/atoms/documents/ui.atoms";
import { updateChatTabTitleAtom } from "@/atoms/tabs/tabs.atom";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import type { HitlDecision, PendingInterruptState } from "@/features/chat-messages/hitl";
import {
	applyActionLogSse,
	applyActionLogUpdatedSse,
	markActionRevertedInCache,
} from "@/hooks/use-agent-actions-query";
import { getAgentFilesystemSelection } from "@/lib/agent-filesystem";
import { authenticatedFetch } from "@/lib/auth-fetch";
import { type ChatFlow, classifyChatError } from "@/lib/chat/chat-error-classifier";
import { tagPreAcceptSendFailure, toHttpResponseError } from "@/lib/chat/chat-request-errors";
import { getMentionDocKey } from "@/lib/chat/mention-doc-key";
import { createStreamFlushHelpers } from "@/lib/chat/stream-flush";
import { consumeSseEvents, processSharedStreamEvent } from "@/lib/chat/stream-pipeline";
import {
	applyTurnIdToAssistantMessageList,
	mergeChatTurnIdIntoMessage,
	readStreamedChatTurnId,
	readStreamedMessageId,
} from "@/lib/chat/stream-side-effects";
import {
	addToolCall,
	buildContentForUI,
	type ContentPartsState,
	type FrameBatchedUpdater,
	type ThinkingStepData,
	updateToolCall,
} from "@/lib/chat/streaming-state";
import {
	appendMessage,
	createThread,
	getRegenerateUrl,
	type ThreadListItem,
	type ThreadListResponse,
	type ThreadRecord,
} from "@/lib/chat/thread-persistence";
import {
	extractUserTurnForNewChatApi,
	type NewChatUserImagePayload,
} from "@/lib/chat/user-turn-api-parts";
import { buildBackendUrl } from "@/lib/env-config";
import {
	trackChatBlocked,
	trackChatCreated,
	trackChatErrorDetailed,
	trackChatMessageSent,
	trackChatResponseReceived,
} from "@/lib/posthog/events";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { queryClient } from "@/lib/query-client/client";
import {
	computeFallbackTurnCancellingRetryDelay,
	freshSynthToolCallId,
	pairBundleToolCallIds,
	RECENT_CANCEL_WINDOW_MS,
	sleep,
	TOOLS_WITH_UI_ALL,
} from "./helpers";
import { chatStreamStore } from "./store";

const jotaiStore = getDefaultStore();
const tokenUsageStore = chatStreamStore.tokenUsage;
const toolsWithUI = TOOLS_WITH_UI_ALL;

/**
 * Display-only setters, valid only while the page is mounted. The stream drives
 * durable state through {@link chatStreamStore}; these just sync the mounted
 * page's local view and are ignored once it unmounts.
 */
export interface EngineView {
	setThreadId: Dispatch<SetStateAction<number | null>>;
	setCurrentThread: Dispatch<SetStateAction<ThreadRecord | null>>;
}

/** Route/view context the page passes into every engine call. */
export interface EngineContext {
	workspaceId: number;
	/** Currently viewed thread id (``activeThreadId`` in the page). */
	threadId: number | null;
	/** The page's current displayed messages — history/slice seed. */
	priorMessages: ThreadMessageLike[];
	view: EngineView;
}

// ---------------------------------------------------------------------------
// Error handling
// ---------------------------------------------------------------------------

async function persistAssistantErrorMessage({
	threadId,
	assistantMsgId,
	text,
}: {
	threadId: number | null;
	assistantMsgId: string;
	text: string;
}): Promise<void> {
	if (threadId != null) {
		chatStreamStore.setMessages(threadId, (prev) =>
			prev.map((m) => (m.id === assistantMsgId ? { ...m, content: [{ type: "text", text }] } : m))
		);
	}

	if (!threadId) return;

	// Persist only temporary assistant placeholders to avoid duplicate rows
	// when the message already has a database-backed ID.
	if (!assistantMsgId.startsWith("msg-assistant-")) return;

	try {
		const savedMessage = await appendMessage(threadId, {
			role: "assistant",
			content: [{ type: "text", text }],
		});
		const newMsgId = `msg-${savedMessage.id}`;
		tokenUsageStore.rename(assistantMsgId, newMsgId);
		chatStreamStore.setMessages(threadId, (prev) =>
			prev.map((m) => (m.id === assistantMsgId ? { ...m, id: newMsgId } : m))
		);
	} catch (persistErr) {
		console.error("Failed to persist assistant error message:", persistErr);
	}
}

async function handleChatFailure({
	error,
	flow,
	threadId,
	assistantMsgId,
	workspaceId,
}: {
	error: unknown;
	flow: ChatFlow;
	threadId: number | null;
	assistantMsgId: string;
	workspaceId: number;
}): Promise<void> {
	const normalized = classifyChatError({
		error,
		flow,
		context: { workspaceId, threadId },
	});

	const logger =
		normalized.severity === "error"
			? console.error
			: normalized.severity === "warn"
				? console.warn
				: console.info;
	logger(`[chat-engine] ${flow} ${normalized.kind}:`, error);

	const telemetryPayload = {
		flow,
		kind: normalized.kind,
		error_code: normalized.errorCode,
		severity: normalized.severity,
		is_expected: normalized.isExpected,
		message: normalized.userMessage,
	};
	if (normalized.telemetryEvent === "chat_blocked") {
		trackChatBlocked(workspaceId, threadId, telemetryPayload);
	} else {
		trackChatErrorDetailed(workspaceId, threadId, telemetryPayload);
	}

	if (normalized.channel === "silent") {
		return;
	}

	if (normalized.channel === "pinned_inline") {
		if (threadId) {
			const currentUser = jotaiStore.get(currentUserAtom).data;
			jotaiStore.set(setPremiumAlertForThreadAtom, {
				threadId,
				message: normalized.userMessage,
				userId: currentUser?.id ?? null,
			});
		}
		if (normalized.assistantMessage) {
			await persistAssistantErrorMessage({
				threadId,
				assistantMsgId,
				text: normalized.assistantMessage,
			});
		}
		return;
	}

	if (normalized.channel === "inline") {
		if (normalized.assistantMessage) {
			await persistAssistantErrorMessage({
				threadId,
				assistantMsgId,
				text: normalized.assistantMessage,
			});
		}
		toast.error(normalized.userMessage);
		return;
	}

	toast.error(normalized.userMessage);
}

async function handleStreamTerminalError({
	error,
	flow,
	threadId,
	assistantMsgId,
	accepted,
	workspaceId,
	onAbort,
	onPreAcceptFailure,
	onAcceptedStreamError,
}: {
	error: unknown;
	flow: ChatFlow;
	threadId: number | null;
	assistantMsgId: string;
	accepted: boolean;
	workspaceId: number;
	onAbort?: () => Promise<void>;
	onPreAcceptFailure?: () => Promise<void>;
	onAcceptedStreamError?: () => Promise<void>;
}): Promise<void> {
	if (error instanceof Error && error.name === "AbortError") {
		await onAbort?.();
		return;
	}

	if (!accepted) {
		await onPreAcceptFailure?.();
	} else {
		await onAcceptedStreamError?.();
	}

	await handleChatFailure({
		error: !accepted ? tagPreAcceptSendFailure(error) : error,
		flow,
		threadId,
		assistantMsgId: accepted ? assistantMsgId : "no-persist-assistant",
		workspaceId,
	});
}

async function fetchWithTurnCancellingRetry(runFetch: () => Promise<Response>): Promise<Response> {
	const maxAttempts = 4;
	for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
		const response = await runFetch();
		if (response.ok) {
			return response;
		}
		const error = await toHttpResponseError(response);
		const withMeta = error as Error & { errorCode?: string; retryAfterMs?: number };
		const isTurnCancelling = withMeta.errorCode === "TURN_CANCELLING";
		const isRecentThreadBusyAfterCancel =
			withMeta.errorCode === "THREAD_BUSY" &&
			Date.now() - chatStreamStore.recentCancelRequestedAt <= RECENT_CANCEL_WINDOW_MS;
		if ((isTurnCancelling || isRecentThreadBusyAfterCancel) && attempt < maxAttempts) {
			const waitMs = withMeta.retryAfterMs ?? computeFallbackTurnCancellingRetryDelay(attempt);
			await sleep(waitMs);
			continue;
		}
		throw error;
	}

	throw Object.assign(new Error("Turn cancellation retry limit exceeded"), {
		errorCode: "TURN_CANCELLING",
	});
}

// ---------------------------------------------------------------------------
// Cancel
// ---------------------------------------------------------------------------

/**
 * Cancel the single in-flight turn. Targets the active stream's OWNER thread
 * (not the currently-viewed thread) so cancel works even after navigation and
 * for the lazy-create case.
 */
export async function cancelActiveTurn(): Promise<void> {
	const threadId = chatStreamStore.activeThreadId;
	if (threadId) {
		try {
			const response = await authenticatedFetch(
				buildBackendUrl(`/api/v1/threads/${threadId}/cancel-active-turn`),
				{ method: "POST" }
			);
			if (response.ok) {
				const payload = (await response.json()) as { error_code?: string };
				if (payload.error_code === "TURN_CANCELLING") {
					chatStreamStore.markRecentCancel();
				}
			}
		} catch (error) {
			console.warn("[chat-engine] Failed to signal cancel-active-turn:", error);
		}
		chatStreamStore.setRunning(threadId, false);
	}
	chatStreamStore.abortActive();
}

// ---------------------------------------------------------------------------
// New chat turn
// ---------------------------------------------------------------------------

export async function startNewChat(ctx: EngineContext, message: AppendMessage): Promise<void> {
	const { workspaceId, threadId, priorMessages, view } = ctx;

	// Supersede any previous in-flight turn.
	chatStreamStore.abortActive();

	// Prefer the submit-time snapshot; fall back to the live atom for the
	// send-button path.
	const submittedSnapshot = jotaiStore.get(submittedMentionsAtom);
	jotaiStore.set(submittedMentionsAtom, null);
	const mentionedDocuments = jotaiStore.get(mentionedDocumentsAtom);
	const activeMentions = submittedSnapshot ?? mentionedDocuments;
	const mentionPayload = deriveMentionedPayload(activeMentions);
	if (activeMentions.length > 0) {
		jotaiStore.set(mentionedDocumentsAtom, []);
	}

	const pendingUserImageUrls = jotaiStore.get(pendingUserImageDataUrlsAtom);
	const urlsSnapshot = [...pendingUserImageUrls];
	const { userQuery, userImages } = extractUserTurnForNewChatApi(message, urlsSnapshot);

	if (!userQuery.trim() && userImages.length === 0) return;

	const localFilesystemEnabled =
		jotaiStore.get(agentFlagsAtom).data?.enable_desktop_local_filesystem === true;
	const disabledTools = jotaiStore.get(disabledToolsAtom);
	const currentUser = jotaiStore.get(currentUserAtom).data;

	// Resolve filesystem selection BEFORE any optimistic UI / lazy thread
	// creation so an unsatisfied "Local Folder" requirement bails cleanly
	// with nothing to roll back and no thread left stuck "running".
	let selection: Awaited<ReturnType<typeof getAgentFilesystemSelection>>;
	try {
		selection = await getAgentFilesystemSelection(workspaceId, { localFilesystemEnabled });
	} catch (error) {
		await handleChatFailure({
			error: tagPreAcceptSendFailure(error),
			flow: "new",
			threadId,
			assistantMsgId: "no-persist-assistant",
			workspaceId,
		});
		return;
	}
	if (
		selection.filesystem_mode === "desktop_local_folder" &&
		(!selection.local_filesystem_mounts || selection.local_filesystem_mounts.length === 0)
	) {
		toast.error("Select a local folder before using Local Folder mode.");
		return;
	}

	// Lazy thread creation: create thread on first message if it doesn't exist.
	let currentThreadId = threadId;
	let isNewThread = false;
	if (!currentThreadId) {
		try {
			const newThread = await createThread(workspaceId, "New Chat");
			currentThreadId = newThread.id;
			view.setThreadId(currentThreadId);
			view.setCurrentThread(newThread);
			queryClient.setQueryData(cacheKeys.threads.detail(newThread.id), newThread);
			queryClient.setQueryData(cacheKeys.threads.messages(newThread.id), { messages: [] });

			trackChatCreated(workspaceId, currentThreadId);

			isNewThread = true;
			// Update URL silently using browser API (not router.replace) to avoid
			// interrupting the ongoing fetch/streaming with React navigation.
			window.history.replaceState(
				null,
				"",
				`/dashboard/${workspaceId}/new-chat/${currentThreadId}`
			);
		} catch (error) {
			console.error("[chat-engine] Failed to create thread:", error);
			await handleChatFailure({
				error: tagPreAcceptSendFailure(error),
				flow: "new",
				threadId: currentThreadId,
				assistantMsgId: "no-persist-assistant",
				workspaceId,
			});
			return;
		}
	}

	// Seed the durable per-thread overlay with the pre-turn conversation and
	// flip it to running so the page renders the live stream.
	const streamThreadId = currentThreadId;
	chatStreamStore.begin(streamThreadId, priorMessages);

	if (urlsSnapshot.length > 0) {
		jotaiStore.set(pendingUserImageDataUrlsAtom, (prev) =>
			prev.filter((u) => !urlsSnapshot.includes(u))
		);
	}

	// Add user message to state. Mutable because the SSE
	// ``data-user-message-id`` handler renames this optimistic id to the
	// canonical ``msg-{db_id}`` once ``persist_user_turn`` resolves.
	let userMsgId = `msg-user-${Date.now()}`;

	const authorMetadata = currentUser
		? {
				custom: {
					author: {
						displayName: currentUser.display_name ?? null,
						avatarUrl: currentUser.avatar_url ?? null,
					},
				},
			}
		: undefined;

	const existingImageUrls = new Set(
		message.content
			.filter(
				(p): p is { type: "image"; image: string } =>
					typeof p === "object" && p !== null && "type" in p && p.type === "image" && "image" in p
			)
			.map((p) => p.image)
	);
	const extraImageParts = urlsSnapshot
		.filter((u) => !existingImageUrls.has(u))
		.map((image) => ({ type: "image" as const, image }));
	const userDisplayContent = [...message.content, ...extraImageParts];

	const userMessage: ThreadMessageLike = {
		id: userMsgId,
		role: "user",
		content: userDisplayContent,
		createdAt: new Date(),
		metadata: authorMetadata,
	};
	chatStreamStore.setMessages(streamThreadId, (prev) => [...prev, userMessage]);

	trackChatMessageSent(workspaceId, streamThreadId, {
		hasAttachments: userImages.length > 0,
		hasMentionedDocuments:
			mentionPayload.document_ids.length > 0 ||
			mentionPayload.folder_ids.length > 0 ||
			mentionPayload.connector_ids.length > 0,
		messageLength: userQuery.length,
	});

	// Collect unique mention chips for display & persistence.
	const allMentionedDocs: MentionedDocumentInfo[] = [];
	const seenDocKeys = new Set<string>();
	for (const doc of activeMentions) {
		const key = getMentionDocKey(doc);
		if (seenDocKeys.has(key)) continue;
		seenDocKeys.add(key);
		allMentionedDocs.push(doc);
	}

	if (allMentionedDocs.length > 0) {
		jotaiStore.set(messageDocumentsMapAtom, (prev) => ({
			...prev,
			[userMsgId]: allMentionedDocs,
		}));
	}

	const controller = new AbortController();
	chatStreamStore.beginActive(streamThreadId, controller);

	// Prepare assistant message. Mutable for the same reason as ``userMsgId``.
	let assistantMsgId = `msg-assistant-${Date.now()}`;
	const currentThinkingSteps = new Map<string, ThinkingStepData>();
	const contentPartsState: ContentPartsState = {
		contentParts: [],
		currentTextPartIndex: -1,
		currentReasoningPartIndex: -1,
		toolCallIndices: new Map(),
	};
	const { contentParts } = contentPartsState;
	let wasInterrupted = false;
	let newAccepted = false;
	let streamBatcher: FrameBatchedUpdater | null = null;

	try {
		// Build message history for context.
		const messageHistory = priorMessages
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

		const hasDocumentIds = mentionPayload.document_ids.length > 0;
		const hasFolderIds = mentionPayload.folder_ids.length > 0;
		const hasConnectorIds = mentionPayload.connector_ids.length > 0;
		const hasThreadIds = mentionPayload.thread_ids.length > 0;

		const response = await fetchWithTurnCancellingRetry(() =>
			authenticatedFetch(buildBackendUrl("/api/v1/new_chat"), {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					chat_id: streamThreadId,
					user_query: userQuery.trim(),
					workspace_id: workspaceId,
					filesystem_mode: selection.filesystem_mode,
					client_platform: selection.client_platform,
					local_filesystem_mounts: selection.local_filesystem_mounts,
					messages: messageHistory,
					mentioned_document_ids: hasDocumentIds ? mentionPayload.document_ids : undefined,
					mentioned_folder_ids: hasFolderIds ? mentionPayload.folder_ids : undefined,
					mentioned_connector_ids: hasConnectorIds ? mentionPayload.connector_ids : undefined,
					mentioned_connectors: hasConnectorIds ? mentionPayload.connectors : undefined,
					mentioned_thread_ids: hasThreadIds ? mentionPayload.thread_ids : undefined,
					mentioned_documents: allMentionedDocs.length > 0 ? allMentionedDocs : undefined,
					disabled_tools: disabledTools.length > 0 ? disabledTools : undefined,
					...(userImages.length > 0 ? { user_images: userImages } : {}),
				}),
				signal: controller.signal,
			})
		);

		if (!response.ok) {
			throw await toHttpResponseError(response);
		}
		newAccepted = true;
		chatStreamStore.setMessages(streamThreadId, (prev) => [
			...prev,
			{
				id: assistantMsgId,
				role: "assistant",
				content: [{ type: "text", text: "" }],
				createdAt: new Date(),
			},
		]);

		const flushMessages = () => {
			chatStreamStore.setMessages(streamThreadId, (prev) =>
				prev.map((m) =>
					m.id === assistantMsgId
						? { ...m, content: buildContentForUI(contentPartsState, toolsWithUI) }
						: m
				)
			);
		};
		const { batcher, scheduleFlush, forceFlush } = createStreamFlushHelpers(flushMessages);
		streamBatcher = batcher;

		await consumeSseEvents(response, async (parsed) => {
			if (
				processSharedStreamEvent(parsed, {
					contentPartsState,
					toolsWithUI,
					currentThinkingSteps,
					scheduleFlush,
					forceFlush,
					onTokenUsage: (data) => {
						tokenUsageStore.set(assistantMsgId, data);
					},
					onTurnStatus: (data) => {
						if (data.status === "cancelling") {
							chatStreamStore.markRecentCancel();
						}
					},
				})
			) {
				return;
			}
			switch (parsed.type) {
				case "data-thread-title-update": {
					const titleData = parsed.data as { threadId: number; title: string };
					if (titleData?.title && titleData?.threadId === streamThreadId) {
						view.setCurrentThread((prev) => (prev ? { ...prev, title: titleData.title } : prev));
						jotaiStore.set(updateChatTabTitleAtom, {
							chatId: streamThreadId,
							title: titleData.title,
						});
						queryClient.setQueriesData<ThreadListResponse>(
							{ queryKey: ["threads", String(workspaceId)] },
							(old) => {
								if (!old) return old;
								const updateTitle = (list: ThreadListItem[]) =>
									list.map((t) =>
										t.id === titleData.threadId ? { ...t, title: titleData.title } : t
									);
								return {
									...old,
									threads: updateTitle(old.threads),
									archived_threads: updateTitle(old.archived_threads),
								};
							}
						);
					}
					break;
				}

				case "data-documents-updated": {
					const docEvent = parsed.data as {
						action: string;
						document: AgentCreatedDocument;
					};
					if (docEvent?.document?.id) {
						jotaiStore.set(agentCreatedDocumentsAtom, (prev) => {
							if (prev.some((d) => d.id === docEvent.document.id)) return prev;
							return [...prev, docEvent.document];
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
					const paired = pairBundleToolCallIds(
						contentPartsState.toolCallIndices,
						contentPartsState.contentParts,
						actionRequests
					);
					const bundleToolCallIds: string[] = [];
					for (let i = 0; i < actionRequests.length; i++) {
						const action = actionRequests[i];
						let targetTcId = paired[i];
						if (!targetTcId) {
							targetTcId = freshSynthToolCallId(contentPartsState.toolCallIndices, action.name, i);
							addToolCall(
								contentPartsState,
								toolsWithUI,
								targetTcId,
								action.name,
								action.args,
								true
							);
						}
						updateToolCall(contentPartsState, targetTcId, {
							result: { __interrupt__: true, ...interruptData },
						});
						bundleToolCallIds.push(targetTcId);
					}
					chatStreamStore.setMessages(streamThreadId, (prev) =>
						prev.map((m) =>
							m.id === assistantMsgId
								? { ...m, content: buildContentForUI(contentPartsState, toolsWithUI) }
								: m
						)
					);
					// ``tool_call_id`` is stamped on the backend by
					// ``checkpointed_subagent_middleware``. Without it we can't
					// address the paused subagent on resume — skip rather than
					// fabricate a synthetic key.
					const interruptId = String(interruptData.tool_call_id ?? "");
					if (interruptId) {
						const incoming: PendingInterruptState = {
							interruptId,
							threadId: streamThreadId,
							assistantMsgId,
							interruptData,
							bundleToolCallIds,
						};
						chatStreamStore.setPendingInterrupts(streamThreadId, (prev) => {
							const without = prev.filter((p) => p.interruptId !== interruptId);
							return [...without, incoming];
						});
					}
					break;
				}

				case "data-action-log": {
					applyActionLogSse(queryClient, streamThreadId, workspaceId, parsed.data);
					break;
				}

				case "data-action-log-updated": {
					applyActionLogUpdatedSse(
						queryClient,
						streamThreadId,
						parsed.data.id,
						parsed.data.reversible
					);
					break;
				}

				case "data-turn-info": {
					const turnId = readStreamedChatTurnId(parsed.data);
					if (turnId) {
						chatStreamStore.setMessages(streamThreadId, (prev) =>
							applyTurnIdToAssistantMessageList(prev, assistantMsgId, turnId)
						);
					}
					break;
				}

				case "data-user-message-id": {
					const parsedMsg = readStreamedMessageId(parsed.data);
					if (!parsedMsg) break;
					const newUserMsgId = `msg-${parsedMsg.messageId}`;
					const oldUserMsgId = userMsgId;
					chatStreamStore.setMessages(streamThreadId, (prev) =>
						prev.map((m) =>
							m.id === oldUserMsgId
								? mergeChatTurnIdIntoMessage({ ...m, id: newUserMsgId }, parsedMsg.turnId)
								: m
						)
					);
					if (allMentionedDocs.length > 0) {
						jotaiStore.set(messageDocumentsMapAtom, (prev) => {
							if (!(oldUserMsgId in prev)) {
								return { ...prev, [newUserMsgId]: allMentionedDocs };
							}
							const { [oldUserMsgId]: _removed, ...rest } = prev;
							return { ...rest, [newUserMsgId]: allMentionedDocs };
						});
					}
					userMsgId = newUserMsgId;
					if (isNewThread) {
						queryClient.invalidateQueries({
							queryKey: ["threads", String(workspaceId)],
						});
					}
					break;
				}

				case "data-assistant-message-id": {
					const parsedMsg = readStreamedMessageId(parsed.data);
					if (!parsedMsg) break;
					const newAssistantMsgId = `msg-${parsedMsg.messageId}`;
					const oldAssistantMsgId = assistantMsgId;
					tokenUsageStore.rename(oldAssistantMsgId, newAssistantMsgId);
					chatStreamStore.setMessages(streamThreadId, (prev) =>
						prev.map((m) =>
							m.id === oldAssistantMsgId
								? mergeChatTurnIdIntoMessage({ ...m, id: newAssistantMsgId }, parsedMsg.turnId)
								: m
						)
					);
					chatStreamStore.setPendingInterrupts(streamThreadId, (prev) =>
						prev.map((p) =>
							p.assistantMsgId === oldAssistantMsgId
								? { ...p, assistantMsgId: newAssistantMsgId }
								: p
						)
					);
					assistantMsgId = newAssistantMsgId;
					break;
				}
			}
		});

		batcher.flush();

		if (contentParts.length > 0 && !wasInterrupted) {
			trackChatResponseReceived(workspaceId, streamThreadId);
		}
	} catch (error) {
		streamBatcher?.dispose();
		await handleStreamTerminalError({
			error,
			flow: "new",
			threadId: streamThreadId,
			assistantMsgId,
			accepted: newAccepted,
			workspaceId,
			onPreAcceptFailure: async () => {
				// Pre-accept failure means the BE never accepted the request — no
				// server-side persistence ran. Roll back the optimistic UI.
				chatStreamStore.setMessages(streamThreadId, (prev) =>
					prev.filter((m) => m.id !== userMsgId)
				);
				jotaiStore.set(messageDocumentsMapAtom, (prev) => {
					if (!(userMsgId in prev)) return prev;
					const { [userMsgId]: _removed, ...rest } = prev;
					return rest;
				});
			},
		});
	} finally {
		chatStreamStore.setRunning(streamThreadId, false);
		chatStreamStore.clearActive(controller);
		void queryClient.invalidateQueries({
			queryKey: cacheKeys.threads.messages(streamThreadId),
		});
		void queryClient.invalidateQueries({
			queryKey: cacheKeys.threads.detail(streamThreadId),
		});
	}
}

// ---------------------------------------------------------------------------
// Resume (HITL decisions)
// ---------------------------------------------------------------------------

export async function resumeChat(
	ctx: EngineContext,
	decisions: Array<{
		type: string;
		message?: string;
		edited_action?: { name: string; args: Record<string, unknown> };
	}>
): Promise<void> {
	const { workspaceId, threadId } = ctx;
	if (threadId == null) return;
	const pendingInterrupts = chatStreamStore.getPendingInterrupts(threadId);
	if (pendingInterrupts.length === 0) return;

	const resumeThreadId = pendingInterrupts[0].threadId;
	let assistantMsgId = pendingInterrupts[0].assistantMsgId;
	const allBundleToolCallIds = pendingInterrupts.flatMap((p) => p.bundleToolCallIds);
	chatStreamStore.setPendingInterrupts(resumeThreadId, () => []);
	chatStreamStore.setRunning(resumeThreadId, true);

	const controller = new AbortController();
	chatStreamStore.beginActive(resumeThreadId, controller);

	const localFilesystemEnabled =
		jotaiStore.get(agentFlagsAtom).data?.enable_desktop_local_filesystem === true;
	const disabledTools = jotaiStore.get(disabledToolsAtom);

	const currentThinkingSteps = new Map<string, ThinkingStepData>();
	const contentPartsState: ContentPartsState = {
		contentParts: [],
		currentTextPartIndex: -1,
		currentReasoningPartIndex: -1,
		toolCallIndices: new Map(),
	};
	const { contentParts, toolCallIndices } = contentPartsState;
	let resumeAccepted = false;
	let streamBatcher: FrameBatchedUpdater | null = null;

	const existingMsg = chatStreamStore
		.getMessages(resumeThreadId)
		.find((m) => m.id === assistantMsgId);
	if (existingMsg && Array.isArray(existingMsg.content)) {
		contentPartsState.suppressStepSeparators = true;
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
						...(typeof p.argsText === "string" ? { argsText: p.argsText } : {}),
						...(typeof p.langchainToolCallId === "string"
							? { langchainToolCallId: p.langchainToolCallId }
							: {}),
						...(p.metadata && typeof p.metadata === "object"
							? { metadata: p.metadata as Record<string, unknown> }
							: {}),
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

	// Apply each decision to its own card by toolCallId so mixed bundles
	// (approve/edit/reject) do not collapse onto ``decisions[0]``.
	const decisionByTcId = new Map<string, (typeof decisions)[number]>();
	const tcIds = allBundleToolCallIds;
	if (decisions.length === tcIds.length) {
		for (let i = 0; i < tcIds.length; i++) decisionByTcId.set(tcIds[i], decisions[i]);
	}
	if (decisionByTcId.size > 0) {
		for (const part of contentParts) {
			if (part.type !== "tool-call") continue;
			const tcId = part.toolCallId as string | undefined;
			const d = tcId ? decisionByTcId.get(tcId) : undefined;
			if (!d) continue;
			if (typeof part.result !== "object" || part.result === null) continue;
			if (!("__interrupt__" in (part.result as Record<string, unknown>))) continue;
			const decided = d.type;
			if (decided === "edit" && d.edited_action) {
				const mergedArgs = { ...part.args, ...d.edited_action.args };
				part.args = mergedArgs;
				part.argsText = JSON.stringify(mergedArgs, null, 2);
			}
			part.result = {
				...(part.result as Record<string, unknown>),
				__decided__: decided,
			};
		}
	}

	try {
		const selection = await getAgentFilesystemSelection(workspaceId, { localFilesystemEnabled });
		const response = await fetchWithTurnCancellingRetry(() =>
			authenticatedFetch(buildBackendUrl(`/api/v1/threads/${resumeThreadId}/resume`), {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					workspace_id: workspaceId,
					decisions,
					disabled_tools: disabledTools.length > 0 ? disabledTools : undefined,
					filesystem_mode: selection.filesystem_mode,
					client_platform: selection.client_platform,
					local_filesystem_mounts: selection.local_filesystem_mounts,
				}),
				signal: controller.signal,
			})
		);

		if (!response.ok) {
			throw await toHttpResponseError(response);
		}
		resumeAccepted = true;

		const flushMessages = () => {
			chatStreamStore.setMessages(resumeThreadId, (prev) =>
				prev.map((m) =>
					m.id === assistantMsgId
						? { ...m, content: buildContentForUI(contentPartsState, toolsWithUI) }
						: m
				)
			);
		};
		const { batcher, scheduleFlush, forceFlush } = createStreamFlushHelpers(flushMessages);
		streamBatcher = batcher;

		await consumeSseEvents(response, async (parsed) => {
			if (
				processSharedStreamEvent(parsed, {
					contentPartsState,
					toolsWithUI,
					currentThinkingSteps,
					scheduleFlush,
					forceFlush,
					onTokenUsage: (data) => {
						tokenUsageStore.set(assistantMsgId, data);
					},
					onTurnStatus: (data) => {
						if (data.status === "cancelling") {
							chatStreamStore.markRecentCancel();
						}
					},
				})
			) {
				return;
			}
			switch (parsed.type) {
				case "data-interrupt-request": {
					const interruptData = parsed.data as Record<string, unknown>;
					const actionRequests = (interruptData.action_requests ?? []) as Array<{
						name: string;
						args: Record<string, unknown>;
					}>;
					const paired = pairBundleToolCallIds(
						contentPartsState.toolCallIndices,
						contentPartsState.contentParts,
						actionRequests
					);
					const bundleToolCallIds: string[] = [];
					for (let i = 0; i < actionRequests.length; i++) {
						const action = actionRequests[i];
						let targetTcId = paired[i];
						if (!targetTcId) {
							targetTcId = freshSynthToolCallId(contentPartsState.toolCallIndices, action.name, i);
							addToolCall(
								contentPartsState,
								toolsWithUI,
								targetTcId,
								action.name,
								action.args,
								true
							);
						}
						updateToolCall(contentPartsState, targetTcId, {
							result: { __interrupt__: true, ...interruptData },
						});
						bundleToolCallIds.push(targetTcId);
					}
					chatStreamStore.setMessages(resumeThreadId, (prev) =>
						prev.map((m) =>
							m.id === assistantMsgId
								? { ...m, content: buildContentForUI(contentPartsState, toolsWithUI) }
								: m
						)
					);
					{
						const interruptId = String(interruptData.tool_call_id ?? "");
						if (interruptId) {
							const incoming: PendingInterruptState = {
								interruptId,
								threadId: resumeThreadId,
								assistantMsgId,
								interruptData,
								bundleToolCallIds,
							};
							chatStreamStore.setPendingInterrupts(resumeThreadId, (prev) => {
								const without = prev.filter((p) => p.interruptId !== interruptId);
								return [...without, incoming];
							});
						}
					}
					break;
				}

				case "data-action-log": {
					applyActionLogSse(queryClient, resumeThreadId, workspaceId, parsed.data);
					break;
				}

				case "data-action-log-updated": {
					applyActionLogUpdatedSse(
						queryClient,
						resumeThreadId,
						parsed.data.id,
						parsed.data.reversible
					);
					break;
				}

				case "data-turn-info": {
					const turnId = readStreamedChatTurnId(parsed.data);
					if (turnId) {
						chatStreamStore.setMessages(resumeThreadId, (prev) =>
							applyTurnIdToAssistantMessageList(prev, assistantMsgId, turnId)
						);
					}
					break;
				}

				case "data-assistant-message-id": {
					const parsedMsg = readStreamedMessageId(parsed.data);
					if (!parsedMsg) break;
					const newAssistantMsgId = `msg-${parsedMsg.messageId}`;
					const oldAssistantMsgId = assistantMsgId;
					tokenUsageStore.rename(oldAssistantMsgId, newAssistantMsgId);
					chatStreamStore.setMessages(resumeThreadId, (prev) =>
						prev.map((m) =>
							m.id === oldAssistantMsgId
								? mergeChatTurnIdIntoMessage({ ...m, id: newAssistantMsgId }, parsedMsg.turnId)
								: m
						)
					);
					assistantMsgId = newAssistantMsgId;
					break;
				}
			}
		});

		batcher.flush();
	} catch (error) {
		streamBatcher?.dispose();
		await handleStreamTerminalError({
			error,
			flow: "resume",
			threadId: resumeThreadId,
			assistantMsgId,
			accepted: resumeAccepted,
			workspaceId,
		});
	} finally {
		chatStreamStore.setRunning(resumeThreadId, false);
		chatStreamStore.clearActive(controller);
		void queryClient.invalidateQueries({
			queryKey: cacheKeys.threads.messages(resumeThreadId),
		});
		void queryClient.invalidateQueries({
			queryKey: cacheKeys.threads.detail(resumeThreadId),
		});
	}
}

// ---------------------------------------------------------------------------
// Regenerate (edit / reload)
// ---------------------------------------------------------------------------

export async function regenerateChat(
	ctx: EngineContext,
	newUserQuery: string | null,
	editExtras?: {
		userMessageContent: ThreadMessageLike["content"];
		userImages: NewChatUserImagePayload[];
		sourceUserMessageId?: string;
	},
	editFromPosition?: {
		fromMessageId?: number | null;
		revertActions?: boolean;
	}
): Promise<void> {
	const { workspaceId, threadId, priorMessages } = ctx;
	if (!threadId) {
		toast.error("Cannot regenerate: no active chat thread");
		return;
	}
	const streamThreadId = threadId;

	const isEdit = newUserQuery !== null;

	// Supersede any previous in-flight turn.
	chatStreamStore.abortActive();

	const messageDocumentsMap = jotaiStore.get(messageDocumentsMapAtom);
	const localFilesystemEnabled =
		jotaiStore.get(agentFlagsAtom).data?.enable_desktop_local_filesystem === true;
	const disabledTools = jotaiStore.get(disabledToolsAtom);

	// Extract the original user query BEFORE removing messages (reload mode).
	let userQueryToDisplay: string | undefined;
	let originalUserMessageContent: ThreadMessageLike["content"] | null = null;
	let originalUserMessageMetadata: ThreadMessageLike["metadata"] | undefined;
	let sourceUserMessageId: string | undefined = editExtras?.sourceUserMessageId;

	if (!isEdit) {
		const lastUserMessage = [...priorMessages].reverse().find((m) => m.role === "user");
		if (lastUserMessage) {
			sourceUserMessageId = lastUserMessage.id;
			originalUserMessageContent = lastUserMessage.content;
			originalUserMessageMetadata = lastUserMessage.metadata;
			for (const part of lastUserMessage.content) {
				if (typeof part === "object" && part.type === "text" && "text" in part) {
					userQueryToDisplay = part.text;
					break;
				}
			}
		}
	} else {
		userQueryToDisplay = newUserQuery;
	}

	// Seed the durable overlay with the pre-regenerate conversation and flip
	// to running so the page renders the live stream.
	chatStreamStore.begin(streamThreadId, priorMessages);

	const controller = new AbortController();
	chatStreamStore.beginActive(streamThreadId, controller);

	let userMsgId = `msg-user-${Date.now()}`;
	let assistantMsgId = `msg-assistant-${Date.now()}`;
	const currentThinkingSteps = new Map<string, ThinkingStepData>();

	const contentPartsState: ContentPartsState = {
		contentParts: [],
		currentTextPartIndex: -1,
		currentReasoningPartIndex: -1,
		toolCallIndices: new Map(),
	};
	const { contentParts } = contentPartsState;
	let regenerateAccepted = false;
	let streamBatcher: FrameBatchedUpdater | null = null;

	const userMessage: ThreadMessageLike = {
		id: userMsgId,
		role: "user",
		content: isEdit
			? (editExtras?.userMessageContent ?? [{ type: "text", text: newUserQuery ?? "" }])
			: originalUserMessageContent || [{ type: "text", text: userQueryToDisplay || "" }],
		createdAt: new Date(),
		metadata: isEdit ? undefined : originalUserMessageMetadata,
	};
	const sourceMentionedDocs =
		sourceUserMessageId && messageDocumentsMap[sourceUserMessageId]
			? messageDocumentsMap[sourceUserMessageId]
			: [];
	try {
		const selection = await getAgentFilesystemSelection(workspaceId, { localFilesystemEnabled });
		const regenerateDocIds = sourceMentionedDocs.filter((d) => d.kind === "doc").map((d) => d.id);
		const regenerateFolderIds = sourceMentionedDocs
			.filter((d) => d.kind === "folder")
			.map((d) => d.id);
		const regenerateConnectors = sourceMentionedDocs.filter((d) => d.kind === "connector");
		const regenerateThreadIds = sourceMentionedDocs
			.filter((d) => d.kind === "thread")
			.map((d) => d.id);

		const requestBody: Record<string, unknown> = {
			workspace_id: workspaceId,
			user_query: newUserQuery,
			disabled_tools: disabledTools.length > 0 ? disabledTools : undefined,
			filesystem_mode: selection.filesystem_mode,
			client_platform: selection.client_platform,
			local_filesystem_mounts: selection.local_filesystem_mounts,
			mentioned_document_ids: regenerateDocIds.length > 0 ? regenerateDocIds : undefined,
			mentioned_folder_ids: regenerateFolderIds.length > 0 ? regenerateFolderIds : undefined,
			mentioned_connector_ids:
				regenerateConnectors.length > 0 ? regenerateConnectors.map((d) => d.id) : undefined,
			mentioned_connectors: regenerateConnectors.length > 0 ? regenerateConnectors : undefined,
			mentioned_thread_ids: regenerateThreadIds.length > 0 ? regenerateThreadIds : undefined,
			mentioned_documents: sourceMentionedDocs.length > 0 ? sourceMentionedDocs : undefined,
		};
		if (isEdit) {
			requestBody.user_images = editExtras?.userImages ?? [];
		}
		if (editFromPosition?.fromMessageId != null) {
			requestBody.from_message_id = editFromPosition.fromMessageId;
			if (editFromPosition.revertActions) {
				requestBody.revert_actions = true;
			}
		}
		const response = await fetchWithTurnCancellingRetry(() =>
			authenticatedFetch(getRegenerateUrl(streamThreadId), {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify(requestBody),
				signal: controller.signal,
			})
		);

		if (!response.ok) {
			throw await toHttpResponseError(response);
		}
		regenerateAccepted = true;

		chatStreamStore.setMessages(streamThreadId, (prev) => {
			let base = prev;
			if (editFromPosition?.fromMessageId != null) {
				const targetId = `msg-${editFromPosition.fromMessageId}`;
				const sliceIndex = prev.findIndex((m) => m.id === targetId);
				if (sliceIndex >= 0) {
					base = prev.slice(0, sliceIndex);
				}
			} else if (prev.length >= 2) {
				base = prev.slice(0, -2);
			}
			return [
				...base,
				userMessage,
				{
					id: assistantMsgId,
					role: "assistant",
					content: [{ type: "text", text: "" }],
					createdAt: new Date(),
				},
			];
		});
		if (sourceMentionedDocs.length > 0) {
			jotaiStore.set(messageDocumentsMapAtom, (prev) => ({
				...prev,
				[userMsgId]: sourceMentionedDocs,
			}));
		}

		const flushMessages = () => {
			chatStreamStore.setMessages(streamThreadId, (prev) =>
				prev.map((m) =>
					m.id === assistantMsgId
						? { ...m, content: buildContentForUI(contentPartsState, toolsWithUI) }
						: m
				)
			);
		};
		const { batcher, scheduleFlush, forceFlush } = createStreamFlushHelpers(flushMessages);
		streamBatcher = batcher;

		await consumeSseEvents(response, async (parsed) => {
			if (
				processSharedStreamEvent(parsed, {
					contentPartsState,
					toolsWithUI,
					currentThinkingSteps,
					scheduleFlush,
					forceFlush,
					onTokenUsage: (data) => {
						tokenUsageStore.set(assistantMsgId, data);
					},
					onTurnStatus: (data) => {
						if (data.status === "cancelling") {
							chatStreamStore.markRecentCancel();
						}
					},
				})
			) {
				return;
			}
			switch (parsed.type) {
				case "data-action-log": {
					applyActionLogSse(queryClient, streamThreadId, workspaceId, parsed.data);
					break;
				}

				case "data-action-log-updated": {
					applyActionLogUpdatedSse(
						queryClient,
						streamThreadId,
						parsed.data.id,
						parsed.data.reversible
					);
					break;
				}

				case "data-turn-info": {
					const turnId = readStreamedChatTurnId(parsed.data);
					if (turnId) {
						chatStreamStore.setMessages(streamThreadId, (prev) =>
							applyTurnIdToAssistantMessageList(prev, assistantMsgId, turnId)
						);
					}
					break;
				}

				case "data-user-message-id": {
					const parsedMsg = readStreamedMessageId(parsed.data);
					if (!parsedMsg) break;
					const newUserMsgId = `msg-${parsedMsg.messageId}`;
					const oldUserMsgId = userMsgId;
					chatStreamStore.setMessages(streamThreadId, (prev) =>
						prev.map((m) =>
							m.id === oldUserMsgId
								? mergeChatTurnIdIntoMessage({ ...m, id: newUserMsgId }, parsedMsg.turnId)
								: m
						)
					);
					if (sourceMentionedDocs.length > 0) {
						jotaiStore.set(messageDocumentsMapAtom, (prev) => {
							if (!(oldUserMsgId in prev)) {
								return { ...prev, [newUserMsgId]: sourceMentionedDocs };
							}
							const { [oldUserMsgId]: _removed, ...rest } = prev;
							return { ...rest, [newUserMsgId]: sourceMentionedDocs };
						});
					}
					userMsgId = newUserMsgId;
					break;
				}

				case "data-assistant-message-id": {
					const parsedMsg = readStreamedMessageId(parsed.data);
					if (!parsedMsg) break;
					const newAssistantMsgId = `msg-${parsedMsg.messageId}`;
					const oldAssistantMsgId = assistantMsgId;
					tokenUsageStore.rename(oldAssistantMsgId, newAssistantMsgId);
					chatStreamStore.setMessages(streamThreadId, (prev) =>
						prev.map((m) =>
							m.id === oldAssistantMsgId
								? mergeChatTurnIdIntoMessage({ ...m, id: newAssistantMsgId }, parsedMsg.turnId)
								: m
						)
					);
					assistantMsgId = newAssistantMsgId;
					break;
				}

				case "data-revert-results": {
					const summary = parsed.data;
					const failureCount =
						summary.failed + summary.not_reversible + (summary.permission_denied ?? 0);
					if (failureCount > 0) {
						toast.warning(
							`Pre-revert: ${summary.reverted}/${summary.total} undone, ${failureCount} could not be rolled back.`
						);
					} else if (summary.reverted > 0) {
						toast.success(
							summary.reverted === 1
								? "Reverted 1 downstream action before regenerating."
								: `Reverted ${summary.reverted} downstream actions before regenerating.`
						);
					}
					for (const r of summary.results) {
						if (r.status === "reverted" || r.status === "already_reverted") {
							markActionRevertedInCache(
								queryClient,
								streamThreadId,
								r.action_id,
								r.new_action_id ?? null
							);
						}
					}
					break;
				}
			}
		});

		batcher.flush();

		if (contentParts.length > 0) {
			trackChatResponseReceived(workspaceId, streamThreadId);
		}
	} catch (error) {
		streamBatcher?.dispose();
		await handleStreamTerminalError({
			error,
			flow: "regenerate",
			threadId: streamThreadId,
			assistantMsgId,
			accepted: regenerateAccepted,
			workspaceId,
		});
	} finally {
		chatStreamStore.setRunning(streamThreadId, false);
		chatStreamStore.clearActive(controller);
		void queryClient.invalidateQueries({
			queryKey: cacheKeys.threads.messages(streamThreadId),
		});
		void queryClient.invalidateQueries({
			queryKey: cacheKeys.threads.detail(streamThreadId),
		});
	}
}

export type { HitlDecision };
