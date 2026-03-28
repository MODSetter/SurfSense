import { z } from "zod";

export type QuickAskActionMode = "transform" | "explore";

export const quickAskActionRead = z.object({
	id: z.number(),
	name: z.string(),
	prompt: z.string(),
	mode: z.enum(["transform", "explore"]),
	icon: z.string().nullable(),
	search_space_id: z.number().nullable(),
	created_at: z.string(),
});

export type QuickAskActionRead = z.infer<typeof quickAskActionRead>;

export const quickAskActionsListResponse = z.array(quickAskActionRead);

export const quickAskActionCreateRequest = z.object({
	name: z.string().min(1).max(200),
	prompt: z.string().min(1),
	mode: z.enum(["transform", "explore"]),
	icon: z.string().max(50).nullable().optional(),
	search_space_id: z.number().nullable().optional(),
});

export type QuickAskActionCreateRequest = z.infer<typeof quickAskActionCreateRequest>;

export const quickAskActionUpdateRequest = z.object({
	name: z.string().min(1).max(200).optional(),
	prompt: z.string().min(1).optional(),
	mode: z.enum(["transform", "explore"]).optional(),
	icon: z.string().max(50).nullable().optional(),
});

export type QuickAskActionUpdateRequest = z.infer<typeof quickAskActionUpdateRequest>;

export const quickAskActionDeleteResponse = z.object({
	success: z.boolean(),
});

export interface QuickAskAction {
	id: string;
	name: string;
	prompt: string;
	mode: QuickAskActionMode;
	icon: string;
	group: "transform" | "explore" | "knowledge" | "custom";
}
