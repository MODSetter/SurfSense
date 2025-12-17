import { atomWithMutation } from "jotai-tanstack-query";
import { toast } from "sonner";
import type {
	CreateRoleRequest,
	CreateRoleResponse,
	DeleteRoleRequest,
	DeleteRoleResponse,
	UpdateRoleRequest,
	UpdateRoleResponse,
} from "@/contracts/types/roles.types";
import { rolesApiService } from "@/lib/apis/roles-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { queryClient } from "@/lib/query-client/client";

export const createRoleMutationAtom = atomWithMutation(() => {
	return {
		mutationFn: async (request: CreateRoleRequest) => {
			return rolesApiService.createRole(request);
		},
		onSuccess: (_: CreateRoleResponse, request: CreateRoleRequest) => {
			toast.success("Role created successfully");
			queryClient.invalidateQueries({
				queryKey: cacheKeys.roles.all(request.search_space_id.toString()),
			});
		},
		onError: () => {
			toast.error("Failed to create role");
		},
	};
});

export const updateRoleMutationAtom = atomWithMutation(() => {
	return {
		mutationFn: async (request: UpdateRoleRequest) => {
			return rolesApiService.updateRole(request);
		},
		onSuccess: (_: UpdateRoleResponse, request: UpdateRoleRequest) => {
			toast.success("Role updated successfully");
			queryClient.invalidateQueries({
				queryKey: cacheKeys.roles.all(request.search_space_id.toString()),
			});
			queryClient.invalidateQueries({
				queryKey: cacheKeys.roles.byId(
					request.search_space_id.toString(),
					request.role_id.toString()
				),
			});
		},
		onError: () => {
			toast.error("Failed to update role");
		},
	};
});

export const deleteRoleMutationAtom = atomWithMutation(() => {
	return {
		mutationFn: async (request: DeleteRoleRequest) => {
			return rolesApiService.deleteRole(request);
		},
		onSuccess: (_: DeleteRoleResponse, request: DeleteRoleRequest) => {
			toast.success("Role deleted successfully");
			queryClient.invalidateQueries({
				queryKey: cacheKeys.roles.all(request.search_space_id.toString()),
			});
		},
		onError: () => {
			toast.error("Failed to delete role");
		},
	};
});
