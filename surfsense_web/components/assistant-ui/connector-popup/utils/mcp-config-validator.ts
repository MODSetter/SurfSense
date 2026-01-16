import type { MCPServerConfig, MCPToolDefinition } from "@/contracts/types/mcp.types";
import { connectorsApiService } from "@/lib/apis/connectors-api.service";

/**
 * Shared MCP configuration validation result
 */
export interface MCPConfigValidationResult {
	config: MCPServerConfig | null;
	error: string | null;
}

/**
 * Shared MCP connection test result
 */
export interface MCPConnectionTestResult {
	status: "success" | "error";
	message: string;
	tools: MCPToolDefinition[];
}

/**
 * Parse and validate MCP server configuration from JSON string
 * @param configJson - JSON string containing MCP server configuration
 * @returns Validation result with parsed config or error message
 */
export const parseMCPConfig = (configJson: string): MCPConfigValidationResult => {
	try {
		const parsed = JSON.parse(configJson);

		// Validate that it's an object, not an array
		if (Array.isArray(parsed)) {
			return {
				config: null,
				error: "Please provide a single server configuration object, not an array",
			};
		}

		// Validate required fields
		if (!parsed.command || typeof parsed.command !== "string") {
			return {
				config: null,
				error: "'command' field is required and must be a string",
			};
		}

		const config: MCPServerConfig = {
			command: parsed.command,
			args: parsed.args || [],
			env: parsed.env || {},
			transport: parsed.transport || "stdio",
		};

		return {
			config,
			error: null,
		};
	} catch (error) {
		return {
			config: null,
			error: error instanceof Error ? error.message : "Invalid JSON",
		};
	}
};

/**
 * Test connection to MCP server
 * @param serverConfig - MCP server configuration to test
 * @returns Connection test result with status, message, and available tools
 */
export const testMCPConnection = async (
	serverConfig: MCPServerConfig
): Promise<MCPConnectionTestResult> => {
	try {
		const result = await connectorsApiService.testMCPConnection(serverConfig);

		if (result.status === "success") {
			return {
				status: "success",
				message: `Successfully connected. Found ${result.tools.length} tool${result.tools.length !== 1 ? "s" : ""}.`,
				tools: result.tools,
			};
		}

		return {
			status: "error",
			message: result.message || "Failed to connect",
			tools: [],
		};
	} catch (error) {
		return {
			status: "error",
			message: error instanceof Error ? error.message : "Failed to connect",
			tools: [],
		};
	}
};

/**
 * Extract server name from MCP config JSON
 * @param configJson - JSON string containing MCP server configuration
 * @returns Server name if found, otherwise default name
 */
export const extractServerName = (configJson: string): string => {
	try {
		const parsed = JSON.parse(configJson);
		if (parsed.name && typeof parsed.name === "string") {
			return parsed.name;
		}
	} catch {
		// Return default if parsing fails
	}
	return "MCP Server";
};
