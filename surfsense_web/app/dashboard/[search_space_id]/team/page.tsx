"use client";

import { useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import {
	Calendar,
	Check,
	ChevronDown,
	ChevronFirst,
	ChevronLast,
	ChevronLeft,
	ChevronRight,
	Clock,
	Copy,
	Hash,
	Link2,
	ShieldUser,
	Trash2,
	User,
	UserPlus,
	Users,
} from "lucide-react";
import { motion } from "motion/react";
import Image from "next/image";
import { useParams, useRouter } from "next/navigation";
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
import { Skeleton } from "@/components/ui/skeleton";
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

const PAGE_SIZE = 5;

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

	const { data: members = [], isLoading: membersLoading } = useAtomValue(membersAtom);

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

	const { data: roles = [] } = useQuery({
		queryKey: cacheKeys.roles.all(searchSpaceId.toString()),
		queryFn: () => rolesApiService.getRoles({ search_space_id: searchSpaceId }),
		enabled: !!searchSpaceId,
	});

	const { data: invites = [] } = useQuery({
		queryKey: cacheKeys.invites.all(searchSpaceId.toString()),
		queryFn: () => invitesApiService.getInvites({ search_space_id: searchSpaceId }),
		staleTime: 5 * 60 * 1000,
	});

	const activeInvites = useMemo(() => invites.filter((i) => i.is_active), [invites]);

	const canInvite = hasPermission("members:invite");
	const canManageRoles = hasPermission("members:manage_roles");
	const canRemove = hasPermission("members:remove");

	const owners = useMemo(() => members.filter((m) => m.is_owner), [members]);
	const nonOwnerMembers = useMemo(() => members.filter((m) => !m.is_owner), [members]);

	const [pageIndex, setPageIndex] = useState(0);
	const totalItems = nonOwnerMembers.length;
	const lastPage = Math.max(0, Math.ceil(totalItems / PAGE_SIZE) - 1);

	useEffect(() => {
		if (pageIndex > lastPage) setPageIndex(lastPage);
	}, [pageIndex, lastPage]);

	const paginatedMembers = useMemo(() => {
		const start = pageIndex * PAGE_SIZE;
		const end = start + PAGE_SIZE;
		return nonOwnerMembers.slice(
			Math.min(start, nonOwnerMembers.length),
			Math.min(end, nonOwnerMembers.length)
		);
	}, [nonOwnerMembers, pageIndex]);

	const displayStart = totalItems > 0 ? pageIndex * PAGE_SIZE + 1 : 0;
	const displayEnd = Math.min((pageIndex + 1) * PAGE_SIZE, totalItems);
	const canPrev = pageIndex > 0;
	const canNext = displayEnd < totalItems;

	useEffect(() => {
		if (members.length > 0 && !membersLoading) {
			const ownerCount = members.filter((m) => m.is_owner).length;
			trackSearchSpaceUsersViewed(searchSpaceId, members.length, ownerCount);
		}
	}, [members, membersLoading, searchSpaceId]);

	if (accessLoading || membersLoading) {
		return (
			<motion.div
				initial={{ opacity: 0 }}
				animate={{ opacity: 1 }}
				transition={{ duration: 0.3 }}
				className="bg-background select-none"
			>
				<div className="container max-w-5xl mx-auto p-4 md:p-6 lg:p-8 pt-20 md:pt-24 lg:pt-28">
					<div className="space-y-6">
						<div className="flex items-center justify-between">
							<Skeleton className="h-9 w-36 rounded-md" />
							<Skeleton className="h-4 w-20" />
						</div>
						<div className="rounded-lg border border-border/40 bg-background overflow-hidden">
							<Table className="table-fixed w-full">
								<TableHeader>
									<TableRow className="hover:bg-transparent border-b border-border/40">
										<TableHead className="w-[45%] px-4 md:px-6 border-r border-border/40">
											<Skeleton className="h-3 w-16" />
										</TableHead>
										<TableHead className="hidden md:table-cell w-[25%] border-r border-border/40">
											<Skeleton className="h-3 w-24" />
										</TableHead>
										<TableHead className="w-[30%] px-4 md:px-6">
											<div className="flex justify-end">
												<Skeleton className="h-3 w-12" />
											</div>
										</TableHead>
									</TableRow>
								</TableHeader>
								<TableBody>
									{Array.from({ length: PAGE_SIZE }).map((_, i) => (
										<TableRow
											key={`skeleton-${i}`}
											className="border-b border-border/40 hover:bg-transparent"
										>
											<TableCell className="w-[45%] py-2.5 px-4 md:px-6 border-r border-border/40">
												<div className="flex items-center gap-3">
													<Skeleton className="h-10 w-10 rounded-full shrink-0" />
													<div className="flex-1 min-w-0 space-y-1.5">
														<Skeleton className="h-4 w-[60%]" />
														<Skeleton className="h-3 w-[40%]" />
													</div>
												</div>
											</TableCell>
											<TableCell className="hidden md:table-cell w-[25%] py-2.5 border-r border-border/40">
												<Skeleton className="h-4 w-24" />
											</TableCell>
											<TableCell className="w-[30%] py-2.5 px-4 md:px-6">
												<div className="flex justify-end">
													<Skeleton className="h-4 w-16" />
												</div>
											</TableCell>
										</TableRow>
									))}
								</TableBody>
							</Table>
						</div>
					</div>
				</div>
			</motion.div>
		);
	}

	return (
		<motion.div
			initial={{ opacity: 0 }}
			animate={{ opacity: 1 }}
			transition={{ duration: 0.3 }}
			className="bg-background select-none"
		>
			<div className="container max-w-5xl mx-auto p-4 md:p-6 lg:p-8 pt-20 md:pt-24 lg:pt-28">
				<div className="space-y-6">
					{/* Header row: Invite button on left, member count on right */}
					<div className="flex items-center justify-between">
						<div className="flex items-center gap-2">
							{canInvite && (
								<CreateInviteDialog
									roles={roles}
									onCreateInvite={handleCreateInvite}
									searchSpaceId={searchSpaceId}
								/>
							)}
							{canInvite && activeInvites.length > 0 && (
								<AllInvitesDialog invites={activeInvites} onRevokeInvite={handleRevokeInvite} />
							)}
						</div>
						<p className="hidden md:block text-sm text-muted-foreground">
							{members.length} {members.length === 1 ? "member" : "members"}
						</p>
					</div>

					{/* Members & Invites Table */}
					<div className="rounded-lg border border-border/40 bg-background overflow-hidden">
						<Table className="table-fixed w-full">
							<TableHeader>
								<TableRow className="hover:bg-transparent border-b border-border/40">
									<TableHead className="w-[45%] px-4 md:px-6 border-r border-border/40">
										<span className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground/70">
											<User size={14} className="opacity-60 text-muted-foreground" />
											Name
										</span>
									</TableHead>
									<TableHead className="hidden md:table-cell w-[25%] border-r border-border/40">
										<span className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground/70">
											<Clock size={14} className="opacity-60 text-muted-foreground" />
											Last logged in
										</span>
									</TableHead>
									<TableHead className="w-[30%] px-4 md:px-6">
										<span className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground/70 justify-end">
											<ShieldUser size={14} className="opacity-60 text-muted-foreground" />
											Role
										</span>
									</TableHead>
								</TableRow>
							</TableHeader>
							<TableBody>
								{owners.map((member, index) => (
									<MemberRow
										key={`member-${member.id}`}
										member={member}
										roles={roles}
										canManageRoles={canManageRoles}
										canRemove={canRemove}
										onUpdateRole={handleUpdateMember}
										onRemoveMember={handleRemoveMember}
										searchSpaceId={searchSpaceId}
										index={index}
									/>
								))}
								{paginatedMembers.map((member, index) => (
									<MemberRow
										key={`member-${member.id}`}
										member={member}
										roles={roles}
										canManageRoles={canManageRoles}
										canRemove={canRemove}
										onUpdateRole={handleUpdateMember}
										onRemoveMember={handleRemoveMember}
										searchSpaceId={searchSpaceId}
										index={owners.length + index}
									/>
								))}
								{members.length === 0 && (
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

					{/* Pagination */}
					{totalItems > PAGE_SIZE && (
						<motion.div
							className="flex items-center justify-end gap-3 py-3 px-2"
							initial={{ opacity: 0, y: 10 }}
							animate={{ opacity: 1, y: 0 }}
							transition={{ type: "spring", stiffness: 300, damping: 30, delay: 0.3 }}
						>
							<span className="text-sm text-muted-foreground tabular-nums">
								{displayStart}-{displayEnd} of {totalItems}
							</span>
							<div className="flex items-center gap-1">
								<Button
									variant="ghost"
									size="icon"
									className="h-8 w-8 disabled:opacity-40"
									onClick={() => setPageIndex(0)}
									disabled={!canPrev}
									aria-label="Go to first page"
								>
									<ChevronFirst size={18} strokeWidth={2} />
								</Button>
								<Button
									variant="ghost"
									size="icon"
									className="h-8 w-8 disabled:opacity-40"
									onClick={() => setPageIndex((i) => Math.max(0, i - 1))}
									disabled={!canPrev}
									aria-label="Go to previous page"
								>
									<ChevronLeft size={18} strokeWidth={2} />
								</Button>
								<Button
									variant="ghost"
									size="icon"
									className="h-8 w-8 disabled:opacity-40"
									onClick={() => setPageIndex((i) => (canNext ? i + 1 : i))}
									disabled={!canNext}
									aria-label="Go to next page"
								>
									<ChevronRight size={18} strokeWidth={2} />
								</Button>
								<Button
									variant="ghost"
									size="icon"
									className="h-8 w-8 disabled:opacity-40"
									onClick={() => setPageIndex(lastPage)}
									disabled={!canNext}
									aria-label="Go to last page"
								>
									<ChevronLast size={18} strokeWidth={2} />
								</Button>
							</div>
						</motion.div>
					)}
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
	searchSpaceId,
	index,
}: {
	member: Membership;
	roles: Role[];
	canManageRoles: boolean;
	canRemove: boolean;
	onUpdateRole: (membershipId: number, roleId: number | null) => Promise<Membership>;
	onRemoveMember: (membershipId: number) => Promise<boolean>;
	searchSpaceId: number;
	index: number;
}) {
	const router = useRouter();
	const initials = getAvatarInitials(member);
	const avatarColor = getAvatarColor(member.user_id);
	const displayName = member.user_display_name || member.user_email || "Unknown";
	const roleName = member.is_owner ? "Owner" : member.role?.name || "No role";
	const showActions = !member.is_owner && (canManageRoles || canRemove);

	return (
		<motion.tr
			initial={{ opacity: 0 }}
			animate={{ opacity: 1, transition: { duration: 0.2, delay: index * 0.02 } }}
			className="border-b border-border/40 transition-colors hover:bg-muted/30"
		>
			<TableCell className="w-[45%] py-2.5 px-4 md:px-6 max-w-0 border-r border-border/40">
				<div className="flex items-center gap-3">
					<div className="shrink-0">
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
					</div>
					<div className="min-w-0">
						<p className="font-medium text-sm truncate select-text">{displayName}</p>
						{member.user_display_name && member.user_email && (
							<p className="text-xs text-muted-foreground truncate select-text">
								{member.user_email}
							</p>
						)}
					</div>
				</div>
			</TableCell>

			<TableCell className="hidden md:table-cell w-[25%] py-2.5 text-sm text-foreground border-r border-border/40">
				{formatRelativeDate(member.joined_at)}
			</TableCell>

			<TableCell className="w-[30%] text-right py-2.5 px-4 md:px-6">
				{showActions ? (
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
						<DropdownMenuContent
							align="end"
							onCloseAutoFocus={(e) => e.preventDefault()}
							className="min-w-[120px] bg-muted dark:border dark:border-neutral-700"
						>
							{canManageRoles &&
								roles
									.filter((r) => r.name !== "Owner")
									.map((role) => (
										<DropdownMenuItem
											key={role.id}
											onClick={() => onUpdateRole(member.id, role.id)}
										>
											Make {role.name}
										</DropdownMenuItem>
									))}
							{canRemove && (
								<AlertDialog>
									<AlertDialogTrigger asChild>
										<DropdownMenuItem
											className="text-destructive focus:text-destructive"
											onSelect={(e) => e.preventDefault()}
										>
											Remove
										</DropdownMenuItem>
									</AlertDialogTrigger>
									<AlertDialogContent>
										<AlertDialogHeader>
											<AlertDialogTitle>Remove member?</AlertDialogTitle>
											<AlertDialogDescription>
												This will remove <span className="font-medium">{member.user_email}</span>{" "}
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
							<DropdownMenuSeparator className="dark:bg-neutral-700" />
							<DropdownMenuItem
								onClick={() =>
									router.push(`/dashboard/${searchSpaceId}/settings?section=team-roles`)
								}
							>
								Manage Roles
							</DropdownMenuItem>
						</DropdownMenuContent>
					</DropdownMenu>
				) : (
					<span className="text-sm text-foreground">{roleName}</span>
				)}
			</TableCell>
		</motion.tr>
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

	const assignableRoles = useMemo(() => roles.filter((r) => r.name !== "Owner"), [roles]);
	const defaultRole = useMemo(() => assignableRoles.find((r) => r.is_default), [assignableRoles]);

	useEffect(() => {
		if (defaultRole && !roleId) {
			setRoleId(defaultRole.id.toString());
		}
	}, [defaultRole, roleId]);

	const handleCreate = async () => {
		setCreating(true);
		try {
			const data: CreateInviteRequest["data"] = {};
			if (name) data.name = name;
			if (roleId) data.role_id = Number(roleId);
			if (maxUses) data.max_uses = Number(maxUses);
			if (expiresAt) data.expires_at = expiresAt.toISOString();

			const invite = await onCreateInvite(data);
			setCreatedInvite(invite);

			const roleName = roleId ? roles.find((r) => r.id.toString() === roleId)?.name : undefined;
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
		setRoleId(defaultRole?.id.toString() ?? "");
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
				<Button
					variant="outline"
					className="gap-2 bg-black text-white dark:bg-white dark:text-black hover:bg-black/90 dark:hover:bg-white/90"
				>
					<UserPlus className="h-4 w-4" />
					Invite members
				</Button>
			</DialogTrigger>
			<DialogContent
				className="w-[92vw] max-w-[92vw] sm:max-w-md p-4 md:p-6 select-none"
				onOpenAutoFocus={(e) => e.preventDefault()}
			>
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
									{copiedLink ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
								</Button>
							</div>
							<div className="flex flex-wrap gap-2 text-sm text-muted-foreground">
								<span className="flex items-center gap-1">
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
										<SelectValue placeholder="Assign a role" />
									</SelectTrigger>
									<SelectContent>
										{assignableRoles.map((role) => (
											<SelectItem key={role.id} value={role.id.toString()}>
												<span className="flex items-center gap-2">
													{role.name}
													{role.is_default && (
														<span className="text-xs text-muted-foreground">(default)</span>
													)}
												</span>
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

// ============ All Invites Dialog ============

function AllInvitesDialog({
	invites,
	onRevokeInvite,
}: {
	invites: Invite[];
	onRevokeInvite: (inviteId: number) => Promise<boolean>;
}) {
	const [copiedId, setCopiedId] = useState<number | null>(null);

	const copyLink = (invite: Invite) => {
		const link = `${window.location.origin}/invite/${invite.invite_code}`;
		navigator.clipboard.writeText(link);
		setCopiedId(invite.id);
		toast.success("Invite link copied");
		setTimeout(() => setCopiedId(null), 2000);
	};

	return (
		<Dialog>
			<DialogTrigger asChild>
				<Button variant="outline" className="gap-2">
					<Link2 className="h-4 w-4 rotate-315" />
					Active invites
					<span className="inline-flex items-center justify-center h-5 min-w-5 px-1 rounded-full bg-muted text-xs font-medium">
						{invites.length}
					</span>
				</Button>
			</DialogTrigger>
			<DialogContent className="w-[92vw] max-w-[92vw] sm:max-w-lg p-4 md:p-6 select-none">
				<DialogHeader>
					<DialogTitle className="flex items-center gap-2">Active Invite Links</DialogTitle>
					<DialogDescription>
						{invites.length} active {invites.length === 1 ? "invite" : "invites"}. Copy a link or
						revoke access.
					</DialogDescription>
				</DialogHeader>
				<div className="max-h-[320px] overflow-y-auto -mx-1 px-1 space-y-3 py-2">
					{invites.map((invite) => (
						<div key={invite.id} className="rounded-lg border border-border/40 p-3 space-y-2.5">
							<div className="flex items-center justify-between gap-2">
								<div className="flex items-center gap-2 min-w-0">
									<p className="text-sm font-medium truncate">{invite.name || "Unnamed invite"}</p>
									<div className="flex flex-wrap gap-x-2 text-xs text-muted-foreground shrink-0">
										{invite.role?.name && (
											<span className="rounded bg-muted px-1.5 py-0.5">{invite.role.name}</span>
										)}
										{invite.max_uses != null && (
											<span className="flex items-center gap-1 rounded bg-muted px-1.5 py-0.5">
												<Hash className="h-3 w-3" />
												{invite.uses_count}/{invite.max_uses}
											</span>
										)}
										{invite.expires_at && (
											<span className="flex items-center gap-1 rounded bg-muted px-1.5 py-0.5">
												<Clock className="h-3 w-3" />
												{new Date(invite.expires_at).toLocaleDateString()}
											</span>
										)}
									</div>
								</div>
								<AlertDialog>
									<AlertDialogTrigger asChild>
										<Button
											variant="ghost"
											size="icon"
											className="h-7 w-7 shrink-0 text-muted-foreground hover:text-destructive"
										>
											<Trash2 className="h-3.5 w-3.5" />
										</Button>
									</AlertDialogTrigger>
									<AlertDialogContent>
										<AlertDialogHeader>
											<AlertDialogTitle>Revoke invite?</AlertDialogTitle>
											<AlertDialogDescription>
												This will permanently delete this invite link. Anyone with this link will no
												longer be able to join.
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
							</div>
							<div className="flex items-center gap-2 rounded-md bg-muted p-2">
								<div className="flex-1 min-w-0 overflow-x-auto scrollbar-hide">
									<code className="text-sm select-all whitespace-nowrap">
										{typeof window !== "undefined"
											? `${window.location.origin}/invite/${invite.invite_code}`
											: `/invite/${invite.invite_code}`}
									</code>
								</div>
								<Button
									variant="ghost"
									size="sm"
									className="shrink-0"
									onClick={() => copyLink(invite)}
								>
									{copiedId === invite.id ? (
										<Check className="h-4 w-4" />
									) : (
										<Copy className="h-4 w-4" />
									)}
								</Button>
							</div>
						</div>
					))}
				</div>
			</DialogContent>
		</Dialog>
	);
}
