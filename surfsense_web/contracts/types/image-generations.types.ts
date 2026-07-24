import { z } from "zod";

// =============================================================================
// Image generations — mirror app/schemas/image_generation.py.
// =============================================================================

export const imageGenerationListItem = z.object({
	id: z.number(),
	prompt: z.string(),
	workspace_id: z.number(),
	created_at: z.string(),
	is_success: z.boolean(),
	image_count: z.number().nullish(),
});
export type ImageGenerationListItem = z.infer<typeof imageGenerationListItem>;

export const imageGenerationList = z.array(imageGenerationListItem);

// Detail carries the raw provider response, which holds the displayable image
// as either a hosted url or inline base64.
export const imageGenerationDetail = z.object({
	id: z.number(),
	prompt: z.string(),
	response_data: z.record(z.string(), z.unknown()).nullish(),
	error_message: z.string().nullish(),
});
export type ImageGenerationDetail = z.infer<typeof imageGenerationDetail>;
