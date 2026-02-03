"use client";

import { useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import {
	Bot,
	Calendar,
	Check,
	Clock,
	Copy,
	Crown,
	Edit2,
	FileText,
	Globe,
	Hash,
	Link2,
	LinkIcon,
	Logs,
	type LucideIcon,
	MessageCircle,
	MessageSquare,
	Mic,
	MoreHorizontal,
	Plug,
	Plus,
	RefreshCw,
	Search,
	Settings,
	Shield,
	ShieldCheck,
	Trash2,
	UserMinus,
	UserPlus,
	Users,
} from "lucide-react";
import { motion } from "motion/react";
import Image from "next/image";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import {
	createInviteMutationAtom,
	deleteInviteMutationAtom,
} from "@/atoms/invites/invites-mutation.atoms";
import {
	deleteMemberMutationAtom,
	updateMemberMutationAtom,
} from "@/atoms/members/members-mutation.atoms";
import { membersAtom, myAccessAtom } from "@/atoms/members/members-query.atoms";
import { permissionsAtom } from "@/atoms/permissions/permissions-query.atoms";
import {
	createRoleMutationAtom,
	deleteRoleMutationAtom,
	updateRoleMutationAtom,
} from "@/atoms/roles/roles-mutation.atoms";
import {
	AlertDialog,
	AlertDialogAction,
	AlertDialogCancel,
	AlertDialogContent,
	AlertDialogDescription,
	AlertDialogFooter,
	AlertDialogHeader,
	AlertDialogTitle,
	AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Calendar as CalendarComponent } from "@/components/ui/calendar";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
	DialogTrigger,
} from "@/components/ui/dialog";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type {
	CreateInviteRequest,
	DeleteInviteRequest,
	Invite,
} from "@/contracts/types/invites.types";
import type {
	DeleteMembershipRequest,
	Membership,
	UpdateMembershipRequest,
} from "@/contracts/types/members.types";
import type { PermissionInfo } from "@/contracts/types/permissions.types";
import type {
	CreateRoleRequest,
	DeleteRoleRequest,
	Role,
	UpdateRoleRequest,
} from "@/contracts/types/roles.types";
import { invitesApiService } from "@/lib/apis/invites-api.service";
import { rolesApiService } from "@/lib/apis/roles-api.service";
import { trackSearchSpaceInviteSent, trackSearchSpaceUsersViewed } from "@/lib/posthog/events";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { cn } from "@/lib/utils";

// Animation variants
const fadeInUp = {
	hidden: { opacity: 0, y: 20 },
	visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: "easeOut" as const } },
};

const staggerContainer = {
	hidden: { opacity: 0 },
	visible: {
		opacity: 1,
		transition: { staggerChildren: 0.1 },
	},
};

const cardVariants = {
	hidden: { opacity: 0, scale: 0.95 },
	visible: {
		opacity: 1,
		scale: 1,
		transition: { type: "spring" as const, stiffness: 300, damping: 30 },
	},
};

