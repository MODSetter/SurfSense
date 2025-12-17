"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { authenticatedFetch, getBearerToken, handleUnauthorized } from "@/lib/auth-utils";

// ============ Types ============

export interface Role {
	id: number;
	name: string;
	description: string | null;
	permissions: string[];
	is_default: boolean;
	is_system_role: boolean;
	search_space_id: number;
	created_at: string;
}

export interface Member {
	id: number;
	user_id: string;
	search_space_id: number;
	role_id: number | null;
	is_owner: boolean;
	joined_at: string;
	created_at: string;
	role: Role | null;
	user_email: string | null;
}

export interface Invite {
	id: number;
	invite_code: string;
	search_space_id: number;
	role_id: number | null;
	created_by_id: string | null;
	expires_at: string | null;
	max_uses: number | null;
	uses_count: number;
	is_active: boolean;
	name: string | null;
	created_at: string;
	role: Role | null;
}

export interface InviteCreate {
	name?: string;
	role_id?: number;
	expires_at?: string;
	max_uses?: number;
}

export interface InviteUpdate {
	name?: string;
	role_id?: number;
	expires_at?: string;
	max_uses?: number;
	is_active?: boolean;
}

export interface RoleCreate {
	name: string;
	description?: string;
	permissions: string[];
	is_default?: boolean;
}

export interface RoleUpdate {
	name?: string;
	description?: string;
	permissions?: string[];
	is_default?: boolean;
}

export interface PermissionInfo {
	value: string;
	name: string;
	category: string;
}

export interface UserAccess {
	search_space_id: number;
	search_space_name: string;
	is_owner: boolean;
	role_name: string | null;
	permissions: string[];
}

export interface InviteInfo {
	search_space_name: string;
	role_name: string | null;
	is_valid: boolean;
	message: string | null;
}

// ============ Members Hook ============

export function useInviteInfo(inviteCode: string | null) {
	const [inviteInfo, setInviteInfo] = useState<InviteInfo | null>(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	const fetchInviteInfo = useCallback(async () => {
		if (!inviteCode) {
			setLoading(false);
			return;
		}

		try {
			setLoading(true);
			const response = await fetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/invites/${inviteCode}/info`,
				{
					method: "GET",
				}
			);

			if (!response.ok) {
				const errorData = await response.json().catch(() => ({}));
				throw new Error(errorData.detail || "Failed to fetch invite info");
			}

			const data = await response.json();
			setInviteInfo(data);
			setError(null);
			return data;
		} catch (err: any) {
			setError(err.message || "Failed to fetch invite info");
			console.error("Error fetching invite info:", err);
		} finally {
			setLoading(false);
		}
	}, [inviteCode]);

	useEffect(() => {
		fetchInviteInfo();
	}, [fetchInviteInfo]);

	const acceptInvite = useCallback(async () => {
		if (!inviteCode) {
			toast.error("No invite code provided");
			return null;
		}

		try {
			const response = await authenticatedFetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/invites/accept`,
				{
					headers: { "Content-Type": "application/json" },
					method: "POST",
					body: JSON.stringify({ invite_code: inviteCode }),
				}
			);

			if (!response.ok) {
				const errorData = await response.json().catch(() => ({}));
				throw new Error(errorData.detail || "Failed to accept invite");
			}

			const data = await response.json();
			toast.success(data.message || "Successfully joined the search space");
			return data;
		} catch (err: any) {
			toast.error(err.message || "Failed to accept invite");
			throw err;
		}
	}, [inviteCode]);

	return {
		inviteInfo,
		loading,
		error,
		fetchInviteInfo,
		acceptInvite,
	};
}
