import { getPermissionsResponse } from "@/contracts/types/permissions.types";
import { baseApiService } from "./base-api.service";

class PermissionsApiService {
	getPermissions = async () => {
		return baseApiService.get(`/api/v1/permissions`, getPermissionsResponse);
	};
}

export const permissionsApiService = new PermissionsApiService();
