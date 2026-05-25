import { z } from "zod";

export const OAUTH_RESULT_COOKIE = "connector_oauth_result";

/**
 * Schema for the payload written to the `connector_oauth_result` cookie by the
 * OAuth callback route and read back by the connector dialog hook.
 */
export const oauthCallbackResultSchema = z.object({
	success: z.string().nullable(),
	error: z.string().nullable(),
	connector: z.string().nullable(),
	connectorId: z.string().nullable(),
});

export type OAuthCallbackResult = z.infer<typeof oauthCallbackResultSchema>;

/**
 * Safely decode and validate the OAuth callback cookie value. Returns `null`
 * when the value is not valid JSON or does not match the expected shape.
 */
export function parseOAuthCallbackResult(raw: string): OAuthCallbackResult | null {
	let parsed: unknown;
	try {
		parsed = JSON.parse(raw);
	} catch {
		return null;
	}
	const result = oauthCallbackResultSchema.safeParse(parsed);
	return result.success ? result.data : null;
}