export default function TeamManagementPage() {
	const params = useParams();
	const searchSpaceId = Number(params.search_space_id);
	const [activeTab, setActiveTab] = useState("members");

	const { data: access = null, isLoading: accessLoading } = useAtomValue(myAccessAtom);

	const hasPermission = useCallback(
		(permission: string) => {
			if (!access) return false;
			if (access.is_owner) return true;
			return access.permissions?.includes(permission) ?? false;
		},
		[access]
	);

	const {
		data: members = [],
		isLoading: membersLoading,
		refetch: fetchMembers,
	} = useAtomValue(membersAtom);

	const { mutateAsync: createRole } = useAtomValue(createRoleMutationAtom);
	const { mutateAsync: updateRole } = useAtomValue(updateRoleMutationAtom);
	const { mutateAsync: deleteRole } = useAtomValue(deleteRoleMutationAtom);
	const { mutateAsync: updateMember } = useAtomValue(updateMemberMutationAtom);

	const { mutateAsync: deleteMember } = useAtomValue(deleteMemberMutationAtom);
	const { mutateAsync: createInvite } = useAtomValue(createInviteMutationAtom);
	const { mutateAsync: revokeInvite } = useAtomValue(deleteInviteMutationAtom);

	const handleRevokeInvite = useCallback(
		async (inviteId: number): Promise<boolean> => {
			const request: DeleteInviteRequest = {
				search_space_id: searchSpaceId,
				invite_id: inviteId,
			};
			await revokeInvite(request);
			return true;
		},
		[revokeInvite, searchSpaceId]
	);

	const handleCreateInvite = useCallback(
		async (inviteData: CreateInviteRequest["data"]) => {
			const request: CreateInviteRequest = {
				search_space_id: searchSpaceId,
				data: inviteData,
			};
			return await createInvite(request);
		},
		[createInvite, searchSpaceId]
	);

	const handleUpdateRole = useCallback(
		async (
			roleId: number,
			data: {
				name?: string;
				description?: string | null;
				permissions?: string[];
				is_default?: boolean;
			}
		): Promise<Role> => {
			const request: UpdateRoleRequest = {
				search_space_id: searchSpaceId,
				role_id: roleId,
				data: data,
			};
			return await updateRole(request);
		},
		[updateRole, searchSpaceId]
	);

	const handleDeleteRole = useCallback(
		async (roleId: number): Promise<boolean> => {
			const request: DeleteRoleRequest = {
				search_space_id: searchSpaceId,
				role_id: roleId,
			};
			await deleteRole(request);
			return true;
		},
		[deleteRole, searchSpaceId]
	);

	const handleCreateRole = useCallback(
		async (roleData: CreateRoleRequest["data"]): Promise<Role> => {
			const request: CreateRoleRequest = {
				search_space_id: searchSpaceId,
				data: roleData,
			};
			return await createRole(request);
		},
		[createRole, searchSpaceId]
	);

	const handleUpdateMember = useCallback(
		async (membershipId: number, roleId: number | null): Promise<Membership> => {
			const request: UpdateMembershipRequest = {
				search_space_id: searchSpaceId,
				membership_id: membershipId,
				data: {
					role_id: roleId,
				},
			};
			return (await updateMember(request)) as Membership;
		},
		[updateMember, searchSpaceId]
	);

	const handleRemoveMember = useCallback(
		async (membershipId: number) => {
			const request: DeleteMembershipRequest = {
				search_space_id: searchSpaceId,
				membership_id: membershipId,
			};
			await deleteMember(request);

			return true;
		},
		[deleteMember, searchSpaceId]
	);
	const {
		data: roles = [],
		isLoading: rolesLoading,
		refetch: fetchRoles,
	} = useQuery({
		queryKey: cacheKeys.roles.all(searchSpaceId.toString()),
		queryFn: () => rolesApiService.getRoles({ search_space_id: searchSpaceId }),
		enabled: !!searchSpaceId,
	});
	const {
		data: invites = [],
		isLoading: invitesLoading,
		refetch: fetchInvites,
	} = useQuery({
		queryKey: cacheKeys.invites.all(searchSpaceId.toString()),
		queryFn: () => invitesApiService.getInvites({ search_space_id: searchSpaceId }),
		staleTime: 5 * 60 * 1000,
	});

	const { data: permissionsData } = useAtomValue(permissionsAtom);
	const permissions = permissionsData?.permissions || [];
	const groupedPermissions = useMemo(() => {
		const groups: Record<string, typeof permissions> = {};
		for (const perm of permissions) {
			if (!groups[perm.category]) {
				groups[perm.category] = [];
			}
			groups[perm.category].push(perm);
		}
		return groups;
	}, [permissions]);

	const canInvite = hasPermission("members:invite");

	const handleRefresh = useCallback(async () => {
		await Promise.all([fetchMembers(), fetchRoles(), fetchInvites()]);
		toast.success("Team data refreshed");
	}, [fetchMembers, fetchRoles, fetchInvites]);

	// Track users per search space when team page is viewed
	useEffect(() => {
		if (members.length > 0 && !membersLoading) {
			const ownerCount = members.filter((m) => m.is_owner).length;
			trackSearchSpaceUsersViewed(searchSpaceId, members.length, ownerCount);
		}
	}, [members, membersLoading, searchSpaceId]);

	if (accessLoading) {
		return (
			<div className="flex items-center justify-center min-h-[60vh]">
				<motion.div
					initial={{ opacity: 0, scale: 0.9 }}
					animate={{ opacity: 1, scale: 1 }}
					className="flex flex-col items-center gap-4"
				>
					<Spinner size="lg" className="text-primary" />
					<p className="text-muted-foreground">Loading team data...</p>
				</motion.div>
			</div>
		);
	}

	return (
		<motion.div
			initial="hidden"
			animate="visible"
			variants={staggerContainer}
			className="min-h-screen bg-background"
		>
			<div className="container max-w-7xl mx-auto p-4 md:p-6 lg:p-8">
				<motion.div variants={fadeInUp} className="space-y-8">
					{/* Header */}
					<div className="space-y-4">
						<div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
							<div className="flex items-start space-x-3 md:items-center md:space-x-4">
								<div className="flex h-10 w-10 md:h-12 md:w-12 items-center justify-center rounded-xl bg-gradient-to-br from-primary/20 to-primary/5 ring-1 ring-primary/10 shrink-0">
									<Users className="h-5 w-5 md:h-6 md:w-6 text-primary" />
								</div>
								<div className="space-y-1 min-w-0">
									<h1 className="text-2xl md:text-3xl font-bold tracking-tight bg-gradient-to-r from-foreground to-foreground/70 bg-clip-text">
										Team Management
									</h1>
									<p className="text-xs md:text-sm text-muted-foreground">
										Manage members, roles, and invite links for your search space
									</p>
								</div>
							</div>
							<div className="flex items-center gap-2">
								<Button
									onClick={handleRefresh}
									variant="outline"
									size="sm"
									className="gap-2 w-full md:w-auto"
								>
									<RefreshCw className="h-4 w-4" />
									Refresh
								</Button>
							</div>
						</div>
					</div>

					{/* Summary Cards */}
					<motion.div variants={staggerContainer} className="grid grid-cols-1 md:grid-cols-3 gap-4">
						<motion.div variants={cardVariants}>
							<Card className="relative overflow-hidden border-none bg-gradient-to-br from-blue-500/10 via-blue-500/5 to-transparent">
								<div className="absolute top-0 right-0 w-32 h-32 bg-blue-500/10 rounded-full blur-3xl -mr-16 -mt-16" />
								<CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
									<CardTitle className="text-sm font-medium">Total Members</CardTitle>
									<Users className="h-5 w-5 text-blue-500" />
								</CardHeader>
								<CardContent>
									<div className="text-3xl font-bold text-blue-600 dark:text-blue-400">
										{members.length}
									</div>
									<p className="text-xs text-muted-foreground mt-1">
										{members.filter((m) => m.is_owner).length} owner
										{members.filter((m) => m.is_owner).length !== 1 ? "s" : ""}
									</p>
								</CardContent>
							</Card>
						</motion.div>

						<motion.div variants={cardVariants}>
							<Card className="relative overflow-hidden border-none bg-gradient-to-br from-violet-500/10 via-violet-500/5 to-transparent">
								<div className="absolute top-0 right-0 w-32 h-32 bg-violet-500/10 rounded-full blur-3xl -mr-16 -mt-16" />
								<CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
									<CardTitle className="text-sm font-medium">Active Roles</CardTitle>
									<Shield className="h-5 w-5 text-violet-500" />
								</CardHeader>
								<CardContent>
									<div className="text-3xl font-bold text-violet-600 dark:text-violet-400">
										{roles.length}
									</div>
									<p className="text-xs text-muted-foreground mt-1">
										{roles.filter((r) => r.is_system_role).length} system roles
									</p>
								</CardContent>
							</Card>
						</motion.div>

						<motion.div variants={cardVariants}>
							<Card className="relative overflow-hidden border-none bg-gradient-to-br from-emerald-500/10 via-emerald-500/5 to-transparent">
								<div className="absolute top-0 right-0 w-32 h-32 bg-emerald-500/10 rounded-full blur-3xl -mr-16 -mt-16" />
								<CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
									<CardTitle className="text-sm font-medium">Active Invites</CardTitle>
									<Link2 className="h-5 w-5 text-emerald-500" />
								</CardHeader>
								<CardContent>
									<div className="text-3xl font-bold text-emerald-600 dark:text-emerald-400">
										{invites.filter((i) => i.is_active).length}
									</div>
									<p className="text-xs text-muted-foreground mt-1">
										{invites.reduce((acc, i) => acc + i.uses_count, 0)} total uses
									</p>
								</CardContent>
							</Card>
						</motion.div>
					</motion.div>

					{/* Tabs Content */}
					<Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
						<div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
							<div className="overflow-x-auto pb-1 md:pb-0">
								<TabsList className="bg-muted/50 p-1 w-full md:w-fit grid grid-cols-3 md:flex">
									<TabsTrigger
										value="members"
										className="gap-1.5 md:gap-2 data-[state=active]:bg-background whitespace-nowrap w-full text-xs md:text-sm flex-1"
									>
										<Users className="h-4 w-4 hidden md:block" />
										<span>Members</span>
										<Badge variant="secondary" className="ml-1 text-xs">
											{members.length}
										</Badge>
									</TabsTrigger>
									<TabsTrigger
										value="roles"
										className="gap-1.5 md:gap-2 data-[state=active]:bg-background whitespace-nowrap w-full text-xs md:text-sm flex-1"
									>
										<Shield className="h-4 w-4 hidden md:block" />
										<span>Roles</span>
										<Badge variant="secondary" className="ml-1 text-xs">
											{roles.length}
										</Badge>
									</TabsTrigger>
									<TabsTrigger
										value="invites"
										className="gap-1.5 md:gap-2 data-[state=active]:bg-background whitespace-nowrap w-full text-xs md:text-sm flex-1"
									>
										<LinkIcon className="h-4 w-4 hidden md:block" />
										<span>Invites</span>
										<Badge variant="secondary" className="ml-1 text-xs">
											{invites.filter((i) => i.is_active).length}
										</Badge>
									</TabsTrigger>
								</TabsList>
							</div>

							{activeTab === "invites" && canInvite && (
								<CreateInviteDialog
									roles={roles}
									onCreateInvite={handleCreateInvite}
									searchSpaceId={searchSpaceId}
									className="w-full md:w-auto"
								/>
							)}
						</div>

						<TabsContent value="members" className="space-y-4">
							<MembersTab
								members={members}
								roles={roles}
								loading={membersLoading}
								onUpdateRole={handleUpdateMember}
								onRemoveMember={handleRemoveMember}
								canManageRoles={hasPermission("members:manage_roles")}
								canRemove={hasPermission("members:remove")}
							/>
						</TabsContent>

						<TabsContent value="roles" className="space-y-4">
							<RolesTab
								roles={roles}
								groupedPermissions={groupedPermissions}
								loading={rolesLoading}
								onUpdateRole={handleUpdateRole}
								onDeleteRole={handleDeleteRole}
								onCreateRole={handleCreateRole}
								canUpdate={hasPermission("roles:update")}
								canDelete={hasPermission("roles:delete")}
								canCreate={hasPermission("roles:create")}
							/>
						</TabsContent>

						<TabsContent value="invites" className="space-y-4">
							<InvitesTab
								invites={invites}
								loading={invitesLoading}
								onRevokeInvite={handleRevokeInvite}
								canRevoke={canInvite}
							/>
						</TabsContent>
					</Tabs>
				</motion.div>
			</div>
		</motion.div>
	);
}

// ============ Members Tab ============

// Helper function to get avatar initials
function getAvatarInitials(member: Membership): string {
	// Try display name first
	if (member.user_display_name) {
		const parts = member.user_display_name.trim().split(/\s+/);
		if (parts.length >= 2) {
			return (parts[0][0] + parts[1][0]).toUpperCase();
		}
		return member.user_display_name.slice(0, 2).toUpperCase();
	}
	// Try email
	if (member.user_email) {
		const emailName = member.user_email.split("@")[0];
		return emailName.slice(0, 2).toUpperCase();
	}
	// Fallback
	return "U";
}

