"use client";

import { useAtomValue } from "jotai";
import { AlertCircle, Globe, Info } from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import { toast } from "sonner";
import { myAccessAtom } from "@/atoms/members/members-query.atoms";
import { deletePublicChatSnapshotMutationAtom } from "@/atoms/public-chat-snapshots/public-chat-snapshots-mutation.atoms";
import { publicChatSnapshotsAtom } from "@/atoms/public-chat-snapshots/public-chat-snapshots-query.atoms";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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
		toast.success("Link copied to clipboard");
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
			<div className="space-y-4 md:space-y-6">
				<Card>
					<CardHeader className="px-3 md:px-6 pt-3 md:pt-6 pb-2 md:pb-3">
						<Skeleton className="h-5 md:h-6 w-36 md:w-48" />
						<Skeleton className="h-3 md:h-4 w-full max-w-md mt-2" />
					</CardHeader>
					<CardContent className="px-3 md:px-6 pb-3 md:pb-6">
						<Skeleton className="h-24 w-full" />
					</CardContent>
				</Card>
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
		<div className="space-y-4 md:space-y-6">
			<Alert className="py-3 md:py-4">
				<Globe className="h-3 w-3 md:h-4 md:w-4 shrink-0" />
				<AlertDescription className="text-xs md:text-sm">
					Public chat links allow anyone with the URL to view a snapshot of a chat. These links do
					not update when the original chat changes.
				</AlertDescription>
			</Alert>

			<Card>
				<CardHeader className="px-3 md:px-6 pt-3 md:pt-6 pb-2 md:pb-3">
					<CardTitle className="text-base md:text-lg flex items-center gap-2">
						<Globe className="h-4 w-4 md:h-5 md:w-5" />
						Public Chat Links
					</CardTitle>
					<CardDescription className="text-xs md:text-sm">
						Manage public links to chats in this search space.
					</CardDescription>
				</CardHeader>
				<CardContent className="px-3 md:px-6 pb-3 md:pb-6">
					<PublicChatSnapshotsList
						snapshots={snapshots}
						canDelete={canDelete}
						onCopy={handleCopy}
						onDelete={handleDelete}
						deletingId={deletingId}
					/>
				</CardContent>
			</Card>
		</div>
	);
}
