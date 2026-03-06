import { z } from "zod";

export const GenerateVideoArgsSchema = z.object({
	topic: z.string(),
	source_content: z.string(),
});

export const GenerateVideoResultSchema = z.object({
	status: z.enum(["success", "error"]),
	topic: z.string(),
	source_content: z.string().optional(),
	search_space_id: z.number().optional(),
	error: z.string().optional(),
});

export type GenerateVideoArgs = z.infer<typeof GenerateVideoArgsSchema>;
export type GenerateVideoResult = z.infer<typeof GenerateVideoResultSchema>;
