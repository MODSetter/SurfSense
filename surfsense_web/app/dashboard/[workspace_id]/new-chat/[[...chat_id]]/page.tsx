"use client";

import {
	type AppendMessage,
	AssistantRuntimeProvider,
	type ThreadMessageLike,
	useExternalStoreRuntime,
} from "@assistant-ui/react";
import { useQueryClient } from "@tanstack/react-query";
import { useAtomValue, useSetAtom, useStore } from "jotai";
import dynamic from "next/dynamic";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { z } from "zod";
import { agentFlagsAtom } from "@/atoms/agent/agent-flags-query.atom";
import { disabledToolsAtom } from "@/atoms/agent-tools/agent-tools.atoms";
import {
	clearTargetCommentIdAtom,
	currentThreadAtom,
	setCurrentThreadMetadataAtom,
	setTargetCommentIdAtom,
} from "@/atoms/chat/current-thread.atom";
import {
	deriveMentionedPayload,
	type MentionedDocumentInfo,
	mentionedDocumentsAtom,
	messageDocumentsMapAtom,
	submittedMentionsAtom,
} from "@/atoms/chat/mentioned-documents.atom";
import { pendingUserImageDataUrlsAtom } from "@/atoms/chat/pending-user-images.atom";
import {
	clearPlanOwnerRegistry,
	// extractWriteTodosFromContent,
} from "@/atoms/chat/plan-state.atom";
import { setPremiumAlertForThreadAtom } from "@/atoms/chat/premium-alert.atom";
import { closeReportPanelAtom } from "@/atoms/chat/report-panel.atom";
import { type AgentCreatedDocument, agentCreatedDocumentsAtom } from "@/atoms/documents/ui.atoms";
import { closeEditorPanelAtom } from "@/atoms/editor/editor-panel.atom";
import { membersAtom } from "@/atoms/members/members-query.atoms";
import { removeChatTabAtom, syncChatTabAtom, updateChatTabTitleAtom } from "@/atoms/tabs/tabs.atom";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import {
	EditMessageDialog,
	type EditMessageDialogChoice,
} from "@/components/assistant-ui/edit-message-dialog";
import { StepSeparatorDataUI } from "@/components/assistant-ui/step-separator";
import { Thread } from "@/components/assistant-ui/thread";
import {
	createTokenUsageStore,
	type TokenUsageData,
	TokenUsageProvider,
} from "@/components/assistant-ui/token-usage-context";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useSyncChatArtifacts } from "@/features/chat-artifacts";
import {
	type HitlDecision,
	PendingInterruptProvider,
	type PendingInterruptState,
} from "@/features/chat-messages/hitl";
import { TimelineDataUI } from "@/features/chat-messages/timeline";
import {
	applyActionLogSse,
	applyActionLogUpdatedSse,
	markActionRevertedInCache,
	useAgentActionsQuery,
} from "@/hooks/use-agent-actions-query";
import { useChatSessionStateSync } from "@/hooks/use-chat-session-state";
import { useMessagesSync } from "@/hooks/use-messages-sync";
import { useThreadDetail, useThreadMessages } from "@/hooks/use-thread-queries";
import { getAgentFilesystemSelection } from "@/lib/agent-filesystem";
import { documentsApiService } from "@/lib/apis/documents-api.service";
import { authenticatedFetch } from "@/lib/auth-fetch";
import { type ChatFlow, classifyChatError } from "@/lib/chat/chat-error-classifier";
import { tagPreAcceptSendFailure, toHttpResponseError } from "@/lib/chat/chat-request-errors";
import { getMentionDocKey } from "@/lib/chat/mention-doc-key";
import {
	convertToThreadMessage,
	reconcileInterruptedAssistantMessages,
} from "@/lib/chat/message-utils";
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
	type ToolUIGate,
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
import { NotFoundError } from "@/lib/error";
import {
	trackChatBlocked,
	trackChatCreated,
	trackChatErrorDetailed,
	trackChatMessageSent,
	trackChatResponseReceived,
} from "@/lib/posthog/events";
import { cacheKeys } from "@/lib/query-client/cache-keys";

const MobileEditorPanel = dynamic(
	() =>
		import("@/components/editor-panel/editor-panel").then((m) => ({
			default: m.MobileEditorPanel,
		})),
	{ ssr: false }
);
const MobileHitlEditPanel = dynamic(
	() =>
		import("@/features/chat-messages/hitl").then((m) => ({
			default: m.MobileHitlEditPanel,
		})),
	{ ssr: false }
);
const MobileReportPanel = dynamic(
	() =>
		import("@/components/report-panel/report-panel").then((m) => ({
			default: m.MobileReportPanel,
		})),
	{ ssr: false }
);
const MobileArtifactsPanel = dynamic(
	() =>
		import("@/features/chat-artifacts/ui/artifacts-panel").then((m) => ({
			default: m.MobileArtifactsPanel,
		})),
	{ ssr: false }
);

/**
 * Generate a synthetic ``toolCallId`` for an action_request that has no
 * matching streamed tool-call card (HITL-blocked subagent calls don't surface
 * as tool-call events). Suffixes a counter when the base id is already taken
 * — sequential interrupts for the same tool name otherwise collide on
 * ``interrupt-${name}-${i}`` and crash assistant-ui with a duplicate-key error.
 */
function freshSynthToolCallId(
	toolCallIndices: Map<string, number>,
	toolName: string,
	index: number
): string {
	const base = `interrupt-${toolName}-${index}`;
	if (!toolCallIndices.has(base)) return base;
	let n = 1;
	while (toolCallIndices.has(`${base}-${n}`)) n++;
	return `${base}-${n}`;
}

/**
 * Pair each ``action_request`` to a unique pending tool-call card, preserving
 * order so ``decisions[i]`` lines up with ``action_requests[i]`` on the wire.
 *
 * Same-name bundles (e.g. three ``create_jira_issue``) used to collapse onto
 * one card because the matcher keyed by name; this consumes each card via the
 * ``claimed`` set and walks forward in DOM order.
 */
function pairBundleToolCallIds(
	toolCallIndices: Map<string, number>,
	contentParts: Array<{
		type: string;
		toolName?: string;
		result?: unknown;
	}>,
	actionRequests: ReadonlyArray<{ name: string }>
): Array<string | null> {
	const claimed = new Set<string>();
	const paired: Array<string | null> = [];
	for (const action of actionRequests) {
		let matched: string | null = null;
		for (const [tcId, idx] of toolCallIndices) {
			if (claimed.has(tcId)) continue;
			const part = contentParts[idx];
			if (!part || part.type !== "tool-call" || part.toolName !== action.name) continue;
			const result = part.result as Record<string, unknown> | undefined | null;
			if (result == null || (result.__interrupt__ === true && !result.__decided__)) {
				matched = tcId;
				claimed.add(tcId);
				break;
			}
		}
		paired.push(matched);
	}
	return paired;
}

/**
 * Zod schema for mentioned document info (for type-safe parsing).
 *
 * ``kind`` defaults to ``"doc"`` so messages persisted before folder
 * mentions existed deserialise unchanged.
 */
const MentionedDocumentInfoSchema = z.object({
	id: z.number(),
	title: z.string(),
	document_type: z.string().optional(),
	kind: z
		.union([z.literal("doc"), z.literal("folder"), z.literal("connector"), z.literal("thread")])
		.optional()
		.default("doc"),
	connector_type: z.string().optional(),
	account_name: z.string().optional(),
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
			return result.data.documents.map<MentionedDocumentInfo>((doc) => {
				if (doc.kind === "connector") {
					return {
						id: doc.id,
						title: doc.title,
						kind: "connector",
						connector_type: doc.connector_type ?? doc.document_type ?? "UNKNOWN",
						account_name: doc.account_name ?? doc.title,
					};
				}
				if (doc.kind === "folder") {
					return {
						id: doc.id,
						title: doc.title,
						kind: "folder",
					};
				}
				if (doc.kind === "thread") {
					return {
						id: doc.id,
						title: doc.title,
						kind: "thread",
					};
				}
				return {
					id: doc.id,
					title: doc.title,
					document_type: doc.document_type ?? "UNKNOWN",
					kind: "doc",
				};
			});
		}
	}

	return [];
}

