"use client";

import { useEffect, useState } from "react";
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

	useEffect(() => {
		const fetchSearchSpaces = async () => {
			try {
				setLoading(true);
				const response = await fetch(
					`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/searchspaces`,
					{
						headers: {
							Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
						},
						method: "GET",
					}
				);

				if (!response.ok) {
					toast.error("Not authenticated");
					throw new Error("Not authenticated");
				}

				const data = await response.json();
				setSearchSpaces(data);
				setError(null);
			} catch (err: any) {
				setError(err.message || "Failed to fetch search spaces");
				console.error("Error fetching search spaces:", err);
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
			const response = await fetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/searchspaces`,
				{
					headers: {
						Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
					},
					method: "GET",
				}
			);

			if (!response.ok) {
				toast.error("Not authenticated");
				throw new Error("Not authenticated");
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
