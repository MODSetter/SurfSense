"use client";
import { MessageSquarePlus } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

interface AutomationsHeaderProps {
	searchSpaceId: number;
	total: number;
	loading: boolean;
	canCreate: boolean;
}

/**
 * Page header: title + count + "Create via chat" CTA. Creation is intent-driven
 * (the create_automation tool runs inside chat with a HITL approval card), so
 * the CTA links to a new chat rather than opening a form.
 */
export function AutomationsHeader({
	searchSpaceId,
	total,
	loading,
	canCreate,
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
			{canCreate && (
				<Button asChild size="sm">
					<Link href={`/dashboard/${searchSpaceId}/new-chat`}>
						<MessageSquarePlus className="mr-2 h-4 w-4" />
						Create via chat
					</Link>
				</Button>
			)}
		</div>
	);
}
