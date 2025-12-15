import { getMeResponse } from "@/contracts/types/user.types";
import { baseApiService } from "./base-api.service";

class UserApiService {
	/**
	 * Get current authenticated user
	 */
	getMe = async () => {
		return baseApiService.get(`/users/me`, getMeResponse);
	};
}

export const userApiService = new UserApiService();
