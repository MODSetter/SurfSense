export type ChatFlow = "new" | "resume" | "regenerate";

export type ChatErrorKind =
	| "premium_quota_exhausted"
	| "thread_busy"
	| "send_failed_pre_accept"
	| "auth_expired"
	| "model_auth_failed"
	| "model_not_found"
	| "model_context_limit"
	| "model_capability_error"
	| "model_provider_unavailable"
	| "rate_limited"
	| "network_offline"
	| "stream_interrupted"
	| "stream_parse_error"
	| "tool_execution_error"
	| "persist_message_failed"
	| "server_error"
	| "unknown";

export type ChatErrorChannel = "pinned_inline" | "inline" | "toast" | "silent";
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
		workspaceId?: number;
		threadId?: number | null;
	};
}

export const PREMIUM_QUOTA_ASSISTANT_MESSAGE =
	"I can’t continue with the current premium model because your premium credit is exhausted. Switch to a free model or top up your credit to continue.";

export const GENERIC_CHAT_ERROR_MESSAGE =
	"We couldn’t complete this response right now. Please try again.";

function getErrorMessage(error: unknown): string {
	if (error instanceof Error) return error.message;
	if (typeof error === "string") return error;
	if (
		typeof error === "object" &&
		error !== null &&
		"message" in error &&
		typeof error.message === "string"
	) {
		return error.message;
	}
	try {
		return JSON.stringify(error);
	} catch {
		return "Unknown error";
	}
}

function getErrorCode(error: unknown): string | undefined {
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

	return undefined;
}

export function classifyChatError(input: RawChatErrorInput): NormalizedChatError {
	const { error } = input;
	const rawMessage = getErrorMessage(error);
	const errorCode = getErrorCode(error);
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
			userMessage: rawMessage || GENERIC_CHAT_ERROR_MESSAGE,
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
			userMessage: rawMessage || GENERIC_CHAT_ERROR_MESSAGE,
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
			userMessage: rawMessage || GENERIC_CHAT_ERROR_MESSAGE,
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

	if (errorCode === "MODEL_AUTH_FAILED") {
		return {
			kind: "model_auth_failed",
			channel: "toast",
			severity: "warn",
			telemetryEvent: "chat_blocked",
			isExpected: true,
			userMessage: rawMessage || GENERIC_CHAT_ERROR_MESSAGE,
			rawMessage,
			errorCode: errorCode ?? "MODEL_AUTH_FAILED",
			details: { flow: input.flow },
		};
	}

	if (errorCode === "MODEL_NOT_FOUND") {
		return {
			kind: "model_not_found",
			channel: "toast",
			severity: "warn",
			telemetryEvent: "chat_blocked",
			isExpected: true,
			userMessage: rawMessage || GENERIC_CHAT_ERROR_MESSAGE,
			rawMessage,
			errorCode: errorCode ?? "MODEL_NOT_FOUND",
			details: { flow: input.flow },
		};
	}

	if (errorCode === "MODEL_CONTEXT_LIMIT") {
		return {
			kind: "model_context_limit",
			channel: "toast",
			severity: "warn",
			telemetryEvent: "chat_blocked",
			isExpected: true,
			userMessage: rawMessage || GENERIC_CHAT_ERROR_MESSAGE,
			rawMessage,
			errorCode: errorCode ?? "MODEL_CONTEXT_LIMIT",
			details: { flow: input.flow },
		};
	}

	if (errorCode === "MODEL_DOES_NOT_SUPPORT_IMAGE_INPUT") {
		return {
			kind: "model_capability_error",
			channel: "toast",
			severity: "warn",
			telemetryEvent: "chat_blocked",
			isExpected: true,
			userMessage: rawMessage || GENERIC_CHAT_ERROR_MESSAGE,
			rawMessage,
			errorCode: errorCode ?? "MODEL_DOES_NOT_SUPPORT_IMAGE_INPUT",
			details: { flow: input.flow },
		};
	}

	if (errorCode === "MODEL_PROVIDER_UNAVAILABLE") {
		return {
			kind: "model_provider_unavailable",
			channel: "toast",
			severity: "warn",
			telemetryEvent: "chat_blocked",
			isExpected: true,
			userMessage: rawMessage || GENERIC_CHAT_ERROR_MESSAGE,
			rawMessage,
			errorCode: errorCode ?? "MODEL_PROVIDER_UNAVAILABLE",
			details: { flow: input.flow },
		};
	}

	if (errorCode === "RATE_LIMITED") {
		return {
			kind: "rate_limited",
			channel: "toast",
			severity: "warn",
			telemetryEvent: "chat_blocked",
			isExpected: true,
			userMessage: rawMessage || GENERIC_CHAT_ERROR_MESSAGE,
			rawMessage,
			errorCode: errorCode ?? "RATE_LIMITED",
			details: { flow: input.flow },
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
			userMessage: rawMessage || GENERIC_CHAT_ERROR_MESSAGE,
			rawMessage,
			errorCode: errorCode ?? "TOOL_EXECUTION_ERROR",
			details: { flow: input.flow },
		};
	}

	if (errorCode === "MESSAGE_PERSIST_FAILED") {
		return {
			kind: "persist_message_failed",
			channel: "toast",
			severity: "error",
			telemetryEvent: "chat_error",
			isExpected: false,
			userMessage: rawMessage || GENERIC_CHAT_ERROR_MESSAGE,
			rawMessage,
			errorCode: errorCode ?? "MESSAGE_PERSIST_FAILED",
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
			userMessage: rawMessage || GENERIC_CHAT_ERROR_MESSAGE,
			rawMessage,
			errorCode: errorCode ?? "SERVER_ERROR",
			details: { flow: input.flow },
		};
	}

	return {
		kind: "unknown",
		channel: "toast",
		severity: "error",
		telemetryEvent: "chat_error",
		isExpected: false,
		userMessage: GENERIC_CHAT_ERROR_MESSAGE,
		rawMessage,
		errorCode,
		details: { flow: input.flow },
	};
}
