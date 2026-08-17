import { z } from "zod";

export const DocumentViewFileSchema = z.object({
	file_id: z.number().int().positive(),
	filename: z.string(),
	mime_type: z.string(),
	size_bytes: z.number().nonnegative(),
	content_url: z.string(),
});

export const DocumentViewManifestSchema = z.object({
	document_id: z.number().int().positive(),
	title: z.string(),
	document_type: z.string(),
	status: z.string(),
	presentation: z.enum(["original", "text", "missing_original"]),
	file: DocumentViewFileSchema.nullable().optional(),
});

export type DocumentViewFile = z.infer<typeof DocumentViewFileSchema>;
export type DocumentViewManifest = z.infer<typeof DocumentViewManifestSchema>;
