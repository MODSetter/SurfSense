import { z } from "zod";

/**
 * MCP Tool Configuration Schema
 */
export const mcpToolConfig = z.object({
	name: z.string().min(1, "Tool name is required"),
	description: z.string().min(1, "Description is required"),
	endpoint: z.string().url("Must be a valid URL"),
	method: z.enum(["GET", "POST", "PUT", "PATCH", "DELETE"]).default("GET"),
	auth_type: z.enum(["none", "bearer", "api_key", "basic"]).default("none"),
	auth_config: z.record(z.string(), z.any()).default({}),
	parameters: z
		.object({
			type: z.literal("object"),
			properties: z.record(z.string(), z.any()),
			required: z.array(z.string()).optional(),
		})
		.default({
			type: "object",
			properties: {},
		}),
	verify_ssl: z.boolean().default(true),
});

/**
 * MCP Connector Schemas
 */
export const mcpConnectorCreate = z.object({
	name: z.string().min(1, "Connector name is required"),
	tools: z.array(mcpToolConfig).min(1, "At least one tool is required"),
	periodic_indexing_enabled: z.boolean().optional().default(false),
	indexing_frequency_minutes: z.number().nullable().optional(),
});

export const mcpConnectorUpdate = z.object({
	name: z.string().min(1).optional(),
	tools: z.array(mcpToolConfig).min(1).optional(),
});

export const mcpConnectorRead = z.object({
	id: z.number(),
	name: z.string(),
	connector_type: z.literal("MCP_CONNECTOR"),
	tools: z.array(mcpToolConfig),
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
export type MCPToolConfig = z.infer<typeof mcpToolConfig>;
export type MCPConnectorCreate = z.infer<typeof mcpConnectorCreate>;
export type MCPConnectorUpdate = z.infer<typeof mcpConnectorUpdate>;
export type MCPConnectorRead = z.infer<typeof mcpConnectorRead>;
export type CreateMCPConnectorRequest = z.infer<typeof createMCPConnectorRequest>;
export type UpdateMCPConnectorRequest = z.infer<typeof updateMCPConnectorRequest>;
export type GetMCPConnectorsRequest = z.infer<typeof getMCPConnectorsRequest>;
