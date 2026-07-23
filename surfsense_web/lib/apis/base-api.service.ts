import type { ZodType } from "zod";
import { getDesktopAccessToken } from "@/lib/auth-fetch";
import { buildBackendUrl } from "@/lib/env-config";
import { getClientPlatform } from "../agent-filesystem";
import { handleUnauthorized, refreshSession } from "../auth-utils";
import {
	AbortedError,
	AppError,
	AuthenticationError,
	AuthorizationError,
	NetworkError,
	NotFoundError,
} from "../error";

enum ResponseType {
	JSON = "json",
	TEXT = "text",
	BLOB = "blob",
	ARRAY_BUFFER = "arrayBuffer",
	// Add more response types as needed
}

const REFRESH_RETRY_BLOCK_MS = 30_000;
const refreshRetryBlockedUntil = new Map<string, number>();

function getRefreshRetryKey(method: RequestOptions["method"], url: string): string {
	return `${method}:${url}`;
}

function isRefreshRetryBlocked(key: string): boolean {
	const blockedUntil = refreshRetryBlockedUntil.get(key);
	if (!blockedUntil) return false;
	if (Date.now() < blockedUntil) return true;
	refreshRetryBlockedUntil.delete(key);
	return false;
}

function blockRefreshRetry(key: string): void {
	refreshRetryBlockedUntil.set(key, Date.now() + REFRESH_RETRY_BLOCK_MS);
}

/**
 * Send an API failure to PostHog error tracking. Scoped by the caller to only
 * 5xx server faults + network outages — 4xx responses are expected behavior.
 * Lazy-imports posthog-js so an ad-blocker can never break the request path.
 */
function captureApiException(error: unknown, url: string, method?: RequestOptions["method"]): void {
	import("posthog-js")
		.then(({ default: posthog }) => {
			posthog.captureException(error, {
				api_url: url,
				api_method: method ?? "GET",
				...(error instanceof AppError && {
					status_code: error.status,
					status_text: error.statusText,
					error_code: error.code,
					request_id: error.requestId,
				}),
			});
		})
		.catch(() => {
			console.error("Failed to capture exception in PostHog");
		});
}

export type RequestOptions = {
	method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
	headers?: Record<string, string>;
	contentType?: "application/json" | "application/x-www-form-urlencoded";
	signal?: AbortSignal;
	body?: unknown;
	responseType?: ResponseType;
	_isRetry?: boolean; // Internal flag to prevent infinite retry loops
	// Add more options as needed
};

class BaseApiService {
	noAuthEndpoints: string[] = ["/auth/jwt/login", "/auth/register", "/auth/jwt/refresh"];

	// Prefixes that don't require auth (checked with startsWith)
	noAuthPrefixes: string[] = ["/api/v1/public/"];

	get isDesktopClient(): boolean {
		return typeof window !== "undefined" && !!window.electronAPI;
	}

