"use client";

import { Link2Off } from "lucide-react";

interface PublicChatSnapshotsEmptyStateProps {
	title?: string;
	description?: string;
}

export function PublicChatSnapshotsEmptyState({
	title = "No public chat links",
	description = "When you create public links to share chats, they will appear here.",
}: PublicChatSnapshotsEmptyStateProps) {
	return (
		<div className="flex flex-col items-center justify-center py-12 text-center">
			<div className="rounded-full bg-muted p-3 mb-4">
				<Link2Off className="h-6 w-6 text-muted-foreground" />
			</div>
			<h3 className="text-sm font-medium text-foreground mb-1">{title}</h3>
			<p className="text-xs text-muted-foreground max-w-sm">{description}</p>
		</div>
	);
}
