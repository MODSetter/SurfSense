import {
	type CreateDocumentRequest,
	createDocumentRequest,
	createDocumentResponse,
	type DeleteDocumentRequest,
	deleteDocumentRequest,
	deleteDocumentResponse,
	type GetDocumentByChunkRequest,
	type GetDocumentRequest,
	type GetDocumentsRequest,
	type GetDocumentTypeCountsRequest,
	type GetSurfsenseDocsRequest,
	getDocumentByChunkRequest,
	getDocumentByChunkResponse,
	getDocumentRequest,
	getDocumentResponse,
	getDocumentsRequest,
	getDocumentsResponse,
	getDocumentTypeCountsRequest,
	getDocumentTypeCountsResponse,
	getSurfsenseDocsByChunkResponse,
	getSurfsenseDocsRequest,
	getSurfsenseDocsResponse,
	type SearchDocumentsRequest,
	type SearchDocumentTitlesRequest,
	searchDocumentsRequest,
	searchDocumentsResponse,
	searchDocumentTitlesRequest,
	searchDocumentTitlesResponse,
	type UpdateDocumentRequest,
	type UploadDocumentRequest,
	updateDocumentRequest,
	updateDocumentResponse,
	uploadDocumentRequest,
	uploadDocumentResponse,
} from "@/contracts/types/document.types";
import { ValidationError } from "../error";
import { baseApiService } from "./base-api.service";

class DocumentsApiService {
	/**
	 * Get a list of documents with optional filtering and pagination
	 */
	getDocuments = async (request: GetDocumentsRequest) => {
		const parsedRequest = getDocumentsRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		// Transform query params to be string values
		const transformedQueryParams = parsedRequest.data.queryParams
			? Object.fromEntries(
					Object.entries(parsedRequest.data.queryParams).map(([k, v]) => {
						// Handle array values (document_type)
						if (Array.isArray(v)) {
							return [k, v.join(",")];
						}
						return [k, String(v)];
					})
				)
			: undefined;

		const queryParams = transformedQueryParams
			? new URLSearchParams(transformedQueryParams).toString()
			: "";

		return baseApiService.get(`/api/v1/documents?${queryParams}`, getDocumentsResponse);
	};

	/**
	 * Get a single document by ID
	 */
	getDocument = async (request: GetDocumentRequest) => {
		const parsedRequest = getDocumentRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.get(`/api/v1/documents/${request.id}`, getDocumentResponse);
	};

	/**
	 * Create documents (extension, crawled URL, or YouTube video)
	 */
	createDocument = async (request: CreateDocumentRequest) => {
		const parsedRequest = createDocumentRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.post(`/api/v1/documents`, createDocumentResponse, {
			body: parsedRequest.data,
		});
	};

	/**
	 * Upload document files
	 */
	uploadDocument = async (request: UploadDocumentRequest) => {
		const parsedRequest = uploadDocumentRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		// Create FormData for file upload
		const formData = new FormData();
		parsedRequest.data.files.forEach((file) => {
			formData.append("files", file);
		});
		formData.append("search_space_id", String(parsedRequest.data.search_space_id));

		return baseApiService.postFormData(`/api/v1/documents/fileupload`, uploadDocumentResponse, {
			body: formData,
		});
	};

	/**
	 * Search documents by title
	 */
	searchDocuments = async (request: SearchDocumentsRequest) => {
		const parsedRequest = searchDocumentsRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		// Transform query params to be string values
		const transformedQueryParams = parsedRequest.data.queryParams
			? Object.fromEntries(
					Object.entries(parsedRequest.data.queryParams).map(([k, v]) => {
						// Handle array values (document_type)
						if (Array.isArray(v)) {
							return [k, v.join(",")];
						}
						return [k, String(v)];
					})
				)
			: undefined;

		const queryParams = transformedQueryParams
			? new URLSearchParams(transformedQueryParams).toString()
			: "";

		return baseApiService.get(`/api/v1/documents/search?${queryParams}`, searchDocumentsResponse);
	};

