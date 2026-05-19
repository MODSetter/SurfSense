import { BellOff } from "lucide-react";

export function AnnouncementsEmptyState() {
	return (
		<div className="flex flex-col items-center justify-center py-12 text-center">
			<div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-muted">
				<BellOff className="h-5 w-5 text-muted-foreground" />
			</div>
			<h3 className="text-sm font-semibold">Nothing new yet</h3>
			<p className="mt-1 max-w-xs text-xs text-muted-foreground">
				You're all caught up! New updates will appear here.
			</p>
		</div>
	);
}
