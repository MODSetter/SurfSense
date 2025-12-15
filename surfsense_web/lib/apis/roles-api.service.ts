import {
	type CreateRoleRequest,
	createRoleRequest,
	createRoleResponse,
	type DeleteRoleRequest,
	deleteRoleRequest,
	deleteRoleResponse,
	type GetRoleByIdRequest,
	getRoleByIdRequest,
	getRoleByIdResponse,
	type GetRolesRequest,
	getRolesRequest,
	getRolesResponse,
	type UpdateRoleRequest,
	updateRoleRequest,
	updateRoleResponse,
} from "@/contracts/types/roles.types";
import { ValidationError } from "../error";
import { baseApiService } from "./base-api.service";

class RolesApiService {
	createRole = async (request: CreateRoleRequest) => {
		const parsedRequest = createRoleRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.errors.map((err) => err.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.post(
			`/api/searchspaces/${parsedRequest.data.search_space_id}/roles`,
			createRoleResponse,
			{
				body: parsedRequest.data.data,
			},
		);
	};
}

export const rolesApiService = new RolesApiService();