function MembersTab({
	members,
	roles,
	loading,
	onUpdateRole,
	onRemoveMember,
	canManageRoles,
	canRemove,
}: {
	members: Membership[];
	roles: Role[];
	loading: boolean;
	onUpdateRole: (membershipId: number, roleId: number | null) => Promise<Membership>;
	onRemoveMember: (membershipId: number) => Promise<boolean>;
	canManageRoles: boolean;
	canRemove: boolean;
}) {
	const [searchQuery, setSearchQuery] = useState("");

	const filteredMembers = useMemo(() => {
		if (!searchQuery) return members;
		const query = searchQuery.toLowerCase();
		return members.filter(
			(m) =>
				m.user_email?.toLowerCase().includes(query) || m.role?.name.toLowerCase().includes(query)
		);
	}, [members, searchQuery]);

	if (loading) {
		return (
			<div className="flex items-center justify-center py-12">
				<Spinner size="md" className="text-primary" />
			</div>
		);
	}

	return (
		<motion.div
			initial={{ opacity: 0, y: 10 }}
			animate={{ opacity: 1, y: 0 }}
			exit={{ opacity: 0, y: -10 }}
			className="space-y-4"
		>
			{/* Search */}
			<div className="flex items-center gap-4">
				<div className="relative flex-1 max-w-sm">
					<Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
					<Input
						placeholder="Search members"
						value={searchQuery}
						onChange={(e) => setSearchQuery(e.target.value)}
						className="pl-9"
					/>
				</div>
			</div>

			{/* Members List */}
			<div className="rounded-lg border bg-card overflow-x-auto">
				<Table>
					<TableHeader>
						<TableRow className="bg-muted/50">
							<TableHead className="w-auto md:w-[300px] px-2 md:px-4">
								<div className="flex items-center gap-2">
									<Users className="h-4 w-4" />
									Member
								</div>
							</TableHead>
							<TableHead className="px-2 md:px-4">
								<div className="flex items-center gap-2">
									<Shield className="h-4 w-4" />
									Role
								</div>
							</TableHead>
							<TableHead className="hidden md:table-cell">
								<div className="flex items-center gap-2">
									<Calendar className="h-4 w-4" />
									Joined
								</div>
							</TableHead>
							<TableHead className="text-right">
								<div className="flex items-center justify-end gap-2">
									<Settings className="h-4 w-4" />
									Actions
								</div>
							</TableHead>
						</TableRow>
					</TableHeader>
					<TableBody>
						{filteredMembers.length === 0 ? (
							<TableRow>
								<TableCell colSpan={4} className="text-center py-12">
									<div className="flex flex-col items-center gap-2">
										<Users className="h-8 w-8 text-muted-foreground/50" />
										<p className="text-muted-foreground">No members found</p>
									</div>
								</TableCell>
							</TableRow>
						) : (
							filteredMembers.map((member, index) => (
								<motion.tr
									key={member.id}
									initial={{ opacity: 0, y: 10 }}
									animate={{ opacity: 1, y: 0 }}
									transition={{ delay: index * 0.05 }}
									className="group border-b transition-colors hover:bg-muted/50"
								>
									<TableCell className="py-2 px-2 md:py-4 md:px-4 align-middle">
										<div className="flex items-center gap-1.5 md:gap-3">
											<div className="relative">
												{member.user_avatar_url ? (
													<Image
														src={member.user_avatar_url}
														alt={member.user_display_name || member.user_email || "User"}
														width={40}
														height={40}
														className="h-8 w-8 md:h-10 md:w-10 rounded-full object-cover"
													/>
												) : (
													<div className="h-8 w-8 md:h-10 md:w-10 rounded-full bg-gradient-to-br from-primary/20 to-primary/5 flex items-center justify-center">
														<span className="text-xs md:text-sm font-medium text-primary">
															{getAvatarInitials(member)}
														</span>
													</div>
												)}
												{member.is_owner && (
													<div className="absolute -top-1 -right-1 h-5 w-5 rounded-full bg-amber-500 flex items-center justify-center">
														<Crown className="h-3 w-3 text-white" />
													</div>
												)}
											</div>
											<div className="min-w-0">
												<p className="font-medium text-xs md:text-sm truncate">
													{member.user_display_name || member.user_email || "Unknown"}
												</p>
												{member.user_display_name && member.user_email && (
													<p className="text-[10px] md:text-xs text-muted-foreground truncate">
														{member.user_email}
													</p>
												)}
												{member.is_owner && (
													<Badge
														variant="outline"
														className="text-[10px] md:text-xs mt-0.5 md:mt-1 bg-amber-500/10 text-amber-600 border-amber-500/20 hidden md:inline-flex"
													>
														Owner
													</Badge>
												)}
											</div>
										</div>
									</TableCell>
									<TableCell className="py-2 px-2 md:py-4 md:px-4 align-middle">
										{canManageRoles && !member.is_owner ? (
											<Select
												value={member.role_id?.toString() || "none"}
												onValueChange={(value) =>
													onUpdateRole(member.id, value === "none" ? null : Number(value))
												}
											>
												<SelectTrigger className="w-full md:w-[180px] h-8 md:h-10 text-xs md:text-sm">
													<SelectValue placeholder="Select role" />
												</SelectTrigger>
												<SelectContent>
													<SelectItem value="none">No role</SelectItem>
													{roles.map((role) => (
														<SelectItem key={role.id} value={role.id.toString()}>
															{role.name}
														</SelectItem>
													))}
												</SelectContent>
											</Select>
										) : (
											<Badge variant="secondary" className="text-[10px] md:text-xs py-0 md:py-0.5">
												{member.role?.name || "No role"}
											</Badge>
										)}
									</TableCell>
									<TableCell className="hidden md:table-cell">
										<span className="text-sm text-muted-foreground">
											{new Date(member.joined_at).toLocaleDateString()}
										</span>
									</TableCell>
									<TableCell className="text-right py-2 px-2 md:py-4 md:px-4 align-middle">
										{canRemove && !member.is_owner && (
											<AlertDialog>
												<AlertDialogTrigger asChild>
													<Button
														variant="ghost"
														size="sm"
														className="text-destructive hover:text-destructive hover:bg-destructive/10"
													>
														<UserMinus className="h-4 w-4" />
													</Button>
												</AlertDialogTrigger>
												<AlertDialogContent>
													<AlertDialogHeader>
														<AlertDialogTitle>Remove member?</AlertDialogTitle>
														<AlertDialogDescription>
															This will remove{" "}
															<span className="font-medium">{member.user_email}</span> from this
															search space. They will lose access to all resources.
														</AlertDialogDescription>
													</AlertDialogHeader>
													<AlertDialogFooter>
														<AlertDialogCancel>Cancel</AlertDialogCancel>
														<AlertDialogAction
															onClick={() => onRemoveMember(member.id)}
															className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
														>
															Remove
														</AlertDialogAction>
													</AlertDialogFooter>
												</AlertDialogContent>
											</AlertDialog>
										)}
									</TableCell>
								</motion.tr>
							))
						)}
					</TableBody>
				</Table>
			</div>
		</motion.div>
	);
}

// ============ Role Permissions Display ============

// Unified category configuration used across all role-related components
const CATEGORY_CONFIG: Record<
	string,
	{ label: string; icon: LucideIcon; description: string; order: number }
> = {
	documents: {
		label: "Documents",
		icon: FileText,
		description: "Manage files, notes, and content",
		order: 1,
	},
	chats: {
		label: "AI Chats",
		icon: MessageSquare,
		description: "Create and manage AI conversations",
		order: 2,
	},
	comments: {
		label: "Comments",
		icon: MessageCircle,
		description: "Add annotations to documents",
		order: 3,
	},
	llm_configs: {
		label: "AI Models",
		icon: Bot,
		description: "Configure AI model settings",
		order: 4,
	},
	podcasts: {
		label: "Podcasts",
		icon: Mic,
		description: "Generate AI podcasts from content",
		order: 5,
	},
	connectors: {
		label: "Integrations",
		icon: Plug,
		description: "Connect external data sources",
		order: 6,
	},
	logs: {
		label: "Activity Logs",
		icon: Logs,
		description: "View and manage audit trail",
		order: 7,
	},
	members: {
		label: "Team Members",
		icon: Users,
		description: "Manage team membership",
		order: 8,
	},
	roles: {
		label: "Roles",
		icon: Shield,
		description: "Configure role permissions",
		order: 9,
	},
	settings: {
		label: "Settings",
		icon: Settings,
		description: "Manage search space settings",
		order: 10,
	},
	public_sharing: {
		label: "Public Chat Sharing",
		icon: Globe,
		description: "Share chats publicly via links",
		order: 11,
	},
};

const ACTION_LABELS: Record<string, string> = {
	create: "Create",
	read: "Read",
	update: "Update",
	delete: "Delete",
	invite: "Invite",
	view: "View",
	remove: "Remove",
	manage_roles: "Manage Roles",
};

function RolePermissionsDisplay({ permissions }: { permissions: string[] }) {
	if (permissions.includes("*")) {
		return (
			<div className="flex items-center gap-3 p-3 rounded-lg bg-gradient-to-r from-amber-500/10 to-orange-500/10 border border-amber-500/20">
				<div className="h-10 w-10 rounded-full bg-gradient-to-br from-amber-500 to-orange-500 flex items-center justify-center shrink-0">
					<Crown className="h-5 w-5 text-white" />
				</div>
				<div className="flex-1 min-w-0">
					<p className="text-sm font-semibold">Full Access</p>
					<p className="text-xs text-muted-foreground">All permissions granted</p>
				</div>
			</div>
		);
	}

	// Group permissions by category
	const grouped: Record<string, string[]> = {};
	for (const perm of permissions) {
		const [category, action] = perm.split(":");
		if (!grouped[category]) grouped[category] = [];
		grouped[category].push(action);
	}

	// Sort categories by predefined order
	const sortedCategories = Object.keys(grouped).sort((a, b) => {
		const orderA = CATEGORY_CONFIG[a]?.order ?? 99;
		const orderB = CATEGORY_CONFIG[b]?.order ?? 99;
		return orderA - orderB;
	});

	const categoryCount = sortedCategories.length;

	return (
		<Dialog>
			<DialogTrigger asChild>
				<button
					type="button"
					className="w-full flex items-center justify-between p-3 rounded-lg border border-border/50 bg-muted/30 hover:bg-muted/50 transition-colors cursor-pointer text-left"
				>
					<div className="flex items-center gap-3">
						<div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
							<ShieldCheck className="h-5 w-5 text-primary" />
						</div>
						<div>
							<p className="text-sm font-semibold">{permissions.length} Permissions</p>
							<p className="text-xs text-muted-foreground">
								Across {categoryCount} {categoryCount === 1 ? "category" : "categories"}
							</p>
						</div>
					</div>
					<div className="text-xs text-muted-foreground">View details</div>
				</button>
			</DialogTrigger>
			<DialogContent className="w-[92vw] max-w-md p-0 gap-0">
				<DialogHeader className="p-4 md:p-5 border-b">
					<DialogTitle className="flex items-center gap-2 text-base">
						<ShieldCheck className="h-4 w-4 text-primary" />
						Role Permissions
					</DialogTitle>
					<DialogDescription className="text-xs">
						{permissions.length} permissions across {categoryCount} categories
					</DialogDescription>
				</DialogHeader>
				<ScrollArea className="max-h-[55vh]">
					<div className="divide-y divide-border/50">
						{sortedCategories.map((category) => {
							const actions = grouped[category];
							const config = CATEGORY_CONFIG[category] || { label: category, icon: FileText };
							const IconComponent = config.icon;
							return (
								<div
									key={category}
									className="flex items-center justify-between gap-3 px-4 md:px-5 py-2.5"
								>
									<div className="flex items-center gap-2 shrink-0">
										<IconComponent className="h-3.5 w-3.5 text-muted-foreground" />
										<span className="text-sm text-muted-foreground">{config.label}</span>
									</div>
									<div className="flex flex-wrap justify-end gap-1">
										{actions.map((action) => (
											<span
												key={action}
												className="px-1.5 py-0.5 rounded bg-primary/10 text-primary text-[11px] font-medium"
											>
												{ACTION_LABELS[action] || action.replace(/_/g, " ")}
											</span>
										))}
									</div>
								</div>
							);
						})}
					</div>
				</ScrollArea>
			</DialogContent>
		</Dialog>
	);
}

