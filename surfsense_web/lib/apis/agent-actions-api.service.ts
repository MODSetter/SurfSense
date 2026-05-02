import { z } from "zod";
import { baseApiService } from "./base-api.service";

const AgentActionReadSchema = z.object({
	id: z.number(),
	thread_id: z.number(),
	user_id: z.string().nullable(),
	search_space_id: z.number(),
	tool_name: z.string(),
	args: z.record(z.string(), z.unknown()).nullable(),
	result_id: z.string().nullable(),
	reversible: z.boolean(),
	reverse_descriptor: z.record(z.string(), z.unknown()).nullable(),
	error: z.record(z.string(), z.unknown()).nullable(),
	reverse_of: z.number().nullable(),
	reverted_by_action_id: z.number().nullable(),
	is_revert_action: z.boolean(),
	// Correlation ids added in migration 135. The LangChain
	// ``tool_call_id`` joins this row to the chat tool card via the
	// ``data-action-log.lc_tool_call_id`` SSE event, and
	// ``chat_turn_id`` keys the per-turn revert endpoint.
	tool_call_id: z.string().nullable().optional(),
	chat_turn_id: z.string().nullable().optional(),
	created_at: z.string(),
});

export type AgentAction = z.infer<typeof AgentActionReadSchema>;

const AgentActionListResponseSchema = z.object({
	items: z.array(AgentActionReadSchema),
	total: z.number(),
	page: z.number(),
	page_size: z.number(),
	has_more: z.boolean(),
});

export type AgentActionListResponse = z.infer<typeof AgentActionListResponseSchema>;

const RevertResponseSchema = z.object({
	status: z.literal("ok"),
	message: z.string(),
	new_action_id: z.number().nullable().optional(),
});

export type RevertResponse = z.infer<typeof RevertResponseSchema>;

// Per-turn batch revert. The route never returns whole-batch 4xx;
// partial success is the common case and surfaced as
// ``status === "partial"`` with a per-action result list.
const RevertTurnActionResultSchema = z.object({
	action_id: z.number(),
	tool_name: z.string(),
	status: z.enum([
		"reverted",
		"already_reverted",
		"not_reversible",
		"permission_denied",
		"failed",
		"skipped",
	]),
	message: z.string().nullable().optional(),
	new_action_id: z.number().nullable().optional(),
	error: z.string().nullable().optional(),
});

export type RevertTurnActionResult = z.infer<typeof RevertTurnActionResultSchema>;

const RevertTurnResponseSchema = z.object({
	status: z.enum(["ok", "partial"]),
	chat_turn_id: z.string(),
	total: z.number(),
	reverted: z.number(),
	already_reverted: z.number(),
	not_reversible: z.number(),
	// ``permission_denied`` and ``skipped`` are first-class counters so
	// ``total === reverted + already_reverted +
	// not_reversible + permission_denied + failed + skipped`` always
	// holds. ``.default(0)`` keeps the schema backwards-compatible
	// with older deployments that haven't shipped the response model
	// update yet.
	permission_denied: z.number().default(0),
	failed: z.number(),
	skipped: z.number().default(0),
	results: z.array(RevertTurnActionResultSchema),
});

export type RevertTurnResponse = z.infer<typeof RevertTurnResponseSchema>;

class AgentActionsApiService {
	listForThread = async (
		threadId: number,
		opts: { page?: number; pageSize?: number } = {}
	): Promise<AgentActionListResponse> => {
		const params = new URLSearchParams();
		params.set("page", String(opts.page ?? 0));
		params.set("page_size", String(opts.pageSize ?? 50));
		return baseApiService.get(
			`/api/v1/threads/${threadId}/actions?${params.toString()}`,
			AgentActionListResponseSchema
		);
	};

	revert = async (threadId: number, actionId: number): Promise<RevertResponse> => {
		return baseApiService.post(
			`/api/v1/threads/${threadId}/revert/${actionId}`,
			RevertResponseSchema,
			{ body: {} }
		);
	};

	revertTurn = async (threadId: number, chatTurnId: string): Promise<RevertTurnResponse> => {
		return baseApiService.post(
			`/api/v1/threads/${threadId}/revert-turn/${encodeURIComponent(chatTurnId)}`,
			RevertTurnResponseSchema,
			{ body: {} }
		);
	};
}

export const agentActionsApiService = new AgentActionsApiService();
