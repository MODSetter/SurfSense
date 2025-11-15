import type z from "zod";
import {
	AppError,
	AuthenticationError,
	AuthorizationError,
	NotFoundError,
	ValidationError,
} from "../error";

export type RequestOptions = {
	method: "GET" | "POST" | "PUT" | "DELETE";
	headers?: Record<string, string>;
	contentType?: "application/json" | "application/x-www-form-urlencoded";
	signal?: AbortSignal;
	body?: any;
	// Add more options as needed
};

export class BaseApiService {
	bearerToken: string;
	baseUrl: string;

	noAuthEndpoints: string[] = ["/auth/jwt/login", "/auth/register"];

	constructor(bearerToken: string, baseUrl: string) {
		this.bearerToken = bearerToken;
		this.baseUrl = baseUrl;
	}

	setBearerToken(bearerToken: string) {
		this.bearerToken = bearerToken;
	}

	async request<T>(
		url: string,
		body?: any,
		responseSchema?: z.ZodSchema<T>,
		options?: RequestOptions
	): Promise<T> {
		try {
			const defaultOptions: RequestOptions = {
				headers: {
					"Content-Type": "application/json",
					Authorization: `Bearer ${this.bearerToken || ""}`,
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

			// biome-ignore lint/suspicious: Unknown
			let requestBody;

			// Serialize body
			if (body) {
				if (mergedOptions.headers?.["Content-Type"].toLocaleLowerCase() === "application/json") {
					requestBody = JSON.stringify(body);
				}

				if (
					mergedOptions.headers?.["Content-Type"].toLocaleLowerCase() ===
					"application/x-www-form-urlencoded"
				) {
					requestBody = new URLSearchParams(body);
				}

				mergedOptions.body = requestBody;
			}

			if (!this.baseUrl) {
				throw new AppError("Base URL is not set.");
			}

			if (!this.bearerToken && !this.noAuthEndpoints.includes(url)) {
				throw new AuthenticationError("You are not authenticated. Please login again.");
			}

			const fullUrl = new URL(url, this.baseUrl).toString();

			const response = await fetch(fullUrl, mergedOptions);

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
		return this.request(url, undefined, responseSchema, {
			...options,
			method: "GET",
		});
	}

	async post<T>(
		url: string,
		body?: any,
		responseSchema?: z.ZodSchema<T>,
		options?: Omit<RequestOptions, "method">
	) {
		return this.request(url, body, responseSchema, {
			...options,
			method: "POST",
		});
	}

	async put<T>(
		url: string,
		body?: any,
		responseSchema?: z.ZodSchema<T>,
		options?: Omit<RequestOptions, "method">
	) {
		return this.request(url, body, responseSchema, {
			...options,
			method: "PUT",
		});
	}

	async delete<T>(
		url: string,
		body?: any,
		responseSchema?: z.ZodSchema<T>,
		options?: Omit<RequestOptions, "method">
	) {
		return this.request(url, body, responseSchema, {
			...options,
			method: "DELETE",
		});
	}
}

export const baseApiService = new BaseApiService(
	typeof window !== "undefined" ? localStorage.getItem("surfsense_bearer_token") || "" : "",
	process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL || ""
);
