"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { authenticatedFetch } from "@/lib/auth-utils";

interface SearchSpace {
	created_at: string;
	id: number;
	name: string;
	description: string;
	user_id: string;
	citations_enabled: boolean;
	qna_custom_instructions: string | null;
}

interface UseSearchSpaceOptions {
	searchSpaceId: string | number;
	autoFetch?: boolean;
}

export function useSearchSpace({ searchSpaceId, autoFetch = true }: UseSearchSpaceOptions) {
	const [searchSpace, setSearchSpace] = useState<SearchSpace | null>(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	const fetchSearchSpace = useCallback(async () => {
		try {
			// Only run on client-side
			if (typeof window === "undefined") return;

			setLoading(true);
			const response = await authenticatedFetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/searchspaces/${searchSpaceId}`,
				{ method: "GET" }
			);

			if (!response.ok) {
				throw new Error(`Failed to fetch search space: ${response.status}`);
			}

			const data = await response.json();
			setSearchSpace(data);
			setError(null);
		} catch (err: any) {
			setError(err.message || "Failed to fetch search space");
			console.error("Error fetching search space:", err);
		} finally {
			setLoading(false);
		}
	}, [searchSpaceId]);

	useEffect(() => {
		if (autoFetch) {
			fetchSearchSpace();
		}
	}, [autoFetch, fetchSearchSpace]);

	return { searchSpace, loading, error, fetchSearchSpace };
}
