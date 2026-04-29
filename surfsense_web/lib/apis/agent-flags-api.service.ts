import { z } from "zod";
import { baseApiService } from "./base-api.service";

const AgentFeatureFlagsSchema = z.object({
	disable_new_agent_stack: z.boolean(),

	enable_context_editing: z.boolean(),
	enable_compaction_v2: z.boolean(),
	enable_retry_after: z.boolean(),
	enable_model_fallback: z.boolean(),
	enable_model_call_limit: z.boolean(),
	enable_tool_call_limit: z.boolean(),
	enable_tool_call_repair: z.boolean(),
	enable_doom_loop: z.boolean(),

	enable_permission: z.boolean(),
	enable_busy_mutex: z.boolean(),
	enable_llm_tool_selector: z.boolean(),

	enable_skills: z.boolean(),
	enable_specialized_subagents: z.boolean(),
	enable_kb_planner_runnable: z.boolean(),

	enable_action_log: z.boolean(),
	enable_revert_route: z.boolean(),

	enable_plugin_loader: z.boolean(),

	enable_otel: z.boolean(),
});

export type AgentFeatureFlags = z.infer<typeof AgentFeatureFlagsSchema>;

class AgentFlagsApiService {
	get = async (): Promise<AgentFeatureFlags> => {
		return baseApiService.get(`/api/v1/agent/flags`, AgentFeatureFlagsSchema);
	};
}

export const agentFlagsApiService = new AgentFlagsApiService();
