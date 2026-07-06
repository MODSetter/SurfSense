import {
	type AutoReloadSettingsResponse,
	autoReloadSettingsResponse,
	type CreateAutoReloadSetupSessionRequest,
	type CreateAutoReloadSetupSessionResponse,
	type CreateCreditCheckoutSessionRequest,
	type CreateCreditCheckoutSessionResponse,
	type CreditStripeStatusResponse,
	createAutoReloadSetupSessionResponse,
	createCreditCheckoutSessionResponse,
	creditStripeStatusResponse,
	type FinalizeCheckoutResponse,
	finalizeCheckoutResponse,
	type GetCreditPurchasesResponse,
	type GetPagePurchasesResponse,
	getCreditPurchasesResponse,
	getPagePurchasesResponse,
	type UpdateAutoReloadSettingsRequest,
} from "@/contracts/types/stripe.types";
import { baseApiService } from "./base-api.service";

class StripeApiService {
	createCreditCheckoutSession = async (
		request: CreateCreditCheckoutSessionRequest
	): Promise<CreateCreditCheckoutSessionResponse> => {
		const { search_space_id, ...body } = request;
		return baseApiService.post(
			"/api/v1/stripe/create-credit-checkout-session",
			createCreditCheckoutSessionResponse,
			{ body: { ...body, workspace_id: search_space_id } }
		);
	};

	getCreditStatus = async (): Promise<CreditStripeStatusResponse> => {
		return baseApiService.get("/api/v1/stripe/credit-status", creditStripeStatusResponse);
	};

	getCreditPurchases = async (): Promise<GetCreditPurchasesResponse> => {
		return baseApiService.get("/api/v1/stripe/credit-purchases", getCreditPurchasesResponse);
	};

	/** Legacy page-purchase history (read-only; page buying is removed). */
	getPagePurchases = async (): Promise<GetPagePurchasesResponse> => {
		return baseApiService.get("/api/v1/stripe/purchases", getPagePurchasesResponse);
	};

	/**
	 * Synchronously fulfil a credit checkout session from the success page.
	 *
	 * Solves the race where the user lands on /purchase-success before
	 * Stripe's checkout.session.completed webhook arrives. Idempotent —
	 * safe to call concurrently with the webhook.
	 */
	finalizeCheckout = async (sessionId: string): Promise<FinalizeCheckoutResponse> => {
		return baseApiService.get(
			`/api/v1/stripe/finalize-checkout?session_id=${encodeURIComponent(sessionId)}`,
			finalizeCheckoutResponse
		);
	};

	// --- Auto-reload --------------------------------------------------------

	getAutoReloadSettings = async (): Promise<AutoReloadSettingsResponse> => {
		return baseApiService.get("/api/v1/stripe/auto-reload", autoReloadSettingsResponse);
	};

	updateAutoReloadSettings = async (
		request: UpdateAutoReloadSettingsRequest
	): Promise<AutoReloadSettingsResponse> => {
		return baseApiService.put("/api/v1/stripe/auto-reload", autoReloadSettingsResponse, {
			body: request,
		});
	};

	createAutoReloadSetupSession = async (
		request: CreateAutoReloadSetupSessionRequest
	): Promise<CreateAutoReloadSetupSessionResponse> => {
		const { search_space_id } = request;
		return baseApiService.post(
			"/api/v1/stripe/auto-reload/setup",
			createAutoReloadSetupSessionResponse,
			{ body: { workspace_id: search_space_id } }
		);
	};
}

export const stripeApiService = new StripeApiService();
