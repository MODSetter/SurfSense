import { z } from "zod";
import { baseApiService } from "./base-api.service";

const AgentToolInfoSchema = z.object({
	name: z.string(),
	description: z.string(),
	enabled_by_default: z.boolean(),
});

export type AgentToolInfo = z.infer<typeof AgentToolInfoSchema>;

const AgentToolsListSchema = z.array(AgentToolInfoSchema);

class AgentToolsApiService {
	async getTools(): Promise<AgentToolInfo[]> {
		return baseApiService.get("/api/v1/agent/tools", AgentToolsListSchema);
	}
}

export const agentToolsApiService = new AgentToolsApiService();
