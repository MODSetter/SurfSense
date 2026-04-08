import { BellOff } from "lucide-react";

export function AnnouncementsEmptyState() {
	return (
		<div className="flex flex-col items-center justify-center py-16 text-center">
			<div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted mb-4">
				<BellOff className="h-7 w-7 text-muted-foreground" />
			</div>
			<h3 className="text-lg font-semibold">No announcements</h3>
			<p className="mt-1 text-sm text-muted-foreground max-w-sm">
				You're all caught up! New announcements will appear here.
			</p>
		</div>
	);
}