// ============ Roles Tab ============

function RolesTab({
	roles,
	groupedPermissions,
	loading,
	onUpdateRole,
	onDeleteRole,
	onCreateRole,
	canUpdate,
	canDelete,
	canCreate,
}: {
	roles: Role[];
	groupedPermissions: Record<string, PermissionWithDescription[]>;
	loading: boolean;
	onUpdateRole: (
		roleId: number,
		data: {
			name?: string;
			description?: string | null;
			permissions?: string[];
			is_default?: boolean;
		}
	) => Promise<Role>;
	onDeleteRole: (roleId: number) => Promise<boolean>;
	onCreateRole: (data: CreateRoleRequest["data"]) => Promise<Role>;
	canUpdate: boolean;
	canDelete: boolean;
	canCreate: boolean;
}) {
	const [showCreateRole, setShowCreateRole] = useState(false);
	const [editingRoleId, setEditingRoleId] = useState<number | null>(null);

	if (loading) {
		return (
			<div className="flex items-center justify-center py-12">
				<Spinner size="md" className="text-primary" />
			</div>
		);
	}

	return (
		<motion.div
			initial={{ opacity: 0, y: 10 }}
			animate={{ opacity: 1, y: 0 }}
			exit={{ opacity: 0, y: -10 }}
			className="space-y-6"
		>
			{/* Create Role Button / Section */}
			{canCreate && !showCreateRole && (
				<motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex justify-end">
					<Button onClick={() => setShowCreateRole(true)} className="gap-2">
						<Plus className="h-4 w-4" />
						Create Custom Role
					</Button>
				</motion.div>
			)}

			{/* Create Role Form */}
			{showCreateRole && (
				<CreateRoleSection
					groupedPermissions={groupedPermissions}
					onCreateRole={onCreateRole}
					onCancel={() => setShowCreateRole(false)}
				/>
			)}

			{/* Edit Role Form */}
			{editingRoleId !== null &&
				(() => {
					const roleToEdit = roles.find((r) => r.id === editingRoleId);
					if (!roleToEdit) return null;
					return (
						<EditRoleSection
							role={roleToEdit}
							groupedPermissions={groupedPermissions}
							onUpdateRole={onUpdateRole}
							onCancel={() => setEditingRoleId(null)}
						/>
					);
				})()}

			{/* Roles Grid */}
			<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
				{roles.map((role, index) => (
					<motion.div
						key={role.id}
						initial={{ opacity: 0, scale: 0.95 }}
						animate={{ opacity: 1, scale: 1 }}
						transition={{ delay: index * 0.05 }}
					>
						<Card
							className={cn(
								"relative overflow-hidden transition-all hover:shadow-lg",
								role.is_system_role && "ring-1 ring-primary/20"
							)}
						>
							{role.is_system_role && (
								<div className="absolute top-0 right-0 px-2 py-1 bg-primary/10 text-primary text-xs font-medium rounded-bl-lg">
									System Role
								</div>
							)}
							<CardHeader>
								<div className="flex items-start justify-between">
									<div className="flex items-center gap-3">
										<div
											className={cn(
												"h-10 w-10 rounded-lg flex items-center justify-center",
												role.name === "Owner" && "bg-amber-500/20",
												role.name === "Editor" && "bg-blue-500/20",
												role.name === "Viewer" && "bg-gray-500/20",
												!["Owner", "Editor", "Viewer"].includes(role.name) && "bg-primary/20"
											)}
										>
											<ShieldCheck
												className={cn(
													"h-5 w-5",
													role.name === "Owner" && "text-amber-600",
													role.name === "Editor" && "text-blue-600",
													role.name === "Viewer" && "text-gray-600",
													!["Owner", "Editor", "Viewer"].includes(role.name) && "text-primary"
												)}
											/>
										</div>
										<div>
											<CardTitle className="text-lg">{role.name}</CardTitle>
											{role.is_default && (
												<Badge variant="outline" className="text-xs mt-1">
													Default
												</Badge>
											)}
										</div>
									</div>
									{!role.is_system_role && (
										<DropdownMenu>
											<DropdownMenuTrigger asChild>
												<Button variant="ghost" size="icon" className="h-8 w-8">
													<MoreHorizontal className="h-4 w-4" />
												</Button>
											</DropdownMenuTrigger>
											<DropdownMenuContent align="end" onCloseAutoFocus={(e) => e.preventDefault()}>
												{canUpdate && (
													<DropdownMenuItem onClick={() => setEditingRoleId(role.id)}>
														<Edit2 className="h-4 w-4 mr-2" />
														Edit Role
													</DropdownMenuItem>
												)}
												{canDelete && (
													<>
														<DropdownMenuSeparator />
														<AlertDialog>
															<AlertDialogTrigger asChild>
																<DropdownMenuItem
																	className="text-destructive focus:text-destructive"
																	onSelect={(e) => e.preventDefault()}
																>
																	<Trash2 className="h-4 w-4 mr-2" />
																	Delete Role
																</DropdownMenuItem>
															</AlertDialogTrigger>
															<AlertDialogContent>
																<AlertDialogHeader>
																	<AlertDialogTitle>Delete role?</AlertDialogTitle>
																	<AlertDialogDescription>
																		This will permanently delete the "{role.name}" role. Members
																		with this role will lose their permissions.
																	</AlertDialogDescription>
																</AlertDialogHeader>
																<AlertDialogFooter>
																	<AlertDialogCancel>Cancel</AlertDialogCancel>
																	<AlertDialogAction
																		onClick={() => onDeleteRole(role.id)}
																		className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
																	>
																		Delete
																	</AlertDialogAction>
																</AlertDialogFooter>
															</AlertDialogContent>
														</AlertDialog>
													</>
												)}
											</DropdownMenuContent>
										</DropdownMenu>
									)}
								</div>
								{role.description && (
									<CardDescription className="mt-2">{role.description}</CardDescription>
								)}
							</CardHeader>
							<CardContent>
								<RolePermissionsDisplay permissions={role.permissions} />
							</CardContent>
						</Card>
					</motion.div>
				))}
			</div>
		</motion.div>
	);
}

// ============ Invites Tab ============

