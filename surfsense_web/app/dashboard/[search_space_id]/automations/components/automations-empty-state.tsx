"use client";
import { MessageSquarePlus, SquarePen, Workflow } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

interface AutomationsEmptyStateProps {
	searchSpaceId: number;
	canCreate: boolean;
}

/**
 * Zero-state for the automations list. The primary CTA points to a new
 * chat — creation happens via the ``create_automation`` HITL tool, not a
 * "new automation" form. We surface the chat path explicitly so users
 * don't go hunting for an "add" button that doesn't exist.
 */
export function AutomationsEmptyState({ searchSpaceId, canCreate }: AutomationsEmptyStateProps) {
	return (
		<div className="rounded-lg border border-dashed border-border/60 bg-muted/20 px-6 py-12 text-center">
			<div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-muted text-muted-foreground">
				<Workflow className="h-6 w-6" aria-hidden />
			</div>
			<h3 className="mt-4 text-base font-semibold text-foreground">No automations yet</h3>
			<p className="mt-1 text-sm text-muted-foreground max-w-md mx-auto">
				Automations let SurfSense run agent tasks on a schedule. Describe what you want in chat and
				SurfSense drafts the automation for your approval.
			</p>
			{canCreate ? (
				<div className="mt-6 flex items-center justify-center gap-2 flex-wrap">
					<Button asChild>
						<Link href={`/dashboard/${searchSpaceId}/new-chat`}>
							<MessageSquarePlus className="mr-2 h-4 w-4" />
							Create via chat
						</Link>
					</Button>
					<Button asChild variant="outline">
						<Link href={`/dashboard/${searchSpaceId}/automations/new`}>
							<SquarePen className="mr-2 h-4 w-4" />
							Create manually
						</Link>
					</Button>
				</div>
			) : (
				<p className="mt-6 text-xs text-muted-foreground">
					You don't have permission to create automations in this search space.
				</p>
			)}
		</div>
	);
}
