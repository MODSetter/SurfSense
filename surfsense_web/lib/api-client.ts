/**
 * Centralized API client with consistent error handling.
 *
 * This module provides a standardized way to make API requests with:
 * - Automatic authentication token handling
 * - Consistent error handling and user notifications
 * - Type-safe request/response handling
 * - Automatic redirect on authentication failures
 */

import { toast } from "sonner";
import { AUTH_TOKEN_KEY } from "@/lib/constants";

/**
 * Custom error class for API errors with structured information
 */
export class ApiError extends Error {
    constructor(
        public status: number,
        public detail: string,
        public originalError?: any
    ) {
        super(detail);
        this.name = "ApiError";
    }
}

/**
 * Configuration options for API requests
 */
export interface ApiRequestOptions extends RequestInit {
    /** Skip authentication token (for public endpoints) */
    skipAuth?: boolean;
    /** Skip automatic error notifications */
    skipErrorNotification?: boolean;
    /** Custom error handler (overrides default notifications) */
    onError?: (error: ApiError) => void;
}

/**
 * Make a type-safe API request with centralized error handling.
 *
 * @example
 * ```typescript
 * // Simple GET request
 * const spaces = await apiRequest<SearchSpace[]>('/api/v1/searchspaces');
 * if (spaces) {
 *   console.log(spaces.length); // Safe access after null check
 * }
 *
 * // POST request with body
 * const newSpace = await apiRequest<SearchSpace>('/api/v1/searchspaces', {
 *   method: 'POST',
 *   body: JSON.stringify({ name: 'My Space' })
 * });
 *
 * // Custom error handling
 * const result = await apiRequest<any>('/api/v1/some-endpoint', {
 *   onError: (error) => {
 *     if (error.status === 404) {
 *       // Handle 404 specifically
 *     }
 *   }
 * });
 * ```
 *
 * @param endpoint - API endpoint path (e.g., '/api/v1/searchspaces')
 * @param options - Request options including method, body, headers, etc.
 * @returns Promise resolving to the typed response data, or undefined for 204 No Content
 * @throws {ApiError} If the request fails
 */
export async function apiRequest<T = any>(
    endpoint: string,
    options: ApiRequestOptions = {}
): Promise<T | undefined> {
    const {
        skipAuth = false,
        skipErrorNotification = false,
        onError,
        headers = {},
        ...fetchOptions
    } = options;

    // Get authentication token
    const token = !skipAuth ? localStorage.getItem(AUTH_TOKEN_KEY) : null;

    // Check if authentication is required but missing
    if (!skipAuth && !token) {
        const error = new ApiError(401, "Authentication required. Please log in.");

        if (!skipErrorNotification) {
            toast.error("Authentication Required", {
                description: "Please log in to continue"
            });
        }

        // Throw error for global handler to manage navigation (preserves SPA flow)
        throw error;
    }

    // Build request headers
    const requestHeaders: HeadersInit = {
        'Content-Type': 'application/json',
        ...headers,
    };

    // Add authentication token if available
    if (token) {
        requestHeaders['Authorization'] = `Bearer ${token}`;
    }

    // Make the request
    try {
        const response = await fetch(
            `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}${endpoint}`,
            {
                ...fetchOptions,
                headers: requestHeaders,
            }
        );

        // Handle non-OK responses
        if (!response.ok) {
            await handleErrorResponse(response, skipErrorNotification, onError);
        }

        // Handle 204 No Content responses (empty body)
        if (response.status === 204) {
            return undefined;
        }

        // Parse and return successful response
        const data: T = await response.json();
        return data;
    } catch (error) {
        // Handle network errors or JSON parsing errors
        if (error instanceof ApiError) {
            throw error; // Re-throw ApiError as-is
        }

        const apiError = new ApiError(
            0,
            error instanceof Error ? error.message : "Network error occurred",
            error
        );

        if (!skipErrorNotification && !onError) {
            toast.error("Network Error", {
                description: "Could not connect to the server. Please check your connection."
            });
        }

        if (onError) {
            onError(apiError);
        }

        throw apiError;
    }
}

/**
 * Handle error responses with appropriate user notifications
 */
async function handleErrorResponse(
    response: Response,
    skipErrorNotification: boolean,
    onError?: (error: ApiError) => void
): Promise<never> {
    // Try to parse error details from response
    let errorData: any = {};
    let detail: string;

    try {
        errorData = await response.json();
        detail = errorData.detail || errorData.message || `Request failed with status ${response.status}`;
    } catch {
        detail = `Request failed with status ${response.status}`;
    }

    const error = new ApiError(response.status, detail, errorData);

    // Handle specific status codes with custom error handler
    if (onError) {
        onError(error);
        throw error;
    }

    // Default error notifications (if not skipped)
    if (!skipErrorNotification) {
        switch (response.status) {
            case 401:
                toast.error("Authentication Failed", {
                    description: "Your session has expired. Please log in again."
                });
                // Note: Navigation should be handled by global error handler to preserve SPA flow
                break;

            case 403:
                toast.error("Permission Denied", {
                    description: detail
                });
                break;

            case 404:
                toast.error("Not Found", {
                    description: detail
                });
                break;

            case 409:
                toast.error("Conflict", {
                    description: detail
                });
                break;

            case 422:
                toast.error("Validation Error", {
                    description: detail
                });
                break;

            case 429:
                toast.error("Rate Limit Exceeded", {
                    description: "Too many requests. Please try again later."
                });
                break;

            case 500:
            case 502:
            case 503:
            case 504:
                toast.error("Server Error", {
                    description: "An error occurred on the server. Please try again later."
                });
                break;

            default:
                toast.error("Request Failed", {
                    description: detail
                });
        }
    }

    throw error;
}

/**
 * Convenience method for GET requests
 */
export async function apiGet<T = any>(
    endpoint: string,
    options?: Omit<ApiRequestOptions, 'method' | 'body'>
): Promise<T | undefined> {
    return apiRequest<T>(endpoint, { ...options, method: 'GET' });
}

/**
 * Convenience method for POST requests
 */
export async function apiPost<T = any>(
    endpoint: string,
    body?: any,
    options?: Omit<ApiRequestOptions, 'method' | 'body'>
): Promise<T | undefined> {
    return apiRequest<T>(endpoint, {
        ...options,
        method: 'POST',
        body: body ? JSON.stringify(body) : undefined,
    });
}

/**
 * Convenience method for PUT requests
 */
export async function apiPut<T = any>(
    endpoint: string,
    body?: any,
    options?: Omit<ApiRequestOptions, 'method' | 'body'>
): Promise<T | undefined> {
    return apiRequest<T>(endpoint, {
        ...options,
        method: 'PUT',
        body: body ? JSON.stringify(body) : undefined,
    });
}

/**
 * Convenience method for PATCH requests
 */
export async function apiPatch<T = any>(
    endpoint: string,
    body?: any,
    options?: Omit<ApiRequestOptions, 'method' | 'body'>
): Promise<T | undefined> {
    return apiRequest<T>(endpoint, {
        ...options,
        method: 'PATCH',
        body: body ? JSON.stringify(body) : undefined,
    });
}

/**
 * Convenience method for DELETE requests
 */
export async function apiDelete<T = any>(
    endpoint: string,
    options?: Omit<ApiRequestOptions, 'method' | 'body'>
): Promise<T | undefined> {
    return apiRequest<T>(endpoint, { ...options, method: 'DELETE' });
}
