export type ChatFlow = "new" | "resume" | "regenerate";

export type ChatErrorKind =
	| "premium_quota_exhausted"
	| "thread_busy"
	| "send_failed_pre_accept"
	| "auth_expired"
	| "rate_limited"
	| "network_offline"
	| "stream_interrupted"
	| "stream_parse_error"
	| "tool_execution_error"
	| "persist_message_failed"
	| "server_error"
	| "unknown";

export type ChatErrorChannel = "pinned_inline" | "toast" | "silent";
export type ChatTelemetryEvent = "chat_blocked" | "chat_error";
export type ChatErrorSeverity = "info" | "warn" | "error";

export interface NormalizedChatError {
	kind: ChatErrorKind;
	channel: ChatErrorChannel;
	severity: ChatErrorSeverity;
	telemetryEvent: ChatTelemetryEvent;
	isExpected: boolean;
	userMessage: string;
	assistantMessage?: string;
	rawMessage?: string;
	errorCode?: string;
	details?: Record<string, unknown>;
}

export interface RawChatErrorInput {
	error: unknown;
	flow: ChatFlow;
	context?: {
		searchSpaceId?: number;
		threadId?: number | null;
	};
}

export const PREMIUM_QUOTA_ASSISTANT_MESSAGE =
	"I can’t continue with the current premium model because your premium credit is exhausted. Switch to a free model or top up your credit to continue.";

function getErrorMessage(error: unknown): string {
	if (error instanceof Error) return error.message;
	if (typeof error === "string") return error;
	try {
		return JSON.stringify(error);
	} catch {
		return "Unknown error";
	}
}

function getErrorCode(
	error: unknown,
	parsedJson: Record<string, unknown> | null
): string | undefined {
	if (error instanceof Error) {
		const withCode = error as Error & { errorCode?: string; code?: string };
		if (withCode.errorCode) return withCode.errorCode;
		if (withCode.code) return withCode.code;
	}

	if (typeof error === "object" && error !== null) {
		const withCode = error as { errorCode?: unknown };
		if (typeof withCode.errorCode === "string" && withCode.errorCode) {
			return withCode.errorCode;
		}
	}

	if (parsedJson) {
		const topLevelCode = parsedJson.errorCode;
		if (typeof topLevelCode === "string" && topLevelCode) {
			return topLevelCode;
		}
	}

	return undefined;
}

function parseEmbeddedJson(text: string): Record<string, unknown> | null {
	const candidates = [text];
	const firstBraceIdx = text.indexOf("{");
	if (firstBraceIdx >= 0) {
		candidates.push(text.slice(firstBraceIdx));
	}
	for (const candidate of candidates) {
		try {
			const parsed = JSON.parse(candidate);
			if (typeof parsed === "object" && parsed !== null) {
				return parsed as Record<string, unknown>;
			}
		} catch {
			// noop
		}
	}
	return null;
}

function inferProviderErrorType(parsedJson: Record<string, unknown> | null): string | undefined {
	if (!parsedJson) return undefined;
	const topLevelType = parsedJson.type;
	if (typeof topLevelType === "string" && topLevelType) return topLevelType;
	const nestedError = parsedJson.error;
	if (typeof nestedError === "object" && nestedError !== null) {
		const nestedType = (nestedError as Record<string, unknown>).type;
		if (typeof nestedType === "string" && nestedType) return nestedType;
	}
	return undefined;
}

