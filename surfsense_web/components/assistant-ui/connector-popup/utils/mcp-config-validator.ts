/**
 * MCP Configuration Validator Utility
 *
 * Shared validation and parsing logic for MCP (Model Context Protocol) server configurations.
 *
 * Features:
 * - Zod schema validation for runtime type safety
 * - Configuration caching to avoid repeated parsing (5-minute TTL)
 * - Standardized error messages
 * - Connection testing utilities
 *
 * Usage:
 * ```typescript
 * // Parse and validate config
 * const result = parseMCPConfig(jsonString);
 * if (result.config) {
 *   // Valid config
 * } else {
 *   // Show result.error to user
 * }
 *
 * // Test connection
 * const testResult = await testMCPConnection(config);
 * if (testResult.status === "success") {
 *   console.log(`Found ${testResult.tools.length} tools`);
 * }
 * ```
 *
 * @module mcp-config-validator
 */

import { z } from "zod";
import type { MCPServerConfig, MCPToolDefinition } from "@/contracts/types/mcp.types";
import { connectorsApiService } from "@/lib/apis/connectors-api.service";

/**
 * Zod schema for MCP server configuration
 * Supports both stdio (local process) and HTTP (remote server) transports
 *
 * Exported for advanced use cases (e.g., form builders)
 */
const StdioConfigSchema = z.object({
	name: z.string().optional(),
	command: z.string().min(1, "Command cannot be empty"),
	args: z.array(z.string()).optional().default([]),
	env: z.record(z.string(), z.string()).optional().default({}),
	transport: z.enum(["stdio"]).optional().default("stdio"),
});

const HttpConfigSchema = z.object({
	name: z.string().optional(),
	url: z.string().url("URL must be a valid URL"),
	headers: z.record(z.string(), z.string()).optional().default({}),
	transport: z.enum(["streamable-http", "http", "sse"]),
});

export const MCPServerConfigSchema = z.union([StdioConfigSchema, HttpConfigSchema]);

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
 * Cache for parsed configurations to avoid re-parsing
 * Key: JSON string, Value: { config, timestamp }
 */
const configCache = new Map<string, { config: MCPServerConfig; timestamp: number }>();
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

/**
 * Clear expired entries from config cache
 */
const clearExpiredCache = () => {
	const now = Date.now();
	for (const [key, value] of configCache.entries()) {
		if (now - value.timestamp > CACHE_TTL) {
			configCache.delete(key);
		}
	}
};

/**
 * Parse and validate MCP server configuration from JSON string
 * Uses Zod for schema validation and caching to avoid re-parsing
 * @param configJson - JSON string containing MCP server configuration
 * @returns Validation result with parsed config or error message
 */
export const parseMCPConfig = (configJson: string): MCPConfigValidationResult => {
	// Check cache first
	const cached = configCache.get(configJson);
	if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
		console.log("[MCP Validator] ✅ Using cached config");
		return { config: cached.config, error: null };
	}

	console.log("[MCP Validator] 🔍 Parsing new config...");

	// Clean up expired cache entries periodically
	if (configCache.size > 100) {
		clearExpiredCache();
	}

	try {
		const parsed = JSON.parse(configJson);

		// Validate that it's an object, not an array
		if (Array.isArray(parsed)) {
			console.error("[MCP Validator] ❌ Error: Config is an array, expected object");
			return {
				config: null,
				error: "Please provide a single server configuration object, not an array",
			};
		}

		// Use Zod schema validation for robust type checking
		const result = MCPServerConfigSchema.safeParse(parsed);

		if (!result.success) {
			// Format Zod validation errors for user-friendly display
			const firstError = result.error.issues[0];
			const fieldPath = firstError.path.join(".");

			// Clean up error message - remove technical Zod jargon
			let errorMsg = firstError.message;

			// Replace technical error messages with user-friendly ones
			if (errorMsg.includes("expected string, received undefined")) {
				errorMsg = fieldPath ? `The '${fieldPath}' field is required` : "This field is required";
			} else if (errorMsg.includes("Invalid input")) {
				errorMsg = fieldPath ? `The '${fieldPath}' field has an invalid value` : "Invalid value";
			} else if (fieldPath && !errorMsg.toLowerCase().includes(fieldPath.toLowerCase())) {
				// If error message doesn't mention the field name, prepend it
				errorMsg = `The '${fieldPath}' field: ${errorMsg}`;
			}

			console.error("[MCP Validator] ❌ Validation error:", errorMsg);
			console.error("[MCP Validator] Full Zod errors:", result.error.issues);

			return {
				config: null,
				error: errorMsg,
			};
		}

		// Build config based on transport type
		const config: MCPServerConfig =
			result.data.transport === "stdio" || !result.data.transport
				? {
						command: (result.data as z.infer<typeof StdioConfigSchema>).command,
						args: (result.data as z.infer<typeof StdioConfigSchema>).args,
						env: (result.data as z.infer<typeof StdioConfigSchema>).env,
						transport: "stdio" as const,
					}
				: {
						url: (result.data as z.infer<typeof HttpConfigSchema>).url,
						headers: (result.data as z.infer<typeof HttpConfigSchema>).headers,
						transport: result.data.transport as "streamable-http" | "http" | "sse",
					};

		// Cache the successfully parsed config
		configCache.set(configJson, {
			config,
			timestamp: Date.now(),
		});

		console.log("[MCP Validator] ✅ Config parsed successfully:", config);

		return {
			config,
			error: null,
		};
	} catch (error) {
		const errorMsg = error instanceof Error ? error.message : "Invalid JSON";
		console.error("[MCP Validator] ❌ JSON parse error:", errorMsg);
		return {
			config: null,
			error: errorMsg,
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
 * Extract server name from MCP config JSON with caching
 * @param configJson - JSON string containing MCP server configuration
 * @returns Server name if found, otherwise default name
 */
export const extractServerName = (configJson: string): string => {
	try {
		const parsed = JSON.parse(configJson);

		// Use Zod to validate and extract name field safely
		const nameSchema = z.object({ name: z.string().optional() });
		const result = nameSchema.safeParse(parsed);

		if (result.success && result.data.name) {
			return result.data.name;
		}
	} catch {
		// Return default if parsing fails
	}
	return "MCP Server";
};

/**
 * Clear the configuration cache
 * Useful for testing or when memory management is needed
 */
export const clearConfigCache = () => {
	configCache.clear();
};

/**
 * Get cache statistics for monitoring/debugging
 */
export const getConfigCacheStats = () => {
	return {
		size: configCache.size,
		entries: Array.from(configCache.entries()).map(([key, value]) => ({
			configPreview: key.substring(0, 50) + (key.length > 50 ? "..." : ""),
			timestamp: new Date(value.timestamp).toISOString(),
			age: Date.now() - value.timestamp,
		})),
	};
};
