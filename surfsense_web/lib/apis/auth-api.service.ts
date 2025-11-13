import {
	loginRequest,
	LoginRequest,
	loginResponse,
	registerRequest,
	RegisterRequest,
	registerResponse,
} from "@/contracts/types/auth.types";
import { baseApiService } from "./base-api.service";

export class AuthApiService {
	login = async (request: LoginRequest) => {
		// Validate the request
		const parsedRequest = loginRequest.safeParse(request);

		if (!parsedRequest.success) {
			throw new Error(`Invalid request: ${parsedRequest.error.message}`);
		}

		return baseApiService.post(`/auth/jwt/login`, parsedRequest.data, loginResponse, {
			contentType: "application/x-www-form-urlencoded",
		});
	};

	register = async (request: RegisterRequest) => {
		// Validate the request
		const parsedRequest = registerRequest.safeParse(request);

		if (!parsedRequest.success) {
			throw new Error(`Invalid request: ${parsedRequest.error.message}`);
		}

		return baseApiService.post(`/auth/register`, parsedRequest.data, registerResponse);
	};
}
