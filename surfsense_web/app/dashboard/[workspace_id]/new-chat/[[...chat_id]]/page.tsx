"use client";

import {
	type AppendMessage,
	AssistantRuntimeProvider,
	type ThreadMessageLike,
	useExternalStoreRuntime,
} from "@assistant-ui/react";
import { useQueryClient } from "@tanstack/react-query";
import { useAtomValue, useSetAtom } from "jotai";
import dynamic from "next/dynamic";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import {
	clearTargetCommentIdAtom,
	currentThreadAtom,
	setCurrentThreadMetadataAtom,
	setTargetCommentIdAtom,
} from "@/atoms/chat/current-thread.atom";
import {
	type MentionedDocumentInfo,
	mentionedDocumentsAtom,
	messageDocumentsMapAtom,
} from "@/atoms/chat/mentioned-documents.atom";
import { clearPlanOwnerRegistry } from "@/atoms/chat/plan-state.atom";
import { closeReportPanelAtom } from "@/atoms/chat/report-panel.atom";
import { closeEditorPanelAtom } from "@/atoms/editor/editor-panel.atom";
import { membersAtom } from "@/atoms/members/members-query.atoms";
import { removeChatTabAtom, syncChatTabAtom } from "@/atoms/tabs/tabs.atom";
import {
	EditMessageDialog,
	type EditMessageDialogChoice,
} from "@/components/assistant-ui/edit-message-dialog";
import { StepSeparatorDataUI } from "@/components/assistant-ui/step-separator";
import { Thread } from "@/components/assistant-ui/thread";
import {
	type TokenUsageData,
	TokenUsageProvider,
} from "@/components/assistant-ui/token-usage-context";
import { Button } from "@/components/ui/button";
import { useSyncChatArtifacts } from "@/features/chat-artifacts";
import {
	type HitlDecision,
	PendingInterruptProvider,
	type PendingInterruptState,
} from "@/features/chat-messages/hitl";
import { TimelineDataUI } from "@/features/chat-messages/timeline";
import { useAgentActionsQuery } from "@/hooks/use-agent-actions-query";
import { useChatSessionStateSync } from "@/hooks/use-chat-session-state";
import { useMessagesSync } from "@/hooks/use-messages-sync";
import { useThreadDetail, useThreadMessages } from "@/hooks/use-thread-queries";
import { documentsApiService } from "@/lib/apis/documents-api.service";
import {
	convertToThreadMessage,
	reconcileInterruptedAssistantMessages,
} from "@/lib/chat/message-utils";
import {
	cancelActiveTurn,
	type EngineContext,
	regenerateChat,
	resumeChat,
	startNewChat,
} from "@/lib/chat/stream-engine/engine";
import { extractMentionedDocuments } from "@/lib/chat/stream-engine/helpers";
import { chatStreamStore } from "@/lib/chat/stream-engine/store";
import { useChatStream } from "@/lib/chat/stream-engine/use-chat-stream";
import type { ThreadRecord } from "@/lib/chat/thread-persistence";
import {
	extractUserTurnForNewChatApi,
	type NewChatUserImagePayload,
} from "@/lib/chat/user-turn-api-parts";
import { NotFoundError } from "@/lib/error";

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

/** Stable empty reference so idle threads don't re-render the interrupt provider. */
const EMPTY_PENDING_INTERRUPTS: PendingInterruptState[] = [];
const EMPTY_MESSAGES: ThreadMessageLike[] = [];

function parseUrlChatId(id: string | string[] | undefined): number {
	let parsed = 0;
	if (Array.isArray(id) && id.length > 0) {
		parsed = Number.parseInt(id[0], 10);
	} else if (typeof id === "string") {
		parsed = Number.parseInt(id, 10);
	}
	return Number.isNaN(parsed) ? 0 : parsed;
}

