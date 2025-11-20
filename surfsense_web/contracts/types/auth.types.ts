import { z } from "zod";

export const loginRequest = z.object({
	username: z.string(),
	password: z.string().min(3, "Password must be at least 3 characters"),
	grant_type: z.string().optional(),
});

export const loginResponse = z.object({
	access_token: z.string().optional(),
	token_type: z.string().optional(),
	requires_2fa: z.boolean().optional(),
	temporary_token: z.string().optional(),
});

export const verify2FARequest = z.object({
	temporary_token: z.string(),
	code: z.string().length(6, "Code must be exactly 6 digits"),
});

export const verify2FAResponse = z.object({
	access_token: z.string(),
	token_type: z.string(),
});

export const registerRequest = loginRequest.omit({ grant_type: true, username: true }).extend({
	email: z.string().email("Invalid email address"),
	is_active: z.boolean().optional(),
	is_superuser: z.boolean().optional(),
	is_verified: z.boolean().optional(),
});

export const registerResponse = registerRequest.omit({ password: true }).extend({
	id: z.string(),
	pages_limit: z.number(),
	pages_used: z.number(),
});

export type LoginRequest = z.infer<typeof loginRequest>;
export type LoginResponse = z.infer<typeof loginResponse>;
export type Verify2FARequest = z.infer<typeof verify2FARequest>;
export type Verify2FAResponse = z.infer<typeof verify2FAResponse>;
export type RegisterRequest = z.infer<typeof registerRequest>;
export type RegisterResponse = z.infer<typeof registerResponse>;
