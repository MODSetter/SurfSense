/**
 * Authentication error messages and handling utilities
 */

interface AuthErrorMapping {
	[key: string]: {
		title: string;
		description?: string;
	};
}

const AUTH_ERROR_MESSAGES: AuthErrorMapping = {
	// Common HTTP errors
	"401": {
		title: "Invalid credentials",
		description: "Please check your email and password",
	},
	"403": {
		title: "Access denied",
		description: "Your account may be suspended or restricted",
	},
	"404": {
		title: "Account not found",
		description: "No account exists with this email address",
	},
	"409": {
		title: "Account conflict",
		description: "An account with this email already exists",
	},
	"429": {
		title: "Too many attempts",
		description: "Please wait before trying again",
	},
	"500": {
		title: "Server error",
		description: "Something went wrong on our end. Please try again",
	},
	"503": {
		title: "Service unavailable",
		description: "Login service is temporarily down",
	},

	// FastAPI specific errors
	LOGIN_BAD_CREDENTIALS: {
		title: "Invalid credentials",
		description: "The email or password you entered is incorrect",
	},
	LOGIN_USER_NOT_VERIFIED: {
		title: "Account not verified",
		description: "Please verify your email address before signing in",
	},
	USER_INACTIVE: {
		title: "Account inactive",
		description: "Your account has been deactivated. Contact support for assistance",
	},
	REGISTER_USER_ALREADY_EXISTS: {
		title: "Account already exists",
		description: "An account with this email address already exists",
	},
	REGISTER_INVALID_PASSWORD: {
		title: "Invalid password",
		description: "Password must meet security requirements",
	},

	// OAuth errors
	access_denied: {
		title: "Access denied",
		description: "You denied access or cancelled the login process",
	},
	invalid_request: {
		title: "Invalid request",
		description: "The login request was malformed",
	},
	unauthorized_client: {
		title: "Authentication failed",
		description: "The application is not authorized to perform this action",
	},
	unsupported_response_type: {
		title: "Login method not supported",
		description: "This login method is not currently available",
	},
	invalid_scope: {
		title: "Invalid permissions",
		description: "The requested permissions are not valid",
	},
	server_error: {
		title: "Server error",
		description: "An error occurred on the authentication server",
	},
	temporarily_unavailable: {
		title: "Service unavailable",
		description: "Login is temporarily unavailable. Please try again later",
	},

	// Network errors
	NETWORK_ERROR: {
		title: "Connection failed",
		description: "Please check your internet connection and try again",
	},
	TIMEOUT: {
		title: "Request timeout",
		description: "The login request took too long. Please try again",
	},

	// Generic fallbacks
	UNKNOWN_ERROR: {
		title: "Login failed",
		description: "An unexpected error occurred. Please try again",
	},
};

/**
 * Get a user-friendly error message for authentication errors
 * @param errorCode - The error code or message from the API
 * @param returnTitle - Whether to return just the title or full description
 * @returns Formatted error message
 */
export function getAuthErrorMessage(errorCode: string, returnTitle: boolean = false): string {
	if (!errorCode) {
		const fallback = AUTH_ERROR_MESSAGES.UNKNOWN_ERROR;
		return returnTitle ? fallback.title : fallback.description || fallback.title;
	}

	// Clean up the error code
	const cleanErrorCode = errorCode.trim().toUpperCase();

	// Try exact match first
	let errorInfo = AUTH_ERROR_MESSAGES[cleanErrorCode] || AUTH_ERROR_MESSAGES[errorCode];

	// Try partial matches for HTTP status codes
	if (!errorInfo) {
		const statusCodeMatch = errorCode.match(/(\d{3})/);
		if (statusCodeMatch) {
			errorInfo = AUTH_ERROR_MESSAGES[statusCodeMatch[1]];
		}
	}

	// Try partial matches for common error patterns
	if (!errorInfo) {
		const patterns = [
			{ pattern: /credential|password|email/i, code: "LOGIN_BAD_CREDENTIALS" },
			{ pattern: /verify|verification/i, code: "LOGIN_USER_NOT_VERIFIED" },
			{ pattern: /inactive|disabled|suspended/i, code: "USER_INACTIVE" },
			{ pattern: /exists|duplicate/i, code: "REGISTER_USER_ALREADY_EXISTS" },
			{ pattern: /network|connection/i, code: "NETWORK_ERROR" },
			{ pattern: /timeout/i, code: "TIMEOUT" },
			{ pattern: /rate|limit|many/i, code: "429" },
		];

		for (const { pattern, code } of patterns) {
			if (pattern.test(errorCode)) {
				errorInfo = AUTH_ERROR_MESSAGES[code];
				break;
			}
		}
	}

	// Fallback to unknown error
	if (!errorInfo) {
		errorInfo = AUTH_ERROR_MESSAGES.UNKNOWN_ERROR;
	}

	return returnTitle ? errorInfo.title : errorInfo.description || errorInfo.title;
}

/**
 * Get both title and description for an error
 * @param errorCode - The error code or message from the API
 * @returns Object with title and description
 */
export function getAuthErrorDetails(errorCode: string): { title: string; description: string } {
	const title = getAuthErrorMessage(errorCode, true);
	const description = getAuthErrorMessage(errorCode, false);

	return { title, description };
}

/**
 * Check if an error is a network-related error
 * @param error - The error object or message
 * @returns True if it's a network error
 */
export function isNetworkError(error: unknown): boolean {
	if (error instanceof TypeError && error.message.includes("fetch")) {
		return true;
	}

	if (typeof error === "string") {
		return /network|connection|fetch|cors/i.test(error);
	}

	return false;
}

/**
 * Check if an error should trigger a retry action
 * @param errorCode - The error code or message
 * @returns True if retry is recommended
 */
export function shouldRetry(errorCode: string): boolean {
	const retryableCodes = [
		"500",
		"503",
		"429",
		"NETWORK_ERROR",
		"TIMEOUT",
		"server_error",
		"temporarily_unavailable",
	];

	return retryableCodes.some(
		(code) => errorCode.includes(code) || errorCode.toUpperCase().includes(code)
	);
}
