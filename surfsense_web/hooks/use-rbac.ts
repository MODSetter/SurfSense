"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

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

export function useMembers(searchSpaceId: number) {
	const [members, setMembers] = useState<Member[]>([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	const fetchMembers = useCallback(async () => {
		if (!searchSpaceId) return;

		try {
			setLoading(true);
			const response = await fetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/searchspaces/${searchSpaceId}/members`,
				{
					headers: {
						Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
					},
					method: "GET",
				}
			);

			if (response.status === 401) {
				localStorage.removeItem("surfsense_bearer_token");
				window.location.href = "/";
				throw new Error("Unauthorized");
			}

			if (!response.ok) {
				const errorData = await response.json().catch(() => ({}));
				throw new Error(errorData.detail || "Failed to fetch members");
			}

			const data = await response.json();
			setMembers(data);
			setError(null);
			return data;
		} catch (err: any) {
			setError(err.message || "Failed to fetch members");
			console.error("Error fetching members:", err);
		} finally {
			setLoading(false);
		}
	}, [searchSpaceId]);

	useEffect(() => {
		fetchMembers();
	}, [fetchMembers]);

	const updateMemberRole = useCallback(
		async (membershipId: number, roleId: number | null) => {
			try {
				const response = await fetch(
					`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/searchspaces/${searchSpaceId}/members/${membershipId}`,
					{
						headers: {
							"Content-Type": "application/json",
							Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
						},
						method: "PUT",
						body: JSON.stringify({ role_id: roleId }),
					}
				);

				if (!response.ok) {
					const errorData = await response.json().catch(() => ({}));
					throw new Error(errorData.detail || "Failed to update member role");
				}

				const updatedMember = await response.json();
				setMembers((prev) => prev.map((m) => (m.id === membershipId ? updatedMember : m)));
				toast.success("Member role updated successfully");
				return updatedMember;
			} catch (err: any) {
				toast.error(err.message || "Failed to update member role");
				throw err;
			}
		},
		[searchSpaceId]
	);

	const removeMember = useCallback(
		async (membershipId: number) => {
			try {
				const response = await fetch(
					`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/searchspaces/${searchSpaceId}/members/${membershipId}`,
					{
						headers: {
							Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
						},
						method: "DELETE",
					}
				);

				if (!response.ok) {
					const errorData = await response.json().catch(() => ({}));
					throw new Error(errorData.detail || "Failed to remove member");
				}

				setMembers((prev) => prev.filter((m) => m.id !== membershipId));
				toast.success("Member removed successfully");
				return true;
			} catch (err: any) {
				toast.error(err.message || "Failed to remove member");
				return false;
			}
		},
		[searchSpaceId]
	);

	const leaveSearchSpace = useCallback(async () => {
		try {
			const response = await fetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/searchspaces/${searchSpaceId}/members/me`,
				{
					headers: {
						Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
					},
					method: "DELETE",
				}
			);

			if (!response.ok) {
				const errorData = await response.json().catch(() => ({}));
				throw new Error(errorData.detail || "Failed to leave search space");
			}

			toast.success("Successfully left the search space");
			return true;
		} catch (err: any) {
			toast.error(err.message || "Failed to leave search space");
			return false;
		}
	}, [searchSpaceId]);

	return {
		members,
		loading,
		error,
		fetchMembers,
		updateMemberRole,
		removeMember,
		leaveSearchSpace,
	};
}

// ============ Roles Hook ============

export function useRoles(searchSpaceId: number) {
	const [roles, setRoles] = useState<Role[]>([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	const fetchRoles = useCallback(async () => {
		if (!searchSpaceId) return;

		try {
			setLoading(true);
			const response = await fetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/searchspaces/${searchSpaceId}/roles`,
				{
					headers: {
						Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
					},
					method: "GET",
				}
			);

			if (response.status === 401) {
				localStorage.removeItem("surfsense_bearer_token");
				window.location.href = "/";
				throw new Error("Unauthorized");
			}

			if (!response.ok) {
				const errorData = await response.json().catch(() => ({}));
				throw new Error(errorData.detail || "Failed to fetch roles");
			}

			const data = await response.json();
			setRoles(data);
			setError(null);
			return data;
		} catch (err: any) {
			setError(err.message || "Failed to fetch roles");
			console.error("Error fetching roles:", err);
		} finally {
			setLoading(false);
		}
	}, [searchSpaceId]);

	useEffect(() => {
		fetchRoles();
	}, [fetchRoles]);

	const createRole = useCallback(
		async (roleData: RoleCreate) => {
			try {
				const response = await fetch(
					`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/searchspaces/${searchSpaceId}/roles`,
					{
						headers: {
							"Content-Type": "application/json",
							Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
						},
						method: "POST",
						body: JSON.stringify(roleData),
					}
				);

				if (!response.ok) {
					const errorData = await response.json().catch(() => ({}));
					throw new Error(errorData.detail || "Failed to create role");
				}

				const newRole = await response.json();
				setRoles((prev) => [...prev, newRole]);
				toast.success("Role created successfully");
				return newRole;
			} catch (err: any) {
				toast.error(err.message || "Failed to create role");
				throw err;
			}
		},
		[searchSpaceId]
	);

	const updateRole = useCallback(
		async (roleId: number, roleData: RoleUpdate) => {
			try {
				const response = await fetch(
					`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/searchspaces/${searchSpaceId}/roles/${roleId}`,
					{
						headers: {
							"Content-Type": "application/json",
							Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
						},
						method: "PUT",
						body: JSON.stringify(roleData),
					}
				);

				if (!response.ok) {
					const errorData = await response.json().catch(() => ({}));
					throw new Error(errorData.detail || "Failed to update role");
				}

				const updatedRole = await response.json();
				setRoles((prev) => prev.map((r) => (r.id === roleId ? updatedRole : r)));
				toast.success("Role updated successfully");
				return updatedRole;
			} catch (err: any) {
				toast.error(err.message || "Failed to update role");
				throw err;
			}
		},
		[searchSpaceId]
	);

	const deleteRole = useCallback(
		async (roleId: number) => {
			try {
				const response = await fetch(
					`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/searchspaces/${searchSpaceId}/roles/${roleId}`,
					{
						headers: {
							Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
						},
						method: "DELETE",
					}
				);

				if (!response.ok) {
					const errorData = await response.json().catch(() => ({}));
					throw new Error(errorData.detail || "Failed to delete role");
				}

				setRoles((prev) => prev.filter((r) => r.id !== roleId));
				toast.success("Role deleted successfully");
				return true;
			} catch (err: any) {
				toast.error(err.message || "Failed to delete role");
				return false;
			}
		},
		[searchSpaceId]
	);

	return {
		roles,
		loading,
		error,
		fetchRoles,
		createRole,
		updateRole,
		deleteRole,
	};
}

// ============ Invites Hook ============

export function useInvites(searchSpaceId: number) {
	const [invites, setInvites] = useState<Invite[]>([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	const fetchInvites = useCallback(async () => {
		if (!searchSpaceId) return;

		try {
			setLoading(true);
			const response = await fetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/searchspaces/${searchSpaceId}/invites`,
				{
					headers: {
						Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
					},
					method: "GET",
				}
			);

			if (response.status === 401) {
				localStorage.removeItem("surfsense_bearer_token");
				window.location.href = "/";
				throw new Error("Unauthorized");
			}

			if (!response.ok) {
				const errorData = await response.json().catch(() => ({}));
				throw new Error(errorData.detail || "Failed to fetch invites");
			}

			const data = await response.json();
			setInvites(data);
			setError(null);
			return data;
		} catch (err: any) {
			setError(err.message || "Failed to fetch invites");
			console.error("Error fetching invites:", err);
		} finally {
			setLoading(false);
		}
	}, [searchSpaceId]);

	useEffect(() => {
		fetchInvites();
	}, [fetchInvites]);

	const createInvite = useCallback(
		async (inviteData: InviteCreate) => {
			try {
				const response = await fetch(
					`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/searchspaces/${searchSpaceId}/invites`,
					{
						headers: {
							"Content-Type": "application/json",
							Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
						},
						method: "POST",
						body: JSON.stringify(inviteData),
					}
				);

				if (!response.ok) {
					const errorData = await response.json().catch(() => ({}));
					throw new Error(errorData.detail || "Failed to create invite");
				}

				const newInvite = await response.json();
				setInvites((prev) => [...prev, newInvite]);
				toast.success("Invite created successfully");
				return newInvite;
			} catch (err: any) {
				toast.error(err.message || "Failed to create invite");
				throw err;
			}
		},
		[searchSpaceId]
	);

	const updateInvite = useCallback(
		async (inviteId: number, inviteData: InviteUpdate) => {
			try {
				const response = await fetch(
					`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/searchspaces/${searchSpaceId}/invites/${inviteId}`,
					{
						headers: {
							"Content-Type": "application/json",
							Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
						},
						method: "PUT",
						body: JSON.stringify(inviteData),
					}
				);

				if (!response.ok) {
					const errorData = await response.json().catch(() => ({}));
					throw new Error(errorData.detail || "Failed to update invite");
				}

				const updatedInvite = await response.json();
				setInvites((prev) => prev.map((i) => (i.id === inviteId ? updatedInvite : i)));
				toast.success("Invite updated successfully");
				return updatedInvite;
			} catch (err: any) {
				toast.error(err.message || "Failed to update invite");
				throw err;
			}
		},
		[searchSpaceId]
	);

	const revokeInvite = useCallback(
		async (inviteId: number) => {
			try {
				const response = await fetch(
					`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/searchspaces/${searchSpaceId}/invites/${inviteId}`,
					{
						headers: {
							Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
						},
						method: "DELETE",
					}
				);

				if (!response.ok) {
					const errorData = await response.json().catch(() => ({}));
					throw new Error(errorData.detail || "Failed to revoke invite");
				}

				setInvites((prev) => prev.filter((i) => i.id !== inviteId));
				toast.success("Invite revoked successfully");
				return true;
			} catch (err: any) {
				toast.error(err.message || "Failed to revoke invite");
				return false;
			}
		},
		[searchSpaceId]
	);

	return {
		invites,
		loading,
		error,
		fetchInvites,
		createInvite,
		updateInvite,
		revokeInvite,
	};
}

// ============ Permissions Hook ============

export function usePermissions() {
	const [permissions, setPermissions] = useState<PermissionInfo[]>([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	const fetchPermissions = useCallback(async () => {
		try {
			setLoading(true);
			const response = await fetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/permissions`,
				{
					headers: {
						Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
					},
					method: "GET",
				}
			);

			if (!response.ok) {
				const errorData = await response.json().catch(() => ({}));
				throw new Error(errorData.detail || "Failed to fetch permissions");
			}

			const data = await response.json();
			setPermissions(data.permissions);
			setError(null);
			return data.permissions;
		} catch (err: any) {
			setError(err.message || "Failed to fetch permissions");
			console.error("Error fetching permissions:", err);
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => {
		fetchPermissions();
	}, [fetchPermissions]);

	// Group permissions by category
	const groupedPermissions = useMemo(() => {
		const groups: Record<string, PermissionInfo[]> = {};
		for (const perm of permissions) {
			if (!groups[perm.category]) {
				groups[perm.category] = [];
			}
			groups[perm.category].push(perm);
		}
		return groups;
	}, [permissions]);

	return {
		permissions,
		groupedPermissions,
		loading,
		error,
		fetchPermissions,
	};
}

// ============ User Access Hook ============

export function useUserAccess(searchSpaceId: number) {
	const [access, setAccess] = useState<UserAccess | null>(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	const fetchAccess = useCallback(async () => {
		if (!searchSpaceId) return;

		try {
			setLoading(true);
			const response = await fetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/searchspaces/${searchSpaceId}/my-access`,
				{
					headers: {
						Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
					},
					method: "GET",
				}
			);

			if (response.status === 401) {
				localStorage.removeItem("surfsense_bearer_token");
				window.location.href = "/";
				throw new Error("Unauthorized");
			}

			if (!response.ok) {
				const errorData = await response.json().catch(() => ({}));
				throw new Error(errorData.detail || "Failed to fetch access info");
			}

			const data = await response.json();
			setAccess(data);
			setError(null);
			return data;
		} catch (err: any) {
			setError(err.message || "Failed to fetch access info");
			console.error("Error fetching access:", err);
		} finally {
			setLoading(false);
		}
	}, [searchSpaceId]);

	useEffect(() => {
		fetchAccess();
	}, [fetchAccess]);

	// Helper function to check if user has a specific permission
	const hasPermission = useCallback(
		(permission: string) => {
			if (!access) return false;
			// Owner/full access check
			if (access.permissions.includes("*")) return true;
			return access.permissions.includes(permission);
		},
		[access]
	);

	// Helper function to check if user has any of the given permissions
	const hasAnyPermission = useCallback(
		(permissions: string[]) => {
			if (!access) return false;
			if (access.permissions.includes("*")) return true;
			return permissions.some((p) => access.permissions.includes(p));
		},
		[access]
	);

	return {
		access,
		loading,
		error,
		fetchAccess,
		hasPermission,
		hasAnyPermission,
	};
}

// ============ Invite Info Hook (Public) ============

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
			const response = await fetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/invites/accept`,
				{
					headers: {
						"Content-Type": "application/json",
						Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
					},
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
