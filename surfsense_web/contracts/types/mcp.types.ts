import { z } from "zod";

/**
 * MCP Server Configuration Schema
 * Supports both stdio (local process) and HTTP (remote server) transports
 */
const stdioConfigSchema = z.object({
	command: z.string().min(1, "Command is required"),
	args: z.array(z.string()).default([]),
	env: z.record(z.string(), z.string()).default({}),
	transport: z.enum(["stdio"]).default("stdio"),
});

const httpConfigSchema = z.object({
	url: z.string().url("URL must be a valid URL"),
	headers: z.record(z.string(), z.string()).default({}),
	transport: z.enum(["streamable-http", "http", "sse"]),
});

export const mcpServerConfig = z.union([stdioConfigSchema, httpConfigSchema]);

/**
 * MCP Connector Schemas
 */
export const mcpConnectorCreate = z.object({
	name: z.string().min(1, "Connector name is required"),
	server_config: mcpServerConfig,
});

export const mcpConnectorUpdate = z.object({
	name: z.string().min(1).optional(),
	server_config: mcpServerConfig.optional(),
});

export const mcpConnectorRead = z.object({
	id: z.number(),
	name: z.string(),
	connector_type: z.literal("MCP_CONNECTOR"),
	server_config: mcpServerConfig,
	search_space_id: z.number(),
	user_id: z.string(),
	created_at: z.string(),
	updated_at: z.string(),
});

/**
 * API Request/Response Types
 */
export const createMCPConnectorRequest = z.object({
	data: mcpConnectorCreate,
	queryParams: z.object({
		search_space_id: z.number().or(z.string()),
	}),
});

export const updateMCPConnectorRequest = z.object({
	id: z.number(),
	data: mcpConnectorUpdate,
});

export const getMCPConnectorsRequest = z.object({
	queryParams: z.object({
		search_space_id: z.number().or(z.string()),
	}),
});

// Inferred Types
export type MCPServerConfig = z.infer<typeof mcpServerConfig>;
export type MCPConnectorCreate = z.infer<typeof mcpConnectorCreate>;
export type MCPConnectorUpdate = z.infer<typeof mcpConnectorUpdate>;
export type MCPConnectorRead = z.infer<typeof mcpConnectorRead>;
export type CreateMCPConnectorRequest = z.infer<typeof createMCPConnectorRequest>;
export type UpdateMCPConnectorRequest = z.infer<typeof updateMCPConnectorRequest>;
export type GetMCPConnectorsRequest = z.infer<typeof getMCPConnectorsRequest>;

/**
 * Tool definition from MCP server
 */
export type MCPToolDefinition = {
	name: string;
	description: string;
	input_schema: Record<string, any>;
};

/**
 * Test connection response
 */
export type MCPTestConnectionResponse = {
	status: "success" | "error";
	message: string;
	tools: MCPToolDefinition[];
};
