/**
 * Connector Status Configuration
 *
 * This configuration allows managing connector statuses in the frontend without backend changes.
 * Statuses control warnings, disabling connectors, and displaying status messages.
 */

import { z } from "zod";

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
	warning: z.string().nullable().optional(),
	statusMessage: z.string().nullable().optional(),
	disableReason: z.string().nullable().optional(),
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
 * Default status configuration for all connectors
 * Connectors not listed here default to "active" and enabled
 *
 * This config is validated at runtime using the Zod schema above
 */
const rawConnectorStatusConfig = {
	connectorStatuses: {
		// Example: Disabled connector
		// "SLACK_CONNECTOR": {
		// 	enabled: false,
		// 	status: "disabled",
		// 	warning: null,
		// 	statusMessage: "Slack connector is currently unavailable due to API changes",
		// 	disableReason: "maintenance",
		// },
		// Example: Connector with warning
		// "NOTION_CONNECTOR": {
		// 	enabled: true,
		// 	status: "warning",
		// 	warning: "Rate limits may apply",
		// 	statusMessage: "Notion API rate limits are currently active. Some requests may be delayed.",
		// 	disableReason: null,
		// },
		// Example: Connector in maintenance
		// "TEAMS_CONNECTOR": {
		// 	enabled: false,
		// 	status: "maintenance",
		// 	warning: "Under maintenance",
		// 	statusMessage: "Temporarily unavailable for maintenance",
		// 	disableReason: "maintenance",
		// },
	},
	globalSettings: {
		showWarnings: true,
		allowManualOverride: false,
	},
};

// Validate the config at module load time (development only)
// In production, this will throw if config is invalid
export const connectorStatusConfig: ConnectorStatusConfigFile =
	connectorStatusConfigFileSchema.parse(rawConnectorStatusConfig);

/**
 * Get default status config for a connector (when not in config file)
 * Returns a validated default config
 */
export function getDefaultConnectorStatus(): ConnectorStatusConfig {
	return connectorStatusConfigSchema.parse({
		enabled: true,
		status: "active",
		warning: null,
		statusMessage: null,
		disableReason: null,
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
