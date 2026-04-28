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
}

export const agentActionsApiService = new AgentActionsApiService();
