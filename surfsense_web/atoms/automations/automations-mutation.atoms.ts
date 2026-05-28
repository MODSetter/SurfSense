import { atomWithMutation } from "jotai-tanstack-query";
import { toast } from "sonner";
import type {
	AutomationCreateRequest,
	AutomationUpdateRequest,
	TriggerCreateRequest,
	TriggerUpdateRequest,
} from "@/contracts/types/automation.types";
import { automationsApiService } from "@/lib/apis/automations-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { queryClient } from "@/lib/query-client/client";

// Cache invalidation strategy:
// - Automation writes invalidate the search-space list + the touched detail.
// - Trigger writes only invalidate the parent automation detail (triggers
//   come back inline in AutomationDetail).
// We deliberately invalidate the whole "automations" prefix on the list side
// because list is keyed by (searchSpaceId, limit, offset) and we don't track
// the active pagination in this layer.

function invalidateList(searchSpaceId: number) {
	queryClient.invalidateQueries({ queryKey: ["automations", "list", searchSpaceId] });
}

function invalidateDetail(automationId: number) {
	queryClient.invalidateQueries({
		queryKey: cacheKeys.automations.detail(automationId),
	});
}

export const createAutomationMutationAtom = atomWithMutation(() => ({
	meta: { suppressGlobalErrorToast: true },
	mutationFn: async (request: AutomationCreateRequest) => {
		return automationsApiService.createAutomation(request);
	},
	onSuccess: (_, variables) => {
		invalidateList(variables.search_space_id);
		toast.success("Automation created");
	},
	onError: (error: Error) => {
		console.error("Error creating automation:", error);
		toast.error("Failed to create automation");
	},
}));

export const updateAutomationMutationAtom = atomWithMutation(() => ({
	meta: { suppressGlobalErrorToast: true },
	mutationFn: async (vars: { automationId: number; patch: AutomationUpdateRequest }) => {
		return automationsApiService.updateAutomation(vars.automationId, vars.patch);
	},
	onSuccess: (automation, vars) => {
		invalidateDetail(vars.automationId);
		invalidateList(automation.search_space_id);
		toast.success("Automation updated");
	},
	onError: (error: Error) => {
		console.error("Error updating automation:", error);
		toast.error("Failed to update automation");
	},
}));

export const deleteAutomationMutationAtom = atomWithMutation(() => ({
	meta: { suppressGlobalErrorToast: true },
	mutationFn: async (vars: { automationId: number; searchSpaceId: number }) => {
		await automationsApiService.deleteAutomation(vars.automationId);
		return vars;
	},
	onSuccess: (vars) => {
		invalidateList(vars.searchSpaceId);
		invalidateDetail(vars.automationId);
		toast.success("Automation deleted");
	},
	onError: (error: Error) => {
		console.error("Error deleting automation:", error);
		toast.error("Failed to delete automation");
	},
}));

export const addTriggerMutationAtom = atomWithMutation(() => ({
	meta: { suppressGlobalErrorToast: true },
	mutationFn: async (vars: { automationId: number; payload: TriggerCreateRequest }) => {
		return automationsApiService.addTrigger(vars.automationId, vars.payload);
	},
	onSuccess: (_, vars) => {
		invalidateDetail(vars.automationId);
		toast.success("Trigger added");
	},
	onError: (error: Error) => {
		console.error("Error adding trigger:", error);
		toast.error("Failed to add trigger");
	},
}));

export const updateTriggerMutationAtom = atomWithMutation(() => ({
	meta: { suppressGlobalErrorToast: true },
	mutationFn: async (vars: {
		automationId: number;
		triggerId: number;
		patch: TriggerUpdateRequest;
	}) => {
		return automationsApiService.updateTrigger(vars.automationId, vars.triggerId, vars.patch);
	},
	onSuccess: (_, vars) => {
		invalidateDetail(vars.automationId);
		toast.success("Trigger updated");
	},
	onError: (error: Error) => {
		console.error("Error updating trigger:", error);
		toast.error("Failed to update trigger");
	},
}));

export const removeTriggerMutationAtom = atomWithMutation(() => ({
	meta: { suppressGlobalErrorToast: true },
	mutationFn: async (vars: { automationId: number; triggerId: number }) => {
		await automationsApiService.removeTrigger(vars.automationId, vars.triggerId);
		return vars;
	},
	onSuccess: (vars) => {
		invalidateDetail(vars.automationId);
		toast.success("Trigger removed");
	},
	onError: (error: Error) => {
		console.error("Error removing trigger:", error);
		toast.error("Failed to remove trigger");
	},
}));
