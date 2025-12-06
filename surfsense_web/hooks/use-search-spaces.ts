"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { authenticatedFetch } from "@/lib/auth-utils";

interface SearchSpace {
	id: number;
	name: string;
	description: string;
	created_at: string;
	citations_enabled: boolean;
	qna_custom_instructions: string | null;
	member_count: number;
	is_owner: boolean;
}

export function useSearchSpaces() {
	const [searchSpaces, setSearchSpaces] = useState<SearchSpace[]>([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		const fetchSearchSpaces = async () => {
			try {
				setLoading(true);
				const response = await authenticatedFetch(
					`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/searchspaces`,
					{ method: "GET" }
				);

				if (!response.ok) {
					toast.error("Failed to fetch search spaces");
					throw new Error("Failed to fetch search spaces");
				}

				const data = await response.json();
				setSearchSpaces(data);
				setError(null);
			} catch (err: any) {
				setError(err.message || "Failed to fetch search spaces");
				logger.error("Error fetching search spaces:", err);
			} finally {
				setLoading(false);
			}
		};

		fetchSearchSpaces();
	}, []);

	// Function to refresh the search spaces list
	const refreshSearchSpaces = async () => {
		setLoading(true);
		try {
			const response = await authenticatedFetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/searchspaces`,
				{ method: "GET" }
			);

			if (!response.ok) {
				toast.error("Failed to fetch search spaces");
				throw new Error("Failed to fetch search spaces");
			}

			const data = await response.json();
			setSearchSpaces(data);
			setError(null);
		} catch (err: any) {
			setError(err.message || "Failed to fetch search spaces");
		} finally {
			setLoading(false);
		}
	};

	return { searchSpaces, loading, error, refreshSearchSpaces };
}
