"use client";

import { useAuiState } from "@assistant-ui/react";
import { useAtomValue } from "jotai";
import { useMemo } from "react";
import { chatSessionStateAtom } from "@/atoms/chat/chat-session-state.atom";
import { useAgentActionsQuery } from "@/hooks/use-agent-actions-query";

/**
 * Resolve the ``AgentActionLog`` row for a given tool-call card. Tries
 * three lookup strategies, in priority order, against the unified
 * ``useAgentActionsQuery`` cache (the same react-query cache the
 * agent-actions sheet consumes — keeps the card and the sheet in
 * lockstep across reload, navigation, live stream, post-stream
 * reversibility flips, and explicit revert clicks).
 *
 * **Tier 1+2 — direct id match (O(1) Map):**
 *   - ``a.tool_call_id === toolCallId`` — hits when the model streamed
 *     ``tool_call_chunks`` so the card id matches the LangChain id.
 *   - ``a.tool_call_id === langchainToolCallId`` — synthetic card id
 *     is ``call_<run_id>`` and the LangChain id was backfilled by
 *     ``tool-output-available``.
 *
 * **Tier 3 — position-within-turn fallback:** only kicks in when the
 *   card has a synthetic ``call_<run_id>`` id AND no
 *   ``langchainToolCallId`` was ever backfilled (tool emitted as a
 *   single non-chunked payload AND streaming pre-dated the
 *   ``on_tool_end`` backfill, e.g. older threads).
 *
 * Returns ``null`` if no row matches OR if there's no thread context.
 *
 * Performance note: ``useAuiState`` returns a PRIMITIVE
 * (``positionInTurn`` is a number; ``chatTurnId`` is a string) so the
 * hook's ``Object.is`` short-circuit prevents re-renders on every
 * text-delta of every other part in the same message during streaming.
 * (See Vercel React rule ``rerender-defer-reads``.)
 */
export function useToolAction({
	toolCallId,
	toolName,
	langchainToolCallId,
}: {
	toolCallId: string;
	toolName: string;
	langchainToolCallId?: string;
}) {
	const session = useAtomValue(chatSessionStateAtom);
	const threadId = session?.threadId ?? null;
	const { findByToolCallId, findByChatTurnAndTool } = useAgentActionsQuery(threadId);

	const chatTurnId = useAuiState(({ message }) => {
		const meta = message?.metadata as { custom?: { chatTurnId?: string } } | undefined;
		return meta?.custom?.chatTurnId ?? null;
	});
	const positionInTurn = useAuiState(({ message }) => {
		const content = message?.content;
		if (!Array.isArray(content)) return -1;
		let n = -1;
		for (const part of content) {
			if (
				part &&
				typeof part === "object" &&
				(part as { type?: string }).type === "tool-call" &&
				(part as { toolName?: string }).toolName === toolName
			) {
				n += 1;
				if ((part as { toolCallId?: string }).toolCallId === toolCallId) return n;
			}
		}
		return -1;
	});

	const action = useMemo(() => {
		const direct = findByToolCallId(toolCallId) ?? findByToolCallId(langchainToolCallId);
		if (direct) return direct;
		if (!chatTurnId || positionInTurn < 0) return null;
		const turnSameTool = findByChatTurnAndTool(chatTurnId, toolName);
		return turnSameTool[positionInTurn] ?? null;
	}, [
		findByToolCallId,
		findByChatTurnAndTool,
		toolCallId,
		langchainToolCallId,
		chatTurnId,
		toolName,
		positionInTurn,
	]);

	return { threadId, action };
}