	async request<T, R extends ResponseType = ResponseType.JSON>(
		url: string,
		responseSchema?: ZodType<T>,
		options?: RequestOptions & { responseType?: R }
	): Promise<
		R extends ResponseType.JSON
			? T
			: R extends ResponseType.TEXT
				? string
				: R extends ResponseType.BLOB
					? Blob
					: R extends ResponseType.ARRAY_BUFFER
						? ArrayBuffer
						: unknown
	> {
		try {
			/**
			 * ----------
			 * REQUEST
			 * ----------
			 */
			const isNoAuthEndpoint =
				this.noAuthEndpoints.includes(url) ||
				this.noAuthPrefixes.some((prefix) => url.startsWith(prefix)) ||
				/^\/api\/v1\/invites\/[^/]+\/info$/.test(url);
			const desktopAccessToken =
				this.isDesktopClient && !isNoAuthEndpoint ? (await getDesktopAccessToken()) || "" : "";
			const defaultOptions: RequestOptions = {
				headers: {
					...(desktopAccessToken ? { Authorization: `Bearer ${desktopAccessToken}` } : {}),
					"X-SurfSense-Client-Platform":
						typeof window === "undefined" ? "web" : getClientPlatform(),
				},
				method: "GET",
				responseType: ResponseType.JSON,
			};

			const mergedOptions: RequestOptions = {
				...defaultOptions,
				...(options ?? {}),
				headers: {
					...defaultOptions.headers,
					...(options?.headers ?? {}),
				},
			};

			const refreshRetryKey = getRefreshRetryKey(mergedOptions.method, url);
			if (this.isDesktopClient && !desktopAccessToken && !isNoAuthEndpoint) {
				// Desktop refresh token is gone/revoked — send the user to /desktop/login
				// (same treatment as a server 401 below) instead of erroring in place.
				handleUnauthorized();
				throw new AuthenticationError("You are not authenticated. Please login again.");
			}

			const fullUrl = buildBackendUrl(url);

			// Prepare fetch options
			const fetchOptions: RequestInit = {
				method: mergedOptions.method,
				headers: mergedOptions.headers,
				signal: mergedOptions.signal,
				credentials: "include",
			};

			// Automatically stringify body if Content-Type is application/json and body is an object
			if (mergedOptions.body !== undefined) {
				const contentType = mergedOptions.headers?.["Content-Type"];
				if (contentType === "application/json" && typeof mergedOptions.body === "object") {
					fetchOptions.body = JSON.stringify(mergedOptions.body);
				} else {
					// Pass body as-is for other content types (form data, already stringified).
					// Caller is responsible for passing a real BodyInit when Content-Type is not JSON.
					fetchOptions.body = mergedOptions.body as BodyInit;
				}
			}

			const response = await fetch(fullUrl, fetchOptions);

			/**
			 * ----------
			 * RESPONSE
			 * ----------
			 */

			// Handle errors
			if (!response.ok) {
				// biome-ignore lint/suspicious: Unknown
				let data;

				try {
					data = await response.json();
				} catch (error) {
					console.error("Failed to parse response as JSON: ", JSON.stringify(error));
					throw new AppError("Failed to parse response", response.status, response.statusText);
				}

				// Extract structured fields from new envelope or legacy shape
				const envelope = typeof data === "object" && data?.error;
				const errorMessage: string =
					envelope?.message ??
					(typeof data === "object" && typeof data?.detail === "string" ? data.detail : "");
				const errorCode: string | undefined = envelope?.code;
				const requestId: string | undefined =
					envelope?.request_id ?? response.headers.get("X-Request-ID") ?? undefined;
				const reportUrl: string | undefined = envelope?.report_url;

				// Handle 401 - try to refresh token first (only once)
				if (response.status === 401) {
					if (options?._isRetry) {
						blockRefreshRetry(refreshRetryKey);
					} else if (!isNoAuthEndpoint && !isRefreshRetryBlocked(refreshRetryKey)) {
						const refreshed = await refreshSession();
						if (refreshed) {
							const newToken = this.isDesktopClient
								? (await getDesktopAccessToken({ forceRefresh: true })) || ""
								: "";
							return this.request(url, responseSchema, {
								...mergedOptions,
								headers: {
									...mergedOptions.headers,
									...(this.isDesktopClient ? { Authorization: `Bearer ${newToken}` } : {}),
								},
								_isRetry: true,
							} as RequestOptions & { responseType?: R });
						}
						blockRefreshRetry(refreshRetryKey);
					}
					handleUnauthorized();
					throw new AuthenticationError(
						errorMessage || "You are not authenticated. Please login again.",
						response.status,
						response.statusText
					);
				}

				// Map status to typed error
				switch (response.status) {
					case 403:
						throw new AuthorizationError(
							errorMessage || "You don't have permission to access this resource.",
							response.status,
							response.statusText
						);
					case 404:
						throw new NotFoundError(
							errorMessage || "Resource not found",
							response.status,
							response.statusText
						);
					default:
						throw new AppError(
							errorMessage || "Something went wrong",
							response.status,
							response.statusText,
							errorCode,
							requestId,
							reportUrl
						);
				}
			}
			refreshRetryBlockedUntil.delete(getRefreshRetryKey(mergedOptions.method, url));

			// biome-ignore lint/suspicious: Unknown
			let data;
			const responseType = mergedOptions.responseType;

			if (response.status === 204) {
				// 204 No Content has no body; .json() would throw SyntaxError.
				// Leave data as null and skip schema validation below so endpoints
				// that opt out of bodies (REST-style DELETE) don't error on success.
				data = null;
			} else {
				try {
					switch (responseType) {
						case ResponseType.JSON:
							data = await response.json();
							break;
						case ResponseType.TEXT:
							data = await response.text();
							break;
						case ResponseType.BLOB:
							data = await response.blob();
							break;
						case ResponseType.ARRAY_BUFFER:
							data = await response.arrayBuffer();
							break;
						//  Add more cases as needed
						default:
							data = await response.json();
					}
				} catch (error) {
					console.error("Failed to parse response as JSON:", error);
					throw new AppError("Failed to parse response", response.status, response.statusText);
				}
			}

			// Validate response
			if (responseType === ResponseType.JSON) {
				if (!responseSchema || response.status === 204) {
					return data;
				}
				const parsedData = responseSchema.safeParse(data);

				if (!parsedData.success) {
					/** The request was successful, but the response data does not match the expected schema.
					 * 	This is a client side error, and should be fixed by updating the responseSchema to keep things typed.
					 *  This error should not be shown to the user , it is for dev only.
					 */
					console.error(`Invalid API response schema - ${url} :`, JSON.stringify(parsedData.error));
				}

				return data;
			}

			return data;
		} catch (error) {
			// Normalize browser-level fetch failures before anything else
			if (error instanceof DOMException && error.name === "AbortError") {
				throw new AbortedError();
			}
			if (error instanceof TypeError && !(error instanceof AppError)) {
				const networkError = new NetworkError(
					"Unable to connect to the server. Check your internet connection and try again."
				);
				// Network failures are genuine outages worth tracking.
				captureApiException(networkError, url, options?.method);
				throw networkError;
			}

			console.error("Request failed:", JSON.stringify(error));
			// Only 5xx server faults are unexpected. 4xx (validation, authz, 404)
			// are expected behavior — capturing them was billable error-tracking
			// noise. AuthenticationError (401) is a 4xx and stays excluded.
			if (error instanceof AppError && error.status >= 500) {
				captureApiException(error, url, options?.method);
			}
			throw error;
		}
	}

