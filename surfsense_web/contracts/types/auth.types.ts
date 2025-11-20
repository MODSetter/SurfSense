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

// 2FA Management types
export const twoFAStatusResponse = z.object({
	enabled: z.boolean(),
	has_backup_codes: z.boolean(),
});

export const twoFASetupResponse = z.object({
	secret: z.string(),
	qr_code: z.string(),
	uri: z.string(),
});

export const verifyCodeRequest = z.object({
	code: z.string().min(1, "Code is required"),
});

export const verifySetupResponse = z.object({
	success: z.boolean(),
	backup_codes: z.array(z.string()).optional(),
});

export const disableRequest = z.object({
	code: z.string().min(1, "Code is required"),
});

export const backupCodesResponse = z.object({
	backup_codes: z.array(z.string()),
});

export const disable2FAResponse = z.object({
	success: z.boolean(),
	message: z.string(),
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
export type TwoFAStatusResponse = z.infer<typeof twoFAStatusResponse>;
export type TwoFASetupResponse = z.infer<typeof twoFASetupResponse>;
export type VerifyCodeRequest = z.infer<typeof verifyCodeRequest>;
export type VerifySetupResponse = z.infer<typeof verifySetupResponse>;
export type DisableRequest = z.infer<typeof disableRequest>;
export type BackupCodesResponse = z.infer<typeof backupCodesResponse>;
export type Disable2FAResponse = z.infer<typeof disable2FAResponse>;
export type RegisterRequest = z.infer<typeof registerRequest>;
export type RegisterResponse = z.infer<typeof registerResponse>;
