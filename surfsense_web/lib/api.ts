import { toast } from "sonner";
import { fetchWithCache, invalidateCache, cacheKeys } from "./apiCache";

type CacheTag = keyof typeof cacheKeys;

// Define a mapping of endpoints to cache tags
const ENDPOINT_CACHE_TAGS: Record<string, CacheTag> = {
  'api/v1/documents': 'documents',
  'api/v1/chats': 'chats',
  'api/v1/searchspaces': 'searchspaces',
  'api/v1/search-source-connectors': 'connectors',
  'api/v1/llm-configs': 'llmconfigs',
  'users/me': 'user'
};

// Helper to determine which cache tag to invalidate
function getCacheTagForEndpoint(path: string): CacheTag | undefined {
  for (const [endpoint, tag] of Object.entries(ENDPOINT_CACHE_TAGS)) {
    if (path.includes(endpoint)) {
      return tag as CacheTag; // Explicit cast to ensure type safety
    }
  }
  return undefined;
}

/**
 * Custom fetch wrapper that handles authentication and redirects to home page on 401 Unauthorized
 *
 * @param url - The URL to fetch
 * @param options - Fetch options
 * @returns The fetch response
 */
export async function fetchWithAuth(url: string, options: RequestInit = {}): Promise<Response> {
	// Only run on client-side
	if (typeof window === "undefined") {
		return fetch(url, options);
	}

	// Get token from localStorage
	const token = localStorage.getItem("surfsense_bearer_token");

	// Add authorization header if token exists
	const headers = {
		...options.headers,
		...(token && { Authorization: `Bearer ${token}` }),
	};

	// Make the request
	const response = await fetch(url, {
		...options,
		headers,
	});

	// Handle 401 Unauthorized response
	if (response.status === 401) {
		// Show error toast
		toast.error("Session expired. Please log in again.");

		// Clear token
		localStorage.removeItem("surfsense_bearer_token");

		// Redirect to home page
		window.location.href = "/";

		// Throw error to stop further processing
		throw new Error("Unauthorized: Redirecting to login page");
	}

	return response;
}

/**
 * Get the full API URL
 *
 * @param path - The API path
 * @returns The full API URL
 */
export function getApiUrl(path: string): string {
	// Remove leading slash if present
	const cleanPath = path.startsWith("/") ? path.slice(1) : path;

	// Get backend URL from environment variable
	const baseUrl = process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL;

	if (!baseUrl) {
		console.error("NEXT_PUBLIC_FASTAPI_BACKEND_URL is not defined");
		return "";
	}

	// Combine base URL and path
	return `${baseUrl}/${cleanPath}`;
}

/**
 * API client with methods for common operations
 */
export const apiClient = {
	/**
	 * Make a GET request
	 *
	 * @param path - The API path
	 * @param options - Additional fetch options
	 * @returns The response data
	 */
	async get<T>(
		path: string, 
		options: RequestInit = {}, 
		revalidate: number | false = 30 // Default 30 second cache
	): Promise<T> {
		const url = getApiUrl(path);
		
		if (typeof window === "undefined") {
		const response = await fetch(url, {
			method: "GET",
			...options,
		});
		
		if (!response.ok) {
			const errorData = await response.json().catch(() => null);
			throw new Error(`API error: ${response.status} ${errorData?.detail || response.statusText}`);
		}
		
		return response.json();
		}
		
		try {
			const token = localStorage.getItem("surfsense_bearer_token");
			const headers = {
				...options.headers,
				...(token && { Authorization: `Bearer ${token}` }),
			};
			
			// Determine the appropriate cache tag
			const tag = getCacheTagForEndpoint(path);
			
			return await fetchWithCache(url, {
				method: "GET",
				...options,
				headers,
				revalidate,
				tag
			});
		} catch (error) {
			if (error instanceof Error && error.message.includes('401')) {
				toast.error("Session expired. Please log in again.");
				localStorage.removeItem("surfsense_bearer_token");
				window.location.href = "/";
				throw new Error("Unauthorized: Redirecting to login page");
			}
			throw error;
		}
	},

	/**
	 * Make a POST request
	 *
	 * @param path - The API path
	 * @param data - The request body
	 * @param options - Additional fetch options
	 * @returns The response data
	 */
	async post<T>(path: string, data: any, options: RequestInit = {}): Promise<T> {
		const response = await fetchWithAuth(getApiUrl(path), {
			method: "POST",
			headers: {
				"Content-Type": "application/json",
				...options.headers,
			},
			body: JSON.stringify(data),
			...options,
		});

		if (!response.ok) {
			const errorData = await response.json().catch(() => null);
			throw new Error(`API error: ${response.status} ${errorData?.detail || response.statusText}`);
		}

		// Invalidate cache after successful mutation
		const tag = getCacheTagForEndpoint(path);
		if (tag) invalidateCache(tag);

		return response.json();
	},

	/**
	 * Make a PUT request
	 *
	 * @param path - The API path
	 * @param data - The request body
	 * @param options - Additional fetch options
	 * @returns The response data
	 */
	async put<T>(path: string, data: any, options: RequestInit = {}): Promise<T> {
		const response = await fetchWithAuth(getApiUrl(path), {
			method: "PUT",
			headers: {
				"Content-Type": "application/json",
				...options.headers,
			},
			body: JSON.stringify(data),
			...options,
		});

		if (!response.ok) {
			const errorData = await response.json().catch(() => null);
			throw new Error(`API error: ${response.status} ${errorData?.detail || response.statusText}`);
		}

		// Invalidate cache after successful mutation
		const tag = getCacheTagForEndpoint(path);
		if (tag) invalidateCache(tag);

		return response.json();
	},

	/**
	 * Make a DELETE request
	 *
	 * @param path - The API path
	 * @param options - Additional fetch options
	 * @returns The response data
	 */
	async delete<T>(path: string, options: RequestInit = {}): Promise<T> {
		const response = await fetchWithAuth(getApiUrl(path), {
			method: "DELETE",
			...options,
		});

		if (!response.ok) {
			const errorData = await response.json().catch(() => null);
			throw new Error(`API error: ${response.status} ${errorData?.detail || response.statusText}`);
		}

		// Invalidate cache after successful mutation
		const tag = getCacheTagForEndpoint(path);
		if (tag) invalidateCache(tag);

		return response.json();
	},
};