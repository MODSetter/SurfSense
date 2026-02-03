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
}

export function PublicChatSnapshotsList({
	snapshots,
	canDelete,
	onCopy,
	onDelete,
	deletingId,
}: PublicChatSnapshotsListProps) {
	if (snapshots.length === 0) {
		return <PublicChatSnapshotsEmptyState />;
	}

	return (
		<div className="border rounded-md divide-y">
			{snapshots.map((snapshot) => (
				<PublicChatSnapshotRow
					key={snapshot.id}
					snapshot={snapshot}
					canDelete={canDelete}
					onCopy={onCopy}
					onDelete={onDelete}
					isDeleting={deletingId === snapshot.id}
				/>
			))}
		</div>
	);
}
