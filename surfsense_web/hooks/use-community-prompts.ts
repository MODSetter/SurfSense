"use client";

import { useCallback, useEffect, useState } from "react";

export interface CommunityPrompt {
	key: string;
	value: string;
	author: string;
	link: string | null;
	category?: string;
}

export function useCommunityPrompts() {
	const [prompts, setPrompts] = useState<CommunityPrompt[]>([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	const fetchPrompts = useCallback(async () => {
		try {
			setLoading(true);
			const response = await fetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/searchspaces/prompts/community`
			);

			if (!response.ok) {
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
