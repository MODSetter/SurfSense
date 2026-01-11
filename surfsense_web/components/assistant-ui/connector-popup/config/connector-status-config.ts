/**
 * Connector Status Configuration
 *
 * Manages connector statuses (disable/enable, status messages). Edit connector-status-config.json to configure.
 * Valid status values: "active", "warning", "disabled", "deprecated", "maintenance".
 * Unlisted connectors default to "active" and enabled. See connector-status-config.example.json for reference.
 */

import { z } from "zod";
import rawConnectorStatusConfigData from "./connector-status-config.json";

// Zod schemas for runtime validation and type safety
export const connectorStatusSchema = z.enum([
	"active",
	"warning",
	"disabled",
	"deprecated",
	"maintenance",
]);

export const connectorStatusConfigSchema = z.object({
	enabled: z.boolean(),
	status: connectorStatusSchema,
	statusMessage: z.string().nullable().optional(),
});

export const connectorStatusMapSchema = z.record(z.string(), connectorStatusConfigSchema);

export const connectorStatusConfigFileSchema = z.object({
	connectorStatuses: connectorStatusMapSchema,
	globalSettings: z.object({
		showWarnings: z.boolean(),
		allowManualOverride: z.boolean(),
	}),
});

// TypeScript types inferred from Zod schemas
export type ConnectorStatus = z.infer<typeof connectorStatusSchema>;
export type ConnectorStatusConfig = z.infer<typeof connectorStatusConfigSchema>;
export type ConnectorStatusMap = z.infer<typeof connectorStatusMapSchema>;
export type ConnectorStatusConfigFile = z.infer<typeof connectorStatusConfigFileSchema>;

/**
 * Validated at runtime via Zod schema; invalid JSON throws at module load time.
 */
export const connectorStatusConfig: ConnectorStatusConfigFile =
	connectorStatusConfigFileSchema.parse(rawConnectorStatusConfigData);

/**
 * Get default status config for a connector (when not in config file)
 * Returns a validated default config
 */
export function getDefaultConnectorStatus(): ConnectorStatusConfig {
	return connectorStatusConfigSchema.parse({
		enabled: true,
		status: "active",
		statusMessage: null,
	});
}

/**
 * Validate a connector status config object
 * Useful for validating config loaded from external sources
 */
export function validateConnectorStatusConfig(config: unknown): ConnectorStatusConfigFile {
	return connectorStatusConfigFileSchema.parse(config);
}

/**
 * Validate a single connector status config
 */
export function validateSingleConnectorStatus(config: unknown): ConnectorStatusConfig {
	return connectorStatusConfigSchema.parse(config);
}
