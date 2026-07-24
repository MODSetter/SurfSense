"use client";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import type { Automation } from "@/contracts/types/automation.types";

interface AutomationEditHeaderProps {
	automation: Automation;
	workspaceId: number;
	modeSwitcher?: ReactNode;
}

export function AutomationEditHeader({
	automation,
	workspaceId,
	modeSwitcher,
}: AutomationEditHeaderProps) {
	const detailHref = `/dashboard/${workspaceId}/automations/${automation.id}`;

	return (
		<div className="space-y-3">
			<Button asChild variant="ghost" size="sm" className="-ml-2 h-auto px-2 py-1">
				<Link href={detailHref} className="text-xs text-muted-foreground">
					<ArrowLeft className="mr-1.5 h-3.5 w-3.5" />
					Back to automation
				</Link>
			</Button>
			<div className="flex flex-wrap items-center justify-between gap-3">
				<h1 className="text-xl md:text-2xl font-semibold text-foreground wrap-break-word">
					Edit automation
				</h1>
				{modeSwitcher ? <div className="ml-auto">{modeSwitcher}</div> : null}
			</div>
		</div>
	);
}