/**
 * Every tool call renders a card. The legacy
 * ``BASE_TOOLS_WITH_UI`` allowlist used to drop unknown tool calls on the
 * floor; we now route everything through ``ToolFallback``. Persisted
 * payload size stays bounded because the backend's
 * ``format_thinking_step`` summarisation and the
 * ``result_length``-only default for unknown tools (see
 * ``stream_new_chat.py``) keep the JSON from ballooning.
 */
const TOOLS_WITH_UI_ALL: ToolUIGate = "all";
const TURN_CANCELLING_INITIAL_DELAY_MS = 200;
const TURN_CANCELLING_BACKOFF_FACTOR = 2;
const TURN_CANCELLING_MAX_DELAY_MS = 1500;
const RECENT_CANCEL_WINDOW_MS = 5_000;

function sleep(ms: number): Promise<void> {
	return new Promise((resolve) => setTimeout(resolve, ms));
}

function computeFallbackTurnCancellingRetryDelay(attempt: number): number {
	const safeAttempt = Math.max(1, attempt);
	const raw =
		TURN_CANCELLING_INITIAL_DELAY_MS * TURN_CANCELLING_BACKOFF_FACTOR ** (safeAttempt - 1);
	return Math.min(raw, TURN_CANCELLING_MAX_DELAY_MS);
}

function parseUrlChatId(id: string | string[] | undefined): number {
	let parsed = 0;
	if (Array.isArray(id) && id.length > 0) {
		parsed = Number.parseInt(id[0], 10);
	} else if (typeof id === "string") {
		parsed = Number.parseInt(id, 10);
	}
	return Number.isNaN(parsed) ? 0 : parsed;
}

function ThreadMessagesSkeleton() {
	return (
		<div
			className="aui-root aui-thread-root @container flex h-full min-h-0 flex-col bg-panel"
			style={{
				["--thread-max-width" as string]: "42rem",
			}}
		>
			<div
				className="aui-thread-viewport relative flex flex-1 min-h-0 flex-col overflow-y-auto px-4 scroll-smooth"
				style={{ scrollbarGutter: "stable" }}
			>
				<div
					aria-hidden
					className="aui-chat-viewport-top-fade pointer-events-none sticky top-0 z-10 -mx-4 h-2 shrink-0 bg-gradient-to-b from-panel from-20% to-transparent"
				/>
				<div className="mx-auto w-full max-w-(--thread-max-width) flex flex-1 flex-col gap-6 py-8">
					<div className="flex justify-end">
						<Skeleton className="h-12 w-[65%] max-w-56 rounded-2xl" />
					</div>

					<div className="flex flex-col gap-2">
						<Skeleton className="h-4 w-full" />
						<Skeleton className="h-4 w-[85%]" />
						<Skeleton className="h-18 w-[40%]" />
					</div>

					<div className="flex gap-2 justify-end">
						<Skeleton className="h-12 w-[78%] max-w-72 rounded-2xl" />
					</div>

					<div className="flex flex-col gap-2">
						<Skeleton className="h-10 w-[30%]" />
						<Skeleton className="h-4 w-[90%]" />
						<Skeleton className="h-6 w-[60%]" />
					</div>

					<div className="flex gap-2 justify-end">
						<Skeleton className="h-12 w-[85%] max-w-96 rounded-2xl" />
					</div>
				</div>

				<div
					className="aui-chat-composer-footer sticky bottom-0 z-20 -mx-4 mt-auto flex flex-col items-stretch bg-gradient-to-t from-panel from-60% to-transparent px-4 pt-6"
					style={{ paddingBottom: "max(0.5rem, env(safe-area-inset-bottom))" }}
				>
					<div className="aui-chat-composer-area relative mx-auto flex w-full max-w-(--thread-max-width) flex-col gap-3 overflow-visible">
						<Skeleton className="h-28 w-full rounded-3xl" />
					</div>
				</div>
			</div>
		</div>
	);
}

