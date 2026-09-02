import { z } from "zod";

export const ArtifactFileSchema = z.object({
	file_id: z.number(),
	role: z.enum(["primary", "preview"]),
	filename: z.string(),
	mime_type: z.string(),
	size_bytes: z.number(),
	content_url: z.string(),
});

const ArtifactLegacySchema = z
	.object({
		kind: z.string(),
		id: z.number().int().positive(),
	})
	.optional();

export const ArtifactManifestSchema = z.object({
	artifact_id: z.number(),
	document_id: z.number(),
	title: z.string(),
	format: z.string(),
	generation: z.number().int().positive(),
	markdown_representation: z.string(),
	files: z.array(ArtifactFileSchema),
	updated_at: z.string().nullable(),
	legacy: ArtifactLegacySchema,
	flashcard_study_state: z.unknown().optional(),
	quiz_state: z.unknown().optional(),
});

export const ArtifactListItemSchema = z.object({
	artifact_id: z.number(),
	document_id: z.number(),
	title: z.string(),
	format: z.string(),
	generation: z.number().int().positive(),
	indexing_status: z.enum(["ready", "pending", "processing", "failed", "deleting"]),
	thread_id: z.number().nullable(),
	created_at: z.string(),
	updated_at: z.string().nullable(),
	legacy: ArtifactLegacySchema,
});

export const ArtifactListSchema = z.array(ArtifactListItemSchema);

export type ArtifactFile = z.infer<typeof ArtifactFileSchema>;
export type ArtifactManifest = z.infer<typeof ArtifactManifestSchema>;
export type ArtifactListItem = z.infer<typeof ArtifactListItemSchema>;
