/**
 * Attachment adapter for assistant-ui
 *
 * This adapter handles file uploads by:
 * 1. Uploading the file to the backend /attachments/process endpoint
 * 2. The backend extracts markdown content using the configured ETL service
 * 3. The extracted content is stored in the attachment and sent with messages
 */

import type { AttachmentAdapter, CompleteAttachment, PendingAttachment } from "@assistant-ui/react";
import { getBearerToken } from "@/lib/auth-utils";

/**
 * Supported file types for the attachment adapter
 *
 * - Text/Markdown: .md, .markdown, .txt
 * - Audio (if STT configured): .mp3, .mp4, .mpeg, .mpga, .m4a, .wav, .webm
 * - Documents (depends on ETL service): .pdf, .docx, .doc, .pptx, .xlsx, .html
 * - Images: .jpg, .jpeg, .png, .gif, .webp
 */
const ACCEPTED_FILE_TYPES = [
	// Text/Markdown (always supported)
	".md",
	".markdown",
	".txt",
	// Audio files
	".mp3",
	".mp4",
	".mpeg",
	".mpga",
	".m4a",
	".wav",
	".webm",
	// Document files (depends on ETL service)
	".pdf",
	".docx",
	".doc",
	".pptx",
	".xlsx",
	".html",
	// Image files
	".jpg",
	".jpeg",
	".png",
	".gif",
	".webp",
].join(",");

/**
 * Response from the attachment processing endpoint
 */
interface ProcessAttachmentResponse {
	id: string;
	name: string;
	type: "document" | "image" | "file";
	content: string;
	contentLength: number;
}

/**
 * Extended CompleteAttachment with our custom extractedContent field
 * We store the extracted text in a custom field so we can access it in onNew
 * For images, we also store the data URL so it can be displayed after persistence
 */
export interface ChatAttachment extends CompleteAttachment {
	extractedContent: string;
	imageDataUrl?: string; // Base64 data URL for images (persists across page reloads)
}

/**
 * Process a file through the backend ETL service
 */
async function processAttachment(file: File): Promise<ProcessAttachmentResponse> {
	const token = getBearerToken();
	if (!token) {
		throw new Error("Not authenticated");
	}

	const backendUrl = process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL || "http://localhost:8000";

	const formData = new FormData();
	formData.append("file", file);

	const response = await fetch(`${backendUrl}/api/v1/attachments/process`, {
		method: "POST",
		headers: {
			Authorization: `Bearer ${token}`,
		},
		body: formData,
	});

	if (!response.ok) {
		const errorText = await response.text();
		console.error("[processAttachment] Error response:", errorText);
		let errorDetail = "Unknown error";
		try {
			const errorJson = JSON.parse(errorText);
			// FastAPI validation errors return detail as array
			if (Array.isArray(errorJson.detail)) {
				errorDetail = errorJson.detail
					.map((err: { msg?: string; loc?: string[] }) => {
						const field = err.loc?.join(".") || "unknown";
						return `${field}: ${err.msg || "validation error"}`;
					})
					.join("; ");
			} else if (typeof errorJson.detail === "string") {
				errorDetail = errorJson.detail;
			} else {
				errorDetail = JSON.stringify(errorJson);
			}
		} catch {
			errorDetail = errorText || `HTTP ${response.status}`;
		}
		throw new Error(errorDetail);
	}

	return response.json();
}

// Store processed results for the send() method
const processedAttachments = new Map<string, ProcessAttachmentResponse>();

// Store image data URLs for attachments (so they persist after File objects are lost)
const imageDataUrls = new Map<string, string>();

/**
 * Convert a File to a data URL (base64) for images
 */
async function fileToDataUrl(file: File): Promise<string> {
	return new Promise((resolve, reject) => {
		const reader = new FileReader();
		reader.onload = () => resolve(reader.result as string);
		reader.onerror = reject;
		reader.readAsDataURL(file);
	});
}

/**
 * Create the attachment adapter for assistant-ui
 *
 * This adapter:
 * 1. Accepts file upload
 * 2. Processes the file through the backend ETL service
 * 3. Returns the attachment with extracted markdown content
 *
 * The content is stored in the attachment and will be sent with the message.
 */
