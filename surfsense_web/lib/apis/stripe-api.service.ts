import {
	type CreateCheckoutSessionRequest,
	type CreateCheckoutSessionResponse,
	type CreateTokenCheckoutSessionRequest,
	type CreateTokenCheckoutSessionResponse,
	createCheckoutSessionResponse,
	createTokenCheckoutSessionResponse,
	type FinalizeCheckoutResponse,
	finalizeCheckoutResponse,
	type GetPagePurchasesResponse,
	type GetTokenPurchasesResponse,
	getPagePurchasesResponse,
	getTokenPurchasesResponse,
	type StripeStatusResponse,
	stripeStatusResponse,
	type TokenStripeStatusResponse,
	tokenStripeStatusResponse,
} from "@/contracts/types/stripe.types";
import { baseApiService } from "./base-api.service";

class StripeApiService {
	createCheckoutSession = async (
		request: CreateCheckoutSessionRequest
	): Promise<CreateCheckoutSessionResponse> => {
		return baseApiService.post(
			"/api/v1/stripe/create-checkout-session",
			createCheckoutSessionResponse,
			{
				body: request,
			}
		);
	};

	getPurchases = async (): Promise<GetPagePurchasesResponse> => {
		return baseApiService.get("/api/v1/stripe/purchases", getPagePurchasesResponse);
	};

	getStatus = async (): Promise<StripeStatusResponse> => {
		return baseApiService.get("/api/v1/stripe/status", stripeStatusResponse);
	};

	createTokenCheckoutSession = async (
		request: CreateTokenCheckoutSessionRequest
	): Promise<CreateTokenCheckoutSessionResponse> => {
		return baseApiService.post(
			"/api/v1/stripe/create-token-checkout-session",
			createTokenCheckoutSessionResponse,
			{ body: request }
		);
	};

	getTokenStatus = async (): Promise<TokenStripeStatusResponse> => {
		return baseApiService.get("/api/v1/stripe/token-status", tokenStripeStatusResponse);
	};

	getTokenPurchases = async (): Promise<GetTokenPurchasesResponse> => {
		return baseApiService.get("/api/v1/stripe/token-purchases", getTokenPurchasesResponse);
	};

	/**
	 * Synchronously fulfil a checkout session from the success page.
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
}

export const stripeApiService = new StripeApiService();
