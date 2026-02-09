"use client";

import type { PublicChatSnapshotDetail } from "@/contracts/types/chat-threads.types";
import { PublicChatSnapshotRow } from "./public-chat-snapshot-row";
import { PublicChatSnapshotsEmptyState } from "./public-chat-snapshots-empty-state";

interface PublicChatSnapshotsListProps {
	snapshots: PublicChatSnapshotDetail[];
	canDelete: boolean;
	onCopy: (snapshot: PublicChatSnapshotDetail) => void;
	onDelete: (snapshot: PublicChatSnapshotDetail) => void;
	deletingId?: number;
	memberMap: Map<string, { name: string; email?: string; avatarUrl?: string }>;
}

export function PublicChatSnapshotsList({
	snapshots,
	canDelete,
	onCopy,
	onDelete,
	deletingId,
	memberMap,
}: PublicChatSnapshotsListProps) {
	if (snapshots.length === 0) {
		return <PublicChatSnapshotsEmptyState />;
	}

	return (
		<div className="grid gap-3 grid-cols-1 sm:grid-cols-2 xl:grid-cols-3">
			{snapshots.map((snapshot) => (
				<PublicChatSnapshotRow
					key={snapshot.id}
					snapshot={snapshot}
					canDelete={canDelete}
					onCopy={onCopy}
					onDelete={onDelete}
					isDeleting={deletingId === snapshot.id}
					memberMap={memberMap}
				/>
			))}
		</div>
	);
}
