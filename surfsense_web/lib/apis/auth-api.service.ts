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
	type Disable2FAResponse,
	disable2FAResponse,
} from "@/contracts/types/auth.types";
import { z } from "zod";
import { ValidationError } from "../error";
import { baseApiService } from "./base-api.service";

export class AuthApiService {
	/**
	 * Private helper method to validate requests using Zod schemas
	 * @param schema - The Zod schema to validate against
	 * @param request - The request data to validate
	 * @param requestName - Name of the request for error messages
	 * @returns Validated and parsed request data
	 * @throws ValidationError if validation fails
	 */
	private _validateRequest<T>(
		schema: z.ZodSchema<T>,
		request: unknown,
		requestName: string
	): T {
		const parsedRequest = schema.safeParse(request);

		if (!parsedRequest.success) {
			console.error(`Invalid ${requestName}:`, parsedRequest.error);
			const errorMessage = parsedRequest.error.errors
				.map((err) => `${err.path.join(".")}: ${err.message}`)
				.join(", ");
			throw new ValidationError(`Invalid ${requestName}: ${errorMessage}`);
		}

		return parsedRequest.data;
	}

	login = async (request: LoginRequest) => {
		// Validate the request
		const validatedRequest = this._validateRequest(loginRequest, request, "login request");

		// Create form data for the API request
		const formData = new URLSearchParams();
		formData.append("username", validatedRequest.username);
		formData.append("password", validatedRequest.password);
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
		const validatedRequest = this._validateRequest(verify2FARequest, request, "2FA verification request");

		return baseApiService.post(`/api/v1/auth/2fa/verify`, verify2FAResponse, {
			body: JSON.stringify(validatedRequest),
		});
	};

	register = async (request: RegisterRequest) => {
		// Validate the request
		const validatedRequest = this._validateRequest(registerRequest, request, "registration request");

		return baseApiService.post(`/auth/register`, registerResponse, {
			body: JSON.stringify(validatedRequest),
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
		const validatedRequest = this._validateRequest(verifyCodeRequest, request, "verification request");

		return baseApiService.post(`/api/v1/auth/2fa/verify-setup`, verifySetupResponse, {
			body: JSON.stringify(validatedRequest),
		});
	};

	disable2FA = async (request: DisableRequest): Promise<Disable2FAResponse> => {
		const validatedRequest = this._validateRequest(disableRequest, request, "disable request");

		return baseApiService.post(`/api/v1/auth/2fa/disable`, disable2FAResponse, {
			body: JSON.stringify(validatedRequest),
		});
	};

	regenerateBackupCodes = async (request: VerifyCodeRequest): Promise<BackupCodesResponse> => {
		const validatedRequest = this._validateRequest(verifyCodeRequest, request, "backup codes request");

		return baseApiService.post(`/api/v1/auth/2fa/backup-codes`, backupCodesResponse, {
			body: JSON.stringify(validatedRequest),
		});
	};
}

export const authApiService = new AuthApiService();
