import { z } from "zod";

export const purchaseStatusEnum = z.enum(["pending", "completed", "failed"]);

// ---------------------------------------------------------------------------
// Credit purchases ($1 packs that top up credit_micros_balance)
// ---------------------------------------------------------------------------

export const createCreditCheckoutSessionRequest = z.object({
	quantity: z.number().int().min(1).max(100),
	search_space_id: z.number().int().min(1),
});

export const createCreditCheckoutSessionResponse = z.object({
	checkout_url: z.string(),
});

// Credit balance availability + records. Unit is integer micro-USD
// (1_000_000 == $1.00); the FE divides by 1M when displaying.
export const creditStripeStatusResponse = z.object({
	credit_buying_enabled: z.boolean(),
	credit_micros_balance: z.number().default(0),
});

export const creditPurchase = z.object({
	id: z.uuid(),
	stripe_checkout_session_id: z.string(),
	stripe_payment_intent_id: z.string().nullable(),
	quantity: z.number(),
	credit_micros_granted: z.number(),
	amount_total: z.number().nullable(),
	currency: z.string().nullable(),
	source: z.string().default("checkout"),
	status: purchaseStatusEnum,
	completed_at: z.string().nullable(),
	created_at: z.string(),
});

export const getCreditPurchasesResponse = z.object({
	purchases: z.array(creditPurchase),
});

// ---------------------------------------------------------------------------
// Legacy page purchases (read-only history; page buying is removed)
// ---------------------------------------------------------------------------

export const pagePurchase = z.object({
	id: z.uuid(),
	stripe_checkout_session_id: z.string(),
	stripe_payment_intent_id: z.string().nullable(),
	quantity: z.number(),
	pages_granted: z.number(),
	amount_total: z.number().nullable(),
	currency: z.string().nullable(),
	status: purchaseStatusEnum,
	completed_at: z.string().nullable(),
	created_at: z.string(),
});

export const getPagePurchasesResponse = z.object({
	purchases: z.array(pagePurchase),
});

// Response from /stripe/finalize-checkout (credit purchases only).
export const finalizeCheckoutResponse = z.object({
	status: purchaseStatusEnum,
	credit_micros_balance: z.number().default(0),
	credit_micros_granted: z.number().nullable().optional(),
});

// ---------------------------------------------------------------------------
// Auto-reload (off-session top-up when the balance drops below a threshold)
// All *_micros fields are integer micro-USD (1_000_000 == $1.00).
// ---------------------------------------------------------------------------

export const autoReloadSettingsResponse = z.object({
	feature_enabled: z.boolean(),
	enabled: z.boolean().default(false),
	threshold_micros: z.number().nullable(),
	amount_micros: z.number().nullable(),
	min_amount_micros: z.number(),
	has_payment_method: z.boolean().default(false),
	failed_at: z.string().nullable(),
});

export const updateAutoReloadSettingsRequest = z.object({
	enabled: z.boolean(),
	threshold_micros: z.number().int().min(0).nullable().optional(),
	amount_micros: z.number().int().min(0).nullable().optional(),
});

export const createAutoReloadSetupSessionRequest = z.object({
	search_space_id: z.number().int().min(1),
});

export const createAutoReloadSetupSessionResponse = z.object({
	checkout_url: z.string(),
});

export type AutoReloadSettingsResponse = z.infer<typeof autoReloadSettingsResponse>;
export type UpdateAutoReloadSettingsRequest = z.infer<typeof updateAutoReloadSettingsRequest>;
export type CreateAutoReloadSetupSessionRequest = z.infer<
	typeof createAutoReloadSetupSessionRequest
>;
export type CreateAutoReloadSetupSessionResponse = z.infer<
	typeof createAutoReloadSetupSessionResponse
>;

export type PurchaseStatus = z.infer<typeof purchaseStatusEnum>;
export type CreateCreditCheckoutSessionRequest = z.infer<typeof createCreditCheckoutSessionRequest>;
export type CreateCreditCheckoutSessionResponse = z.infer<
	typeof createCreditCheckoutSessionResponse
>;
export type CreditStripeStatusResponse = z.infer<typeof creditStripeStatusResponse>;
export type CreditPurchase = z.infer<typeof creditPurchase>;
export type GetCreditPurchasesResponse = z.infer<typeof getCreditPurchasesResponse>;
export type PagePurchase = z.infer<typeof pagePurchase>;
export type GetPagePurchasesResponse = z.infer<typeof getPagePurchasesResponse>;
export type FinalizeCheckoutResponse = z.infer<typeof finalizeCheckoutResponse>;
