"use client";

import { atom } from "jotai";

/**
 * Minimal per-row projection of ``AgentActionLog`` that the tool card
 * needs to decide whether to render a Revert button.
 *
 * Fields are deliberately a subset of the full ``AgentAction`` so the
 * SSE side-channel (``data-action-log`` / ``data-action-log-updated``)
 * can populate them without depending on the REST endpoint
 * ``GET /threads/.../actions`` (which 503s when
 * ``SURFSENSE_ENABLE_ACTION_LOG`` is off).
 */
export interface AgentActionLite {
	id: number;
	threadId: number | null;
	lcToolCallId: string | null;
	chatTurnId: string | null;
	toolName: string;
	reversible: boolean;
	reverseDescriptorPresent: boolean;
	error: boolean;
	revertedByActionId: number | null;
	isRevertAction: boolean;
	createdAt: string | null;
}

/**
 * Map keyed off the LangChain ``tool_call.id`` (mirrors ``ContentPart
 * tool-call.langchainToolCallId``).
 */
export const agentActionByLcIdAtom = atom<Map<string, AgentActionLite>>(new Map());

/**
 * Parallel map keyed off the synthetic chat-card ``toolCallId``
 * (``call_<run-id>``) so ``ToolFallback`` (which only receives the
 * synthetic id from assistant-ui) can join its card to the action log.
 *
 * Both maps are kept in sync by ``upsertAgentActionAtom``.
 */
export const agentActionByToolCallIdAtom = atom<Map<string, AgentActionLite>>(new Map());

/**
 * Index keyed by ``chat_turn_id`` so the per-turn revert UI can answer
 * "how many reversible actions does this assistant turn contain?" in
 * O(1). Each entry's array is ordered by insertion (which
 * for a single turn matches ``created_at`` because action-log writes
 * happen synchronously).
 */
export const agentActionsByChatTurnIdAtom = atom<Map<string, AgentActionLite[]>>(new Map());

/**
 * Action to upsert one ``AgentActionLite`` row.
 *
 * ``toolCallId`` is the synthetic card id (``call_<run-id>`` from
 * ``stream_new_chat.py``). When provided alongside ``lcToolCallId``, the
 * action is indexed under BOTH ids so the tool card can perform the
 * lookup without going via the streaming state.
 */
export const upsertAgentActionAtom = atom(
	null,
	(_get, set, payload: { action: AgentActionLite; toolCallId?: string | null }) => {
		const { action, toolCallId } = payload;
		const upsertInto = (
			prev: Map<string, AgentActionLite>,
			key: string
		): Map<string, AgentActionLite> => {
			const next = new Map(prev);
			const existing = next.get(key);
			next.set(key, {
				...action,
				// Preserve the local "reverted" bookkeeping if a reversibility
				// flip arrives AFTER the user already reverted via the REST
				// route. We never want a stale ``reversible=true`` event to
				// resurrect a Reverted card.
				revertedByActionId: existing?.revertedByActionId ?? action.revertedByActionId,
				isRevertAction: existing?.isRevertAction ?? action.isRevertAction,
			});
			return next;
		};
		if (action.lcToolCallId) {
			set(agentActionByLcIdAtom, (prev) => upsertInto(prev, action.lcToolCallId as string));
		}
		if (toolCallId) {
			set(agentActionByToolCallIdAtom, (prev) => upsertInto(prev, toolCallId));
		}
		if (action.chatTurnId) {
			set(agentActionsByChatTurnIdAtom, (prev) => {
				const next = new Map(prev);
				const turnId = action.chatTurnId as string;
				const existing = next.get(turnId) ?? [];
				const priorEntry = existing.find((row) => row.id === action.id);
				const merged: AgentActionLite = {
					...action,
					revertedByActionId: priorEntry?.revertedByActionId ?? action.revertedByActionId,
					isRevertAction: priorEntry?.isRevertAction ?? action.isRevertAction,
				};
				const others = existing.filter((row) => row.id !== action.id);
				next.set(turnId, [...others, merged]);
				return next;
			});
		}
	}
);

function mutateById(
	prev: Map<string, AgentActionLite>,
	id: number,
	mutator: (entry: AgentActionLite) => AgentActionLite
): Map<string, AgentActionLite> {
	let mutated = false;
	const next = new Map(prev);
	for (const [key, value] of next) {
		if (value.id === id) {
			next.set(key, mutator(value));
			mutated = true;
		}
	}
	return mutated ? next : prev;
}

function mutateByIdInTurnIndex(
	prev: Map<string, AgentActionLite[]>,
	id: number,
	mutator: (entry: AgentActionLite) => AgentActionLite
): Map<string, AgentActionLite[]> {
	let mutated = false;
	const next = new Map(prev);
	for (const [key, list] of next) {
		let listMutated = false;
		const updated = list.map((row) => {
			if (row.id === id) {
				listMutated = true;
				return mutator(row);
			}
			return row;
		});
		if (listMutated) {
			next.set(key, updated);
			mutated = true;
		}
	}
	return mutated ? next : prev;
}

/**
 * Action to flip an existing entry's ``reversible`` flag, keyed by the
 * AgentActionLog row id (the SSE ``data-action-log-updated`` payload
 * does NOT carry ``lcToolCallId``).
 */
export const updateAgentActionReversibleAtom = atom(
	null,
	(_get, set, payload: { id: number; reversible: boolean }) => {
		const apply = (entry: AgentActionLite): AgentActionLite => ({
			...entry,
			reversible: payload.reversible,
		});
		set(agentActionByLcIdAtom, (prev) => mutateById(prev, payload.id, apply));
		set(agentActionByToolCallIdAtom, (prev) => mutateById(prev, payload.id, apply));
		set(agentActionsByChatTurnIdAtom, (prev) => mutateByIdInTurnIndex(prev, payload.id, apply));
	}
);

/** Action to mark an existing entry as reverted (post-revert call). */
export const markAgentActionRevertedAtom = atom(
	null,
	(_get, set, payload: { id: number; newActionId: number | null }) => {
		const apply = (entry: AgentActionLite): AgentActionLite => ({
			...entry,
			revertedByActionId: payload.newActionId ?? -1,
		});
		set(agentActionByLcIdAtom, (prev) => mutateById(prev, payload.id, apply));
		set(agentActionByToolCallIdAtom, (prev) => mutateById(prev, payload.id, apply));
		set(agentActionsByChatTurnIdAtom, (prev) => mutateByIdInTurnIndex(prev, payload.id, apply));
	}
);

/** Mark every action in a turn as reverted, given a list of (id, newActionId) pairs. */
export const markAgentActionsRevertedBatchAtom = atom(
	null,
	(_get, set, payload: { entries: Array<{ id: number; newActionId: number | null }> }) => {
		for (const entry of payload.entries) {
			set(markAgentActionRevertedAtom, entry);
		}
	}
);

/** Reset all maps (e.g. when the active thread changes). */
export const resetAgentActionMapAtom = atom(null, (_get, set) => {
	set(agentActionByLcIdAtom, new Map());
	set(agentActionByToolCallIdAtom, new Map());
	set(agentActionsByChatTurnIdAtom, new Map());
});
