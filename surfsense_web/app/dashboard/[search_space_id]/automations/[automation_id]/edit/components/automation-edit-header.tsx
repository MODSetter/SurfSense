"use client";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import type { Automation } from "@/contracts/types/automation.types";

interface AutomationEditHeaderProps {
	automation: Automation;
	searchSpaceId: number;
}

export function AutomationEditHeader({ automation, searchSpaceId }: AutomationEditHeaderProps) {
	const detailHref = `/dashboard/${searchSpaceId}/automations/${automation.id}`;

	return (
		<div className="space-y-3">
			<Button asChild variant="ghost" size="sm" className="-ml-2 h-auto px-2 py-1">
				<Link href={detailHref} className="text-xs text-muted-foreground">
					<ArrowLeft className="mr-1.5 h-3.5 w-3.5" />
					Back to automation
				</Link>
			</Button>
			<div>
				<h1 className="text-xl md:text-2xl font-semibold text-foreground wrap-break-word">
					Edit automation
				</h1>
				<p className="text-sm text-muted-foreground mt-1">{automation.name}</p>
			</div>
		</div>
	);
}
