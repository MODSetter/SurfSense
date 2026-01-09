/**
 * Connector Status Configuration
 *
 * This configuration allows managing connector statuses.
 * Statuses control disabling connectors and displaying status messages.
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
 * Default status configuration for all connectors
 * Connectors not listed here default to "active" and enabled
 *
 * This config is validated at runtime using the Zod schema above
 */
const rawConnectorStatusConfig = {
	connectorStatuses: {
		"SLACK_CONNECTOR": {
			enabled: false,
			status: "disabled",
			statusMessage: "Unavailable due to API changes",
		},
		"NOTION_CONNECTOR": {
			enabled: true,
			status: "warning",
			statusMessage: "Rate limits may apply",
		},
		"TEAMS_CONNECTOR": {
			enabled: false,
			status: "maintenance",
			statusMessage: "Temporarily unavailable for maintenance",
		},
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
