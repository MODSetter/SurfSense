"use client";

import { useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import {
	Calendar,
	Check,
	ChevronDown,
	Clock,
	Copy,
	Crown,
	Hash,
	Shield,
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
import { Button } from "@/components/ui/button";
import { Calendar as CalendarComponent } from "@/components/ui/calendar";
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
import type { Role } from "@/contracts/types/roles.types";
import { invitesApiService } from "@/lib/apis/invites-api.service";
import { rolesApiService } from "@/lib/apis/roles-api.service";
import { formatRelativeDate } from "@/lib/format-date";
import { trackSearchSpaceInviteSent, trackSearchSpaceUsersViewed } from "@/lib/posthog/events";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { cn } from "@/lib/utils";

const AVATAR_COLORS = [
	"bg-amber-600",
	"bg-blue-600",
	"bg-emerald-600",
	"bg-violet-600",
	"bg-rose-600",
	"bg-cyan-600",
	"bg-orange-600",
	"bg-teal-600",
	"bg-pink-600",
	"bg-indigo-600",
];

function getAvatarColor(identifier: string): string {
	let hash = 0;
	for (let i = 0; i < identifier.length; i++) {
		hash = identifier.charCodeAt(i) + ((hash << 5) - hash);
	}
	return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}

function getAvatarInitials(member: Membership): string {
	if (member.user_display_name) {
		const parts = member.user_display_name.trim().split(/\s+/);
		if (parts.length >= 2) {
			return (parts[0][0] + parts[1][0]).toUpperCase();
		}
		return member.user_display_name.slice(0, 2).toUpperCase();
	}
	if (member.user_email) {
		const emailName = member.user_email.split("@")[0];
		return emailName.slice(0, 2).toUpperCase();
	}
	return "U";
}

function getInviteInitials(invite: Invite): string {
	if (invite.name) {
		const parts = invite.name.trim().split(/\s+/);
		if (parts.length >= 2) {
			return (parts[0][0] + parts[1][0]).toUpperCase();
		}
		return invite.name.slice(0, 2).toUpperCase();
	}
	return "IN";
}

export default function TeamManagementPage() {
	const params = useParams();
	const searchSpaceId = Number(params.search_space_id);

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
	} = useAtomValue(membersAtom);

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

	const handleUpdateMember = useCallback(
		async (membershipId: number, roleId: number | null): Promise<Membership> => {
			const request: UpdateMembershipRequest = {
				search_space_id: searchSpaceId,
				membership_id: membershipId,
				data: { role_id: roleId },
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
	} = useQuery({
		queryKey: cacheKeys.roles.all(searchSpaceId.toString()),
		queryFn: () => rolesApiService.getRoles({ search_space_id: searchSpaceId }),
		enabled: !!searchSpaceId,
	});

	const {
		data: invites = [],
	} = useQuery({
		queryKey: cacheKeys.invites.all(searchSpaceId.toString()),
		queryFn: () => invitesApiService.getInvites({ search_space_id: searchSpaceId }),
		staleTime: 5 * 60 * 1000,
	});

	const activeInvites = useMemo(() => invites.filter((i) => i.is_active), [invites]);

	const canInvite = hasPermission("members:invite");
	const canManageRoles = hasPermission("members:manage_roles");
	const canRemove = hasPermission("members:remove");

	useEffect(() => {
		if (members.length > 0 && !membersLoading) {
			const ownerCount = members.filter((m) => m.is_owner).length;
			trackSearchSpaceUsersViewed(searchSpaceId, members.length, ownerCount);
		}
	}, [members, membersLoading, searchSpaceId]);

	if (accessLoading || membersLoading) {
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
			initial={{ opacity: 0 }}
			animate={{ opacity: 1 }}
			transition={{ duration: 0.3 }}
			className="min-h-screen bg-background"
		>
			<div className="container max-w-5xl mx-auto p-4 md:p-6 lg:p-8">
				<div className="space-y-6">
					{/* Header row: Invite button on left, member count on right */}
					<div className="flex items-center justify-between">
						{canInvite && (
							<CreateInviteDialog
								roles={roles}
								onCreateInvite={handleCreateInvite}
								searchSpaceId={searchSpaceId}
							/>
						)}
						{!canInvite && <div />}
						<p className="text-sm text-muted-foreground">
							{members.length} {members.length === 1 ? "member" : "members"}
						</p>
					</div>

					{/* Members & Invites Table */}
					<div className="rounded-xl border bg-card overflow-hidden">
						<Table>
							<TableHeader>
								<TableRow className="bg-muted/30 hover:bg-muted/30">
									<TableHead className="w-[40%] px-4 md:px-6 font-normal text-muted-foreground">
										Name
									</TableHead>
									<TableHead className="hidden md:table-cell font-normal text-muted-foreground">
										Last logged in
									</TableHead>
									<TableHead className="text-right px-4 md:px-6 font-normal text-muted-foreground">
										Role
									</TableHead>
								</TableRow>
							</TableHeader>
							<TableBody>
								{members.map((member) => (
									<MemberRow
										key={`member-${member.id}`}
										member={member}
										roles={roles}
										canManageRoles={canManageRoles}
										canRemove={canRemove}
										onUpdateRole={handleUpdateMember}
										onRemoveMember={handleRemoveMember}
									/>
								))}
								{activeInvites.map((invite) => (
									<InviteRow
										key={`invite-${invite.id}`}
										invite={invite}
										canRevoke={canInvite}
										onRevokeInvite={handleRevokeInvite}
									/>
								))}
								{members.length === 0 && activeInvites.length === 0 && (
									<TableRow>
										<TableCell colSpan={3} className="text-center py-12">
											<div className="flex flex-col items-center gap-2">
												<Users className="h-8 w-8 text-muted-foreground/50" />
												<p className="text-muted-foreground">No members yet</p>
											</div>
										</TableCell>
									</TableRow>
								)}
							</TableBody>
						</Table>
					</div>
				</div>
			</div>
		</motion.div>
	);
}

// ============ Member Row ============

function MemberRow({
	member,
	roles,
	canManageRoles,
	canRemove,
	onUpdateRole,
	onRemoveMember,
}: {
	member: Membership;
	roles: Role[];
	canManageRoles: boolean;
	canRemove: boolean;
	onUpdateRole: (membershipId: number, roleId: number | null) => Promise<Membership>;
	onRemoveMember: (membershipId: number) => Promise<boolean>;
}) {
	const initials = getAvatarInitials(member);
	const avatarColor = getAvatarColor(member.user_id);
	const displayName = member.user_display_name || member.user_email || "Unknown";
	const roleName = member.is_owner ? "Owner" : (member.role?.name || "No role");
	const showActions = canManageRoles || canRemove;

	return (
		<TableRow className="group hover:bg-muted/30">
			{/* Name + Avatar */}
			<TableCell className="py-3 px-4 md:px-6">
				<div className="flex items-center gap-3">
					<div className="relative shrink-0">
						{member.user_avatar_url ? (
							<Image
								src={member.user_avatar_url}
								alt={displayName}
								width={40}
								height={40}
								className="h-10 w-10 rounded-full object-cover"
							/>
						) : (
							<div
								className={cn(
									"h-10 w-10 rounded-full flex items-center justify-center text-white font-medium text-sm",
									avatarColor
								)}
							>
								{initials}
							</div>
						)}
						{member.is_owner && (
							<div className="absolute -top-1 -right-1 h-4 w-4 rounded-full bg-amber-500 flex items-center justify-center ring-2 ring-background">
								<Crown className="h-2.5 w-2.5 text-white" />
							</div>
						)}
					</div>
					<div className="min-w-0">
						<p className="font-medium text-sm truncate">{displayName}</p>
						{member.user_display_name && member.user_email && (
							<p className="text-xs text-muted-foreground truncate">{member.user_email}</p>
						)}
					</div>
				</div>
			</TableCell>

			{/* Last logged in */}
			<TableCell className="hidden md:table-cell py-3 text-sm text-muted-foreground">
				{formatRelativeDate(member.joined_at)}
			</TableCell>

			{/* Role */}
			<TableCell className="text-right py-3 px-4 md:px-6">
				{showActions && !member.is_owner ? (
					<DropdownMenu>
						<DropdownMenuTrigger asChild>
							<button
								type="button"
								className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
							>
								{roleName}
								<ChevronDown className="h-4 w-4" />
							</button>
						</DropdownMenuTrigger>
						<DropdownMenuContent align="end" onCloseAutoFocus={(e) => e.preventDefault()}>
							{canManageRoles && (
								<>
									{roles.map((role) => (
										<DropdownMenuItem
											key={role.id}
											onClick={() => onUpdateRole(member.id, role.id)}
											className={cn(
												member.role_id === role.id && "bg-accent"
											)}
										>
											{role.name}
										</DropdownMenuItem>
									))}
									<DropdownMenuItem
										onClick={() => onUpdateRole(member.id, null)}
										className={cn(!member.role_id && "bg-accent")}
									>
										No role
									</DropdownMenuItem>
								</>
							)}
							{canManageRoles && canRemove && <DropdownMenuSeparator />}
							{canRemove && (
								<AlertDialog>
									<AlertDialogTrigger asChild>
										<DropdownMenuItem
											className="text-destructive focus:text-destructive"
											onSelect={(e) => e.preventDefault()}
										>
											<UserMinus className="h-4 w-4 mr-2" />
											Remove member
										</DropdownMenuItem>
									</AlertDialogTrigger>
									<AlertDialogContent>
										<AlertDialogHeader>
											<AlertDialogTitle>Remove member?</AlertDialogTitle>
											<AlertDialogDescription>
												This will remove{" "}
												<span className="font-medium">{member.user_email}</span>{" "}
												from this search space. They will lose access to all resources.
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
						</DropdownMenuContent>
					</DropdownMenu>
				) : (
					<span className={cn("text-sm", member.is_owner ? "text-foreground" : "text-muted-foreground")}>
						{roleName}
						{!member.is_owner && <ChevronDown className="inline h-4 w-4 ml-1" />}
					</span>
				)}
			</TableCell>
		</TableRow>
	);
}

// ============ Invite Row ============

function InviteRow({
	invite,
	canRevoke,
	onRevokeInvite,
}: {
	invite: Invite;
	canRevoke: boolean;
	onRevokeInvite: (inviteId: number) => Promise<boolean>;
}) {
	const initials = getInviteInitials(invite);
	const avatarColor = getAvatarColor(invite.invite_code);
	const displayName = invite.name || "Unnamed Invite";

	return (
		<TableRow className="group hover:bg-muted/30">
			<TableCell className="py-3 px-4 md:px-6">
				<div className="flex items-center gap-3">
					<div
						className={cn(
							"h-10 w-10 rounded-full flex items-center justify-center text-white font-medium text-sm shrink-0 opacity-60",
							avatarColor
						)}
					>
						{initials}
					</div>
					<div className="min-w-0">
						<p className="font-medium text-sm truncate text-muted-foreground">{displayName}</p>
						{invite.role?.name && (
							<p className="text-xs text-muted-foreground/70 truncate">
								Will join as {invite.role.name}
							</p>
						)}
					</div>
				</div>
			</TableCell>

			<TableCell className="hidden md:table-cell py-3 text-sm text-muted-foreground">
				Never
			</TableCell>

			<TableCell className="text-right py-3 px-4 md:px-6">
				{canRevoke ? (
					<DropdownMenu>
						<DropdownMenuTrigger asChild>
							<button
								type="button"
								className="inline-flex items-center gap-1.5 text-sm text-muted-foreground/60"
							>
								Invited
								<ChevronDown className="h-4 w-4" />
							</button>
						</DropdownMenuTrigger>
						<DropdownMenuContent align="end" onCloseAutoFocus={(e) => e.preventDefault()}>
							<DropdownMenuItem
								onClick={() => {
									const link = `${window.location.origin}/invite/${invite.invite_code}`;
									navigator.clipboard.writeText(link);
									toast.success("Invite link copied");
								}}
							>
								<Copy className="h-4 w-4 mr-2" />
								Copy invite link
							</DropdownMenuItem>
							<DropdownMenuSeparator />
							<AlertDialog>
								<AlertDialogTrigger asChild>
									<DropdownMenuItem
										className="text-destructive focus:text-destructive"
										onSelect={(e) => e.preventDefault()}
									>
										<Trash2 className="h-4 w-4 mr-2" />
										Revoke invite
									</DropdownMenuItem>
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
						</DropdownMenuContent>
					</DropdownMenu>
				) : (
					<span className="text-sm text-muted-foreground/60">Invited</span>
				)}
			</TableCell>
		</TableRow>
	);
}

// ============ Create Invite Dialog ============

function CreateInviteDialog({
	roles,
	onCreateInvite,
	searchSpaceId,
}: {
	roles: Role[];
	onCreateInvite: (data: CreateInviteRequest["data"]) => Promise<Invite>;
	searchSpaceId: number;
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
				<Button variant="outline" className="gap-2">
					<UserPlus className="h-4 w-4" />
					Invite members
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
							<DialogTitle>Invite Members</DialogTitle>
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
