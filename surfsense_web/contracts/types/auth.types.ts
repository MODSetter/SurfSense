import { z } from "zod";

export const loginRequest = z.object({
	email: z.string().email(),
	password: z.string().min(1),
	grant_type: z.string().optional(),
});

export const loginResponse = z.object({
	access_token: z.string(),
	token_type: z.string(),
});

export const registerRequest = z.object({
	email: z.string().email(),
	password: z.string().min(1),
	is_active: z.boolean().optional(),
	is_superuser: z.boolean().optional(),
	is_verified: z.boolean().optional(),
});

export const registerResponse = z.object({
	id: z.number(),
	email: z.string().email(),
	is_active: z.boolean(),
	is_superuser: z.boolean(),
	is_verified: z.boolean(),
	pages_limit: z.number(),
	pages_used: z.number(),
});

export type LoginRequest = z.infer<typeof loginRequest>;
export type LoginResponse = z.infer<typeof loginResponse>;
export type RegisterRequest = z.infer<typeof registerRequest>;
export type RegisterResponse = z.infer<typeof registerResponse>;
