import { atomWithMutation } from "jotai-tanstack-query";
import { toast } from "sonner";
import type {
	AcceptInviteRequest,
	CreateInviteRequest,
	DeleteInviteRequest,
	UpdateInviteRequest,
} from "@/contracts/types/invites.types";
import { invitesApiService } from "@/lib/apis/invites-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { queryClient } from "@/lib/query-client/client";

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

/**
 * Mutation atom for deleting an invite
 */
export const deleteInviteMutationAtom = atomWithMutation(() => ({
	mutationFn: async (request: DeleteInviteRequest) => {
		return invitesApiService.deleteInvite(request);
	},
	onSuccess: (_, variables) => {
		queryClient.invalidateQueries({
			queryKey: cacheKeys.invites.all(variables.search_space_id.toString()),
		});
		toast.success("Invite deleted successfully");
	},
	onError: (error: Error) => {
		console.error("Error deleting invite:", error);
		toast.error("Failed to delete invite");
	},
}));

/**
 * Mutation atom for accepting an invite
 */
export const acceptInviteMutationAtom = atomWithMutation(() => ({
	mutationFn: async (request: AcceptInviteRequest) => {
		return invitesApiService.acceptInvite(request);
	},
	onSuccess: () => {
		queryClient.invalidateQueries({ queryKey: cacheKeys.searchSpaces.all });
		toast.success("Invite accepted successfully");
	},
	onError: (error: Error) => {
		console.error("Error accepting invite:", error);
		toast.error("Failed to accept invite");
	},
}));
