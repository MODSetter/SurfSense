import type { DocumentWithChunks } from "@/hooks/use-document-by-chunk";
import type { DocumentTypeCount } from "@/hooks/use-document-types";
import { normalizeListResponse } from "../pagination";

export const uploadDocument = async (formData: FormData, authToken: string) => {
	const response = await fetch(
		`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/documents/fileupload`,
		{
			method: "POST",
			headers: {
				Authorization: `Bearer ${authToken}`,
			},
			body: formData,
		}
	);

	if (!response.ok) {
		throw new Error("Failed to upload document");
	}

	return await response.json();
};

export const createDocument = async (request: {
	documentType: string;
	content: any;
	searchSpaceId: number;
	authToken: string;
}) => {
	const response = await fetch(`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/documents`, {
		method: "POST",
		headers: {
			"Content-Type": "application/json",
			Authorization: `Bearer ${request.authToken}`,
		},
		body: JSON.stringify(request),
	});

	if (!response.ok) {
		throw new Error("Failed to process document");
	}

	return await response.json();
};

export const fetchDocumentByChunk = async (chunkId: number, authToken: string) => {
	const response = await fetch(
		`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/documents/by-chunk/${chunkId}`,
		{
			headers: {
				Authorization: `Bearer ${authToken}`,
				"Content-Type": "application/json",
			},
			method: "GET",
		}
	);

	if (!response.ok) {
		const errorText = await response.text();
		let errorMessage = "Failed to fetch document";

		try {
			const errorData = JSON.parse(errorText);
			errorMessage = errorData.detail || errorMessage;
		} catch {
			// If parsing fails, use default message
		}

		if (response.status === 404) {
			errorMessage = "Chunk not found or you don't have access to it";
		}
		throw new Error(errorMessage);
	}

	const data: DocumentWithChunks = await response.json();

	return data;
};

export const fetchDocumentTypes = async (authToken: string) => {
	if (!authToken) {
		throw new Error("No authentication token found");
	}

	// Build URL with optional search_space_id query parameter
	const url = new URL(
		`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/documents/type-counts`
	);

	const response = await fetch(url.toString(), {
		method: "GET",
		headers: {
			"Content-Type": "application/json",
			Authorization: `Bearer ${authToken}`,
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

	return typeCounts;
};

export const fetchDocuments = async (
	searchSpaceId: number,
	authToken: string,
	fetchPage?: number,
	fetchPageSize?: number,
	fetchDocumentTypes?: string[]
) => {
	// Build query params
	const params = new URLSearchParams({
		search_space_id: searchSpaceId.toString(),
	});

	//   // Use passed parameters or fall back to state/options
	//   const effectivePage = fetchPage !== undefined ? fetchPage : page;
	//   const effectivePageSize =
	//     fetchPageSize !== undefined ? fetchPageSize : pageSize;
	//   const effectiveDocumentTypes =
	//     fetchDocumentTypes !== undefined ? fetchDocumentTypes : documentTypes;

	//   if (effectivePage !== undefined) {
	//     params.append("page", effectivePage.toString());
	//   }
	//   if (effectivePageSize !== undefined) {
	//     params.append("page_size", effectivePageSize.toString());
	//   }
	//   if (effectiveDocumentTypes && effectiveDocumentTypes.length > 0) {
	//     params.append("document_types", effectiveDocumentTypes.join(","));
	//   }

	const response = await fetch(
		`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/documents?${params.toString()}`,
		{
			headers: {
				Authorization: `Bearer ${authToken}`,
			},
			method: "GET",
		}
	);

	if (!response.ok) {
		throw new Error("Failed to fetch documents");
	}

	const data = await response.json();
	return normalizeListResponse<Document>(data);
};

export const searchDocuments = async (
	searchSpaceId: number,
	authToken: string,
	searchQuery: string,
	fetchPage?: number,
	fetchPageSize?: number,
	fetchDocumentTypes?: string[]
) => {
	// if (!searchQuery.trim()) {
	// 	// If search is empty, fetch all documents
	// 	// return fetchDocuments(fetchPage, fetchPageSize, fetchDocumentTypes);
	// }

	// Build query params
	const params = new URLSearchParams({
		search_space_id: searchSpaceId.toString(),
		title: searchQuery,
	});

	// // Use passed parameters or fall back to state/options
	// const effectivePage = fetchPage !== undefined ? fetchPage : page;
	// const effectivePageSize = fetchPageSize !== undefined ? fetchPageSize : pageSize;
	// const effectiveDocumentTypes =
	// 	fetchDocumentTypes !== undefined ? fetchDocumentTypes : documentTypes;

	// if (effectivePage !== undefined) {
	// 	params.append("page", effectivePage.toString());
	// }
	// if (effectivePageSize !== undefined) {
	// 	params.append("page_size", effectivePageSize.toString());
	// }
	// if (effectiveDocumentTypes && effectiveDocumentTypes.length > 0) {
	// 	params.append("document_types", effectiveDocumentTypes.join(","));
	// }

	const response = await fetch(
		`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/documents/search?${params.toString()}`,
		{
			headers: {
				Authorization: `Bearer ${authToken}`,
			},
			method: "GET",
		}
	);

	if (!response.ok) {
		throw new Error("Failed to search documents");
	}

	const data = await response.json();
	const normalized = normalizeListResponse<Document>(data);
	return normalized;
};

export const deleteDocument = async (documentId: number, authToken: string) => {
	const response = await fetch(
		`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/documents/${documentId}`,
		{
			headers: {
				Authorization: `Bearer ${authToken}`,
			},
			method: "DELETE",
		}
	);

	if (!response.ok) {
		throw new Error("Failed to delete document");
	}

	return await response.json();
};

export const getDocumentTypeCounts = async (searchSpaceId: number, authToken: string) => {
	try {
		const params = new URLSearchParams({
			search_space_id: searchSpaceId.toString(),
		});

		const response = await fetch(
			`${
				process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL
			}/api/v1/documents/type-counts?${params.toString()}`,
			{
				headers: {
					Authorization: `Bearer ${authToken}`,
				},
				method: "GET",
			}
		);

		if (!response.ok) {
			throw new Error("Failed to fetch document type counts");
		}

		const counts = await response.json();
		return counts as Record<string, number>;
	} catch (err: any) {
		console.error("Error fetching document type counts:", err);
		return {};
	}
};
