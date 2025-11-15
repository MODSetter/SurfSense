import {
	type LoginRequest,
	loginRequest,
	loginResponse,
	type RegisterRequest,
	registerRequest,
	registerResponse,
} from "@/contracts/types/auth.types";
import { ValidationError } from "../error";
import { baseApiService } from "./base-api.service";

export class AuthApiService {
	login = async (request: LoginRequest) => {
		// Validate the request
		const parsedRequest = loginRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			// Format a user frendly error message
			const errorMessage = parsedRequest.error.errors.map((err) => err.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`, undefined, "VALLIDATION_ERROR");
		}

		return baseApiService.post(`/auth/jwt/login`, parsedRequest.data, loginResponse, {
			contentType: "application/x-www-form-urlencoded",
		});
	};

	register = async (request: RegisterRequest) => {
		// Validate the request
		const parsedRequest = registerRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			// Format a user frendly error message
			const errorMessage = parsedRequest.error.errors.map((err) => err.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.post(`/auth/register`, parsedRequest.data, registerResponse);
	};
}

export const authApiService = new AuthApiService();
