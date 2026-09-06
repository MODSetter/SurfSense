import { z } from "zod";

export const purchaseStatusEnum = z.enum(["pending", "completed", "failed"]);

// ---------------------------------------------------------------------------
// Credit purchases ($1 packs that top up credit_micros_balance)
// ---------------------------------------------------------------------------

export const createCreditCheckoutSessionRequest = z.object({
	quantity: z.number().int().min(1).max(10_000),
	workspace_id: z.number().int().min(1),
});

export const createCreditCheckoutSessionResponse = z.object({
	checkout_url: z.string(),
});

// Credit balance availability + records. Unit is integer micro-USD
// (1_000_000 == $1.00); the FE divides by 1M when displaying.
//
// The wallet has two buckets: `credit_micros_allowance` is the plan grant,
// which resets every period, and `credit_micros_balance` is permanent money
// from purchases. A debit spends the allowance first, so a display that reads
// either one alone under-reports what the user can actually spend — use
// `spendableMicros` below.
export const creditStripeStatusResponse = z.object({
	credit_buying_enabled: z.boolean(),
	credit_micros_balance: z.number().default(0),
	credit_micros_allowance: z.number().default(0),
	// What the plan grants per period, where the field above is what is left of
	// it. Both are needed to render "$2.40 of $6.00"; the amounts come from the
	// backend rather than being keyed off the plan name here, because they are
	// environment-overridable and a hardcoded copy would drift.
	allowance_granted_micros: z.number().default(0),
	allowance_period_end: z.string().nullable().default(null),
	plan: z.string().default("free"),
});

/**
 * Total credit a user can spend right now, across both wallet buckets.
 *
 * Mirrors `wallet_credit.funds_micros` on the backend, including the clamp: an
 * allowance is never negative, but a balance can be, because a job's real cost
 * can exceed the estimate it was pre-charged against.
 */
export function spendableMicros(allowanceMicros: number, balanceMicros: number): number {
	return Math.max(0, allowanceMicros) + balanceMicros;
}

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
	workspace_id: z.number().int().min(1),
});

export const createAutoReloadSetupSessionResponse = z.object({
	checkout_url: z.string(),
});

// ---------------------------------------------------------------------------
// Subscription (Pro plan)
// ---------------------------------------------------------------------------

export const createSubscriptionCheckoutSessionRequest = z.object({
	workspace_id: z.number().int().min(1),
});

export const createSubscriptionCheckoutSessionResponse = z.object({
	checkout_url: z.string(),
});

// `period_end` is when the current allowance expires, ISO-8601 or null for an
// account that has never been on a period. `subscription_available` is false
// when the deployment has no Pro price configured — every self-hosted install,
// so the upgrade path has to hide rather than fail.
export const planStatusResponse = z.object({
	plan: z.string(),
	allowance_micros: z.number().default(0),
	period_end: z.string().nullable().default(null),
	credit_micros_balance: z.number().default(0),
	subscription_available: z.boolean().default(false),
});

export type AutoReloadSettingsResponse = z.infer<typeof autoReloadSettingsResponse>;
export type UpdateAutoReloadSettingsRequest = z.infer<typeof updateAutoReloadSettingsRequest>;
export type CreateAutoReloadSetupSessionRequest = z.infer<
	typeof createAutoReloadSetupSessionRequest
>;
export type CreateAutoReloadSetupSessionResponse = z.infer<
	typeof createAutoReloadSetupSessionResponse
>;
export type CreateSubscriptionCheckoutSessionRequest = z.infer<
	typeof createSubscriptionCheckoutSessionRequest
>;
export type CreateSubscriptionCheckoutSessionResponse = z.infer<
	typeof createSubscriptionCheckoutSessionResponse
>;
export type PlanStatusResponse = z.infer<typeof planStatusResponse>;

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
