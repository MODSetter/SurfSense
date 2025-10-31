import { useCallback, useEffect, useState } from "react";

export interface DocumentTypeCount {
	type: string;
	count: number;
}

/**
 * Hook to fetch document type counts from the API
 * @param searchSpaceId - The search space ID to filter document types
 * @param lazy - If true, types won't be fetched on mount
 */
export const useDocumentTypes = (searchSpaceId?: number, lazy: boolean = false) => {
	const [documentTypes, setDocumentTypes] = useState<DocumentTypeCount[]>([]);
	const [isLoading, setIsLoading] = useState(!lazy);
	const [isLoaded, setIsLoaded] = useState(false);
	const [error, setError] = useState<Error | null>(null);

	const fetchDocumentTypes = useCallback(
		async (spaceId?: number) => {
			if (isLoaded && lazy) return;

			try {
				setIsLoading(true);
				setError(null);
				const token = localStorage.getItem("surfsense_bearer_token");

				if (!token) {
					throw new Error("No authentication token found");
				}

				// Build URL with optional search_space_id query parameter
				const url = new URL(
					`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/documents/type-counts`
				);
				if (spaceId !== undefined) {
					url.searchParams.append("search_space_id", spaceId.toString());
				}

				const response = await fetch(url.toString(), {
					method: "GET",
					headers: {
						"Content-Type": "application/json",
						Authorization: `Bearer ${token}`,
					},
				});

				if (!response.ok) {
					throw new Error(`Failed to fetch document types: ${response.statusText}`);
				}

				const data = await response.json();

				// Convert the object to an array of DocumentTypeCount
				const typeCounts: DocumentTypeCount[] = Object.entries(data).map(([type, count]) => ({
					type,
					count: count as number,
				}));

				setDocumentTypes(typeCounts);
				setIsLoaded(true);

				return typeCounts;
			} catch (err) {
				setError(err instanceof Error ? err : new Error("An unknown error occurred"));
				console.error("Error fetching document types:", err);
			} finally {
				setIsLoading(false);
			}
		},
		[isLoaded, lazy]
	);

	useEffect(() => {
		if (!lazy) {
			fetchDocumentTypes(searchSpaceId);
		}
	}, [lazy, fetchDocumentTypes, searchSpaceId]);

	// Function to refresh the document types
	const refreshDocumentTypes = useCallback(
		async (spaceId?: number) => {
			setIsLoaded(false);
			await fetchDocumentTypes(spaceId !== undefined ? spaceId : searchSpaceId);
		},
		[fetchDocumentTypes, searchSpaceId]
	);

	return {
		documentTypes,
		isLoading,
		isLoaded,
		error,
		fetchDocumentTypes,
		refreshDocumentTypes,
	};
};
