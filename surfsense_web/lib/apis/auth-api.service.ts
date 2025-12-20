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

class AuthApiService {
	login = async (request: LoginRequest) => {
		// Validate the request
		const parsedRequest = loginRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			// Format a user frendly error message
			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		// Create form data for the API request
		const formData = new URLSearchParams();
		formData.append("username", request.username);
		formData.append("password", request.password);
		formData.append("grant_type", "password");

		return baseApiService.post(`/auth/jwt/login`, loginResponse, {
			body: formData.toString(),
			headers: {
				"Content-Type": "application/x-www-form-urlencoded",
			},
		});
	};

	register = async (request: RegisterRequest) => {
		// Validate the request
		const parsedRequest = registerRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			// Format a user frendly error message
			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.post(`/auth/register`, registerResponse, {
			body: parsedRequest.data,
		});
	};
}

export const authApiService = new AuthApiService();
