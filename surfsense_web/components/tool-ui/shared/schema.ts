import { z } from "zod";

/**
 * Shared action schema for tool UI components
 */
export const ActionSchema = z.object({
	id: z.string(),
	label: z.string(),
	variant: z.enum(["default", "secondary", "destructive", "outline", "ghost", "link"]).optional(),
	disabled: z.boolean().optional(),
});

export type Action = z.infer<typeof ActionSchema>;

/**
 * Actions configuration schema
 */
export const ActionsConfigSchema = z.object({
	confirm: ActionSchema.optional(),
	cancel: ActionSchema.optional(),
});

export type ActionsConfig = z.infer<typeof ActionsConfigSchema>;
