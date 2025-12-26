import {
	type CreateRoleRequest,
	createRoleRequest,
	createRoleResponse,
	type DeleteRoleRequest,
	deleteRoleRequest,
	deleteRoleResponse,
	type GetRoleByIdRequest,
	type GetRolesRequest,
	getRoleByIdRequest,
	getRoleByIdResponse,
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

			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.post(
			`/api/v1/searchspaces/${parsedRequest.data.search_space_id}/roles`,
			createRoleResponse,
			{
				body: parsedRequest.data.data,
			}
		);
	};

	getRoles = async (request: GetRolesRequest) => {
		const parsedRequest = getRolesRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.get(
			`/api/v1/searchspaces/${parsedRequest.data.search_space_id}/roles`,
			getRolesResponse
		);
	};

	getRoleById = async (request: GetRoleByIdRequest) => {
		const parsedRequest = getRoleByIdRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.get(
			`/api/v1/searchspaces/${parsedRequest.data.search_space_id}/roles/${parsedRequest.data.role_id}`,
			getRoleByIdResponse
		);
	};

	updateRole = async (request: UpdateRoleRequest) => {
		const parsedRequest = updateRoleRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.put(
			`/api/v1/searchspaces/${parsedRequest.data.search_space_id}/roles/${parsedRequest.data.role_id}`,
			updateRoleResponse,
			{
				body: parsedRequest.data.data,
			}
		);
	};

	deleteRole = async (request: DeleteRoleRequest) => {
		const parsedRequest = deleteRoleRequest.safeParse(request);

		if (!parsedRequest.success) {
			console.error("Invalid request:", parsedRequest.error);

			const errorMessage = parsedRequest.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}

		return baseApiService.delete(
			`/api/v1/searchspaces/${parsedRequest.data.search_space_id}/roles/${parsedRequest.data.role_id}`,
			deleteRoleResponse
		);
	};
}

export const rolesApiService = new RolesApiService();