export default function NewChatPage() {
	const params = useParams();
	const queryClient = useQueryClient();
	const urlChatId = useMemo(() => parseUrlChatId(params.chat_id), [params.chat_id]);
	const [threadId, setThreadId] = useState<number | null>(() => (urlChatId > 0 ? urlChatId : null));
	const activeThreadId = urlChatId > 0 ? urlChatId : threadId;
	const handledLoadErrorThreadRef = useRef<number | null>(null);
	const [currentThread, setCurrentThread] = useState<ThreadRecord | null>(null);
	const [messages, setMessages] = useState<ThreadMessageLike[]>([]);
	const [isRunning, setIsRunning] = useState(false);
	const [tokenUsageStore] = useState(() => createTokenUsageStore());
	const abortControllerRef = useRef<AbortController | null>(null);
	const recentCancelRequestedAtRef = useRef(0);
	// One entry per paused subagent, in receipt order (which matches the
	// backend's ``state.interrupts`` traversal — and therefore the order
	// ``slice_decisions_by_tool_call`` consumes on resume). Cleared on submit
	// or on a fresh user turn.
	const [pendingInterrupts, setPendingInterrupts] = useState<PendingInterruptState[]>([]);
	// Per-card staged decisions held until every pending card has submitted,
	// at which point we batch them into one ``hitl-decision`` event in the
	// same order as ``pendingInterrupts``. Using a ref because partial
	// progress should not re-render the page.
	const stagedDecisionsByInterruptIdRef = useRef<Map<string, HitlDecision[]>>(new Map());
	const toolsWithUI = TOOLS_WITH_UI_ALL;
	const setMessageDocumentsMap = useSetAtom(messageDocumentsMapAtom);

	const persistAssistantErrorMessage = useCallback(
		async ({
			threadId,
			assistantMsgId,
			text,
		}: {
			threadId: number | null;
			assistantMsgId: string;
			text: string;
		}) => {
			setMessages((prev) =>
				prev.map((m) =>
					m.id === assistantMsgId
						? {
								...m,
								content: [{ type: "text", text }],
							}
						: m
				)
			);

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
				setMessages((prev) =>
					prev.map((m) => (m.id === assistantMsgId ? { ...m, id: newMsgId } : m))
				);
			} catch (persistErr) {
				console.error("Failed to persist assistant error message:", persistErr);
			}
		},
		[tokenUsageStore]
	);

	// NOTE: ``persistUserTurn`` / ``persistAssistantTurn`` callbacks
	// were removed in the SSE-based message ID handshake refactor.
	// ``stream_new_chat`` and ``stream_resume_chat`` now persist both
	// the user and assistant rows server-side via
	// ``persist_user_turn`` / ``persist_assistant_shell`` and emit
	// ``data-user-message-id`` / ``data-assistant-message-id`` SSE
	// events; the consumers below rename the optimistic ids in real
	// time. ``persistAssistantErrorMessage`` (above) is intentionally
	// kept — it is the pre-stream-error fallback fired when the
	// server NEVER accepted the request, and the BE has nothing to
	// persist in that case.

	// Get disabled tools from the tool toggle UI
	const disabledTools = useAtomValue(disabledToolsAtom);

	const jotaiStore = useStore();
	const mentionedDocuments = useAtomValue(mentionedDocumentsAtom);
	const messageDocumentsMap = useAtomValue(messageDocumentsMapAtom);
	const setMentionedDocuments = useSetAtom(mentionedDocumentsAtom);
	const currentThreadState = useAtomValue(currentThreadAtom);
	const setCurrentThreadMetadata = useSetAtom(setCurrentThreadMetadataAtom);
	const setPremiumAlertForThread = useSetAtom(setPremiumAlertForThreadAtom);
	const setTargetCommentId = useSetAtom(setTargetCommentIdAtom);
	const clearTargetCommentId = useSetAtom(clearTargetCommentIdAtom);
	const closeReportPanel = useSetAtom(closeReportPanelAtom);
	const closeEditorPanel = useSetAtom(closeEditorPanelAtom);
	const syncChatTab = useSetAtom(syncChatTabAtom);
	const updateChatTabTitle = useSetAtom(updateChatTabTitleAtom);
	const removeChatTab = useSetAtom(removeChatTabAtom);
	const setAgentCreatedDocuments = useSetAtom(agentCreatedDocumentsAtom);
	const pendingUserImageUrls = useAtomValue(pendingUserImageDataUrlsAtom);
	const setPendingUserImageUrls = useSetAtom(pendingUserImageDataUrlsAtom);
	// Edit dialog state. Holds the message id being edited and
	// the (already extracted) regenerate args so we can resume the edit
	// after the user picks "revert all" / "continue" / "cancel".
	const [editDialogState, setEditDialogState] = useState<{
		fromMessageId: number;
		userQuery: string | null;
		userMessageContent: ThreadMessageLike["content"];
		userImages: NewChatUserImagePayload[];
		downstreamReversibleCount: number;
		downstreamTotalCount: number;
	} | null>(null);

	// Get current user for author info in shared chats
	const { data: currentUser } = useAtomValue(currentUserAtom);
	const { data: agentFlags } = useAtomValue(agentFlagsAtom);
	const localFilesystemEnabled = agentFlags?.enable_desktop_local_filesystem === true;
	const threadDetailQuery = useThreadDetail(activeThreadId);
	const threadMessagesQuery = useThreadMessages(activeThreadId);

	// Live collaboration: sync session state and messages via Zero
	useChatSessionStateSync(activeThreadId);
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
				// Forwarded so ``convertToThreadMessage`` can rebuild the
				// ``metadata.custom.chatTurnId`` on the
				// ``ThreadMessageLike``. Required by the inline Revert
				// button's per-turn fallback.
				turn_id?: string | null;
			}[]
		) => {
			if (isRunning) {
				return;
			}

			setMessages((prev) => {
				if (syncedMessages.length < prev.length) {
					return prev;
				}

				const memberById = new Map(membersData?.map((m) => [m.user_id, m]) ?? []);
				const prevById = new Map(prev.map((m) => [m.id, m]));

				return reconcileInterruptedAssistantMessages(syncedMessages).map((msg) => {
					const member = msg.author_id ? (memberById.get(msg.author_id) ?? null) : null;

					// Preserve existing author info if member lookup fails (e.g., cloned chats)
					const existingMsg = prevById.get(`msg-${msg.id}`);
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
						// Forward the per-turn correlation id so the
						// inline Revert button's ``(chat_turn_id,
						// tool_name, position)`` fallback survives the
						// post-stream Zero re-sync.
						turn_id: msg.turn_id ?? null,
					});
				});
			});
		},
		[isRunning, membersData]
	);

	useMessagesSync(activeThreadId, handleSyncedMessagesUpdate);

	// Extract workspace_id from URL params
	const workspaceId = useMemo(() => {
		const id = params.workspace_id;
		const parsed = typeof id === "string" ? Number.parseInt(id, 10) : 0;
		return Number.isNaN(parsed) ? 0 : parsed;
	}, [params.workspace_id]);

	// Unified store for agent-action rows (the same react-query cache
	// the agent-actions dialog, the inline Revert button, and the
	// per-turn Revert button all read). Hydrates from
	// ``GET /threads/{id}/actions`` and is updated incrementally by the
	// SSE handlers + revert-batch results below — no atom side-channel.
	const { items: agentActionItems } = useAgentActionsQuery(activeThreadId);

	const handleChatFailure = useCallback(
		async ({
			error,
			flow,
			threadId,
			assistantMsgId,
		}: {
			error: unknown;
			flow: ChatFlow;
			threadId: number | null;
			assistantMsgId: string;
		}) => {
			const normalized = classifyChatError({
				error,
				flow,
				context: {
					workspaceId,
					threadId,
				},
			});

			const logger =
				normalized.severity === "error"
					? console.error
					: normalized.severity === "warn"
						? console.warn
						: console.info;
			logger(`[NewChatPage] ${flow} ${normalized.kind}:`, error);

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
					setPremiumAlertForThread({
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
		},
		[currentUser?.id, persistAssistantErrorMessage, workspaceId, setPremiumAlertForThread]
	);

	const handleStreamTerminalError = useCallback(
		async ({
			error,
			flow,
			threadId,
			assistantMsgId,
			accepted,
			onAbort,
			onPreAcceptFailure,
			onAcceptedStreamError,
		}: {
			error: unknown;
			flow: ChatFlow;
			threadId: number | null;
			assistantMsgId: string;
			accepted: boolean;
			onAbort?: () => Promise<void>;
			onPreAcceptFailure?: () => Promise<void>;
			onAcceptedStreamError?: () => Promise<void>;
		}) => {
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
			});
		},
		[handleChatFailure]
	);

	const fetchWithTurnCancellingRetry = useCallback(async (runFetch: () => Promise<Response>) => {
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
				Date.now() - recentCancelRequestedAtRef.current <= RECENT_CANCEL_WINDOW_MS;
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
	}, []);

	const hydratedMessagesRef = useRef<{
		threadId: number | null;
		data: typeof threadMessagesQuery.data;
	}>({ threadId: null, data: undefined });

	// Reset thread-local runtime state on route/search-space changes. Data fetching
	// is handled by React Query below so the chat shell can render immediately.
	useEffect(() => {
		const nextThreadId = urlChatId > 0 ? urlChatId : null;
		handledLoadErrorThreadRef.current = null;
		hydratedMessagesRef.current = { threadId: null, data: undefined };
		setThreadId(nextThreadId);
		setMessages([]);
		setCurrentThread(null);
		setMentionedDocuments([]);
		tokenUsageStore.clear();
		setMessageDocumentsMap({});
		clearPlanOwnerRegistry();
		closeReportPanel();
		closeEditorPanel();
		// Note: agent-action data is keyed by threadId in react-query so
		// switching threads naturally swaps caches; no explicit reset.
	}, [
		urlChatId,
		setMentionedDocuments,
		setMessageDocumentsMap,
		tokenUsageStore,
		closeReportPanel,
		closeEditorPanel,
	]);

	useEffect(() => {
		if (!activeThreadId) {
			setCurrentThread(null);
			return;
		}
		if (threadDetailQuery.data?.id === activeThreadId) {
			const thread = threadDetailQuery.data;
			setCurrentThread(thread);
			syncChatTab({
				chatId: thread.id,
				title: thread.title,
				chatUrl: `/dashboard/${thread.workspace_id ?? workspaceId}/new-chat/${thread.id}`,
				workspaceId: thread.workspace_id ?? workspaceId,
				visibility: thread.visibility,
				hasComments: thread.has_comments ?? false,
			});
		}
	}, [activeThreadId, workspaceId, syncChatTab, threadDetailQuery.data]);

	useEffect(() => {
		const messagesResponse = threadMessagesQuery.data;
		if (!activeThreadId || !messagesResponse) return;

		if (
			hydratedMessagesRef.current.threadId === activeThreadId &&
			hydratedMessagesRef.current.data === messagesResponse
		) {
			return;
		}

		if (isRunning) {
			return;
		}

		const loadedMessages = reconcileInterruptedAssistantMessages(messagesResponse.messages).map(
			convertToThreadMessage
		);
		if (messages.length > 0 && loadedMessages.length < messages.length) {
			return;
		}
		setMessages(loadedMessages);

		tokenUsageStore.clear();
		const restoredDocsMap: Record<string, MentionedDocumentInfo[]> = {};
		for (const msg of messagesResponse.messages) {
			if (msg.token_usage) {
				tokenUsageStore.set(`msg-${msg.id}`, msg.token_usage as TokenUsageData);
			}
			if (msg.role === "user") {
				const docs = extractMentionedDocuments(msg.content);
				if (docs.length > 0) {
					restoredDocsMap[`msg-${msg.id}`] = docs;
				}
			}
		}
		setMessageDocumentsMap(restoredDocsMap);
		hydratedMessagesRef.current = { threadId: activeThreadId, data: messagesResponse };
	}, [
		activeThreadId,
		isRunning,
		messages.length,
		setMessageDocumentsMap,
		threadMessagesQuery.data,
		tokenUsageStore,
	]);

	useEffect(() => {
		const loadError = threadDetailQuery.error ?? threadMessagesQuery.error;
		if (!activeThreadId || !loadError) return;
		if (handledLoadErrorThreadRef.current === activeThreadId) return;

		handledLoadErrorThreadRef.current = activeThreadId;
		console.error("[NewChatPage] Failed to load thread:", loadError);

		if (loadError instanceof NotFoundError) {
			removeChatTab(activeThreadId);
			if (typeof window !== "undefined") {
				window.history.replaceState(null, "", `/dashboard/${workspaceId}/new-chat`);
			}
			setThreadId(null);
			setCurrentThread(null);
			setMessages([]);
			toast.error("This chat was deleted.");
			return;
		}

		toast.error("Failed to load chat. Please try again.");
	}, [
		activeThreadId,
		removeChatTab,
		workspaceId,
		threadDetailQuery.error,
		threadMessagesQuery.error,
	]);

	// Prefetch document titles for @ mention picker
	// Runs when user lands on page so data is ready when they type @
	useEffect(() => {
		if (!workspaceId) return;

		const prefetchParams = {
			workspace_id: workspaceId,
			page: 0,
			page_size: 20,
		};

		queryClient.prefetchQuery({
			queryKey: ["document-titles", prefetchParams],
			queryFn: () => documentsApiService.searchDocumentTitles({ queryParams: prefetchParams }),
			staleTime: 60 * 1000,
		});
	}, [workspaceId, queryClient]);

	// Handle scroll to comment from URL query params (e.g., from inbox item click)
	// Read from window.location.search inside the effect instead of subscribing via
	// useSearchParams() — avoids re-rendering this heavy component tree on every
	// unrelated query-string change. (Vercel Best Practice: rerender-defer-reads 5.2)
	useEffect(() => {
		const readAndApplyCommentId = () => {
			const params = new URLSearchParams(window.location.search);
			const raw = params.get("commentId");
			if (raw && activeThreadId) {
				const commentId = Number.parseInt(raw, 10);
				if (!Number.isNaN(commentId)) {
					setTargetCommentId(commentId);
				}
			}
		};

		readAndApplyCommentId();

		// Also respond to SPA navigations (back/forward) that change the query string
		window.addEventListener("popstate", readAndApplyCommentId);

		// Cleanup on unmount or when navigating away
		return () => {
			window.removeEventListener("popstate", readAndApplyCommentId);
			clearTargetCommentId();
		};
	}, [activeThreadId, setTargetCommentId, clearTargetCommentId]);

	// Sync current thread state to atom
	useEffect(() => {
		if (!currentThread) {
			if (activeThreadId) {
				return;
			}
			setCurrentThreadMetadata({
				id: null,
				workspaceId: null,
				visibility: null,
				hasComments: false,
			});
			return;
		}

		const visibility =
			currentThreadState.id === currentThread.id && currentThreadState.visibility !== null
				? currentThreadState.visibility
				: currentThread.visibility;

		setCurrentThreadMetadata({
			id: currentThread.id,
			workspaceId: currentThread.workspace_id ?? workspaceId,
			visibility,
			hasComments: currentThread.has_comments ?? false,
		});
	}, [
		activeThreadId,
		currentThread,
		currentThreadState.id,
		currentThreadState.visibility,
		workspaceId,
		setCurrentThreadMetadata,
	]);

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
		if (threadId) {
			try {
				const response = await authenticatedFetch(
					buildBackendUrl(`/api/v1/threads/${threadId}/cancel-active-turn`),
					{
						method: "POST",
					}
				);
				if (response.ok) {
					const payload = (await response.json()) as {
						error_code?: string;
					};
					if (payload.error_code === "TURN_CANCELLING") {
						recentCancelRequestedAtRef.current = Date.now();
					}
				}
			} catch (error) {
				console.warn("[NewChatPage] Failed to signal cancel-active-turn:", error);
			}
		}
		if (abortControllerRef.current) {
			abortControllerRef.current.abort();
			abortControllerRef.current = null;
		}
		setIsRunning(false);
	}, [threadId]);

	// Handle new message from user
	const onNew = useCallback(
		async (message: AppendMessage) => {
			// Abort any previous streaming request to prevent race conditions
			// when user sends a second query while the first is still streaming
			if (abortControllerRef.current) {
				abortControllerRef.current.abort();
				abortControllerRef.current = null;
			}

			// Prefer the submit-time snapshot; fall back to the live atom
			// for the send-button path.
			const submittedSnapshot = jotaiStore.get(submittedMentionsAtom);
			jotaiStore.set(submittedMentionsAtom, null);
			const activeMentions = submittedSnapshot ?? mentionedDocuments;
			const mentionPayload = deriveMentionedPayload(activeMentions);
			if (activeMentions.length > 0) {
				setMentionedDocuments([]);
			}

			const urlsSnapshot = [...pendingUserImageUrls];
			const { userQuery, userImages } = extractUserTurnForNewChatApi(message, urlsSnapshot);

			if (!userQuery.trim() && userImages.length === 0) return;

			// Lazy thread creation: create thread on first message if it doesn't exist
			let currentThreadId = threadId;
			let isNewThread = false;
			if (!currentThreadId) {
				try {
					const newThread = await createThread(workspaceId, "New Chat");
					currentThreadId = newThread.id;
					setThreadId(currentThreadId);
					// Set currentThread so share button in header appears immediately
					setCurrentThread(newThread);
					queryClient.setQueryData(cacheKeys.threads.detail(newThread.id), newThread);
					queryClient.setQueryData(cacheKeys.threads.messages(newThread.id), { messages: [] });

					// Track chat creation
					trackChatCreated(workspaceId, currentThreadId);

					isNewThread = true;
					// Update URL silently using browser API (not router.replace) to avoid
					// interrupting the ongoing fetch/streaming with React navigation
					window.history.replaceState(
						null,
						"",
						`/dashboard/${workspaceId}/new-chat/${currentThreadId}`
					);
				} catch (error) {
					console.error("[NewChatPage] Failed to create thread:", error);
					await handleChatFailure({
						error: tagPreAcceptSendFailure(error),
						flow: "new",
						threadId: currentThreadId,
						assistantMsgId: "no-persist-assistant",
					});
					return;
				}
			}

			if (urlsSnapshot.length > 0) {
				setPendingUserImageUrls((prev) => prev.filter((u) => !urlsSnapshot.includes(u)));
			}

			// Add user message to state. Mutable because the SSE
			// ``data-user-message-id`` handler (below) renames this
			// optimistic id to the canonical ``msg-{db_id}`` once the
			// backend's ``persist_user_turn`` resolves the row, and
			// the in-stream flush / interrupt closures need to see
			// the post-rename value via this live ``let`` binding.
			let userMsgId = `msg-user-${Date.now()}`;

			// Always include author metadata so the UI layer can decide visibility
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
							typeof p === "object" &&
							p !== null &&
							"type" in p &&
							p.type === "image" &&
							"image" in p
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
			setMessages((prev) => [...prev, userMessage]);

			// Track message sent
			trackChatMessageSent(workspaceId, currentThreadId, {
				hasAttachments: userImages.length > 0,
				hasMentionedDocuments:
					mentionPayload.document_ids.length > 0 ||
					mentionPayload.folder_ids.length > 0 ||
					mentionPayload.connector_ids.length > 0,
				messageLength: userQuery.length,
			});

			// Collect unique mention chips for display & persistence.
			// The ``kind`` field is forwarded to the backend
			// so the persisted ``mentioned-documents`` content part
			// can render the correct chip type on reload.
			const allMentionedDocs: MentionedDocumentInfo[] = [];
			const seenDocKeys = new Set<string>();
			for (const doc of activeMentions) {
				const key = getMentionDocKey(doc);
				if (seenDocKeys.has(key)) continue;
				seenDocKeys.add(key);
				allMentionedDocs.push(doc);
			}

			if (allMentionedDocs.length > 0) {
				setMessageDocumentsMap((prev) => ({
					...prev,
					[userMsgId]: allMentionedDocs,
				}));
			}

			// Start streaming response
			setIsRunning(true);
			const controller = new AbortController();
			abortControllerRef.current = controller;

			// Prepare assistant message. Mutable for the same reason
			// as ``userMsgId`` above — the ``data-assistant-message-id``
			// SSE handler reassigns this once
			// ``persist_assistant_shell`` returns its canonical id.
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
				const selection = await getAgentFilesystemSelection(workspaceId, {
					localFilesystemEnabled,
				});
				if (
					selection.filesystem_mode === "desktop_local_folder" &&
					(!selection.local_filesystem_mounts || selection.local_filesystem_mounts.length === 0)
				) {
					toast.error("Select a local folder before using Local Folder mode.");
					return;
				}

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

				// Backend expects each mention kind in its own payload bucket.
				const hasDocumentIds = mentionPayload.document_ids.length > 0;
				const hasFolderIds = mentionPayload.folder_ids.length > 0;
				const hasConnectorIds = mentionPayload.connector_ids.length > 0;
				const hasThreadIds = mentionPayload.thread_ids.length > 0;

				const response = await fetchWithTurnCancellingRetry(() =>
					authenticatedFetch(buildBackendUrl("/api/v1/new_chat"), {
						method: "POST",
						headers: {
							"Content-Type": "application/json",
						},
						body: JSON.stringify({
							chat_id: currentThreadId,
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
							// Full mention metadata so the backend can persist a
							// ``mentioned-documents`` ContentPart on the user message.
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
				setMessages((prev) => [
					...prev,
					{
						id: assistantMsgId,
						role: "assistant",
						content: [{ type: "text", text: "" }],
						createdAt: new Date(),
					},
				]);

				const flushMessages = () => {
					setMessages((prev) =>
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
									recentCancelRequestedAtRef.current = Date.now();
								}
							},
						})
					) {
						return;
					}
					switch (parsed.type) {
						case "data-thread-title-update": {
							const titleData = parsed.data as { threadId: number; title: string };
							if (titleData?.title && titleData?.threadId === currentThreadId) {
								setCurrentThread((prev) => (prev ? { ...prev, title: titleData.title } : prev));
								updateChatTabTitle({ chatId: currentThreadId, title: titleData.title });
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
								setAgentCreatedDocuments((prev) => {
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
									targetTcId = freshSynthToolCallId(
										contentPartsState.toolCallIndices,
										action.name,
										i
									);
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
							setMessages((prev) =>
								prev.map((m) =>
									m.id === assistantMsgId
										? { ...m, content: buildContentForUI(contentPartsState, toolsWithUI) }
										: m
								)
							);
							if (currentThreadId) {
								// ``tool_call_id`` is stamped on the backend by
								// ``checkpointed_subagent_middleware``. Without it we
								// can't address the paused subagent on resume — skip
								// rather than fabricate a synthetic key.
								const interruptId = String(interruptData.tool_call_id ?? "");
								if (interruptId) {
									const incoming: PendingInterruptState = {
										interruptId,
										threadId: currentThreadId,
										assistantMsgId,
										interruptData,
										bundleToolCallIds,
									};
									setPendingInterrupts((prev) => {
										const without = prev.filter((p) => p.interruptId !== interruptId);
										return [...without, incoming];
									});
								}
							}
							break;
						}

						case "data-action-log": {
							applyActionLogSse(queryClient, currentThreadId, workspaceId, parsed.data);
							break;
						}

						case "data-action-log-updated": {
							applyActionLogUpdatedSse(
								queryClient,
								currentThreadId,
								parsed.data.id,
								parsed.data.reversible
							);
							break;
						}

						case "data-turn-info": {
							const turnId = readStreamedChatTurnId(parsed.data);
							if (turnId) {
								setMessages((prev) =>
									applyTurnIdToAssistantMessageList(prev, assistantMsgId, turnId)
								);
							}
							break;
						}

						case "data-user-message-id": {
							// Server-authoritative user message id resolved by
							// ``persist_user_turn`` (or recovered via ON CONFLICT).
							// Rename the optimistic ``msg-user-XXX`` placeholder to
							// the canonical ``msg-{db_id}`` so DB-id-gated UI
							// (comments, edit-from-this-message) unlocks immediately,
							// migrate the local mentioned-documents map, and reassign
							// the closure variable so all downstream
							// ``m.id === userMsgId`` checks see the new value.
							const parsedMsg = readStreamedMessageId(parsed.data);
							if (!parsedMsg) break;
							const newUserMsgId = `msg-${parsedMsg.messageId}`;
							const oldUserMsgId = userMsgId;
							setMessages((prev) =>
								prev.map((m) =>
									m.id === oldUserMsgId
										? mergeChatTurnIdIntoMessage({ ...m, id: newUserMsgId }, parsedMsg.turnId)
										: m
								)
							);
							if (allMentionedDocs.length > 0) {
								setMessageDocumentsMap((prev) => {
									if (!(oldUserMsgId in prev)) {
										return { ...prev, [newUserMsgId]: allMentionedDocs };
									}
									const { [oldUserMsgId]: _removed, ...rest } = prev;
									return { ...rest, [newUserMsgId]: allMentionedDocs };
								});
							}
							userMsgId = newUserMsgId;
							if (isNewThread) {
								// First user-side row landed in ``new_chat_messages``;
								// refresh the sidebar so the freshly-bumped
								// ``thread.updated_at`` reorders this thread.
								queryClient.invalidateQueries({
									queryKey: ["threads", String(workspaceId)],
								});
							}
							break;
						}

						case "data-assistant-message-id": {
							// Server-authoritative assistant message id resolved
							// by ``persist_assistant_shell``. Rename the optimistic
							// id, migrate ``tokenUsageStore`` so any pending
							// ``data-token-usage`` payload binds to the new id,
							// remap any in-flight ``pendingInterrupts`` entries,
							// and reassign the closure variable so the in-stream
							// flush callback (line ~1074) keeps writing to the
							// renamed message.
							const parsedMsg = readStreamedMessageId(parsed.data);
							if (!parsedMsg) break;
							const newAssistantMsgId = `msg-${parsedMsg.messageId}`;
							const oldAssistantMsgId = assistantMsgId;
							tokenUsageStore.rename(oldAssistantMsgId, newAssistantMsgId);
							setMessages((prev) =>
								prev.map((m) =>
									m.id === oldAssistantMsgId
										? mergeChatTurnIdIntoMessage({ ...m, id: newAssistantMsgId }, parsedMsg.turnId)
										: m
								)
							);
							setPendingInterrupts((prev) =>
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

				// Server-authoritative persistence: ``stream_new_chat``
				// already wrote the user row in ``persist_user_turn``
				// (the FE renamed the optimistic id mid-stream via
				// ``data-user-message-id``) and finalises the assistant
				// row in ``finalize_assistant_turn`` from a shielded
				// ``finally`` block. Nothing left for the FE to persist
				// here — track the response and unblock the UI.
				if (contentParts.length > 0 && !wasInterrupted) {
					trackChatResponseReceived(workspaceId, currentThreadId);
				}
			} catch (error) {
				streamBatcher?.dispose();
				await handleStreamTerminalError({
					error,
					flow: "new",
					threadId: currentThreadId,
					assistantMsgId,
					accepted: newAccepted,
					// Server-side ``finalize_assistant_turn`` runs from a
					// shielded ``anyio.CancelScope(shield=True)`` finally
					// block, so partial content (incl. abort-mid-stream)
					// is already persisted by the BE for the assistant
					// row, and ``persist_user_turn`` ran before any LLM
					// call. The FE's only remaining responsibility on
					// abort / accepted-stream-error is to surface the
					// error toast (handled by ``handleStreamTerminalError``
					// itself).
					onPreAcceptFailure: async () => {
						// Pre-accept failure means the BE never accepted the
						// request — no server-side persistence ran. Roll
						// back the optimistic UI insertions we made before
						// the fetch so the user message and any local
						// mentioned-docs metadata don't linger.
						setMessages((prev) => prev.filter((m) => m.id !== userMsgId));
						setMessageDocumentsMap((prev) => {
							if (!(userMsgId in prev)) return prev;
							const { [userMsgId]: _removed, ...rest } = prev;
							return rest;
						});
					},
				});
			} finally {
				setIsRunning(false);
				abortControllerRef.current = null;
				if (currentThreadId) {
					void queryClient.invalidateQueries({
						queryKey: cacheKeys.threads.messages(currentThreadId),
					});
					void queryClient.invalidateQueries({
						queryKey: cacheKeys.threads.detail(currentThreadId),
					});
				}
			}
		},
		[
			threadId,
			workspaceId,
			messages,
			jotaiStore,
			mentionedDocuments,
			setMentionedDocuments,
			setMessageDocumentsMap,
			setAgentCreatedDocuments,
			queryClient,
			currentUser,
			localFilesystemEnabled,
			disabledTools,
			updateChatTabTitle,
			tokenUsageStore,
			pendingUserImageUrls,
			setPendingUserImageUrls,
			fetchWithTurnCancellingRetry,
			handleStreamTerminalError,
			handleChatFailure,
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
			if (pendingInterrupts.length === 0) return;
			// All cards in this turn share the same threadId/assistantMsgId
			// (they're siblings of one parent agent step), so reading from
			// the first entry is safe.
			const resumeThreadId = pendingInterrupts[0].threadId;
			// Destructured separately as ``let`` so the SSE
			// ``data-assistant-message-id`` handler (resume always
			// allocates a fresh server-side row) can rename it to
			// the canonical ``msg-{db_id}`` mid-stream.
			let assistantMsgId = pendingInterrupts[0].assistantMsgId;
			// Concatenate every card's tool-call ids in pendingInterrupts order;
			// this matches the ``decisions`` ordering produced by
			// ``handleApprovalSubmit`` and the backend slicer's traversal of
			// ``state.interrupts``.
			const allBundleToolCallIds = pendingInterrupts.flatMap((p) => p.bundleToolCallIds);
			setPendingInterrupts([]);
			stagedDecisionsByInterruptIdRef.current.clear();
			setIsRunning(true);

			const controller = new AbortController();
			abortControllerRef.current = controller;

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

			const existingMsg = messages.find((m) => m.id === assistantMsgId);
			if (existingMsg && Array.isArray(existingMsg.content)) {
				// See ``ContentPartsState.suppressStepSeparators`` doc.
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
								// argsText: assistant-ui prefers it over
								// JSON.stringify(args), so restoring it keeps
								// pretty-printed JSON across reloads.
								...(typeof p.argsText === "string" ? { argsText: p.argsText } : {}),
								...(typeof p.langchainToolCallId === "string"
									? { langchainToolCallId: p.langchainToolCallId }
									: {}),
								// metadata: spanId / thinkingStepId drive the
								// timeline's step↔tool join. Dropping these
								// here orphans every rehydrated tool-call.
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

			// Apply each decision to its own card by toolCallId so mixed
			// bundles (approve/edit/reject) and multi-edit bundles do not
			// collapse onto ``decisions[0]``. Cards outside the bundle are
			// untouched. Mirrors the host ``hitl-decision`` handler.
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
						// Sync argsText so the rendered card shows the
						// edited inputs (assistant-ui prefers it over
						// JSON.stringify(args)).
						part.argsText = JSON.stringify(mergedArgs, null, 2);
					}
					part.result = {
						...(part.result as Record<string, unknown>),
						__decided__: decided,
					};
				}
			}

			try {
				const selection = await getAgentFilesystemSelection(workspaceId, {
					localFilesystemEnabled,
				});
				const response = await fetchWithTurnCancellingRetry(() =>
					authenticatedFetch(buildBackendUrl(`/api/v1/threads/${resumeThreadId}/resume`), {
						method: "POST",
						headers: {
							"Content-Type": "application/json",
						},
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
					setMessages((prev) =>
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
									recentCancelRequestedAtRef.current = Date.now();
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
									targetTcId = freshSynthToolCallId(
										contentPartsState.toolCallIndices,
										action.name,
										i
									);
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
							setMessages((prev) =>
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
									setPendingInterrupts((prev) => {
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
								setMessages((prev) =>
									applyTurnIdToAssistantMessageList(prev, assistantMsgId, turnId)
								);
							}
							break;
						}

						case "data-assistant-message-id": {
							// Resume always allocates a fresh ``new_chat_messages``
							// row anchored to a new ``turn_id`` (the original
							// interrupted turn's row stays as-is), so this is a
							// real id swap. Rename the optimistic placeholder to
							// ``msg-{db_id}`` and reassign closure state. Resume
							// does NOT emit ``data-user-message-id`` — the user
							// row belongs to the original interrupted turn.
							const parsedMsg = readStreamedMessageId(parsed.data);
							if (!parsedMsg) break;
							const newAssistantMsgId = `msg-${parsedMsg.messageId}`;
							const oldAssistantMsgId = assistantMsgId;
							tokenUsageStore.rename(oldAssistantMsgId, newAssistantMsgId);
							setMessages((prev) =>
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

				// Server-authoritative persistence: ``stream_resume_chat``
				// finalises the assistant row in
				// ``finalize_assistant_turn`` from a shielded
				// ``finally`` block (covers both happy-path and
				// abort-mid-stream). FE has no remaining persistence
				// work here.
			} catch (error) {
				streamBatcher?.dispose();
				await handleStreamTerminalError({
					error,
					flow: "resume",
					threadId: resumeThreadId,
					assistantMsgId,
					accepted: resumeAccepted,
				});
			} finally {
				setIsRunning(false);
				abortControllerRef.current = null;
				void queryClient.invalidateQueries({
					queryKey: cacheKeys.threads.messages(resumeThreadId),
				});
				void queryClient.invalidateQueries({
					queryKey: cacheKeys.threads.detail(resumeThreadId),
				});
			}
		},
		[
			pendingInterrupts,
			messages,
			workspaceId,
			localFilesystemEnabled,
			disabledTools,
			queryClient,
			tokenUsageStore,
			fetchWithTurnCancellingRetry,
			handleStreamTerminalError,
		]
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
			if (!detail?.decisions || pendingInterrupts.length === 0) return;
			const incoming = detail.decisions;
			if (incoming.length === 0) return;
			// Concatenated tool-call ids across every pending card, in the
			// order ``handleApprovalSubmit`` produced ``incoming``.
			const tcIds = pendingInterrupts.flatMap((p) => p.bundleToolCallIds);
			const N = tcIds.length;

			// Refuse rather than silently broadcast or drop. The orchestrator
			// only fires ``hitl-decision`` once every pending card has
			// submitted, so a count mismatch indicates a contract drift
			// (and would later make the backend slicer raise).
			if (incoming.length !== N) {
				toast.error(
					`Cannot resume: ${incoming.length} decision(s) submitted for ${N} pending actions.`
				);
				return;
			}

			const byTcId = new Map<string, (typeof incoming)[number]>();
			const submittedDecisions: typeof incoming = [];
			for (let i = 0; i < tcIds.length; i++) {
				const tcId = tcIds[i];
				const decision = incoming[i];
				if (tcId === undefined || decision === undefined) {
					toast.error(
						`Cannot resume: ${incoming.length} decision(s) submitted for ${N} pending actions.`
					);
					return;
				}
				byTcId.set(tcId, decision);
				submittedDecisions.push(decision);
			}

			// All pending cards belong to the same assistant message, so a
			// single content-update pass suffices.
			const targetAssistantMsgId = pendingInterrupts[0].assistantMsgId;
			setMessages((prev) =>
				prev.map((m) => {
					if (m.id !== targetAssistantMsgId) return m;
					const parts = m.content as unknown as Array<Record<string, unknown>>;
					const newContent = parts.map((part) => {
						const tcId = part.toolCallId as string | undefined;
						const d = tcId ? byTcId.get(tcId) : undefined;
						if (!d || part.type !== "tool-call") return part;
						if (typeof part.result !== "object" || part.result === null) return part;
						if (!("__interrupt__" in (part.result as Record<string, unknown>))) return part;
						const decided = d.type;
						if (decided === "edit" && d.edited_action) {
							return {
								...part,
								args: d.edited_action.args,
								// Sync argsText so the card renders the edited
								// inputs (assistant-ui prefers it over JSON.stringify).
								argsText: JSON.stringify(d.edited_action.args, null, 2),
								result: {
									...(part.result as Record<string, unknown>),
									__decided__: decided,
								},
							};
						}
						return {
							...part,
							result: {
								...(part.result as Record<string, unknown>),
								__decided__: decided,
							},
						};
					});
					return { ...m, content: newContent as unknown as ThreadMessageLike["content"] };
				})
			);
			handleResume(submittedDecisions);
		};
		window.addEventListener("hitl-decision", handler);
		return () => window.removeEventListener("hitl-decision", handler);
	}, [handleResume, pendingInterrupts]);

	// Convert message (pass through since already in correct format)
	const convertMessage = useCallback(
		(message: ThreadMessageLike): ThreadMessageLike => message,
		[]
	);

	/**
	 * Handle regeneration (edit or reload) by calling the regenerate endpoint
	 * and streaming the response. This rewinds the LangGraph checkpointer state.
	 *
	 * @param newUserQuery - `null` = reload with same turn from the server. A string = edit
	 *   (including an empty string when the edited turn is images-only); pass `editExtras` for images/content.
	 */
	const handleRegenerate = useCallback(
		async (
			newUserQuery: string | null,
			editExtras?: {
				userMessageContent: ThreadMessageLike["content"];
				userImages: NewChatUserImagePayload[];
				sourceUserMessageId?: string;
			},
			editFromPosition?: {
				/** Message id (numeric, parsed from ``msg-<n>``) to rewind to. */
				fromMessageId?: number | null;
				/** When true, revert reversible downstream actions before stream. */
				revertActions?: boolean;
			}
		) => {
			if (!threadId) {
				toast.error("Cannot regenerate: no active chat thread");
				return;
			}

			const isEdit = newUserQuery !== null;

			// Abort any previous streaming request
			if (abortControllerRef.current) {
				abortControllerRef.current.abort();
				abortControllerRef.current = null;
			}

			// Extract the original user query BEFORE removing messages (for reload mode)
			let userQueryToDisplay: string | undefined;
			let originalUserMessageContent: ThreadMessageLike["content"] | null = null;
			let originalUserMessageMetadata: ThreadMessageLike["metadata"] | undefined;
			let sourceUserMessageId: string | undefined = editExtras?.sourceUserMessageId;

			if (!isEdit) {
				// Reload mode - find and preserve the last user message content
				const lastUserMessage = [...messages].reverse().find((m) => m.role === "user");
				if (lastUserMessage) {
					sourceUserMessageId = lastUserMessage.id;
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
			} else {
				userQueryToDisplay = newUserQuery;
			}

			// Start streaming
			setIsRunning(true);
			const controller = new AbortController();
			abortControllerRef.current = controller;

			// Add placeholder user message if we have a new query (edit mode).
			// Mutable for the same reason as in ``onNew`` — both ids are
			// renamed mid-stream by the new ``data-user-message-id`` /
			// ``data-assistant-message-id`` SSE handlers below.
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

			// Add placeholder messages to UI
			// Always add back the user message (with new query for edit, or original content for reload)
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
				const selection = await getAgentFilesystemSelection(workspaceId, {
					localFilesystemEnabled,
				});
				// Partition the source mentions back into doc/folder id buckets
				// so the regenerate route can pass them to ``stream_new_chat``
				// and the priority middleware sees the same ``[USER-MENTIONED]``
				// priority entries the original turn did. Without this partition
				// the regenerate flow silently dropped the agent's mention
				// awareness — same architectural bug we fixed on the new-chat path.
				const regenerateDocIds = sourceMentionedDocs
					.filter((d) => d.kind === "doc")
					.map((d) => d.id);
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
					// Full mention metadata for the regenerate-specific
					// source list. Only meaningful for edit (the BE only
					// re-persists a user row when ``user_query`` is set);
					// reload reuses the original turn's mentioned_documents.
					mentioned_documents: sourceMentionedDocs.length > 0 ? sourceMentionedDocs : undefined,
				};
				if (isEdit) {
					requestBody.user_images = editExtras?.userImages ?? [];
				}
				// Explicit edit-from-arbitrary-position. Only send
				// ``from_message_id`` / ``revert_actions`` when the
				// caller asked for them; otherwise the backend keeps the
				// legacy "last 2 messages" behaviour for back-compat.
				if (editFromPosition?.fromMessageId != null) {
					requestBody.from_message_id = editFromPosition.fromMessageId;
					if (editFromPosition.revertActions) {
						requestBody.revert_actions = true;
					}
				}
				const response = await fetchWithTurnCancellingRetry(() =>
					authenticatedFetch(getRegenerateUrl(threadId), {
						method: "POST",
						headers: {
							"Content-Type": "application/json",
						},
						body: JSON.stringify(requestBody),
						signal: controller.signal,
					})
				);

				if (!response.ok) {
					throw await toHttpResponseError(response);
				}
				regenerateAccepted = true;

				// Only switch UI to regenerated placeholder messages after the backend accepts
				// regenerate. This avoids local message loss when regenerate fails early (e.g. 400).
				//
				// When an explicit ``editFromPosition.fromMessageId`` is passed, slice from
				// that message forward so edit-from-arbitrary-position drops every downstream
				// message; otherwise fall back to the legacy "drop the last 2" behaviour.
				setMessages((prev) => {
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
					setMessageDocumentsMap((prev) => ({
						...prev,
						[userMsgId]: sourceMentionedDocs,
					}));
				}

				const flushMessages = () => {
					setMessages((prev) =>
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
									recentCancelRequestedAtRef.current = Date.now();
								}
							},
						})
					) {
						return;
					}
					switch (parsed.type) {
						case "data-action-log": {
							if (threadId !== null) {
								applyActionLogSse(queryClient, threadId, workspaceId, parsed.data);
							}
							break;
						}

						case "data-action-log-updated": {
							if (threadId !== null) {
								applyActionLogUpdatedSse(
									queryClient,
									threadId,
									parsed.data.id,
									parsed.data.reversible
								);
							}
							break;
						}

						case "data-turn-info": {
							const turnId = readStreamedChatTurnId(parsed.data);
							if (turnId) {
								setMessages((prev) =>
									applyTurnIdToAssistantMessageList(prev, assistantMsgId, turnId)
								);
							}
							break;
						}

						case "data-user-message-id": {
							// Same role as in ``onNew`` but the regenerate-specific
							// mention metadata (``sourceMentionedDocs``) is the
							// list to migrate onto the canonical id key.
							const parsedMsg = readStreamedMessageId(parsed.data);
							if (!parsedMsg) break;
							const newUserMsgId = `msg-${parsedMsg.messageId}`;
							const oldUserMsgId = userMsgId;
							setMessages((prev) =>
								prev.map((m) =>
									m.id === oldUserMsgId
										? mergeChatTurnIdIntoMessage({ ...m, id: newUserMsgId }, parsedMsg.turnId)
										: m
								)
							);
							if (sourceMentionedDocs.length > 0) {
								setMessageDocumentsMap((prev) => {
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
							setMessages((prev) =>
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
							// failureCount must include every "not undone" bucket
							// (not_reversible, permission_denied, failed) so the
							// toast's "X could not be rolled back" math matches
							// the response invariant ``total === sum(counters)``.
							// ``skipped`` rows are batch revert artefacts (revert
							// rows themselves) and are not user-facing failures.
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
							if (threadId !== null) {
								for (const r of summary.results) {
									if (r.status === "reverted" || r.status === "already_reverted") {
										markActionRevertedInCache(
											queryClient,
											threadId,
											r.action_id,
											r.new_action_id ?? null
										);
									}
								}
							}
							break;
						}
					}
				});

				batcher.flush();

				// Server-authoritative persistence: ``stream_new_chat``
				// (regenerate flow) wrote the user row in
				// ``persist_user_turn`` and finalises the assistant row
				// in ``finalize_assistant_turn`` from a shielded
				// ``finally`` block (covers both happy-path and
				// abort-mid-stream). FE only needs to track the
				// successful response here.
				if (contentParts.length > 0) {
					trackChatResponseReceived(workspaceId, threadId);
				}
			} catch (error) {
				streamBatcher?.dispose();
				await handleStreamTerminalError({
					error,
					flow: "regenerate",
					threadId,
					assistantMsgId,
					accepted: regenerateAccepted,
				});
			} finally {
				setIsRunning(false);
				abortControllerRef.current = null;
				void queryClient.invalidateQueries({
					queryKey: cacheKeys.threads.messages(threadId),
				});
				void queryClient.invalidateQueries({
					queryKey: cacheKeys.threads.detail(threadId),
				});
			}
		},
		[
			threadId,
			workspaceId,
			messages,
			disabledTools,
			localFilesystemEnabled,
			messageDocumentsMap,
			setMessageDocumentsMap,
			queryClient,
			tokenUsageStore,
			fetchWithTurnCancellingRetry,
			handleStreamTerminalError,
		]
	);

	// Handle editing a message - truncates history and regenerates with new query.
	//
	// When ``message.sourceId`` is set (the assistant-ui way to say
	// "this edit replaces an older message"), we pin
	// ``from_message_id`` so the backend rewinds to the right LangGraph
	// checkpoint instead of relying on the legacy "last 2 messages"
	// rewind. We also count downstream reversible actions and prompt the
	// user to revert / continue / cancel before regenerating.
	const onEdit = useCallback(
		async (message: AppendMessage) => {
			const { userQuery, userImages } = extractUserTurnForNewChatApi(message, []);
			const queryForApi = userQuery.trim();
			if (!queryForApi && userImages.length === 0) {
				toast.error("Cannot edit with empty message");
				return;
			}

			const userMessageContent = message.content as unknown as ThreadMessageLike["content"];

			// ``sourceId`` per @assistant-ui/core's ``AppendMessage`` is
			// "the ID of the message that was edited". Parse the numeric
			// suffix so we can map it back to a DB row.
			const sourceId = (message as { sourceId?: string }).sourceId;
			const fromMessageId =
				sourceId && /^msg-\d+$/.test(sourceId)
					? Number.parseInt(sourceId.replace(/^msg-/, ""), 10)
					: null;

			if (fromMessageId == null) {
				// No source id (or non-DB id) — fall back to today's
				// last-2 behaviour. The user gets the legacy edit flow.
				await handleRegenerate(queryForApi, {
					userMessageContent,
					userImages,
					sourceUserMessageId: sourceId,
				});
				return;
			}

			// Pre-flight: count reversible downstream actions so we can
			// auto-skip the dialog for harmless edits.
			//
			// "Downstream" means messages AFTER the edited one. The
			// previous slice ``messages.slice(editedIndex)`` included
			// the edited message itself in both the total
			// count and the reversibility scan (any actions on the
			// edited turn would be double-counted). Slice from
			// ``editedIndex + 1`` so the dialog text matches reality:
			// "N downstream messages will be dropped".
			const editedIndex = messages.findIndex((m) => m.id === `msg-${fromMessageId}`);
			let downstreamReversibleCount = 0;
			let downstreamTotalCount = 0;
			if (editedIndex >= 0) {
				const downstream = messages.slice(editedIndex + 1);
				downstreamTotalCount = downstream.length;
				const seenTurns = new Set<string>();
				const downstreamTurnIds = new Set<string>();
				for (const m of downstream) {
					const meta = (m.metadata ?? {}) as { custom?: { chatTurnId?: string } };
					const tid = meta.custom?.chatTurnId;
					if (!tid || seenTurns.has(tid)) continue;
					seenTurns.add(tid);
					downstreamTurnIds.add(tid);
				}
				// Source of truth: the unified react-query cache. Every
				// action whose ``chat_turn_id`` belongs to the slice we're
				// about to drop counts toward the prompt.
				for (const a of agentActionItems) {
					if (!a.chat_turn_id || !downstreamTurnIds.has(a.chat_turn_id)) continue;
					if (
						a.reversible &&
						(a.reverted_by_action_id === null || a.reverted_by_action_id === undefined) &&
						!a.is_revert_action &&
						(a.error === null || a.error === undefined)
					) {
						downstreamReversibleCount += 1;
					}
				}
			}

			if (downstreamReversibleCount === 0) {
				// Nothing to revert — submit silently.
				await handleRegenerate(
					queryForApi,
					{ userMessageContent, userImages, sourceUserMessageId: sourceId },
					{ fromMessageId, revertActions: false }
				);
				return;
			}

			setEditDialogState({
				fromMessageId,
				userQuery: queryForApi,
				userMessageContent,
				userImages,
				downstreamReversibleCount,
				downstreamTotalCount,
			});
		},
		[handleRegenerate, messages, agentActionItems]
	);

	const handleApprovalSubmit = useCallback(
		(interruptId: string, decisions: HitlDecision[]) => {
			// Stage this card's decisions; only fire the resume once every
			// pending card in the current turn has submitted, so the
			// backend slicer sees a single concatenated decisions list
			// whose total matches the parent state's pending action count.
			stagedDecisionsByInterruptIdRef.current.set(interruptId, decisions);
			if (stagedDecisionsByInterruptIdRef.current.size < pendingInterrupts.length) {
				return;
			}
			const ordered: HitlDecision[] = [];
			for (const pi of pendingInterrupts) {
				const staged = stagedDecisionsByInterruptIdRef.current.get(pi.interruptId);
				if (!staged) {
					// Defensive: a missing entry means the staging map and
					// the pending list disagreed for one cycle. Bail rather
					// than dispatch a count-mismatched batch.
					return;
				}
				ordered.push(...staged);
			}
			stagedDecisionsByInterruptIdRef.current.clear();
			window.dispatchEvent(new CustomEvent("hitl-decision", { detail: { decisions: ordered } }));
		},
		[pendingInterrupts]
	);

	const handleEditDialogChoice = useCallback(
		async (choice: EditMessageDialogChoice) => {
			const pending = editDialogState;
			if (!pending) return;
			setEditDialogState(null);
			if (choice === "cancel") return;
			await handleRegenerate(
				pending.userQuery,
				{
					userMessageContent: pending.userMessageContent,
					userImages: pending.userImages,
					sourceUserMessageId: `msg-${pending.fromMessageId}`,
				},
				{
					fromMessageId: pending.fromMessageId,
					revertActions: choice === "revert",
				}
			);
		},
		[editDialogState, handleRegenerate]
	);

	// Handle reloading/refreshing the last AI response
	const onReload = useCallback(async () => {
		// parentId is the ID of the message to reload from (the user message)
		// We call regenerate without a query to use the same query
		await handleRegenerate(null);
	}, [handleRegenerate]);

	// Surface the thread's deliverables to the layout-level artifacts sidebar.
	useSyncChatArtifacts(messages);

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

	const threadLoadError = activeThreadId
		? (threadDetailQuery.error ?? threadMessagesQuery.error)
		: null;
	const shouldShowThreadLoadError =
		!!threadLoadError && !!activeThreadId && !currentThread && messages.length === 0;
	const isThreadMessagesLoading =
		!!activeThreadId &&
		threadMessagesQuery.isPending &&
		messages.length === 0 &&
		!threadMessagesQuery.error;

	if (shouldShowThreadLoadError) {
		return (
			<div className="flex h-full flex-col items-center justify-center gap-4">
				<div className="text-destructive">Failed to load chat</div>
				<Button
					type="button"
					onClick={() => {
						void Promise.all([threadDetailQuery.refetch(), threadMessagesQuery.refetch()]);
					}}
				>
					Try Again
				</Button>
			</div>
		);
	}

	return (
		<TokenUsageProvider store={tokenUsageStore}>
			<AssistantRuntimeProvider runtime={runtime}>
				<TimelineDataUI />
				<StepSeparatorDataUI />
				<PendingInterruptProvider
					pendingInterrupts={pendingInterrupts}
					onSubmit={handleApprovalSubmit}
				>
					<div key={workspaceId} className="flex h-full overflow-hidden">
						<div className="relative flex-1 flex flex-col min-w-0 overflow-hidden">
							<Thread hasActiveThread={!!activeThreadId} />
							{isThreadMessagesLoading ? (
								<div className="absolute inset-0 z-10 bg-panel">
									<ThreadMessagesSkeleton />
								</div>
							) : null}
						</div>
						<MobileReportPanel />
						<MobileEditorPanel />
						<MobileHitlEditPanel />
						<MobileArtifactsPanel />
					</div>
				</PendingInterruptProvider>
				<EditMessageDialog
					open={editDialogState !== null}
					onOpenChange={(open) => {
						if (!open) setEditDialogState(null);
					}}
					downstreamReversibleCount={editDialogState?.downstreamReversibleCount ?? 0}
					downstreamTotalCount={editDialogState?.downstreamTotalCount ?? 0}
					onChoose={handleEditDialogChoice}
				/>
			</AssistantRuntimeProvider>
		</TokenUsageProvider>
	);
}