export function classifyChatError(input: RawChatErrorInput): NormalizedChatError {
	const { error } = input;
	const rawMessage = getErrorMessage(error);
	const parsedJson = parseEmbeddedJson(rawMessage);
	const errorCode = getErrorCode(error, parsedJson);
	const providerErrorType = inferProviderErrorType(parsedJson);
	const providerTypeNormalized = providerErrorType?.toLowerCase() ?? "";
	const errorName = error instanceof Error ? error.name : undefined;

	if (errorName === "AbortError") {
		return {
			kind: "stream_interrupted",
			channel: "silent",
			severity: "info",
			telemetryEvent: "chat_error",
			isExpected: true,
			userMessage: "Request canceled.",
			rawMessage,
			errorCode,
			details: { flow: input.flow },
		};
	}

	if (errorCode === "PREMIUM_QUOTA_EXHAUSTED") {
		return {
			kind: "premium_quota_exhausted",
			channel: "pinned_inline",
			severity: "info",
			telemetryEvent: "chat_blocked",
			isExpected: true,
			userMessage: "Buy more tokens to continue with this model, or switch to a free model.",
			assistantMessage: PREMIUM_QUOTA_ASSISTANT_MESSAGE,
			rawMessage,
			errorCode: errorCode ?? "PREMIUM_QUOTA_EXHAUSTED",
			details: { flow: input.flow },
		};
	}

	if (errorCode === "TURN_CANCELLING") {
		return {
			kind: "thread_busy",
			channel: "toast",
			severity: "info",
			telemetryEvent: "chat_blocked",
			isExpected: true,
			userMessage: "A previous response is still stopping. Please try again in a moment.",
			rawMessage,
			errorCode: errorCode ?? "TURN_CANCELLING",
			details: { flow: input.flow },
		};
	}

	if (errorCode === "THREAD_BUSY") {
		return {
			kind: "thread_busy",
			channel: "toast",
			severity: "warn",
			telemetryEvent: "chat_blocked",
			isExpected: true,
			userMessage:
				"Another response is still finishing for this thread. Please try again in a moment.",
			rawMessage,
			errorCode: errorCode ?? "THREAD_BUSY",
			details: { flow: input.flow },
		};
	}

	if (errorCode === "SEND_FAILED_PRE_ACCEPT") {
		return {
			kind: "send_failed_pre_accept",
			channel: "toast",
			severity: "warn",
			telemetryEvent: "chat_blocked",
			isExpected: true,
			userMessage: "Message not sent. Please retry.",
			rawMessage,
			errorCode: errorCode ?? "SEND_FAILED_PRE_ACCEPT",
			details: { flow: input.flow },
		};
	}

	if (errorCode === "AUTH_EXPIRED" || errorCode === "UNAUTHORIZED") {
		return {
			kind: "auth_expired",
			channel: "toast",
			severity: "warn",
			telemetryEvent: "chat_error",
			isExpected: true,
			userMessage: "Your session expired. Please sign in again.",
			rawMessage,
			errorCode: errorCode ?? "AUTH_EXPIRED",
			details: { flow: input.flow },
		};
	}

	if (errorCode === "RATE_LIMITED" || providerTypeNormalized === "rate_limit_error") {
		return {
			kind: "rate_limited",
			channel: "toast",
			severity: "warn",
			telemetryEvent: "chat_blocked",
			isExpected: true,
			userMessage:
				"This model is temporarily rate-limited. Please try again in a few seconds or switch models.",
			rawMessage,
			errorCode: errorCode ?? "RATE_LIMITED",
			details: { flow: input.flow, providerErrorType },
		};
	}

	if (errorCode === "NETWORK_ERROR") {
		return {
			kind: "network_offline",
			channel: "toast",
			severity: "warn",
			telemetryEvent: "chat_error",
			isExpected: true,
			userMessage: "Connection issue. Please try again.",
			rawMessage,
			errorCode: errorCode ?? "NETWORK_ERROR",
			details: { flow: input.flow },
		};
	}

	if (errorCode === "STREAM_PARSE_ERROR") {
		return {
			kind: "stream_parse_error",
			channel: "toast",
			severity: "error",
			telemetryEvent: "chat_error",
			isExpected: false,
			userMessage: "We hit a response formatting issue. Please try again.",
			rawMessage,
			errorCode: errorCode ?? "STREAM_PARSE_ERROR",
			details: { flow: input.flow },
		};
	}

	if (errorCode === "TOOL_EXECUTION_ERROR") {
		return {
			kind: "tool_execution_error",
			channel: "toast",
			severity: "error",
			telemetryEvent: "chat_error",
			isExpected: false,
			userMessage: "A tool failed while processing your request. Please try again.",
			rawMessage,
			errorCode: errorCode ?? "TOOL_EXECUTION_ERROR",
			details: { flow: input.flow },
		};
	}

	if (errorCode === "PERSIST_MESSAGE_FAILED") {
		return {
			kind: "persist_message_failed",
			channel: "toast",
			severity: "error",
			telemetryEvent: "chat_error",
			isExpected: false,
			userMessage: "Response generated, but saving failed. Please retry once.",
			rawMessage,
			errorCode: errorCode ?? "PERSIST_MESSAGE_FAILED",
			details: { flow: input.flow },
		};
	}

	if (errorCode === "SERVER_ERROR") {
		return {
			kind: "server_error",
			channel: "toast",
			severity: "error",
			telemetryEvent: "chat_error",
			isExpected: false,
			userMessage: "We couldn’t complete this response right now. Please try again.",
			rawMessage,
			errorCode: errorCode ?? "SERVER_ERROR",
			details: { flow: input.flow, providerErrorType },
		};
	}

	return {
		kind: "unknown",
		channel: "toast",
		severity: "error",
		telemetryEvent: "chat_error",
		isExpected: false,
		userMessage: "We couldn’t complete this response right now. Please try again.",
		rawMessage,
		errorCode,
		details: { flow: input.flow, providerErrorType },
	};
}
