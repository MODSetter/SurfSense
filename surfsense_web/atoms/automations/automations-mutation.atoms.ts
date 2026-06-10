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
	trackAutomationCreated,
	trackAutomationCreateFailed,
	trackAutomationDeleted,
	trackAutomationDeleteFailed,
	trackAutomationStatusChanged,
	trackAutomationTriggerAdded,
	trackAutomationTriggerAddFailed,
	trackAutomationTriggerRemoved,
	trackAutomationTriggerRemoveFailed,
	trackAutomationTriggerUpdated,
	trackAutomationTriggerUpdateFailed,
	trackAutomationUpdated,
	trackAutomationUpdateFailed,
} from "@/lib/posthog/events";
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
	onSuccess: (automation, variables) => {
		invalidateList(variables.search_space_id);
		toast.success("Automation created");
		trackAutomationCreated({
			search_space_id: variables.search_space_id,
			automation_id: automation.id,
			task_count: variables.definition.plan.length,
			trigger_type: variables.triggers?.[0]?.type ?? "none",
			has_schedule: (variables.triggers?.length ?? 0) > 0,
			chat_model_id: variables.definition.models?.chat_model_id,
			image_gen_model_id: variables.definition.models?.image_gen_model_id,
			vision_model_id: variables.definition.models?.vision_model_id,
			tags_count: variables.definition.metadata?.tags?.length,
		});
	},
	onError: (error: Error, variables) => {
		console.error("Error creating automation:", error);
		toast.error("Failed to create automation");
		trackAutomationCreateFailed({
			search_space_id: variables.search_space_id,
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
		invalidateList(automation.search_space_id);
		toast.success("Automation updated");
		// A status-only patch (pause/resume/archive) is a distinct action from a
		// definition/name edit, so split it into its own event.
		if (vars.patch.status && !vars.patch.definition) {
			trackAutomationStatusChanged({
				automation_id: vars.automationId,
				search_space_id: automation.search_space_id,
				next_status: vars.patch.status,
			});
		} else {
			trackAutomationUpdated({
				automation_id: vars.automationId,
				search_space_id: automation.search_space_id,
				has_definition_change: !!vars.patch.definition,
				has_name_change: vars.patch.name != null,
				has_description_change: vars.patch.description !== undefined,
				task_count: vars.patch.definition?.plan?.length,
			});
		}
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
	mutationFn: async (vars: { automationId: number; searchSpaceId: number }) => {
		await automationsApiService.deleteAutomation(vars.automationId);
		return vars;
	},
	onSuccess: (vars) => {
		invalidateList(vars.searchSpaceId);
		invalidateDetail(vars.automationId);
		toast.success("Automation deleted");
		trackAutomationDeleted({
			automation_id: vars.automationId,
			search_space_id: vars.searchSpaceId,
		});
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
	onSuccess: (trigger, vars) => {
		invalidateDetail(vars.automationId);
		toast.success("Trigger added");
		trackAutomationTriggerAdded({
			automation_id: vars.automationId,
			trigger_id: trigger.id,
			trigger_type: trigger.type,
			enabled: trigger.enabled,
			has_cron: !!trigger.params?.cron,
		});
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
		const change: "enabled" | "params" | "other" = vars.patch.params
			? "params"
			: vars.patch.enabled !== undefined && vars.patch.enabled !== null
				? "enabled"
				: "other";
		trackAutomationTriggerUpdated({
			automation_id: vars.automationId,
			trigger_id: vars.triggerId,
			change,
			enabled: vars.patch.enabled ?? undefined,
		});
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
		trackAutomationTriggerRemoved({
			automation_id: vars.automationId,
			trigger_id: vars.triggerId,
		});
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
