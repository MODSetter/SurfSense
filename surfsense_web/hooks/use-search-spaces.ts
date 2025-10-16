"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchWithCache, invalidateCache } from "@/lib/apiCache";
import { toast } from "sonner";

interface SearchSpace {
	id: number;
	name: string;
	description: string;
	created_at: string;
	// Add other fields from your SearchSpaceRead model
}

export function useSearchSpaces() {
	const [searchSpaces, setSearchSpaces] = useState<SearchSpace[]>([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	const fetchSearchSpaces = useCallback(async () => {
		try {
			setLoading(true);

			const data = await fetchWithCache(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/searchspaces/`,
				{
					headers: {
						Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
						'Cache-Control': 'no-store, max-age=0, must-revalidate',
  						'Pragma': 'no-cache'
					},
					method: "GET",
					revalidate: 60,
					tag: 'searchspaces'
				}
			).catch(err => {
				toast.error("Not authenticated");
				throw new Error("Not authenticated");
			});
			setSearchSpaces(data);
			setError(null);
		} catch (err: any) {
			setError(err.message || "Failed to fetch search spaces");
			console.error("Error fetching search spaces:", err);
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => {
		fetchSearchSpaces();
	}, [fetchSearchSpaces]);

	const refreshSearchSpaces = useCallback(async () => {
		try {
			setLoading(true);
			
			invalidateCache('searchspaces');
			
			const data = await fetchWithCache(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/searchspaces/`,
				{
					headers: {
						Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
						'Cache-Control': 'no-store, max-age=0, must-revalidate',
  						'Pragma': 'no-cache'
					},
					method: "GET",
					revalidate: 60,
					tag: 'searchspaces'
				}
			);
			
			setSearchSpaces(data);
			setError(null);
		} catch (err: any) {
			setError(err.message || "Failed to fetch search spaces");
			console.error("Error refreshing search spaces:", err);
		} finally {
			setLoading(false);
		}
	}, []);

	return { searchSpaces, loading, error, refreshSearchSpaces };
}