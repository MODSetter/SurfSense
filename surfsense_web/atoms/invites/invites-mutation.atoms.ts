import { atomWithMutation } from "jotai-tanstack-query";
import { invitesApiService } from "@/lib/apis/invites-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { queryClient } from "@/lib/query-client/client";
import type {
	CreateInviteRequest,
	UpdateInviteRequest,
	DeleteInviteRequest,
	AcceptInviteRequest,
} from "@/contracts/types/invites.types";
import { toast } from "sonner";

/**
 * Mutation atom for creating an invite
 */
export const createInviteMutationAtom = atomWithMutation(() => ({
	mutationFn: async (request: CreateInviteRequest) => {
		return invitesApiService.createInvite(request);
	},
	onSuccess: (_, variables) => {
		queryClient.invalidateQueries({
			queryKey: cacheKeys.invites.all(variables.search_space_id.toString()),
		});
		toast.success("Invite created successfully");
	},
	onError: (error: Error) => {
		console.error("Error creating invite:", error);
		toast.error("Failed to create invite");
	},
}));

/**
 * Mutation atom for updating an invite
 */
export const updateInviteMutationAtom = atomWithMutation(() => ({
	mutationFn: async (request: UpdateInviteRequest) => {
		return invitesApiService.updateInvite(request);
	},
	onSuccess: (_, variables) => {
		queryClient.invalidateQueries({
			queryKey: cacheKeys.invites.all(variables.search_space_id.toString()),
		});
		toast.success("Invite updated successfully");
	},
	onError: (error: Error) => {
		console.error("Error updating invite:", error);
		toast.error("Failed to update invite");
	},
}));
