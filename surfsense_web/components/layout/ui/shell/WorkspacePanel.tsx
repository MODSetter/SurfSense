import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface WorkspacePanelProps {
	children: ReactNode;
	className?: string;
	contentClassName?: string;
}

/**
 * Full workspace area to the right of the left rail/sidebar.
 * Use this when a route should own the whole workspace instead of rendering
 * inside the normal TabBar/Header/main/right-panel chrome.
 */
export function WorkspacePanel({ children, className, contentClassName }: WorkspacePanelProps) {
	return (
		<main
			className={cn(
				"relative isolate flex min-w-0 flex-1 flex-col overflow-hidden bg-panel",
				className
			)}
		>
			<div className="flex min-h-0 flex-1 items-center justify-center overflow-auto px-4 py-8">
				<div className={cn("w-full max-w-md", contentClassName)}>{children}</div>
			</div>
		</main>
	);
}
