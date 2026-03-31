import { z } from "zod";
import { ToolUIIdSchema, ToolUIReceiptSchema, ToolUIRoleSchema } from "../shared/schema";

export const CitationTypeSchema = z.enum([
	"webpage",
	"document",
	"article",
	"api",
	"code",
	"other",
]);

export type CitationType = z.infer<typeof CitationTypeSchema>;

export const CitationVariantSchema = z.enum(["default", "inline", "stacked"]);

export type CitationVariant = z.infer<typeof CitationVariantSchema>;

export const SerializableCitationSchema = z.object({
	id: ToolUIIdSchema,
	role: ToolUIRoleSchema.optional(),
	receipt: ToolUIReceiptSchema.optional(),
	href: z.string().url(),
	title: z.string(),
	snippet: z.string().optional(),
	domain: z.string().optional(),
	favicon: z.string().url().optional(),
	author: z.string().optional(),
	publishedAt: z.string().datetime().optional(),
	type: CitationTypeSchema.optional(),
	locale: z.string().optional(),
});

export type SerializableCitation = z.infer<typeof SerializableCitationSchema>;
