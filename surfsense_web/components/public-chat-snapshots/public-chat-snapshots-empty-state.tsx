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
			<h3 className="text-sm md:text-base font-semibold mb-2">{title}</h3>
			<p className="text-[11px] md:text-xs text-muted-foreground max-w-sm">{description}</p>
		</div>
	);
}
