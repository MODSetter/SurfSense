import { toast } from "sonner";
import { AbortedError, AppError, AuthenticationError, SURFSENSE_ISSUES_URL } from "./error";

/**
 * Build a GitHub issue URL pre-filled with diagnostic context.
 * Avoids including PII — only structural metadata.
 */
export function buildIssueUrl(error: unknown): string {
	const params = new URLSearchParams();

	const lines: string[] = ["## Bug Report", "", "**Describe what happened:**", "", ""];

	if (error instanceof AppError) {
		lines.push("## Diagnostics (auto-filled)", "");
		if (error.code) lines.push(`- **Error code:** \`${error.code}\``);
		if (error.requestId) lines.push(`- **Request ID:** \`${error.requestId}\``);
		if (error.status) lines.push(`- **HTTP status:** ${error.status}`);
		lines.push(`- **Message:** ${error.message}`);
	} else if (error instanceof Error) {
		lines.push("## Diagnostics (auto-filled)", "");
		lines.push(`- **Error:** ${error.message}`);
	}

	lines.push(`- **Timestamp:** ${new Date().toISOString()}`);
	lines.push(
		`- **Page:** \`${typeof window !== "undefined" ? window.location.pathname : "unknown"}\``
	);
	lines.push(
		`- **User Agent:** \`${typeof navigator !== "undefined" ? navigator.userAgent : "unknown"}\``
	);

	params.set("body", lines.join("\n"));
	params.set("labels", "bug");

	return `${SURFSENSE_ISSUES_URL}/new?${params.toString()}`;
}

/**
 * Show a standardized error toast with a "Report Issue" action.
 *
 * Suppressed for:
 * - AbortedError (user-initiated cancellation)
 * - AuthenticationError (handled by redirect)
 */
export function showErrorToast(error: unknown, fallbackMessage?: string) {
	if (error instanceof AbortedError || error instanceof AuthenticationError) {
		return;
	}

	const message =
		error instanceof AppError
			? error.message
			: error instanceof Error
				? error.message
				: (fallbackMessage ?? "An unexpected error occurred.");

	const code = error instanceof AppError ? error.code : undefined;
	const requestId = error instanceof AppError ? error.requestId : undefined;

	const descParts: string[] = [];
	if (code) descParts.push(`Error: ${code}`);
	if (requestId) descParts.push(`ID: ${requestId}`);

	toast.error(message, {
		description: descParts.length > 0 ? descParts.join(" | ") : undefined,
		duration: 8000,
		action: {
			label: "Report Issue",
			onClick: () => window.open(buildIssueUrl(error), "_blank"),
		},
	});
}
