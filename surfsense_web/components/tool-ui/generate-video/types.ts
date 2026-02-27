import { z } from "zod";

export const MAX_ATTEMPTS = 3;
export const MIN_DURATION = 900;
export const MAX_DURATION = 9000;
export const DEFAULT_DURATION = 1800;

export const GenerateVideoArgsSchema = z.object({
	topic: z.string(),
	source_content: z.string(),
});

export const GenerateVideoResultSchema = z.object({
	status: z.literal("prompt_ready"),
	search_space_id: z.number(),
	topic: z.string(),
	source_content: z.string(),
});

export type GenerateVideoArgs = z.infer<typeof GenerateVideoArgsSchema>;
export type GenerateVideoResult = z.infer<typeof GenerateVideoResultSchema>;

export type Phase = "idle" | "generating" | "success" | "failed";
