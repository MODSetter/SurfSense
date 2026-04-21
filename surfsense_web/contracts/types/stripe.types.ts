import { z } from "zod";

export const pagePurchaseStatusEnum = z.enum(["pending", "completed", "failed"]);

export const createCheckoutSessionRequest = z.object({
	quantity: z.number().int().min(1).max(100),
	search_space_id: z.number().int().min(1),
});

export const createCheckoutSessionResponse = z.object({
	checkout_url: z.string(),
});

export const stripeStatusResponse = z.object({
	page_buying_enabled: z.boolean(),
});

export const pagePurchase = z.object({
	id: z.uuid(),
	stripe_checkout_session_id: z.string(),
	stripe_payment_intent_id: z.string().nullable(),
	quantity: z.number(),
	pages_granted: z.number(),
	amount_total: z.number().nullable(),
	currency: z.string().nullable(),
	status: pagePurchaseStatusEnum,
	completed_at: z.string().nullable(),
	created_at: z.string(),
});

export const getPagePurchasesResponse = z.object({
	purchases: z.array(pagePurchase),
});

// Premium token purchases
export const createTokenCheckoutSessionRequest = z.object({
	quantity: z.number().int().min(1).max(100),
	search_space_id: z.number().int().min(1),
});

export const createTokenCheckoutSessionResponse = z.object({
	checkout_url: z.string(),
});

export const tokenStripeStatusResponse = z.object({
	token_buying_enabled: z.boolean(),
	premium_tokens_used: z.number().default(0),
	premium_tokens_limit: z.number().default(0),
	premium_tokens_remaining: z.number().default(0),
});

export const tokenPurchaseStatusEnum = pagePurchaseStatusEnum;

export const tokenPurchase = z.object({
	id: z.uuid(),
	stripe_checkout_session_id: z.string(),
	stripe_payment_intent_id: z.string().nullable(),
	quantity: z.number(),
	tokens_granted: z.number(),
	amount_total: z.number().nullable(),
	currency: z.string().nullable(),
	status: tokenPurchaseStatusEnum,
	completed_at: z.string().nullable(),
	created_at: z.string(),
});

export const getTokenPurchasesResponse = z.object({
	purchases: z.array(tokenPurchase),
});

export type PagePurchaseStatus = z.infer<typeof pagePurchaseStatusEnum>;
export type CreateCheckoutSessionRequest = z.infer<typeof createCheckoutSessionRequest>;
export type CreateCheckoutSessionResponse = z.infer<typeof createCheckoutSessionResponse>;
export type StripeStatusResponse = z.infer<typeof stripeStatusResponse>;
export type PagePurchase = z.infer<typeof pagePurchase>;
export type GetPagePurchasesResponse = z.infer<typeof getPagePurchasesResponse>;
export type CreateTokenCheckoutSessionRequest = z.infer<typeof createTokenCheckoutSessionRequest>;
export type CreateTokenCheckoutSessionResponse = z.infer<typeof createTokenCheckoutSessionResponse>;
export type TokenStripeStatusResponse = z.infer<typeof tokenStripeStatusResponse>;
export type TokenPurchaseStatus = z.infer<typeof tokenPurchaseStatusEnum>;
export type TokenPurchase = z.infer<typeof tokenPurchase>;
export type GetTokenPurchasesResponse = z.infer<typeof getTokenPurchasesResponse>;
