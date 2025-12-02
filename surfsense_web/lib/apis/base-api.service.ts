import type z from "zod";
import {
	AppError,
	AuthenticationError,
	AuthorizationError,
	NotFoundError,
	ValidationError,
} from "../error";
import { getCSRFTokenFromCookie, getCSRFHeaderName, ensureCSRFToken } from "../csrf-utils";

export type RequestOptions = {
	method: "GET" | "POST" | "PUT" | "DELETE";
	headers?: Record<string, string>;
	contentType?: "application/json" | "application/x-www-form-urlencoded";
	signal?: AbortSignal;
	body?: any;
	// Add more options as needed
};

export class BaseApiService {
	baseUrl: string;

	noAuthEndpoints: string[] = [
		"/auth/jwt/login", 
		"/auth/register", 
		"/auth/refresh", 
		"/api/v1/auth/2fa/login", 
		"/api/v1/auth/2fa/verify"
	];
	
	// Methods that require CSRF protection
	csrfProtectedMethods = ["POST", "PUT", "DELETE", "PATCH"];

	constructor(baseUrl: string) {
		this.baseUrl = baseUrl;
	}

	async request<T>(
		url: string,
		responseSchema?: z.ZodSchema<T>,
		options?: RequestOptions
	): Promise<T> {
		try {
			const defaultOptions: RequestOptions = {
				headers: {
					"Content-Type": "application/json",
				},
				method: "GET",
			};

			const mergedOptions: RequestOptions = {
				...defaultOptions,
				...(options ?? {}),
				headers: {
					...defaultOptions.headers,
					...(options?.headers ?? {}),
				},
			};

			// SECURITY: Add CSRF token for state-changing requests
			if (mergedOptions.method && this.csrfProtectedMethods.includes(mergedOptions.method)) {
				const csrfToken = getCSRFTokenFromCookie();
				if (csrfToken) {
					mergedOptions.headers![getCSRFHeaderName()] = csrfToken;
				}
			}

			// SECURITY: Include credentials to send HttpOnly cookies
			// Cookies are automatically sent by the browser - no manual token handling needed
			const fetchOptions: RequestInit = {
				...mergedOptions,
				credentials: 'include',  // Critical for HttpOnly cookies and CSRF
			};

			if (!this.baseUrl) {
				throw new AppError("Base URL is not set.");
			}

			const fullUrl = new URL(url, this.baseUrl).toString();

			const response = await fetch(fullUrl, fetchOptions);

			if (!response.ok) {
				// biome-ignore lint/suspicious: Unknown
				let data;

				try {
					data = await response.json();
				} catch (error) {
					console.error("Failed to parse response as JSON:", error);

					throw new AppError("Something went wrong", response.status, response.statusText);
				}

				// for fastapi errors response
				if ("detail" in data) {
					throw new AppError(data.detail, response.status, response.statusText);
				}

				switch (response.status) {
					case 401:
						throw new AuthenticationError(
							"You are not authenticated. Please login again.",
							response.status,
							response.statusText
						);
					case 403:
						// Check if it's a CSRF error
						if (data.detail && data.detail.includes("CSRF")) {
							// Try to fetch a new CSRF token and retry the request
							if (mergedOptions.method && this.csrfProtectedMethods.includes(mergedOptions.method)) {
								try {
									const newToken = await ensureCSRFToken();
									mergedOptions.headers![getCSRFHeaderName()] = newToken;
									// Retry the request once with new token
									return this.request(url, responseSchema, mergedOptions);
								} catch (csrfError) {
									throw new AuthorizationError(
										"CSRF validation failed. Please refresh the page.",
										response.status,
										response.statusText
									);
								}
							}
						}
						throw new AuthorizationError(
							"You don't have permission to access this resource.",
							response.status,
							response.statusText
						);
					case 404:
						throw new NotFoundError("Resource not found", response.status, response.statusText);
					//  Add more cases as needed
					default:
						throw new AppError("Something went wrong", response.status, response.statusText);
				}
			}

			// biome-ignore lint/suspicious: Unknown
			let data;

			try {
				data = await response.json();
			} catch (error) {
				console.error("Failed to parse response as JSON:", error);

				throw new AppError("Something went wrong", response.status, response.statusText);
			}

			if (!responseSchema) {
				return data;
			}

			const parsedData = responseSchema.safeParse(data);

			if (!parsedData.success) {
				/** The request was successful, but the response data does not match the expected schema.
				 * 	This is a client side error, and should be fixed by updating the responseSchema to keep things typed.
				 *  This error should not be shown to the user , it is for dev only.
				 */
				console.error("Invalid API response schema:", parsedData.error);
			}

			return data;
		} catch (error) {
			console.error("Request failed:", error);
			throw error;
		}
	}

	async get<T>(
		url: string,
		responseSchema?: z.ZodSchema<T>,
		options?: Omit<RequestOptions, "method">
	) {
		return this.request(url, responseSchema, {
			...options,
			method: "GET",
		});
	}

	async post<T>(
		url: string,
		responseSchema?: z.ZodSchema<T>,
		options?: Omit<RequestOptions, "method">
	) {
		return this.request(url, responseSchema, {
			method: "POST",
			...options,
		});
	}

	async put<T>(
		url: string,
		responseSchema?: z.ZodSchema<T>,
		options?: Omit<RequestOptions, "method">
	) {
		return this.request(url, responseSchema, {
			method: "PUT",
			...options,
		});
	}

	async delete<T>(
		url: string,
		responseSchema?: z.ZodSchema<T>,
		options?: Omit<RequestOptions, "method">
	) {
		return this.request(url, responseSchema, {
			method: "DELETE",
			...options,
		});
	}
}

// SECURITY NOTE: No longer reading from localStorage - using HttpOnly cookies instead
// Cookies are automatically included in requests via credentials: 'include'
// CSRF protection via double-submit cookie pattern
export const baseApiService = new BaseApiService(
	process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL || ""
);
