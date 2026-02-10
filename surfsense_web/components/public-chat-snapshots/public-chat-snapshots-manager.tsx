"use client";

import { useAtomValue } from "jotai";
import { AlertCircle, Info } from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import { toast } from "sonner";
import { membersAtom, myAccessAtom } from "@/atoms/members/members-query.atoms";
import { deletePublicChatSnapshotMutationAtom } from "@/atoms/public-chat-snapshots/public-chat-snapshots-mutation.atoms";
import { publicChatSnapshotsAtom } from "@/atoms/public-chat-snapshots/public-chat-snapshots-query.atoms";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { PublicChatSnapshotDetail } from "@/contracts/types/chat-threads.types";
import { PublicChatSnapshotsList } from "./public-chat-snapshots-list";

interface PublicChatSnapshotsManagerProps {
	searchSpaceId: number;
}

export function PublicChatSnapshotsManager({
	searchSpaceId: _searchSpaceId,
}: PublicChatSnapshotsManagerProps) {
	const [deletingId, setDeletingId] = useState<number | undefined>();

	// Data fetching
	const { data: snapshotsData, isLoading, isError } = useAtomValue(publicChatSnapshotsAtom);

	// Members for user resolution
	const { data: members } = useAtomValue(membersAtom);
	const memberMap = useMemo(() => {
		const map = new Map<string, { name: string; email?: string; avatarUrl?: string }>();
		if (members) {
			for (const m of members) {
				map.set(m.user_id, {
					name: m.user_display_name || m.user_email || "Unknown",
					email: m.user_email || undefined,
					avatarUrl: m.user_avatar_url || undefined,
				});
			}
		}
		return map;
	}, [members]);

	// Permissions
	const { data: access } = useAtomValue(myAccessAtom);
	const canView = useMemo(() => {
		if (!access) return false;
		if (access.is_owner) return true;
		return access.permissions?.includes("public_sharing:view") ?? false;
	}, [access]);

	const canDelete = useMemo(() => {
		if (!access) return false;
		if (access.is_owner) return true;
		return access.permissions?.includes("public_sharing:delete") ?? false;
	}, [access]);

	// Mutations
	const { mutateAsync: deleteSnapshot } = useAtomValue(deletePublicChatSnapshotMutationAtom);

	// Handlers
	const handleCopy = useCallback((snapshot: PublicChatSnapshotDetail) => {
		const publicUrl = `${window.location.origin}/public/${snapshot.share_token}`;
		navigator.clipboard.writeText(publicUrl);
	}, []);

	const handleDelete = useCallback(
		async (snapshot: PublicChatSnapshotDetail) => {
			try {
				setDeletingId(snapshot.id);
				await deleteSnapshot({
					thread_id: snapshot.thread_id,
					snapshot_id: snapshot.id,
				});
			} catch (error) {
				console.error("Failed to delete snapshot:", error);
			} finally {
				setDeletingId(undefined);
			}
		},
		[deleteSnapshot]
	);

	// Loading state
	if (isLoading) {
		return (
			<div className="space-y-4 md:space-y-5">
				{/* Info alert skeleton */}
				<Skeleton className="h-12 w-full rounded-lg" />

				{/* Cards grid skeleton */}
				<div className="grid gap-3 grid-cols-1 sm:grid-cols-2">
					{["skeleton-a", "skeleton-b", "skeleton-c"].map((key) => (
						<Card key={key} className="border-border/60">
							<CardContent className="p-4 flex flex-col gap-3">
								{/* Header: Title */}
								<div className="flex items-start justify-between gap-2">
									<Skeleton className="h-4 w-36 md:w-44" />
								</div>
								{/* Message count badge */}
								<div className="flex items-center gap-1.5">
									<Skeleton className="h-5 w-24 rounded-full" />
								</div>
								{/* URL skeleton */}
								<Skeleton className="h-3 w-full rounded" />
								{/* Footer: Date + Creator */}
								<div className="flex items-center gap-2 pt-2 border-t border-border/40">
									<Skeleton className="h-3 w-20" />
									<Skeleton className="h-4 w-4 rounded-full" />
									<Skeleton className="h-3 w-16" />
								</div>
							</CardContent>
						</Card>
					))}
				</div>
			</div>
		);
	}

	// Error state
	if (isError) {
		return (
			<Alert variant="destructive">
				<AlertCircle className="h-4 w-4" />
				<AlertDescription>
					Failed to load public chat links. Please try again later.
				</AlertDescription>
			</Alert>
		);
	}

	// Permission denied
	if (!canView) {
		return (
			<Alert variant="destructive">
				<Info className="h-4 w-4" />
				<AlertDescription>
					You don't have permission to view public chat links in this search space.
				</AlertDescription>
			</Alert>
		);
	}

	const snapshots = snapshotsData?.snapshots ?? [];

	return (
		<div className="space-y-4 md:space-y-5">
			<Alert className="bg-muted/50 py-3 md:py-4">
				<Info className="h-3 w-3 md:h-4 md:w-4 shrink-0" />
				<AlertDescription className="text-xs md:text-sm">
					Public chat links allow anyone with the URL to view a snapshot of a chat. These links do
					not update when the original chat changes.
				</AlertDescription>
			</Alert>

			<PublicChatSnapshotsList
				snapshots={snapshots}
				canDelete={canDelete}
				onCopy={handleCopy}
				onDelete={handleDelete}
				deletingId={deletingId}
				memberMap={memberMap}
			/>
		</div>
	);
}