export function createAttachmentAdapter(): AttachmentAdapter {
	return {
		accept: ACCEPTED_FILE_TYPES,

		/**
		 * Async generator that yields pending states while processing
		 * and returns a pending attachment when done.
		 *
		 * IMPORTANT: The generator should return status: { type: "running", progress: 100 }
		 * NOT status: { type: "complete" }. The "complete" status is set by send().
		 * Returning "complete" from the generator will prevent send() from being called!
		 *
		 * This pattern allows the UI to show a loading indicator
		 * while the file is being processed by the backend.
		 * The send() method is called to finalize the attachment.
		 */
		async *add(input: File | { file: File }): AsyncGenerator<PendingAttachment, void> {
			// Handle both direct File and { file: File } patterns
			const file = input instanceof File ? input : input.file;

			if (!file) {
				console.error("[AttachmentAdapter] No file found in input:", input);
				throw new Error("No file provided");
			}

			// Generate a unique ID for this attachment
			const id = crypto.randomUUID();

			// Determine attachment type from file
			const attachmentType = file.type.startsWith("image/") ? "image" : "document";

			// Yield initial pending state with "running" status (0% progress)
			// This triggers the loading indicator in the UI
			yield {
				id,
				type: attachmentType,
				name: file.name,
				file,
				status: { type: "running", reason: "uploading", progress: 0 },
			} as PendingAttachment;

			try {
				// For images, convert to data URL so we can display them after persistence
				if (attachmentType === "image") {
					const dataUrl = await fileToDataUrl(file);
					imageDataUrls.set(id, dataUrl);
				}

				// Process the file through the backend ETL service
				const result = await processAttachment(file);

				// Verify we have the required fields
				if (!result.content) {
					console.error("[AttachmentAdapter] WARNING: No content received from backend!");
				}

				// Store the processed result for send()
				processedAttachments.set(id, result);

				// Create the final pending attachment
				// IMPORTANT: Use "running" status with progress: 100 to indicate processing is done
				// but attachment is still pending. The "complete" status will be set by send().
				// Yield the final state to ensure it gets processed by the UI
				yield {
					id,
					type: result.type,
					name: result.name,
					file,
					status: { type: "running", reason: "uploading", progress: 100 },
				} as PendingAttachment;
			} catch (error) {
				console.error("[AttachmentAdapter] Failed to process attachment:", error);
				throw error;
			}
		},

		/**
		 * Called when user sends the message.
		 * Converts the pending attachment to a complete attachment.
		 */
		async send(pendingAttachment: PendingAttachment): Promise<ChatAttachment> {
			const result = processedAttachments.get(pendingAttachment.id);
			const imageDataUrl = imageDataUrls.get(pendingAttachment.id);

			if (result) {
				// Clean up stored result
				processedAttachments.delete(pendingAttachment.id);
				if (imageDataUrl) {
					imageDataUrls.delete(pendingAttachment.id);
				}

				return {
					id: result.id,
					type: result.type,
					name: result.name,
					contentType: "text/markdown",
					status: { type: "complete" },
					content: [
						{
							type: "text",
							text: result.content,
						},
					],
					extractedContent: result.content,
					imageDataUrl, // Store data URL for images so they can be displayed after persistence
				};
			}

			// Fallback if no processed result found
			console.warn(
				"[AttachmentAdapter] send() - No processed result found for attachment:",
				pendingAttachment.id
			);
			return {
				id: pendingAttachment.id,
				type: pendingAttachment.type,
				name: pendingAttachment.name,
				contentType: "text/plain",
				status: { type: "complete" },
				content: [],
				extractedContent: "",
				imageDataUrl, // Still include data URL if available
			};
		},

		async remove() {
			// No server-side cleanup needed since we don't persist attachments
		},
	};
}

/**
 * Extract attachment content for chat request
 *
 * This function extracts the content from attachments to be sent with the chat request.
 * Only attachments that have been fully processed (have content) will be included.
 */
export function extractAttachmentContent(
	attachments: Array<unknown>
): Array<{ id: string; name: string; type: string; content: string }> {
	return attachments
		.filter((att): att is ChatAttachment => {
			if (!att || typeof att !== "object") return false;
			const a = att as Record<string, unknown>;
			// Check for our custom extractedContent field first
			if (typeof a.extractedContent === "string" && a.extractedContent.length > 0) {
				return true;
			}
			// Fallback: check if content array has text content
			if (Array.isArray(a.content)) {
				const textContent = (a.content as Array<{ type: string; text?: string }>).find(
					(c) => c.type === "text" && typeof c.text === "string" && c.text.length > 0
				);
				return Boolean(textContent);
			}
			return false;
		})
		.map((att) => {
			// Get content from extractedContent or from content array
			let content = "";
			if (typeof att.extractedContent === "string") {
				content = att.extractedContent;
			} else if (Array.isArray(att.content)) {
				const textContent = (att.content as Array<{ type: string; text?: string }>).find(
					(c) => c.type === "text"
				);
				content = textContent?.text || "";
			}

			return {
				id: att.id,
				name: att.name,
				type: att.type,
				content,
			};
		});
}