	/**
	 * Search document titles (lightweight, optimized for mention picker)
	 * Returns only id, title, document_type - no content or metadata
	 * @param request - The search request with query params
	 * @param signal - Optional AbortSignal for request cancellation
	 */
	searchDocumentTitles = async (request: SearchDocumentTitlesRequest, signal?: AbortSignal) => {
		const parsedRequest = searchDocumentTitlesRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		// Transform query params to be string values
		const transformedQueryParams = Object.fromEntries(
			Object.entries(parsedRequest.data.queryParams)
				.filter(([, v]) => v !== undefined)
				.map(([k, v]) => [k, String(v)])
		);

		const queryParams = new URLSearchParams(transformedQueryParams).toString();

		return baseApiService.get(
			`/api/v1/documents/search/titles?${queryParams}`,
			searchDocumentTitlesResponse,
			{ signal }
		);
	};

	/**
	 * Get document type counts
	 */
	getDocumentTypeCounts = async (request: GetDocumentTypeCountsRequest) => {
		// Validate the request
		const parsedRequest = getDocumentTypeCountsRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			// Format a user friendly error message
			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		// Transform query params to be string values
		const transformedQueryParams = parsedRequest.data.queryParams
			? Object.fromEntries(
					Object.entries(parsedRequest.data.queryParams).map(([k, v]) => [k, String(v)])
				)
			: undefined;

		const queryParams = transformedQueryParams
			? new URLSearchParams(transformedQueryParams).toString()
			: "";

		return baseApiService.get(
			`/api/v1/documents/type-counts?${queryParams}`,
			getDocumentTypeCountsResponse
		);
	};

	/**
	 * Get document by chunk ID (includes all chunks)
	 */
	getDocumentByChunk = async (request: GetDocumentByChunkRequest) => {
		// Validate the request
		const parsedRequest = getDocumentByChunkRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			// Format a user friendly error message
			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.get(
			`/api/v1/documents/by-chunk/${request.chunk_id}`,
			getDocumentByChunkResponse
		);
	};

	/**
	 * Get Surfsense documentation by chunk ID
	 * Used for resolving [citation:doc-XXX] citations
	 */
	getSurfsenseDocByChunk = async (chunkId: number) => {
		return baseApiService.get(
			`/api/v1/surfsense-docs/by-chunk/${chunkId}`,
			getSurfsenseDocsByChunkResponse
		);
	};

	/**
	 * List all Surfsense documentation documents
	 * @param request - The request with query params
	 * @param signal - Optional AbortSignal for request cancellation
	 */
	getSurfsenseDocs = async (request: GetSurfsenseDocsRequest, signal?: AbortSignal) => {
		const parsedRequest = getSurfsenseDocsRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		// Transform query params to be string values
		const transformedQueryParams = parsedRequest.data.queryParams
			? Object.fromEntries(
					Object.entries(parsedRequest.data.queryParams).map(([k, v]) => [k, String(v)])
				)
			: undefined;

		const queryParams = transformedQueryParams
			? new URLSearchParams(transformedQueryParams).toString()
			: "";

		const url = `/api/v1/surfsense-docs?${queryParams}`;

		return baseApiService.get(url, getSurfsenseDocsResponse, { signal });
	};

	/**
	 * Update a document
	 */
	updateDocument = async (request: UpdateDocumentRequest) => {
		// Validate the request
		const parsedRequest = updateDocumentRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			// Format a user friendly error message
			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		const { id, data } = parsedRequest.data;

		return baseApiService.put(`/api/v1/documents/${id}`, updateDocumentResponse, {
			body: data,
		});
	};

	/**
	 * Delete a document
	 */
	deleteDocument = async (request: DeleteDocumentRequest) => {
		// Validate the request
		const parsedRequest = deleteDocumentRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			// Format a user friendly error message
			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.delete(`/api/v1/documents/${request.id}`, deleteDocumentResponse);
	};
}

export const documentsApiService = new DocumentsApiService();