function InvitesTab({
	invites,
	loading,
	onRevokeInvite,
	canRevoke,
}: {
	invites: Invite[];
	loading: boolean;
	onRevokeInvite: (inviteId: number) => Promise<boolean>;
	canRevoke: boolean;
}) {
	const [copiedId, setCopiedId] = useState<number | null>(null);

	const copyInviteLink = useCallback((invite: Invite) => {
		const link = `${window.location.origin}/invite/${invite.invite_code}`;
		navigator.clipboard.writeText(link);
		setCopiedId(invite.id);
		toast.success("Invite link copied to clipboard");
		setTimeout(() => setCopiedId(null), 2000);
	}, []);

	if (loading) {
		return (
			<div className="flex items-center justify-center py-12">
				<Spinner size="md" className="text-primary" />
			</div>
		);
	}

	if (invites.length === 0) {
		return (
			<motion.div
				initial={{ opacity: 0, y: 10 }}
				animate={{ opacity: 1, y: 0 }}
				className="flex flex-col items-center justify-center py-16 text-center"
			>
				<div className="h-16 w-16 rounded-full bg-muted flex items-center justify-center mb-4">
					<LinkIcon className="h-8 w-8 text-muted-foreground" />
				</div>
				<h3 className="text-lg font-medium mb-1">No invite links</h3>
				<p className="text-muted-foreground max-w-sm">
					Create an invite link to allow others to join your search space with specific roles.
				</p>
			</motion.div>
		);
	}

	return (
		<motion.div
			initial={{ opacity: 0, y: 10 }}
			animate={{ opacity: 1, y: 0 }}
			exit={{ opacity: 0, y: -10 }}
			className="space-y-4"
		>
			{invites.map((invite, index) => {
				const isExpired = invite.expires_at && new Date(invite.expires_at) < new Date();
				const isMaxedOut = invite.max_uses && invite.uses_count >= invite.max_uses;
				const isInactive = !invite.is_active || isExpired || isMaxedOut;

				return (
					<motion.div
						key={invite.id}
						initial={{ opacity: 0, x: -20 }}
						animate={{ opacity: 1, x: 0 }}
						transition={{ delay: index * 0.05 }}
					>
						<Card
							className={cn("relative overflow-hidden transition-all", isInactive && "opacity-60")}
						>
							<CardContent className="p-4">
								<div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
									<div className="flex items-start md:items-center gap-4 flex-1 min-w-0">
										<div
											className={cn(
												"h-10 w-10 md:h-12 md:w-12 rounded-xl flex items-center justify-center shrink-0",
												invite.is_active && !isExpired && !isMaxedOut
													? "bg-emerald-500/20"
													: "bg-muted"
											)}
										>
											<Link2
												className={cn(
													"h-5 w-5 md:h-6 md:w-6",
													invite.is_active && !isExpired && !isMaxedOut
														? "text-emerald-600"
														: "text-muted-foreground"
												)}
											/>
										</div>
										<div className="flex-1 min-w-0">
											<div className="flex items-center gap-2 flex-wrap">
												<p className="font-medium truncate">{invite.name || "Unnamed Invite"}</p>
												{isExpired && (
													<Badge variant="destructive" className="text-xs">
														Expired
													</Badge>
												)}
												{isMaxedOut && (
													<Badge variant="secondary" className="text-xs">
														Maxed
													</Badge>
												)}
												{!invite.is_active && !isExpired && !isMaxedOut && (
													<Badge variant="secondary" className="text-xs">
														Inactive
													</Badge>
												)}
											</div>
											<div className="flex flex-col md:flex-row md:items-center gap-2 md:gap-4 mt-1 text-sm text-muted-foreground">
												<span className="flex items-center gap-1">
													<Shield className="h-3 w-3" />
													{invite.role?.name || "Default role"}
												</span>
												<span className="flex items-center gap-1">
													<Hash className="h-3 w-3" />
													{invite.uses_count}
													{invite.max_uses ? ` / ${invite.max_uses} uses` : " uses"}
												</span>
												{invite.expires_at && (
													<span className="flex items-center gap-1">
														<Clock className="h-3 w-3" />
														{isExpired
															? "Expired"
															: `Exp: ${new Date(invite.expires_at).toLocaleDateString()}`}
													</span>
												)}
											</div>
										</div>
									</div>
									<div className="flex items-center gap-2 shrink-0 self-end md:self-auto">
										<Button
											variant="outline"
											size="sm"
											className="gap-2 flex-1 md:flex-none"
											onClick={() => copyInviteLink(invite)}
											disabled={Boolean(isInactive)}
										>
											{copiedId === invite.id ? (
												<>
													<Check className="h-4 w-4 text-emerald-500" />
													<span className="md:inline">Copied!</span>
												</>
											) : (
												<>
													<Copy className="h-4 w-4" />
													<span className="md:inline">Copy</span>
												</>
											)}
										</Button>
										{canRevoke && (
											<AlertDialog>
												<AlertDialogTrigger asChild>
													<Button
														variant="ghost"
														size="icon"
														className="h-9 w-9 text-destructive hover:text-destructive hover:bg-destructive/10"
													>
														<Trash2 className="h-4 w-4" />
													</Button>
												</AlertDialogTrigger>
												<AlertDialogContent>
													<AlertDialogHeader>
														<AlertDialogTitle>Revoke invite?</AlertDialogTitle>
														<AlertDialogDescription>
															This will permanently delete this invite link. Anyone with this link
															will no longer be able to join.
														</AlertDialogDescription>
													</AlertDialogHeader>
													<AlertDialogFooter>
														<AlertDialogCancel>Cancel</AlertDialogCancel>
														<AlertDialogAction
															onClick={() => onRevokeInvite(invite.id)}
															className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
														>
															Revoke
														</AlertDialogAction>
													</AlertDialogFooter>
												</AlertDialogContent>
											</AlertDialog>
										)}
									</div>
								</div>
							</CardContent>
						</Card>
					</motion.div>
				);
			})}
		</motion.div>
	);
}

// ============ Create Invite Dialog ============

function CreateInviteDialog({
	roles,
	onCreateInvite,
	searchSpaceId,
	className,
}: {
	roles: Role[];
	onCreateInvite: (data: CreateInviteRequest["data"]) => Promise<Invite>;
	searchSpaceId: number;
	className?: string;
}) {
	const [open, setOpen] = useState(false);
	const [creating, setCreating] = useState(false);
	const [name, setName] = useState("");
	const [roleId, setRoleId] = useState<string>("");
	const [maxUses, setMaxUses] = useState<string>("");
	const [expiresAt, setExpiresAt] = useState<Date | undefined>(undefined);
	const [createdInvite, setCreatedInvite] = useState<Invite | null>(null);
	const [copiedLink, setCopiedLink] = useState(false);

	const handleCreate = async () => {
		setCreating(true);
		try {
			const data: CreateInviteRequest["data"] = {};
			if (name) data.name = name;
			if (roleId && roleId !== "default") data.role_id = Number(roleId);
			if (maxUses) data.max_uses = Number(maxUses);
			if (expiresAt) data.expires_at = expiresAt.toISOString();

			const invite = await onCreateInvite(data);
			setCreatedInvite(invite);

			// Track invite sent event
			const roleName =
				roleId && roleId !== "default"
					? roles.find((r) => r.id.toString() === roleId)?.name
					: undefined;
			trackSearchSpaceInviteSent(searchSpaceId, {
				roleName,
				hasExpiry: !!expiresAt,
				hasMaxUses: !!maxUses,
			});
		} catch (error) {
			console.error("Failed to create invite:", error);
		} finally {
			setCreating(false);
		}
	};

	const handleClose = () => {
		setOpen(false);
		setName("");
		setRoleId("");
		setMaxUses("");
		setExpiresAt(undefined);
		setCreatedInvite(null);
		setCopiedLink(false);
	};

	const copyLink = () => {
		if (!createdInvite) return;
		const link = `${window.location.origin}/invite/${createdInvite.invite_code}`;
		navigator.clipboard.writeText(link);
		setCopiedLink(true);
		toast.success("Invite link copied to clipboard");
	};

	return (
		<Dialog open={open} onOpenChange={(v) => (v ? setOpen(true) : handleClose())}>
			<DialogTrigger asChild>
				<Button className={cn("gap-2", className)}>
					<UserPlus className="h-4 w-4" />
					Create Invite
				</Button>
			</DialogTrigger>
			<DialogContent className="w-[92vw] max-w-[92vw] sm:max-w-md p-4 md:p-6">
				{createdInvite ? (
					<>
						<DialogHeader>
							<DialogTitle className="flex items-center gap-2">
								<Check className="h-5 w-5 text-emerald-500" />
								Invite Created!
							</DialogTitle>
							<DialogDescription>
								Share this link to invite people to your search space.
							</DialogDescription>
						</DialogHeader>
						<div className="space-y-3 py-2 md:py-4">
							<div className="flex items-center gap-2 p-3 bg-muted rounded-lg">
								<code className="flex-1 min-w-0 text-sm break-all">
									{window.location.origin}/invite/{createdInvite.invite_code}
								</code>
								<Button variant="outline" size="sm" onClick={copyLink} className="shrink-0">
									{copiedLink ? (
										<Check className="h-4 w-4 text-emerald-500" />
									) : (
										<Copy className="h-4 w-4" />
									)}
								</Button>
							</div>
							<div className="flex flex-wrap gap-2 text-sm text-muted-foreground">
								<span className="flex items-center gap-1">
									<Shield className="h-3 w-3" />
									{createdInvite.role?.name || "Default role"}
								</span>
								{createdInvite.max_uses && (
									<span className="flex items-center gap-1">
										<Hash className="h-3 w-3" />
										Max {createdInvite.max_uses} uses
									</span>
								)}
								{createdInvite.expires_at && (
									<span className="flex items-center gap-1">
										<Clock className="h-3 w-3" />
										Expires {new Date(createdInvite.expires_at).toLocaleDateString()}
									</span>
								)}
							</div>
						</div>
						<DialogFooter>
							<Button onClick={handleClose}>Done</Button>
						</DialogFooter>
					</>
				) : (
					<>
						<DialogHeader>
							<DialogTitle>Create Invite Link</DialogTitle>
							<DialogDescription>
								Create a link to invite people to this search space.
							</DialogDescription>
						</DialogHeader>
						<div className="space-y-3 py-2 md:py-4">
							<div className="space-y-2">
								<Label htmlFor="invite-name">Name (optional)</Label>
								<Input
									id="invite-name"
									placeholder="e.g., Marketing team invite"
									value={name}
									onChange={(e) => setName(e.target.value)}
								/>
							</div>
							<div className="space-y-2">
								<Label htmlFor="invite-role">Role</Label>
								<Select value={roleId} onValueChange={setRoleId}>
									<SelectTrigger>
										<SelectValue placeholder="Select a role (default: Viewer)" />
									</SelectTrigger>
									<SelectContent>
										<SelectItem value="default">Default role (Viewer)</SelectItem>
										{roles
											.filter((r) => r.name !== "Owner")
											.map((role) => (
												<SelectItem key={role.id} value={role.id.toString()}>
													<div className="flex items-center gap-2">
														<Shield className="h-3 w-3" />
														{role.name}
													</div>
												</SelectItem>
											))}
									</SelectContent>
								</Select>
							</div>
							<div className="flex flex-col md:grid md:grid-cols-2 gap-3 md:gap-4">
								<div className="space-y-2">
									<Label htmlFor="max-uses">Max uses (optional)</Label>
									<Input
										id="max-uses"
										type="number"
										min="1"
										placeholder="Unlimited"
										value={maxUses}
										onChange={(e) => setMaxUses(e.target.value)}
									/>
								</div>
								<div className="space-y-2">
									<Label>Expires on (optional)</Label>
									<Popover>
										<PopoverTrigger asChild>
											<Button
												variant="outline"
												className={cn(
													"w-full justify-start text-left font-normal",
													!expiresAt && "text-muted-foreground"
												)}
											>
												<Calendar className="mr-2 h-4 w-4" />
												{expiresAt ? expiresAt.toLocaleDateString() : "Never"}
											</Button>
										</PopoverTrigger>
										<PopoverContent className="w-auto p-0" align="start">
											<CalendarComponent
												mode="single"
												selected={expiresAt}
												onSelect={setExpiresAt}
												disabled={(date) => date < new Date()}
												initialFocus
											/>
										</PopoverContent>
									</Popover>
								</div>
							</div>
						</div>
						<DialogFooter>
							<Button variant="outline" onClick={handleClose}>
								Cancel
							</Button>
							<Button onClick={handleCreate} disabled={creating}>
								{creating ? (
									<>
										<Spinner size="sm" className="mr-2" />
										Creating
									</>
								) : (
									"Create Invite"
								)}
							</Button>
						</DialogFooter>
					</>
				)}
			</DialogContent>
		</Dialog>
	);
}

