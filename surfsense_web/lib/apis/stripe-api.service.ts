import {
	type CreateCheckoutSessionRequest,
	type CreateCheckoutSessionResponse,
	type CreateTokenCheckoutSessionRequest,
	type CreateTokenCheckoutSessionResponse,
	createCheckoutSessionResponse,
	createTokenCheckoutSessionResponse,
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
}

export const stripeApiService = new StripeApiService();
