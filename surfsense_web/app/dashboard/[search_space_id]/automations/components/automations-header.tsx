"use client";
import { MessageSquarePlus, SquarePen } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

interface AutomationsHeaderProps {
	searchSpaceId: number;
	total: number;
	loading: boolean;
	canCreate: boolean;
	/**
	 * Render the header's Create CTA. Defaults to true; the empty state owns
	 * the primary CTA on its own card, so the orchestrator turns this off
	 * there to avoid a duplicate button.
	 */
	showCreateCta?: boolean;
	/**
	 * Disable the create CTAs when the search space's models aren't billable
	 * for automations (free/Auto). When set, a tooltip explains why and the
	 * buttons render disabled rather than as links.
	 */
	createDisabled?: boolean;
	disabledReason?: string;
}

const DEFAULT_DISABLED_REASON =
	"Automations need a premium or your own (BYOK) model. Update your model settings to enable.";

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
	showCreateCta = true,
	createDisabled = false,
	disabledReason,
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
					{createDisabled ? (
						<>
							<DisabledCta
								variant="outline"
								icon={<SquarePen className="mr-2 h-4 w-4" />}
								label="Create manually"
								reason={disabledReason ?? DEFAULT_DISABLED_REASON}
							/>
							<DisabledCta
								icon={<MessageSquarePlus className="mr-2 h-4 w-4" />}
								label="Create via chat"
								reason={disabledReason ?? DEFAULT_DISABLED_REASON}
							/>
						</>
					) : (
						<>
							<Button asChild size="sm" variant="outline">
								<Link href={`/dashboard/${searchSpaceId}/automations/new`}>
									<SquarePen className="mr-2 h-4 w-4" />
									Create manually
								</Link>
							</Button>
							<Button asChild size="sm">
								<Link href={`/dashboard/${searchSpaceId}/new-chat`}>
									<MessageSquarePlus className="mr-2 h-4 w-4" />
									Create via chat
								</Link>
							</Button>
						</>
					)}
				</div>
			)}
		</div>
	);
}

function DisabledCta({
	icon,
	label,
	reason,
	variant,
}: {
	icon: ReactNode;
	label: string;
	reason: string;
	variant?: "outline";
}) {
	return (
		<Tooltip>
			<TooltipTrigger asChild>
				{/* aria-disabled (not `disabled`) keeps the button focusable so the
				    tooltip is reachable by hover and keyboard; onClick is a no-op. */}
				<Button
					size="sm"
					variant={variant}
					aria-disabled
					className="cursor-not-allowed opacity-50"
					onClick={(event) => event.preventDefault()}
				>
					{icon}
					{label}
				</Button>
			</TooltipTrigger>
			<TooltipContent className="max-w-xs">{reason}</TooltipContent>
		</Tooltip>
	);
}
