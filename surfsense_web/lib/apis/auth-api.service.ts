import {
	type LoginRequest,
	loginRequest,
	loginResponse,
	type RegisterRequest,
	registerRequest,
	registerResponse,
	type Verify2FARequest,
	verify2FARequest,
	verify2FAResponse,
	type TwoFAStatusResponse,
	twoFAStatusResponse,
	type TwoFASetupResponse,
	twoFASetupResponse,
	type VerifyCodeRequest,
	verifyCodeRequest,
	type VerifySetupResponse,
	verifySetupResponse,
	type DisableRequest,
	disableRequest,
	type BackupCodesResponse,
	backupCodesResponse,
} from "@/contracts/types/auth.types";
import { z } from "zod";
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
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		// Create form data for the API request
		const formData = new URLSearchParams();
		formData.append("username", request.username);
		formData.append("password", request.password);
		formData.append("grant_type", "password");

		// Use the 2FA-aware login endpoint
		return baseApiService.post(`/api/v1/auth/2fa/login`, loginResponse, {
			body: formData.toString(),
			headers: {
				"Content-Type": "application/x-www-form-urlencoded",
			},
		});
	};

	verify2FA = async (request: Verify2FARequest) => {
		// Validate the request
		const parsedRequest = verify2FARequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid 2FA request:", parsedRequest.error);

			// Format a user friendly error message
			const errorMessage = parsedRequest.error.errors.map((err) => err.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.post(`/api/v1/auth/2fa/verify`, verify2FAResponse, {
			body: JSON.stringify(parsedRequest.data),
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

		return baseApiService.post(`/auth/register`, registerResponse, {
			body: JSON.stringify(parsedRequest.data),
		});
	};

	// 2FA Management methods
	get2FAStatus = async (): Promise<TwoFAStatusResponse> => {
		return baseApiService.get(`/api/v1/auth/2fa/status`, twoFAStatusResponse);
	};

	setup2FA = async (): Promise<TwoFASetupResponse> => {
		return baseApiService.post(`/api/v1/auth/2fa/setup`, twoFASetupResponse, {
			body: JSON.stringify({}),
		});
	};

	verifySetup2FA = async (request: VerifyCodeRequest): Promise<VerifySetupResponse> => {
		const parsedRequest = verifyCodeRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid verification request:", parsedRequest.error);
			const errorMessage = parsedRequest.error.errors.map((err) => err.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.post(`/api/v1/auth/2fa/verify-setup`, verifySetupResponse, {
			body: JSON.stringify(parsedRequest.data),
		});
	};

	disable2FA = async (request: DisableRequest): Promise<{ success: boolean; message: string }> => {
		const parsedRequest = disableRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid disable request:", parsedRequest.error);
			const errorMessage = parsedRequest.error.errors.map((err) => err.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.post(`/api/v1/auth/2fa/disable`,
			z.object({ success: z.boolean(), message: z.string() }), {
			body: JSON.stringify(parsedRequest.data),
		});
	};

	regenerateBackupCodes = async (request: VerifyCodeRequest): Promise<BackupCodesResponse> => {
		const parsedRequest = verifyCodeRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);
			const errorMessage = parsedRequest.error.errors.map((err) => err.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.post(`/api/v1/auth/2fa/backup-codes`, backupCodesResponse, {
			body: JSON.stringify(parsedRequest.data),
		});
	};
}

export const authApiService = new AuthApiService();
