import {
	type CreateCheckoutSessionRequest,
	type CreateCheckoutSessionResponse,
	createCheckoutSessionResponse,
	type GetPagePurchasesResponse,
	getPagePurchasesResponse,
	type StripeStatusResponse,
	stripeStatusResponse,
} from "@/contracts/types/stripe.types";
import { baseApiService } from "./base-api.service";

class StripeApiService {
	createCheckoutSession = async (
		request: CreateCheckoutSessionRequest
	): Promise<CreateCheckoutSessionResponse> => {
		return baseApiService.post("/api/v1/stripe/create-checkout-session", createCheckoutSessionResponse, {
			body: request,
		});
	};

	getPurchases = async (): Promise<GetPagePurchasesResponse> => {
		return baseApiService.get("/api/v1/stripe/purchases", getPagePurchasesResponse);
	};

	getStatus = async (): Promise<StripeStatusResponse> => {
		return baseApiService.get("/api/v1/stripe/status", stripeStatusResponse);
	};
}

export const stripeApiService = new StripeApiService();
