"use client";
import { Info } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

interface UnattendedToggleProps {
	checked: boolean;
	onChange: (checked: boolean) => void;
}

/**
 * Maps to ``auto_approve_all`` on every agent task. Automations run with no one
 * watching, so this defaults ON; turning it off means any approval prompt the
 * agent raises is rejected and the step can stall.
 */
export function UnattendedToggle({ checked, onChange }: UnattendedToggleProps) {
	return (
		<div className="flex items-start justify-between gap-3 rounded-lg border border-border/60 bg-background px-3 py-3">
			<div className="space-y-0.5 min-w-0">
				<div className="flex items-center gap-1.5">
					<span className="text-sm font-medium text-foreground">
						Run without asking for approvals
					</span>
					<Tooltip>
						<TooltipTrigger asChild>
							<button type="button" aria-label="More info" className="text-muted-foreground">
								<Info className="h-3.5 w-3.5" />
							</button>
						</TooltipTrigger>
						<TooltipContent className="max-w-xs">
							Automations run unattended. With this off, any approval the agent asks for is
							rejected, which can stall a step.
						</TooltipContent>
					</Tooltip>
				</div>
				<p className="text-xs text-muted-foreground">
					Auto-approve actions the agent would normally pause to confirm.
				</p>
			</div>
			<Switch
				checked={checked}
				onCheckedChange={onChange}
				aria-label="Run without asking for approvals"
			/>
		</div>
	);
}
