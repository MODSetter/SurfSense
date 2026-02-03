"use client";

import { Copy, MessageSquare, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { PublicChatSnapshotDetail } from "@/contracts/types/chat-threads.types";

interface PublicChatSnapshotRowProps {
	snapshot: PublicChatSnapshotDetail;
	canDelete: boolean;
	onCopy: (snapshot: PublicChatSnapshotDetail) => void;
	onDelete: (snapshot: PublicChatSnapshotDetail) => void;
	isDeleting?: boolean;
}

export function PublicChatSnapshotRow({
	snapshot,
	canDelete,
	onCopy,
	onDelete,
	isDeleting = false,
}: PublicChatSnapshotRowProps) {
	const formattedDate = new Date(snapshot.created_at).toLocaleDateString(undefined, {
		year: "numeric",
		month: "short",
		day: "numeric",
	});

	return (
		<div className="flex items-center justify-between py-3 px-4 border-b last:border-b-0 hover:bg-muted/50 transition-colors">
			<div className="flex-1 min-w-0 mr-4">
				<h4 className="text-sm font-medium truncate" title={snapshot.thread_title}>
					{snapshot.thread_title}
				</h4>
				<div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
					<span>{formattedDate}</span>
					<span className="flex items-center gap-1">
						<MessageSquare className="h-3 w-3" />
						{snapshot.message_count}
					</span>
				</div>
			</div>
			<div className="flex items-center gap-2">
				<Button
					variant="ghost"
					size="sm"
					onClick={() => onCopy(snapshot)}
					className="h-8 px-2"
					title="Copy link"
				>
					<Copy className="h-4 w-4" />
				</Button>
				{canDelete && (
					<Button
						variant="ghost"
						size="sm"
						onClick={() => onDelete(snapshot)}
						disabled={isDeleting}
						className="h-8 px-2 text-destructive hover:text-destructive hover:bg-destructive/10"
						title="Delete link"
					>
						<Trash2 className="h-4 w-4" />
					</Button>
				)}
			</div>
		</div>
	);
}
