"use client";
import { Switch } from "@/components/ui/switch";

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
		<div className="flex items-start justify-between gap-3 rounded-md bg-transparent">
			<div className="space-y-0.5 min-w-0">
				<div className="flex items-center gap-1.5">
					<span className="text-sm font-medium text-foreground">
						Run without asking for approvals
					</span>
				</div>
				<p className="text-xs text-muted-foreground">
					Tasks run automatically without asking for confirmation
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
