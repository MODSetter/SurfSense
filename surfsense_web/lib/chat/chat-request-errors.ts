export async function toHttpResponseError(
	response: Response
): Promise<Error & { errorCode?: string; retryAfterMs?: number }> {
	const statusDefaultCode =
		response.status === 409
			? "THREAD_BUSY"
			: response.status === 429
				? "RATE_LIMITED"
				: response.status === 401 || response.status === 403
					? "AUTH_EXPIRED"
					: "SERVER_ERROR";

	let rawBody = "";
	try {
		rawBody = await response.text();
	} catch {
		// noop
	}

	let parsedBody: Record<string, unknown> | null = null;
	if (rawBody) {
		try {
			const parsed = JSON.parse(rawBody);
			if (typeof parsed === "object" && parsed !== null) {
				parsedBody = parsed as Record<string, unknown>;
			}
		} catch {
			// noop
		}
	}

	const detail = parsedBody?.detail;
	const detailObject =
		typeof detail === "object" && detail !== null ? (detail as Record<string, unknown>) : null;
	const detailMessage = typeof detail === "string" ? detail : undefined;
	const topLevelMessage =
		typeof parsedBody?.message === "string" ? (parsedBody.message as string) : undefined;
	const detailNestedMessage =
		typeof detailObject?.message === "string" ? (detailObject.message as string) : undefined;

	const topLevelCode =
		typeof parsedBody?.errorCode === "string"
			? parsedBody.errorCode
			: typeof parsedBody?.error_code === "string"
				? parsedBody.error_code
				: undefined;
	const detailCode =
		typeof detailObject?.errorCode === "string"
			? detailObject.errorCode
			: typeof detailObject?.error_code === "string"
				? detailObject.error_code
				: undefined;

	const errorCode = detailCode ?? topLevelCode ?? statusDefaultCode;

	const detailRetryAfterMs =
		typeof detailObject?.retry_after_ms === "number"
			? detailObject.retry_after_ms
			: typeof detailObject?.retryAfterMs === "number"
				? detailObject.retryAfterMs
				: undefined;
	const topRetryAfterMs =
		typeof parsedBody?.retry_after_ms === "number"
			? parsedBody.retry_after_ms
			: typeof parsedBody?.retryAfterMs === "number"
				? parsedBody.retryAfterMs
				: undefined;
	const headerRetryAfterMsRaw = response.headers.get("retry-after-ms");
	const headerRetryAfterMs = headerRetryAfterMsRaw ? Number.parseFloat(headerRetryAfterMsRaw) : NaN;
	const retryAfterHeader = response.headers.get("retry-after");
	const retryAfterSeconds = retryAfterHeader ? Number.parseFloat(retryAfterHeader) : NaN;
	const retryAfterMsFromHeader = Number.isFinite(headerRetryAfterMs)
		? Math.max(0, Math.round(headerRetryAfterMs))
		: Number.isFinite(retryAfterSeconds)
			? Math.max(0, Math.round(retryAfterSeconds * 1000))
			: undefined;
	const retryAfterMs =
		detailRetryAfterMs ?? topRetryAfterMs ?? retryAfterMsFromHeader ?? undefined;
	const message =
		detailNestedMessage ??
		detailMessage ??
		topLevelMessage ??
		`Backend error: ${response.status}`;

	return Object.assign(new Error(message), { errorCode, retryAfterMs });
}

export function tagPreAcceptSendFailure(error: unknown): unknown {
	if (error instanceof Error) {
		const withCode = error as Error & { errorCode?: string; code?: string };
		const existingCode = withCode.errorCode ?? withCode.code;
		const passthroughCodes = new Set([
			"PREMIUM_QUOTA_EXHAUSTED",
			"THREAD_BUSY",
			"TURN_CANCELLING",
			"AUTH_EXPIRED",
			"UNAUTHORIZED",
			"RATE_LIMITED",
			"NETWORK_ERROR",
			"STREAM_PARSE_ERROR",
			"TOOL_EXECUTION_ERROR",
			"PERSIST_MESSAGE_FAILED",
			"SERVER_ERROR",
		]);
		if (existingCode && passthroughCodes.has(existingCode)) {
			return Object.assign(error, { errorCode: existingCode });
		}
		return Object.assign(error, { errorCode: "SEND_FAILED_PRE_ACCEPT" });
	}

	return Object.assign(new Error("Failed to send message before stream acceptance"), {
		errorCode: "SEND_FAILED_PRE_ACCEPT",
	});
}
