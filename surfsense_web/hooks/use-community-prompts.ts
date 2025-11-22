"use client";

import { useCallback, useEffect, useState } from "react";

export interface CommunityPrompt {
	key: string;
	value: string;
	author: string;
	link: string | null;
	category?: string;
}

/**
 * Hook to fetch and manage community-curated prompts for SearchSpace system instructions.
 *
 * Features:
 * - Fetches prompts from the authenticated backend endpoint
 * - Provides loading and error states
 * - Supports manual refetch
 * - Categorized prompts (developer, general, creative, business, etc.)
 *
 * @returns Object containing prompts array, loading state, error, and refetch function
 *
 * @example
 * ```tsx
 * const { prompts, loading, error, refetch } = useCommunityPrompts();
 *
 * if (loading) return <Spinner />;
 * if (error) return <Error message={error} />;
 *
 * return (
 *   <Select>
 *     {prompts.map(p => <Option key={p.key} value={p.value}>{p.key}</Option>)}
 *   </Select>
 * );
 * ```
 */
export function useCommunityPrompts() {
	const [prompts, setPrompts] = useState<CommunityPrompt[]>([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	const fetchPrompts = useCallback(async () => {
		try {
			setLoading(true);

			// Get auth token for authenticated request
			const token = localStorage.getItem("surfsense_bearer_token");

			if (!token) {
				throw new Error("Authentication required to fetch community prompts");
			}

			const response = await fetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/searchspaces/prompts/community`,
				{
					headers: {
						Authorization: `Bearer ${token}`,
					},
				}
			);

			if (!response.ok) {
				if (response.status === 401) {
					throw new Error("Unauthorized: Please log in again");
				}
				throw new Error(`Failed to fetch community prompts: ${response.status}`);
			}

			const data = await response.json();
			setPrompts(data);
			setError(null);
		} catch (err: any) {
			setError(err.message || "Failed to fetch community prompts");
			console.error("Error fetching community prompts:", err);
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => {
		fetchPrompts();
	}, [fetchPrompts]);

	return { prompts, loading, error, refetch: fetchPrompts };
}
