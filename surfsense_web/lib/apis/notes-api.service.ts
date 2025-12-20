import { z } from "zod";
import { ValidationError } from "../error";
import { baseApiService } from "./base-api.service";

// Request/Response schemas
const createNoteRequest = z.object({
	search_space_id: z.number(),
	title: z.string().min(1),
	blocknote_document: z.array(z.any()).optional(),
});

const createNoteResponse = z.object({
	id: z.number(),
	title: z.string(),
	document_type: z.string(),
	content: z.string(),
	content_hash: z.string(),
	unique_identifier_hash: z.string().nullable(),
	document_metadata: z.record(z.string(), z.any()).nullable(),
	search_space_id: z.number(),
	created_at: z.string(),
	updated_at: z.string().nullable(),
});

const getNotesRequest = z.object({
	search_space_id: z.number(),
	skip: z.number().optional(),
	page: z.number().optional(),
	page_size: z.number().optional(),
});

const noteItem = z.object({
	id: z.number(),
	title: z.string(),
	document_type: z.string(),
	content: z.string(),
	content_hash: z.string(),
	unique_identifier_hash: z.string().nullable(),
	document_metadata: z.record(z.string(), z.any()).nullable(),
	search_space_id: z.number(),
	created_at: z.string(),
	updated_at: z.string().nullable(),
});

const getNotesResponse = z.object({
	items: z.array(noteItem),
	total: z.number(),
	page: z.number(),
	page_size: z.number(),
	has_more: z.boolean(),
});

const deleteNoteRequest = z.object({
	search_space_id: z.number(),
	note_id: z.number(),
});

const deleteNoteResponse = z.object({
	message: z.string(),
	note_id: z.number(),
});

// Type exports
export type CreateNoteRequest = z.infer<typeof createNoteRequest>;
export type CreateNoteResponse = z.infer<typeof createNoteResponse>;
export type GetNotesRequest = z.infer<typeof getNotesRequest>;
export type GetNotesResponse = z.infer<typeof getNotesResponse>;
export type NoteItem = z.infer<typeof noteItem>;
export type DeleteNoteRequest = z.infer<typeof deleteNoteRequest>;
export type DeleteNoteResponse = z.infer<typeof deleteNoteResponse>;

class NotesApiService {
	/**
	 * Create a new note
	 */
	createNote = async (request: CreateNoteRequest) => {
		const parsedRequest = createNoteRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);
			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		const { search_space_id, title, blocknote_document } = parsedRequest.data;

		// Send both title and blocknote_document in request body
		const body = {
			title,
			...(blocknote_document && { blocknote_document }),
		};

		return baseApiService.post(
			`/api/v1/search-spaces/${search_space_id}/notes`,
			createNoteResponse,
			{ body }
		);
	};

	/**
	 * Get list of notes
	 */
	getNotes = async (request: GetNotesRequest) => {
		const parsedRequest = getNotesRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);
			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		const { search_space_id, skip, page, page_size } = parsedRequest.data;

		// Build query params
		const params = new URLSearchParams();
		if (skip !== undefined) params.append("skip", String(skip));
		if (page !== undefined) params.append("page", String(page));
		if (page_size !== undefined) params.append("page_size", String(page_size));

		return baseApiService.get(
			`/api/v1/search-spaces/${search_space_id}/notes?${params.toString()}`,
			getNotesResponse
		);
	};

	/**
	 * Delete a note
	 */
	deleteNote = async (request: DeleteNoteRequest) => {
		const parsedRequest = deleteNoteRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);
			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		const { search_space_id, note_id } = parsedRequest.data;

		return baseApiService.delete(
			`/api/v1/search-spaces/${search_space_id}/notes/${note_id}`,
			deleteNoteResponse
		);
	};
}

export const notesApiService = new NotesApiService();