export default function NewChatPage() {
	const params = useParams();
	const queryClient = useQueryClient();
	const urlChatId = useMemo(() => parseUrlChatId(params.chat_id), [params.chat_id]);
	const [threadId, setThreadId] = useState<number | null>(() => (urlChatId > 0 ? urlChatId : null));
	const activeThreadId = urlChatId > 0 ? urlChatId : threadId;
	const handledLoadErrorThreadRef = useRef<number | null>(null);
	const [currentThread, setCurrentThread] = useState<ThreadRecord | null>(null);
	// DB-hydrated messages for the viewed thread (idle display). While a turn
	// is streaming, the live overlay in ``chatStreamStore`` takes precedence
	// (see ``displayMessages``) so it survives this page unmounting on nav.
	const [messages, setMessages] = useState<ThreadMessageLike[]>([]);

	// Durable, cross-navigation streaming state for the viewed thread.
	const streamState = useChatStream(activeThreadId);
	const isRunning = streamState?.isRunning ?? false;
	const pendingInterrupts = streamState?.pendingInterrupts ?? EMPTY_PENDING_INTERRUPTS;
	// Live overlay while a turn is streaming / awaiting HITL; DB-hydrated
	// messages once the overlay is cleared (the hydration effect drops it only
	// after the DB catches up, so there is no finish->refetch gap).
	const displayMessages = streamState ? streamState.messages : messages;

	// One shared token-usage store, alive across navigation.
	const tokenUsageStore = chatStreamStore.tokenUsage;

	const setMessageDocumentsMap = useSetAtom(messageDocumentsMapAtom);
	const setMentionedDocuments = useSetAtom(mentionedDocumentsAtom);
	const currentThreadState = useAtomValue(currentThreadAtom);
	const setCurrentThreadMetadata = useSetAtom(setCurrentThreadMetadataAtom);
	const setTargetCommentId = useSetAtom(setTargetCommentIdAtom);
	const clearTargetCommentId = useSetAtom(clearTargetCommentIdAtom);
	const closeReportPanel = useSetAtom(closeReportPanelAtom);
	const closeEditorPanel = useSetAtom(closeEditorPanelAtom);
	const syncChatTab = useSetAtom(syncChatTabAtom);
	const removeChatTab = useSetAtom(removeChatTabAtom);

	// Edit dialog state. Holds the message id being edited and the (already
	// extracted) regenerate args so we can resume the edit after the user picks
	// "revert all" / "continue" / "cancel".
	const [editDialogState, setEditDialogState] = useState<{
		fromMessageId: number;
		userQuery: string | null;
		userMessageContent: ThreadMessageLike["content"];
		userImages: NewChatUserImagePayload[];
		downstreamReversibleCount: number;
		downstreamTotalCount: number;
	} | null>(null);

	// Per-card staged decisions held until every pending card has submitted, at
	// which point we batch them into one ``hitl-decision`` event in the same
	// order as ``pendingInterrupts``. A ref because partial progress should not
	// re-render the page.
	const stagedDecisionsByInterruptIdRef = useRef<Map<string, HitlDecision[]>>(new Map());

	const threadDetailQuery = useThreadDetail(activeThreadId);
	const threadMessagesQuery = useThreadMessages(activeThreadId);
	const hydratedMessagesRef = useRef<{
		threadId: number | null;
		data: typeof threadMessagesQuery.data;
	}>({ threadId: null, data: undefined });
	const hasLiveStream = !!streamState && streamState.messages.length > 0;
	const isActiveThreadHydrated = hydratedMessagesRef.current.threadId === activeThreadId;
	const shouldHideStaleMessages = !!activeThreadId && !hasLiveStream && !isActiveThreadHydrated;
	const isThreadMessagesLoading =
		shouldHideStaleMessages && !threadMessagesQuery.error;
	const runtimeMessages = shouldHideStaleMessages ? EMPTY_MESSAGES : displayMessages;

	// Live collaboration: sync session state and messages via Zero. Kept on the
	// page because "AI responding" reflects the currently-viewed thread.
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

	// Unified store for agent-action rows (react-query cache). Used by the
	// edit pre-flight to count reversible downstream actions.
	const { items: agentActionItems } = useAgentActionsQuery(activeThreadId);

	// Latest displayed messages, read by the engine wrappers at call time so
	// history/slice seeds stay fresh without re-creating the callbacks.
	const messagesRef = useRef<ThreadMessageLike[]>(runtimeMessages);
	messagesRef.current = runtimeMessages;

	const buildCtx = useCallback(
		(): EngineContext => ({
			workspaceId,
			threadId: activeThreadId,
			priorMessages: messagesRef.current,
			view: { setThreadId, setCurrentThread },
		}),
		[workspaceId, activeThreadId]
	);

	// Reset thread-local runtime state on route/workspace changes. The durable
	// streaming overlay is preserved for any still-running thread (and the newly
	// viewed thread) via ``clearInactive`` so an in-flight turn survives nav.
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
		chatStreamStore.clearInactive(nextThreadId);
	}, [
		urlChatId,
		setMentionedDocuments,
		setMessageDocumentsMap,
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
				workspaceId: thread.workspace_id ?? workspaceId,
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

		// Per-thread gate: never overwrite the live overlay of a running turn.
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

		// The DB is now authoritative for this thread — drop the streaming
		// overlay so we render DB messages (no-op while running / HITL-pending).
		if (loadedMessages.length >= chatStreamStore.getMessages(activeThreadId).length) {
			chatStreamStore.clear(activeThreadId);
		}
	}, [
		activeThreadId,
		isRunning,
		messages.length,
		setMessageDocumentsMap,
		threadMessagesQuery.data,
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

	// Prefetch document titles for @ mention picker so data is ready on type.
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

	// Handle scroll to comment from URL query params (e.g., from inbox click).
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

		window.addEventListener("popstate", readAndApplyCommentId);

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

	// Handle new message from user
	const onNew = useCallback(
		(message: AppendMessage) => {
			if (isThreadMessagesLoading) return Promise.resolve();
			return startNewChat(buildCtx(), message);
		},
		[buildCtx, isThreadMessagesLoading]
	);

	// Cancel the in-flight turn (targets the active stream's owner thread).
	const onCancel = useCallback(async () => {
		await cancelActiveTurn();
	}, []);

	// Convert message (pass through since already in correct format)
	const convertMessage = useCallback(
		(message: ThreadMessageLike): ThreadMessageLike => message,
		[]
	);

	// Handle editing a message - truncates history and regenerates with new
	// query. When ``message.sourceId`` is set we pin ``from_message_id`` so the
	// backend rewinds to the right checkpoint, and prompt the user to revert /
	// continue / cancel before regenerating.
	const onEdit = useCallback(
		async (message: AppendMessage) => {
			const { userQuery, userImages } = extractUserTurnForNewChatApi(message, []);
			const queryForApi = userQuery.trim();
			if (!queryForApi && userImages.length === 0) {
				toast.error("Cannot edit with empty message");
				return;
			}

			const userMessageContent = message.content as unknown as ThreadMessageLike["content"];

			const sourceId = (message as { sourceId?: string }).sourceId;
			const fromMessageId =
				sourceId && /^msg-\d+$/.test(sourceId)
					? Number.parseInt(sourceId.replace(/^msg-/, ""), 10)
					: null;

			if (fromMessageId == null) {
				await regenerateChat(buildCtx(), queryForApi, {
					userMessageContent,
					userImages,
					sourceUserMessageId: sourceId,
				});
				return;
			}

			const msgs = messagesRef.current;
			const editedIndex = msgs.findIndex((m) => m.id === `msg-${fromMessageId}`);
			let downstreamReversibleCount = 0;
			let downstreamTotalCount = 0;
			if (editedIndex >= 0) {
				const downstream = msgs.slice(editedIndex + 1);
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
				await regenerateChat(
					buildCtx(),
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
		[buildCtx, agentActionItems]
	);

	const handleApprovalSubmit = useCallback(
		(interruptId: string, decisions: HitlDecision[]) => {
			// Stage this card's decisions; only fire the resume once every pending
			// card in the current turn has submitted, so the backend slicer sees a
			// single concatenated decisions list.
			stagedDecisionsByInterruptIdRef.current.set(interruptId, decisions);
			if (stagedDecisionsByInterruptIdRef.current.size < pendingInterrupts.length) {
				return;
			}
			const ordered: HitlDecision[] = [];
			for (const pi of pendingInterrupts) {
				const staged = stagedDecisionsByInterruptIdRef.current.get(pi.interruptId);
				if (!staged) {
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
			await regenerateChat(
				buildCtx(),
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
		[editDialogState, buildCtx]
	);

	// Handle reloading/refreshing the last AI response
	const onReload = useCallback(async () => {
		await regenerateChat(buildCtx(), null);
	}, [buildCtx]);

	// HITL resume bridge. Submit always happens from this page's approval UI, so
	// the currently-viewed thread owns the pending interrupts. Applies each
	// decision to its card, then resumes the (durable) stream.
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
			const tcIds = pendingInterrupts.flatMap((p) => p.bundleToolCallIds);
			const N = tcIds.length;

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

			const targetAssistantMsgId = pendingInterrupts[0].assistantMsgId;
			if (activeThreadId != null) {
				chatStreamStore.setMessages(activeThreadId, (prev) =>
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
			}
			void resumeChat(buildCtx(), submittedDecisions);
		};
		window.addEventListener("hitl-decision", handler);
		return () => window.removeEventListener("hitl-decision", handler);
	}, [buildCtx, pendingInterrupts, activeThreadId]);

	// Surface the thread's deliverables to the layout-level artifacts sidebar.
	useSyncChatArtifacts(runtimeMessages);

	// Create external store runtime
	const runtime = useExternalStoreRuntime({
		messages: runtimeMessages,
		isRunning,
		onNew,
		onEdit,
		onReload,
		convertMessage,
		onCancel,
	});

	const threadLoadError = activeThreadId
		? (threadDetailQuery.error ?? threadMessagesQuery.error)
		: null;
	const shouldShowThreadLoadError =
		!!threadLoadError && !!activeThreadId && !currentThread && runtimeMessages.length === 0;

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
							<Thread
								hasActiveThread={!!activeThreadId}
								isLoadingMessages={isThreadMessagesLoading}
							/>
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
