import { z } from "zod";

export const ArtifactFileSchema = z.object({
	file_id: z.number(),
	role: z.enum(["primary", "preview"]),
	filename: z.string(),
	mime_type: z.string(),
	size_bytes: z.number(),
	content_url: z.string(),
});

export const ArtifactContentSchema = z.discriminatedUnion("kind", [
	z.object({
		kind: z.literal("text"),
		document_id: z.number(),
		title: z.string(),
		source_markdown: z.string(),
		generated: z.boolean(),
		updated_at: z.string().nullable(),
	}),
	z.object({
		kind: z.literal("file"),
		document_id: z.number(),
		title: z.string(),
		generated: z.boolean(),
		files: z.array(ArtifactFileSchema),
		updated_at: z.string().nullable(),
	}),
]);

export type ArtifactFile = z.infer<typeof ArtifactFileSchema>;
export type ArtifactContent = z.infer<typeof ArtifactContentSchema>;
export type TextArtifactContent = Extract<ArtifactContent, { kind: "text" }>;
export type FileArtifactContent = Extract<ArtifactContent, { kind: "file" }>;