// ============ Create Role Section ============

// Preset permission sets for quick role creation
const ROLE_PRESETS = {
	editor: {
		name: "Editor",
		description: "Can create, read, and update content, but cannot delete or manage team settings",
		permissions: [
			"documents:create",
			"documents:read",
			"documents:update",
			"chats:create",
			"chats:read",
			"chats:update",
			"comments:create",
			"comments:read",
			"llm_configs:create",
			"llm_configs:read",
			"llm_configs:update",
			"podcasts:create",
			"podcasts:read",
			"podcasts:update",
			"connectors:create",
			"connectors:read",
			"connectors:update",
			"logs:read",
			"members:invite",
			"members:view",
			"roles:read",
			"settings:view",
		],
	},
	viewer: {
		name: "Viewer",
		description: "Read-only access with ability to add comments",
		permissions: [
			"documents:read",
			"chats:read",
			"comments:create",
			"comments:read",
			"llm_configs:read",
			"podcasts:read",
			"connectors:read",
			"logs:read",
			"members:view",
			"roles:read",
			"settings:view",
		],
	},
	contributor: {
		name: "Contributor",
		description: "Can add and manage their own content",
		permissions: [
			"documents:create",
			"documents:read",
			"documents:update",
			"chats:create",
			"chats:read",
			"comments:create",
			"comments:read",
			"llm_configs:read",
			"podcasts:read",
			"connectors:read",
			"logs:read",
			"members:view",
			"roles:read",
			"settings:view",
		],
	},
};

// Action display labels
const ACTION_DISPLAY: Record<string, { label: string; color: string }> = {
	create: { label: "Create", color: "text-emerald-600 bg-emerald-500/10" },
	read: { label: "View", color: "text-blue-600 bg-blue-500/10" },
	update: { label: "Edit", color: "text-amber-600 bg-amber-500/10" },
	delete: { label: "Delete", color: "text-red-600 bg-red-500/10" },
	invite: { label: "Invite", color: "text-violet-600 bg-violet-500/10" },
	view: { label: "View", color: "text-blue-600 bg-blue-500/10" },
	remove: { label: "Remove", color: "text-red-600 bg-red-500/10" },
	manage_roles: { label: "Manage Roles", color: "text-violet-600 bg-violet-500/10" },
};

// Use the imported PermissionInfo type which now includes description
type PermissionWithDescription = PermissionInfo;

