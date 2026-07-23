import { atomWithMutation } from "jotai-tanstack-query";
import { toast } from "sonner";
import type {
	AutomationCreateRequest,
	AutomationUpdateRequest,
	TriggerCreateRequest,
	TriggerUpdateRequest,
} from "@/contracts/types/automation.types";
import { automationsApiService } from "@/lib/apis/automations-api.service";
import {
	trackAutomationCreateFailed,
	trackAutomationDeleteFailed,
	trackAutomationTriggerAddFailed,
	trackAutomationTriggerRemoveFailed,
	trackAutomationTriggerUpdateFailed,
	trackAutomationUpdateFailed,
} from "@/lib/posthog/events";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { queryClient } from "@/lib/query-client/client";

// Cache invalidation strategy:
// - Automation writes invalidate the workspace list + the touched detail.
// - Trigger writes only invalidate the parent automation detail (triggers
//   come back inline in AutomationDetail).
// We deliberately invalidate the whole "automations" prefix on the list side
// because list is keyed by (workspaceId, limit, offset) and we don't track
// the active pagination in this layer.

function invalidateList(workspaceId: number) {
	queryClient.invalidateQueries({ queryKey: ["automations", "list", workspaceId] });
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
	onSuccess: (_automation, variables) => {
		invalidateList(variables.workspace_id);
		toast.success("Automation created");
		// automation_created is now emitted server-side (AutomationService.create).
	},
	onError: (error: Error, variables) => {
		console.error("Error creating automation:", error);
		toast.error("Failed to create automation");
		trackAutomationCreateFailed({
			workspace_id: variables.workspace_id,
			error: error.message,
		});
	},
}));

export const updateAutomationMutationAtom = atomWithMutation(() => ({
	meta: { suppressGlobalErrorToast: true },
	mutationFn: async (vars: { automationId: number; patch: AutomationUpdateRequest }) => {
		return automationsApiService.updateAutomation(vars.automationId, vars.patch);
	},
	onSuccess: (automation, vars) => {
		invalidateDetail(vars.automationId);
		invalidateList(automation.workspace_id);
		toast.success("Automation updated");
		// automation_updated / automation_status_changed are now emitted
		// server-side (AutomationService.update).
	},
	onError: (error: Error, vars) => {
		console.error("Error updating automation:", error);
		toast.error("Failed to update automation");
		trackAutomationUpdateFailed({
			automation_id: vars.automationId,
			error: error.message,
		});
	},
}));

export const deleteAutomationMutationAtom = atomWithMutation(() => ({
	meta: { suppressGlobalErrorToast: true },
	mutationFn: async (vars: { automationId: number; workspaceId: number }) => {
		await automationsApiService.deleteAutomation(vars.automationId);
		return vars;
	},
	onSuccess: (vars) => {
		invalidateList(vars.workspaceId);
		invalidateDetail(vars.automationId);
		toast.success("Automation deleted");
		// automation_deleted is now emitted server-side (AutomationService.delete).
	},
	onError: (error: Error, vars) => {
		console.error("Error deleting automation:", error);
		toast.error("Failed to delete automation");
		trackAutomationDeleteFailed({
			automation_id: vars.automationId,
			error: error.message,
		});
	},
}));

export const addTriggerMutationAtom = atomWithMutation(() => ({
	meta: { suppressGlobalErrorToast: true },
	mutationFn: async (vars: { automationId: number; payload: TriggerCreateRequest }) => {
		return automationsApiService.addTrigger(vars.automationId, vars.payload);
	},
	onSuccess: (_trigger, vars) => {
		invalidateDetail(vars.automationId);
		toast.success("Trigger added");
		// automation_trigger_added is now emitted server-side (TriggerService.add).
	},
	onError: (error: Error, vars) => {
		console.error("Error adding trigger:", error);
		toast.error("Failed to add trigger");
		trackAutomationTriggerAddFailed({
			automation_id: vars.automationId,
			error: error.message,
		});
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
		// automation_trigger_updated is now emitted server-side (TriggerService.update).
	},
	onError: (error: Error, vars) => {
		console.error("Error updating trigger:", error);
		toast.error("Failed to update trigger");
		trackAutomationTriggerUpdateFailed({
			automation_id: vars.automationId,
			trigger_id: vars.triggerId,
			error: error.message,
		});
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
		// automation_trigger_removed is now emitted server-side (TriggerService.remove).
	},
	onError: (error: Error, vars) => {
		console.error("Error removing trigger:", error);
		toast.error("Failed to remove trigger");
		trackAutomationTriggerRemoveFailed({
			automation_id: vars.automationId,
			trigger_id: vars.triggerId,
			error: error.message,
		});
	},
}));
