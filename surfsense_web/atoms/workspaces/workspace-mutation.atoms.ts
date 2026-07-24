import { atomWithMutation } from "jotai-tanstack-query";
import { toast } from "sonner";
import type {
	CreateWorkspaceRequest,
	DeleteWorkspaceRequest,
	UpdateWorkspaceApiAccessRequest,
	UpdateWorkspaceRequest,
} from "@/contracts/types/workspace.types";
import { workspacesApiService } from "@/lib/apis/workspaces-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { queryClient } from "@/lib/query-client/client";
import { activeWorkspaceIdAtom } from "./workspace-query.atoms";

export const createWorkspaceMutationAtom = atomWithMutation(() => {
	return {
		mutationKey: ["create-workspace"],
		mutationFn: async (request: CreateWorkspaceRequest) => {
			return workspacesApiService.createWorkspace(request);
		},

		onSuccess: () => {
			toast.success("Search space created successfully");
			queryClient.invalidateQueries({
				queryKey: cacheKeys.workspaces.all,
			});
		},
	};
});

export const updateWorkspaceMutationAtom = atomWithMutation((get) => {
	const activeWorkspaceId = get(activeWorkspaceIdAtom);

	return {
		mutationKey: ["update-workspace", activeWorkspaceId],
		enabled: !!activeWorkspaceId,
		mutationFn: async (request: UpdateWorkspaceRequest) => {
			return workspacesApiService.updateWorkspace(request);
		},

		onSuccess: (_, request: UpdateWorkspaceRequest) => {
			toast.success("Search space updated successfully");
			queryClient.invalidateQueries({
				queryKey: cacheKeys.workspaces.all,
			});
			if (request.id) {
				queryClient.invalidateQueries({
					queryKey: cacheKeys.workspaces.detail(String(request.id)),
				});
			}
		},
	};
});

export const updateWorkspaceApiAccessMutationAtom = atomWithMutation((get) => {
	const activeWorkspaceId = get(activeWorkspaceIdAtom);

	return {
		mutationKey: ["update-workspace-api-access", activeWorkspaceId],
		enabled: !!activeWorkspaceId,
		mutationFn: async (request: UpdateWorkspaceApiAccessRequest) => {
			return workspacesApiService.updateWorkspaceApiAccess(request);
		},

		onSuccess: (_, request: UpdateWorkspaceApiAccessRequest) => {
			toast.success("API access updated successfully");
			queryClient.invalidateQueries({
				queryKey: cacheKeys.workspaces.all,
			});
			queryClient.invalidateQueries({
				queryKey: cacheKeys.workspaces.detail(String(request.id)),
			});
		},
	};
});

export const deleteWorkspaceMutationAtom = atomWithMutation((get) => {
	const activeWorkspaceId = get(activeWorkspaceIdAtom);

	return {
		mutationKey: ["delete-workspace", activeWorkspaceId],
		enabled: !!activeWorkspaceId,
		mutationFn: async (request: DeleteWorkspaceRequest) => {
			return workspacesApiService.deleteWorkspace(request);
		},

		onSuccess: (_, request: DeleteWorkspaceRequest) => {
			toast.success("Search space deleted successfully");
			queryClient.invalidateQueries({
				queryKey: cacheKeys.workspaces.all,
			});
			if (request.id) {
				queryClient.removeQueries({
					queryKey: cacheKeys.workspaces.detail(String(request.id)),
				});
			}
		},
	};
});