function CreateRoleSection({
	groupedPermissions,
	onCreateRole,
	onCancel,
}: {
	groupedPermissions: Record<string, PermissionWithDescription[]>;
	onCreateRole: (data: CreateRoleRequest["data"]) => Promise<Role>;
	onCancel: () => void;
}) {
	const [creating, setCreating] = useState(false);
	const [name, setName] = useState("");
	const [description, setDescription] = useState("");
	const [selectedPermissions, setSelectedPermissions] = useState<string[]>([]);
	const [isDefault, setIsDefault] = useState(false);
	const [expandedCategories, setExpandedCategories] = useState<string[]>([]);

	// Sort categories by order
	const sortedCategories = useMemo(() => {
		return Object.keys(groupedPermissions).sort((a, b) => {
			const orderA = CATEGORY_CONFIG[a]?.order ?? 99;
			const orderB = CATEGORY_CONFIG[b]?.order ?? 99;
			return orderA - orderB;
		});
	}, [groupedPermissions]);

	const handleCreate = async () => {
		if (!name.trim()) {
			toast.error("Please enter a role name");
			return;
		}

		setCreating(true);
		try {
			await onCreateRole({
				name: name.trim(),
				description: description.trim() || null,
				permissions: selectedPermissions,
				is_default: isDefault,
			});
			onCancel();
		} catch (error) {
			console.error("Failed to create role:", error);
		} finally {
			setCreating(false);
		}
	};

	const togglePermission = useCallback((perm: string) => {
		setSelectedPermissions((prev) =>
			prev.includes(perm) ? prev.filter((p) => p !== perm) : [...prev, perm]
		);
	}, []);

	const toggleCategory = useCallback(
		(category: string) => {
			const categoryPerms = groupedPermissions[category]?.map((p) => p.value) || [];
			const allSelected = categoryPerms.every((p) => selectedPermissions.includes(p));

			if (allSelected) {
				setSelectedPermissions((prev) => prev.filter((p) => !categoryPerms.includes(p)));
			} else {
				setSelectedPermissions((prev) => [...new Set([...prev, ...categoryPerms])]);
			}
		},
		[groupedPermissions, selectedPermissions]
	);

	const toggleCategoryExpanded = useCallback((category: string) => {
		setExpandedCategories((prev) =>
			prev.includes(category) ? prev.filter((c) => c !== category) : [...prev, category]
		);
	}, []);

	const applyPreset = useCallback(
		(presetKey: keyof typeof ROLE_PRESETS) => {
			const preset = ROLE_PRESETS[presetKey];
			setSelectedPermissions(preset.permissions);
			if (!name.trim()) {
				setName(preset.name);
				setDescription(preset.description);
			}
			toast.success(`Applied ${preset.name} preset`);
		},
		[name]
	);

	const getCategoryStats = useCallback(
		(category: string) => {
			const perms = groupedPermissions[category] || [];
			const selected = perms.filter((p) => selectedPermissions.includes(p.value)).length;
			return { selected, total: perms.length, allSelected: selected === perms.length };
		},
		[groupedPermissions, selectedPermissions]
	);

	return (
		<motion.div
			initial={{ opacity: 0, y: -10 }}
			animate={{ opacity: 1, y: 0 }}
			exit={{ opacity: 0, y: -10 }}
			className="mb-6"
		>
			<Card className="border-primary/20 bg-gradient-to-br from-primary/5 via-background to-background">
				<CardHeader className="pb-4">
					<div className="flex items-center justify-between">
						<div className="flex items-center gap-3">
							<div className="h-10 w-10 rounded-xl bg-primary/10 flex items-center justify-center">
								<Plus className="h-5 w-5 text-primary" />
							</div>
							<div>
								<CardTitle className="text-lg">Create Custom Role</CardTitle>
								<CardDescription className="text-sm">
									Define permissions for a new role in this search space
								</CardDescription>
							</div>
						</div>
						<Button variant="ghost" size="icon" onClick={onCancel}>
							<Trash2 className="h-4 w-4" />
						</Button>
					</div>
				</CardHeader>
				<CardContent className="space-y-6">
					{/* Quick Start with Presets */}
					<div className="space-y-3">
						<Label className="text-sm font-medium">Quick Start with a Template</Label>
						<div className="grid grid-cols-1 md:grid-cols-3 gap-3">
							{Object.entries(ROLE_PRESETS).map(([key, preset]) => (
								<button
									key={key}
									type="button"
									onClick={() => applyPreset(key as keyof typeof ROLE_PRESETS)}
									className={cn(
										"p-4 rounded-lg border-2 text-left transition-all hover:border-primary/50 hover:bg-primary/5",
										selectedPermissions.length > 0 &&
											preset.permissions.every((p) => selectedPermissions.includes(p))
											? "border-primary bg-primary/10"
											: "border-border"
									)}
								>
									<div className="flex items-center gap-2 mb-1">
										<ShieldCheck
											className={cn(
												"h-4 w-4",
												key === "editor" && "text-blue-600",
												key === "viewer" && "text-gray-600",
												key === "contributor" && "text-emerald-600"
											)}
										/>
										<span className="font-medium text-sm">{preset.name}</span>
									</div>
									<p className="text-xs text-muted-foreground">{preset.description}</p>
								</button>
							))}
						</div>
					</div>

					{/* Role Details */}
					<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
						<div className="space-y-2">
							<Label htmlFor="role-name">Role Name *</Label>
							<Input
								id="role-name"
								placeholder="e.g., Content Manager"
								value={name}
								onChange={(e) => setName(e.target.value)}
							/>
						</div>
						<div className="space-y-2">
							<Label htmlFor="role-description">Description</Label>
							<Input
								id="role-description"
								placeholder="Brief description of this role"
								value={description}
								onChange={(e) => setDescription(e.target.value)}
							/>
						</div>
					</div>

					{/* Default Role Checkbox */}
					<div className="flex items-center gap-3 p-3 rounded-lg bg-muted/50">
						<Checkbox
							id="is-default"
							checked={isDefault}
							onCheckedChange={(checked) => setIsDefault(checked === true)}
						/>
						<div className="flex-1">
							<Label htmlFor="is-default" className="cursor-pointer font-medium">
								Set as default role
							</Label>
							<p className="text-xs text-muted-foreground">
								New members without a specific role will be assigned this role
							</p>
						</div>
					</div>

					{/* Permissions Section */}
					<div className="space-y-3">
						<div className="flex items-center justify-between">
							<Label className="text-sm font-medium">
								Permissions ({selectedPermissions.length} selected)
							</Label>
							<Button
								type="button"
								variant="ghost"
								size="sm"
								className="text-xs h-7"
								onClick={() =>
									setExpandedCategories(
										expandedCategories.length === sortedCategories.length ? [] : sortedCategories
									)
								}
							>
								{expandedCategories.length === sortedCategories.length
									? "Collapse All"
									: "Expand All"}
							</Button>
						</div>

						<div className="space-y-2">
							{sortedCategories.map((category) => {
								const config = CATEGORY_CONFIG[category] || {
									label: category,
									icon: FileText,
									description: "",
									order: 99,
								};
								const IconComponent = config.icon;
								const stats = getCategoryStats(category);
								const isExpanded = expandedCategories.includes(category);
								const perms = groupedPermissions[category] || [];

								return (
									<div key={category} className="rounded-lg border bg-card overflow-hidden">
										{/* Category Header */}
										<div
											className={cn(
												"flex items-center justify-between p-3 cursor-pointer hover:bg-muted/50 transition-colors",
												stats.allSelected && "bg-primary/5"
											)}
											onClick={() => toggleCategoryExpanded(category)}
											onKeyDown={(e) => {
												if (e.key === "Enter" || e.key === " ") {
													e.preventDefault();
													toggleCategoryExpanded(category);
												}
											}}
											tabIndex={0}
											role="button"
										>
											<div className="flex items-center gap-3">
												<div
													className={cn(
														"h-8 w-8 rounded-lg flex items-center justify-center",
														stats.selected > 0 ? "bg-primary/10" : "bg-muted"
													)}
												>
													<IconComponent
														className={cn(
															"h-4 w-4",
															stats.selected > 0 ? "text-primary" : "text-muted-foreground"
														)}
													/>
												</div>
												<div>
													<div className="flex items-center gap-2">
														<span className="font-medium text-sm">{config.label}</span>
														<Badge
															variant={stats.selected > 0 ? "default" : "secondary"}
															className="text-xs h-5"
														>
															{stats.selected}/{stats.total}
														</Badge>
													</div>
													<p className="text-xs text-muted-foreground hidden md:block">
														{config.description}
													</p>
												</div>
											</div>
											<div className="flex items-center gap-2">
												<Checkbox
													checked={stats.allSelected}
													onCheckedChange={() => toggleCategory(category)}
													onClick={(e) => e.stopPropagation()}
													aria-label={`Select all ${config.label} permissions`}
												/>
												<motion.div
													animate={{ rotate: isExpanded ? 180 : 0 }}
													transition={{ duration: 0.2 }}
												>
													<svg
														className="h-4 w-4 text-muted-foreground"
														fill="none"
														viewBox="0 0 24 24"
														stroke="currentColor"
													>
														<path
															strokeLinecap="round"
															strokeLinejoin="round"
															strokeWidth={2}
															d="M19 9l-7 7-7-7"
														/>
													</svg>
												</motion.div>
											</div>
										</div>

										{/* Permissions List */}
										{isExpanded && (
											<motion.div
												initial={{ height: 0, opacity: 0 }}
												animate={{ height: "auto", opacity: 1 }}
												exit={{ height: 0, opacity: 0 }}
												transition={{ duration: 0.2 }}
												className="border-t"
											>
												<div className="p-3 space-y-1">
													{perms.map((perm) => {
														const action = perm.value.split(":")[1];
														const actionConfig = ACTION_DISPLAY[action] || {
															label: action,
															color: "text-gray-600 bg-gray-500/10",
														};
														const isSelected = selectedPermissions.includes(perm.value);

														return (
															<div
																key={perm.value}
																className={cn(
																	"flex items-center justify-between p-2 rounded-md cursor-pointer transition-colors",
																	isSelected
																		? "bg-primary/10 hover:bg-primary/15"
																		: "hover:bg-muted/50"
																)}
																onClick={() => togglePermission(perm.value)}
																onKeyDown={(e) => {
																	if (e.key === "Enter" || e.key === " ") {
																		e.preventDefault();
																		togglePermission(perm.value);
																	}
																}}
																tabIndex={0}
																role="checkbox"
																aria-checked={isSelected}
															>
																<div className="flex items-center gap-3 flex-1 min-w-0">
																	<Checkbox
																		checked={isSelected}
																		onCheckedChange={() => togglePermission(perm.value)}
																		onClick={(e) => e.stopPropagation()}
																	/>
																	<div className="flex-1 min-w-0">
																		<div className="flex items-center gap-2">
																			<span
																				className={cn(
																					"text-xs font-medium px-2 py-0.5 rounded",
																					actionConfig.color
																				)}
																			>
																				{actionConfig.label}
																			</span>
																		</div>
																		<p className="text-xs text-muted-foreground mt-0.5 truncate">
																			{perm.description}
																		</p>
																	</div>
																</div>
															</div>
														);
													})}
												</div>
											</motion.div>
										)}
									</div>
								);
							})}
						</div>
					</div>

					{/* Actions */}
					<div className="flex items-center justify-end gap-3 pt-4 border-t">
						<Button variant="outline" onClick={onCancel}>
							Cancel
						</Button>
						<Button onClick={handleCreate} disabled={creating || !name.trim()}>
							{creating ? (
								<>
									<Spinner size="sm" className="mr-2" />
									Creating...
								</>
							) : (
								<>
									<Check className="h-4 w-4 mr-2" />
									Create Role
								</>
							)}
						</Button>
					</div>
				</CardContent>
			</Card>
		</motion.div>
	);
}