	async get<T>(
		url: string,
		responseSchema?: ZodType<T>,
		options?: Omit<RequestOptions, "method" | "responseType">
	) {
		return this.request(url, responseSchema, {
			method: "GET",
			headers: {
				"Content-Type": "application/json",
			},
			...options,
			responseType: ResponseType.JSON,
		});
	}

	async post<T>(
		url: string,
		responseSchema?: ZodType<T>,
		options?: Omit<RequestOptions, "method" | "responseType">
	) {
		return this.request(url, responseSchema, {
			method: "POST",
			headers: {
				"Content-Type": "application/json",
			},
			...options,
			responseType: ResponseType.JSON,
		});
	}

	async put<T>(
		url: string,
		responseSchema?: ZodType<T>,
		options?: Omit<RequestOptions, "method" | "responseType">
	) {
		return this.request(url, responseSchema, {
			method: "PUT",
			headers: {
				"Content-Type": "application/json",
			},
			...options,
			responseType: ResponseType.JSON,
		});
	}

	async delete<T>(
		url: string,
		responseSchema?: ZodType<T>,
		options?: Omit<RequestOptions, "method" | "responseType">
	) {
		return this.request(url, responseSchema, {
			method: "DELETE",
			headers: {
				"Content-Type": "application/json",
			},
			...options,
			responseType: ResponseType.JSON,
		});
	}

	async patch<T>(
		url: string,
		responseSchema?: ZodType<T>,
		options?: Omit<RequestOptions, "method" | "responseType">
	) {
		return this.request(url, responseSchema, {
			method: "PATCH",
			headers: {
				"Content-Type": "application/json",
			},
			...options,
			responseType: ResponseType.JSON,
		});
	}

	async getBlob(url: string, options?: Omit<RequestOptions, "method" | "responseType">) {
		return this.request(url, undefined, {
			...options,
			method: "GET",
			responseType: ResponseType.BLOB,
		});
	}

	async postFormData<T>(
		url: string,
		responseSchema?: ZodType<T>,
		options?: Omit<RequestOptions, "method" | "responseType" | "body"> & { body: FormData }
	) {
		// Remove Content-Type from options headers if present
		const headersWithoutContentType = { ...(options?.headers ?? {}) };
		delete headersWithoutContentType["Content-Type"];

		return this.request(url, responseSchema, {
			method: "POST",
			...options,
			headers: {
				// Don't set Content-Type - let browser set it with multipart boundary
				...headersWithoutContentType,
			},
			responseType: ResponseType.JSON,
		});
	}
}

export const baseApiService = new BaseApiService();
