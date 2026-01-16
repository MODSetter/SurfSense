import {
	getMeResponse,
	type UpdateUserRequest,
	updateUserResponse,
} from "@/contracts/types/user.types";
import { baseApiService } from "./base-api.service";

class UserApiService {
	/**
	 * Get current authenticated user
	 */
	getMe = async () => {
		return baseApiService.get(`/users/me`, getMeResponse);
	};

	/**
	 * Update current authenticated user
	 */
	updateMe = async (request: UpdateUserRequest) => {
		return baseApiService.patch(`/users/me`, updateUserResponse, {
			body: request,
		});
	};
}

export const userApiService = new UserApiService();
