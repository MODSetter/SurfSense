"use client";
import { useAtomValue } from "jotai";
import { useMemo } from "react";
import { canPerform, myAccessAtom } from "@/atoms/members/members-query.atoms";

/**
 * Centralized RBAC gates for the automations slice. Co-located with the
 * route so adding/removing surfaces stays a one-file change. Backed by
 * the same ``myAccessAtom`` the rest of the app uses; owners short-circuit
 * to ``true`` for every action.
 *
 * Mirrors backend permissions in ``app.db.permissions`` (automations:*).
 */
export interface AutomationPermissions {
	loading: boolean;
	canCreate: boolean;
	canRead: boolean;
	canUpdate: boolean;
	canDelete: boolean;
	canExecute: boolean;
}

export function useAutomationPermissions(): AutomationPermissions {
	const { data: access, isLoading } = useAtomValue(myAccessAtom);

	return useMemo(
		() => ({
			loading: isLoading,
			canCreate: canPerform(access, "automations:create"),
			canRead: canPerform(access, "automations:read"),
			canUpdate: canPerform(access, "automations:update"),
			canDelete: canPerform(access, "automations:delete"),
			canExecute: canPerform(access, "automations:execute"),
		}),
		[access, isLoading]
	);
}
