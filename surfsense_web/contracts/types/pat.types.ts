import { z } from "zod";

export const pat = z.object({
	id: z.number(),
	label: z.string(),
	prefix: z.string(),
	expires_at: z.string().nullable(),
	last_used_at: z.string().nullable(),
	created_at: z.string(),
});

export const createPatRequest = z.object({
	label: z.string().min(1).max(120),
	expires_in_days: z.number().int().positive().nullable().optional(),
});

export const createPatResponse = z.object({
	id: z.number(),
	label: z.string(),
	token: z.string(),
	prefix: z.string(),
	expires_at: z.string().nullable(),
});

export const listPatsResponse = z.array(pat);
export const deletePatResponse = z.void();

export type PersonalAccessToken = z.infer<typeof pat>;
export type CreatePatRequest = z.infer<typeof createPatRequest>;
export type CreatedPat = z.infer<typeof createPatResponse>;
