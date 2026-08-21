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

	/**
	 * Delete the current account. Locks it out immediately; the erase follows.
	 */
	deleteMe = async () => {
		return baseApiService.delete(`/users/me`);
	};
}

export const userApiService = new UserApiService();
