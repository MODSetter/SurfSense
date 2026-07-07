"use client";
import Link from "next/link";
import { Button } from "@/components/ui/button";

interface AutomationsHeaderProps {
	workspaceId: number;
	total: number;
	loading: boolean;
	canCreate: boolean;
	/**
	 * Render the header's Create CTA. Defaults to true; the empty state owns
	 * the primary CTA on its own card, so the orchestrator turns this off
	 * there to avoid a duplicate button.
	 */
	showCreateCta?: boolean;
}

/**
 * Page header: title + count + "Create via chat" CTA. Creation is intent-driven
 * (the create_automation tool runs inside chat with a HITL approval card), so
 * the CTA links to a new chat rather than opening a form. Model eligibility is
 * handled per-automation in the builder + approval card, not gated here.
 */
export function AutomationsHeader({
	workspaceId,
	total,
	loading,
	canCreate,
	showCreateCta = true,
}: AutomationsHeaderProps) {
	return (
		<div className="flex items-center justify-between gap-4 flex-wrap">
			<div className="flex items-baseline gap-3">
				<h1 className="text-xl md:text-2xl font-semibold text-foreground">Automations</h1>
				{!loading && (
					<span className="text-sm text-muted-foreground">
						{total} {total === 1 ? "automation" : "automations"}
					</span>
				)}
			</div>
			{canCreate && showCreateCta && (
				<div className="flex items-center gap-2">
					<Button
						asChild
						size="sm"
						variant="ghost"
						className="justify-start rounded-md bg-muted px-3 hover:bg-accent"
					>
						<Link href={`/dashboard/${workspaceId}/automations/new`}>Create manually</Link>
					</Button>
					<Button asChild size="sm">
						<Link href={`/dashboard/${workspaceId}/new-chat`}>Create via chat</Link>
					</Button>
				</div>
			)}
		</div>
	);
}
