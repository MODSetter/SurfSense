import { z } from "zod";
import { searchSourceConnectorTypeEnum } from "@/contracts/types/connector.types";

/**
 * Schema for URL query parameters used by the connector popup
 */
export const connectorPopupQueryParamsSchema = z.object({
	modal: z.enum(["connectors"]).optional(),
	tab: z.enum(["all", "active"]).optional(),
	view: z
		.enum(["configure", "edit", "connect", "youtube", "accounts", "mcp-list", "composio"])
		.optional(),
	connector: z.string().optional(),
	connectorId: z.string().optional(),
	connectorType: z.string().optional(),
	success: z.enum(["true", "false"]).optional(),
	error: z.string().optional(),
});

export type ConnectorPopupQueryParams = z.infer<typeof connectorPopupQueryParamsSchema>;

/**
 * Schema for OAuth API response (auth_url)
 */
export const oauthAuthResponseSchema = z.object({
	auth_url: z.string().url("Invalid auth URL format"),
});

export type OAuthAuthResponse = z.infer<typeof oauthAuthResponseSchema>;

/**
 * Schema for IndexingConfigState
 */
export const indexingConfigStateSchema = z.object({
	connectorType: searchSourceConnectorTypeEnum,
	connectorId: z.number().int().positive("Connector ID must be a positive integer"),
	connectorTitle: z.string().min(1, "Connector title is required"),
});

export type IndexingConfigState = z.infer<typeof indexingConfigStateSchema>;

/**
 * Schema for frequency minutes (must be one of the allowed values)
 */
export const frequencyMinutesSchema = z.enum(["5", "15", "60", "360", "720", "1440", "10080"], {
	message: "Invalid frequency value",
});

export type FrequencyMinutes = z.infer<typeof frequencyMinutesSchema>;

/**
 * Schema for date range validation
 */
export const dateRangeSchema = z
	.object({
		startDate: z.date().optional(),
		endDate: z.date().optional(),
	})
	.refine(
		(data) => {
			if (data.startDate && data.endDate) {
				return data.startDate <= data.endDate;
			}
			return true;
		},
		{
			message: "Start date must be before or equal to end date",
			path: ["endDate"],
		}
	);

export type DateRange = z.infer<typeof dateRangeSchema>;

/**
 * Schema for connector ID validation (used in URL params)
 */
export const connectorIdSchema = z.string().min(1, "Connector ID is required");

/**
 * Helper function to safely parse query params
 */
export function parseConnectorPopupQueryParams(
	params: URLSearchParams | Record<string, string | null>
): ConnectorPopupQueryParams {
	const obj: Record<string, string | undefined> = {};

	if (params instanceof URLSearchParams) {
		params.forEach((value, key) => {
			obj[key] = value || undefined;
		});
	} else {
		Object.entries(params).forEach(([key, value]) => {
			obj[key] = value || undefined;
		});
	}

	return connectorPopupQueryParamsSchema.parse(obj);
}

/**
 * Helper function to safely parse OAuth response
 */
export function parseOAuthAuthResponse(data: unknown): OAuthAuthResponse {
	return oauthAuthResponseSchema.parse(data);
}

/**
 * Helper function to validate indexing config state
 */
export function validateIndexingConfigState(data: unknown): IndexingConfigState {
	return indexingConfigStateSchema.parse(data);
}