function EditRoleSection({
	role,
	groupedPermissions,
	onUpdateRole,
	onCancel,
}: {
	role: Role;
	groupedPermissions: Record<string, PermissionWithDescription[]>;
	onUpdateRole: (
		roleId: number,
		data: {
			name?: string;
			description?: string | null;
			permissions?: string[];
			is_default?: boolean;
		}
	) => Promise<Role>;
	onCancel: () => void;
}) {
	const [saving, setSaving] = useState(false);
	const [name, setName] = useState(role.name);
	const [description, setDescription] = useState(role.description || "");
	const [selectedPermissions, setSelectedPermissions] = useState<string[]>(role.permissions);
	const [isDefault, setIsDefault] = useState(role.is_default);
	const [expandedCategories, setExpandedCategories] = useState<string[]>([]);

	// Sort categories by order
	const sortedCategories = useMemo(() => {
		return Object.keys(groupedPermissions).sort((a, b) => {
			const orderA = CATEGORY_CONFIG[a]?.order ?? 99;
			const orderB = CATEGORY_CONFIG[b]?.order ?? 99;
			return orderA - orderB;
		});
	}, [groupedPermissions]);

	const handleSave = async () => {
		if (!name.trim()) {
			toast.error("Please enter a role name");
			return;
		}

		setSaving(true);
		try {
			await onUpdateRole(role.id, {
				name: name.trim(),
				description: description.trim() || null,
				permissions: selectedPermissions,
				is_default: isDefault,
			});
			toast.success("Role updated successfully");
			onCancel();
		} catch (error) {
			console.error("Failed to update role:", error);
			toast.error("Failed to update role");
		} finally {
			setSaving(false);
		}
	};

	const togglePermission = useCallback((perm: string) => {
		setSelectedPermissions((prev) =>
			prev.includes(perm) ? prev.filter((p) => p !== perm) : [...prev, perm]
		);
	}, []);

	const toggleCategory = useCallback(
		(category: string) => {
			const categoryPerms = groupedPermissions[category]?.map((p) => p.value) || [];
			const allSelected = categoryPerms.every((p) => selectedPermissions.includes(p));

			if (allSelected) {
				setSelectedPermissions((prev) => prev.filter((p) => !categoryPerms.includes(p)));
			} else {
				setSelectedPermissions((prev) => [...new Set([...prev, ...categoryPerms])]);
			}
		},
		[groupedPermissions, selectedPermissions]
	);

	const toggleCategoryExpanded = useCallback((category: string) => {
		setExpandedCategories((prev) =>
			prev.includes(category) ? prev.filter((c) => c !== category) : [...prev, category]
		);
	}, []);

	const getCategoryStats = useCallback(
		(category: string) => {
			const perms = groupedPermissions[category] || [];
			const selected = perms.filter((p) => selectedPermissions.includes(p.value)).length;
			return { selected, total: perms.length, allSelected: selected === perms.length };
		},
		[groupedPermissions, selectedPermissions]
	);

	return (
		<motion.div
			initial={{ opacity: 0, y: -10 }}
			animate={{ opacity: 1, y: 0 }}
			exit={{ opacity: 0, y: -10 }}
			className="mb-6"
		>
			<Card className="border-primary/20 bg-gradient-to-br from-primary/5 via-background to-background">
				<CardHeader className="pb-4">
					<div className="flex items-center justify-between">
						<div className="flex items-center gap-3">
							<div className="h-10 w-10 rounded-xl bg-primary/10 flex items-center justify-center">
								<Edit2 className="h-5 w-5 text-primary" />
							</div>
							<div>
								<CardTitle className="text-lg">Edit Role</CardTitle>
								<CardDescription className="text-sm">
									Modify permissions for "{role.name}"
								</CardDescription>
							</div>
						</div>
						<Button variant="ghost" size="icon" onClick={onCancel}>
							<Trash2 className="h-4 w-4" />
						</Button>
					</div>
				</CardHeader>
				<CardContent className="space-y-6">
					{/* Role Details */}
					<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
						<div className="space-y-2">
							<Label htmlFor="edit-role-name">Role Name *</Label>
							<Input
								id="edit-role-name"
								placeholder="e.g., Content Manager"
								value={name}
								onChange={(e) => setName(e.target.value)}
							/>
						</div>
						<div className="space-y-2">
							<Label htmlFor="edit-role-description">Description</Label>
							<Input
								id="edit-role-description"
								placeholder="Brief description of this role"
								value={description}
								onChange={(e) => setDescription(e.target.value)}
							/>
						</div>
					</div>

					{/* Default Role Checkbox */}
					<div className="flex items-center gap-3 p-3 rounded-lg bg-muted/50">
						<Checkbox
							id="edit-is-default"
							checked={isDefault}
							onCheckedChange={(checked) => setIsDefault(checked === true)}
						/>
						<div className="flex-1">
							<Label htmlFor="edit-is-default" className="cursor-pointer font-medium">
								Set as default role
							</Label>
							<p className="text-xs text-muted-foreground">
								New members without a specific role will be assigned this role
							</p>
						</div>
					</div>

					{/* Permissions Section */}
					<div className="space-y-3">
						<div className="flex items-center justify-between">
							<Label className="text-sm font-medium">
								Permissions ({selectedPermissions.length} selected)
							</Label>
							<Button
								type="button"
								variant="ghost"
								size="sm"
								className="text-xs h-7"
								onClick={() =>
									setExpandedCategories(
										expandedCategories.length === sortedCategories.length ? [] : sortedCategories
									)
								}
							>
								{expandedCategories.length === sortedCategories.length
									? "Collapse All"
									: "Expand All"}
							</Button>
						</div>

						<div className="space-y-2">
							{sortedCategories.map((category) => {
								const config = CATEGORY_CONFIG[category] || {
									label: category,
									icon: FileText,
									description: "",
									order: 99,
								};
								const IconComponent = config.icon;
								const stats = getCategoryStats(category);
								const isExpanded = expandedCategories.includes(category);
								const perms = groupedPermissions[category] || [];

								return (
									<div key={category} className="rounded-lg border bg-card overflow-hidden">
										{/* Category Header */}
										<div
											className={cn(
												"flex items-center justify-between p-3 cursor-pointer hover:bg-muted/50 transition-colors",
												stats.allSelected && "bg-primary/5"
											)}
											onClick={() => toggleCategoryExpanded(category)}
											onKeyDown={(e) => {
												if (e.key === "Enter" || e.key === " ") {
													e.preventDefault();
													toggleCategoryExpanded(category);
												}
											}}
											tabIndex={0}
											role="button"
										>
											<div className="flex items-center gap-3">
												<div
													className={cn(
														"h-8 w-8 rounded-lg flex items-center justify-center",
														stats.selected > 0 ? "bg-primary/10" : "bg-muted"
													)}
												>
													<IconComponent
														className={cn(
															"h-4 w-4",
															stats.selected > 0 ? "text-primary" : "text-muted-foreground"
														)}
													/>
												</div>
												<div>
													<div className="flex items-center gap-2">
														<span className="font-medium text-sm">{config.label}</span>
														<Badge
															variant={stats.selected > 0 ? "default" : "secondary"}
															className="text-xs h-5"
														>
															{stats.selected}/{stats.total}
														</Badge>
													</div>
													<p className="text-xs text-muted-foreground hidden md:block">
														{config.description}
													</p>
												</div>
											</div>
											<div className="flex items-center gap-2">
												<Checkbox
													checked={stats.allSelected}
													onCheckedChange={() => toggleCategory(category)}
													onClick={(e) => e.stopPropagation()}
													aria-label={`Select all ${config.label} permissions`}
												/>
												<motion.div
													animate={{ rotate: isExpanded ? 180 : 0 }}
													transition={{ duration: 0.2 }}
												>
													<svg
														className="h-4 w-4 text-muted-foreground"
														fill="none"
														viewBox="0 0 24 24"
														stroke="currentColor"
													>
														<path
															strokeLinecap="round"
															strokeLinejoin="round"
															strokeWidth={2}
															d="M19 9l-7 7-7-7"
														/>
													</svg>
												</motion.div>
											</div>
										</div>

										{/* Permissions List */}
										{isExpanded && (
											<motion.div
												initial={{ height: 0, opacity: 0 }}
												animate={{ height: "auto", opacity: 1 }}
												exit={{ height: 0, opacity: 0 }}
												transition={{ duration: 0.2 }}
												className="border-t"
											>
												<div className="p-3 space-y-1">
													{perms.map((perm) => {
														const action = perm.value.split(":")[1];
														const actionConfig = ACTION_DISPLAY[action] || {
															label: action,
															color: "text-gray-600 bg-gray-500/10",
														};
														const isSelected = selectedPermissions.includes(perm.value);

														return (
															<div
																key={perm.value}
																className={cn(
																	"flex items-center justify-between p-2 rounded-md cursor-pointer transition-colors",
																	isSelected
																		? "bg-primary/10 hover:bg-primary/15"
																		: "hover:bg-muted/50"
																)}
																onClick={() => togglePermission(perm.value)}
																onKeyDown={(e) => {
																	if (e.key === "Enter" || e.key === " ") {
																		e.preventDefault();
																		togglePermission(perm.value);
																	}
																}}
																tabIndex={0}
																role="checkbox"
																aria-checked={isSelected}
															>
																<div className="flex items-center gap-3 flex-1 min-w-0">
																	<Checkbox
																		checked={isSelected}
																		onCheckedChange={() => togglePermission(perm.value)}
																		onClick={(e) => e.stopPropagation()}
																	/>
																	<div className="flex-1 min-w-0">
																		<div className="flex items-center gap-2">
																			<span
																				className={cn(
																					"text-xs font-medium px-2 py-0.5 rounded",
																					actionConfig.color
																				)}
																			>
																				{actionConfig.label}
																			</span>
																		</div>
																		<p className="text-xs text-muted-foreground mt-0.5 truncate">
																			{perm.description}
																		</p>
																	</div>
																</div>
															</div>
														);
													})}
												</div>
											</motion.div>
										)}
									</div>
								);
							})}
						</div>
					</div>

					{/* Actions */}
					<div className="flex items-center justify-end gap-3 pt-4 border-t">
						<Button variant="outline" onClick={onCancel}>
							Cancel
						</Button>
						<Button onClick={handleSave} disabled={saving || !name.trim()}>
							{saving ? (
								<>
									<Spinner size="sm" className="mr-2" />
									Saving...
								</>
							) : (
								<>
									<Check className="h-4 w-4 mr-2" />
									Save Changes
								</>
							)}
						</Button>
					</div>
				</CardContent>
			</Card>
		</motion.div>
	);
}
